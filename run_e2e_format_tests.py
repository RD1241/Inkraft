# run_e2e_format_tests.py
import requests
import time
import sys
import json
import sqlite3
import os
import uuid

BASE = "http://127.0.0.1:8000/api"
TEST_EMAIL = f"format_e2etest_{uuid.uuid4().hex[:8]}@inkraft.test"
TEST_PASS  = "TestPass123!"

DIVIDER = "=" * 70

def banner(msg):
    print(f"\n{DIVIDER}")
    print(f"  {msg}")
    print(DIVIDER)

def ok(msg):
    print(f"  [OK]   {msg}")

def fail(msg):
    print(f"  [FAIL] {msg}")
    sys.exit(1)

def info(msg):
    print(f"  [INFO] {msg}")

# Wait for server to start
info("Checking if server is up...")
for _ in range(15):
    try:
        r = requests.get(f"{BASE}/health", timeout=2)
        if r.status_code == 200:
            ok("Server is online!")
            break
    except Exception:
        pass
    time.sleep(1)
else:
    fail("FastAPI server on port 8000 did not start in time.")

# ─────────────────────────────────────────────────────────────
# Auth Registration
# ─────────────────────────────────────────────────────────────
info(f"Registering E2E test user: {TEST_EMAIL}")
r = requests.post(f"{BASE}/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASS})
reg_data = r.json()
token = reg_data.get("access_token") or reg_data.get("token") or (reg_data.get("data") or {}).get("access_token")
user_id = (reg_data.get("user") or {}).get("id") or "00000000-0000-0000-0000-000000000000"

if not token:
    # Try login
    r = requests.post(f"{BASE}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASS})
    login_data = r.json()
    token = login_data.get("access_token") or login_data.get("token") or (login_data.get("data") or {}).get("access_token")
    user_id = (login_data.get("user") or {}).get("id") or user_id

if not token:
    fail(f"Could not authenticate E2E test user. Reg response: {reg_data}")

AUTH_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}",
    "X-User-ID": user_id
}
ok(f"Authenticated! token={token[:25]}..., user_id={user_id}")

# ─────────────────────────────────────────────────────────────
# TEST 1: Manhwa Single Page, AI Decides
# ─────────────────────────────────────────────────────────────
banner("TEST 1: Manhwa Single Page (AI Decides format)")
t1_payload = {
    "text": "Elena stood at the window, staring out at the rain-slicked city. She was waiting for him.",
    "style": "manhwa",
    "generation_format": None # AI Decides
}
r1 = requests.post(f"{BASE}/generate_comic", json=t1_payload, headers=AUTH_HEADERS)
if not r1.ok:
    fail(f"Test 1 request failed: {r1.text}")
t1_job_id = r1.json()["job_id"]
info(f"Test 1 queued. Job ID: {t1_job_id}")

# Poll status
t1_success = False
while True:
    status_res = requests.get(f"{BASE}/status/{t1_job_id}", headers=AUTH_HEADERS).json()
    status = status_res.get("status")
    progress = status_res.get("progress")
    info(f"Test 1 progress: {status} | {progress}")
    if status == "completed":
        t1_success = True
        break
    elif status == "failed":
        fail(f"Test 1 failed: {status_res.get('error')}")
    time.sleep(5)

# Verify Test 1 results
if t1_success:
    # Query database directly to check resolved format
    db_path = os.path.join("core", "jobs.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT generation_format, panel_count FROM jobs WHERE job_id = ?", (t1_job_id,))
    row = cursor.fetchone()
    conn.close()
    
    resolved_format = row[0] if row else None
    panel_count = row[1] if row else None
    
    ok(f"Test 1 resolved format in DB: {resolved_format}, panel_count: {panel_count}")
    
    status_res = requests.get(f"{BASE}/status/{t1_job_id}", headers=AUTH_HEADERS).json()
    result = status_res.get("result")
    if isinstance(result, str):
        result = json.loads(result)
        
    panels = result.get("panels", [])
    total_scenes = result.get("total_scenes")
    
    ok(f"Test 1 result has {len(panels)} panel image and total_scenes = {total_scenes}")
    if len(panels) == 1 and total_scenes == 1:
        ok("TEST 1 PASSED: Resolved to exactly 1 single page cinematic panel.")
    else:
        fail(f"TEST 1 FAILED: Expected 1 panel, got {len(panels)}")

# ─────────────────────────────────────────────────────────────
# TEST 2: Manga Panel Strip, AI Decides
# ─────────────────────────────────────────────────────────────
banner("TEST 2: Manga Panel Strip (AI Decides format)")
t2_payload = {
    "text": "Kael charged forward, his steps heavy. Elena watched him, silent. Then, he spoke: 'We must go.'",
    "style": "manga",
    "generation_format": None # AI Decides
}
r2 = requests.post(f"{BASE}/generate_comic", json=t2_payload, headers=AUTH_HEADERS)
if not r2.ok:
    fail(f"Test 2 request failed: {r2.text}")
t2_job_id = r2.json()["job_id"]
info(f"Test 2 queued. Job ID: {t2_job_id}")

# Poll status
t2_success = False
while True:
    status_res = requests.get(f"{BASE}/status/{t2_job_id}", headers=AUTH_HEADERS).json()
    status = status_res.get("status")
    progress = status_res.get("progress")
    info(f"Test 2 progress: {status} | {progress}")
    if status == "completed":
        t2_success = True
        break
    elif status == "failed":
        fail(f"Test 2 failed: {status_res.get('error')}")
    time.sleep(5)

# Verify Test 2 results
if t2_success:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT generation_format, panel_count FROM jobs WHERE job_id = ?", (t2_job_id,))
    row = cursor.fetchone()
    conn.close()
    
    resolved_format = row[0] if row else None
    panel_count = row[1] if row else None
    
    ok(f"Test 2 resolved format in DB: {resolved_format}, panel_count: {panel_count}")
    
    status_res = requests.get(f"{BASE}/status/{t2_job_id}", headers=AUTH_HEADERS).json()
    result = status_res.get("result")
    if isinstance(result, str):
        result = json.loads(result)
        
    panels = result.get("panels", [])
    total_scenes = result.get("total_scenes")
    
    ok(f"Test 2 result has {len(panels)} panels and total_scenes = {total_scenes}")
    if len(panels) >= 2:
        ok("TEST 2 PASSED: Resolved to multi-panel panel strip format.")
    else:
        fail(f"TEST 2 FAILED: Expected multiple panels, got {len(panels)}")

# ─────────────────────────────────────────────────────────────
# TEST 3: Manga Action SFX, Panel Strip
# ─────────────────────────────────────────────────────────────
banner("TEST 3: Manga Action SFX")
t3_payload = {
    "text": "Kael's blade clashed against the iron shield. Sparks flew as the sword scraped against metal. Elena watched the duel in terror.",
    "style": "manga",
    "generation_format": "panel_strip",
    "layout_type": "action",
    "panel_count": 3
}
r3 = requests.post(f"{BASE}/generate_comic", json=t3_payload, headers=AUTH_HEADERS)
if not r3.ok:
    fail(f"Test 3 request failed: {r3.text}")
t3_job_id = r3.json()["job_id"]
info(f"Test 3 queued. Job ID: {t3_job_id}")

# Poll status
t3_success = False
while True:
    status_res = requests.get(f"{BASE}/status/{t3_job_id}", headers=AUTH_HEADERS).json()
    status = status_res.get("status")
    progress = status_res.get("progress")
    info(f"Test 3 progress: {status} | {progress}")
    if status == "completed":
        t3_success = True
        break
    elif status == "failed":
        fail(f"Test 3 failed: {status_res.get('error')}")
    time.sleep(5)

# Verify Test 3 results and logs
if t3_success:
    ok("Test 3 generation completed successfully.")
    
    # Check that SFX printed log output
    # Find uvicorn task log file
    task_log_dir = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\dell"), ".gemini", "antigravity", "brain", "9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6", ".system_generated", "tasks")
    log_files = [f for f in os.listdir(task_log_dir) if f.endswith(".log")]
    
    # Sort logs by modification time to find the latest uvicorn output
    log_files.sort(key=lambda x: os.path.getmtime(os.path.join(task_log_dir, x)), reverse=True)
    
    sfx_font_log_found = False
    sfx_render_log_found = False
    
    for log_file in log_files:
        log_path = os.path.join(task_log_dir, log_file)
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "[Renderer] SFX font:" in content:
                    sfx_font_log_found = True
                if "rendered at corner" in content or "Sound effect" in content:
                    sfx_render_log_found = True
                if sfx_font_log_found:
                    # Print matching font log line
                    for line in content.split("\n"):
                        if "[Renderer] SFX font:" in line:
                            info(f"Found log line: {line.strip()}")
                    break
        except Exception:
            pass
            
    if sfx_font_log_found:
        ok("TEST 3 PASSED: Sound effect font fallback chain logged successfully.")
    else:
        fail("TEST 3 FAILED: Sound effect font log not found in uvicorn logs.")

banner("ALL E2E VERIFICATION TESTS PASSED SUCCESSFULLY!")
