"""Für die Modell-Übersicht: von jedem Next-Order-Modell OBJ + Haupttextur exportieren.

  python vorschau_export.py <unit-ordner> <zielordner>

Schreibt <ziel>/<id>.obj, <ziel>/<id>.png und <ziel>/liste.json (alle IDs mit Modell).
"""

import json
import sys
from pathlib import Path

import UnityPy


def main(src: str, dst: str) -> None:
    out = Path(dst)
    out.mkdir(parents=True, exist_ok=True)
    ids = []
    for path in sorted(Path(src).iterdir()):
        if not path.is_file():
            continue
        try:
            env = UnityPy.load(str(path))
        except Exception as exc:  # noqa: BLE001 – einzelne kaputte Pakete überspringen
            print("übersprungen", path.name, exc)
            continue
        meshes, textures = [], {}
        for obj in env.objects:
            if obj.type.name == "Mesh":
                meshes.append(obj.read())
            elif obj.type.name == "Texture2D":
                tex = obj.read()
                textures[tex.m_Name] = tex
        if not meshes:
            continue
        mesh = max(meshes, key=lambda m: len(m.export()))
        main_tex = textures.get(f"{path.name}_c00") or next(
            (t for n, t in textures.items() if n.endswith("_c00")), None)
        (out / f"{path.name}.obj").write_text(mesh.export(), encoding="utf-8")
        if main_tex:
            img = main_tex.image.convert("RGB")
            img.thumbnail((256, 256))
            img.save(out / f"{path.name}.png")
        ids.append(path.name)
        print("ok", path.name)
    (out / "liste.json").write_text(json.dumps(ids), encoding="utf-8")
    print(len(ids), "Modelle")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
