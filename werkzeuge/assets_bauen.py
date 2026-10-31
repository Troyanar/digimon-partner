"""Spieldaten für die Webseite zusammenstellen und verkleinern.

Nimmt aus _spieldaten/export/<id>/ das FBX (Modell + Skelett), die Texturen, die Augen-UV und
die Animationen und schreibt sie nach data/assets/<id>/. Dabei:
  - nur die Animationen, die der Partner wirklich nutzt (statt ~43)
  - Spuren, die sich nie ändern, nur mit einem Wert
  - Zahlen gekürzt
  - zusätzlich .gz-Fassungen, die der Server direkt ausliefert

  python assets_bauen.py            (alle Formen aus lines.py)
"""

import gzip
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))

import lines as L  # noqa: E402

EXPORT = BASE / "_spieldaten" / "export"
TARGET = BASE / "data" / "assets"
# Diese Animationen nutzt der Partner (Stehen, Essen, Ausruhen, Gehen, Rennen, Gefühle, Springen, Angriffe, Aufstehen)
KEEP = re.compile(r"_(base_f[ab]0|eat_|rest_|walk_fa0|run_|feel_f[a-i]0|jump_fa1|atck_fa0|spat_|getu_)")


def compact_clip(clip: dict) -> dict:
    tracks = []
    for t in clip["tracks"]:
        size = 4 if t["type"] == "quaternion" else 3
        vals = t["values"]
        first = vals[:size]
        const = all(abs(v - first[i % size]) < 1e-4 for i, v in enumerate(vals))
        if t["type"] == "scale" and const and all(abs(v - 1) < 1e-4 for v in first):
            continue  # Größe bleibt immer 1 – weglassen
        out = first if const else vals
        tracks.append({"bone": t["bone"], "type": t["type"], "values": [round(v, 4) for v in out]})
    return {"name": clip["name"], "duration": clip["duration"], "fps": clip["fps"], "tracks": tracks}


def write(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    path.with_name(path.name + ".gz").write_bytes(gzip.compress(data, 9))


def build(mid: str) -> int:
    src = EXPORT / mid
    fbx_dir = src / "FBX_Animator" / mid
    if not (fbx_dir / f"{mid}.fbx").exists():
        print("fehlt (FBX):", mid)
        return 0
    dst = TARGET / mid
    dst.mkdir(parents=True, exist_ok=True)
    for f in fbx_dir.iterdir():
        if f.suffix == ".png":
            shutil.copy2(f, dst / f.name)
    write(dst / f"{mid}.fbx", (fbx_dir / f"{mid}.fbx").read_bytes())
    anim = json.loads((src / "anim.json").read_text()) if (src / "anim.json").exists() else {"clips": []}
    clips = [compact_clip(c) for c in anim["clips"] if KEEP.search(c["name"])]
    write(dst / "anim.json", json.dumps({"clips": clips}, separators=(",", ":")).encode())
    if (src / "uv.json").exists():
        write(dst / "uv.json", (src / "uv.json").read_bytes())
    return sum(f.stat().st_size for f in dst.iterdir() if f.suffix == ".gz" or f.suffix == ".png")


def main() -> None:
    ids = L.all_forms()
    total = 0
    for mid in ids:
        total += build(mid)
    print(f"{len(ids)} Formen, über das Netz ca. {total / 1e6:.0f} MB (gepackt)")


if __name__ == "__main__":
    main()
