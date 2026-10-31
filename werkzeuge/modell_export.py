"""Modell (ohne Animation) und Texturen aus einem Next-Order-Paket holen.

  python modell_export.py <unit-bundle> <zielordner>

Schreibt <name>.obj (Teilnetze als eigene Gruppen) und die Texturen als PNG.
"""

import sys
from pathlib import Path

import UnityPy


def main(bundle: str, target: str) -> None:
    out = Path(target)
    out.mkdir(parents=True, exist_ok=True)
    env = UnityPy.load(bundle)
    for obj in env.objects:
        kind = obj.type.name
        if kind == "Mesh":
            mesh = obj.read()
            (out / f"{mesh.m_Name}.obj").write_text(mesh.export(), encoding="utf-8")
            print("Modell:", mesh.m_Name, "Teilnetze:", len(mesh.m_SubMeshes))
        elif kind == "Texture2D":
            tex = obj.read()
            tex.image.save(out / f"{tex.m_Name}.png")
            print("Textur:", tex.m_Name)
        elif kind == "Material":
            mat = obj.read()
            names = []
            for key, env_tex in mat.m_SavedProperties.m_TexEnvs:
                ref = env_tex.m_Texture
                if ref and ref.m_PathID:
                    try:
                        names.append(f"{key}={ref.read().m_Name}")
                    except Exception:  # noqa: BLE001 – Verweis in ein anderes Paket
                        names.append(f"{key}=?")
            print("Material:", mat.m_Name, names)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
