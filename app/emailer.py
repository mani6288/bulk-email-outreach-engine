import re
import aiosmtplib
from email.message import EmailMessage
from .config import settings


def _looks_like_html(s: str) -> bool:
    return bool(s) and s.lstrip().startswith("<")


def _plaintext_fallback(html: str) -> str:
    """
    Very light HTML->text fallback so multipart emails always have a text part.
    We intentionally keep it simple to avoid heavy deps.
    """
    text = html
    # Convert obvious <br> and <p> to newlines
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*p\s*>", "\n\n", text)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Unescape a few common entities
    text = (text
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">"))
    # Collapse excessive whitespace
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


async def send_email(to_email: str, subject: str, body_text_or_html: str):
    """
    Sends email via SMTP.
    - If body starts with '<', we treat it as HTML and send multipart/alternative
      (plain-text fallback + HTML). Otherwise plain-text only.
    """
    msg = EmailMessage()
    msg["From"] = f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    if _looks_like_html(body_text_or_html):
        # HTML path: add text fallback first, then HTML alternative
        text_part = _plaintext_fallback(body_text_or_html)
        msg.set_content(text_part)
        msg.add_alternative(body_text_or_html, subtype="html")
    else:
        # Plain-text path
        msg.set_content(body_text_or_html)

    # Optionally respect a REPLY_TO if you add it in .env
    if getattr(settings, "REPLY_TO", None):
        msg["Reply-To"] = settings.REPLY_TO

    # Send
    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        start_tls=True,  # Gmail/most providers: 587 + STARTTLS
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
        timeout=60,
    )
