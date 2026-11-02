"""App-Icon für den Home-Bildschirm: Digivice-Bildschirm mit der Digitalen Welt und dem Digi-Ei.

Start: .venv-werkzeuge\\Scripts\\python werkzeuge\\icons_bauen.py
Ergebnis: static/icons/ (icon.svg als Quelle, apple-touch-icon 180, icon-192, icon-512, maskable-512)
Farben wie in der App: Gerät #0c0d0f, Welt aus world.js PALETTE.day, Ei wie favicon.svg.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "icons"

GROUND = "#0c0d0f"
SKY, FAR, NEAR = "#4cbcf6", "#8fd0f7", "#2f9de0"
FLOOR, GRID = "#c4ebff", "#7cc9f2"
PLAZA, PLAZA_EDGE, SHADOW = "#eaf8ff", "#8fd3fa", "#a9c2d6"
SUN = "#ffe066"
EGG, EGG_LINE, BAND = "#f6f1e4", "#0d2366", "#ffb21e"
HORIZON = 300


def floor_grid() -> str:
    """Gitter in Fluchtpunkt-Perspektive: Linien laufen zur Bildmitte über dem Horizont."""
    vx, vy = 256, 210
    lines = []
    for x in range(-640, 1153, 96):                      # Längslinien vom unteren Rand zum Fluchtpunkt
        lines.append(f'<line x1="{x}" y1="512" x2="{vx}" y2="{vy}"/>')
    for y in (318, 342, 376, 424, 492):        # Querlinien, nach vorn immer weiter auseinander
        lines.append(f'<line x1="0" y1="{y}" x2="512" y2="{y}"/>')
    return (f'<g clip-path="url(#floor)" stroke="{GRID}" stroke-width="5" stroke-linecap="square">'
            + "".join(lines) + "</g>")


def svg(bezel: bool) -> str:
    # Bildschirm: mit Rahmen wie das Digivice; maskable (Android schneidet zu) ohne Rahmen, randlos
    inset, radius = (30, 86) if bezel else (0, 0)
    w = 512 - 2 * inset
    rain = "".join(f'<rect x="{x}" y="{y}" width="7" height="{h}" rx="3.5"/>'
                   for x, y, h in ((214, 74, 30), (186, 196, 20), (352, 84, 26), (408, 136, 38), (300, 168, 18), (456, 92, 22)))
    cubes = "".join(f'<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="3" transform="rotate(20 {x} {y})"/>'
                    for x, y, s in ((392, 248, 16), (128, 236, 12)))
    rays = "".join(f'<rect x="-4" y="-66" width="8" height="18" rx="4" transform="rotate({a})"/>' for a in range(0, 360, 45))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <clipPath id="screen"><rect x="{inset}" y="{inset}" width="{w}" height="{w}" rx="{radius}"/></clipPath>
    <clipPath id="floor"><rect x="0" y="{HORIZON}" width="512" height="{512 - HORIZON}"/></clipPath>
  </defs>
  <rect width="512" height="512" fill="{GROUND}"/>
  <g clip-path="url(#screen)">
    <rect width="512" height="512" fill="{SKY}"/>
    <g transform="translate(118 112)" fill="{SUN}"><circle r="34"/>{rays}</g>
    <g fill="#ffffff">{rain}</g>
    <polygon fill="{FAR}" points="0,{HORIZON} 0,222 58,178 120,236 176,196 236,{HORIZON}"/>
    <polygon fill="{FAR}" points="250,{HORIZON} 330,206 380,240 430,188 512,248 512,{HORIZON}"/>
    <polygon fill="{NEAR}" points="0,{HORIZON} 0,262 70,236 150,{HORIZON}"/>
    <polygon fill="{NEAR}" points="330,{HORIZON} 420,252 512,276 512,{HORIZON}"/>
    <g fill="#ffffff">{cubes}</g>
    <rect x="0" y="{HORIZON}" width="512" height="{512 - HORIZON}" fill="{FLOOR}"/>
    {floor_grid()}
    <ellipse cx="256" cy="400" rx="146" ry="34" fill="{PLAZA}" stroke="{PLAZA_EDGE}" stroke-width="7"/>
    <ellipse cx="256" cy="394" rx="74" ry="13" fill="{SHADOW}"/>
    <g transform="translate(124 147) scale(8.25)" stroke-linejoin="round">
      <path d="M16 2c6 0 10 7 10 15s-4 13-10 13S6 25 6 17 10 2 16 2z" fill="{EGG}" stroke="{EGG_LINE}" stroke-width="1.6"/>
      <path d="M7 15l4-3 5 3 5-3 4 3v4l-4-3-5 3-5-3-4 3z" fill="{BAND}"/>
      <path d="M16 2c6 0 10 7 10 15s-4 13-10 13S6 25 6 17 10 2 16 2z" fill="none" stroke="{EGG_LINE}" stroke-width="1.6"/>
    </g>
  </g>
</svg>'''


# Größe, Dateiname, mit Digivice-Rahmen?
ICONS = [(180, "apple-touch-icon.png", True), (192, "icon-192.png", True),
         (512, "icon-512.png", True), (512, "maskable-512.png", False)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "icon.svg").write_text(svg(True), encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge")  # Edge ist auf Windows schon da
        for size, name, bezel in ICONS:
            tab = browser.new_page(viewport={"width": size, "height": size})
            tab.set_content(f"<html><body style='margin:0;width:{size}px;height:{size}px'>{svg(bezel)}</body></html>")
            tab.screenshot(path=str(OUT / name))
            tab.close()
            print("gebaut:", name)
        browser.close()


if __name__ == "__main__":
    main()
