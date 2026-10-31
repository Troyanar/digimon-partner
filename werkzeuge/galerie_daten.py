"""Für alle Galerie-Digimon: Animationen (anim.json) und Augen-UV (uv.json) erzeugen.

  python galerie_daten.py            (nimmt werkzeuge/galerie_ids.txt)

Ergebnis je Digimon in _spieldaten/export/<id>/. Schon vorhandene Dateien werden übersprungen.
"""

import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(HERE))

import anim_export  # noqa: E402
import uv_export  # noqa: E402


def main() -> None:
    ids = (HERE / "galerie_ids.txt").read_text().split()
    raw = BASE / "_spieldaten" / "roh"
    for n, mid in enumerate(ids, 1):
        out = BASE / "_spieldaten" / "export" / mid
        out.mkdir(parents=True, exist_ok=True)
        unit, anim = raw / "unit" / mid, raw / "animator" / f"{mid}_animcontroller"
        try:
            if not (out / "uv.json").exists():
                uv_export.main(str(unit), str(out / "uv.json"))
            if not (out / "anim.json").exists() and anim.exists():
                anim_export.main(str(unit), str(anim), str(out / "anim.json"))
            print(f"[{n}/{len(ids)}] {mid} ok", flush=True)
        except Exception:  # noqa: BLE001 – ein Fehler soll die anderen nicht aufhalten
            print(f"[{n}/{len(ids)}] {mid} FEHLER", flush=True)
            traceback.print_exc()


if __name__ == "__main__":
    main()
