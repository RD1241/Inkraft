import os
import sqlite3
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


class GalleryService:
    """
    GalleryService handles SQL queries for public, shared, and featured comics.
    It synchronizes updates to both Supabase (if configured) and the local SQLite database.
    """
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(settings.DB_DIR, "jobs.db")
        self.supabase_url = load_env_var("SUPABASE_URL")
        self.supabase_key = load_env_var("SUPABASE_SECRET_KEY")
        self.supabase_enabled = bool(self.supabase_url and self.supabase_key)

        if self.supabase_enabled:
            print(f"[GalleryService] Supabase integration enabled. Reading from {self.supabase_url}")
        else:
            print("[GalleryService] Supabase URL or Secret Key not set. Falling back to local SQLite.")

        self._init_sqlite()

    def _init_sqlite(self):
        # Add is_public and is_featured columns to the local SQLite comics table if they don't exist
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for col_name, col_type in [("is_public", "INTEGER DEFAULT 0"), ("is_featured", "INTEGER DEFAULT 0")]:
            try:
                cursor.execute(f"ALTER TABLE comics ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass
        conn.commit()
        conn.close()

    def get_public_comics(self, style: str = None, page: int = 1, limit: int = 20) -> dict:
        """
        Retrieves a paginated list of public (shared) comics, sorted by is_featured DESC, created_at DESC.
        Can be optionally filtered by style.
        """
        offset = (page - 1) * limit
        style_filter = style.strip().lower() if style else None

        # 1. Supabase Fetch
        if self.supabase_enabled:
            url = f"{self.supabase_url.rstrip('/')}/rest/v1/comics"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Range": f"{offset}-{offset + limit - 1}",
                "Prefer": "count=exact"
            }
            params = {
                "is_public": "eq.true",
                "order": "is_featured.desc,created_at.desc"
            }
            if style_filter:
                params["style"] = f"eq.{style_filter}"

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
                        "is_public": item.get("is_public", False),
                        "is_featured": item.get("is_featured", False),
                        "created_at": item.get("created_at")
                    })
                return {
                    "comics": comics_list,
                    "total_count": total,
                    "page": page,
                    "limit": limit
                }
            except Exception as e:
                print(f"[Warning] Failed to fetch public comics from Supabase: {e}. Falling back to SQLite.")

        # 2. SQLite Fallback
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query_count = "SELECT COUNT(*) FROM comics WHERE is_public = 1"
        query_select = """
            SELECT id, user_id, job_id, title, style, layout_type, panel_count, panel_count_mode, panel_urls, final_page, is_public, is_featured, created_at
            FROM comics WHERE is_public = 1
        """
        params = []

        if style_filter:
            query_count += " AND LOWER(style) = ?"
            query_select += " AND LOWER(style) = ?"
            params.append(style_filter)

        cursor.execute(query_count, params)
        total_count = cursor.fetchone()[0]

        query_select += " ORDER BY is_featured DESC, created_at DESC LIMIT ? OFFSET ?"
        select_params = params + [limit, offset]

        cursor.execute(query_select, select_params)
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

    def set_public(self, comic_id: str, is_public: bool, user_id: str = None) -> bool:
        """
        Toggles is_public for a given comic sheet.
        If user_id is provided, only updates if the user is the owner.
        """
        # 1. Update SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("UPDATE comics SET is_public = ? WHERE id = ? AND user_id = ?", (1 if is_public else 0, comic_id, user_id))
        else:
            cursor.execute("UPDATE comics SET is_public = ? WHERE id = ?", (1 if is_public else 0, comic_id))
        
        updated_rows = cursor.rowcount
        conn.commit()
        conn.close()

        # 2. Update Supabase
        supabase_success = False
        if self.supabase_enabled:
            url = f"{self.supabase_url.rstrip('/')}/rest/v1/comics"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            payload = {
                "is_public": is_public
            }
            
            # Form params
            filter_url = f"{url}?id=eq.{comic_id}"
            if user_id:
                filter_url += f"&user_id=eq.{user_id}"

            try:
                r = httpx.patch(filter_url, headers=headers, json=payload, timeout=10.0)
                r.raise_for_status()
                # If representation returned data, then it succeeded
                if r.json():
                    supabase_success = True
            except Exception as e:
                print(f"[Warning] Failed to update is_public in Supabase: {e}")

        return (updated_rows > 0) or supabase_success

    def feature_comic(self, comic_id: str, is_featured: bool) -> bool:
        """
        Toggles is_featured for a given comic sheet.
        """
        # 1. Update SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE comics SET is_featured = ? WHERE id = ?", (1 if is_featured else 0, comic_id))
        updated_rows = cursor.rowcount
        conn.commit()
        conn.close()

        # 2. Update Supabase
        supabase_success = False
        if self.supabase_enabled:
            url = f"{self.supabase_url.rstrip('/')}/rest/v1/comics?id=eq.{comic_id}"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            payload = {
                "is_featured": is_featured
            }

            try:
                r = httpx.patch(url, headers=headers, json=payload, timeout=10.0)
                r.raise_for_status()
                if r.json():
                    supabase_success = True
            except Exception as e:
                print(f"[Warning] Failed to update is_featured in Supabase: {e}")

        return (updated_rows > 0) or supabase_success


# Global gallery service instance
gallery_service = GalleryService()
