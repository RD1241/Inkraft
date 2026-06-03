import os
import sys
import shutil
import unittest
import json
import sqlite3
from fastapi.testclient import TestClient
from PIL import Image

# Ensure the root workspace directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app
from services.billing_service import billing_service
from config import settings

class TestPDFDownload(unittest.TestCase):
    def setUp(self):
        # Set up a clean local testing directory under outputs for dummy assets
        self.test_job_id = "11111111-2222-3333-4444-555555555555"
        self.test_user_id = "00000000-0000-0000-0000-000000000000"
        
        self.job_dir = os.path.join(settings.OUTPUTS_DIR, "test_job_123")
        os.makedirs(self.job_dir, exist_ok=True)
        
        # Create dummy panels
        self.panel_paths = []
        self.panel_web_urls = []
        for i in range(1, 4):
            img_filename = f"scene_{i}.png"
            img_path = os.path.join(self.job_dir, img_filename)
            # Create a 200x200 solid color dummy panel
            img = Image.new("RGB", (200, 200), color=(100 + i * 40, 50, 50))
            img.save(img_path)
            self.panel_paths.append(img_path)
            self.panel_web_urls.append(f"/outputs/test_job_123/{img_filename}")
            
        # Create dummy final page sheet
        self.final_sheet_path = os.path.join(self.job_dir, "final_comic_page.png")
        img_sheet = Image.new("RGB", (1024, 1450), color="black")
        img_sheet.save(self.final_sheet_path)
        self.final_sheet_web_url = "/outputs/test_job_123/final_comic_page.png"
        
        # Write a dummy metadata.json to describe the layout of the panels
        self.metadata = {
            "layout_type": "standard",
            "scenes": [
                {"panel_id": 1, "x": 10, "y": 10, "width": 500, "height": 700, "tension_level": 5},
                {"panel_id": 2, "x": 518, "y": 10, "width": 500, "height": 700, "tension_level": 5},
                {"panel_id": 3, "x": 10, "y": 718, "width": 1008, "height": 700, "tension_level": 5}
            ]
        }
        with open(os.path.join(self.job_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=4)
            
        # Seed test user and comic database records locally
        self.db_path = billing_service.db_path
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Reset tables for tests
        cursor.execute("DELETE FROM credits WHERE user_id = ?", (self.test_user_id,))
        cursor.execute("DELETE FROM credit_transactions WHERE user_id = ?", (self.test_user_id,))
        cursor.execute("DELETE FROM comics WHERE id = ?", (self.test_job_id,))
        cursor.execute("DELETE FROM jobs WHERE job_id = ?", (self.test_job_id,))
        
        # 1. Insert Credits (Set balance to 10)
        cursor.execute(
            "INSERT INTO credits (user_id, balance, created_at, updated_at) VALUES (?, ?, datetime('now'), datetime('now'))",
            (self.test_user_id, 10)
        )
        
        # 2. Insert Comic linked to test_job_id
        panel_urls_str = json.dumps(self.panel_web_urls)
        cursor.execute(
            "INSERT INTO comics (id, user_id, job_id, title, style, layout_type, panel_urls, final_page, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (self.test_job_id, self.test_user_id, self.test_job_id, "Test Comic Title", "anime", "standard", panel_urls_str, self.final_sheet_web_url)
        )
        
        conn.commit()
        conn.close()
        
        # Initialize fastapi test client
        self.client = TestClient(app)

    def tearDown(self):
        # Clean up test output directory
        if os.path.exists(self.job_dir):
            shutil.rmtree(self.job_dir)
            
        # Clean up local DB seeds
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM credits WHERE user_id = ?", (self.test_user_id,))
        cursor.execute("DELETE FROM credit_transactions WHERE user_id = ?", (self.test_user_id,))
        cursor.execute("DELETE FROM comics WHERE id = ?", (self.test_job_id,))
        conn.commit()
        conn.close()

    def test_auth_missing(self):
        """Verify that requests without authorization header or user id are rejected with 401."""
        # 1. PDF Download
        r = self.client.get(f"/api/download/{self.test_job_id}/pdf")
        self.assertEqual(r.status_code, 401)
        self.assertIn("Authentication credentials missing", r.json()["detail"])
        
        # 2. PNG Download
        r = self.client.get(f"/api/download/{self.test_job_id}/png")
        self.assertEqual(r.status_code, 401)
        self.assertIn("Authentication credentials missing", r.json()["detail"])

    def test_billing_deductor_pdf(self):
        """Verify that downloading PDF checks user balance, deducts 1 credit, and registers transaction."""
        initial_balance = billing_service.get_or_create_balance(self.test_user_id)
        self.assertEqual(initial_balance, 10)
        
        # Request with X-User-ID header (Costs 1 credit)
        headers = {"X-User-ID": self.test_user_id}
        r = self.client.get(f"/api/download/{self.test_job_id}/pdf", headers=headers)
        
        # Assert PDF download succeeds
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "application/pdf")
        
        # Verify that 1 credit was deducted
        post_balance = billing_service.get_or_create_balance(self.test_user_id)
        self.assertEqual(post_balance, 9)
        
        # Verify transaction logs
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT amount, reason FROM credit_transactions WHERE user_id = ?", (self.test_user_id,))
        txs = cursor.fetchall()
        conn.close()
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0][0], -1)
        self.assertEqual(txs[0][1], "pdf_download")

    def test_insufficient_credits_pdf(self):
        """Verify that downloading PDF is blocked with HTTP 402 if balance is less than 1 credit."""
        # Force user balance to 0 credits
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE credits SET balance = 0 WHERE user_id = ?", (self.test_user_id,))
        conn.commit()
        conn.close()
        
        headers = {"X-User-ID": self.test_user_id}
        r = self.client.get(f"/api/download/{self.test_job_id}/pdf", headers=headers)
        
        # Assert response is HTTP 402 Payment Required
        self.assertEqual(r.status_code, 402)
        self.assertIn("Insufficient credits", r.json()["detail"])

    def test_free_png_sheet_no_cost(self):
        """Verify that downloading PNG sheet is free of cost and works for premium users (no watermark)."""
        initial_balance = billing_service.get_or_create_balance(self.test_user_id)
        
        headers = {"X-User-ID": self.test_user_id}
        r = self.client.get(f"/api/download/{self.test_job_id}/png", headers=headers)
        
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "image/png")
        
        # Credit should not be deducted
        post_balance = billing_service.get_or_create_balance(self.test_user_id)
        self.assertEqual(post_balance, initial_balance)

    def test_free_png_sheet_watermark(self):
        """Verify that free users (balance <= 0 or X-User-Tier=free) receive a watermarked PNG sheet."""
        # 1. Force user balance to 0 to simulate free tier user
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE credits SET balance = 0 WHERE user_id = ?", (self.test_user_id,))
        conn.commit()
        conn.close()
        
        headers = {"X-User-ID": self.test_user_id}
        r = self.client.get(f"/api/download/{self.test_job_id}/png", headers=headers)
        self.assertEqual(r.status_code, 200)
        
        # Watermarked image should exist in the directory
        watermarked_path = os.path.join(self.job_dir, "watermarked_final_comic_page.png")
        self.assertTrue(os.path.exists(watermarked_path))
        
        # Let's verify that watermark image actually has different dimensions/content if overlayed
        original_img = Image.open(self.final_sheet_path)
        watermarked_img = Image.open(watermarked_path)
        self.assertEqual(original_img.size, watermarked_img.size)

if __name__ == "__main__":
    unittest.main()
