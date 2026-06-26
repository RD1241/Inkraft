import os
import sys
import httpx

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from config import settings
    FAL_KEY = getattr(settings, "FAL_KEY", None)
except ImportError:
    FAL_KEY = None

def main():
    fal_key = os.environ.get("FAL_KEY") or FAL_KEY
    if not fal_key:
        print("FAL_KEY is not set.")
        return

    headers = {
        "Authorization": f"Key {fal_key}"
    }

    endpoints = [
        "https://rest.fal.ai/billing/balance",
        "https://rest.fal.ai/users/me/balance",
        "https://rest.fal.ai/billing/details",
        "https://rest.fal.ai/usage",
    ]

    for url in endpoints:
        print(f"Trying GET {url}...")
        try:
            r = httpx.get(url, headers=headers, timeout=5)
            print(f"  Status: {r.status_code}")
            if r.status_code == 200:
                print(f"  Response: {r.text}")
            else:
                print(f"  Error Response: {r.text[:200]}")
        except Exception as e:
            print(f"  Failed: {e}")

if __name__ == "__main__":
    main()
