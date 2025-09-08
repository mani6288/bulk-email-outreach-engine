from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./outreach.db")
    PORTFOLIO_URL: str = os.getenv("PORTFOLIO_URL", "")
    CV_URL: str = os.getenv("CV_URL", "")
    UNSUB_BASE_URL: str = os.getenv("UNSUB_BASE_URL", "http://localhost:8000/unsubscribe")

    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "")
    FROM_NAME: str = os.getenv("FROM_NAME", "Outreach Bot")
    REPLY_TO: str = os.getenv("REPLY_TO", "")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    IMAP_HOST: str = os.getenv("IMAP_HOST", "imap.gmail.com")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USERNAME: str = os.getenv("IMAP_USERNAME", "")
    IMAP_PASSWORD: str = os.getenv("IMAP_PASSWORD", "")

    DAILY_CAP: int = int(os.getenv("DAILY_CAP", "100"))
    PER_EMAIL_DELAY_SECONDS: int = int(os.getenv("PER_EMAIL_DELAY_SECONDS", "25"))
    JITTER_MIN: float = float(os.getenv("JITTER_MIN", "0"))
    JITTER_MAX: float = float(os.getenv("JITTER_MAX", "0"))

    FU1_DELAY_HOURS: int = int(os.getenv("FU1_DELAY_HOURS", "24"))
    FU2_DELAY_HOURS: int = int(os.getenv("FU2_DELAY_HOURS", "48"))
    CUTOFF_DELAY_HOURS: int = int(os.getenv("CUTOFF_DELAY_HOURS", "168"))

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Karachi")

settings = Settings()
