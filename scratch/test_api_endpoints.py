import os
import sys
import unittest
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from api.main import app
from services.credits_service import credits_service

class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        from api.routes.auth import get_current_user
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "22222222-3333-4444-5555-666666666666",
            "email": "test-api@example.com"
        }
        self.client = TestClient(app)
        # Point to a temporary db for testing inside the credits service
        self.test_db = os.path.join(os.path.dirname(__file__), "test_api_jobs.db")
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        credits_service.db_path = self.test_db
        credits_service._init_sqlite()

    def tearDown(self):
        from api.routes.auth import get_current_user
        app.dependency_overrides.pop(get_current_user, None)
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_credits_balance_endpoint(self):
        # 1. Default user balance request
        r = self.client.get("/api/credits/balance")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["balance"], 10)

        # 2. Specific user id as query param
        user_id = "11111111-2222-3333-4444-555555555555"
        r = self.client.get(f"/api/credits/balance?user_id={user_id}")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["user_id"], user_id)
        self.assertEqual(data["balance"], 10)

        # 3. Specific user id as X-User-ID header
        user_id_header = "66666666-7777-8888-9999-000000000000"
        r = self.client.get("/api/credits/balance", headers={"X-User-ID": user_id_header})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["user_id"], user_id_header)
        self.assertEqual(data["balance"], 10)

    def test_credits_history_endpoint(self):
        r = self.client.get("/api/credits/history")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(len(data["history"]) >= 1)

    def test_generate_comic_billing_gate(self):
        # 1. Invalid input validation check (too short)
        r = self.client.post("/api/generate_comic", json={
            "text": "short",
            "style": "anime"
        }, headers={"Authorization": "Bearer mock-token"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["status"], "error")
        self.assertIn("too short", r.json()["message"].lower())

        # 2. Deduct credit flow for valid length prompt
        user_id = "22222222-3333-4444-5555-666666666666"
        # Pre-initialize user balance
        credits_service.get_balance(user_id)
        self.assertEqual(credits_service.get_balance(user_id), 10)

        # We will mock the cache manager to not hit, and verify that the billing gate deducts a credit
        from unittest.mock import patch
        with patch('core.cache_manager.CacheManager.get_cached_result', return_value=None), \
             patch('services.comic_service.comic_service.job_executor.submit') as mock_submit:
            # Try to post a valid generation request
            # Let's use a long enough prompt text: "This is a long enough text description for the novel to comic generator test to pass validation."
            r = self.client.post("/api/generate_comic", json={
                "text": "This is a long enough text description for the novel to comic generator test to pass validation.",
                "style": "anime",
                "user_id": user_id
            }, headers={"Authorization": "Bearer mock-token"})
            # Verify deduction took place
            self.assertEqual(credits_service.get_balance(user_id), 9)
            # Verify that the background worker was indeed queued
            mock_submit.assert_called_once()

if __name__ == "__main__":
    unittest.main()
