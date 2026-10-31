"""Animationen aus Next Order (Unity-Mecanim, "generic") als JSON für den Browser (three.js).

  python anim_export.py <unit-bundle> <animator-bundle> <ziel.json>

Unity speichert eine Animation als drei Kurven-Sorten (streamed = Polynome je Abschnitt,
dense = feste Bildraten-Tabelle, constant = ein Wert). Jede Kurve gehört über "genericBindings"
zu einem Knochen (CRC32 seines Pfads) und einer Eigenschaft (Position, Drehung, Größe).
Hier wird alles gleichmäßig mit 30 Bildern/s abgetastet. Koordinaten werden wie beim
FBX-Export von AssetStudio umgerechnet (Unity ist linkshändig): x spiegeln.
"""

from __future__ import annotations

import json
import math
import struct
import sys
import zlib

import UnityPy

FPS = 30
TRANSFORM = 4  # Unity-Klassen-ID für Transform


# --- Knochen-Pfade aus dem Modell ------------------------------------------------------
def bone_paths(unit_bundle: str) -> dict[int, str]:
    """CRC32 des Pfads (relativ zum Wurzel-Objekt) -> Knochenname.

    Next Order speichert das Skelett "optimiert": die Knochen sind keine eigenen Objekte,
    ihre Pfade stehen nur in der Tabelle m_TOS des Avatars. Manche Modelle haben mehrere Avatare
    (z. B. eigene für Effekte) – darum werden alle zusammengenommen."""
    env = UnityPy.load(unit_bundle)
    out = {}
    for obj in env.objects:
        if obj.type.name == "Avatar":
            for h, p in obj.read().m_TOS:
                if p:
                    out.setdefault(h, p.split("/")[-1])
    if out:
        return out
    transforms = {}
    for obj in env.objects:
        if obj.type.name == "Transform":
            t = obj.read()
            transforms[obj.path_id] = t
    names = {pid: t.m_GameObject.read().m_Name for pid, t in transforms.items()}
    parent = {pid: (t.m_Father.path_id if t.m_Father else 0) for pid, t in transforms.items()}
    roots = [pid for pid, par in parent.items() if par == 0 or par not in transforms]
    out = {}
    for pid in transforms:
        parts, p = [], pid
        while p in transforms and p not in roots:
            parts.append(names[p])
            p = parent[p]
        path = "/".join(reversed(parts))
        out[zlib.crc32(path.encode("utf-8"))] = names[pid]
    return out


# --- Kurven auswerten ----------------------------------------------------------------
def streamed_curves(data: list[int]) -> dict[int, list[tuple[float, list[float]]]]:
    """Streamed-Daten (uint32-Liste) -> je Kurve eine Liste (Zeit, Koeffizienten a,b,c,d)."""
    raw = struct.pack(f"<{len(data)}I", *data)
    pos, curves = 0, {}
    while pos < len(raw):
        time, count = struct.unpack_from("<fi", raw, pos)
        pos += 8
        for _ in range(count):
            idx, a, b, c, d = struct.unpack_from("<iffff", raw, pos)
            pos += 20
            curves.setdefault(idx, []).append((time, [a, b, c, d]))
    return curves


def eval_streamed(keys: list[tuple[float, list[float]]], t: float) -> float:
    """Wert = a·dt³ + b·dt² + c·dt + d im Abschnitt, der vor t beginnt."""
    seg = keys[0]
    for k in keys:
        if k[0] <= t:
            seg = k
        else:
            break
    start = seg[0] if math.isfinite(seg[0]) else t
    dt = t - start
    a, b, c, d = seg[1]
    return ((a * dt + b) * dt + c) * dt + d


def binding_slots(bindings) -> list[tuple[object, int]]:
    """Kurven-Index -> (Binding, Komponente). Position/Größe/Euler haben 3 Kurven, Drehung 4."""
    slots = []
    for b in bindings:
        if b.typeID == TRANSFORM:
            n = 4 if b.attribute == 2 else 3 if b.attribute in (1, 3, 4) else 1
        else:
            n = 1
        slots.extend((b, i) for i in range(n))
    return slots


def euler_to_quat(x: float, y: float, z: float) -> list[float]:
    """Unity-Euler (Grad, Reihenfolge Z, X, Y) -> Quaternion (x, y, z, w)."""
    cx, sx = math.cos(math.radians(x) / 2), math.sin(math.radians(x) / 2)
    cy, sy = math.cos(math.radians(y) / 2), math.sin(math.radians(y) / 2)
    cz, sz = math.cos(math.radians(z) / 2), math.sin(math.radians(z) / 2)
    return [sx * cy * cz + cx * sy * sz, cx * sy * cz - sx * cy * sz,
            cx * cy * sz - sx * sy * cz, cx * cy * cz + sx * sy * sz]


def export_clip(clip, paths: dict[int, str]) -> dict:
    mc = clip.m_MuscleClip
    data = mc.m_Clip.data
    start, stop = mc.m_StartTime, mc.m_StopTime
    frames = max(1, round((stop - start) * FPS)) + 1
    times = [start + i / FPS for i in range(frames)]

    streamed = streamed_curves(data.m_StreamedClip.data)
    s_count = data.m_StreamedClip.curveCount
    dense = data.m_DenseClip
    d_count = dense.m_CurveCount
    const = data.m_ConstantClip.data

    def curve_values(index: int) -> list[float]:
        if index < s_count:
            keys = streamed.get(index)
            return [eval_streamed(keys, t) for t in times] if keys else [0.0] * frames
        index -= s_count
        if index < d_count:
            out = []
            for t in times:
                f = (t - dense.m_BeginTime) * dense.m_SampleRate
                f0 = max(0, min(dense.m_FrameCount - 1, int(math.floor(f))))
                f1 = min(dense.m_FrameCount - 1, f0 + 1)
                w = min(1.0, max(0.0, f - f0))
                v0 = dense.m_SampleArray[f0 * d_count + index]
                v1 = dense.m_SampleArray[f1 * d_count + index]
                out.append(v0 + (v1 - v0) * w)
            return out
        return [const[index - d_count]] * frames

    slots = binding_slots(clip.m_ClipBindingConstant.genericBindings)
    total = s_count + d_count + len(const)
    channels: dict[tuple[str, int], dict[int, list[float]]] = {}
    for idx in range(min(total, len(slots))):
        b, comp = slots[idx]
        if b.typeID != TRANSFORM or b.path not in paths:
            continue
        channels.setdefault((paths[b.path], b.attribute), {})[comp] = curve_values(idx)

    tracks = []
    for (bone, attr), comps in channels.items():
        values = []
        for f in range(frames):
            v = [comps.get(i, [0.0] * frames)[f] for i in range(4 if attr == 2 else 3)]
            if attr == 1:                       # Position: x spiegeln
                v = [-v[0], v[1], v[2]]
            elif attr == 2:                     # Drehung (Quaternion): y und z spiegeln
                v = [v[0], -v[1], -v[2], v[3]]
            elif attr == 4:                     # Euler -> Quaternion, dann spiegeln
                q = euler_to_quat(*v)
                v = [q[0], -q[1], -q[2], q[3]]
            values.append(v)
        kind = {1: "position", 2: "quaternion", 3: "scale", 4: "quaternion"}[attr]
        if kind == "quaternion":                # kürzesten Weg halten, sonst springt die Drehung
            for i in range(1, len(values)):
                if sum(a * b for a, b in zip(values[i], values[i - 1])) < 0:
                    values[i] = [-x for x in values[i]]
        tracks.append({"bone": bone, "type": kind,
                       "values": [round(x, 5) for v in values for x in v]})
    return {"name": clip.m_Name, "duration": round(stop - start, 4), "fps": FPS,
            "loop": bool(clip.m_MuscleClip.m_LoopTime), "tracks": tracks}


def main(unit: str, animator: str, target: str) -> None:
    paths = bone_paths(unit)
    env = UnityPy.load(animator)
    clips = [export_clip(o.read(), paths) for o in env.objects if o.type.name == "AnimationClip"]
    clips.sort(key=lambda c: c["name"])
    with open(target, "w", encoding="utf-8") as f:
        json.dump({"clips": clips}, f, separators=(",", ":"))
    for c in clips:
        print(f"{c['name']:18} {c['duration']:5.2f}s  Spuren: {len(c['tracks'])}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
