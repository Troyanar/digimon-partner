"""Zweite UV-Ebene (Augen) eines Next-Order-Modells als JSON – je Dreieck, über alle Teilmodelle.

AssetStudio schreibt nur die erste UV ins FBX. Die Augen liegen aber auf der zweiten.
Am Augenrand gibt es doppelte Punkte: gleiche Position und gleiche erste UV, aber verschiedene
zweite UV (einer gehört zum Auge, einer zur Haut). Einzelne Punkte lassen sich darum nicht
eindeutig zuordnen – ganze Dreiecke schon (kein Dreieck ist halb Auge, halb Haut).

Ausgabe "tris": je Dreieck 3 Ecken × [u0, v0, u1, v1], dazu "eye" (1 = Augen-Dreieck).
Augen-Punkte erkennt man daran, dass sie weit weg vom "Park-Fleck" liegen, auf den das Spiel
alle übrigen Punkte der zweiten UV legt. Modelle ohne zweite UV bekommen eine leere Liste.

  python uv_export.py <unit-bundle> <ziel.json>
"""

import json
import sys

import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler


def mesh_tris(mesh) -> tuple[list[float], list[int]]:
    handler = MeshHandler(mesh)
    handler.process()
    uv0, uv1 = handler.m_UV0, handler.m_UV1
    if not uv0 or not uv1:
        return [], []
    mu = sorted(u for u, _ in uv1)[len(uv1) // 2]
    mv = sorted(v for _, v in uv1)[len(uv1) // 2]
    is_eye = [((u - mu) ** 2 + (v - mv) ** 2) ** 0.5 > 0.15 for u, v in uv1]
    tris, eye = [], []
    for sub in handler.get_triangles():
        for t in sub:
            for i in t:
                tris += [round(uv0[i][0], 5), round(uv0[i][1], 5), round(uv1[i][0], 5), round(uv1[i][1], 5)]
            eye.append(1 if all(is_eye[i] for i in t) else 0)
    return tris, eye


def main(bundle: str, target: str) -> None:
    env = UnityPy.load(bundle)
    tris, eye = [], []
    for obj in env.objects:
        if obj.type.name == "Mesh":
            t, e = mesh_tris(obj.read())
            tris += t
            eye += e
    with open(target, "w", encoding="utf-8") as f:
        json.dump({"tris": tris, "eye": eye}, f, separators=(",", ":"))
    print("Dreiecke:", len(eye), "davon Auge:", sum(eye))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
