-- Create contacts table
CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    telegram_id BIGINT,
    thread_id BIGINT NOT NULL REFERENCES clients(thread_id), -- Linked to project topic
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(phone, thread_id) -- Avoid duplicate phones in the same project
);

-- Enable RLS and public policies
ALTER TABLE public.contacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable read access for all users" ON public.contacts
    FOR SELECT USING (true);

CREATE POLICY "Enable insert for all users" ON public.contacts
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update for all users" ON public.contacts
    FOR UPDATE USING (true);
