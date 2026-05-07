-- Create table for Telegram Whitelist
CREATE TABLE IF NOT EXISTS allowed_chats (
    chat_id BIGINT PRIMARY KEY,
    added_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Initial seeding (optional, but good for persistence)
-- Note: env variables will also be checked
INSERT INTO allowed_chats (chat_id, added_by) VALUES 
(-8534227633, 542053490),
(-195051697, 542053490),
(542053490, 542053490)
ON CONFLICT DO NOTHING;
