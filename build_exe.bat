@echo off
echo Creating the virtual environment...
uv venv

echo Installing dependencies and PyInstaller...
uv pip install -r requirements.txt pyinstaller

echo.
echo Checking the version...
uv run python scripts/version_check.py --build
if errorlevel 1 (
    echo Fix docs/versions.csv and run again.
    pause
    exit /b 1
)

echo Building the executable with PyInstaller...
uv run pyinstaller --onefile --noconsole --name GARTOK --add-data "locales;locales" --add-data "maps;maps" --add-data "npcs;npcs" --add-data "gartok/assets;gartok/assets" --add-data "gartok/web/client;gartok/web/client" main.py

echo.
echo Done! The executable is in the "dist" folder.
pause
