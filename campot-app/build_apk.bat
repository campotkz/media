@echo off
echo [1/6] Copying web assets...
copy ..\index.html www\index.html /y
copy ..\timer.html www\timer.html /y
copy ..\favicon.png www\favicon.png /y

echo [2/6] Generating App Icons...
if exist "assets\icon.png" (
    echo [INFO] Updating icons from assets folder...
    call npx @capacitor/assets generate --android
) else (
    echo [WARN] assets folder not configured, skipping icon update.
)

echo [3/6] Capacitor Sync...
call npx cap sync android

echo [4/6] Building APK (Gradle) using Java 21...
set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
set "PATH=%JAVA_HOME%\bin;%PATH%"
cd android
echo [INFO] Stopping old Gradle daemons...
call gradlew.bat --stop
echo [INFO] Starting build...
call gradlew.bat clean assembleDebug --stacktrace
cd ..

echo [5/6] Exporting APK to root folder...
if exist "android\app\build\outputs\apk\debug\campot-debug.apk" (
    copy android\app\build\outputs\apk\debug\campot-debug.apk ..\Campot_v1.apk /y
    copy android\app\build\outputs\apk\debug\campot-debug.apk ..\Campot_v2_OFFLINE.apk /y
    echo [SUCCESS] APK exported to e:\Campot\Campot_v1.apk and Campot_v2_OFFLINE.apk
) else (
    echo [ERROR] APK not found! Build probably failed. Check logs above.
)

echo [6/6] Done!

