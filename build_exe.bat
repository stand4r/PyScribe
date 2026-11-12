@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ===================================================
echo PyScribe - Self-contained Windows Exe Build
echo ===================================================
echo.
echo Target executable will be windowless (no command prompt).
echo Python runtime and Qt dependencies will be bundled into dist\PyScribe\.
echo Target PC does NOT need Python installed.
echo.

python -c "import sys; print('Build Python:', sys.version)"
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    goto :fail
)

python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to verify or install PyInstaller.
    goto :fail
)

if not exist "src\PyScribe.ico" (
    echo [ERROR] src\PyScribe.ico not found.
    goto :fail
)

if not exist "PyScribe.spec" (
    echo [ERROR] PyScribe.spec not found.
    goto :fail
)

echo Cleaning previous build artifacts...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo.
echo Running PyInstaller with PyScribe.spec...
python -m PyInstaller --noconfirm --clean PyScribe.spec
if errorlevel 1 goto :fail

if not exist "dist\PyScribe\PyScribe.exe" (
    echo [ERROR] dist\PyScribe\PyScribe.exe was not created.
    goto :fail
)

echo.
echo ===================================================
echo BUILD SUCCESSFUL!
echo Output folder: %~dp0dist\PyScribe\
echo Executable:    %~dp0dist\PyScribe\PyScribe.exe
echo ===================================================
echo.
echo Next step: run installer\build_installer.bat to generate Inno Setup installer.
pause
exit /b 0

:fail
echo.
echo [ERROR] BUILD FAILED. Check console output above for details.
pause
exit /b 1
