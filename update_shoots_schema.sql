-- SQL to expand shoots table for new fields
ALTER TABLE public.shoots 
ADD COLUMN IF NOT EXISTS post_production text,
ADD COLUMN IF NOT EXISTS casting_project text,
ADD COLUMN IF NOT EXISTS actors text;
