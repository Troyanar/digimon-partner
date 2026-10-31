# Digimon-Partner

Ein Digimon, das sich durch dein echtes Leben entwickelt: Wasser trinken, essen, fasten, trainieren.
Plan und Linien: **PLAN.md**. 3D-Modelle und Animationen stammen aus deiner Steam-Kopie von
*Digimon World Next Order* – nur privat, nicht weitergeben.

## Starten (Windows)
`start.bat` doppelklicken → http://localhost:8420. Beim ersten Mal ein Konto anlegen (das erste ist Admin,
braucht keinen Code). Freunde brauchen einen Einladungscode (Mehr → Freunde einladen).

**Test-Modus:** In der `.env` `DEV=1` setzen. Dann gibt es unter dem Partner Knöpfe zum Vorspulen der Zeit,
für Test-Training und zum Setzen einer Form (z. B. `f014`). Auf dem Server immer `DEV=0`.

## So funktioniert der Partner
- **Werte** (0–100): Hunger, Durst, Kraft, Geist, Disziplin, Laune. Sie sinken, solange du wach bist;
  in deiner Schlafenszeit (Mehr → Dein Tag) schläft dein Digimon und nichts sinkt.
- **Pflegefehler:** Hunger oder Durst 2 Stunden leer (beim Fasten zählt leerer Magen nicht).
- **Digitation:** Baby 1 Tag, In-Training 2 Tage, Rookie 1 Woche, Champion 2 Wochen, Ultimate 3 Wochen.
  Welcher Weg: mehr Krafttraining → Kraft-Weg, mehr Dehnen/Yoga → Geist-Weg, viele Pflegefehler → wild,
  kaum Training → Numemon, viel vernachlässigt → Sukamon. Paildramon nur per Jogress (kommt mit „Freunde“).
- **Fasten:** Start/Stopp; Ziel erreicht → Disziplin. Essen beendet das Fasten.
- **Endstufe:** dann kannst du ein neues Ei legen; dein Partner zieht in die Ruhmeshalle.

## Aufbau
- `app.py` Webserver (aiohttp), Login, API · `db.py` SQLite (`data/partner.db`) · `game.py` Spiel-Logik
- `lines.py` Linien und Regeln · `static/` Oberfläche (`viewer.js` = 3D mit three.js)
- `data/assets/<id>/` 3D-Daten für die Seite – nur für angemeldete Nutzer erreichbar
- `tests/` → `python -m unittest discover -s tests`

## 3D-Daten neu erzeugen
1. `werkzeuge/cpk.py` holt Modelle/Animationen aus `DigimonDataR.cpk` (nur lesend).
2. `werkzeuge/assetstudio_alle.ps1` (selbst starten) exportiert FBX mit AssetStudioMod.
3. `werkzeuge/galerie_daten.py` liest Animationen + Augen-Ebene aus.
4. `werkzeuge/assets_bauen.py` verkleinert alles nach `data/assets/`.
Vorschau aller Digimon: `vorschau-starten.bat` (Galerie).
