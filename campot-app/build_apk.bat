@echo off
echo ==============================================
echo Копирование новых файлов из корневой папки...
echo ==============================================
copy /Y "e:\Campot\index.html" "e:\Campot\campot-app\www\"
copy /Y "e:\Campot\timer.html" "e:\Campot\campot-app\www\"
copy /Y "e:\Campot\favicon.png" "e:\Campot\campot-app\www\"

echo.
echo ==============================================
echo Перенос веб-файлов в проект Android (Capacitor)...
echo ==============================================
call npx cap copy android

echo.
echo ==============================================
echo Открытие Android Studio...
echo ==============================================
call npx cap open android
