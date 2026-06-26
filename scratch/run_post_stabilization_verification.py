# scratch/run_post_stabilization_verification.py
import os
import sys
import json
import time
import uuid
import sqlite3
from datetime import datetime
from PIL import Image

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from dotenv import load_dotenv
load_dotenv()

from config import settings
from services.comic_service import comic_service
from services.credits_service import credits_service
from services.history_service import history_service
from core.character_designer import CharacterDesignSheet
from providers.factory import get_image_provider, get_storage_provider, get_llm_provider
from providers.auth.supabase_auth import SupabaseAuth

# Test UUIDs
TEST_USER_ID = str(uuid.uuid4())
TEST_EMAIL = f"qa_verifier_{uuid.uuid4().hex[:6]}@inkraft.test"

DIVIDER = "=" * 80

def banner(msg):
    print(f"\n{DIVIDER}")
    print(f"  {msg}")
    print(DIVIDER)

def verify_image(path):
    """
    Returns (is_valid: bool, error_msg: str, extrema: tuple)
    Checks size, readability, and whether it is black.
    """
    if not os.path.exists(path):
        return False, "File does not exist", None
    if os.path.getsize(path) < 1024:
        return False, "File too small (<1KB)", None
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            extrema = img.convert("L").getextrema()
            if extrema[1] < 10:
                return False, f"Image is black/mostly-black (max intensity {extrema[1]})", extrema
            return True, "Valid image", extrema
    except Exception as e:
        return False, f"Corrupted or unreadable: {e}", None

def check_supabase_sync():
    """
    Checks if Supabase integration is active and healthy.
    """
    auth = SupabaseAuth()
    if not auth.enabled or not auth.client:
        return False, "Supabase integration not enabled in settings/env."
    try:
        # Check simple query
        r = auth.client.table("credits").select("balance").limit(1).execute()
        return True, "Supabase is active and query succeeded.", getattr(r, "data", [])
    except Exception as e:
        return False, f"Supabase health check failed: {e}", None

def run_e2e_job(prompt, style, panel_count, layout_type, format_val, characters):
    """
    Runs an E2E generation job using comic_service.queue_comic_generation
    and polls it to completion.
    """
    print(f"[QA] Queueing job... Style: {style}, Format: {format_val}, Panels: {panel_count}, Layout: {layout_type}")
    
    # 1. Deduct credit
    credits_before = credits_service.get_balance(TEST_USER_ID)
    try:
        credits_service.deduct_credit(TEST_USER_ID, re_generate=True)
        print(f"[QA] Credit deducted. Balance: {credits_before} -> {credits_service.get_balance(TEST_USER_ID)}")
    except Exception as e:
        print(f"[QA] Credit deduction failed: {e}")
        return None, "deduction_failed", 0

    # 2. Queue job
    job_id, cached = comic_service.queue_comic_generation(
        text=prompt,
        style=style,
        panel_count=panel_count,
        layout_type=layout_type,
        user_id=TEST_USER_ID,
        characters=characters,
        generation_format=format_val
    )
    
    start_time = time.time()
    
    # 3. Poll status
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
        
    duration = time.time() - start_time
    credits_after = credits_service.get_balance(TEST_USER_ID)
    
    if success:
        return {
            "job_id": job_id,
            "status": "success",
            "duration_seconds": int(duration),
            "credits_before": credits_before,
            "credits_after": credits_after,
            "result": result
        }, None, duration
    else:
        # Check if refund was processed
        print(f"[QA] Job failed: {error}. Verifying refund...")
        refunded_credits = credits_service.get_balance(TEST_USER_ID)
        return {
            "job_id": job_id,
            "status": "failed",
            "error": error,
            "duration_seconds": int(duration),
            "credits_before": credits_before,
            "credits_after": refunded_credits
        }, error, duration

def main():
    banner("INKRAFT POST-STABILIZATION QA & VALIDATION SPRINT")
    
    # Pre-test connections and checks
    print("[QA] 1. Verifying environment configurations...")
    supabase_ok, supabase_msg, _ = check_supabase_sync()
    print(f"     Supabase status: {supabase_msg}")
    
    # Register QA user on local credits DB
    credits_service._init_sqlite()
    initial_credits = credits_service.get_balance(TEST_USER_ID)
    print(f"     Test User UUID: {TEST_USER_ID}")
    print(f"     Test User Initial Credits: {initial_credits}")
    
    # 1. Save character profiles in local SQLite & Supabase
    print("\n[QA] 2. Preparing saved character profiles...")
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
    
    # Save profiles via characters DB helpers
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO character_design_sheets 
        (user_id, name, gender, age_range, hair_style, hair_color, eye_color, body_type, primary_outfit, distinguishing_features, personality_note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (TEST_USER_ID, "Kael", kael_sheet.gender, kael_sheet.age_range, kael_sheet.hair_style, kael_sheet.hair_color, kael_sheet.eye_color, kael_sheet.body_type, kael_sheet.primary_outfit, kael_sheet.distinguishing_features, kael_sheet.personality_note))
    cursor.execute('''
        INSERT OR REPLACE INTO character_design_sheets 
        (user_id, name, gender, age_range, hair_style, hair_color, eye_color, body_type, primary_outfit, distinguishing_features, personality_note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (TEST_USER_ID, "Elena", elena_sheet.gender, elena_sheet.age_range, elena_sheet.hair_style, elena_sheet.hair_color, elena_sheet.eye_color, elena_sheet.body_type, elena_sheet.primary_outfit, elena_sheet.distinguishing_features, elena_sheet.personality_note))
    conn.commit()
    conn.close()
    
    if supabase_ok:
        auth = SupabaseAuth()
        try:
            auth.client.table("character_design_sheets").upsert({
                "user_id": TEST_USER_ID,
                "name": "Kael",
                **kael_sheet.model_dump()
            }).execute()
            auth.client.table("character_design_sheets").upsert({
                "user_id": TEST_USER_ID,
                "name": "Elena",
                **elena_sheet.model_dump()
            }).execute()
            print("     Character profiles successfully synced to Supabase.")
        except Exception as e:
            print(f"     [Warning] Failed to sync characters to Supabase: {e}")
            
    print("     Character profiles saved successfully.")

    # We will record E2E metrics for the 5 tests
    test_results = {}
    
    # ========================================================
    # TEST 1 — MANGA
    # ========================================================
    banner("TEST 1: Manga Style - Action Layout")
    t1_prompt = "Kael charged forward, his blade catching the moonlight. The knight raised his shield, sparks flying as steel met steel."
    t1_res, t1_err, t1_dur = run_e2e_job(
        prompt=t1_prompt,
        style="manga",
        panel_count=3,
        layout_type="action",
        format_val=None, # AI Decides
        characters=[kael_sheet.model_dump()]
    )
    test_results["Test 1 (Manga)"] = (t1_res, t1_err, t1_dur)

    # ========================================================
    # TEST 2 — MANHWA
    # ========================================================
    banner("TEST 2: Manhwa Style - Drama Layout")
    t2_prompt = "Elena set the letter on the table between them. Neither spoke. Then she said quietly: 'I know what you did.'"
    t2_res, t2_err, t2_dur = run_e2e_job(
        prompt=t2_prompt,
        style="manhwa",
        panel_count=3,
        layout_type="drama",
        format_val=None, # AI Decides
        characters=[elena_sheet.model_dump()]
    )
    test_results["Test 2 (Manhwa)"] = (t2_res, t2_err, t2_dur)

    # ========================================================
    # TEST 3 — ANIME
    # ========================================================
    banner("TEST 3: Anime Style - Dialogue Layout")
    # First save fresh character profile for Sora
    sora_sheet = CharacterDesignSheet(
        name="Sora",
        gender="Female",
        age_range="Teen",
        hair_style="twin tails ponytail",
        hair_color="electric blue hair",
        eye_color="violet eyes",
        body_type="slender petite",
        primary_outfit="school uniform blazer",
        distinguishing_features="red ribbon hairclip",
        personality_note="cheerful talking smile"
    )
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO character_design_sheets 
        (user_id, name, gender, age_range, hair_style, hair_color, eye_color, body_type, primary_outfit, distinguishing_features, personality_note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (TEST_USER_ID, "Sora", sora_sheet.gender, sora_sheet.age_range, sora_sheet.hair_style, sora_sheet.hair_color, sora_sheet.eye_color, sora_sheet.body_type, sora_sheet.primary_outfit, sora_sheet.distinguishing_features, sora_sheet.personality_note))
    conn.commit()
    conn.close()
    if supabase_ok:
        try:
            auth = SupabaseAuth()
            auth.client.table("character_design_sheets").upsert({
                "user_id": TEST_USER_ID,
                "name": "Sora",
                **sora_sheet.model_dump()
            }).execute()
        except Exception as e:
            print(f"     [Warning] Failed to sync Sora to Supabase: {e}")
    print("[QA] Fresh character profile 'Sora' saved in vault.")
    
    t3_prompt = "Sora smiled warmly, pointing to the skies. 'Look, a shooting star! make a wish right now!'"
    t3_res, t3_err, t3_dur = run_e2e_job(
        prompt=t3_prompt,
        style="anime",
        panel_count=3,
        layout_type="dialogue",
        format_val=None, # AI Decides
        characters=[sora_sheet.model_dump()]
    )
    test_results["Test 3 (Anime)"] = (t3_res, t3_err, t3_dur)

    # ========================================================
    # TEST 4 — CINEMATIC
    # ========================================================
    banner("TEST 4: Cinematic Style - Single Page Format")
    t4_prompt = "A mysterious knight climbs the high peaks of the dragon mountain. A storm rages, lightning crackling across the gray clouds. Elena stands determined in the wind."
    t4_res, t4_err, t4_dur = run_e2e_job(
        prompt=t4_prompt,
        style="cinematic",
        panel_count=1,
        layout_type="cinematic",
        format_val="single_page",
        characters=[elena_sheet.model_dump()]
    )
    test_results["Test 4 (Cinematic)"] = (t4_res, t4_err, t4_dur)

    # ========================================================
    # TEST 5 — REALISTIC
    # ========================================================
    banner("TEST 5: Realistic Style - Single Page Format")
    t5_prompt = "A portrait photo of Kael, wearing his high-collared leather coat, standing in a crowded neon-lit Tokyo street."
    t5_res, t5_err, t5_dur = run_e2e_job(
        prompt=t5_prompt,
        style="realistic",
        panel_count=1,
        layout_type="cinematic",
        format_val="single_page",
        characters=[kael_sheet.model_dump()]
    )
    test_results["Test 5 (Realistic)"] = (t5_res, t5_err, t5_dur)

    # ========================================================
    # REFUND & FAILURE VERIFICATION (Failure Test Case)
    # ========================================================
    banner("REFUND & FAILURE VERIFICATION")
    # We will intentionally force a failure by mocking image generation to raise an error
    from unittest.mock import patch
    print("[QA] Simulating generation failure to verify refund behavior...")
    
    with patch('providers.image.fal_ai.FalAIImageProvider.generate_image', side_effect=RuntimeError("Simulated API generating failure")):
        tf_res, tf_err, tf_dur = run_e2e_job(
            prompt="Simulated crash description with long prompt text.",
            style="anime",
            panel_count=2,
            layout_type="dialogue",
            format_val=None,
            characters=[]
        )
    test_results["Refund Test"] = (tf_res, tf_err, tf_dur)

    # Print E2E Sprint Report Summary
    banner("QA VERIFICATION SPRINT REPORT")
    print(f"Test User UUID: {TEST_USER_ID}")
    
    black_image_fail = False
    
    for name, (res, err, dur) in test_results.items():
        print(f"\n{name} Results:")
        if err:
            print(f"  - Status: FAILED")
            print(f"  - Error: {err}")
            if res:
                print(f"  - Credits before: {res['credits_before']}")
                print(f"  - Credits after (refunded): {res['credits_after']}")
                if res['credits_before'] == res['credits_after']:
                    print(f"  - Credit check: PASSED (net zero balance change)")
                else:
                    print(f"  - Credit check: FAILED (credits were deducted but not refunded)")
            else:
                print(f"  - Credit check: SKIPPED (Job was not queued)")
        else:
            print(f"  - Status: SUCCESS")
            print(f"  - Duration: {int(dur)} seconds")
            print(f"  - Credits before: {res['credits_before']}")
            print(f"  - Credits after: {res['credits_after']}")
            if res['credits_before'] - 1 == res['credits_after']:
                print(f"  - Credit check: PASSED (-1 credit deducted)")
            else:
                print(f"  - Credit check: FAILED (deduction count error)")
                
            # Black image check
            comic_res = json.loads(res["result"]) if isinstance(res["result"], str) else res["result"]
            final_page = comic_res.get("final_page")
            panels = comic_res.get("panels", [])
            
            # Check final page
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            final_path = os.path.join(base_dir, final_page.lstrip('/'))
            valid, msg, extrema = verify_image(final_path)
            print(f"  - Final Page Check ({final_page}): {'PASSED' if valid else 'FAILED'} | {msg}")
            if not valid:
                black_image_fail = True
                
            # Check individual panels
            for idx, panel in enumerate(panels):
                panel_path = os.path.join(base_dir, panel.lstrip('/'))
                valid_p, msg_p, extrema_p = verify_image(panel_path)
                print(f"    * Panel {idx+1} ({panel}): {'PASSED' if valid_p else 'FAILED'} | {msg_p}")
                if not valid_p:
                    black_image_fail = True

    print(f"\n[QA] Black Image Safety verification: {'FAILED' if black_image_fail else 'PASSED'}")
    
    # Check logs/generation_metadata.jsonl exists and has rows
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "generation_metadata.jsonl")
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as lf:
            lines = lf.readlines()
        print(f"[QA] Metadata log path '{log_path}' has {len(lines)} records.")
        # Print the last record
        if lines:
            print(f"     Last Log Entry: {lines[-1].strip()}")
    else:
        print("[QA] Warning: logs/generation_metadata.jsonl file was not found!")

if __name__ == "__main__":
    main()
