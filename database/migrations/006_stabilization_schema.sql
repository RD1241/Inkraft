-- 006_stabilization_schema.sql
-- Migration to align Supabase PostgreSQL schemas with local SQLite schemas

-- ---------------------------------------------------------
-- 1. Align Jobs Table
-- ---------------------------------------------------------
-- Make novel_text nullable since SQLite does not store it
ALTER TABLE jobs ALTER COLUMN novel_text DROP NOT NULL;

-- Add missing columns to jobs table
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS panel_count_mode TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS generation_format TEXT;

-- ---------------------------------------------------------
-- 2. Create Character Design Sheets Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS character_design_sheets (
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    gender TEXT,
    age_range TEXT,
    hair_style TEXT,
    hair_color TEXT,
    eye_color TEXT,
    body_type TEXT,
    primary_outfit TEXT,
    distinguishing_features TEXT,
    personality_note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    PRIMARY KEY (user_id, name)
);

-- Enable Row Level Security (RLS)
ALTER TABLE character_design_sheets ENABLE ROW LEVEL SECURITY;

-- Set up RLS Policies
CREATE POLICY "users_own_character_design_sheets" ON character_design_sheets
    FOR ALL USING (auth.uid() = user_id);

-- ---------------------------------------------------------
-- 3. Grant privileges
-- ---------------------------------------------------------
GRANT ALL ON character_design_sheets TO service_role;
GRANT ALL ON character_design_sheets TO postgres;
GRANT SELECT, INSERT, UPDATE, DELETE ON character_design_sheets TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON character_design_sheets TO anon;
