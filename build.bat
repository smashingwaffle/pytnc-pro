@echo off
REM ============================================================
REM PyTNC Pro - Windows Build Script
REM ============================================================
REM
REM Prerequisites:
REM   - Python 3.10+ installed
REM   - pip install pyinstaller
REM   - All dependencies from requirements.txt installed
REM
REM Usage: build.bat
REM
REM Output: dist\PyTNC_Pro\PyTNC_Pro.exe
REM ============================================================

echo.
echo ============================================================
echo   PyTNC Pro - Build Script
echo ============================================================
echo.

REM Use venv if it exists
if exist .venv\Scripts\python.exe (
    echo Using virtual environment...
    set PYTHON=.venv\Scripts\python.exe
    set PIP=.venv\Scripts\pip.exe
) else (
    echo Using system Python...
    set PYTHON=python
    set PIP=pip
)

REM Check Python
%PYTHON% --version
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3.10 or higher
    pause
    exit /b 1
)

REM Check PyInstaller
%PYTHON% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    %PIP% install pyinstaller
)

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Run PyInstaller
echo.
echo Building PyTNC Pro...
echo This may take several minutes...
echo.

%PYTHON% -m PyInstaller pytnc_pro.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ============================================================
    echo   BUILD FAILED
    echo ============================================================
    echo Check the error messages above.
    echo.
    pause
    exit /b 1
)

REM Copy additional files to dist folder
echo.
echo Copying additional files...

REM Find the output folder (PyTNC-Pro_v*)
for /d %%D in (dist\PyTNC-Pro_v*) do set DIST_FOLDER=%%D
if not defined DIST_FOLDER set DIST_FOLDER=dist\PyTNC-Pro

echo Output folder: %DIST_FOLDER%

REM Copy settings template
if exist pytnc_settings_template.json (
    copy pytnc_settings_template.json "%DIST_FOLDER%\"
)

REM Copy README
if exist README.md (
    copy README.md "%DIST_FOLDER%\"
)

REM Copy LICENSE
if exist LICENSE (
    copy LICENSE "%DIST_FOLDER%\"
)

REM Copy MANUAL
if exist MANUAL.md (
    copy MANUAL.md "%DIST_FOLDER%\"
)

REM Create empty presets folder
if not exist "%DIST_FOLDER%\presets" mkdir "%DIST_FOLDER%\presets"

echo.
echo ============================================================
echo   BUILD SUCCESSFUL!
echo ============================================================
echo.
echo Output: %DIST_FOLDER%\
echo.
echo To distribute:
echo   1. Zip the entire %DIST_FOLDER% folder
echo   2. Share the ZIP with testers
echo.
echo To test locally:
echo   cd %DIST_FOLDER%
echo   PyTNC-Pro_v*.exe
echo.

pause
