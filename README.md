# Digimon Partner (work in progress)

A Digimon that grows with your real life: drink water, eat, fast and work out, and your partner gets stronger and digivolves.

> **Status:** work in progress.

## Features
- Partner stats driven by real habits: water, meals, fasting, training, steps
- Branching digivolution lines
- 3D viewer with animations (three.js)
- Friends: invites, cheers and Jogress
- Installable PWA with offline support, a DEV time-travel mode and unit tests
- Small Android WebView wrapper in `geraet-app/`, Docker deployment

## Stack
Python 3, aiohttp, SQLite, three.js. Entry point: `app.py`.

## Setup
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python app.py   # http://localhost:8420
```
The first account becomes the admin. Run the tests with `python -m unittest`.

The 3D models and animations are not part of this repository. They come from your own copy of
*Digimon World Next Order* (Steam) and are extracted with the scripts in `werkzeuge/`.

German documentation: [README.de.md](README.de.md) · plan: [PLAN.md](PLAN.md)
