"""Die Digi-Eier aus Next Order für die Webseite: Modell als OBJ + Textur + Ramp nach data/assets/eggNN/.

Die Eier sind einfache, unbewegte Modelle – darum reicht der OBJ-Export von UnityPy (kein AssetStudio nötig).

  python eier_bauen.py
"""

import gzip
import sys
from pathlib import Path

import UnityPy

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))

import lines as L  # noqa: E402

RAW = BASE / "_spieldaten" / "roh" / "unit"
TARGET = BASE / "data" / "assets"


def main() -> None:
    for egg in sorted({line["egg_model"] for line in L.LINES.values()}):
        env = UnityPy.load(str(RAW / egg))
        dst = TARGET / egg
        dst.mkdir(parents=True, exist_ok=True)
        for obj in env.objects:
            if obj.type.name == "Mesh":
                data = obj.read().export().encode()
                (dst / f"{egg}.obj").write_bytes(data)
                (dst / f"{egg}.obj.gz").write_bytes(gzip.compress(data, 9))
            elif obj.type.name == "Texture2D":
                tex = obj.read()
                if tex.m_Name in (egg, f"{egg}_r00"):
                    tex.image.save(dst / f"{tex.m_Name}.png")
        print("Ei:", egg, sorted(f.name for f in dst.iterdir()))


if __name__ == "__main__":
    main()
