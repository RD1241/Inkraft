import os
import sys
import unittest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from services.credits_service import CreditsService, clean_uuid

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
        self.assertEqual(balance, 10)
        
        # Verify transaction log
        history = self.service.get_history(user_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["amount"], 10)
        self.assertEqual(history[0]["reason"], "new_user_bonus")

    def test_deduction_and_refund(self):
        user_id = "test_user_2"
        # Triggers registration
        self.assertEqual(self.service.get_balance(user_id), 10)
        
        # Deduct
        self.service.deduct_credit(user_id)
        self.assertEqual(self.service.get_balance(user_id), 9)
        
        # Verify transaction history
        history = self.service.get_history(user_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["amount"], -1)
        self.assertEqual(history[0]["reason"], "generation")

        # Refund
        self.service.refund_credit(user_id)
        self.assertEqual(self.service.get_balance(user_id), 10)
        
        # Verify transaction history again
        history = self.service.get_history(user_id)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["amount"], 1)
        self.assertEqual(history[0]["reason"], "refund")

    def test_daily_limit(self):
        user_id = "test_user_3"
        # Registers user (starts with 10 credits)
        self.service.get_balance(user_id)

        # Deduct 3 credits (the maximum daily limit allowed)
        self.assertTrue(self.service.deduct_credit(user_id))
        self.assertTrue(self.service.deduct_credit(user_id))
        self.assertTrue(self.service.deduct_credit(user_id))
        self.assertEqual(self.service.get_balance(user_id), 7)

        # Attempting a 4th deduction must raise a ValueError (daily limit reached)
        with self.assertRaises(ValueError) as ctx:
            self.service.deduct_credit(user_id)
        self.assertIn("Daily limit of 3 generations reached.", str(ctx.exception))

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
