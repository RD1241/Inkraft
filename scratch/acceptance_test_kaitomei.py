"""
Acceptance test v2: Kaito/Mei story through the live app with correct routes.
"""
import httpx
import json
import time
import sys

STORY = (
    "Kaito sat alone in the school library, the only sound the soft hum "
    "of the ceiling lights. He stared at the letter in his hands, reading "
    "it for the third time. Across the room, the door creaked open and "
    "Mei stepped in, her bag slung over one shoulder. She froze when she "
    "saw his expression. 'What happened?' she asked, walking closer. "
    "Kaito didn't look up. 'They're closing the dojo. After twenty years, "
    "it's just... over.' He crumpled the letter and pressed it against his "
    "chest. Mei sat down beside him, saying nothing, just staying close as "
    "the silence settled between them."
)

BASE = "http://127.0.0.1:8000"

# Register
reg = httpx.post(f"{BASE}/api/auth/register",
    json={"email": "kaitomei_test@inkraft.ai", "password": "TestPass123!", "username": "kaitomeitest"},
    timeout=10)
print(f"Register: {reg.status_code}")

# Login
login = httpx.post(f"{BASE}/api/auth/login",
    json={"email": "kaitomei_test@inkraft.ai", "password": "TestPass123!"},
    timeout=10)
print(f"Login: {login.status_code}")
token = login.json().get("access_token", "")
if not token:
    print(f"Login body: {login.text[:300]}")
    sys.exit(1)

headers = {"Authorization": f"Bearer {token}"}

# Submit generation
gen = httpx.post(f"{BASE}/api/generate_comic",
    json={"text": STORY, "style": "manga", "panel_count": 3},
    headers=headers, timeout=15)
print(f"Generate: {gen.status_code}")
if gen.status_code not in (200, 202):
    print(gen.text[:500])
    sys.exit(1)

job_id = gen.json().get("job_id", "")
print(f"Job ID: {job_id}")

# Poll
start = time.time()
last_progress = ""
while time.time() - start < 300:
    st = httpx.get(f"{BASE}/api/status/{job_id}", headers=headers, timeout=10)
    data = st.json()
    status = data.get("status", "")
    progress = data.get("progress", "")
    if progress != last_progress:
        elapsed = time.time() - start
        print(f"  [{elapsed:.0f}s] {status}: {progress}")
        last_progress = progress
    if status == "completed":
        res_val = data.get("result")
        result = json.loads(res_val) if isinstance(res_val, str) else (res_val or {})
        print(f"\nCOMPLETED")
        print(f"output_dir: {result.get('output_dir', '?')}")
        print(f"comic_page_url: {result.get('comic_page_url', '?')}")
        # Print character extraction result
        scenes = result.get('scenes_metadata', {})
        if isinstance(scenes, dict):
            for sc in scenes.get('scenes', [])[:2]:
                chars = [c.get('name') for c in sc.get('characters', [])]
                print(f"Scene {sc.get('scene_id')}: chars={chars}")
        break
    elif status == "failed":
        print(f"FAILED: {data.get('error','?')}")
        sys.exit(1)
    time.sleep(3)
