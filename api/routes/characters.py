import re
import sqlite3
from collections import Counter
from fastapi import APIRouter, HTTPException, Query, Header, status
from pydantic import BaseModel
from typing import Optional, List
from config import settings
from core.character_designer import CharacterDesignSheet
from core.llm_processor import LLMProcessor
from providers.auth.supabase_auth import SupabaseAuth

router = APIRouter(prefix="/characters", tags=["characters"])

def get_uid(authorization: Optional[str], user_id: Optional[str], x_user_id: Optional[str]) -> str:
    """Helper to extract user_id from token or headers/query params."""
    uid = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            auth_provider = SupabaseAuth()
            user = auth_provider.verify_token(token)
            if user and "id" in user:
                uid = user["id"]
        except Exception as e:
            print(f"[Warning] Failed to verify token in characters route: {e}")

    if not uid:
        uid = user_id or x_user_id or "00000000-0000-0000-0000-000000000000"
    return uid

@router.post("")
def save_character(
    sheet: CharacterDesignSheet,
    user_id: Optional[str] = Query(None),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    uid = get_uid(authorization, user_id, x_user_id)

    # 1. Save to local SQLite cache
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    try:
        # Ensure the table is created
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS character_design_sheets (
                user_id TEXT,
                name TEXT,
                gender TEXT,
                age_range TEXT,
                hair_style TEXT,
                hair_color TEXT,
                eye_color TEXT,
                body_type TEXT,
                primary_outfit TEXT,
                distinguishing_features TEXT,
                personality_note TEXT,
                PRIMARY KEY (user_id, name)
            )
        ''')
        cursor.execute('''
            INSERT INTO character_design_sheets (
                user_id, name, gender, age_range, hair_style, hair_color, eye_color, body_type, primary_outfit, distinguishing_features, personality_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, name) DO UPDATE SET
                gender = excluded.gender,
                age_range = excluded.age_range,
                hair_style = excluded.hair_style,
                hair_color = excluded.hair_color,
                eye_color = excluded.eye_color,
                body_type = excluded.body_type,
                primary_outfit = excluded.primary_outfit,
                distinguishing_features = excluded.distinguishing_features,
                personality_note = excluded.personality_note
        ''', (
            uid, sheet.name, sheet.gender, sheet.age_range, sheet.hair_style, sheet.hair_color, sheet.eye_color, sheet.body_type, sheet.primary_outfit, sheet.distinguishing_features, sheet.personality_note
        ))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"SQLite save error: {str(e)}")
    conn.close()

    # 2. Sync to Supabase table if enabled
    auth = SupabaseAuth()
    supabase_synced = False
    if auth.enabled and auth.client:
        try:
            payload = {
                "name": sheet.name,
                "gender": sheet.gender,
                "age_range": sheet.age_range,
                "hair_style": sheet.hair_style,
                "hair_color": sheet.hair_color,
                "eye_color": sheet.eye_color,
                "body_type": sheet.body_type,
                "primary_outfit": sheet.primary_outfit,
                "distinguishing_features": sheet.distinguishing_features,
                "personality_note": sheet.personality_note
            }
            res = auth.client.table("character_design_sheets").select("name").eq("user_id", uid).eq("name", sheet.name).execute()
            existing = getattr(res, "data", [])
            if existing:
                auth.client.table("character_design_sheets").update(payload).eq("user_id", uid).eq("name", sheet.name).execute()
            else:
                auth.client.table("character_design_sheets").insert({**payload, "user_id": uid}).execute()
            supabase_synced = True
        except Exception as e:
            print(f"[Supabase Sync Warning] Failed to save/update character_design_sheets table: {e}")

    return {
        "status": "success",
        "message": "Character saved successfully.",
        "supabase_synced": supabase_synced,
        "character": sheet
    }

@router.get("")
def list_characters(
    user_id: Optional[str] = Query(None),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    uid = get_uid(authorization, user_id, x_user_id)

    # 1. Try Supabase first if enabled
    auth = SupabaseAuth()
    if auth.enabled and auth.client:
        try:
            res = auth.client.table("character_design_sheets").select("*").eq("user_id", uid).execute()
            data = getattr(res, "data", []) or []
            sheets = []
            for row in data:
                sheets.append({
                    "name": row.get("name"),
                    "gender": row.get("gender"),
                    "age_range": row.get("age_range"),
                    "hair_style": row.get("hair_style") or "",
                    "hair_color": row.get("hair_color") or "",
                    "eye_color": row.get("eye_color") or "",
                    "body_type": row.get("body_type") or "",
                    "primary_outfit": row.get("primary_outfit") or "",
                    "distinguishing_features": row.get("distinguishing_features") or "",
                    "personality_note": row.get("personality_note") or ""
                })
            return sheets
        except Exception as e:
            print(f"[Supabase Fetch Warning] Failed to list characters: {e}. Falling back to SQLite.")

    # 2. SQLite fallback
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    sheets = []
    try:
        cursor.execute('''
            SELECT name, gender, age_range, hair_style, hair_color, eye_color, body_type, primary_outfit, distinguishing_features, personality_note
            FROM character_design_sheets
            WHERE user_id = ?
        ''', (uid,))
        rows = cursor.fetchall()
        for r in rows:
            sheets.append({
                "name": r[0],
                "gender": r[1],
                "age_range": r[2],
                "hair_style": r[3],
                "hair_color": r[4],
                "eye_color": r[5],
                "body_type": r[6],
                "primary_outfit": r[7],
                "distinguishing_features": r[8],
                "personality_note": r[9]
            })
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"SQLite read error: {str(e)}")
    conn.close()

    return sheets

# ---------------------------------------------------------------------------
# Character detection endpoint (rule-based, no LLM)
# ---------------------------------------------------------------------------

class DetectRequest(BaseModel):
    text: str
    user_id: Optional[str] = None

@router.post("/detect")
def detect_characters(body: DetectRequest):
    """
    Scans story text for candidate character names using the same
    capitalized-word, 2+ occurrence rule as _rule_based_extraction
    in llm_processor.py, then detects gender for each via
    LLMProcessor.detect_character_gender (static, no Ollama).

    Returns: {"characters": [{"name": "Kaito", "gender": "male"}, ...]}
    """
    text = body.text or ""

    blacklist = {
        # pronouns / generic references
        "he", "she", "it", "they", "them", "him", "her", "his", "hers", "their", "theirs",
        "someone", "everyone", "nobody", "noone", "anybody", "somebody", "character",
        "people", "man", "woman", "boy", "girl", "knight", "commander", "enemy",
        # common conjunctions / prepositions / articles
        "the", "and", "but", "then", "this", "that", "these", "those", "when", "after",
        "for", "with", "a", "an", "of",
        # common sentence-starting adverbs / prepositions that get capitalised
        "across", "above", "before", "below", "behind", "beside", "between",
        "beyond", "during", "inside", "outside", "around", "against",
        "meanwhile", "suddenly", "finally", "already", "later", "now",
        "slowly", "quickly", "quietly", "together", "however", "though",
        "although", "while", "until", "unless", "despite", "without",
        # common dialogue / imperative / interjection openers (the "Look" false-positive class)
        "look", "wait", "stop", "run", "come", "please", "yes", "okay", "hey", "well",
        "listen", "watch", "help", "hello", "sorry", "thanks", "never", "always", "maybe",
        "perhaps", "once", "soon", "still", "just", "only", "even", "also", "indeed",
        "instead", "what", "why", "how", "who", "where", "here", "there", "everything",
        "nothing", "something", "anything", "good", "great", "okay", "fine", "sure",
    }

    # A capitalized word is a NAME candidate only if it appears capitalized at least once
    # MID-SENTENCE — i.e. immediately after a lowercase letter ("met Mei", "Kaito's sword").
    # Real proper nouns get capitalized in running text; common words like "Look"/"Then"/
    # "Wait" are only capitalized at the start of a sentence or quote. This kills the
    # false-positive vault-enforcement block on ordinary English words. [QA 2026-06-30]
    order = list(dict.fromkeys(re.findall(r"[A-Z][a-z]{2,}", text)))
    mid_sentence = set()
    counts = Counter()
    for m in re.finditer(r"[A-Z][a-z]{2,}", text):
        w = m.group(0)
        if w.lower() in blacklist:
            continue
        counts[w] += 1
        j = m.start() - 1
        while j >= 0 and text[j] in " \t":
            j -= 1
        if j >= 0 and text[j].islower():   # preceded by a lowercase word → strong proper-noun signal
            mid_sentence.add(w)

    # A name qualifies if it appears capitalized mid-sentence (e.g. "met Mei") OR recurs 2+
    # times (e.g. "Harry ... Harry"). Common words are excluded by the blacklist, so a bare
    # sentence-start "Look" no longer counts — fixing the false vault-enforcement block.
    char_names = [
        w for w in order
        if w.lower() not in blacklist and (w in mid_sentence or counts[w] >= 2)
    ]

    processor = LLMProcessor()
    characters = []
    for name in char_names:
        gender = processor.detect_character_gender(name, text)
        characters.append({"name": name, "gender": gender})

    return {"characters": characters}

@router.get("/{name}")
def get_character(
    name: str,
    user_id: Optional[str] = Query(None),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    uid = get_uid(authorization, user_id, x_user_id)

    # 1. Try Supabase
    auth = SupabaseAuth()
    if auth.enabled and auth.client:
        try:
            res = auth.client.table("character_design_sheets").select("*").eq("user_id", uid).eq("name", name).execute()
            data = getattr(res, "data", []) or []
            if data:
                row = data[0]
                return {
                    "name": row.get("name"),
                    "gender": row.get("gender"),
                    "age_range": row.get("age_range"),
                    "hair_style": row.get("hair_style") or "",
                    "hair_color": row.get("hair_color") or "",
                    "eye_color": row.get("eye_color") or "",
                    "body_type": row.get("body_type") or "",
                    "primary_outfit": row.get("primary_outfit") or "",
                    "distinguishing_features": row.get("distinguishing_features") or "",
                    "personality_note": row.get("personality_note") or ""
                }
        except Exception as e:
            print(f"[Supabase Fetch Warning] Failed to get character: {e}. Falling back to SQLite.")

    # 2. SQLite fallback
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT name, gender, age_range, hair_style, hair_color, eye_color, body_type, primary_outfit, distinguishing_features, personality_note
            FROM character_design_sheets
            WHERE user_id = ? AND LOWER(name) = ?
        ''', (uid, name.lower()))
        r = cursor.fetchone()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"SQLite read error: {str(e)}")
    conn.close()

    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Character '{name}' not found.")

    return {
        "name": r[0],
        "gender": r[1],
        "age_range": r[2],
        "hair_style": r[3],
        "hair_color": r[4],
        "eye_color": r[5],
        "body_type": r[6],
        "primary_outfit": r[7],
        "distinguishing_features": r[8],
        "personality_note": r[9]
    }

@router.delete("/{name}")
def delete_character(
    name: str,
    user_id: Optional[str] = Query(None),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    uid = get_uid(authorization, user_id, x_user_id)

    # 1. Delete from SQLite
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    rowcount = 0
    try:
        cursor.execute('DELETE FROM character_design_sheets WHERE user_id = ? AND LOWER(name) = ?', (uid, name.lower()))
        rowcount = cursor.rowcount
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"SQLite delete error: {str(e)}")
    conn.close()

    # 2. Delete from Supabase
    auth = SupabaseAuth()
    supabase_deleted = False
    if auth.enabled and auth.client:
        try:
            auth.client.table("character_design_sheets").delete().eq("user_id", uid).eq("name", name).execute()
            supabase_deleted = True
        except Exception as e:
            print(f"[Supabase Delete Warning] Failed to delete character: {e}")

    if rowcount == 0 and not supabase_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Character '{name}' not found.")

    return {
        "status": "success",
        "message": f"Character '{name}' deleted successfully."
    }
