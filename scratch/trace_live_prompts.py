"""
Reconstruct the actual prompts that would have been transmitted for the
Kaito/Mei library generation (outputs/20260624_034751).

Reads the saved metadata.json and runs the actual current prompt_builder
code against those exact scenes/characters to show what was sent.
"""
import json
import sys
import os

sys.path.insert(0, '.')

# Load the saved storyboard output
metadata_path = 'outputs/20260624_034751/metadata.json'
if not os.path.exists(metadata_path):
    print(f"Error: {metadata_path} not found.")
    sys.exit(1)

with open(metadata_path) as f:
    meta = json.load(f)

print("=" * 70)
print("RAW CHARACTER EXTRACTION OUTPUT")
print("=" * 70)

print("\n[Characters per scene as stored in metadata.json]")
for scene in meta.get('scenes', []):
    sid = scene.get('scene_id')
    focus = scene.get('focus_character')
    chars = scene.get('characters', [])
    print(f"\nScene {sid}: focus_character={repr(focus)}")
    for c in chars:
        print(f"  name={repr(c['name'])}, role={repr(c.get('character_role',''))}, desc={repr(c.get('description',''))}")

print("\n[Panels as stored in metadata.json]")
for p in meta.get('panels', []):
    pid = p.get('panel_id')
    focus = p.get('focus_character')
    action = p.get('action', '')
    camera = p.get('camera_shot')
    lighting = p.get('lighting')
    emotion = p.get('emotion')
    print(f"\nPanel {pid}: focus={repr(focus)}, camera={camera}, lighting={repr(lighting)}, emotion={emotion}")
    print(f"  action: {repr(action[:150])}")

print("\n" + "=" * 70)
print("RECONSTRUCTED PROMPTS (using current prompt_builder.py)")
print("=" * 70)

from core.prompt_builder import PromptBuilder, STYLE_TEMPLATES, SDXL_STYLE_TEMPLATES
from core.camera_director import CameraDirector
from core.expression_engine import ExpressionEngine
from config import settings

print(f"\nIMAGE_PROVIDER from settings: {getattr(settings, 'IMAGE_PROVIDER', 'NOT SET')}")
print(f"is_sdxl = (IMAGE_PROVIDER == 'fal_ai'): {getattr(settings, 'IMAGE_PROVIDER', '') == 'fal_ai'}")

class MockConsistency:
    def __init__(self):
        self.profiles = {
            "kaito": {
                "name": "kaito",
                "base_description": "kaito character",
                "hairstyle_tokens": "short black hair",
                "outfit_tokens": "school uniform",
                "gender_tokens": "1boy, male",
                "role": "main_character",
                "reference_image_path": "dummy_ref.png",
                "reference_image_locked": True,
                "gender": "male",
                "gender_locked": True,
                "hair_color_token": "black hair",
                "hair_style_token": "short"
            },
            "mei": {
                "name": "mei",
                "base_description": "mei character",
                "hairstyle_tokens": "long brown hair, ponytail",
                "outfit_tokens": "casual outfit",
                "gender_tokens": "1girl, female",
                "role": "secondary_character",
                "reference_image_path": "dummy_ref.png",
                "reference_image_locked": True,
                "gender": "female",
                "gender_locked": True,
                "hair_color_token": "brown hair",
                "hair_style_token": "long, ponytail"
            }
        }

    def get_profile(self, name):
        if not name:
            return None
        return self.profiles.get(name.lower().strip())

    def get_dominant_character(self, scene):
        focus = scene.get("focus_character")
        if focus:
            return focus
        chars = scene.get("characters", [])
        if chars:
            return chars[0].get("name")
        return None

class MockMemory:
    def __init__(self):
        self.consistency = MockConsistency()
    def get_character(self, name):
        return None
    def get_environment(self):
        return None
    def get_design_sheet(self, name):
        return None

mock_memory = MockMemory()
camera_director = CameraDirector()
expression_engine = ExpressionEngine()

reconstructed_panel_2_pos_unfiltered = ""
reconstructed_panel_2_pos_filtered = ""
first_panel_pos_prompt = ""

print("\n[Reconstructing each panel's prompt as the live app would build it]")
for panel_idx, scene in enumerate(meta.get('scenes', [])[:3]):  # first 3 scenes = 3 panels
    panel_id = panel_idx + 1
    
    # Find panel in metadata
    panel = None
    for p in meta.get('panels', []):
        if p.get('panel_id') == panel_id:
            panel = p
            break
    if not panel:
        continue

    # Prepare characters_list matching filtered live app behavior
    characters_list = scene.get("characters", [])
    if panel.get("camera_shot") in ("CLOSE_UP", "EXTREME_CLOSE_UP") and panel.get("focus_character"):
        focus_name_lower = str(panel.get("focus_character")).strip().lower()
        filtered_chars = [c for c in characters_list if c.get("name", "").strip().lower() == focus_name_lower]
        if filtered_chars:
            characters_list = filtered_chars

    panel_scene = {
        "scene_id": panel.get("scene_id"),
        "panel_id": panel.get("panel_id"),
        "focus_character": panel.get("focus_character"),
        "action": panel.get("action"),
        "dialogue": panel.get("dialogue"),
        "camera": camera_director.get_shot_tokens(panel.get("camera_shot")),
        "emotion": expression_engine.build_emotion_prompt_segment(panel.get("emotion")),
        "lighting": panel.get("lighting"),
        "environment": meta.get("global_environment", "library"),
        "global_environment": meta.get("global_environment", "library"),
        "characters": characters_list
    }

    builder = PromptBuilder(style='manga')
    if panel_idx > 0 and first_panel_pos_prompt:
        builder.last_positive_prompt = first_panel_pos_prompt

    pos, neg = builder.build_prompt(
        scene=panel_scene,
        memory_manager=mock_memory,
        is_continuation=(panel_idx > 0),
        style='manga'
    )
    
    dominant_char = mock_memory.consistency.get_dominant_character(panel_scene)
    use_reference = (panel_idx > 0) and bool(dominant_char)
    if use_reference:
        pos, neg = builder.apply_reference_conditioning_prompt(pos, neg)

    if panel_idx == 0:
        first_panel_pos_prompt = pos

    if panel_id == 2:
        reconstructed_panel_2_pos_filtered = pos

    print(f"\n--- Panel {panel_id} ---")
    print(f"POSITIVE PROMPT:\n  {pos}")
    print(f"NEGATIVE PROMPT:\n  {neg}")
    
    mono_tokens = ['monochrome', 'greyscale', 'black and white', 'manga style']
    neg_color_tokens = ['colorful', 'cel shading', 'multicolored', 'chromatic']
    print(f"\n  Monochrome tokens in positive: {[t for t in mono_tokens if t in pos.lower()]}")
    print(f"  Color-suppression in negative: {[t for t in neg_color_tokens if t in neg.lower()]}")

# Separate run specifically for reconstruction validation (no character filtering on panel 2 close-up)
# This simulates the exact conditions under which historical Test A was generated.
scene_2 = meta.get('scenes', [])[1]
panel_2 = [p for p in meta.get('panels', []) if p.get('panel_id') == 2][0]
panel_scene_unfiltered = {
    "scene_id": panel_2.get("scene_id"),
    "panel_id": 2,
    "focus_character": panel_2.get("focus_character"),
    "action": panel_2.get("action"),
    "dialogue": panel_2.get("dialogue"),
    "camera": camera_director.get_shot_tokens(panel_2.get("camera_shot")),
    "emotion": expression_engine.build_emotion_prompt_segment(panel_2.get("emotion")),
    "lighting": panel_2.get("lighting"),
    "environment": meta.get("global_environment", "library"),
    "global_environment": meta.get("global_environment", "library"),
    "characters": scene_2.get("characters", []) # No filter
}
builder_unfiltered = PromptBuilder(style='manga')
builder_unfiltered.last_positive_prompt = first_panel_pos_prompt
pos_unfiltered, neg_unfiltered = builder_unfiltered.build_prompt(
    scene=panel_scene_unfiltered,
    memory_manager=mock_memory,
    is_continuation=True,
    style='manga'
)
pos_unfiltered, _ = builder_unfiltered.apply_reference_conditioning_prompt(pos_unfiltered, neg_unfiltered)
reconstructed_panel_2_pos_unfiltered = pos_unfiltered

print("\n" + "=" * 70)
print("SELF-CHECK VERIFICATION")
print("=" * 70)

# Check against ablation_results.json Test A
ablation_paths = [
    'C:/Users/dell/.gemini/antigravity/brain/9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6/ablation_results.json',
    'ablation_results.json'
]
ablation_data = None
for path in ablation_paths:
    if os.path.exists(path):
        with open(path) as f:
            ablation_data = json.load(f)
        print(f"Loaded ablation results from: {path}")
        break

if ablation_data:
    known_prompt = ablation_data.get("Test_A", {}).get("prompt", "")
    if not known_prompt:
        print("Self-check failed: 'Test_A' or 'prompt' not found in ablation results.")
        sys.exit(1)
    
    print("\nComparing reconstructed Panel 2 positive prompt (unfiltered) against known real payload...")
    print(f"Expected: {known_prompt[:120]}... [len={len(known_prompt)}]")
    print(f"Actual:   {reconstructed_panel_2_pos_unfiltered[:120]}... [len={len(reconstructed_panel_2_pos_unfiltered)}]")
    
    if reconstructed_panel_2_pos_unfiltered == known_prompt:
        print("\n>>> SELF-CHECK SUCCESS: Reconstructed prompt matches known real fal.ai payload exactly! <<<")
    else:
        print("\n>>> SELF-CHECK WARNING: Reconstruction does not match known payload exactly. <<<")
        # Print differences
        import difflib
        diff = list(difflib.ndiff([known_prompt], [reconstructed_panel_2_pos_unfiltered]))
        print("Diff analysis:")
        for line in diff:
            print(line)
        sys.exit(1)
else:
    print("Self-check skipped: ablation_results.json not found.")
