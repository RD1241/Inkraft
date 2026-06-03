import os, sys
sys.path.insert(0, '.')
import config.settings as s

print("--- Diagnostic Report ---")
print(f".env path:       {s._env_path}")
print(f".env exists:     {os.path.exists(s._env_path)}")

url_val = s.SUPABASE_URL
url_display = (url_val[:40] + "...") if len(url_val) > 40 else (url_val if url_val else "EMPTY — not filled in .env")
print(f"SUPABASE_URL:    [{url_display}]")

key_val = s.SUPABASE_SECRET_KEY
key_display = f"SET ({len(key_val)} chars)" if key_val else "EMPTY — not filled in .env"
print(f"SECRET_KEY:      [{key_display}]")

pub_val = s.SUPABASE_PUBLISHABLE_KEY
pub_display = f"SET ({len(pub_val)} chars)" if pub_val else "EMPTY — not filled in .env"
print(f"PUBLISHABLE_KEY: [{pub_display}]")

print(f"STORAGE_PROVIDER: {os.environ.get('STORAGE_PROVIDER', 'not in env')}")
print(f"LLM_PROVIDER:     {os.environ.get('LLM_PROVIDER', 'not in env')}")

if not url_val or not key_val:
    print()
    print(f"ACTION REQUIRED: Open {s._env_path} and fill in:")
    print("  SUPABASE_URL=https://xxxx.supabase.co")
    print("  SUPABASE_SECRET_KEY=your-service-role-key")
    print("  SUPABASE_PUBLISHABLE_KEY=your-anon-key")
else:
    print()
    print("All Supabase credentials loaded correctly.")
print("--- End ---")
