@echo off
rem Start the CD-SEM Predict API (Windows).  Optional environment variables: PORT, HOST, CDSEM_IMAGE_DIR, CDSEM_DATA_DIR, TESSERACT_CMD
cd /d "%~dp0"
if "%PORT%"=="" set PORT=8000
if "%HOST%"=="" set HOST=0.0.0.0
if "%TESSERACT_CMD%"=="" if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe"
.venv\Scripts\python.exe -m uvicorn cdsem_api:app --host %HOST% --port %PORT%
pause
