import sys
import os
import shutil
import json
import time

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

os.environ["IMAGE_PROVIDER"] = "fal_ai"

from config import settings
from services.comic_service import comic_service

settings.IMAGE_PROVIDER = "fal_ai"
settings.SD_WIDTH = 768
settings.SD_HEIGHT = 1024
settings.SD_INFERENCE_STEPS = 25
settings.ENABLE_CACHING = False

test = {
    "id": "Test2_Drama",
    "text": "Elena set the letter on the table between them. Neither spoke. Then she said quietly: I know what you did. His face did not change. That was what hurt the most.",
    "style": "manhwa",
    "panel_count": 3,
    "layout_type": "drama"
}

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
    test_id = test["id"]
    test_dest_dir = os.path.join(target_base_dir, test_id)
    os.makedirs(test_dest_dir, exist_ok=True)

    print(f"Re-running Test 2 to resolve black panel...")
    job_id = comic_service.job_manager.create_job(
        panel_count=test["panel_count"],
        layout_type=test["layout_type"],
        panel_count_mode="user_specified"
    )

    start_t = time.time()
    try:
        # We can change the seed slightly to avoid safety blocks if there was one
        settings.SD_DEFAULT_SEED = 100
        comic_service.process_job_worker(
            job_id=job_id,
            text=test["text"],
            style=test["style"],
            panel_count=test["panel_count"],
            layout_type=test["layout_type"]
        )
        elapsed = time.time() - start_t
        print(f"Completed in {elapsed:.1f}s.")
    except Exception as e:
        print(f"Failed: {e}")
        return

    latest_dir = get_latest_output_dir()
    if not latest_dir:
        print("No output dir found.")
        return

    final_src = os.path.join(latest_dir, "final_comic_page.png")
    if os.path.exists(final_src):
        shutil.copy2(final_src, os.path.join(test_dest_dir, "final_comic_page.png"))
        print("Saved final_comic_page.png")

    for p_idx in range(1, test["panel_count"] + 1):
        panel_src = os.path.join(latest_dir, f"scene_{p_idx}.png")
        if os.path.exists(panel_src):
            shutil.copy2(panel_src, os.path.join(test_dest_dir, f"scene_{p_idx}.png"))
            print(f"Saved scene_{p_idx}.png")

    meta_src = os.path.join(latest_dir, "metadata.json")
    if os.path.exists(meta_src):
        shutil.copy2(meta_src, os.path.join(test_dest_dir, "storyboard_plan.json"))
        print("Saved storyboard_plan.json")

    with open(os.path.join(test_dest_dir, "test_info.json"), "w") as f:
        json.dump({
            "test_id": test_id,
            "text": test["text"],
            "style": test["style"],
            "panel_count": test["panel_count"],
            "layout_type": test["layout_type"],
            "dimensions": "768x1024",
            "steps": 25,
            "elapsed_seconds": elapsed,
            "estimated_cost_usd": test["panel_count"] * 0.003
        }, f, indent=4)
    print("Saved test_info.json\n")

if __name__ == "__main__":
    main()
