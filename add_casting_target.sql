-- Добавляем пропущенную колонку в таблицу анкет
ALTER TABLE public.casting_applications 
ADD COLUMN IF NOT EXISTS casting_target TEXT;
