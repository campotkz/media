-- Add visibility and status columns to the projects table
ALTER TABLE clients ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT false;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT false;

-- Update existing projects: if they have a checkmark in the name, set is_active to true
UPDATE clients SET is_active = true WHERE name LIKE '%✅%';
