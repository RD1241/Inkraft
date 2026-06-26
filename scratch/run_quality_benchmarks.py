# scratch/run_quality_benchmarks.py
import os
import sys
import json
import time
import uuid
import sqlite3
from PIL import Image

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from dotenv import load_dotenv
load_dotenv()

from config import settings
from services.comic_service import comic_service
from services.credits_service import credits_service
from core.character_designer import CharacterDesignSheet
from providers.factory import get_storage_provider
from providers.auth.supabase_auth import SupabaseAuth

# Fix daily limit check for verification/benchmarking by bypassing it
credits_service.check_daily_limit = lambda user_id: True
credits_service.deduct_credit = lambda user_id, re_generate=False: True

# Constant Test User UUID to reuse saved character sheets
BENCHMARK_USER_ID = "b8784513-0e0c-4d2d-a198-255871ff3dca"

DIVIDER = "=" * 80

def banner(msg):
    print(f"\n{DIVIDER}")
    print(f"  {msg}")
    print(DIVIDER)

def verify_image(path):
    """Checks size, readability, and whether it is black."""
    if not os.path.exists(path):
        return False, "File does not exist"
    if os.path.getsize(path) < 1024:
        return False, "File too small (<1KB)"
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            extrema = img.convert("L").getextrema()
            if extrema[1] < 10:
                return False, f"Image is black/mostly-black (max intensity {extrema[1]})"
            return True, "Valid image"
    except Exception as e:
        return False, f"Corrupted or unreadable: {e}"

def run_e2e_job(prompt, style, panel_count, layout_type, format_val, characters):
    print(f"[BENCHMARK] Queueing... Style: {style}, Format: {format_val}, Panels: {panel_count}, Layout: {layout_type}")
    
    # Deduct credit (bypass limits via re_generate=True)
    try:
        credits_service.deduct_credit(BENCHMARK_USER_ID, re_generate=True)
    except Exception as e:
        print(f"[BENCHMARK] Credit deduction failed: {e}")
        return None, "deduction_failed"

    # Queue job
    job_id, cached = comic_service.queue_comic_generation(
        text=prompt,
        style=style,
        panel_count=panel_count,
        layout_type=layout_type,
        user_id=BENCHMARK_USER_ID,
        characters=characters,
        generation_format=format_val
    )
    
    # Poll status
    success = False
    error = None
    result = None
    
    for attempt in range(120): # Max 10 minutes polling
        job = comic_service.job_manager.get_job(job_id)
        status = job.get("status")
        progress = job.get("progress")
        print(f"     Poll {attempt+1}: Status = {status} | Progress = {progress}")
        
        if status == "completed":
            success = True
            result = job.get("result")
            break
        elif status == "failed":
            error = job.get("error")
            break
        time.sleep(5)
        
    if success:
        return result, None
    else:
        return None, error

def main():
    banner("INKRAFT QUALITY BENCHMARK GENERATION SUITE")
    
    # 1. Prepare character profiles
    kael_sheet = CharacterDesignSheet(
        name="Kael",
        gender="Male",
        age_range="Adult",
        hair_style="spiky short crop",
        hair_color="silver hair",
        eye_color="sapphire blue eyes",
        body_type="athletic muscular",
        primary_outfit="high-collared black leather coat",
        distinguishing_features="scar across left cheek",
        personality_note="cold determined gaze"
    )
    elena_sheet = CharacterDesignSheet(
        name="Elena",
        gender="Female",
        age_range="Adult",
        hair_style="long straight braid",
        hair_color="crimson red hair",
        eye_color="emerald green eyes",
        body_type="slender built",
        primary_outfit="silver steel breastplate armor",
        distinguishing_features="small star tattoo under right eye",
        personality_note="cautious sharp eyes"
    )
    aldric_sheet = CharacterDesignSheet(
        name="Aldric",
        gender="Male",
        age_range="Adult",
        hair_style="short slicked back",
        hair_color="golden hair",
        eye_color="amber eyes",
        body_type="tall imposing built",
        primary_outfit="ornate gold-trimmed red robe",
        distinguishing_features="sharp goatee",
        personality_note="stern arrogant look"
    )

    print("[BENCHMARK] Syncing character profiles to Local DB & Supabase...")
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    for sheet in [kael_sheet, elena_sheet, aldric_sheet]:
        cursor.execute('''
            INSERT OR REPLACE INTO character_design_sheets 
            (user_id, name, gender, age_range, hair_style, hair_color, eye_color, body_type, primary_outfit, distinguishing_features, personality_note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (BENCHMARK_USER_ID, sheet.name, sheet.gender, sheet.age_range, sheet.hair_style, sheet.hair_color, sheet.eye_color, sheet.body_type, sheet.primary_outfit, sheet.distinguishing_features, sheet.personality_note))
    conn.commit()
    conn.close()

    auth = SupabaseAuth()
    if auth.enabled and auth.client:
        try:
            for sheet in [kael_sheet, elena_sheet, aldric_sheet]:
                auth.client.table("character_design_sheets").upsert({
                    "user_id": BENCHMARK_USER_ID,
                    "name": sheet.name,
                    **sheet.model_dump()
                }).execute()
            print("[BENCHMARK] Synced characters to Supabase successfully.")
        except Exception as e:
            print(f"[BENCHMARK] [Warning] Failed to sync characters to Supabase: {e}")

    benchmarks = [
        {
            "id": 1,
            "name": "Benchmark 1 — Action Scene",
            "prompt": "Kael charges across a ruined battlefield. An enemy commander blocks his path. Their swords collide with tremendous force. A shockwave erupts across the battlefield.",
            "style": "manga",
            "panel_count": 4,
            "layout_type": "action",
            "format_val": None,
            "characters": [kael_sheet.model_dump()]
        },
        {
            "id": 2,
            "name": "Benchmark 2 — Emotional Dialogue",
            "prompt": "Elena finally discovers that Kael betrayed the kingdom. She asks why. Kael silently lowers his head. Elena begins to cry.",
            "style": "anime",
            "panel_count": 4,
            "layout_type": "dialogue",
            "format_val": None,
            "characters": [kael_sheet.model_dump(), elena_sheet.model_dump()]
        },
        {
            "id": 3,
            "name": "Benchmark 3 — Fantasy World",
            "prompt": "A floating city drifts above the clouds. Ancient dragons circle the towers. A young mage stands on a balcony overlooking the world.",
            "style": "manhwa",
            "panel_count": 1,
            "layout_type": "cinematic",
            "format_val": "single_page",
            "characters": []
        },
        {
            "id": 4,
            "name": "Benchmark 4 — Romance",
            "prompt": "Kael and Elena walk together beneath glowing lanterns. They stop near a river. Neither knows what to say. Their hands slowly touch.",
            "style": "anime",
            "panel_count": 4,
            "layout_type": "drama",
            "format_val": None,
            "characters": [kael_sheet.model_dump(), elena_sheet.model_dump()]
        },
        {
            "id": 5,
            "name": "Benchmark 5 — Two Character Confrontation",
            "prompt": "Kael confronts Aldric in the throne room. Both men accuse each other of betrayal. The tension rises. Neither is willing to back down.",
            "style": "cinematic",
            "panel_count": 1,
            "layout_type": "action",
            "format_val": "single_page",
            "characters": [kael_sheet.model_dump(), aldric_sheet.model_dump()]
        }
    ]

    results_report = {}
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for b in benchmarks:
        banner(f"RUNNING {b['name']}")
        res_payload, err = run_e2e_job(
            prompt=b["prompt"],
            style=b["style"],
            panel_count=b["panel_count"],
            layout_type=b["layout_type"],
            format_val=b["format_val"],
            characters=b["characters"]
        )
        
        if err:
            print(f"[BENCHMARK] {b['name']} FAILED: {err}")
            results_report[b["name"]] = {"status": "failed", "error": err}
        else:
            comic_res = json.loads(res_payload) if isinstance(res_payload, str) else res_payload
            final_page = comic_res.get("final_page")
            panels = comic_res.get("panels", [])
            
            final_path = os.path.join(base_dir, final_page.lstrip('/'))
            valid, msg = verify_image(final_path)
            print(f"[BENCHMARK] Final Page ({final_page}) verification: {'PASSED' if valid else 'FAILED'} | {msg}")
            
            panel_status = []
            for p in panels:
                p_path = os.path.join(base_dir, p.lstrip('/'))
                v_p, msg_p = verify_image(p_path)
                panel_status.append({"path": p, "valid": v_p, "msg": msg_p})
                print(f"     * Panel ({p}) verification: {'PASSED' if v_p else 'FAILED'} | {msg_p}")
                
            results_report[b["name"]] = {
                "status": "success",
                "final_page": final_page,
                "panels": panels,
                "verification": "PASSED" if valid else "FAILED",
                "panel_status": panel_status
            }

    banner("QUALITY BENCHMARK RUN COMPLETE")
    print(json.dumps(results_report, indent=2))

if __name__ == "__main__":
    main()
