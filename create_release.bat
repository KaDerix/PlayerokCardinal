@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================
echo   Creating Playerok Cardinal Release
echo ============================================
echo.

cd /d "%~dp0"

if not exist "main.py" (
    echo [ERROR] main.py not found. Run this script from the project folder.
    pause
    exit /b 1
)

set "VERSION="
for /f "tokens=3" %%V in ('findstr /B /C:"VERSION = " main.py') do set "VERSION=%%~V"

if not defined VERSION (
    echo [ERROR] Failed to get version from main.py
    echo         Make sure main.py contains: VERSION = "1.0.0"
    pause
    exit /b 1
)

echo [OK] Version: %VERSION%
echo.

set "MISSING="
where git >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Git is not installed or not in PATH.
    echo           Download: https://git-scm.com/download/win
    echo           Archive will still be created without git.
    echo.
    set "MISSING=1"
) else (
    if not exist ".git" (
        echo [INFO] Initializing git repository...
        git init
        if errorlevel 1 (
            echo [ERROR] git init failed
            pause
            exit /b 1
        )
        echo [OK] Git repository initialized
        echo.
        echo [WARNING] Configure remote repository:
        echo    git remote add origin https://github.com/KITUSTTT/PlayerokCardinal.git
        echo.
    )

    git remote get-url origin >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] No git remote configured. Add one, for example:
        echo    git remote add origin https://github.com/KITUSTTT/PlayerokCardinal.git
        echo.
    )
)

set "ARCHIVE=PlayerokCardinal-v%VERSION%.zip"
if exist "%ARCHIVE%" del /f "%ARCHIVE%"

echo [INFO] Creating archive %ARCHIVE% ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\pack_release.ps1" -ArchiveName "%ARCHIVE%"
if errorlevel 1 (
    echo [ERROR] Failed to create archive
    pause
    exit /b 1
)

echo [OK] Archive created: %ARCHIVE%
echo.

if not defined MISSING (
    echo Next steps:
    echo   git add .
    echo   git commit -m "Release v%VERSION%"
    echo   git tag v%VERSION%
    echo   git push -u origin main --tags
    echo.
)

pause
