-- ИСПРАВЛЕНИЕ ТИПОВ ДАННЫХ ДЛЯ ТАЙМЕРА
-- Если при запуске выдает "invalid input syntax for type bigint: тест"
-- Выполни этот код в Supabase SQL Editor

-- 1. Меняем project_id на TEXT (чтобы принимал названия проектов)
ALTER TABLE public.production_shifts 
ALTER COLUMN project_id TYPE TEXT;

-- 2. Меняем chat_id и thread_id на TEXT (на всякий случай, для гибкости)
ALTER TABLE public.production_shifts 
ALTER COLUMN chat_id TYPE TEXT;

ALTER TABLE public.production_shifts 
ALTER COLUMN thread_id TYPE TEXT;

-- 3. Убеждаемся, что индексы на месте
CREATE INDEX IF NOT EXISTS idx_shifts_project_id ON public.production_shifts(project_id);

COMMENT ON COLUMN public.production_shifts.project_id IS 'ID проекта или его название (принимает текст)';
