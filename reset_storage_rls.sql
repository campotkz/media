-- Скрипт "Полного Сброса" для хранилища (Устранение ошибки Row Level Security)

-- 1. Удаляем старые политики, чтобы не было конфликтов
DROP POLICY IF EXISTS "Allow public uploads to casting_media" ON storage.objects;
DROP POLICY IF EXISTS "Allow public reading from casting_media" ON storage.objects;
DROP POLICY IF EXISTS "Allow public updates to casting_media" ON storage.objects;
DROP POLICY IF EXISTS "Allow public deletion from casting_media" ON storage.objects;

-- 2. Создаем новую универсальную политику "Доступ ко всему" для этого бакета
-- Это разрешит Анонимным пользователям (публике) загружать и смотреть файлы в casting_media
CREATE POLICY "Public Full Access casting_media"
ON storage.objects FOR ALL TO public
USING ( bucket_id = 'casting_media' )
WITH CHECK ( bucket_id = 'casting_media' );
