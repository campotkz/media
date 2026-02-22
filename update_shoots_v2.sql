-- SQL to update shoots table with report_link and ensure schedule is TEXT
ALTER TABLE public.shoots 
ADD COLUMN IF NOT EXISTS report_link TEXT;

-- Ensure schedule can hold large JSON data
ALTER TABLE public.shoots 
ALTER COLUMN schedule TYPE TEXT;

COMMENT ON COLUMN public.shoots.report_link IS 'Link to the shift report (PDF/Excel/Timing App)';
COMMENT ON COLUMN public.shoots.schedule IS 'Structured timing plan stored as JSON string';
