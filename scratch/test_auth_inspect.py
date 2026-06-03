import sys
import os
import uuid
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

client = TestClient(app)

email = f"user_{uuid.uuid4().hex[:6]}@example.com"
password = "Password123!"

print(f"Registering user {email} via TestClient...")
try:
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    print("Register status:", r.status_code)
    data = r.json()
    token = data.get("access_token")
    user_id = data.get("user", {}).get("id")
    print("User ID:", user_id)
    print("Token prefix:", token[:15] if token else "None")
    
    if token:
        # Now let's call get history
        print("\nCalling GET /api/history with token...")
        headers = {"Authorization": f"Bearer {token}"}
        r_hist = client.get("/api/history", headers=headers)
        print("History response status:", r_hist.status_code)
        print("History response body:", r_hist.text)
        
        # Now let's call get balance
        print("\nCalling GET /api/credits/balance with token...")
        r_bal = client.get("/api/credits/balance", headers=headers)
        print("Balance response status:", r_bal.status_code)
        print("Balance response body:", r_bal.text)
except Exception as e:
    print("Exception during test:", e)
