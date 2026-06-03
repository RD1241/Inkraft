import os
import sys
import unittest
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from api.main import app

class TestCharactersAPI(unittest.TestCase):
    def setUp(self):
        from api.routes.auth import get_current_user
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "test-user-characters-api",
            "email": "test-characters-api@example.com"
        }
        self.client = TestClient(app)
        self.user_id = "test-user-characters-api"
        
    def tearDown(self):
        from api.routes.auth import get_current_user
        app.dependency_overrides.pop(get_current_user, None)
        
    def test_characters_crud_flow(self):
        # 1. Create a character design sheet via POST
        payload = {
            "name": "Alex",
            "gender": "non-binary",
            "age_range": "young adult",
            "hair_style": "undercut",
            "hair_color": "neon pink",
            "eye_color": "hazel",
            "body_type": "slender",
            "primary_outfit": "leather jacket and dark jeans",
            "distinguishing_features": "silver earring",
            "personality_note": "sarcastic but loyal"
        }
        
        r = self.client.post(f"/api/characters?user_id={self.user_id}", json=payload)
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["character"]["name"], "Alex")
        
        # 2. Get the created character via GET /{name}
        r = self.client.get(f"/api/characters/Alex?user_id={self.user_id}")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["name"], "Alex")
        self.assertEqual(data["gender"], "non-binary")
        self.assertEqual(data["hair_style"], "undercut")
        self.assertEqual(data["hair_color"], "neon pink")
        
        # 3. List all characters via GET
        r = self.client.get(f"/api/characters?user_id={self.user_id}")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertIsInstance(data, list)
        self.assertTrue(any(c["name"] == "Alex" for c in data))
        
        # 4. Delete the character via DELETE /{name}
        r = self.client.delete(f"/api/characters/Alex?user_id={self.user_id}")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["status"], "success")
        
        # 5. Verify it was deleted (should return 404)
        r = self.client.get(f"/api/characters/Alex?user_id={self.user_id}")
        self.assertEqual(r.status_code, 404)

    def test_generate_comic_accepts_characters(self):
        # Verify that generating comic endpoint accepts the 'characters' field without schema errors
        # (even if input validation fails for text length or credit balance, the schema check must pass)
        r = self.client.post("/api/generate_comic", json={
            "text": "short text",
            "style": "anime",
            "characters": [
                {
                    "name": "Alex",
                    "gender": "male",
                    "age_range": "teen",
                    "hair_style": "short",
                    "hair_color": "black",
                    "eye_color": "brown",
                    "body_type": "average",
                    "primary_outfit": "casual shirts",
                    "distinguishing_features": "none",
                    "personality_note": "calm"
                }
            ]
        }, headers={"Authorization": "Bearer mock-token"})
        # Validates that we don't get a 422 Unprocessable Entity (schema error), but instead 400 (validation error for too short text)
        self.assertEqual(r.status_code, 400)
        self.assertIn("too short", r.json()["message"].lower())

if __name__ == "__main__":
    unittest.main()
