import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)
r = client.post("/api/generate_comic", json={
    "text": "short",
    "style": "anime"
})
print("STATUS CODE:", r.status_code)
print("RESPONSE BODY:", r.text)
