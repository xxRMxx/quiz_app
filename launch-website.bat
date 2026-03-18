@echo off
setlocal EnableDelayedExpansion

rem ==========================================
rem Move to the folder where this script lives
rem ==========================================
pushd "%~dp0"

rem ==========================================
rem Ensure virtual environment exists
rem ==========================================
if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found. Creating one...
    
    rem Try using "python" then "py"
    python -m venv .venv 2>nul
    if errorlevel 1 (
        echo "python" failed. Trying "py" instead...
        py -3 -m venv .venv
        if errorlevel 1 (
            echo ERROR: Could not create virtual environment.
            echo Ensure Python is installed and added to PATH.
            popd
            exit /b 1
        )
    )
    
    echo Virtual environment created successfully.

    rem Install requirements if file exists
    if exist requirements.txt (
        echo Installing packages from requirements.txt...
        call .venv\Scripts\activate
        pip install -r requirements.txt
        echo Requirements installed.
    ) else (
        echo WARNING: No requirements.txt found. Skipping package installation.
    )
)

rem ==========================================
rem Virtual environment now guaranteed to exist
rem ==========================================

rem Start Django server in new window
start "Django Server" cmd /k ^
    "call .venv\Scripts\activate && python manage.py runserver 0.0.0.0:8000"

rem Wait for server to come online, then open browser
powershell -NoProfile -Command ^
  "for ($i=0; $i -lt 30; $i++) { try { $r = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/admin-dashboard/' -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } } catch { }; Start-Sleep -Seconds 1 }; exit 1"

if %ERRORLEVEL%==0 (
  start "" "http://127.0.0.1:8000/admin-dashboard/"
  echo Opened http://127.0.0.1:8000/admin-dashboard/
) else (
  echo Server did not respond in time.
  echo You can try opening the URL manually:
  echo http://127.0.0.1:8000/admin-dashboard/
)

popd
endlocal
