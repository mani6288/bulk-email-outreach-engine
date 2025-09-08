import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from .db import engine, Base, SessionLocal
from .models import Suppressed
from .config import settings
from .scheduler import run_scheduler
from .imap_listener import process_mailbox

app = FastAPI(title="Outreach Engine")

@app.on_event("startup")
async def startup():
    Base.metadata.create_all(bind=engine)
    # fire-and-forget scheduler
    asyncio.create_task(run_scheduler())

@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/unsubscribe", response_class=PlainTextResponse)
def unsubscribe(e: str = Query(..., description="Email to unsubscribe")):
    e = e.strip().lower()
    if not e:
        raise HTTPException(status_code=400, detail="Missing email")
    db = SessionLocal()
    try:
        db.merge(Suppressed(email=e, reason="unsubscribe"))
        db.commit()
    finally:
        db.close()
    return "You have been unsubscribed. Sorry to see you go."

@app.post("/mailbox/poll", response_class=PlainTextResponse)
def mailbox_poll():
    # Trigger IMAP poll manually (or via cron outside)
    try:
        process_mailbox()
        return "ok"
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))
