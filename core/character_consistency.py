"""
core/character_consistency.py
Stage 2 — Component 2E
Description: Implements the CharacterConsistency class which manages character profiles,
identity anchors, IP-Adapter reference images, and dominant character selection.
"""

import sqlite3
import os
from config import settings

class CharacterConsistency:
    def __init__(self, db_path=None):
        self.db_path = db_path or settings.DB_PATH
        self._init_db()

    def _init_db(self):
        """Initializes the character_profiles table in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS character_profiles (
                name TEXT PRIMARY KEY,
                base_description TEXT,
                hairstyle_tokens TEXT,
                outfit_tokens TEXT,
                gender_tokens TEXT,
                role TEXT,
                reference_image_path TEXT,
                reference_image_locked INTEGER DEFAULT 0
            )
        ''')
        # Safe runtime alterations to add columns if they don't exist
        try:
            cursor.execute("ALTER TABLE character_profiles ADD COLUMN gender TEXT")
        except sqlite3.OperationalError:
            pass # Already exists
        try:
            cursor.execute("ALTER TABLE character_profiles ADD COLUMN gender_locked INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass # Already exists
        try:
            cursor.execute("ALTER TABLE character_profiles ADD COLUMN hair_color_token TEXT")
        except sqlite3.OperationalError:
            pass # Already exists
        try:
            cursor.execute("ALTER TABLE character_profiles ADD COLUMN hair_style_token TEXT")
        except sqlite3.OperationalError:
            pass # Already exists
        conn.commit()
        conn.close()

    def clear_profiles(self):
        """Wipes all character consistency profiles."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM character_profiles')
        conn.commit()
        conn.close()

    def parse_description(self, description: str) -> dict:
        """
        Parses a raw character description string to extract gender, hair, outfit, and base descriptions.
        Splits by comma to handle the LLM's structured output format cleanly.
        """
        if not description:
            return {
                "gender_tokens": "",
                "hairstyle_tokens": "",
                "outfit_tokens": "",
                "base_description": "",
                "hair_color_token": "",
                "hair_style_token": ""
            }

        parts = [p.strip() for p in description.split(",") if p.strip()]
        
        gender_words = {"male", "female", "man", "woman", "boy", "girl", "guy", "lady", "gentleman"}
        hair_words = {"hair", "ponytail", "bald", "braids", "coils", "dreadlocks", "afro", "mohawk"}
        outfit_words = {
            "wearing", "outfit", "armor", "jacket", "shirt", "pants", "suit", "dress", 
            "clothing", "clothes", "robe", "cloak", "uniform", "hat", "cap", "boots", "shoes"
        }
        
        gender_tokens = []
        hairstyle_tokens = []
        outfit_tokens = []
        other_tokens = []
        
        for part in parts:
            part_lower = part.lower()
            if any(w in part_lower for w in gender_words):
                gender_tokens.append(part)
            elif any(w in part_lower for w in hair_words):
                hairstyle_tokens.append(part)
            elif any(w in part_lower for w in outfit_words):
                outfit_tokens.append(part)
            else:
                other_tokens.append(part)
                
        # Split hairstyle_tokens into hair_color_token and hair_style_token
        hair_colors = ["black", "brown", "blonde", "blond", "red", "silver", "grey", "gray", "white", "pink", "blue", "green", "purple", "yellow"]
        hair_color_token = ""
        hair_style_tokens = []
        for t in hairstyle_tokens:
            t_lower = t.lower()
            found_color = None
            for col in hair_colors:
                if col in t_lower:
                    found_color = col
                    break
            if found_color:
                col_name = "blonde" if found_color == "blond" else found_color
                hair_color_token = f"{col_name} hair"
                style_part = t_lower.replace(found_color, "").replace("  ", " ").strip()
                if style_part and style_part != "hair":
                    hair_style_tokens.append(style_part)
            else:
                hair_style_tokens.append(t)
        
        if not hair_style_tokens and hairstyle_tokens:
            hair_style_tokens = ["hair"]
            
        hair_style_token = ", ".join(hair_style_tokens)

        return {
            "gender_tokens": ", ".join(gender_tokens),
            "hairstyle_tokens": ", ".join(hairstyle_tokens),
            "outfit_tokens": ", ".join(outfit_tokens),
            "base_description": ", ".join(other_tokens),
            "hair_color_token": hair_color_token,
            "hair_style_token": hair_style_token
        }

    def add_or_update_character(self, name: str, description: str, role: str = None, panel_index: int = 0, story_text: str = None, memory_manager = None):
        """
        Inserts or updates a character profile.
        - Hairstyle tokens and Gender tokens are locked after their initial insert (Panel 1/first appearance).
        - Outfit tokens are dynamically updated on subsequent panels.
        """
        if not name:
            return

        name_lower = name.lower()
        parsed = self.parse_description(description)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if character already exists
        cursor.execute('''
            SELECT hairstyle_tokens, gender_tokens, reference_image_path, reference_image_locked, gender, gender_locked, hair_color_token, hair_style_token
            FROM character_profiles 
            WHERE name = ?
        ''', (name_lower,))
        row = cursor.fetchone()
        
        # Check design sheet override
        design_sheet_gender = None
        if memory_manager and hasattr(memory_manager, "get_design_sheet"):
            sheet = memory_manager.get_design_sheet(name_lower)
            if sheet and getattr(sheet, "gender", None):
                design_sheet_gender = sheet.gender.lower()
        
        if row is None:
            # First time seeing the character (Panel 1 / initial appearance)
            gender_source = "default"
            if design_sheet_gender:
                gender = design_sheet_gender
                gender_source = "design_sheet"
                # Log design sheet detection
                print(f"[CharacterDetection] {name}: detected gender = {gender} (source: {gender_source})")
            else:
                # Use pronoun detector
                from core.llm_processor import LLMProcessor
                gender = LLMProcessor.detect_character_gender(name, story_text)
            
            # Map gender to gender_tokens
            if gender == "female":
                gender_tokens = "1girl, female"
            elif gender == "male":
                gender_tokens = "1boy, male"
            else:
                gender_tokens = parsed["gender_tokens"]

            # Lock the gender permanently if panel_index > 0
            gender_locked_val = 1 if panel_index > 0 else 0

            cursor.execute('''
                INSERT INTO character_profiles (
                    name, base_description, hairstyle_tokens, outfit_tokens, gender_tokens, role, reference_image_locked, gender, gender_locked, hair_color_token, hair_style_token
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            ''', (
                name_lower, 
                parsed["base_description"], 
                parsed["hairstyle_tokens"], 
                parsed["outfit_tokens"], 
                gender_tokens, 
                role,
                gender,
                gender_locked_val,
                parsed["hair_color_token"],
                parsed["hair_style_token"]
            ))
        else:
            # Subsequent panel or updates
            existing_hair, existing_gender_tokens, ref_path, ref_locked, existing_gender, existing_gender_locked, existing_hair_color, existing_hair_style = row
            
            # If design sheet is provided, it always overrides unless we already have design_sheet gender locked
            if design_sheet_gender:
                gender = design_sheet_gender
                gender_locked_val = 1
                if gender == "female":
                    gender_tokens = "1girl, female"
                elif gender == "male":
                    gender_tokens = "1boy, male"
                else:
                    gender_tokens = parsed["gender_tokens"]
            elif existing_gender_locked:
                gender = existing_gender
                gender_tokens = existing_gender_tokens
                gender_locked_val = 1
            else:
                # Not locked yet
                if panel_index > 0:
                    # Time to lock it!
                    gender_locked_val = 1
                    # Keep existing gender or detect if not yet set
                    gender = existing_gender
                    if not gender:
                        from core.llm_processor import LLMProcessor
                        gender = LLMProcessor.detect_character_gender(name, story_text)
                    if gender == "female":
                        gender_tokens = "1girl, female"
                    elif gender == "male":
                        gender_tokens = "1boy, male"
                    else:
                        gender_tokens = existing_gender_tokens or parsed["gender_tokens"]
                else:
                    # Still panel 1, we can redetect/update
                    gender_locked_val = 0
                    from core.llm_processor import LLMProcessor
                    gender = LLMProcessor.detect_character_gender(name, story_text)
                    if gender == "female":
                        gender_tokens = "1girl, female"
                    elif gender == "male":
                        gender_tokens = "1boy, male"
                    else:
                        gender_tokens = parsed["gender_tokens"]
            
            hair_to_save = existing_hair if (existing_hair or panel_index > 0) else parsed["hairstyle_tokens"]
            outfit_to_save = parsed["outfit_tokens"] if parsed["outfit_tokens"] else ""
            
            hair_color_to_save = existing_hair_color if (existing_hair_color or panel_index > 0) else parsed["hair_color_token"]
            hair_style_to_save = existing_hair_style if (existing_hair_style or panel_index > 0) else parsed["hair_style_token"]
            
            cursor.execute('''
                UPDATE character_profiles
                SET base_description = ?,
                    hairstyle_tokens = ?,
                    outfit_tokens = ?,
                    gender_tokens = ?,
                    role = COALESCE(?, role),
                    gender = ?,
                    gender_locked = ?,
                    hair_color_token = ?,
                    hair_style_token = ?
                WHERE name = ?
            ''', (
                parsed["base_description"], 
                hair_to_save, 
                outfit_to_save, 
                gender_tokens, 
                role,
                gender,
                gender_locked_val,
                hair_color_to_save,
                hair_style_to_save,
                name_lower
            ))
            
        conn.commit()
        conn.close()

    def get_profile(self, name: str) -> dict:
        """Retrieves a character profile as a dictionary."""
        if not name:
            return None

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, base_description, hairstyle_tokens, outfit_tokens, gender_tokens, role, reference_image_path, reference_image_locked, gender, gender_locked, hair_color_token, hair_style_token
            FROM character_profiles
            WHERE name = ?
        ''', (name.lower(),))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "name": row[0],
                "base_description": row[1],
                "hairstyle_tokens": row[2],
                "outfit_tokens": row[3],
                "gender_tokens": row[4],
                "role": row[5],
                "reference_image_path": row[6],
                "reference_image_locked": bool(row[7]),
                "gender": row[8],
                "gender_locked": bool(row[9]),
                "hair_color_token": row[10] if row[10] else "",
                "hair_style_token": row[11] if row[11] else ""
            }
        return None

    def validate_reference_image(self, image_path: str) -> bool:
        if not image_path or not os.path.exists(image_path):
            return False
        try:
            if os.path.getsize(image_path) < 1024:
                return False
            from PIL import Image
            with Image.open(image_path) as img:
                w, h = img.size
                if w <= 0 or h <= 0:
                    return False
                extrema = img.convert("L").getextrema()
                if extrema[1] < 10:
                    return False
            return True
        except Exception:
            return False

    def lock_character_anchor(self, name: str, image_path: str):
        """
        Locks a character's reference image path, saving it to character_profiles.
        Logs the exact message:
        [CharacterConsistency] Anchor locked for {character_name} — reference saved to {path}
        """
        name_lower = name.lower()
        
        # Validate reference image before saving
        if not self.validate_reference_image(image_path):
            print(f"[CharacterConsistency] Reference validation failed for {name}. Skipping consistency lock.")
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if character exists
        cursor.execute("SELECT name FROM character_profiles WHERE name = ?", (name_lower,))
        if cursor.fetchone() is None:
            cursor.execute('''
                INSERT INTO character_profiles (name, reference_image_path, reference_image_locked)
                VALUES (?, ?, 1)
            ''', (name_lower, image_path))
        else:
            cursor.execute('''
                UPDATE character_profiles
                SET reference_image_path = ?,
                    reference_image_locked = 1
                WHERE name = ?
            ''', (image_path, name_lower))
        conn.commit()
        conn.close()
        
        print(f"[CharacterConsistency] Anchor locked for {name} — reference saved to {image_path}")

    def get_ip_adapter_reference(self, name: str, panel_index: int = 0) -> str:
        """
        Retrieves the IP-Adapter reference image path for a character.
        Logs the exact message on load:
        [CharacterConsistency] IP reference loaded for {character_name} at panel {index}
        """
        name_lower = name.lower()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT reference_image_path FROM character_profiles WHERE name = ?", (name_lower,))
        row = cursor.fetchone()
        conn.close()
        
        path = row[0] if row else None
        if path:
            if self.validate_reference_image(path):
                print(f"[CharacterConsistency] IP reference loaded for {name} at panel {panel_index}")
                return path
            else:
                print(f"[CharacterConsistency] Reference validation failed for {name} during load. Automatically disabling.")
                # Clear path and disable lock
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE character_profiles
                    SET reference_image_path = NULL,
                        reference_image_locked = 0
                    WHERE name = ?
                ''', (name_lower,))
                conn.commit()
                conn.close()
        return None

    def select_dominant_character(self, scene: dict) -> str:
        """
        Selects the dominant character in the scene based on focus and dialogue speaker priority.
        """
        characters = scene.get("characters", [])
        if not characters:
            focus = scene.get("focus_character")
            return focus if focus else None
            
        focus_char = str(scene.get("focus_character", "")).strip().lower()
        dialogues = scene.get("dialogue", [])
        
        # Extract speakers
        speakers = [str(d.get("speaker", "")).strip().lower() for d in dialogues if d.get("speaker")]
        
        best_char = None
        best_score = -1
        
        for char in characters:
            char_name = str(char.get("name", "")).strip()
            name_lower = char_name.lower()
            if not name_lower:
                continue
                
            score = 0
            
            # Focus character priority
            if focus_char and (focus_char in name_lower or name_lower in focus_char):
                score += 10
                
            # Speaker priority
            if speakers:
                if name_lower in speakers:
                    score += 5
                    # Extra priority if they are the first speaker
                    if speakers[0] == name_lower:
                        score += 2
                        
            # Role priority
            role = str(char.get("character_role", "")).lower()
            if role == "main_character":
                score += 3
            elif role == "secondary_character":
                score += 1
                
            if score > best_score:
                best_score = score
                best_char = char_name
                
        return best_char

    def get_dominant_character(self, scene: dict) -> str:
        """Alias for select_dominant_character."""
        return self.select_dominant_character(scene)
