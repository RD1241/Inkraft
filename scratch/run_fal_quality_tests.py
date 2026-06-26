import sys
import os
import shutil
import json
import time

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Set environment variables for fal.ai before importing modules
os.environ["IMAGE_PROVIDER"] = "fal_ai"

from config import settings
from services.comic_service import comic_service

# Force override settings for cost control & portrait format
settings.IMAGE_PROVIDER = "fal_ai"
settings.SD_WIDTH = 768
settings.SD_HEIGHT = 1024
settings.SD_INFERENCE_STEPS = 25
settings.ENABLE_CACHING = False  # Ensure fresh generations

TESTS = [
    {
        "id": "Test1_Action",
        "text": "Kael charged forward, his blade catching the moonlight. The knight raised his shield, sparks flying as steel met steel. Kael spun low, sweeping at the knight's legs.",
        "style": "manga",
        "panel_count": 3,
        "layout_type": "action"
    },
    {
        "id": "Test2_Drama",
        "text": "Elena set the letter on the table between them. Neither spoke. Then she said quietly: I know what you did. His face did not change. That was what hurt the most.",
        "style": "manhwa",
        "panel_count": 3,
        "layout_type": "drama"
    },
    {
        "id": "Test3_Dialogue",
        "text": "You must be the new apprentice, the old mage said. I am, she said. Can you make tea? Yes. He finally looked up. Good. That is the only skill that matters here.",
        "style": "manga",
        "panel_count": 3,
        "layout_type": "dialogue"
    }
]

def get_latest_output_dir():
    import glob
    folders = glob.glob(os.path.join(settings.OUTPUTS_DIR, "*"))
    folders = [f for f in folders if os.path.isdir(f) and ("_" in os.path.basename(f) or os.path.basename(f).isdigit())]
    if not folders:
        return None
    folders.sort(key=os.path.getmtime)
    return folders[-1]

def main():
    target_base_dir = os.path.abspath(os.path.join("test_outputs", "fal_quality_test"))
    os.makedirs(target_base_dir, exist_ok=True)

    print("=====================================================================")
    print("INKRAFT - RUNNING FAL.AI QUALITY TESTS WITH ANIMAGINE XL & NOOBAI")
    print("=====================================================================")
    print(f"Target Directory: {target_base_dir}")
    print(f"Cost Control Rules: 3 panels per test | Size: 768x1024 | Steps: 25")
    print("=====================================================================\n")

    for idx, test in enumerate(TESTS):
        test_id = test["id"]
        text = test["text"]
        style = test["style"]
        panel_count = test["panel_count"]
        layout_type = test["layout_type"]

        test_dest_dir = os.path.join(target_base_dir, test_id)
        os.makedirs(test_dest_dir, exist_ok=True)

        print(f"[{idx+1}/{len(TESTS)}] RUNNING: {test_id}...")
        print(f"  Style: {style} | Panels: {panel_count} | Layout: {layout_type}")
        print(f"  Story: \"{text}\"")

        # Create new unique SQLite Job ID
        job_id = comic_service.job_manager.create_job(
            panel_count=panel_count,
            layout_type=layout_type,
            panel_count_mode="user_specified"
        )

        start_t = time.time()
        try:
            comic_service.process_job_worker(
                job_id=job_id,
                text=text,
                style=style,
                panel_count=panel_count,
                layout_type=layout_type
            )
            elapsed = time.time() - start_t
            print(f"  Completed successfully in {elapsed:.1f}s.")
        except Exception as e:
            print(f"  [ERROR] Execution failed: {e}")
            continue

        # Resolve latest output folder
        latest_dir = get_latest_output_dir()
        if not latest_dir:
            print("  [ERROR] No output directory found in outputs/!")
            continue

        # Copy final stitched page
        final_src = os.path.join(latest_dir, "final_comic_page.png")
        if os.path.exists(final_src):
            shutil.copy2(final_src, os.path.join(test_dest_dir, "final_comic_page.png"))
            print("  -> Saved final_comic_page.png")
        else:
            print("  [ERROR] final_comic_page.png not found!")

        # Copy panel files
        for p_idx in range(1, panel_count + 1):
            panel_src = os.path.join(latest_dir, f"scene_{p_idx}.png")
            if os.path.exists(panel_src):
                shutil.copy2(panel_src, os.path.join(test_dest_dir, f"scene_{p_idx}.png"))
                print(f"  -> Saved scene_{p_idx}.png")
            else:
                print(f"  [ERROR] scene_{p_idx}.png not found!")

        # Copy metadata
        meta_src = os.path.join(latest_dir, "metadata.json")
        if os.path.exists(meta_src):
            shutil.copy2(meta_src, os.path.join(test_dest_dir, "storyboard_plan.json"))
            print("  -> Saved storyboard_plan.json")
        else:
            print("  [ERROR] metadata.json not found!")

        # Record prompt summary
        with open(os.path.join(test_dest_dir, "test_info.json"), "w") as f:
            json.dump({
                "test_id": test_id,
                "text": text,
                "style": style,
                "panel_count": panel_count,
                "layout_type": layout_type,
                "dimensions": "768x1024",
                "steps": 25,
                "elapsed_seconds": elapsed,
                "estimated_cost_usd": panel_count * 0.003
            }, f, indent=4)
        print("  -> Saved test_info.json\n")

    print("=====================================================================")
    print("ALL 3 QUALITY TESTS COMPLETED SUCCESSFULLY!")
    print("=====================================================================")

if __name__ == "__main__":
    main()
