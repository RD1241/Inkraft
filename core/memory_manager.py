import sqlite3
import os
from config import settings
from core.character_consistency import CharacterConsistency

class MemoryManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or settings.DB_PATH
        self.consistency = CharacterConsistency(db_path=self.db_path)
        self.active_sheets = {}
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Simple schema to track character visual attributes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                description TEXT
            )
        ''')
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
        conn.commit()
        conn.close()

    def clear_memory(self):
        """Wipes the memory for a fresh generation job."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM characters')
        conn.commit()
        conn.close()
        
        # Also wipe character consistency profiles
        self.consistency.clear_profiles()

    def add_character(self, name: str, description: str, role: str = None, panel_index: int = 0):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        name_lower = name.lower()

        try:
            # IDENTITY LOCK: First description from Panel 1 is the immutable anchor.
            # ON CONFLICT DO NOTHING ensures later panels never overwrite Panel 1's anchor.
            cursor.execute('''
                INSERT INTO characters (name, description)
                VALUES (?, ?)
                ON CONFLICT(name) DO NOTHING
            ''', (name_lower, description))
            conn.commit()
        except Exception as e:
            print(f"Memory update error: {e}")
        finally:
            conn.close()

        # Update or add character in the CharacterConsistency profiles
        self.consistency.add_or_update_character(name, description, role=role, panel_index=panel_index)

    def get_character(self, name: str) -> str:
        # Check case-insensitive CharacterDesignSheet override
        if hasattr(self, "active_sheets") and name.lower() in self.active_sheets:
            return self.active_sheets[name.lower()].to_prompt_tokens()

        # First, try to retrieve profile from CharacterConsistency
        profile = self.consistency.get_profile(name)
        if profile:
            # Combine the parts: gender_tokens, hairstyle_tokens, base_description, outfit_tokens
            parts = []
            if profile.get("gender_tokens"):
                parts.append(profile["gender_tokens"])
            if profile.get("hairstyle_tokens"):
                parts.append(profile["hairstyle_tokens"])
            if profile.get("base_description"):
                parts.append(profile["base_description"])
            if profile.get("outfit_tokens"):
                parts.append(profile["outfit_tokens"])
            return ", ".join(parts)

        # Fallback to the original table
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT description FROM characters WHERE name = ?', (name.lower(),))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def get_design_sheet(self, name: str):
        if hasattr(self, "active_sheets") and name.lower() in self.active_sheets:
            return self.active_sheets[name.lower()]
        return None

    def load_character_design_sheets(self, user_id: str, request_sheets: list = None):
        """
        Loads character design sheets from the cache/Supabase or from the API request payload.
        Stores them in self.active_sheets for case-insensitive lookup during this job.
        """
        self.active_sheets = {}
        
        # 1. Load from DB/Supabase if user_id is provided
        if user_id:
            db_sheets = self._fetch_design_sheets_for_user(user_id)
            for sheet in db_sheets:
                self.active_sheets[sheet.name.lower()] = sheet
                
        # 2. Overwrite/add sheets passed directly in the request payload (if any)
        if request_sheets:
            from core.character_designer import CharacterDesignSheet
            for sheet_data in request_sheets:
                if isinstance(sheet_data, dict):
                    try:
                        sheet = CharacterDesignSheet(**sheet_data)
                        self.active_sheets[sheet.name.lower()] = sheet
                    except Exception as e:
                        print(f"[Warning] Failed to parse request character design sheet: {e}")

    def _fetch_design_sheets_for_user(self, user_id: str):
        from core.character_designer import CharacterDesignSheet
        sheets = []
        
        # Try Supabase if enabled
        from providers.auth.supabase_auth import SupabaseAuth
        auth = SupabaseAuth()
        if auth.enabled and auth.client:
            try:
                res = auth.client.table("characters").select("*").eq("user_id", user_id).execute()
                data = getattr(res, "data", []) or []
                for row in data:
                    # Map possible Supabase column names to the local fields
                    sheets.append(CharacterDesignSheet(
                        name=row.get("name"),
                        gender=row.get("gender"),
                        age_range=row.get("age_range"),
                        hair_style=row.get("hair_style") or row.get("hair_description", ""),
                        hair_color=row.get("hair_color") or "",
                        eye_color=row.get("eye_color") or "",
                        body_type=row.get("body_type") or "",
                        primary_outfit=row.get("primary_outfit") or row.get("outfit", ""),
                        distinguishing_features=row.get("distinguishing_features") or row.get("features", ""),
                        personality_note=row.get("personality_note") or row.get("personality", "")
                    ))
                return sheets
            except Exception as e:
                print(f"[Warning] Failed to fetch characters from Supabase: {e}. Falling back to SQLite cache.")

        # Fallback to local SQLite cache
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT name, gender, age_range, hair_style, hair_color, eye_color, body_type, primary_outfit, distinguishing_features, personality_note
                FROM character_design_sheets
                WHERE user_id = ?
            ''', (user_id,))
            rows = cursor.fetchall()
            for r in rows:
                sheets.append(CharacterDesignSheet(
                    name=r[0],
                    gender=r[1],
                    age_range=r[2],
                    hair_style=r[3],
                    hair_color=r[4],
                    eye_color=r[5],
                    body_type=r[6],
                    primary_outfit=r[7],
                    distinguishing_features=r[8],
                    personality_note=r[9]
                ))
        except Exception as e:
            print(f"[Error] Failed to fetch character design sheets from SQLite: {e}")
        finally:
            conn.close()
            
        return sheets
        
    def process_scene_characters(self, scene_data: dict):
        """Extracts characters from scene JSON data and saves them to memory."""
        scene_id = scene_data.get("scene_id", 1)
        panel_index = scene_id - 1
        for character in scene_data.get('characters', []):
            name = character.get('name')
            desc = character.get('description')
            role = character.get('character_role')
            if name and desc:
                self.add_character(name, desc, role=role, panel_index=panel_index)

