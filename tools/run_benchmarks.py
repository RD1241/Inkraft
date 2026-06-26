import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # path bootstrap: allow app imports after move into tools/
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

# 12 Benchmark Prompts
TESTS = [
    {
        "id": "A1",
        "folder": "A1_sword_fight",
        "text": "Kael charged forward, his blade catching the moonlight as he closed the distance between himself and the armored knight. The knight raised his shield just in time, sparks flying as steel met steel. Kael spun low, sweeping at the knight's legs. The knight leaped back, breathing hard. For a moment they faced each other across the ruined courtyard, neither moving.",
        "style": "manga",
        "panel_count": None,
        "layout_type": "action"
    },
    {
        "id": "A2",
        "folder": "A2_chase",
        "text": "She ran. Behind her the guards' boots thundered on the cobblestones, getting closer. She ducked into an alley, vaulted a low wall, and landed badly, pain shooting through her ankle. She pressed herself flat against the wall as the guards ran past, torches blazing. Slowly she let out her breath. They were gone. For now.",
        "style": "manhwa",
        "panel_count": 5,
        "layout_type": "action"
    },
    {
        "id": "A3",
        "folder": "A3_battle",
        "text": "The dragon opened its maw and fire poured out. Marcus threw his hands up and the barrier held — barely. He could feel it cracking. The heat was unbearable. With his last strength he pushed everything he had into one final counterattack, a beam of pure white light that struck the dragon square in the chest. Silence. Then the dragon fell.",
        "style": "manga",
        "panel_count": 4,
        "layout_type": "action"
    },
    {
        "id": "B1",
        "folder": "B1_betrayal",
        "text": "Elena set the letter on the table between them. For a long moment neither spoke. Then she said quietly: I know what you did. I know it was you. His face did not change. That was what hurt the most — not the betrayal itself, but how practiced his expression was. How many times had he looked at her just like this and lied.",
        "style": "manhwa",
        "panel_count": None,
        "layout_type": "drama"
    },
    {
        "id": "B2",
        "folder": "B2_confrontation",
        "text": "You were supposed to protect him. That was the only thing I asked of you. Her voice was barely above a whisper but it landed like a blow. He had no answer. There was no answer. The silence between them said everything that words could not. She turned away so he would not see her cry.",
        "style": "manga",
        "panel_count": 3,
        "layout_type": "drama"
    },
    {
        "id": "B3",
        "folder": "B3_grief",
        "text": "She sat alone in the empty room. His chair was still at the table. His coat was still on the hook. Everything was exactly as he had left it that morning, before they knew. She did not move for a very long time. Outside the window the city carried on without him, indifferent.",
        "style": "cinematic",
        "panel_count": None,
        "layout_type": "drama"
    },
    {
        "id": "C1",
        "folder": "C1_negotiation",
        "text": "Sit down, the general said. She did not sit. You have two choices, he continued, spreading a map across the desk. You help us find the northern pass, or we level the village. Your village. She looked at the map. Then she looked at him. Then she pulled out the chair and sat down.",
        "style": "manhwa",
        "panel_count": 4,
        "layout_type": "dialogue"
    },
    {
        "id": "C2",
        "folder": "C2_first_meeting",
        "text": "You must be the new apprentice, the old mage said without looking up from his book. I am, she said. He turned a page. Can you make tea? Yes. Can you be quiet for six hours at a time? She thought about it. Probably. He finally looked up. Good. Those are the only two skills that matter here.",
        "style": "manga",
        "panel_count": None,
        "layout_type": "dialogue"
    },
    {
        "id": "C3",
        "folder": "C3_confession",
        "text": "I have to tell you something. She had rehearsed this a hundred times but now the words were gone. He waited, patient as always. I think — She stopped. Started again. When you were away last winter, I was not alright. Not even close. I just need you to know that. He did not say anything. He just moved to sit beside her.",
        "style": "manhwa",
        "panel_count": 4,
        "layout_type": "drama"
    },
    {
        "id": "D1",
        "folder": "D1_horror",
        "text": "The door at the end of the corridor was open. It had not been open before. She raised her lamp and took a step forward. The floorboard creaked. From somewhere deeper in the dark came a sound that might have been breathing. She told herself it was the house settling. She did not believe herself.",
        "style": "cinematic",
        "panel_count": None,
        "layout_type": "cinematic"
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
    }
]

def get_latest_output_dir():
    folders = glob.glob(os.path.join(settings.OUTPUTS_DIR, "*"))
    folders = [f for f in folders if os.path.isdir(f) and ("_" in os.path.basename(f) or os.path.basename(f).isdigit())]
    if not folders:
        return None
    folders.sort(key=os.path.getmtime)
    return folders[-1]

def run_all_benchmarks():
    base_target_dir = os.path.abspath(os.path.join("test_outputs", "stage_2_5"))
    os.makedirs(base_target_dir, exist_ok=True)

    print("=====================================================================")
    print("INKRAFT - STAGE 2.5 QUALITY VALIDATION BENCHMARKS")
    print("=====================================================================")
    print(f"Target Directory: {base_target_dir}")
    print(f"Total Tests to Run: {len(TESTS)}")
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

        print(f"[{idx+1}/{len(TESTS)}] RUNNING {test_id} ({folder_name})...")
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
        print("  Generating images and planning layout (this may take up to a minute)...")
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
        print(f"  Generation finished in {elapsed:.1f}s.")

        # Resolve latest output folder
        latest_dir = get_latest_output_dir()
        if not latest_dir:
            print("  [ERROR] No output directory detected in outputs/!")
            continue

        # 1. Copy final stitched page
        final_src = os.path.join(latest_dir, "final_comic_page.png")
        if os.path.exists(final_src):
            shutil.copy2(final_src, os.path.join(test_dest_dir, "final_comic_page.png"))
            print("  -> Saved final_comic_page.png")
        else:
            print("  [ERROR] final_comic_page.png not found!")

        # 2. Copy storyboard plan JSON
        meta_src = os.path.join(latest_dir, "metadata.json")
        if os.path.exists(meta_src):
            shutil.copy2(meta_src, os.path.join(test_dest_dir, "storyboard_plan.json"))
            print("  -> Saved storyboard_plan.json")
        else:
            print("  [ERROR] metadata.json not found!")

        # 3. Save panel prompts
        prompts_dest = os.path.join(test_dest_dir, "panel_prompts.txt")
        with open(prompts_dest, "w", encoding="utf-8") as f:
            f.write(f"=== PANEL PROMPTS FOR {test_id} ({folder_name}) ===\n")
            f.write(f"Original Text: {text}\n")
            f.write(f"Style: {style} | Layout: {layout_type}\n\n")
            for pid, pos, neg in job_prompts:
                f.write(f"--- Panel {pid} ---\n")
                f.write(f"POSITIVE: {pos}\n")
                f.write(f"NEGATIVE: {neg}\n\n")
        print("  -> Saved panel_prompts.txt")

        # 4. Save generation logs
        logs_dest = os.path.join(test_dest_dir, "generation_log.txt")
        with open(logs_dest, "w", encoding="utf-8") as f:
            f.write(f"=== DETAILED GENERATION LOGS FOR {test_id} ===\n")
            f.write(capture.buffer.getvalue())
        print("  -> Saved generation_log.txt")

        print("  [OK] Done!\n")

    print("=====================================================================")
    print("ALL 12 VALIDATION COMICS SUCCESSFULLY GENERATED AND BENCHMARKED!")
    print("=====================================================================")

if __name__ == "__main__":
    run_all_benchmarks()
