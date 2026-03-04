@echo off
echo [1/6] Copying web assets...
copy ..\index.html www\index.html /y
copy ..\timer.html www\timer.html /y
copy ..\favicon.png www\favicon.png /y

echo [2/6] Generating App Icons from campot.jpg...
if exist "..\campot.jpg" (
    echo [INFO] Found campot.jpg, updating icons...
    call npx -y @capacitor/assets generate --icon ..\campot.jpg --android
) else (
    echo [WARN] campot.jpg not found in root, skipping icon update.
)

echo [3/6] Capacitor Sync...
call npx cap sync android

echo [4/6] Building APK (Gradle) using Java 21...
set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
cd android
call gradlew.bat clean assembleDebug
cd ..

echo [5/6] Exporting APK to root folder...
copy android\app\build\outputs\apk\debug\campot-debug.apk ..\Campot_v1.apk /y

echo [6/6] Done! APK is available at e:\Campot\Campot_v1.apk
pause
