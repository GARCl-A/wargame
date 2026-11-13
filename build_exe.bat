@echo off
echo Creating the virtual environment...
uv venv

echo Installing dependencies and PyInstaller...
uv pip install -r requirements.txt pyinstaller

echo.
echo Checking the version...
uv run python scripts/version_check.py --build
if errorlevel 1 (
    echo Fix the error above and run again.
    pause
    exit /b 1
)

echo Building the native client (server with PyInstaller, window with Electron)...
uv run python scripts/build_client.py
if errorlevel 1 (
    echo Fix the error above and run again.
    pause
    exit /b 1
)

echo.
echo Done! The client is the zip in the "dist" folder.
pause
