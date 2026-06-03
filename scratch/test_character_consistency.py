import sys
import os

# Adjust path to find core/config modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.character_consistency import CharacterConsistency
from core.memory_manager import MemoryManager

def test_character_consistency():
    print("=== Testing CharacterConsistency and MemoryManager ===")
    
    # 1. Initialize MemoryManager (which also initializes CharacterConsistency)
    # Use a test DB in scratch directory to avoid modifying production DB
    test_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_character_memory.db")
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        
    mm = MemoryManager(db_path=test_db_path)
    cc = mm.consistency
    
    # 2. Add a character on Panel 1 (panel_index = 0)
    # The first appearance is their Panel 1. This locks gender & hairstyle.
    desc_p1 = "young male warrior, spiky black hair, intense eyes, wearing iron plate armor"
    print(f"Adding character 'Arthur' on Panel 1 with: '{desc_p1}'")
    mm.add_character("Arthur", desc_p1, role="main_character", panel_index=0)
    
    # Verify profile creation
    profile = cc.get_profile("Arthur")
    print(f"Retrieved profile: {profile}")
    assert profile["name"] == "arthur"
    assert profile["gender_tokens"] == "young male warrior"
    assert profile["hairstyle_tokens"] == "spiky black hair"
    assert profile["outfit_tokens"] == "wearing iron plate armor"
    assert profile["base_description"] == "intense eyes"
    assert profile["role"] == "main_character"
    
    # 3. Add same character on Panel 2 with a new outfit and slightly different hair/gender description
    # Hairstyle & Gender are LOCKED after Panel 1, but Outfit is updated dynamically.
    desc_p2 = "older male warrior, long blonde hair, intense eyes, wearing a royal blue cloak"
    print(f"Updating character 'Arthur' on Panel 2 with: '{desc_p2}'")
    mm.add_character("Arthur", desc_p2, role="main_character", panel_index=1)
    
    # Verify profile updates
    profile_p2 = cc.get_profile("Arthur")
    print(f"Retrieved profile after Panel 2 update: {profile_p2}")
    # Hair and gender must NOT change
    assert profile_p2["gender_tokens"] == "young male warrior", "Gender token was not locked!"
    assert profile_p2["hairstyle_tokens"] == "spiky black hair", "Hairstyle token was not locked!"
    # Outfit MUST be updated dynamically
    assert profile_p2["outfit_tokens"] == "wearing a royal blue cloak", "Outfit was not updated dynamically!"
    
    # 4. Test reconstructed prompt description
    rec_desc = mm.get_character("Arthur")
    print(f"Reconstructed Description for prompt builder: '{rec_desc}'")
    assert "young male warrior" in rec_desc
    assert "spiky black hair" in rec_desc
    assert "intense eyes" in rec_desc
    assert "wearing a royal blue cloak" in rec_desc
    
    # 5. Test anchor locking
    print("Testing Anchor Locking:")
    anchor_path = "outputs/characters/arthur_anchor.png"
    cc.lock_character_anchor("Arthur", anchor_path)
    profile_locked = cc.get_profile("Arthur")
    assert profile_locked["reference_image_path"] == anchor_path
    assert profile_locked["reference_image_locked"] is True
    
    # 6. Test reference loading with logging
    print("Testing Reference Loading:")
    ref_path = cc.get_ip_adapter_reference("Arthur", panel_index=2)
    assert ref_path == anchor_path
    
    # 7. Test dominant character selection
    print("Testing Dominant Character Selection:")
    scene = {
        "scene_id": 1,
        "focus_character": "Arthur",
        "characters": [
            {"name": "Arthur", "character_role": "main_character", "description": "young male warrior"},
            {"name": "Goblin", "character_role": "enemy_character", "description": "small green monster"}
        ],
        "dialogue": [
            {"speaker": "Arthur", "text": "Prepare to face justice!"}
        ]
    }
    dom_char = cc.get_dominant_character(scene)
    print(f"Selected Dominant Character: '{dom_char}'")
    assert dom_char == "Arthur"
    
    # 8. Clean up
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    print("=== All tests passed successfully! ===")

if __name__ == "__main__":
    test_character_consistency()
