import os
import sys
import time
import json
import glob

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.comic_service import comic_service
from config import settings

def get_latest_output_dir():
    folders = glob.glob(os.path.join(settings.OUTPUTS_DIR, "*"))
    folders = [f for f in folders if os.path.isdir(f)]
    if not folders:
        return None
    folders.sort(key=os.path.getmtime)
    return folders[-1]

def main():
    print("==================================================")
    print("INKRAFT - RUNNING QUALITY VERIFICATION TESTS")
    print("==================================================")
    
    # Ensure FAL_KEY is set
    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        print("[Error] FAL_KEY environment variable is not set!")
        return

    # TEST A: Action Manga (3 Panels)
    text_a = "Kael charged forward, his blade catching the moonlight. The knight raised his shield, sparks flying as steel met steel. Kael spun low, sweeping at the knight's legs."
    print("\n--- RUNNING TEST A (Action Manga, 3 Panels) ---")
    job_id_a = comic_service.job_manager.create_job(
        panel_count=3,
        layout_type="action",
        panel_count_mode="user_specified"
    )
    
    start_time_a = time.time()
    try:
        comic_service.process_job_worker(
            job_id=job_id_a,
            text=text_a,
            style="manga",
            panel_count=3,
            layout_type="action"
        )
    except Exception as e:
        print(f"[Test A Failed]: {e}")
    end_time_a = time.time()
    duration_a = end_time_a - start_time_a
    print(f"Test A completed in: {duration_a:.2f} seconds")
    
    dir_a = get_latest_output_dir()
    if dir_a:
        print(f"Test A output directory: {dir_a}")
        meta_path = os.path.join(dir_a, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
                print(f"Stitched page layout: {meta.get('layout_type')}")
                for p in meta.get("panels", []):
                    print(f"  Panel {p.get('panel_id')}: size {p.get('width')}x{p.get('height')}, dialogues: {len(p.get('dialogue', []))}")

    # TEST B: Drama Manhwa (3 Panels)
    text_b = "Elena set the letter on the table between them. Neither spoke. Then she said quietly: I know what you did. His face did not change. That was what hurt the most."
    print("\n--- RUNNING TEST B (Drama Manhwa, 3 Panels) ---")
    job_id_b = comic_service.job_manager.create_job(
        panel_count=3,
        layout_type="drama",
        panel_count_mode="user_specified"
    )
    
    start_time_b = time.time()
    try:
        comic_service.process_job_worker(
            job_id=job_id_b,
            text=text_b,
            style="manhwa",
            panel_count=3,
            layout_type="drama"
        )
    except Exception as e:
        print(f"[Test B Failed]: {e}")
    end_time_b = time.time()
    duration_b = end_time_b - start_time_b
    print(f"Test B completed in: {duration_b:.2f} seconds")
    
    dir_b = get_latest_output_dir()
    if dir_b:
        print(f"Test B output directory: {dir_b}")
        meta_path = os.path.join(dir_b, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
                print(f"Stitched page layout: {meta.get('layout_type')}")
                for p in meta.get("panels", []):
                    print(f"  Panel {p.get('panel_id')}: size {p.get('width')}x{p.get('height')}, dialogues: {len(p.get('dialogue', []))}")

    print("\n==================================================")
    print("VERIFICATION RUN COMPLETED")
    print("==================================================")

if __name__ == "__main__":
    main()
