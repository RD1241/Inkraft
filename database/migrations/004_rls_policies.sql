-- 004_rls_policies.sql
-- Migration to set up proper Row Level Security (RLS) policies on Supabase.

-- Enable RLS on newly created tables
ALTER TABLE credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE comics ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------
-- 1. Comics Policies
-- ---------------------------------------------------------
-- Users can only do operations on their own comics (except read public ones)
CREATE POLICY "users_own_comics" ON comics
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "public_comics_readable" ON comics
  FOR SELECT USING (is_public = true);

-- ---------------------------------------------------------
-- 2. Jobs Policies (Update to limit to logged-in user)
-- ---------------------------------------------------------
-- Drop old lax policies if they exist, and enforce user-owned locks
DROP POLICY IF EXISTS "Allow public select on jobs" ON jobs;
DROP POLICY IF EXISTS "Allow public insert on jobs" ON jobs;
DROP POLICY IF EXISTS "Allow public update on jobs" ON jobs;
DROP POLICY IF EXISTS "Allow public delete on jobs" ON jobs;

-- Add column user_id to jobs if it doesn't exist to bind auth context
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_id UUID;

CREATE POLICY "users_own_jobs" ON jobs
  FOR ALL USING (auth.uid() = user_id);

-- ---------------------------------------------------------
-- 3. Credits Policies
-- ---------------------------------------------------------
CREATE POLICY "users_own_credits" ON credits
  FOR ALL USING (auth.uid() = user_id);

-- ---------------------------------------------------------
-- 4. Credit Transactions Policies
-- ---------------------------------------------------------
CREATE POLICY "users_own_credit_transactions" ON credit_transactions
  FOR ALL USING (auth.uid() = user_id);

-- ---------------------------------------------------------
-- 5. Panels Policies
-- ---------------------------------------------------------
-- Users can only see panels belonging to their own comics/jobs
DROP POLICY IF EXISTS "Allow public select on panels" ON panels;
DROP POLICY IF EXISTS "Allow public insert on panels" ON panels;
DROP POLICY IF EXISTS "Allow public update on panels" ON panels;
DROP POLICY IF EXISTS "Allow public delete on panels" ON panels;

CREATE POLICY "users_own_panels" ON panels
  FOR ALL USING (
    job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid())
  );
