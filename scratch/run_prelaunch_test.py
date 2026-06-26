import os
import sys
import shutil
import glob
import time

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from services.comic_service import comic_service

TESTS = [
    {
        "name": "elena_drama_manhwa",
        "text": "Elena placed the letter on the table between them. His face did not change when she said quietly: I know what you did. She turned away so he couldn't see her cry.",
        "style": "manhwa",
        "panel_count": 3,
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

def run():
    artifact_dir = "C:/Users/dell/.gemini/antigravity/brain/9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6"
    test_outputs_dir = "D:/Project_I/NovelToComic/test_outputs/final_prelaunch_test"
    
    os.makedirs(artifact_dir, exist_ok=True)
    os.makedirs(test_outputs_dir, exist_ok=True)
    
    print("Starting Pre-Launch Verification...")
    
    for idx, test in enumerate(TESTS):
        print(f"\nRunning test {idx+1}/{len(TESTS)}: {test['name']}")
        print(f"Text: {test['text']}")
        print(f"Style: {test['style']} | Panels: {test['panel_count']} | Layout: {test['layout_type']}")
        
        job_id = comic_service.job_manager.create_job(
            panel_count=test["panel_count"],
            layout_type=test["layout_type"],
            panel_count_mode="user_specified"
        )
        
        start_time = time.time()
        try:
            comic_service.process_job_worker(
                job_id=job_id,
                text=test["text"],
                style=test["style"],
                panel_count=test["panel_count"],
                layout_type=test["layout_type"]
            )
            elapsed = time.time() - start_time
            print(f"Finished in {elapsed:.1f}s")
            
            latest_dir = get_latest_output_dir()
            if latest_dir:
                # Copy all files in latest_dir to test_outputs_dir
                for file_path in glob.glob(os.path.join(latest_dir, "*")):
                    if os.path.isfile(file_path):
                        dest_file = os.path.join(test_outputs_dir, os.path.basename(file_path))
                        shutil.copy(file_path, dest_file)
                        print(f"Copied {os.path.basename(file_path)} to test_outputs: {dest_file}")
                
                final_page = os.path.join(latest_dir, "final_comic_page.png")
                if os.path.exists(final_page):
                    dest_filename = f"prelaunch_{test['name']}.png"
                    dest_path = os.path.join(artifact_dir, dest_filename)
                    shutil.copy(final_page, dest_path)
                    print(f"Copied final image to artifact: {dest_path}")
                else:
                    print("Error: final_comic_page.png not found in output directory")
            else:
                print("Error: No output directory found")
                
        except Exception as e:
            print(f"Error executing test: {e}")

if __name__ == "__main__":
    run()
