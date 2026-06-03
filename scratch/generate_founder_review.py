import os
import sys
import glob
import shutil
import time

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from services.comic_service import comic_service

TESTS = [
    {
        "name": "test1_action",
        "text": "Kael charged forward, his blade catching the moonlight as he closed the distance. The knight raised his shield just in time, sparks flying as steel met steel. Kael spun low, sweeping at the knight's legs.",
        "style": "manga",
        "panel_count": 4,
        "layout_type": "action"
    },
    {
        "name": "test2_drama",
        "text": "Elena set the letter on the table between them. For a long moment neither spoke. Then she said quietly: I know what you did. His face did not change. That was what hurt the most.",
        "style": "manhwa",
        "panel_count": 3,
        "layout_type": "drama"
    },
    {
        "name": "test3_dialogue",
        "text": "You must be the new apprentice, the old mage said without looking up. I am, she said. He turned a page. Can you make tea? Yes. He finally looked up. Good. That is the only skill that matters here.",
        "style": "manga",
        "panel_count": None,
        "layout_type": "dialogue"
    }
]

def get_latest_output_dir():
    folders = glob.glob(os.path.join(settings.OUTPUTS_DIR, "*"))
    folders = [f for f in folders if os.path.isdir(f) and ("_" in os.path.basename(f) or os.path.basename(f).isdigit())]
    if not folders:
        return None
    folders.sort(key=os.path.getmtime)
    return folders[-1]

def run():
    dest_dir = os.path.abspath(os.path.join("test_outputs", "founder_review"))
    os.makedirs(dest_dir, exist_ok=True)

    print("=========================================================")
    print("GENERATING COMICS FOR FOUNDER REVIEW")
    print("=========================================================")

    for idx, test in enumerate(TESTS):
        print(f"\n[{idx+1}/3] Generating {test['name']}...")
        
        job_id = comic_service.job_manager.create_job(
            panel_count=test["panel_count"],
            layout_type=test["layout_type"],
            panel_count_mode="user_specified" if test["panel_count"] else "ai_decided"
        )
        
        start_t = time.time()
        try:
            comic_service.process_job_worker(
                job_id=job_id,
                text=test["text"],
                style=test["style"],
                panel_count=test["panel_count"],
                layout_type=test["layout_type"]
            )
            print(f"  Finished in {time.time() - start_t:.1f}s.")
            
            latest_dir = get_latest_output_dir()
            if latest_dir:
                final_src = os.path.join(latest_dir, "final_comic_page.png")
                if os.path.exists(final_src):
                    dest_path = os.path.join(dest_dir, f"{test['name']}.png")
                    shutil.copy2(final_src, dest_path)
                    print(f"  -> Successfully saved: {dest_path}")
                else:
                    print("  [ERROR] final_comic_page.png not found in output directory!")
            else:
                print("  [ERROR] No output directory detected!")
        except Exception as e:
            print(f"  [FATAL ERROR]: {e}")

    print("\n=========================================================")
    print("ALL 3 FOUNDER REVIEW COMICS GENERATED!")
    print("=========================================================")

if __name__ == "__main__":
    run()
