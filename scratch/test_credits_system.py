import os
import sys
import unittest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from services.credits_service import CreditsService, clean_uuid
from config import settings

GRANT = settings.NEW_USER_CREDITS  # configured new-user starting credits

class TestCreditsSystem(unittest.TestCase):
    def setUp(self):
        # Create a temp database for testing
        self.test_db = os.path.join(os.path.dirname(__file__), "test_jobs.db")
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.service = CreditsService(db_path=self.test_db)
        self.service.supabase_enabled = False

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_clean_uuid(self):
        # Valid UUID
        val = "123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(clean_uuid(val), val)
        # Invalid UUID string
        val2 = "my_cool_user_id"
        cleaned2 = clean_uuid(val2)
        # Deterministic
        self.assertEqual(clean_uuid(val2), cleaned2)
        # Not empty and is valid UUID format
        self.assertTrue(len(cleaned2) > 0)

    def test_starting_credits(self):
        user_id = "test_user_1"
        balance = self.service.get_balance(user_id)
        self.assertEqual(balance, GRANT)

        # Verify transaction log
        history = self.service.get_history(user_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["amount"], GRANT)
        self.assertEqual(history[0]["reason"], "new_user_bonus")

    def test_deduction_and_refund(self):
        user_id = "test_user_2"
        # Triggers registration
        self.assertEqual(self.service.get_balance(user_id), GRANT)

        # Deduct
        self.service.deduct_credit(user_id)
        self.assertEqual(self.service.get_balance(user_id), GRANT - 1)

        # Verify transaction history
        history = self.service.get_history(user_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["amount"], -1)
        self.assertEqual(history[0]["reason"], "generation")

        # Refund
        self.service.refund_credit(user_id)
        self.assertEqual(self.service.get_balance(user_id), GRANT)

        # Verify transaction history again
        history = self.service.get_history(user_id)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["amount"], 1)
        self.assertEqual(history[0]["reason"], "refund")

    def test_tiered_pricing(self):
        # credits_for_panels: AI(None/0)=default; tiers 1-2=1, 3-4=2, 5-6=3.
        self.assertEqual(self.service.credits_for_panels(None), settings.CREDITS_AI_DEFAULT)
        self.assertEqual(self.service.credits_for_panels(1), 1)
        self.assertEqual(self.service.credits_for_panels(2), 1)
        self.assertEqual(self.service.credits_for_panels(3), 2)
        self.assertEqual(self.service.credits_for_panels(6), 3)
        # Above the top tier pays the top rate (no free overflow).
        self.assertEqual(self.service.credits_for_panels(99), settings.CREDIT_PANEL_TIERS[-1][1])

    def test_tiered_deduct_refund_amount(self):
        user_id = "test_user_tier"
        self.assertEqual(self.service.get_balance(user_id), GRANT)
        # A 6-panel comic costs 3 credits.
        self.service.deduct_credit(user_id, amount=self.service.credits_for_panels(6))
        self.assertEqual(self.service.get_balance(user_id), GRANT - 3)
        # Failure refunds the same 3 credits.
        self.service.refund_credit(user_id, amount=3)
        self.assertEqual(self.service.get_balance(user_id), GRANT)

    def test_deduction_limit(self):
        user_id = "test_user_3"
        # Registers user (starts with GRANT credits)
        self.service.get_balance(user_id)

        # Deduct all GRANT credits (1 at a time)
        for _ in range(GRANT):
            self.assertTrue(self.service.deduct_credit(user_id))
        self.assertEqual(self.service.get_balance(user_id), 0)

        # Attempting one more deduction must raise a ValueError (insufficient credits)
        with self.assertRaises(ValueError) as ctx:
            self.service.deduct_credit(user_id)
        self.assertIn("Insufficient credits", str(ctx.exception))

    def test_insufficient_credits(self):
        user_id = "test_user_4"
        # Registers user
        self.service.get_balance(user_id)

        # Explicitly modify SQLite balance to 0
        import sqlite3
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("UPDATE credits SET balance = 0 WHERE user_id = ?", (clean_uuid(user_id),))
        conn.commit()
        conn.close()

        # Deducting should fail with insufficient credits
        with self.assertRaises(ValueError) as ctx:
            self.service.deduct_credit(user_id)
        self.assertIn("Insufficient credits", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
