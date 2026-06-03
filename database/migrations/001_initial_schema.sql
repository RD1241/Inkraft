-- 001_initial_schema.sql
-- Migration to set up initial schema for NovelToComic SaaS platform.

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------
-- 1. Jobs Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL DEFAULT 'queued',
    progress TEXT DEFAULT 'Waiting in queue...',
    result JSONB,
    error TEXT,
    novel_text TEXT NOT NULL,
    style TEXT DEFAULT 'anime',
    panel_count INTEGER,
    layout_type TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ---------------------------------------------------------
-- 2. Scenes Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS scenes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE NOT NULL,
    scene_id INTEGER NOT NULL,
    environment TEXT,
    focus_character TEXT,
    action TEXT,
    emotion TEXT,
    is_action BOOLEAN DEFAULT false,
    is_dialogue BOOLEAN DEFAULT false,
    is_calm BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ---------------------------------------------------------
-- 3. Characters Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS characters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id UUID REFERENCES scenes(id) ON DELETE CASCADE NOT NULL,
    name TEXT NOT NULL,
    character_role TEXT DEFAULT 'secondary_character',
    description TEXT,
    gender_tag TEXT,
    negative_gender TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ---------------------------------------------------------
-- 4. Dialogues Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS dialogues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id UUID REFERENCES scenes(id) ON DELETE CASCADE NOT NULL,
    speaker TEXT NOT NULL,
    type TEXT DEFAULT 'speech',
    text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ---------------------------------------------------------
-- 5. Panels Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS panels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE NOT NULL,
    scene_id UUID REFERENCES scenes(id) ON DELETE SET NULL,
    panel_index INTEGER NOT NULL,
    image_url TEXT,
    dialogue_text TEXT,
    config JSONB,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ---------------------------------------------------------
-- 6. Character Memories Table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS character_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ---------------------------------------------------------
-- Enable Row Level Security (RLS)
-- ---------------------------------------------------------
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE scenes ENABLE ROW LEVEL SECURITY;
ALTER TABLE characters ENABLE ROW LEVEL SECURITY;
ALTER TABLE dialogues ENABLE ROW LEVEL SECURITY;
ALTER TABLE panels ENABLE ROW LEVEL SECURITY;
ALTER TABLE character_memories ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------
-- RLS Policies
-- For local and SaaS flexibility, we allow standard access policies.
-- ---------------------------------------------------------

-- Jobs Policies
CREATE POLICY "Allow public select on jobs" ON jobs FOR SELECT USING (true);
CREATE POLICY "Allow public insert on jobs" ON jobs FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update on jobs" ON jobs FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "Allow public delete on jobs" ON jobs FOR DELETE USING (true);

-- Scenes Policies
CREATE POLICY "Allow public select on scenes" ON scenes FOR SELECT USING (true);
CREATE POLICY "Allow public insert on scenes" ON scenes FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update on scenes" ON scenes FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "Allow public delete on scenes" ON scenes FOR DELETE USING (true);

-- Characters Policies
CREATE POLICY "Allow public select on characters" ON characters FOR SELECT USING (true);
CREATE POLICY "Allow public insert on characters" ON characters FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update on characters" ON characters FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "Allow public delete on characters" ON characters FOR DELETE USING (true);

-- Dialogues Policies
CREATE POLICY "Allow public select on dialogues" ON dialogues FOR SELECT USING (true);
CREATE POLICY "Allow public insert on dialogues" ON dialogues FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update on dialogues" ON dialogues FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "Allow public delete on dialogues" ON dialogues FOR DELETE USING (true);

-- Panels Policies
CREATE POLICY "Allow public select on panels" ON panels FOR SELECT USING (true);
CREATE POLICY "Allow public insert on panels" ON panels FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update on panels" ON panels FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "Allow public delete on panels" ON panels FOR DELETE USING (true);

-- Character Memories Policies
CREATE POLICY "Allow public select on character_memories" ON character_memories FOR SELECT USING (true);
CREATE POLICY "Allow public insert on character_memories" ON character_memories FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update on character_memories" ON character_memories FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "Allow public delete on character_memories" ON character_memories FOR DELETE USING (true);
