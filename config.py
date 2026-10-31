"""Einstellungen aus der .env (siehe .env.example)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _int_env(name: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if lo <= value <= hi else default


HOST = os.getenv("HOST", "127.0.0.1")
PORT = _int_env("PORT", 8420, 1, 65535)
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "partner.db"))
# 3D-Modelle aus Next Order – werden nur an angemeldete Nutzer ausgeliefert
ASSET_DIR = Path(os.getenv("ASSET_DIR", DATA_DIR / "assets"))
# Geräte-App zum Herunterladen (geraet-app\bauen.ps1 legt sie hier ab; nur für angemeldete Nutzer)
APK_PATH = Path(os.getenv("APK_PATH", DATA_DIR / "app" / "DigimonPartner.apk"))
TRUSTED_PROXIES = {p.strip() for p in os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1").split(",") if p.strip()}
TZ = os.getenv("TZ_NAME", "Europe/Berlin")
# Test-Werkzeuge (Zeit vorspulen, Training eintragen) – nur lokal einschalten, nie auf dem Server
DEV = os.getenv("DEV", "0") == "1"
