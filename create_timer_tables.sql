-- ============================================================
-- ТАБЛИЦЫ ДЛЯ ТАЙМЕРА / ХЛОПУШКИ (Film Timer PRO)
-- Вставь этот код в Supabase → SQL Editor → Run
-- ============================================================

-- 1. ТАБЛИЦА СМЕН (production_shifts)
-- Хранит каждую начатую смену с временем старта/финиша
CREATE TABLE IF NOT EXISTS public.production_shifts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id TEXT,                    -- ID проекта (PID из Telegram)
    chat_id TEXT,                       -- ID чата Telegram
    thread_id TEXT,                     -- ID топика Telegram
    shoot_id TEXT,                      -- Связь с таблицей shoots (календарь)
    start_time TIMESTAMPTZ NOT NULL,    -- Время начала смены
    end_time TIMESTAMPTZ,              -- Время конца смены (NULL пока идёт)
    status TEXT DEFAULT 'active',       -- active / finished
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.production_shifts IS 'Записи смен из Film Timer PRO';

-- 2. ТАБЛИЦА СОБЫТИЙ (production_logs)
-- Хранит ВСЕ события: старт/стоп таймеров, моторы, дубли, задержки и т.д.
CREATE TABLE IF NOT EXISTS public.production_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    shift_id UUID REFERENCES public.production_shifts(id),  -- К какой смене
    event_type TEXT NOT NULL,           -- Тип события (motor_start, light_end, delay_tech_start...)
    data JSONB DEFAULT '{}',           -- Доп. данные (scene, shot, take, duration, reason...)
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.production_logs IS 'Лог всех событий таймера: моторы, таймеры, задержки, оценки';

-- 3. ИНДЕКСЫ для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_shifts_project ON public.production_shifts(project_id);
CREATE INDEX IF NOT EXISTS idx_shifts_date ON public.production_shifts(created_at);
CREATE INDEX IF NOT EXISTS idx_logs_shift ON public.production_logs(shift_id);
CREATE INDEX IF NOT EXISTS idx_logs_type ON public.production_logs(event_type);

-- 4. RLS (Row Level Security) — РАЗРЕШИТЬ ВСЕ операции через anon key
-- Без этого вставка из фронтенда будет заблокирована!
ALTER TABLE public.production_shifts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.production_logs ENABLE ROW LEVEL SECURITY;

-- Политики: разрешить всё для anon (публичный ключ)
CREATE POLICY "Allow all for shifts" ON public.production_shifts
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all for logs" ON public.production_logs
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- ГОТОВО! После выполнения таймер сможет:
-- ✅ Создавать записи смен (production_shifts)
-- ✅ Логировать ВСЕ события (production_logs):
--    - shift_start / shift_finish
--    - motor_start / motor_stop
--    - light_start / light_end (+ duration, promised, delay)
--    - camera_start / camera_end
--    - makeup_start / makeup_end
--    - travel_start / travel_stop
--    - loc_move_start / loc_move_stop
--    - lunch_start / lunch_stop
--    - delay_tech_start / delay_tech_end (+ reason, resolution)
--    - actor_arrival / actor_departure / actor_ready
--    - crew_arrival / client_arrival
--    - take_evaluation (good/bad/tech)
--    - location_change
--    - note (memo)
--    - wrap / last_man_out
-- ============================================================
