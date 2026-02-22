-- Add Telegram identification columns to casting_applications
ALTER TABLE casting_applications ADD COLUMN IF NOT EXISTS tg_message_id BIGINT;
ALTER TABLE casting_applications ADD COLUMN IF NOT EXISTS additional_media JSONB DEFAULT '[]'::jsonb;
