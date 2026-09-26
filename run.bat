@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title SafeCircle Demo
echo.
echo  ========================================
echo   SafeCircle - backend + frontend
echo  ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] Python not found on PATH.
  echo  Install Python 3.9+ and try again.
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" (
    echo  No .env found - copying .env.example
    copy /Y ".env.example" ".env" >nul
    echo  Add OPENAI_API_KEY to .env for AI mode, then re-run.
    echo.
  )
)

echo  Installing/checking openai package...
python -m pip install -q -r requirements.txt 2>nul

set PORT=8000
set HOST=127.0.0.1

echo.
echo  Starting server at http://localhost:%PORT%
echo    Main UI:   http://localhost:%PORT%/
echo    3-panel:   http://localhost:%PORT%/demo.html
echo  Press Ctrl+C to stop.
echo.

REM Open frontend after a short delay so the server can bind
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:%PORT%/demo.html && start http://localhost:%PORT%/"

python server.py --host %HOST% --port %PORT%
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE% neq 0 (
  echo  Server exited with code %EXITCODE%.
  pause
)
exit /b %EXITCODE%
