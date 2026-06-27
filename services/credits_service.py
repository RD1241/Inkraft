import os
import sqlite3
import uuid
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


def clean_uuid(user_id: str) -> str:
    """
    Validates that user_id is a valid UUID. If not, generates a deterministic
    UUID from the input string to prevent database schema errors.
    """
    if not user_id:
        return "00000000-0000-0000-0000-000000000000"
    try:
        return str(uuid.UUID(user_id))
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, user_id))


class CreditsService:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(settings.DB_DIR, "jobs.db")
        self.supabase_url = load_env_var("SUPABASE_URL")
        self.supabase_key = load_env_var("SUPABASE_SECRET_KEY")
        self.supabase_enabled = bool(self.supabase_url and self.supabase_key)

        if self.supabase_enabled:
            print(f"[CreditsService] Supabase integration enabled. Syncing to {self.supabase_url}")
        else:
            print("[CreditsService] Supabase credentials not found. Local SQLite mode.")

        self._init_sqlite()

    def _init_sqlite(self):
        """Initializes the SQLite database with credits tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS credits (
                user_id TEXT PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS credit_transactions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    def get_balance(self, user_id: str) -> int:
        """
        Retrieves the user's current credit balance.
        If the user does not exist, registers them with 3 starting credits.
        """
        u_id = clean_uuid(user_id)
        now = datetime.utcnow().isoformat()

        supabase_failed = False

        # 1. Try querying Supabase if enabled
        if self.supabase_enabled:
            url = f"{self.supabase_url.rstrip('/')}/rest/v1/credits?user_id=eq.{u_id}"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}"
            }
            try:
                r = httpx.get(url, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    data = r.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        balance = int(data[0].get("balance", 10))
                        # Sync to local sqlite
                        self._sqlite_sync_balance(u_id, balance)
                        print("[CREDITS] Existing balance synced.")
                        return balance
                    else:
                        # User doesn't exist in Supabase yet (GET succeeded but returned empty list)
                        # Check SQLite before seeding
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute("SELECT balance FROM credits WHERE user_id = ?", (u_id,))
                        row = cursor.fetchone()
                        conn.close()
                        
                        if row is not None:
                            balance = row[0]
                            print(f"[CREDITS] User not in Supabase but found in SQLite. Syncing SQLite balance ({balance}) to Supabase.")
                            try:
                                credits_url = f"{self.supabase_url.rstrip('/')}/rest/v1/credits"
                                httpx.post(credits_url, headers={**headers, "Content-Type": "application/json"}, json={
                                    "user_id": u_id,
                                    "balance": balance,
                                    "created_at": now,
                                    "updated_at": now
                                }, timeout=10.0)
                            except Exception as e:
                                print(f"[Warning] Failed to sync local balance to Supabase: {e}")
                            return balance
                        else:
                            # User does not exist in Supabase AND does not exist in SQLite
                            print("[CREDITS] No balance found anywhere.")
                            return self._register_user(u_id)
                else:
                    print(f"[Warning] Supabase credits GET returned status: {r.status_code}")
                    supabase_failed = True
            except Exception as e:
                print(f"[Warning] Failed to fetch balance from Supabase: {e}. Falling back to SQLite.")
                supabase_failed = True

        if supabase_failed:
            print("[CREDITS] Supabase unavailable.")

        # 2. SQLite Fallback
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM credits WHERE user_id = ?", (u_id,))
        row = cursor.fetchone()
        conn.close()

        if row is not None:
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
            return self._register_user(u_id)

    def credits_for_panels(self, panel_count) -> int:
        """
        Credits charged for a comic of `panel_count` panels (tiered pricing so
        credits track real fal.ai cost without lowering quality). AI-decided
        count (None/0) is charged the configured default. See settings.CREDIT_PANEL_TIERS.
        """
        tiers = getattr(settings, "CREDIT_PANEL_TIERS", [(2, 1), (4, 2), (6, 3)])
        if not panel_count or panel_count <= 0:
            return getattr(settings, "CREDITS_AI_DEFAULT", 2)
        for max_p, cost in tiers:
            if panel_count <= max_p:
                return cost
        return tiers[-1][1]  # anything above the top tier pays the top rate

    def _register_user(self, user_id: str) -> int:
        """Registers a new user with the configured starting credits (settings.NEW_USER_CREDITS)."""
        now = datetime.utcnow().isoformat()
        starting_balance = getattr(settings, "NEW_USER_CREDITS", 5)
        txn_id = str(uuid.uuid4())

        # 1. SQLite registration
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Insert credit record
            cursor.execute('''
                INSERT OR IGNORE INTO credits (user_id, balance, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, starting_balance, now, now))
            # Insert starting credits transaction
            cursor.execute('''
                INSERT OR IGNORE INTO credit_transactions (id, user_id, amount, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (txn_id, user_id, starting_balance, "new_user_bonus", now))
            conn.commit()
            print("[CREDITS] Initial balance seeded.")
        except Exception as e:
            print(f"[Error] Local registration failed: {e}")
        finally:
            conn.close()

        # 2. Supabase registration if enabled
        if self.supabase_enabled:
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            # Post credits row
            try:
                credits_url = f"{self.supabase_url.rstrip('/')}/rest/v1/credits"
                httpx.post(credits_url, headers=headers, json={
                    "user_id": user_id,
                    "balance": starting_balance,
                    "created_at": now,
                    "updated_at": now
                }, timeout=10.0)
            except Exception as e:
                print(f"[Warning] Failed to post starting balance to Supabase: {e}")

            # Post transaction row
            try:
                txn_url = f"{self.supabase_url.rstrip('/')}/rest/v1/credit_transactions"
                httpx.post(txn_url, headers=headers, json={
                    "id": txn_id,
                    "user_id": user_id,
                    "amount": starting_balance,
                    "reason": "new_user_bonus",
                    "created_at": now
                }, timeout=10.0)
            except Exception as e:
                print(f"[Warning] Failed to post starting transaction to Supabase: {e}")

        return starting_balance

    def _sqlite_sync_balance(self, user_id: str, balance: int):
        """Syncs the balance from Supabase back to local SQLite."""
        now = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO credits (user_id, balance, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    balance = excluded.balance,
                    updated_at = excluded.updated_at
            ''', (user_id, balance, now, now))
            conn.commit()
        except Exception as e:
            print(f"[Warning] Failed to sync balance to local SQLite: {e}")
        finally:
            conn.close()

    def get_history(self, user_id: str) -> list:
        """Retrieves user credit ledger transaction history."""
        u_id = clean_uuid(user_id)
        # Guarantee user is registered
        self.get_balance(u_id)

        # 1. Supabase Query
        if self.supabase_enabled:
            url = f"{self.supabase_url.rstrip('/')}/rest/v1/credit_transactions?user_id=eq.{u_id}&order=created_at.desc"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}"
            }
            try:
                r = httpx.get(url, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    return r.json()
            except Exception as e:
                print(f"[Warning] Failed to fetch transaction history from Supabase: {e}. Falling back to SQLite.")

        # 2. SQLite Fallback Query
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, amount, reason, created_at
            FROM credit_transactions
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (u_id,))
        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            history.append({
                "id": row[0],
                "user_id": row[1],
                "amount": row[2],
                "reason": row[3],
                "created_at": row[4]
            })
        return history

    def deduct_credit(self, user_id: str, re_generate: bool = False, amount: int = 1) -> bool:
        """
        Checks balance, then deducts `amount` credits from user balance and registers a
        transaction of -amount with reason 'generation' or 'regeneration'.
        """
        u_id = clean_uuid(user_id)
        amount = max(1, int(amount))

        # Get current balance
        balance = self.get_balance(u_id)
        if balance < amount:
            raise ValueError(
                f"Insufficient credits. This comic needs {amount} credit(s); balance: {balance}."
            )

        new_balance = balance - amount
        now = datetime.utcnow().isoformat()
        txn_id = str(uuid.uuid4())
        reason = "regeneration" if re_generate else "generation"

        # 1. Update SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Update balance
            cursor.execute("UPDATE credits SET balance = ?, updated_at = ? WHERE user_id = ?", (new_balance, now, u_id))
            # Insert transaction
            cursor.execute('''
                INSERT INTO credit_transactions (id, user_id, amount, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (txn_id, u_id, -amount, reason, now))
            conn.commit()
        except Exception as e:
            print(f"[Error] Local deduction failed: {e}")
            conn.close()
            raise RuntimeError("Database update failed")
        finally:
            conn.close()

        # 2. Update Supabase
        if self.supabase_enabled:
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            # Update credits
            try:
                credits_url = f"{self.supabase_url.rstrip('/')}/rest/v1/credits?user_id=eq.{u_id}"
                httpx.patch(credits_url, headers=headers, json={
                    "balance": new_balance,
                    "updated_at": now
                }, timeout=10.0)
            except Exception as e:
                print(f"[Warning] Failed to update balance in Supabase: {e}")

            # Post transaction row
            try:
                txn_url = f"{self.supabase_url.rstrip('/')}/rest/v1/credit_transactions"
                httpx.post(txn_url, headers=headers, json={
                    "id": txn_id,
                    "user_id": u_id,
                    "amount": -amount,
                    "reason": reason,
                    "created_at": now
                }, timeout=10.0)
            except Exception as e:
                print(f"[Warning] Failed to post deduction transaction in Supabase: {e}")

        return True


    def refund_credit(self, user_id: str, amount: int = 1) -> bool:
        """
        Refunds `amount` credits back to user balance (e.g. generation failure).
        Registers a transaction of +amount with reason 'refund'.
        """
        u_id = clean_uuid(user_id)
        amount = max(1, int(amount))
        balance = self.get_balance(u_id)
        new_balance = balance + amount
        now = datetime.utcnow().isoformat()
        txn_id = str(uuid.uuid4())

        # 1. Update SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Update balance
            cursor.execute("UPDATE credits SET balance = ?, updated_at = ? WHERE user_id = ?", (new_balance, now, u_id))
            # Insert transaction
            cursor.execute('''
                INSERT INTO credit_transactions (id, user_id, amount, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (txn_id, u_id, amount, "refund", now))
            conn.commit()
        except Exception as e:
            print(f"[Error] Local refund failed: {e}")
            conn.close()
            return False
        finally:
            conn.close()

        # 2. Update Supabase
        if self.supabase_enabled:
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            # Update credits
            try:
                credits_url = f"{self.supabase_url.rstrip('/')}/rest/v1/credits?user_id=eq.{u_id}"
                httpx.patch(credits_url, headers=headers, json={
                    "balance": new_balance,
                    "updated_at": now
                }, timeout=10.0)
            except Exception as e:
                print(f"[Warning] Failed to update refunded balance in Supabase: {e}")

            # Post transaction row
            try:
                txn_url = f"{self.supabase_url.rstrip('/')}/rest/v1/credit_transactions"
                httpx.post(txn_url, headers=headers, json={
                    "id": txn_id,
                    "user_id": u_id,
                    "amount": amount,
                    "reason": "refund",
                    "created_at": now
                }, timeout=10.0)
            except Exception as e:
                print(f"[Warning] Failed to post refund transaction in Supabase: {e}")

        return True

    def get_daily_usage(self, user_id: str) -> dict:
        """
        Returns a dictionary summarizing:
          - balance: user's current credit balance
          - usage_today: number of generations today
          - reset_countdown_seconds: seconds until the next UTC day starts
        """
        u_id = clean_uuid(user_id)
        balance = self.get_balance(u_id)
        
        # Calculate start of day in UTC
        start_of_day = datetime.utcnow().date().isoformat() + "T00:00:00"
        
        # Count successful generations today
        if self.supabase_enabled:
            url = f"{self.supabase_url.rstrip('/')}/rest/v1/credit_transactions?user_id=eq.{u_id}&reason=eq.generation&created_at=gte.{start_of_day}"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}"
            }
            try:
                r = httpx.get(url, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    data = r.json()
                    usage_today = sum(1 for item in data if int(item.get("amount", 0)) < 0)
                else:
                    usage_today = 0
            except Exception as e:
                print(f"[Warning] Failed to fetch usage from Supabase: {e}. Falling back to SQLite.")
                usage_today = self._sqlite_count_usage(u_id, start_of_day)
        else:
            usage_today = self._sqlite_count_usage(u_id, start_of_day)
            
        # Calculate seconds until next UTC day (00:00:00)
        from datetime import time as dt_time, timedelta
        now = datetime.utcnow()
        next_day = datetime.combine(now.date() + timedelta(days=1), dt_time.min)
        reset_countdown_seconds = int((next_day - now).total_seconds())
        
        return {
            "balance": balance,
            "usage_today": usage_today,
            "reset_countdown_seconds": reset_countdown_seconds
        }

    def _sqlite_count_usage(self, user_id: str, start_of_day: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM credit_transactions
            WHERE user_id = ? AND reason = 'generation' AND amount < 0 AND created_at >= ?
        ''', (user_id, start_of_day))
        count = cursor.fetchone()[0]
        conn.close()
        return count

credits_service = CreditsService()
