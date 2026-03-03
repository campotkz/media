@echo off
echo [1/5] Copying web assets...
copy ..\index.html www\index.html /y
copy ..\timer.html www\timer.html /y
copy ..\favicon.png www\favicon.png /y

echo [2/5] Capacitor Sync...
call npx cap sync android

echo [3/5] Building APK (Gradle) using Java 21...
set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
cd android
call gradlew.bat clean assembleDebug
cd ..

echo [4/5] Exporting APK to root folder...
copy android\app\build\outputs\apk\debug\campot-debug.apk ..\Campot_v1.apk /y

echo [5/5] Done! APK is available at e:\Campot\Campot_v1.apk
pause
