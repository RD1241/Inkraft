-- 003_gallery_columns.sql
-- Migration to add gallery sharing and featuring columns to the comics table.

ALTER TABLE comics ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT false;
ALTER TABLE comics ADD COLUMN IF NOT EXISTS is_featured BOOLEAN DEFAULT false;
