import os
import sqlite3
import uuid
import json
import httpx
from datetime import datetime
from config import settings

def load_env_var(key: str, default: str = "") -> str:
    """
    Robust env var loader. Checks os.environ first, then falls back to parsing
    the .env file in the base directory to avoid environment loading issues.
    """
    val = os.environ.get(key)
    if val:
        return val.strip()

    # Fallback to reading the .env file in the project base directory
    services_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(services_dir)
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_stripped = line.strip()
                    if not line_stripped or line_stripped.startswith("#"):
                        continue
                    if "=" in line_stripped:
                        parts = line_stripped.split("=", 1)
                        if len(parts) == 2 and parts[0].strip() == key:
                            return parts[1].strip()
        except Exception:
            pass
    return default


class HistoryService:
    """
    HistoryService handles SQL queries mapping comics metadata, final page coordinates, and image URLs.
    It synchronizes updates to both Supabase (if configured) and the local SQLite database.
    """
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(settings.DB_DIR, "jobs.db")
        self.supabase_url = load_env_var("SUPABASE_URL")
        self.supabase_key = load_env_var("SUPABASE_SECRET_KEY")
        self.supabase_enabled = bool(self.supabase_url and self.supabase_key)

        if self.supabase_enabled:
            print(f"[HistoryService] Supabase integration enabled. Writing to {self.supabase_url}")
        else:
            print("[HistoryService] Supabase URL or Secret Key not set. Falling back to local SQLite.")

        self._init_sqlite()

    def _init_sqlite(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comics (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                job_id TEXT,
                title TEXT NOT NULL,
                style TEXT NOT NULL DEFAULT 'anime',
                layout_type TEXT DEFAULT 'standard',
                panel_count INTEGER,
                panel_count_mode TEXT DEFAULT 'ai_decided',
                panel_urls TEXT DEFAULT '[]',
                final_page TEXT,
                created_at TEXT
            )
        ''')
        # Ensure correct column definitions are active
        for col_name, col_type in [("panel_count", "INTEGER"), ("layout_type", "TEXT"), ("panel_count_mode", "TEXT"), ("is_public", "INTEGER DEFAULT 0"), ("is_featured", "INTEGER DEFAULT 0")]:
            try:
                cursor.execute(f"ALTER TABLE comics ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass
        conn.commit()
        conn.close()

    def auto_title(self, scene_text: str) -> str:
        """
        Auto-generate titles using the first 6 words + "...".
        """
        if not scene_text:
            return "Untitled Comic"
        words = scene_text.strip().split()
        if len(words) <= 6:
            return " ".join(words)
        return " ".join(words[:6]) + "..."

    def save_comic(self, user_id: str, job_id: str, title: str, style: str, layout_type: str, 
                   panel_count: int, panel_count_mode: str, panel_urls: list, final_page: str, 
                   comic_id: str = None) -> dict:
        """
        Saves a generated comic sheet both locally and in Supabase (if enabled).
        """
        if not comic_id:
            comic_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        panel_urls_str = json.dumps(panel_urls or [])

        # 1. Save to local SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO comics (id, user_id, job_id, title, style, layout_type, panel_count, panel_count_mode, panel_urls, final_page, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (comic_id, user_id, job_id, title, style, layout_type, panel_count, panel_count_mode, panel_urls_str, final_page, created_at))
        conn.commit()
        conn.close()

        comic_data = {
            "id": comic_id,
            "user_id": user_id,
            "job_id": job_id,
            "title": title,
            "style": style,
            "layout_type": layout_type,
            "panel_count": panel_count,
            "panel_count_mode": panel_count_mode,
            "panel_urls": panel_urls,
            "final_page": final_page,
            "created_at": created_at
        }

        # 2. Save to Supabase if enabled
        if self.supabase_enabled:
            self._supabase_save_comic(comic_data)

        return comic_data

    def _supabase_save_comic(self, comic_data: dict):
        url = f"{self.supabase_url.rstrip('/')}/rest/v1/comics"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal"
        }
        payload = {
            "id": comic_data["id"],
            "user_id": comic_data["user_id"],
            "job_id": comic_data["job_id"],
            "title": comic_data["title"],
            "style": comic_data["style"],
            "layout_type": comic_data["layout_type"],
            "panel_count": comic_data["panel_count"],
            "panel_count_mode": comic_data["panel_count_mode"],
            "panel_urls": comic_data["panel_urls"],  # JSONB field in Postgres
            "final_page": comic_data["final_page"],
            "created_at": comic_data["created_at"]
        }
        try:
            r = httpx.post(url, headers=headers, json=payload, timeout=10.0)
            r.raise_for_status()
        except Exception as e:
            print(f"[Warning] Failed to save comic in Supabase: {e}")

    def get_user_comics(self, user_id: str, page: int = 1, limit: int = 10) -> dict:
        """
        Retrieves a paginated list of comics saved under a specific user account.
        """
        offset = (page - 1) * limit

        # If Supabase is enabled, retrieve directly from it to ensure live sync
        if self.supabase_enabled:
            url = f"{self.supabase_url.rstrip('/')}/rest/v1/comics"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Range": f"{offset}-{offset + limit - 1}",
                "Prefer": "count=exact"
            }
            params = {
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc"
            }
            try:
                r = httpx.get(url, headers=headers, params=params, timeout=10.0)
                r.raise_for_status()
                content_range = r.headers.get("Content-Range", "")
                total = 0
                if "/" in content_range:
                    total = int(content_range.split("/")[-1])
                supabase_data = r.json()

                comics_list = []
                for item in supabase_data:
                    # Unpack panel_urls
                    urls = item.get("panel_urls")
                    if isinstance(urls, str):
                        try:
                            urls = json.loads(urls)
                        except Exception:
                            urls = []
                    
                    comics_list.append({
                        "id": item.get("id"),
                        "user_id": item.get("user_id"),
                        "job_id": item.get("job_id"),
                        "title": item.get("title"),
                        "style": item.get("style"),
                        "layout_type": item.get("layout_type"),
                        "panel_count": item.get("panel_count"),
                        "panel_count_mode": item.get("panel_count_mode"),
                        "panel_urls": urls or [],
                        "final_page": item.get("final_page"),
                        "created_at": item.get("created_at")
                    })
                if comics_list:
                    return {
                        "comics": comics_list,
                        "total_count": total,
                        "page": page,
                        "limit": limit
                    }
                else:
                    print(f"[HistoryService] Supabase returned 0 comics for user {user_id}. Checking local SQLite database.")
            except Exception as e:
                print(f"[Warning] Failed to fetch user comics from Supabase: {e}. Falling back to SQLite.")

        # SQLite Fallback
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM comics WHERE user_id = ?", (user_id,))
        total_count = cursor.fetchone()[0]

        cursor.execute('''
            SELECT id, user_id, job_id, title, style, layout_type, panel_count, panel_count_mode, panel_urls, final_page, is_public, is_featured, created_at
            FROM comics WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (user_id, limit, offset))
        rows = cursor.fetchall()
        conn.close()

        comics_list = []
        for r in rows:
            try:
                p_urls = json.loads(r[8])
            except Exception:
                p_urls = []
            comics_list.append({
                "id": r[0],
                "user_id": r[1],
                "job_id": r[2],
                "title": r[3],
                "style": r[4],
                "layout_type": r[5],
                "panel_count": r[6],
                "panel_count_mode": r[7],
                "panel_urls": p_urls,
                "final_page": r[9],
                "is_public": bool(r[10]),
                "is_featured": bool(r[11]),
                "created_at": r[12]
            })

        return {
            "comics": comics_list,
            "total_count": total_count,
            "page": page,
            "limit": limit
        }

    def get_comic_by_id(self, comic_id: str) -> dict:
        """
        Fetches details of a specific saved comic sheet.
        """
        # First check local database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, job_id, title, style, layout_type, panel_count, panel_count_mode, panel_urls, final_page, is_public, is_featured, created_at
            FROM comics WHERE id = ?
        ''', (comic_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            try:
                p_urls = json.loads(row[8])
            except Exception:
                p_urls = []
            return {
                "id": row[0],
                "user_id": row[1],
                "job_id": row[2],
                "title": row[3],
                "style": row[4],
                "layout_type": row[5],
                "panel_count": row[6],
                "panel_count_mode": row[7],
                "panel_urls": p_urls,
                "final_page": row[9],
                "is_public": bool(row[10]),
                "is_featured": bool(row[11]),
                "created_at": row[12]
            }

        # Check Supabase if enabled
        if self.supabase_enabled:
            url = f"{self.supabase_url.rstrip('/')}/rest/v1/comics?id=eq.{comic_id}"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}"
            }
            try:
                r = httpx.get(url, headers=headers, timeout=10.0)
                r.raise_for_status()
                data = r.json()
                if data and len(data) > 0:
                    item = data[0]
                    urls = item.get("panel_urls")
                    if isinstance(urls, str):
                        try:
                            urls = json.loads(urls)
                        except Exception:
                            urls = []

                    # Cache retrieve back to local SQLite
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO comics (id, user_id, job_id, title, style, layout_type, panel_count, panel_count_mode, panel_urls, final_page, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        item.get("id"),
                        item.get("user_id"),
                        item.get("job_id"),
                        item.get("title"),
                        item.get("style"),
                        item.get("layout_type"),
                        item.get("panel_count"),
                        item.get("panel_count_mode"),
                        json.dumps(urls or []),
                        item.get("final_page"),
                        item.get("created_at")
                    ))
                    conn.commit()
                    conn.close()

                    return {
                        "id": item.get("id"),
                        "user_id": item.get("user_id"),
                        "job_id": item.get("job_id"),
                        "title": item.get("title"),
                        "style": item.get("style"),
                        "layout_type": item.get("layout_type"),
                        "panel_count": item.get("panel_count"),
                        "panel_count_mode": item.get("panel_count_mode"),
                        "panel_urls": urls or [],
                        "final_page": item.get("final_page"),
                        "created_at": item.get("created_at")
                    }
            except Exception as e:
                print(f"[Warning] Failed to fetch comic by ID from Supabase: {e}")

        return None

    def delete_comic(self, comic_id: str) -> bool:
        """
        Deletes a specific saved comic sheet from history.
        """
        # 1. Delete from local SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM comics WHERE id = ?", (comic_id,))
        deleted_rows = cursor.rowcount
        conn.commit()
        conn.close()

        # 2. Delete from Supabase if enabled
        supabase_success = False
        if self.supabase_enabled:
            url = f"{self.supabase_url.rstrip('/')}/rest/v1/comics?id=eq.{comic_id}"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}"
            }
            try:
                r = httpx.delete(url, headers=headers, timeout=10.0)
                r.raise_for_status()
                supabase_success = True
            except Exception as e:
                print(f"[Warning] Failed to delete comic in Supabase: {e}")

        return deleted_rows > 0 or supabase_success

# Instantiate global service instance
history_service = HistoryService()
