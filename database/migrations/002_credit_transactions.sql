-- 002_credit_transactions.sql
-- Migration to set up the Credits system tables and the Comics history tables.

-- ---------------------------------------------------------
-- 1. Credits Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS credits (
    user_id UUID PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 10,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ---------------------------------------------------------
-- 2. Credit Transactions Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS credit_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    amount INTEGER NOT NULL, -- positive=add, negative=deduct
    reason TEXT NOT NULL, -- "new_user_bonus", "generation", "refund", "purchase"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ---------------------------------------------------------
-- 3. Comics Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS comics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    style TEXT NOT NULL DEFAULT 'anime',
    layout_type TEXT DEFAULT 'standard',
    panel_count INTEGER,
    panel_count_mode TEXT DEFAULT 'ai_decided',
    panel_urls JSONB DEFAULT '[]'::jsonb, -- list of individual panel URLs
    final_page TEXT, -- URL to stitched final page
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
