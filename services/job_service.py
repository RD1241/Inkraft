import sqlite3
import os
import uuid
import json
import re
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


class JobService:
    """
    JobService handles comic generation job status, progress percentages, and results.
    It synchronizes updates to both Supabase (if configured) and the local SQLite database.

    Supabase Table Schema:
    ----------------------
    CREATE TABLE jobs (
        job_id TEXT PRIMARY KEY,
        status TEXT,
        progress TEXT,
        created_at TEXT,
        updated_at TEXT,
        result TEXT,
        error TEXT
    );
    """
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(settings.DB_DIR, "jobs.db")
        self.supabase_url = load_env_var("SUPABASE_URL")
        self.supabase_key = load_env_var("SUPABASE_SECRET_KEY")
        self.supabase_enabled = bool(self.supabase_url and self.supabase_key)

        if self.supabase_enabled:
            print(f"[JobService] Supabase integration enabled. Writing to {self.supabase_url}")
        else:
            print("[JobService] Supabase URL or Secret Key not set. Falling back to local SQLite.")

        self._init_sqlite()

    def _init_sqlite(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                user_id TEXT,
                status TEXT,
                progress TEXT,
                created_at TEXT,
                updated_at TEXT,
                result TEXT,
                error TEXT,
                panel_count INTEGER,
                layout_type TEXT,
                panel_count_mode TEXT,
                generation_format TEXT
            )
        ''')
        # Add columns if upgrading from an old schema
        for col_name, col_type in [("user_id", "TEXT"), ("progress", "TEXT"), ("panel_count", "INTEGER"), ("layout_type", "TEXT"), ("panel_count_mode", "TEXT"), ("generation_format", "TEXT")]:
            try:
                cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass
        conn.commit()
        conn.close()

    def create_job(self, panel_count: int = None, layout_type: str = None, panel_count_mode: str = None, generation_format: str = None, user_id: str = None) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        status = "queued"
        progress = "0% - Waiting in queue..."

        # 1. Write to local SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO jobs (job_id, user_id, status, progress, created_at, updated_at, panel_count, layout_type, panel_count_mode, generation_format)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (job_id, user_id, status, progress, now, now, panel_count, layout_type, panel_count_mode, generation_format))
        conn.commit()
        conn.close()

        # 2. Write to Supabase if enabled
        if self.supabase_enabled:
            self._supabase_create_job(job_id, status, progress, now, panel_count, layout_type, panel_count_mode, generation_format, user_id)

        return job_id

    def _supabase_create_job(self, job_id: str, status: str, progress: str, created_at: str, panel_count: int = None, layout_type: str = None, panel_count_mode: str = None, generation_format: str = None, user_id: str = None):
        url = f"{self.supabase_url.rstrip('/')}/rest/v1/jobs"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        payload = {
            "id": job_id,
            "status": status,
            "progress": progress,
            "created_at": created_at,
            "updated_at": created_at,
            "result": None,
            "error": None,
            "panel_count": panel_count,
            "layout_type": layout_type,
            "panel_count_mode": panel_count_mode,
            "generation_format": generation_format
        }
        if user_id:
            payload["user_id"] = user_id
        try:
            r = httpx.post(url, headers=headers, json=payload, timeout=10.0)
            r.raise_for_status()
        except Exception as e:
            print(f"[Warning] Failed to create job in Supabase: {e}")

    def _get_current_progress(self, job_id: str) -> str:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT progress FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else ""
        except Exception:
            return ""

    def _extract_total_panels(self, progress_str: str) -> int:
        if not progress_str:
            return 1
        match = re.search(r"panel\s+\d+\s*/\s*(\d+)", progress_str, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 1

    def _get_progress_updates(self, job_id: str, status: str, progress_str: str, error: str = None) -> list:
        """
        Parses pipeline messages and returns the sequence of progress percentage updates
        corresponding to each stage of the generation process:
         - Queued: 0%
         - Scene extraction complete: 20%
         - Storyboard plan complete: 35%
         - Each panel generated: 35 + ((panel_index + 1) / total_panels) * 50
         - Rendering and assembly complete: 100%
        """
        if status == "completed":
            if progress_str and "Your page is ready!" in progress_str:
                return [progress_str]
            return ["100% - Rendering and assembly complete"]
        if status == "failed":
            return [f"Failed - {error or 'Unknown error'}"]
        if status == "queued":
            return ["0% - Waiting in queue..."]

        if not progress_str:
            return []

        # If progress_str already has a percentage prefix, bypass parsing and return it directly
        if re.match(r"^\d+%", progress_str.strip()):
            return [progress_str]

        # Parse panel number and total panels if available (e.g. "Drawing panel 1/4...")
        panel_match = re.search(r"Drawing panel\s+(\d+)\s*/\s*(\d+)", progress_str, re.IGNORECASE)
        if panel_match:
            panel_num = int(panel_match.group(1))
            total_panels = max(1, int(panel_match.group(2)))
            if panel_num == 1:
                # Panel 1 starting means: Scene Extraction (20%) and Storyboard Plan (35%) are complete!
                return [
                    "20% - Scene extraction complete",
                    "35% - Storyboard plan complete",
                    f"35% - Drawing panel 1/{total_panels}..."
                ]
            else:
                # Panel (panel_num - 1) has completed generation
                # percentage = 35 + (completed_panels / total_panels) * 50
                completed_panels = panel_num - 1
                percent = 35 + (completed_panels / total_panels) * 50
                return [
                    f"{percent:.0f}% - Drawing panel {completed_panels}/{total_panels} complete",
                    f"{percent:.0f}% - Drawing panel {panel_num}/{total_panels}..."
                ]

        if "Assembling" in progress_str:
            # Assembly starting means all panels are now complete!
            prev_progress = self._get_current_progress(job_id)
            total_panels = self._extract_total_panels(prev_progress)
            percent = 35 + (total_panels / total_panels) * 50  # 85%
            return [
                f"{percent:.0f}% - Drawing panel {total_panels}/{total_panels} complete",
                f"{percent:.0f}% - Assembling final comic page..."
            ]

        # Extract LLM scenes extraction starting phase
        if "Extracting" in progress_str:
            return ["0% - Extracting scenes with LLM..."]

        return [progress_str]

    def update_job(self, job_id: str, status: str, result: str = None, error: str = None, progress: str = None):
        now = datetime.datetime.now().isoformat() if hasattr(datetime, "datetime") else datetime.now().isoformat()

        # Compute progress percentage sequence
        progress_updates = self._get_progress_updates(job_id, status, progress, error)

        if not progress_updates:
            self._update_single(job_id, status, progress, result, error, now)
        else:
            for i, p_upd in enumerate(progress_updates):
                is_last = (i == len(progress_updates) - 1)
                curr_status = status if is_last else "processing"
                curr_result = result if is_last else None
                curr_error = error if is_last else None
                self._update_single(job_id, curr_status, p_upd, curr_result, curr_error, now)

    def _update_single(self, job_id: str, status: str, progress: str, result: str, error: str, updated_at: str):
        # 1. Update local SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE jobs SET status = ?, progress = ?, result = ?, error = ?, updated_at = ?
            WHERE job_id = ?
        ''', (status, progress, result, error, updated_at, job_id))
        conn.commit()
        conn.close()

        # 2. Update Supabase if enabled
        if self.supabase_enabled:
            self._supabase_update_job(job_id, status, progress, result, error, updated_at)

    def _supabase_update_job(self, job_id: str, status: str, progress: str, result: str, error: str, updated_at: str):
        url = f"{self.supabase_url.rstrip('/')}/rest/v1/jobs?id=eq.{job_id}"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        payload = {
            "status": status,
            "progress": progress,
            "updated_at": updated_at
        }
        if result is not None:
            payload["result"] = result
        if error is not None:
            payload["error"] = error

        try:
            r = httpx.patch(url, headers=headers, json=payload, timeout=10.0)
            r.raise_for_status()
        except Exception as e:
            print(f"[Warning] Failed to update job in Supabase: {e}")

    def get_job(self, job_id: str) -> dict:
        # First query local SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT job_id, user_id, status, progress, created_at, updated_at, result, error, panel_count, layout_type, panel_count_mode, generation_format
            FROM jobs WHERE job_id = ?
        ''', (job_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "job_id": row[0],
                "user_id": row[1],
                "status": row[2],
                "progress": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "result": json.loads(row[6]) if row[6] else None,
                "error": row[7],
                "panel_count": row[8],
                "layout_type": row[9],
                "panel_count_mode": row[10],
                "generation_format": row[11],
            }

        # Query Supabase if enabled as a fallback
        if self.supabase_enabled:
            url = f"{self.supabase_url.rstrip('/')}/rest/v1/jobs?id=eq.{job_id}"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}"
            }
            try:
                r = httpx.get(url, headers=headers, timeout=10.0)
                r.raise_for_status()
                data = r.json()
                if data and isinstance(data, list) and len(data) > 0:
                    job_data = data[0]
                    # Cache retrieve back to local SQLite
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO jobs (job_id, user_id, status, progress, created_at, updated_at, result, error, panel_count, layout_type, panel_count_mode, generation_format)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        job_data.get("id"),
                        job_data.get("user_id"),
                        job_data.get("status"),
                        job_data.get("progress"),
                        job_data.get("created_at"),
                        job_data.get("updated_at"),
                        job_data.get("result"),
                        job_data.get("error"),
                        job_data.get("panel_count"),
                        job_data.get("layout_type"),
                        job_data.get("panel_count_mode"),
                        job_data.get("generation_format")
                    ))
                    conn.commit()
                    conn.close()

                    return {
                        "job_id": job_data.get("id"),
                        "user_id": job_data.get("user_id"),
                        "status": job_data.get("status"),
                        "progress": job_data.get("progress"),
                        "created_at": job_data.get("created_at"),
                        "updated_at": job_data.get("updated_at"),
                        "result": json.loads(job_data.get("result")) if job_data.get("result") else None,
                        "error": job_data.get("error"),
                        "panel_count": job_data.get("panel_count"),
                        "layout_type": job_data.get("layout_type"),
                        "panel_count_mode": job_data.get("panel_count_mode"),
                        "generation_format": job_data.get("generation_format"),
                    }
            except Exception as e:
                print(f"[Warning] Failed to fetch job from Supabase: {e}")

        return None
