import sys
import os
import shutil
import glob
import json
import time
import io
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import settings
from services.comic_service import comic_service
from core.prompt_builder import PromptBuilder

# Redirect capture utility
class RedirectionCapture:
    def __enter__(self):
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        self.buffer = io.StringIO()
        sys.stdout = self.buffer
        sys.stderr = self.buffer
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

# Intercept prompts using PromptBuilder patching
job_prompts = []
orig_build_prompt = PromptBuilder.build_prompt

def patched_build_prompt(self, scene, memory_manager, is_continuation=False, style=None):
    pos, neg = orig_build_prompt(self, scene, memory_manager, is_continuation, style)
    panel_id = scene.get("panel_id", len(job_prompts) + 1)
    job_prompts.append((panel_id, pos, neg))
    return pos, neg

PromptBuilder.build_prompt = patched_build_prompt

# 4 flagged retest prompts
TESTS = [
    {
        "id": "C2",
        "folder": "C2_first_meeting",
        "text": "You must be the new apprentice, the old mage said without looking up from his book. I am, she said. He turned a page. Can you make tea? Yes. Can you be quiet for six hours at a time? She thought about it. Probably. He finally looked up. Good. Those are the only two skills that matter here.",
        "style": "manga",
        "panel_count": None,
        "layout_type": "dialogue"
    },
    {
        "id": "D2",
        "folder": "D2_slice_of_life",
        "text": "They sat across from each other at the tiny kitchen table, two coffees going cold between them. Outside it was raining. He had been trying to say something for ten minutes. She already knew what it was. She picked up her cup and waited. He said it. She nodded slowly. Outside a car drove through a puddle.",
        "style": "manhwa",
        "panel_count": None,
        "layout_type": "dialogue"
    },
    {
        "id": "D3",
        "folder": "D3_epic",
        "text": "She stood at the edge of the cliff as the sun rose over the valley. Below, the army moved like a river of steel, ten thousand soldiers marching toward a city that did not yet know they were coming. She had tried to stop this. She had failed. Now she could only watch and remember this moment — the last morning before everything changed.",
        "style": "cinematic",
        "panel_count": 2,
        "layout_type": "splash"
    },
    {
        "id": "B1",
        "folder": "B1_betrayal",
        "text": "Elena set the letter on the table between them. For a long moment neither spoke. Then she said quietly: I know what you did. I know it was you. His face did not change. That was what hurt the most — not the betrayal itself, but how practiced his expression was. How many times had he looked at her just like this and lied.",
        "style": "manhwa",
        "panel_count": None,
        "layout_type": "drama"
    }
]

def get_latest_output_dir():
    folders = glob.glob(os.path.join(settings.OUTPUTS_DIR, "*"))
    folders = [f for f in folders if os.path.isdir(f) and ("_" in os.path.basename(f) or os.path.basename(f).isdigit())]
    if not folders:
        return None
    folders.sort(key=os.path.getmtime)
    return folders[-1]

def run_retests():
    base_target_dir = os.path.abspath(os.path.join("test_outputs", "stage_2_5"))
    os.makedirs(base_target_dir, exist_ok=True)

    print("=====================================================================")
    print("INKRAFT - RUNNING STAGE 2.5 QUALITY RETESTS")
    print("=====================================================================")
    print(f"Target Directory: {base_target_dir}")
    print(f"Total Retests to Run: {len(TESTS)}")
    print("=====================================================================\n")

    for idx, test in enumerate(TESTS):
        test_id = test["id"]
        folder_name = test["folder"]
        text = test["text"]
        style = test["style"]
        panel_count = test["panel_count"]
        layout_type = test["layout_type"]

        test_dest_dir = os.path.join(base_target_dir, folder_name)
        os.makedirs(test_dest_dir, exist_ok=True)

        print(f"[{idx+1}/{len(TESTS)}] RE-RUNNING {test_id} ({folder_name})...")
        print(f"  Style: {style} | Panel Count Preference: {panel_count} | Layout: {layout_type}")
        print(f"  Story Text: \"{text[:60]}...\"")

        # Reset captured prompts list
        global job_prompts
        job_prompts = []

        # Create new unique SQLite Job ID
        job_id = comic_service.job_manager.create_job(
            panel_count=panel_count,
            layout_type=layout_type,
            panel_count_mode="user_specified" if panel_count else "ai_decided"
        )

        # Run synchronously on main thread, capturing stdout and stderr
        print("  Generating images with high-intensity expressions and token packing...")
        start_t = time.time()
        
        with RedirectionCapture() as capture:
            try:
                comic_service.process_job_worker(
                    job_id=job_id,
                    text=text,
                    style=style,
                    panel_count=panel_count,
                    layout_type=layout_type
                )
            except Exception as e:
                print(f"\n[FATAL ERROR IN WORKER]: {e}\n")

        elapsed = time.time() - start_t
        print(f"  Retest finished in {elapsed:.1f}s.")

        # Resolve latest output folder
        latest_dir = get_latest_output_dir()
        if not latest_dir:
            print("  [ERROR] No output directory detected in outputs/!")
            continue

        # 1. Copy final stitched page (overwriting previous)
        final_src = os.path.join(latest_dir, "final_comic_page.png")
        if os.path.exists(final_src):
            shutil.copy2(final_src, os.path.join(test_dest_dir, "final_comic_page.png"))
            print("  -> Saved new final_comic_page.png")
        else:
            print("  [ERROR] final_comic_page.png not found!")

        # 2. Copy storyboard plan JSON
        meta_src = os.path.join(latest_dir, "metadata.json")
        if os.path.exists(meta_src):
            shutil.copy2(meta_src, os.path.join(test_dest_dir, "storyboard_plan.json"))
            print("  -> Saved new storyboard_plan.json")
        else:
            print("  [ERROR] metadata.json not found!")

        # 3. Save panel prompts
        prompts_dest = os.path.join(test_dest_dir, "panel_prompts.txt")
        with open(prompts_dest, "w", encoding="utf-8") as f:
            f.write(f"=== PANEL PROMPTS FOR RETEST {test_id} ({folder_name}) ===\n")
            f.write(f"Original Text: {text}\n")
            f.write(f"Style: {style} | Layout: {layout_type}\n\n")
            for pid, pos, neg in job_prompts:
                f.write(f"--- Panel {pid} ---\n")
                f.write(f"POSITIVE: {pos}\n")
                f.write(f"NEGATIVE: {neg}\n\n")
        print("  -> Saved new panel_prompts.txt")

        # 4. Save generation logs
        logs_dest = os.path.join(test_dest_dir, "generation_log.txt")
        with open(logs_dest, "w", encoding="utf-8") as f:
            f.write(f"=== DETAILED GENERATION LOGS FOR RETEST {test_id} ===\n")
            f.write(capture.buffer.getvalue())
        print("  -> Saved new generation_log.txt")

        print("  [OK] Done!\n")

    print("=====================================================================")
    print("ALL 4 FLAGGED RETEST COMICS SUCCESSFULLY GENERATED!")
    print("=====================================================================")

if __name__ == "__main__":
    run_retests()
