-- Добавить колонку gear в таблицу shoots для хранения JSON-данных техники
ALTER TABLE public.shoots 
ADD COLUMN IF NOT EXISTS gear TEXT;

COMMENT ON COLUMN public.shoots.gear IS 'Structured equipment data stored as JSON string (camera, optics, light, sound)';
