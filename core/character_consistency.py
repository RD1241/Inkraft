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
                "base_description": ""
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
                
        return {
            "gender_tokens": ", ".join(gender_tokens),
            "hairstyle_tokens": ", ".join(hairstyle_tokens),
            "outfit_tokens": ", ".join(outfit_tokens),
            "base_description": ", ".join(other_tokens)
        }

    def add_or_update_character(self, name: str, description: str, role: str = None, panel_index: int = 0):
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
            SELECT hairstyle_tokens, gender_tokens, reference_image_path, reference_image_locked 
            FROM character_profiles 
            WHERE name = ?
        ''', (name_lower,))
        row = cursor.fetchone()
        
        if row is None:
            # First time seeing the character (Panel 1 / initial appearance)
            cursor.execute('''
                INSERT INTO character_profiles (
                    name, base_description, hairstyle_tokens, outfit_tokens, gender_tokens, role, reference_image_locked
                )
                VALUES (?, ?, ?, ?, ?, ?, 0)
            ''', (
                name_lower, 
                parsed["base_description"], 
                parsed["hairstyle_tokens"], 
                parsed["outfit_tokens"], 
                parsed["gender_tokens"], 
                role
            ))
        else:
            # Subsequent panel or updates
            existing_hair, existing_gender, ref_path, ref_locked = row
            
            # hairstyle_tokens (LOCKED after Panel 1)
            # gender_tokens (LOCKED)
            # outfit_tokens (dynamic updates)
            hair_to_save = existing_hair if (existing_hair or panel_index > 0) else parsed["hairstyle_tokens"]
            gender_to_save = existing_gender if (existing_gender or panel_index > 0) else parsed["gender_tokens"]
            outfit_to_save = parsed["outfit_tokens"] if parsed["outfit_tokens"] else ""
            
            cursor.execute('''
                UPDATE character_profiles
                SET base_description = ?,
                    hairstyle_tokens = ?,
                    outfit_tokens = ?,
                    gender_tokens = ?,
                    role = COALESCE(?, role)
                WHERE name = ?
            ''', (
                parsed["base_description"], 
                hair_to_save, 
                outfit_to_save, 
                gender_to_save, 
                role, 
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
            SELECT name, base_description, hairstyle_tokens, outfit_tokens, gender_tokens, role, reference_image_path, reference_image_locked
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
                "reference_image_locked": bool(row[7])
            }
        return None

    def lock_character_anchor(self, name: str, image_path: str):
        """
        Locks a character's reference image path, saving it to character_profiles.
        Logs the exact message:
        [CharacterConsistency] Anchor locked for {character_name} — reference saved to {path}
        """
        name_lower = name.lower()
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
            print(f"[CharacterConsistency] IP reference loaded for {name} at panel {panel_index}")
            return path
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
