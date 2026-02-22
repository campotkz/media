-- ИСПРАВЛЕНИЕ ТИПОВ ДАННЫХ ДЛЯ ТАЙМЕРА (С УЧЕТОМ СВЯЗЕЙ)
-- Если Supabase ругается на "foreign key constraint", используй этот скрипт

-- 1. Удаляем внешнюю связь, которая мешает изменить тип (если она есть)
ALTER TABLE public.production_shifts 
DROP CONSTRAINT IF EXISTS production_shifts_project_id_fkey;

-- 2. Меняем project_id на TEXT (чтобы принимал названия проектов)
ALTER TABLE public.production_shifts 
ALTER COLUMN project_id TYPE TEXT;

-- 3. Меняем chat_id и thread_id на TEXT (на всякий случай)
ALTER TABLE public.production_shifts 
ALTER COLUMN chat_id TYPE TEXT,
ALTER COLUMN thread_id TYPE TEXT;

-- 4. Пересоздаем индекс для скорости поиска
DROP INDEX IF EXISTS idx_shifts_project;
CREATE INDEX IF NOT EXISTS idx_shifts_project ON public.production_shifts(project_id);

COMMENT ON COLUMN public.production_shifts.project_id IS 'ID проекта или его название (принимает текст)';
