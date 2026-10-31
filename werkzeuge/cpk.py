"""Leser für CRI-CPK-Archive (unverschlüsselt), wie sie Digimon World Next Order benutzt.

Liest das Inhaltsverzeichnis (TOC) und entpackt einzelne Dateien, inkl. CRILAYLA-Kompression.
Nur lesend: das Spiel wird nicht verändert.

  python cpk.py liste  <archiv.cpk> [filter]          Dateien auflisten (Filter = Teil des Pfads)
  python cpk.py hole   <archiv.cpk> <ziel> <filter>   passende Dateien nach <ziel> entpacken
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

# --- @UTF-Tabellen -------------------------------------------------------------------
TYPES = {0: ">B", 1: ">b", 2: ">H", 3: ">h", 4: ">I", 5: ">i", 6: ">Q", 7: ">q", 8: ">f"}


def read_utf(buf: bytes) -> list[dict]:
    """Eine @UTF-Tabelle in eine Liste von Zeilen (dict Spalte -> Wert) umwandeln."""
    if buf[:4] != b"@UTF":
        raise ValueError("keine @UTF-Tabelle (verschlüsselt?)")
    _size, rows_off, str_off, data_off, _name, ncols, row_len, nrows = struct.unpack(">IIIIIHHI", buf[4:32])
    base = 8
    strings = buf[base + str_off:base + data_off]

    def string(off: int) -> str:
        end = strings.index(b"\0", off)
        return strings[off:end].decode("utf-8", "replace")

    def value(kind: int, pos: int) -> tuple[object, int]:
        if kind in TYPES:
            fmt = TYPES[kind]
            return struct.unpack_from(fmt, buf, pos)[0], pos + struct.calcsize(fmt)
        if kind == 0xA:
            return string(struct.unpack_from(">I", buf, pos)[0]), pos + 4
        if kind == 0xB:
            off, size = struct.unpack_from(">II", buf, pos)
            return buf[base + data_off + off:base + data_off + off + size], pos + 8
        raise ValueError(f"unbekannter Spaltentyp {kind:#x}")

    cols, pos = [], 32
    for _ in range(ncols):
        flags = buf[pos]
        name = string(struct.unpack_from(">I", buf, pos + 1)[0])
        pos += 5
        const = None
        if flags & 0xF0 == 0x30:
            const, pos = value(flags & 0x0F, pos)
        cols.append((name, flags, const))

    rows = []
    for r in range(nrows):
        p = base + rows_off + r * row_len
        row = {}
        for name, flags, const in cols:
            store = flags & 0xF0
            if store == 0x50:
                row[name], p = value(flags & 0x0F, p)
            elif store == 0x30:
                row[name] = const
            else:
                row[name] = None
        rows.append(row)
    return rows


# --- CRILAYLA ------------------------------------------------------------------------
def crilayla(data: bytes) -> bytes:
    """CRI-eigene Kompression: liest Bits rückwärts, schreibt die Ausgabe rückwärts."""
    if data[:8] != b"CRILAYLA":
        return data
    usize, hoff = struct.unpack_from("<II", data, 8)
    out = bytearray(usize + 0x100)
    out[:0x100] = data[hoff + 0x10:hoff + 0x110]
    src = len(data) - 0x100 - 1
    end = 0x100 + usize - 1
    pool = left = 0
    done = 0

    def bits(n: int) -> int:
        nonlocal pool, left, src
        v = got = 0
        while got < n:
            if left == 0:
                pool, left, src = data[src], 8, src - 1
            take = min(left, n - got)
            v = (v << take) | ((pool >> (left - take)) & ((1 << take) - 1))
            left -= take
            got += take
        return v

    while done < usize:
        if bits(1):
            ref = end - done + bits(13) + 3
            length = 3
            for lvl in (2, 3, 5, 8):
                step = bits(lvl)
                length += step
                if step != (1 << lvl) - 1:
                    break
            else:
                while True:
                    step = bits(8)
                    length += step
                    if step != 255:
                        break
            for _ in range(length):
                out[end - done] = out[ref]
                ref -= 1
                done += 1
        else:
            out[end - done] = bits(8)
            done += 1
    return bytes(out)


# --- Archiv --------------------------------------------------------------------------
class Cpk:
    def __init__(self, path: Path):
        self.f = open(path, "rb")
        head = self.f.read(16)
        if head[:4] != b"CPK ":
            raise ValueError("keine CPK-Datei")
        size = struct.unpack_from("<I", head, 8)[0]
        info = read_utf(self.f.read(size))[0]
        toc_off, content_off = info.get("TocOffset") or 0, info.get("ContentOffset") or 0
        self.f.seek(toc_off)
        toc_head = self.f.read(16)
        if toc_head[:4] != b"TOC ":
            raise ValueError("kein Inhaltsverzeichnis (TOC) – anderes CPK-Format")
        toc = read_utf(self.f.read(struct.unpack_from("<I", toc_head, 8)[0]))
        add = min(o for o in (toc_off, content_off) if o) if (toc_off or content_off) else 0
        self.files = []
        for row in toc:
            name = "/".join(p for p in (row.get("DirName") or "", row.get("FileName") or "") if p)
            self.files.append({"name": name, "offset": row["FileOffset"] + add,
                               "size": row["FileSize"], "extract": row.get("ExtractSize") or row["FileSize"]})

    def read(self, entry: dict) -> bytes:
        self.f.seek(entry["offset"])
        data = self.f.read(entry["size"])
        return crilayla(data) if entry["extract"] != entry["size"] else data


def main(argv: list[str]) -> None:
    cmd, archive = argv[0], Path(argv[1])
    cpk = Cpk(archive)
    if cmd == "liste":
        flt = argv[2].lower() if len(argv) > 2 else ""
        hits = [e for e in cpk.files if flt in e["name"].lower()]
        for e in hits:
            print(f"{e['extract']:>10}  {e['name']}")
        print(f"{len(hits)} von {len(cpk.files)} Dateien")
    elif cmd == "hole":
        # Filter: Teil des Pfads; mehrere mit Komma; "=pfad" = nur genau dieser Pfad
        target = Path(argv[2])
        flts = [f.strip().lower() for f in argv[3].split(",") if f.strip()]
        match = lambda n: any(n == f[1:] if f.startswith("=") else f in n for f in flts)  # noqa: E731
        for e in cpk.files:
            if match(e["name"].lower()):
                out = target / e["name"]
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(cpk.read(e))
                print("entpackt:", e["name"])


if __name__ == "__main__":
    main(sys.argv[1:])
