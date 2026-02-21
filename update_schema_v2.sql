-- 1. Add chat_id and category to clients (Projects)
ALTER TABLE clients ADD COLUMN IF NOT EXISTS chat_id BIGINT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'media'; -- 'media' or 'casting'

-- 2. Add chat_id and category to contacts
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS chat_id BIGINT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'media';

-- 3. Update constraints for isolation
-- Drop old unique constraint if it exists
ALTER TABLE contacts DROP CONSTRAINT IF EXISTS contacts_phone_thread_id_key;

-- Add new unique constraint including chat_id. 
-- This allows the same phone/thread combo in DIFFERENT groups, 
-- but prevents many entries in THE SAME group.
ALTER TABLE contacts ADD CONSTRAINT contacts_unique_phone_chat_thread UNIQUE(phone, chat_id, thread_id);
