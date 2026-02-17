-- Create tasks table
create table public.tasks (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  title text not null,
  description text,
  assignee_ids text[], -- Array of Telegram IDs or Names
  project_id text, -- Link to thread_id if related to a project
  deadline date,
  status text default 'pending', -- 'pending', 'done'
  bg_color text default '#FF9F0A' -- Orange for tasks by default
);

-- Note: We store assignee_ids as simple text array for flexibility first.
-- Enable RLS (if needed later, keeping open for now)
alter table public.tasks enable row level security;

create policy "Enable all access for now" on public.tasks
for all using (true) with check (true);
