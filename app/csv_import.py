# app/csv_import.py
import json
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .db import engine, SessionLocal, Base
from .models import Contact

HEADER_MAP = {
    "email": "email",
    "first": "first_name",
    "last": "last_name",
    "company": "company",
    "company type": "company_focus",
    "title": "__extra__title",
    "company linkedin url": "__extra__company_linkedin_url",
    "linkedin url": "__extra__linkedin_url",
    "website": "__extra__website",
    "country": "__extra__country",
    "company size": "__extra__company_size",
}

def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    lower_map = {c.lower().strip(): c for c in df.columns}
    rename = {}
    for norm, orig in lower_map.items():
        if norm in HEADER_MAP:
            rename[orig] = HEADER_MAP[norm]
    return df.rename(columns=rename)

def import_csv(path: str):
    Base.metadata.create_all(bind=engine)
    df = pd.read_csv(path)

    # Normalize headers and ensure email presence
    df = normalize_cols(df)
    if "email" not in df.columns:
        raise ValueError("CSV must contain an Email column (any casing).")

    # Normalize/clean email & basic fields
    df["email"] = df["email"].astype(str).str.strip().str.lower()
    for col in ["first_name", "last_name", "company", "company_focus"]:
        if col not in df.columns:
            df[col] = None

    # Drop rows with blank email
    df = df[df["email"].ne("") & df["email"].notna()]

    # Drop duplicate emails (case-insensitive already)
    df = df.drop_duplicates(subset=["email"], keep="first").reset_index(drop=True)

    extra_cols = [c for c in df.columns if c.startswith("__extra__")]

    db: Session = SessionLocal()
    seen = set()
    try:
        count = 0
        for _, row in df.iterrows():
            email = row["email"]
            if email in seen:
                continue
            seen.add(email)

            # Build extras JSON
            extras = {}
            for c in extra_cols:
                v = row.get(c)
                if pd.notna(v) and str(v).strip():
                    extras[c.replace("__extra__", "").strip("_")] = str(v).strip()
            notes = json.dumps(extras, ensure_ascii=False) if extras else None

            existing = db.get(Contact, email)
            if existing:
                # Update a few fields if provided
                if pd.notna(row.get("first_name")) and str(row.get("first_name")).strip():
                    existing.first_name = str(row["first_name"]).strip()
                if pd.notna(row.get("last_name")) and str(row.get("last_name")).strip():
                    existing.last_name = str(row["last_name"]).strip()
                if pd.notna(row.get("company")) and str(row.get("company")).strip():
                    existing.company = str(row["company"]).strip()
                if pd.notna(row.get("company_focus")) and str(row.get("company_focus")).strip():
                    existing.company_focus = str(row["company_focus"]).strip()
                # Merge notes
                if notes:
                    try:
                        old = json.loads(existing.notes) if existing.notes else {}
                    except Exception:
                        old = {}
                    old.update(extras)
                    existing.notes = json.dumps(old, ensure_ascii=False)
                db.add(existing)
            else:
                c = Contact(
                    email=email,
                    first_name=str(row["first_name"]).strip() if pd.notna(row.get("first_name")) else None,
                    last_name=str(row["last_name"]).strip() if pd.notna(row.get("last_name")) else None,
                    company=str(row["company"]).strip() if pd.notna(row.get("company")) else None,
                    company_focus=str(row["company_focus"]).strip() if pd.notna(row.get("company_focus")) else None,
                    status="no_sync",
                    sequence_step=0,
                    notes=notes,
                )
                db.add(c)

            count += 1
            if count % 5000 == 0:
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    # Safety retry per-row in rare race with duplicates
                    try:
                        existing = db.get(Contact, email)
                        if not existing:
                            db.add(c)
                        db.commit()
                    except Exception:
                        db.rollback()
                        # skip problematic row
                        continue

        db.commit()
        print(f"Imported/updated {count} unique emails")
    finally:
        db.close()
