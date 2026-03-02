import os
import sys
import io
import time
from datetime import datetime

# You must install requirements before running:
# pip install -r requirements.txt

try:
    from supabase import create_client, Client
    from PIL import Image
except ImportError:
    print("❌ Не установлены нужные библиотеки. Запустите: pip install supabase Pillow")
    sys.exit(1)

# --- НАСТРОЙКИ ---
# ВАЖНО: Вставьте сюда свои реальные ключи от Supabase,
# либо установите их как переменные окружения (set SUPABASE_URL=...) перед запуском.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "ВСТАВЬТЕ_СЮДА_ВАШ_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "ВСТАВЬТЕ_СЮДА_ВАШ_SERVICE_ROLE_KEY")

BUCKET_NAME = "casting_media"
FOLDER_PREFIX = "photos"  # Ищем фото только в папке photos
MAX_SIZE_PX = 800         # Максимальный размер по длинной стороне
JPEG_QUALITY = 65         # Качество сжатия (0-100, 65 - хорошее соотношение вес/качество)

def get_supabase_client() -> Client:
    if "ВСТАВЬТЕ_СЮДА" in SUPABASE_URL:
        # Попытка вытащить ключи из api/index.py если они там захардкожены (для удобства)
        try:
            import re
            with open('api/index.py', 'r', encoding='utf-8') as f:
                content = f.read()
                url_m = re.search(r'SUPABASE_URL\s*=\s*(?:"|\')(.*?)(?:"|\')', content)
                key_m = re.search(r'SUPABASE_KEY\s*=\s*(?:"|\')(.*?)(?:"|\')', content)
                if url_m and key_m:
                    return create_client(url_m.group(1), key_m.group(1))
        except Exception as e:
            print(f"Не удалось прочитать ключи из api/index.py: {e}")

        print("❌ Пожалуйста, откройте этот файл (api/optimize_storage.py) и вставьте ваши SUPABASE_URL и SUPABASE_KEY!")
        sys.exit(1)

    return create_client(SUPABASE_URL, SUPABASE_KEY)

def optimize_image(image_bytes: bytes) -> bytes:
    """Сжимает изображение с помощью Pillow и возвращает байты JPEG."""
    img = Image.open(io.BytesIO(image_bytes))

    # Конвертируем в RGB если формат RGBA (PNG с прозрачностью)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Уменьшаем размер если нужно
    img.thumbnail((MAX_SIZE_PX, MAX_SIZE_PX), Image.Resampling.LANCZOS)

    # Сохраняем в память
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return output.getvalue()

def process_files():
    supabase = get_supabase_client()
    print(f"🔄 Подключение к Supabase успешно. Проверяем бакет '{BUCKET_NAME}'...")

    try:
        # Получаем список файлов в папке (до 1000 за раз)
        # В Supabase list_files принимает path. Если пусто, то корнем
        files_res = supabase.storage.from_(BUCKET_NAME).list(FOLDER_PREFIX)

        if not files_res:
            print("📂 В папке photos/ пусто или папка не найдена.")
            return

        image_files = [f for f in files_res if f['name'] != '.emptyFolderPlaceholder' and not f['name'].startswith('.')]
        total_files = len(image_files)
        print(f"📸 Найдено файлов для проверки: {total_files}")

        optimized_count = 0
        skipped_count = 0
        error_count = 0
        saved_bytes = 0

        for i, file_obj in enumerate(image_files, 1):
            file_name = file_obj['name']
            file_path = f"{FOLDER_PREFIX}/{file_name}"

            # Проверяем размер. Если файл уже меньше ~150 КБ, скорее всего он уже сжат.
            # Можно пропустить для ускорения, или сжимать всё подряд.
            original_size = file_obj['metadata']['size']

            if original_size < 100 * 1024: # 100 KB
                print(f"[{i}/{total_files}] ⏭️ Пропуск {file_name} (уже легкий: {original_size/1024:.1f} KB)")
                skipped_count += 1
                continue

            print(f"[{i}/{total_files}] ⏳ Скачивание {file_name} ({original_size/1024/1024:.2f} MB)...")

            try:
                # 1. Скачиваем файл
                download_res = supabase.storage.from_(BUCKET_NAME).download(file_path)

                # 2. Сжимаем
                optimized_bytes = optimize_image(download_res)
                new_size = len(optimized_bytes)

                # 3. Если сжатие дало профит хотя бы на 10%
                if new_size < original_size * 0.9:
                    # ВАЖНО: Используем fileOptions upsert=True, чтобы перезаписать старый файл
                    # MIME-тип ставим image/jpeg, так как мы конвертировали всё в JPG
                    supabase.storage.from_(BUCKET_NAME).upload(
                        file_path,
                        optimized_bytes,
                        file_options={"cacheControl": "3600", "upsert": "true", "contentType": "image/jpeg"}
                    )

                    diff = original_size - new_size
                    saved_bytes += diff
                    optimized_count += 1
                    print(f"  ✅ Сжато! Новый размер: {new_size/1024:.1f} KB (Сэкономили: {diff/1024/1024:.2f} MB)")
                else:
                    print(f"  ➖ Пропуск (сжатие не дало выигрыша, старый {original_size/1024:.1f}KB, новый {new_size/1024:.1f}KB)")
                    skipped_count += 1

            except Exception as e:
                print(f"  ❌ Ошибка обработки {file_name}: {e}")
                error_count += 1

            # Небольшая пауза, чтобы не дудосить API
            time.sleep(0.5)

        print("\n" + "="*40)
        print("🎉 ОПТИМИЗАЦИЯ ЗАВЕРШЕНА!")
        print(f"Всего проверено: {total_files}")
        print(f"Сжато файлов: {optimized_count}")
        print(f"Пропущено: {skipped_count}")
        print(f"Ошибок: {error_count}")
        print(f"🔥 Освобождено места: {saved_bytes / 1024 / 1024:.2f} MB")
        print("="*40)

    except Exception as e:
        print(f"❌ Критическая ошибка при работе со Storage: {e}")

if __name__ == "__main__":
    process_files()
