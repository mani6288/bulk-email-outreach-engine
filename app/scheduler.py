import asyncio
import random
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import and_, not_
from sqlalchemy.orm import Session

from .db import engine, SessionLocal, Base
from .models import Contact, Suppressed
from .config import settings
from .emailer import send_email
from .ai import build_email

# ----------------------------
# Time helpers
# ----------------------------
def now_utc():
    return datetime.now(tz=timezone.utc)

def _tz():
    # Use .env TIMEZONE if provided; else Asia/Karachi
    return getattr(settings, "TIMEZONE", "Asia/Karachi")

# ----------------------------
# Delay / Jitter helpers
# ----------------------------
def _per_email_sleep_seconds():
    base = getattr(settings, "PER_EMAIL_DELAY_SECONDS", 30)
    jmin = getattr(settings, "JITTER_MIN", 0)
    jmax = getattr(settings, "JITTER_MAX", 0)
    if jmax and jmax >= jmin:
        return max(0, base + random.uniform(jmin, jmax))
    return base

# ----------------------------
# Shared ctx builder
# ----------------------------
def _ctx_from_contact(c: Contact) -> dict:
    return {
        "first_name": c.first_name,
        "company": c.company,
        "company_focus": c.company_focus,
        "portfolio_url": settings.PORTFOLIO_URL,
        "cv_url": settings.CV_URL,
        "unsub_url": settings.UNSUB_BASE_URL,
        "email": c.email,
        "from_name": settings.FROM_NAME,
    }

# ----------------------------
# Intro batch
# ----------------------------
async def send_batch_intro():
    db: Session = SessionLocal()
    sent, skipped = 0, 0
    try:
        # build a set of suppressed for extra safety (also filter in SQL)
        suppressed = {s.email for s in db.query(Suppressed.email).all()}

        q = (
            db.query(Contact)
            .filter(
                and_(
                    Contact.status == "no_sync",
                    not_(Contact.email.in_(suppressed)) if suppressed else True,
                )
            )
            .order_by(Contact.email)
            .limit(settings.DAILY_CAP)
        )

        rows = list(q)
        print(f"[intro] picked {len(rows)} contacts (cap={settings.DAILY_CAP})")

        for c in rows:
            try:
                ctx = _ctx_from_contact(c)
                subject, body = build_email(0, ctx)
                await send_email(c.email, subject, body)

                c.status = "sync"
                c.sequence_step = 1
                c.last_sent_at = now_utc()
                db.add(c)
                db.commit()

                sent += 1
                await asyncio.sleep(_per_email_sleep_seconds())
            except Exception as e:
                db.rollback()
                skipped += 1
                print(f"[intro] ⚠️ error sending to {c.email}: {e}")

        print(f"[intro] done: sent={sent}, errors={skipped}")
    finally:
        db.close()

# ----------------------------
# Generic follow-up runner
# step_expected: 1 (FU1) / 2 (FU2) / 3 (cutoff)
# hours_delay: FU1_DELAY_HOURS / FU2_DELAY_HOURS / CUTOFF_DELAY_HOURS
# new_status: '1st_followup_sent' / '2nd_followup_sent' / 'cut_off'
# ----------------------------
async def followup(step_expected: int, hours_delay: int, new_status: str):
    db: Session = SessionLocal()
    sent, skipped = 0, 0
    try:
        threshold = now_utc() - timedelta(hours=hours_delay)

        suppressed = {s.email for s in db.query(Suppressed.email).all()}

        q = (
            db.query(Contact)
            .filter(
                and_(
                    Contact.status.in_(["sync", "1st_followup_sent", "2nd_followup_sent"]),
                    Contact.sequence_step == step_expected,
                    Contact.last_sent_at <= threshold,
                    Contact.last_reply_at.is_(None),
                    not_(Contact.email.in_(suppressed)) if suppressed else True,
                )
            )
            .order_by(Contact.last_sent_at)
            .limit(settings.DAILY_CAP)
        )

        rows = list(q)
        label = {1: "fu1", 2: "fu2", 3: "cutoff"}.get(step_expected, f"step{step_expected}")
        print(f"[{label}] picked {len(rows)} contacts (cap={settings.DAILY_CAP}, threshold={threshold.isoformat()})")

        for c in rows:
            try:
                ctx = _ctx_from_contact(c)
                subject, body = build_email(step_expected, ctx)
                await send_email(c.email, subject, body)

                c.status = new_status
                c.sequence_step = step_expected + 1
                c.last_sent_at = now_utc()
                db.add(c)
                db.commit()

                sent += 1
                await asyncio.sleep(_per_email_sleep_seconds())
            except Exception as e:
                db.rollback()
                skipped += 1
                print(f"[{label}] ⚠️ error sending to {c.email}: {e}")

        print(f"[{label}] done: sent={sent}, errors={skipped}")
    finally:
        db.close()

# ----------------------------
# Scheduler bootstrap
# ----------------------------
async def run_scheduler():
    # Ensure schema exists
    Base.metadata.create_all(bind=engine)

    tz = _tz()
    scheduler = AsyncIOScheduler(timezone=tz)

    # 1) Daily intro batch: ~09:30 PKT (04:30 UTC)
    scheduler.add_job(
        send_batch_intro,
        "cron",
        hour=9, minute=30,
        id="daily_intro_batch",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    # 2) Follow-up 1 (24h after intro) — evaluate hourly
    scheduler.add_job(
        lambda: followup(1, settings.FU1_DELAY_HOURS, "1st_followup_sent"),
        "interval",
        minutes=60,
        id="fu1_hourly",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    # 3) Follow-up 2 (48h after FU1) — evaluate hourly
    scheduler.add_job(
        lambda: followup(2, settings.FU2_DELAY_HOURS, "2nd_followup_sent"),
        "interval",
        minutes=60,
        id="fu2_hourly",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    # 4) Cutoff (7d after FU2) — check daily, evening slot
    scheduler.add_job(
        lambda: followup(3, settings.CUTOFF_DELAY_HOURS, "cut_off"),
        "cron",
        hour=18, minute=0,
        id="cutoff_daily",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    # 5) 🔥 OPTIONAL: one-time kick to send immediately after startup
    #    Uncomment to fire once ~10s after boot (remember to re-comment later)
    from datetime import timedelta as _td
    scheduler.add_job(
        send_batch_intro,
        "date",
        run_date=datetime.now(tz=scheduler.timezone) + _td(seconds=10),
        id="one_time_kick",
    )

    scheduler.start()
    print("[scheduler] started with jobs:", scheduler.get_jobs())

    # Keep loop alive (Uvicorn lifespan)
    while True:
        await asyncio.sleep(3600)
