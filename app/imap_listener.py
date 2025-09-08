import imaplib, email, re
from email.header import decode_header
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Contact, Suppressed
from .config import settings
from datetime import datetime, timezone

def _extract_emails(text: str):
    return re.findall(r"[\w.+-]+@[\w.-]+", text or "")

def process_mailbox():
    db: Session = SessionLocal()
    try:
        imap = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        imap.login(settings.IMAP_USERNAME, settings.IMAP_PASSWORD)
        imap.select("INBOX")
        status, messages = imap.search(None, 'UNSEEN')
        if status != "OK":
            return

        for msg_id in messages[0].split():
            _, msg_data = imap.fetch(msg_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    from_addr = email.utils.parseaddr(msg.get("From"))[1].lower()
                    subject = msg.get("Subject") or ""
                    # crude bounce detection
                    if "mailer-daemon" in from_addr or "postmaster" in from_addr:
                        # try to find original recipient
                        payload = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    payload += part.get_payload(decode=True).decode(errors="ignore")
                        else:
                            payload = msg.get_payload(decode=True).decode(errors="ignore")
                        addrs = _extract_emails(payload)
                        if addrs:
                            target = addrs[0].lower()
                            c = db.get(Contact, target)
                            if c:
                                c.status = "bounced"
                                db.add(c)
                                db.merge(Suppressed(email=target, reason="bounce"))
                                db.commit()
                    else:
                        # mark replied
                        tos = _extract_emails(msg.get("To") or "")
                        if tos:
                            target = tos[0].lower()
                            c = db.get(Contact, target)
                            if c:
                                c.status = "replied"
                                c.last_reply_at = datetime.now(timezone.utc)
                                db.add(c)
                                db.commit()
            imap.store(msg_id, '+FLAGS', '\\Seen')
        imap.close()
        imap.logout()
    finally:
        db.close()
