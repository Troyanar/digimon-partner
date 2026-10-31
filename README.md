# Digimon Partner (work in progress)

A Digimon that grows with your real life: drinking water, eating, fasting, working out.
Plan and evolution lines: **[PLAN.md](PLAN.md)**. The 3D models and animations come from your own Steam copy of
*Digimon World Next Order* – private use only, do not redistribute.

> **Status:** work in progress.

**Stack:** Python 3, aiohttp, SQLite, three.js. Entry point: `app.py`.

## Start (Windows)

Double-click `start.bat` → http://localhost:8420. Create an account the first time (the first account becomes admin
and needs no code). Friends need an invite code (More → Invite friends).

Manual setup:
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python app.py
```
The database (`data/partner.db`) is created on first start.

**Test mode:** set `DEV=1` in `.env`. Buttons below the partner then let you fast-forward time, run test workouts and
set a form (e.g. `f014`). Always `DEV=0` on a server.

## How the partner works

- **Stats** (0–100): hunger, thirst, strength, spirit, discipline, mood. They drop while you are awake;
  during your sleep time (More → Your day) your Digimon sleeps and nothing drops.
- **Care mistakes:** hunger or thirst empty for 2 hours (an empty stomach does not count while fasting).
- **Digivolution:** Baby 1 day, In-Training 2 days, Rookie 1 week, Champion 2 weeks, Ultimate 3 weeks.
  Which path: more strength training → strength path, more stretching/yoga → spirit path, many care mistakes → wild,
  hardly any training → Numemon, heavily neglected → Sukamon. Paildramon only via Jogress (comes with "Friends").
- **Fasting:** start/stop; reaching the goal → discipline. Eating ends the fast.
- **Final stage:** you can then lay a new egg; your partner moves into the Hall of Fame.

## Layout

- `app.py` web server (aiohttp), login, API · `db.py` SQLite (`data/partner.db`) · `game.py` game logic
- `lines.py` lines and rules · `static/` UI (`viewer.js` = 3D with three.js)
- `data/assets/<id>/` 3D data for the site – only reachable for logged-in users
- `geraet-app/` small Android WebView app (`bauen.ps1`; the site address goes into `geraet-app/url.txt`, not in the repository)
- `tests/` → `python -m unittest discover -s tests`

## Rebuilding the 3D data

The 3D data is not part of this repository. To create it from your own copy of the game:

1. `werkzeuge/cpk.py` extracts models/animations from `DigimonDataR.cpk` (read-only).
2. `werkzeuge/assetstudio_alle.ps1` (run it yourself) exports FBX with AssetStudioMod.
3. `werkzeuge/galerie_daten.py` reads the animations and the eye layer.
4. `werkzeuge/assets_bauen.py` shrinks everything into `data/assets/`.

Preview of all Digimon: `vorschau-starten.bat` (gallery).
