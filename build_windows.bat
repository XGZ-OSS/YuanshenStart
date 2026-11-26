@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title YuanshenStart Windows EXE Builder
echo ===================================================
echo   YuanshenStart - Windows EXE Builder
echo ===================================================
echo.
echo Build script uses ASCII only to avoid CMD encoding errors.
echo.

py -3.14 --version >nul 2>&1
if errorlevel 1 goto no_python

if not exist "app.py" goto missing_files
if not exist "logo.png" goto missing_files
if not exist "app.ico" goto missing_files

echo [1/3] Installing PyInstaller...
py -3.14 -m pip --version >nul 2>&1
if errorlevel 1 py -3.14 -m ensurepip --upgrade
py -3.14 -m pip install "pyinstaller>=6.15,<7"
if errorlevel 1 goto build_failed

echo.
echo [2/3] Building one-file Windows EXE...
py -3.14 -m PyInstaller --noconfirm --clean --onefile --windowed --name "YuanshenStart" --icon "%CD%\app.ico" --add-data "%CD%\logo.png;." --distpath "%CD%\dist" --workpath "%CD%\build" "%CD%\app.py"
if errorlevel 1 goto build_failed
if not exist "dist\YuanshenStart.exe" goto build_failed

echo.
echo [3/3] Copying EXE into release folder...
if not exist "release" mkdir "release"
copy /y "dist\YuanshenStart.exe" "release\YuanshenStart.exe" >nul
if errorlevel 1 goto build_failed
if not exist "release\update_url.txt" if exist "update_url.txt" copy /y "update_url.txt" "release\update_url.txt" >nul

echo.
echo ===================================================
echo SUCCESS: release\YuanshenStart.exe
echo You can double-click this EXE without Python.
echo Data is stored in the per-user LocalAppData folder.
echo ===================================================
echo.
explorer "release"
pause
exit /b 0

:no_python
echo [ERROR] Python 3.14 was not found through the py launcher.
echo Install Python 3.14 for Windows, then run this BAT again.
pause
exit /b 1

:missing_files
echo [ERROR] app.py, logo.png, or app.ico is missing.
echo Extract the full ZIP before running this BAT.
pause
exit /b 1

:build_failed
echo.
echo [ERROR] Build failed. Please copy the messages above.
pause
exit /b 1
