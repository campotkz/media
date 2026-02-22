-- Create table for storing links from Telegram topics
CREATE TABLE IF NOT EXISTS public.project_resources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    chat_id BIGINT NOT NULL,
    thread_id BIGINT, -- Can be NULL for main chat
    url TEXT NOT NULL,
    title TEXT,
    message_id BIGINT,
    username TEXT,
    
    -- Constraint: Avoid duplicate links in the same topic
    UNIQUE(chat_id, thread_id, url)
);

-- Enable RLS
ALTER TABLE public.project_resources ENABLE ROW LEVEL SECURITY;

-- Allow public read (for the Web App)
CREATE POLICY "Allow public read" ON public.project_resources FOR SELECT USING (true);

-- Allow bot/public insert
CREATE POLICY "Allow public insert" ON public.project_resources FOR INSERT WITH CHECK (true);

COMMENT ON TABLE public.project_resources IS 'Storage for links shared in project Telegram topics (Resources, Docs, etc.)';
