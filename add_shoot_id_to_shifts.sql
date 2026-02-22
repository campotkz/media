-- Migration to link production_shifts to calendar shoots
ALTER TABLE public.production_shifts 
ADD COLUMN IF NOT EXISTS shoot_id TEXT; -- Storing as TEXT to match index.html's shoot IDs

COMMENT ON COLUMN public.production_shifts.shoot_id IS 'Link to the shoots table (Production Calendar Day)';
