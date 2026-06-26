import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.environ.get("SUPABASE_URL", "").rstrip('/')
supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")

if not supabase_url or not supabase_key:
    print("Supabase credentials not found!")
    exit(1)

headers = {
    "apikey": supabase_key,
    "Authorization": f"Bearer {supabase_key}"
}

url = f"{supabase_url}/rest/v1/"
try:
    r = httpx.get(url, headers=headers, timeout=10.0)
    if r.status_code == 200:
        spec = r.json()
        definitions = spec.get("definitions", {})
        
        # Save structural definitions for jobs, comics, characters
        result = {}
        for table in ["jobs", "comics", "credits", "credit_transactions", "characters", "character_design_sheets"]:
            if table in definitions:
                properties = definitions[table].get("properties", {})
                cols = {k: v.get("format", v.get("type")) for k, v in properties.items()}
                result[table] = cols
            else:
                result[table] = "NOT DEFINED"
                
        print(json.dumps(result, indent=4))
    else:
        print(f"Failed to fetch OpenAPI spec: {r.status_code} - {r.text}")
except Exception as e:
    print(f"Error: {e}")
