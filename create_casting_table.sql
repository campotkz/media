-- Create casting_applications table
CREATE TABLE IF NOT EXISTS casting_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id BIGINT,
    thread_id BIGINT,
    project_name TEXT,
    full_name TEXT NOT NULL,
    gender TEXT,
    city TEXT,
    dob DATE,
    nationality TEXT,
    phone TEXT,
    instagram TEXT,
    height_weight TEXT,
    sizes TEXT,
    experience TEXT,
    skills TEXT,
    fee_range TEXT,
    underwear_ok TEXT,
    extras_ok TEXT,
    photo_urls TEXT[], -- Array of Supabase Storage links
    video_audition_url TEXT,
    portfolio_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE casting_applications ENABLE ROW LEVEL SECURITY;

-- Allow public inserts
CREATE POLICY "Allow public inserts" ON casting_applications
FOR INSERT WITH CHECK (true);

-- Allow public selection (optional, for admin review)
CREATE POLICY "Allow public select" ON casting_applications
FOR SELECT USING (true);
