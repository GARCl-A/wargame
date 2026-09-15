@echo off
echo Criando ambiente virtual...
uv venv

echo Instalando dependencias e o PyInstaller...
uv pip install -r requirements.txt pyinstaller

echo.
echo Construindo o executavel com PyInstaller...
uv run pyinstaller --onefile --noconsole --name GARTOK --add-data "locales;locales" --add-data "maps;maps" --add-data "npcs;npcs" --add-data "gartok/assets;gartok/assets" main.py

echo.
echo Pronto! O executavel esta na pasta "dist".
pause
