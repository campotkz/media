-- Add type, casting and actors fields to tasks table
alter table public.tasks 
add column if not exists type text default 'general',
add column if not exists casting_project text,
add column if not exists actors text;
