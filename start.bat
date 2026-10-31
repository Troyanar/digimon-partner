@echo off
rem Startet den Digimon-Partner lokal: http://localhost:8420
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python wurde nicht gefunden. Bitte Python 3 installieren: https://www.python.org/downloads/
    pause
    exit /b 1
)
if not exist .venv\Scripts\python.exe (
    echo Richte Python-Umgebung ein ...
    python -m venv .venv
    if errorlevel 1 goto fehler
)
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto fehler
if not exist .env copy .env.example .env >nul
start "" "http://localhost:8420"
.venv\Scripts\python app.py
pause
exit /b 0

:fehler
echo.
echo Einrichtung fehlgeschlagen (Internet da?). Beim naechsten Start wird es erneut versucht.
pause
exit /b 1
