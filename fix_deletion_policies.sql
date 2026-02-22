-- Add missing DELETE policies for tables managed by the bot

-- 1. Contacts (Actors)
DROP POLICY IF EXISTS "Enable delete for all users" ON public.contacts;
CREATE POLICY "Enable delete for all users" ON public.contacts
  FOR DELETE USING (true);

-- 2. Project Resources (Links)
DROP POLICY IF EXISTS "Allow public delete" ON public.project_resources;
CREATE POLICY "Allow public delete" ON public.project_resources
  FOR DELETE USING (true);

-- 3. Project Locations (Ensure it's there)
DROP POLICY IF EXISTS "Enable delete for all users" ON public.project_locations;
CREATE POLICY "Enable delete for all users" ON public.project_locations
  FOR DELETE USING (true);

-- Also ensure public UPDATE is available for all if not already
DROP POLICY IF EXISTS "Enable update for all users" ON public.contacts;
CREATE POLICY "Enable update for all users" ON public.contacts
  FOR UPDATE USING (true);

DROP POLICY IF EXISTS "Allow public update" ON public.project_resources;
CREATE POLICY "Allow public update" ON public.project_resources
  FOR UPDATE USING (true);
