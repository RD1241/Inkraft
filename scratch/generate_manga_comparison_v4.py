import sys
import os
import httpx

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(r"d:\Project_I\NovelToComic")

from config import settings
from scratch.original_prompt_builder import PromptBuilder as OriginalPromptBuilder
from core.prompt_builder import PromptBuilder as ModifiedPromptBuilder
from core.memory_manager import MemoryManager

def log(msg):
    print(msg, flush=True)

def main():
    log("[Manga Monochrome Test V4] Starting generation script...")
    
    fal_key = os.environ.get("FAL_KEY")
    if not fal_key and settings:
        fal_key = getattr(settings, "FAL_KEY", None)
    if not fal_key:
        log("FAL_KEY not found in environment or settings. Exiting.")
        sys.exit(1)
        
    os.environ["FAL_KEY"] = fal_key
    import fal_client
    
    # Setup dummy database for MemoryManager so it initializes without error
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
    
    mm = MemoryManager()
    
    scenes = [
        {
            "camera": "wide angle, cinematic shot",
            "emotion": "determined, serious",
            "lighting": "sunset light, heavy shadows",
            "focus_character": "Samurai",
            "characters": [{"name": "Samurai", "description": "male samurai with a long katana, traditional armor"}],
            "action": "standing on a cliff side looking down at the valley",
            "environment": "mountainous cliff side",
            "global_environment": "mountainous cliff side"
        },
        {
            "camera": "low angle, dramatic perspective",
            "emotion": "intense, aggressive",
            "lighting": "neon rim lighting",
            "focus_character": "Mecha",
            "characters": [{"name": "Mecha", "description": "giant robotic mech suit, metallic armor, glowing eyes"}],
            "action": "marching through a dark futuristic city block",
            "environment": "cyberpunk city, tall skyscrapers",
            "global_environment": "cyberpunk city"
        },
        {
            "camera": "extreme close up",
            "emotion": "shocked, crying, tears streaming down",
            "lighting": "dim light, stark shadow",
            "focus_character": "Girl",
            "characters": [{"name": "Girl", "description": "young teenage girl with big expressive eyes, school uniform"}],
            "action": "gasping in pure disbelief and grief",
            "environment": "dark empty room",
            "global_environment": "dark empty room"
        }
    ]
    
    brain_dir = r"C:\Users\dell\.gemini\antigravity\brain\9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6"
    
    # ── GENERATE BEFORE (UNMODIFIED) ──
    log("\n=== Generating 'Before' Panels (Original Prompt) ===")
    pb_before = OriginalPromptBuilder(style="manga")
    
    before_prompts = []
    before_negs = []
    
    for idx, scene in enumerate(scenes, 1):
        pos, neg = pb_before.build_prompt(scene, mm)
        before_prompts.append(pos)
        before_negs.append(neg)
        log(f"\nBefore Panel {idx}:")
        log(f"  Positive: {pos}")
        log(f"  Negative: {neg}")
        
        # Call fal_client
        result = fal_client.subscribe(
            "fal-ai/fast-sdxl",
            arguments={
                "prompt": pos,
                "negative_prompt": neg,
                "model_name": "cagliostrolab/animagine-xl-3.1",
                "image_size": {"width": 1024, "height": 1024},
                "seed": 2000 + idx
            }
        )
        url = result["images"][0]["url"]
        log(f"  Generated! URL: {url}")
        
        # Download
        resp = httpx.get(url)
        resp.raise_for_status()
        out_path = os.path.join(brain_dir, f"manga_before_panel_{idx}.png")
        with open(out_path, "wb") as f:
            f.write(resp.content)
        log(f"  Saved to: {out_path}")

    # ── GENERATE AFTER (MODIFIED) ──
    log("\n=== Generating 'After' Panels (Modified Prompt with color block) ===")
    pb_after = ModifiedPromptBuilder(style="manga")
    
    after_prompts = []
    after_negs = []
    
    for idx, scene in enumerate(scenes, 1):
        pos, neg = pb_after.build_prompt(scene, mm)
        after_prompts.append(pos)
        after_negs.append(neg)
        log(f"\nAfter Panel {idx}:")
        log(f"  Positive: {pos}")
        log(f"  Negative: {neg}")
        
        # Call fal_client
        result = fal_client.subscribe(
            "fal-ai/fast-sdxl",
            arguments={
                "prompt": pos,
                "negative_prompt": neg,
                "model_name": "cagliostrolab/animagine-xl-3.1",
                "image_size": {"width": 1024, "height": 1024},
                "seed": 2000 + idx
            }
        )
        url = result["images"][0]["url"]
        log(f"  Generated! URL: {url}")
        
        # Download
        resp = httpx.get(url)
        resp.raise_for_status()
        out_path = os.path.join(brain_dir, f"manga_after_panel_{idx}.png")
        with open(out_path, "wb") as f:
            f.write(resp.content)
        log(f"  Saved to: {out_path}")
        
    log("\nGeneration complete. All panels successfully generated and saved.")

if __name__ == "__main__":
    main()
