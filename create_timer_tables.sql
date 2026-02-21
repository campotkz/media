-- 1. Shifts Table
CREATE TABLE IF NOT EXISTS public.production_shifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id BIGINT REFERENCES public.clients(id),
    chat_id BIGINT,
    thread_id BIGINT,
    start_time TIMESTAMPTZ DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    status TEXT DEFAULT 'active', -- 'active', 'finished'
    director_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Logs Table
CREATE TABLE IF NOT EXISTS public.production_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shift_id UUID REFERENCES public.production_shifts(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- 'checkin', 'prep', 'rehearsal', 'motor', 'stop', 'take', 'lunch', 'move', 'delay', 'note'
    event_time TIMESTAMPTZ DEFAULT NOW(),
    data JSONB DEFAULT '{}'::jsonb, -- dynamic data like {dept: 'light', actor: 'Ivan', take_no: 1, is_good: true}
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Enable RLS
ALTER TABLE public.production_shifts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.production_logs ENABLE ROW LEVEL SECURITY;

-- 4. Public Access Policies (Prototyping)
DROP POLICY IF EXISTS "Public Select Shifts" ON public.production_shifts;
DROP POLICY IF EXISTS "Public Insert Shifts" ON public.production_shifts;
DROP POLICY IF EXISTS "Public Update Shifts" ON public.production_shifts;

CREATE POLICY "Public Select Shifts" ON public.production_shifts FOR SELECT TO anon USING (true);
CREATE POLICY "Public Insert Shifts" ON public.production_shifts FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Public Update Shifts" ON public.production_shifts FOR UPDATE TO anon USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Public Select Logs" ON public.production_logs;
DROP POLICY IF EXISTS "Public Insert Logs" ON public.production_logs;

CREATE POLICY "Public Select Logs" ON public.production_logs FOR SELECT TO anon USING (true);
CREATE POLICY "Public Insert Logs" ON public.production_logs FOR INSERT TO anon WITH CHECK (true);
