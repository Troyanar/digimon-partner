"""Welche Digimon aus unserem Plan gibt es in Next Order? Liest die Namensliste aus der englischen Texttabelle.

  python roster_check.py <lang_00_en.bin>
"""

import sys

PLAN = {
    "Agumon": "Botamon Koromon Agumon Greymon MetalGreymon WarGreymon GeoGreymon RiseGreymon ShineGreymon SkullGreymon",
    "Gabumon": "Punimon Tsunomon Gabumon Garurumon WereGarurumon MetalGarurumon Lobomon KendoGarurumon MagnaGarurumon",
    "Veemon": "Chibomon DemiVeemon Veemon ExVeemon Paildramon Imperialdramon Veedramon AeroVeedramon UlforceVeedramon",
    "Wormmon": "Leafmon Minomon Wormmon Stingmon DinoBeemon GranKuwagamon JewelBeemon TigerVespamon",
    "Gomamon": "Pichimon Bukamon Gomamon Ikkakumon Zudomon Vikemon Seadramon Whamon MarineAngemon",
    "Guilmon": "Jyarimon Gigimon Guilmon Growlmon WarGrowlmon Gallantmon Megidramon",
    "Renamon": "Relemon Viximon Renamon Kyubimon Youkomon Kuzuhamon Taomon Sakuyamon",
    "Impmon": "Keemon Yarmon Impmon Devimon SkullSatamon Beelzemon Wizardmon Mistymon",
    "Faul": "Numemon Sukamon Monzaemon Etemon KingEtemon",
}


def roster(raw: bytes) -> list[str]:
    strs = [s.decode("utf-8", "replace") for s in raw.split(b"\0") if len(s) >= 3]
    start = strs.index("Botamon")
    end = strs.index("Shiki", start)
    return strs[start:end]


def main(path: str) -> None:
    names = roster(open(path, "rb").read())
    low = {n.lower(): n for n in names}
    print(f"Digimon im Spiel: {len(names)}\n")
    for line, wanted in PLAN.items():
        parts = []
        for w in wanted.split():
            hit = low.get(w.lower()) or next((n for n in names if n.lower().startswith(w.lower() + " ")), None)
            parts.append(f"{w}{'' if hit else ' ✗'}" + (f" ({hit})" if hit and hit != w else ""))
        print(f"{line:8} " + ", ".join(parts))
    print("\nAlle Namen:", ", ".join(names))


if __name__ == "__main__":
    main(sys.argv[1])
