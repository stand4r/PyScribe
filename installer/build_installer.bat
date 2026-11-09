@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

if not exist "dist\PyScribe\PyScribe.exe" (
  echo dist\PyScribe\PyScribe.exe not found.
  echo First run build_exe.bat from the project root.
  pause
  exit /b 1
)

where ISCC.exe >nul 2>&1
if errorlevel 1 (
  if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
  ) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
  ) else (
    echo Inno Setup 6 was not found.
    echo Install Inno Setup and run this script again.
    pause
    exit /b 1
  )
) else (
  set "ISCC=ISCC.exe"
)


"%ISCC%" "installer\PyScribe.iss"
if errorlevel 1 (
  echo Installer build failed.
  pause
  exit /b 1
)

echo.
echo ========================================
echo Installer created:
set /p PYSCRIBE_VERSION=<VERSION
echo installer_output\PyScribe-Setup-v%PYSCRIBE_VERSION%.exe
echo ========================================
echo.
pause
