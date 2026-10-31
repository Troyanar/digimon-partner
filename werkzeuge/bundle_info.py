"""Zeigt, was in einem Unity-Paket (AssetBundle) aus Next Order steckt.

  python bundle_info.py <bundle> [weitere bundles ...]
"""

import sys
from collections import Counter

import UnityPy


def main(paths: list[str]) -> None:
    for path in paths:
        env = UnityPy.load(path)
        kinds = Counter(obj.type.name for obj in env.objects)
        print(f"== {path}")
        print("   Typen:", dict(kinds))
        for obj in env.objects:
            if obj.type.name in ("Mesh", "Texture2D", "AnimationClip", "SkinnedMeshRenderer", "GameObject", "AnimatorController", "Avatar"):
                try:
                    data = obj.read()
                    name = getattr(data, "m_Name", "") or getattr(data, "name", "")
                except Exception as exc:  # noqa: BLE001 – nur Übersicht
                    name = f"(nicht lesbar: {exc})"
                if obj.type.name in ("GameObject",) and kinds["GameObject"] > 15:
                    continue
                extra = ""
                if obj.type.name == "AnimationClip":
                    extra = f"  {getattr(data, 'm_MuscleClipSize', '')}"
                print(f"   {obj.type.name:20} {name}{extra}")


if __name__ == "__main__":
    main(sys.argv[1:])
