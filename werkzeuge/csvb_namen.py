"""Digimon-Namen zu Modell-IDs aus der Next-Order-Texttabelle (CSVB) finden.

Die Tabelle besteht aus Zeilen (Schlüssel-Hash, Text-Offset). Gesucht ist die Vorschrift, nach der
der Schlüssel gebildet wird: Wir probieren gängige Schreibweisen + Hash-Verfahren aus und schauen,
welche für "c001" auf "Agumon" zeigt.

  python csvb_namen.py <lang_00_xx.bin> [ausgabe.json]
"""

import json
import struct
import sys
import zlib


def fnv1a32(s: bytes) -> int:
    h = 0x811C9DC5
    for c in s:
        h = ((h ^ c) * 0x01000193) & 0xFFFFFFFF
    return h


def fnv1_32(s: bytes) -> int:
    h = 0x811C9DC5
    for c in s:
        h = ((h * 0x01000193) & 0xFFFFFFFF) ^ c
    return h


HASHES = {"crc32": lambda s: zlib.crc32(s) & 0xFFFFFFFF, "fnv1a": fnv1a32, "fnv1": fnv1_32}


def read_table(raw: bytes) -> dict[int, str]:
    rows = struct.unpack_from("<I", raw, 32 + 20)[0]
    str_base = struct.unpack_from("<I", raw, 16)[0]
    out = {}
    pos = 32 + 16 + 4 * 8  # erste Zeile direkt hinter dem Kopf
    for _ in range(rows):
        h, off = struct.unpack_from("<II", raw, pos)
        pos += 8
        end = raw.index(b"\0", str_base + off)
        out[h] = raw[str_base + off:end].decode("utf-8", "replace")
    return out


def main(path: str, target: str | None = None) -> None:
    raw = open(path, "rb").read()
    table = read_table(raw)
    print("Zeilen:", len(table), "Beispiel:", list(table.values())[:3])
    agumon = [h for h, s in table.items() if s == "Agumon"]
    print("Hash(es) für 'Agumon':", [hex(h) for h in agumon])
    patterns = ["c001", "C001", "{}_name", "name_{}", "chr_{}", "{}_NAME", "NAME_{}", "DIGIMON_{}", "digimon_{}",
                "{}name", "name{}", "chr{}", "chr_name_{}", "digimon_name_{}", "DigimonName_{}", "{}_00", "dname_{}"]
    for pat in patterns:
        key = pat.format("c001") if "{}" in pat else pat
        for variant in {key, key.upper(), key.lower()}:
            for hname, fn in HASHES.items():
                if fn(variant.encode()) in agumon:
                    print("GEFUNDEN:", hname, repr(pat), "->", variant)
                    if target:
                        ids = [f"{s}{n:03d}" for s in "abcdefg" for n in range(1, 80)]
                        names = {}
                        for i in ids:
                            k = pat.format(i) if "{}" in pat else i
                            k = k.upper() if variant == key.upper() and variant != key else k
                            v = table.get(fn(k.encode()))
                            if v:
                                names[i] = v
                        json.dump(names, open(target, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                        print(len(names), "Namen gespeichert")
                    return
    print("keine Vorschrift gefunden")


if __name__ == "__main__":
    main(*sys.argv[1:3])
