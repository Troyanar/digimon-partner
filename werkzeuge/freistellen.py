"""Digi-API-Artworks freistellen: weißer Hintergrund wird durchsichtig, Figur unten bündig.

Der Hintergrund wird von den Bildrändern aus gefüllt (Flood-Fill). Weiße Stellen IN der Figur
(Krallen, Zähne) bleiben, weil sie von der schwarzen Kontur umschlossen sind.

Aufruf: python freistellen.py <eingabe-ordner> <ausgabe-ordner>
"""

import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter

WHITE = 232      # ab dieser Helligkeit (alle drei Farben) gilt ein Pixel als Hintergrund
SIZE = 320       # Ausgabe: quadratisch, Figur unten mittig


def cutout(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    bg = bytearray(w * h)
    todo = deque((x, y) for x in range(w) for y in (0, h - 1))
    todo.extend((x, y) for y in range(h) for x in (0, w - 1))
    while todo:
        x, y = todo.popleft()
        i = y * w + x
        if bg[i]:
            continue
        r, g, b, _ = px[x, y]
        if min(r, g, b) < WHITE:
            continue
        bg[i] = 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not bg[ny * w + nx]:
                todo.append((nx, ny))
    mask = Image.new("L", (w, h), 255)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            if bg[y * w + x]:
                mp[x, y] = 0
    # weiche Kante, damit kein weißer Saum bleibt
    mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.7))
    img.putalpha(mask)
    box = img.getbbox()
    fig = img.crop(box)
    scale = min((SIZE - 8) / fig.width, (SIZE - 4) / fig.height, 1.0)
    if scale < 1:
        fig = fig.resize((round(fig.width * scale), round(fig.height * scale)), Image.LANCZOS)
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(fig, ((SIZE - fig.width) // 2, SIZE - fig.height - 2), fig)
    return out


def main(src: str, dst: str) -> None:
    Path(dst).mkdir(parents=True, exist_ok=True)
    for path in sorted(Path(src).glob("*.png")):
        cutout(Image.open(path)).save(Path(dst) / path.name, optimize=True)
        print("frei:", path.name)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
