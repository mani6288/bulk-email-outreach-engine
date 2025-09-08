from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.sql import func
from .db import Base

class Contact(Base):
    __tablename__ = "contacts"
    email = Column(String, primary_key=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    company = Column(String, nullable=True)
    company_focus = Column(String, nullable=True)
    status = Column(String, nullable=False, default="no_sync")  # no_sync -> sync -> 1st_followup_sent -> 2nd_followup_sent -> cut_off -> replied/bounced/unsubscribed
    sequence_step = Column(Integer, nullable=False, default=0)  # 0=intro,1=f1,2=f2,3=cutoff
    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    last_reply_at = Column(DateTime(timezone=True), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    thread_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

class Suppressed(Base):
    __tablename__ = "suppressed_emails"
    email = Column(String, primary_key=True)
    reason = Column(String, nullable=True)  # unsubscribe | bounce | manual
    ts = Column(DateTime(timezone=True), server_default=func.now())
