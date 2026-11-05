@echo off
rem One-time setup (Windows): creates .venv and installs the Python packages. Needs Python 3.12 or newer.
cd /d "%~dp0"
py -3 -m venv .venv || python -m venv .venv
if errorlevel 1 (
    echo Could not create the virtual environment. Is Python 3.12+ installed and on PATH?
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo pip install failed.
    pause
    exit /b 1
)
where tesseract >nul 2>nul
if errorlevel 1 if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo.
    echo WARNING: Tesseract OCR was not found. Install it, then set TESSERACT_CMD to tesseract.exe if it is not on PATH.
)
echo.
echo Setup finished. Start the API with start_api.bat
pause
