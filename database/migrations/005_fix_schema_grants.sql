-- 005_fix_schema_grants.sql
-- Migration to grant essential schema-wide privileges to database roles.
-- This ensures that the PostgREST API (service_role, authenticated, and anon)
-- has the necessary permissions to access tables inside the public schema.

-- Grant all privileges on all tables/sequences in public schema to service_role and postgres
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Ensure authenticated and anon roles have access (required for RLS policies to evaluate)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO anon;
