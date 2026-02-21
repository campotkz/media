-- Change dob column type from DATE to TEXT to allow numeric age inputs (e.g., "25")
ALTER TABLE public.casting_applications 
ALTER COLUMN dob TYPE TEXT;
