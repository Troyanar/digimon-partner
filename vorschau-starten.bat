@echo off
rem Startet einen kleinen lokalen Webserver fuer die Vorschau-Seiten und oeffnet die Digimon-Galerie.
rem Fenster offen lassen, solange du schaust. Schliessen = Server aus.
cd /d "%~dp0"
start "" "http://127.0.0.1:8411/vorschau/galerie.html"
".venv-werkzeuge\Scripts\python.exe" -m http.server 8411 --bind 127.0.0.1
