import os
import uuid
import json
import sqlite3
import httpx
from datetime import datetime
from config import settings
from services.job_service import load_env_var

class BillingService:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(settings.DB_DIR, "jobs.db")
        self.supabase_url = load_env_var("SUPABASE_URL")
        self.supabase_key = load_env_var("SUPABASE_SECRET_KEY")
        self.supabase_enabled = bool(self.supabase_url and self.supabase_key)
        
        self._init_sqlite()

    def _init_sqlite(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. Credits Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS credits (
                user_id TEXT PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 10,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # 2. Credit Transactions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS credit_transactions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # 3. Comics Table
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
                panel_urls TEXT DEFAULT '[]', -- JSON string of individual panel URLs
                final_page TEXT, -- URL to stitched final page
                created_at TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()

    def _supabase_request(self, method: str, path: str, payload: dict = None, params: dict = None) -> list:
        if not self.supabase_enabled:
            return []
            
        url = f"{self.supabase_url.rstrip('/')}/rest/v1/{path}"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json"
        }
        
        if method.upper() in ("POST", "PATCH"):
            headers["Prefer"] = "return=representation"
            
        try:
            if method.upper() == "GET":
                r = httpx.get(url, headers=headers, params=params, timeout=10.0)
            elif method.upper() == "POST":
                r = httpx.post(url, headers=headers, json=payload, timeout=10.0)
            elif method.upper() == "PATCH":
                r = httpx.patch(url, headers=headers, json=payload, params=params, timeout=10.0)
            else:
                return []
                
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[BillingService] Supabase {method} {path} error: {e}")
            return None

    def _local_upsert_credits(self, user_id: str, balance: int, created_at: str, updated_at: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO credits (user_id, balance, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                balance = excluded.balance,
                updated_at = excluded.updated_at
        ''', (user_id, balance, created_at, updated_at))
        conn.commit()
        conn.close()

    def get_or_create_balance(self, user_id: str) -> int:
        now = datetime.utcnow().isoformat()
        
        supabase_failed = False
        
        # 1. If Supabase is enabled, check balance there
        if self.supabase_enabled:
            try:
                data = self._supabase_request("GET", "credits", params={"user_id": f"eq.{user_id}"})
                if data is None:
                    supabase_failed = True
                elif len(data) > 0:
                    balance = data[0].get("balance", 10)
                    # Keep local SQLite in sync
                    self._local_upsert_credits(user_id, balance, now, now)
                    print("[CREDITS] Existing balance synced.")
                    return balance
                else:
                    # User doesn't exist in Supabase yet (GET succeeded but returned empty list)
                    # Check SQLite before seeding
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT balance FROM credits WHERE user_id = ?", (user_id,))
                    row = cursor.fetchone()
                    conn.close()
                    
                    if row:
                        balance = row[0]
                        print(f"[CREDITS] User not in Supabase but found in SQLite. Syncing SQLite balance ({balance}) to Supabase.")
                        self._supabase_request("POST", "credits", payload={
                            "user_id": user_id,
                            "balance": balance,
                            "created_at": now,
                            "updated_at": now
                        })
                        return balance
                    else:
                        # User does not exist in Supabase AND does not exist in SQLite
                        print("[CREDITS] No balance found anywhere.")
                        self._supabase_request("POST", "credits", payload={
                            "user_id": user_id,
                            "balance": 10,
                            "created_at": now,
                            "updated_at": now
                        })
                        self._local_upsert_credits(user_id, 10, now, now)
                        print("[CREDITS] Initial balance seeded.")
                        return 10
            except Exception as e:
                print(f"[Warning] Supabase fetch error in BillingService: {e}")
                supabase_failed = True

        if supabase_failed:
            print("[CREDITS] Supabase unavailable.")
            
        # 2. Local SQLite balance retrieval
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM credits WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            balance = row[0]
            if supabase_failed:
                print(f"[CREDITS] Using existing SQLite balance. (balance={balance})")
            return balance
        else:
            if supabase_failed:
                print("[CREDITS] BALANCE_VERIFICATION_FAILED")
                raise ValueError("Unable to verify account balance.\nPlease try again shortly.")
            
            # If supabase is not enabled, register locally
            print("[CREDITS] No balance found anywhere.")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO credits (user_id, balance, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, 10, now, now))
            conn.commit()
            conn.close()
            print("[CREDITS] Initial balance seeded.")
            return 10

    def deduct_credit(self, user_id: str, amount: int = 1, reason: str = "pdf_download") -> bool:
        current_balance = self.get_or_create_balance(user_id)
        if current_balance < amount:
            return False
            
        new_balance = current_balance - amount
        now = datetime.utcnow().isoformat()
        tx_id = str(uuid.uuid4())
        
        # 1. Update Supabase if enabled
        if self.supabase_enabled:
            self._supabase_request("PATCH", "credits", payload={"balance": new_balance, "updated_at": now}, params={"user_id": f"eq.{user_id}"})
            self._supabase_request("POST", "credit_transactions", payload={
                "id": tx_id,
                "user_id": user_id,
                "amount": -amount,
                "reason": reason,
                "created_at": now
            })
            
        # 2. Update local SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO credits (user_id, balance, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    balance = ?,
                    updated_at = ?
            ''', (user_id, new_balance, now, now, new_balance, now))
            
            cursor.execute('''
                INSERT INTO credit_transactions (id, user_id, amount, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (tx_id, user_id, -amount, reason, now))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[BillingService] SQLite credit deduction error: {e}")
            return False
        finally:
            conn.close()

    def create_comic(self, user_id: str, job_id: str, title: str, style: str, layout_type: str, panel_urls: list, final_page: str) -> str:
        comic_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        panel_urls_str = json.dumps(panel_urls)
        
        if self.supabase_enabled:
            self._supabase_request("POST", "comics", payload={
                "id": comic_id,
                "user_id": user_id,
                "job_id": job_id,
                "title": title,
                "style": style,
                "layout_type": layout_type,
                "panel_urls": panel_urls,
                "final_page": final_page,
                "created_at": now
            })
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO comics (id, user_id, job_id, title, style, layout_type, panel_urls, final_page, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (comic_id, user_id, job_id, title, style, layout_type, panel_urls_str, final_page, now))
        conn.commit()
        conn.close()
        
        return comic_id

    def get_comic_by_id(self, comic_id: str) -> dict:
        """
        Retrieves a comic by its ID, searching both the 'comics' and 'jobs' tables.
        """
        # 1. Search in 'comics' table first
        # 1.1 Supabase
        if self.supabase_enabled:
            data = self._supabase_request("GET", "comics", params={"id": f"eq.{comic_id}"})
            if data and len(data) > 0:
                comic = data[0]
                panel_urls = comic.get("panel_urls", [])
                if isinstance(panel_urls, str):
                    try:
                        panel_urls = json.loads(panel_urls)
                    except Exception:
                        panel_urls = []
                return {
                    "id": comic.get("id"),
                    "user_id": comic.get("user_id"),
                    "job_id": comic.get("job_id"),
                    "title": comic.get("title"),
                    "style": comic.get("style", "anime"),
                    "layout_type": comic.get("layout_type", "standard"),
                    "panel_urls": panel_urls,
                    "final_page": comic.get("final_page"),
                    "created_at": comic.get("created_at")
                }
                
        # 1.2 SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, job_id, title, style, layout_type, panel_urls, final_page, created_at FROM comics WHERE id = ?", (comic_id,))
        row = cursor.fetchone()
        if row:
            conn.close()
            panel_urls = []
            if row[6]:
                try:
                    panel_urls = json.loads(row[6])
                except Exception:
                    panel_urls = []
            return {
                "id": row[0],
                "user_id": row[1],
                "job_id": row[2],
                "title": row[3],
                "style": row[4],
                "layout_type": row[5],
                "panel_urls": panel_urls,
                "final_page": row[7],
                "created_at": row[8]
            }
            
        # 2. Search in 'jobs' table
        cursor.execute("SELECT job_id, result, style, layout_type, created_at FROM jobs WHERE job_id = ?", (comic_id,))
        job_row = cursor.fetchone()
        conn.close()
        
        if job_row:
            job_id, result_str, style, layout_type, created_at = job_row
            result = {}
            if result_str:
                try:
                    result = json.loads(result_str)
                except Exception:
                    pass
            
            panel_urls = result.get("panels", [])
            final_page = result.get("final_page")
            
            return {
                "id": job_id,
                "user_id": None,
                "job_id": job_id,
                "title": f"Comic #{job_id[:8]}",
                "style": style or "anime",
                "layout_type": layout_type or "standard",
                "panel_urls": panel_urls,
                "final_page": final_page,
                "created_at": created_at
            }
            
        # 3. Search in Supabase jobs
        if self.supabase_enabled:
            data = self._supabase_request("GET", "jobs", params={"job_id": f"eq.{comic_id}"})
            if data and len(data) > 0:
                job_data = data[0]
                result_str = job_data.get("result")
                result = {}
                if result_str:
                    try:
                        result = json.loads(result_str) if isinstance(result_str, str) else result_str
                    except Exception:
                        pass
                
                return {
                    "id": job_data.get("job_id"),
                    "user_id": None,
                    "job_id": job_data.get("job_id"),
                    "title": f"Comic #{job_data.get('job_id')[:8]}",
                    "style": job_data.get("style", "anime"),
                    "layout_type": job_data.get("layout_type", "standard"),
                    "panel_urls": result.get("panels", []),
                    "final_page": result.get("final_page"),
                    "created_at": job_data.get("created_at")
                }
                
        return None

billing_service = BillingService()
