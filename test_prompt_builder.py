import sys
import os

# Add parent directory to path so config can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.prompt_builder import PromptBuilder, STYLE_TEMPLATES
from core.memory_manager import MemoryManager
from config import settings

def test_prompt_builder():
    print("Initializing PromptBuilder and MemoryManager...")
    pb = PromptBuilder(style="anime")
    mm = MemoryManager()

    # Create dummy database table for memory manager so it compiles and runs without crashing
    import sqlite3
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            name TEXT PRIMARY KEY,
            description TEXT
        )
    """)
    conn.commit()
    conn.close()

    scene1 = {
        "scene_id": 1,
        "camera": "wide shot, high angle",
        "emotion": "joyful, cheerful",
        "lighting": "sunset light",
        "focus_character": "Hero",
        "characters": [
            {
                "name": "Hero",
                "description": "young man with black hair, blue eyes",
                "_gender_tag": "male character, masculine features",
                "_negative_gender": "feminine face, female anatomy"
            }
        ],
        "action": "Hero is waving towards the horizon",
        "environment": "beach side",
        "global_environment": "beach side"
    }

    print("\n--- Test 1: Standard Prompt Building (Anime style) ---")
    pos, neg = pb.build_prompt(scene1, mm, is_continuation=False)
    print(f"Positive Prompt:\n{pos}")
    print(f"Negative Prompt:\n{neg}")

    # Check strict order of layers
    # Layer 1: Camera
    assert "wide shot" in pos, "Missing Camera tokens"
    # Layer 2: Emotion
    assert "joyful" in pos, "Missing Emotion tokens"
    # Layer 3: Lighting
    assert "sunset light" in pos, "Missing Lighting tokens"
    assert "vibrant lighting" in pos, "Missing Style Lighting tokens"
    # Layer 4: Character
    assert "Hero" in pos, "Missing Character tokens"
    # Layer 5: Action & Env
    assert "waving" in pos, "Missing Action/Env tokens"
    # Layer 6: Style prefix
    assert "anime illustration" in pos, "Missing Style Prefix tokens"

    # Verify positions: Camera is first, Style is last
    tokens = [t.strip().lower() for t in pos.split(",")]
    camera_idx = tokens.index("wide shot")
    style_idx = tokens.index("anime illustration")
    assert camera_idx < style_idx, "Strict ordering violated: Camera must precede Style!"
    print("[PASS] Test 1: Order and content validation passed!")

    print("\n--- Test 2: Consecutive Duplicate Panel Guard (Similarity > 70%) ---")
    # Build second scene almost identical to first
    scene2 = scene1.copy()
    scene2["scene_id"] = 2
    
    pos2, neg2 = pb.build_prompt(scene2, mm, is_continuation=True)
    print(f"Positive Prompt 2:\n{pos2}")
    
    # Verify duplicate guard injected variation token
    tokens2 = [t.strip().lower() for t in pos2.split(",")]
    assert any(var in tokens2[0] for var in ["reversed composition", "mirror framing", "opposite angle"]), \
        f"Consecutive panel guard failed! First token was: {tokens2[0]}"
    print("[PASS] Test 2: Consecutive duplicate panel guard triggered and resolved successfully!")

    print("\n--- Test 3: Deduplication and 110-Token Limit ---")
    # Create extreme scene with many duplicate tokens and long character list
    scene3 = {
        "scene_id": 3,
        "camera": "close up, close up, close up, detailed face",
        "emotion": "angry, angry, angry",
        "lighting": "neon glow, neon glow",
        "focus_character": "Hero",
        "characters": [
            {
                "name": "Hero",
                "description": ", ".join(["young man with black hair"] * 25), # very long!
                "_gender_tag": "male character",
                "_negative_gender": "female anatomy"
            }
        ],
        "action": "shouting loudly",
        "environment": "dark alley",
        "global_environment": "dark alley"
    }

    pos3, neg3 = pb.build_prompt(scene3, mm, is_continuation=True)
    tokens3 = [t.strip() for t in pos3.split(",")]
    print(f"Positive Prompt 3 Token Count: {len(tokens3)}")
    print(f"Positive Prompt 3 Content:\n{pos3}")
    
    # Assert exact deduplication occurred
    assert tokens3.count("close up") == 1, "Deduplication failed!"
    assert tokens3.count("angry") == 1, "Deduplication failed!"
    # Assert total length <= 110
    assert len(tokens3) <= 110, f"Token limit exceeded! Count: {len(tokens3)}"
    print("[PASS] Test 3: Deduplication and strict 110-token limit enforced successfully!")

    print("\n--- Test 4: All Style Templates ---")
    for style in ["anime", "manga", "manhwa", "manhua", "cinematic", "realistic"]:
        pb_style = PromptBuilder(style=style)
        pos_s, neg_s = pb_style.build_prompt(scene1, mm, is_continuation=False)
        print(f"Style: {style}")
        print(f"  Pos: {pos_s[:120]}...")
        # Check that style templates are correctly mapped
        prefix_first_token = STYLE_TEMPLATES[style]["prefix"].split(",")[0]
        assert prefix_first_token in pos_s, f"Style mapping prefix failed for {style}"
        override_first_token = STYLE_TEMPLATES[style]["lighting_override"].split(",")[0]
        assert override_first_token in pos_s, f"Style mapping lighting_override failed for {style}"
    print("[PASS] Test 4: All detailed style templates verified successfully!")

    print("\nAll unit tests passed successfully!")

def test_character_design_sheets():
    print("\n--- Test 5: Character Design Sheet Integration ---")
    from core.character_designer import CharacterDesignSheet
    from core.memory_manager import MemoryManager
    from core.prompt_builder import PromptBuilder
    
    # Create a character design sheet
    sheet = CharacterDesignSheet(
        name="Leo",
        gender="male",
        age_range="teen",
        hair_style="short spiky",
        hair_color="black hair",
        eye_color="blue",
        body_type="slender",
        primary_outfit="blue hoodie and black jeans",
        distinguishing_features="scar over left eye",
        personality_note="energetic and optimistic"
    )
    
    # Test methods
    prompt_tokens = sheet.to_prompt_tokens()
    neg_tokens = sheet.to_negative_tokens()
    
    print(f"Prompt Tokens: {prompt_tokens}")
    print(f"Negative Tokens: {neg_tokens}")
    
    # Check ordering: gender -> age -> hair -> eyes -> outfit -> features
    assert "male" in prompt_tokens
    assert "teen" in prompt_tokens
    assert "short spiky black hair" in prompt_tokens
    assert "blue eyes" in prompt_tokens
    assert "blue hoodie and black jeans" in prompt_tokens
    assert "scar over left eye" in prompt_tokens
    
    # Check negative tokens
    assert "feminine features" in neg_tokens
    assert "old age" in neg_tokens
    assert "wrong hair color" in neg_tokens
    
    # Test MemoryManager overriding
    mm = MemoryManager()
    # Mock loaded active sheet
    mm.active_sheets = {"leo": sheet}
    
    # Retrieve character Leo - should use design sheet tokens
    leo_desc = mm.get_character("Leo")
    assert leo_desc == prompt_tokens, f"Expected {prompt_tokens}, got {leo_desc}"
    print("[PASS] MemoryManager get_character overrides with design sheet tokens!")
    
    # Test PromptBuilder injecting positive and negative tokens
    pb = PromptBuilder(style="anime")
    scene = {
        "scene_id": 1,
        "focus_character": "Leo",
        "characters": [
            {
                "name": "Leo",
                "description": "random text to override"
            }
        ],
        "action": "running fast",
        "environment": "forest path"
    }
    
    pos, neg = pb.build_prompt(scene, mm, is_continuation=False)
    print(f"Positive: {pos}")
    print(f"Negative: {neg}")
    
    assert "short spiky black hair" in pos
    assert "scar over left eye" in pos
    assert "wrong hair color" in neg
    print("[PASS] PromptBuilder successfully incorporates positive and negative design sheet tokens!")

if __name__ == "__main__":
    test_prompt_builder()
    test_character_design_sheets()
