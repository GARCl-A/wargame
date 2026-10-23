@echo off
rem Double-click: pick a lab fight and play it in the web client.
cd /d "%~dp0..\..\..\.."
echo.
echo   1  fortress     The Ogre's fortress (default)
echo   2  dungeon      Ancient Ruins, in the dark
echo   3  wilds        Wilds ambush
echo   4  road         Old Road ambush
echo   5  camp         Wildfire camp
echo   6  necromancer  The Necromancer at the Front (big board)
echo   7  lair         The Dragon's Lair
echo   8  brawl        Games: Brawl
echo   9  champion     Challenge the Champion
echo.
set "pick=1"
set /p "pick=Fight [1]: "
set "fight=fortress"
if "%pick%"=="2" set "fight=dungeon"
if "%pick%"=="3" set "fight=wilds"
if "%pick%"=="4" set "fight=road"
if "%pick%"=="5" set "fight=camp"
if "%pick%"=="6" set "fight=necromancer"
if "%pick%"=="7" set "fight=lair"
if "%pick%"=="8" set "fight=brawl"
if "%pick%"=="9" set "fight=champion"
python -m gartok.web --fight %fight%
if errorlevel 1 pause
