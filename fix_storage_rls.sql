-- SQL to fix Row Level Security (RLS) for the casting_media bucket
-- This allows anyone (anonymous users) to upload and view files in this bucket

-- 1. Enable RLS on the storage.objects table (usually enabled)
-- 2. Create policy to allow public inserts (uploads)
CREATE POLICY "Allow public uploads to casting_media"
ON storage.objects
FOR INSERT
WITH CHECK (
  bucket_id = 'casting_media'
);

-- 3. Create policy to allow public viewing (reading)
CREATE POLICY "Allow public reading from casting_media"
ON storage.objects
FOR SELECT
USING (
  bucket_id = 'casting_media'
);

-- 4. Create policy to allow public updates (optional but helpful for overwriting)
CREATE POLICY "Allow public updates to casting_media"
ON storage.objects
FOR UPDATE
USING (
  bucket_id = 'casting_media'
);

-- Note: Ensure the 'casting_media' bucket is created and set to "Public" in the Supabase UI as well.
