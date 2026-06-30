"""
feedback.py — private beta feedback collection.

POST /api/feedback stores a user's feedback (rating, "would you use it?", message)
to local SQLite (settings.DB_DIR, volume-persistent) AND syncs to a Supabase
`feedback` table if configured. Feedback is PRIVATE (not shown on the site) — it's
for the founder to read during the soft-launch demand validation.

Supabase table to create once (SQL):
  create table feedback (
    id bigint generated always as identity primary key,
    user_id text, email text, rating int, would_use text,
    message text, page text, created_at timestamptz default now()
  );
If the Supabase table doesn't exist yet, SQLite still captures everything.
"""
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, field_validator

from config import settings
from providers.auth.supabase_auth import SupabaseAuth

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackInput(BaseModel):
    message: str = ""
    rating: Optional[int] = None          # 1–5 stars (optional)
    would_use: Optional[str] = None       # "yes" | "maybe" | "no"
    email: Optional[str] = None
    page: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def _rating(cls, v):
        if v is None:
            return v
        if v < 1 or v > 5:
            raise ValueError("rating must be 1–5")
        return v


def _resolve_uid(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.startswith("Bearer "):
        try:
            user = SupabaseAuth().verify_token(authorization.split(" ", 1)[1])
            if user and "id" in user:
                return user["id"]
        except Exception:
            pass
    return None


@router.post("")
def submit_feedback(
    fb: FeedbackInput,
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    message = (fb.message or "").strip()[:2000]
    would_use = (fb.would_use or "").strip().lower()[:16]
    if would_use and would_use not in ("yes", "maybe", "no"):
        would_use = ""
    if not message and fb.rating is None and not would_use:
        raise HTTPException(status_code=400, detail="Feedback is empty.")

    uid = _resolve_uid(authorization)
    email = (fb.email or "").strip()[:200]
    page = (fb.page or "").strip()[:200]
    created_at = datetime.now(timezone.utc).isoformat()

    # 1. SQLite (always; volume-persistent)
    try:
        os.makedirs(settings.DB_DIR, exist_ok=True)
        conn = sqlite3.connect(os.path.join(settings.DB_DIR, "feedback.db"))
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT, email TEXT, rating INTEGER,
                would_use TEXT, message TEXT, page TEXT, created_at TEXT
            )
        """)
        cur.execute(
            "INSERT INTO feedback (user_id, email, rating, would_use, message, page, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, email, fb.rating, would_use, message, page, created_at),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save feedback: {e}")

    # 2. Supabase sync (best-effort; needs the `feedback` table to exist)
    try:
        auth = SupabaseAuth()
        if auth.enabled and auth.client:
            auth.client.table("feedback").insert({
                "user_id": uid, "email": email, "rating": fb.rating,
                "would_use": would_use, "message": message, "page": page,
                "created_at": created_at,
            }).execute()
    except Exception as e:
        print(f"[Feedback] Supabase sync skipped: {e}")

    return {"status": "success", "message": "Thanks for the feedback!"}
