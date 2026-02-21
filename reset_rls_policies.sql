-- 1. Ensure columns exist (just in case)
ALTER TABLE clients ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT false;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS chat_id BIGINT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'media';
ALTER TABLE clients ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT false;

-- 2. Drop all possibly conflicting policies
DROP POLICY IF EXISTS "Enable read access for all users" ON public.clients;
DROP POLICY IF EXISTS "Enable insert for all users" ON public.clients;
DROP POLICY IF EXISTS "Enable update for all users" ON public.clients;
DROP POLICY IF EXISTS "Enable all access for all users" ON public.clients;

-- 3. Create fresh, most permissive policies for the 'anon' role (public access)
-- Note: 'USING (true)' and 'WITH CHECK (true)' ensure all rows are accessible and updatable
CREATE POLICY "Public Read" ON public.clients FOR SELECT TO anon USING (true);
CREATE POLICY "Public Insert" ON public.clients FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Public Update" ON public.clients FOR UPDATE TO anon USING (true) WITH CHECK (true);

-- 4. Enable RLS (just to be sure)
ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;
