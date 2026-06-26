import os
import httpx
from dotenv import load_dotenv

# Load env
load_dotenv()

supabase_url = os.environ.get("SUPABASE_URL", "").rstrip('/')
supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")

if not supabase_url or not supabase_key:
    print("Supabase credentials not found in env!")
    exit(1)

print(f"Connecting to Supabase at {supabase_url}...")

headers = {
    "apikey": supabase_key,
    "Authorization": f"Bearer {supabase_key}",
    "Content-Type": "application/json"
}

# We can query PostgREST API schema details or query empty tables to inspect column names
tables = ["jobs", "comics", "credits", "credit_transactions", "characters", "dialogues", "panels"]

for table in tables:
    url = f"{supabase_url}/rest/v1/{table}"
    # Query with Limit 0 to get column headers or structures
    params = {"limit": "1"}
    try:
        r = httpx.get(url, headers=headers, params=params, timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            cols = list(data[0].keys()) if data else "Empty table (no rows)"
            print(f"\nTable '{table}' response columns: {cols}")
        else:
            print(f"\nTable '{table}' failed with status {r.status_code}: {r.text}")
    except Exception as e:
        print(f"\nTable '{table}' failed with error: {e}")
