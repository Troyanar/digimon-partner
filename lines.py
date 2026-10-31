"""Die Entwicklungslinien (siehe PLAN.md). Modell-IDs aus Digimon World Next Order.

Jede Form hat eine Liste von Regeln (Bedingung, Ziel). Beim Stufenwechsel gewinnt die erste
erfüllte Regel. Der Faul-Weg (Numemon/Sukamon) wird in game.py vor diesen Regeln geprüft.

Bedingungen:
  immer     – kommt immer
  kraft     – mehr Krafttraining als Dehnen/Yoga in dieser Stufe
  geist     – mehr Dehnen/Yoga als Krafttraining
  wild      – viele Pflegefehler in dieser Stufe (aber trainiert)
  jogress   – Fusion mit einem Partner (Etappe Freunde); bis dahin wird gewartet
  comeback  – Faul-Digimon hat sich wieder aufgerappelt
  numemon   – Faul-Weg kam über Numemon (sonst Sukamon)
"""

STAGES = ["egg", "baby", "intraining", "rookie", "champion", "ultimate", "mega"]
STAGE_LABEL = {"egg": "Digi-Ei", "baby": "Baby", "intraining": "In-Training", "rookie": "Rookie",
               "champion": "Champion", "ultimate": "Ultimate", "mega": "Mega"}
# Wie lange eine Stufe dauert (Stunden). Danach wird digitiert. Mega bleibt.
STAGE_HOURS = {"egg": 0.05, "baby": 24, "intraining": 48, "rookie": 168, "champion": 336, "ultimate": 504}
# Wie lange ExVeemon/Stingmon auf einen Jogress-Partner warten (Stunden)
JOGRESS_WAIT_HOURS = 14 * 24

STAGE_OF_PREFIX = {"a": "baby", "b": "intraining", "c": "rookie", "d": "champion", "e": "ultimate", "f": "mega", "g": "mega"}

NAMES = {
    "a001": "Botamon", "b001": "Koromon", "c001": "Agumon", "d001": "Greymon", "e001": "MetalGreymon", "f001": "WarGreymon",
    "d053": "Greymon (Blue)", "e045": "MetalGreymon (Blue)", "f002": "ShineGreymon", "e026": "SkullGreymon", "f049": "BlackWarGreymon",
    "a002": "Punimon", "b002": "Tsunomon", "c002": "Gabumon", "d002": "Garurumon", "e002": "WereGarurumon", "f003": "MetalGarurumon",
    "d043": "Gururumon", "e029": "IceLeomon", "f075": "MagnaGarurumon", "d054": "Garurumon (Black)",
    "e046": "WereGarurumon (Black)", "f050": "MetalGarurumon (Black)",
    "a005": "Pabumon", "b005": "Motimon", "c009": "Veemon", "d009": "ExVeemon", "e009": "Paildramon", "f057": "Imperialdramon",
    "d020": "Veedramon", "e017": "AeroVeedramon", "f020": "UlforceVeedramon",
    "a008": "Conomon", "b006": "Tanemon", "c011": "Wormmon", "d011": "Stingmon", "e037": "Okuwamon", "f040": "GranKuwagamon",
    "e005": "MegaKabuterimon", "f007": "HerculesKabuterimon",
    "a010": "Pichimon", "b012": "Bukamon", "c006": "Gomamon", "d006": "Ikkakumon", "e006": "Zudomon", "f008": "Vikemon",
    "d032": "Seadramon", "e036": "MegaSeadramon", "f011": "MarineAngemon", "e053": "WaruSeadramon", "f039": "MetalSeadramon",
    "a006": "Jyarimon", "b007": "Gigimon", "c012": "Guilmon", "d010": "Growlmon", "e011": "WarGrowlmon", "f014": "Gallantmon",
    "g013": "Gallantmon Crimson Mode", "e028": "Megadramon", "f073": "Darkdramon", "e049": "BlackWarGrowlmon", "f051": "ChaosGallantmon",
    "a004": "YukimiBotamon", "b011": "Nyaromon", "c015": "Renamon", "d049": "Youkomon", "e052": "Doumon", "f052": "Kuzuhamon",
    "d015": "Kyubimon", "e014": "Taomon", "f017": "Sakuyamon",
    "a009": "Kuramon", "b010": "Tsumemon", "c027": "DemiDevimon", "d019": "Devimon", "e018": "Myotismon", "f021": "VenomMyotismon",
    "d018": "Wizardmon", "e019": "LadyDevimon", "f022": "Lilithmon", "d056": "IceDevimon", "f030": "Beelzemon",
    "d059": "Numemon", "d061": "Sukamon", "e056": "Monzaemon", "e055": "Etemon", "f055": "PlatinumNumemon", "f062": "KingSukamon",
}

LINES = {
    "agumon": {"egg": "Agumon", "egg_model": "egg01", "start": "a001", "evo": {
        "a001": [("immer", "b001")], "b001": [("immer", "c001")],
        "c001": [("kraft", "d001"), ("geist", "d053")],
        "d001": [("wild", "e026"), ("immer", "e001")], "e001": [("immer", "f001")],
        "d053": [("wild", "e026"), ("immer", "e045")], "e045": [("immer", "f002")],
        "e026": [("immer", "f049")],
    }},
    "gabumon": {"egg": "Gabumon", "egg_model": "egg02", "start": "a002", "evo": {
        "a002": [("immer", "b002")], "b002": [("immer", "c002")],
        "c002": [("wild", "d054"), ("kraft", "d002"), ("geist", "d043")],
        "d002": [("immer", "e002")], "e002": [("immer", "f003")],
        "d043": [("immer", "e029")], "e029": [("immer", "f075")],
        "d054": [("immer", "e046")], "e046": [("immer", "f050")],
    }},
    "veemon": {"egg": "Veemon", "egg_model": "egg16", "start": "a005", "evo": {
        "a005": [("immer", "b005")], "b005": [("immer", "c009")],
        "c009": [("kraft", "d009"), ("geist", "d020")],
        # ExVeemon: Paildramon nur per Jogress; ohne Partner nach der Wartezeit der Geist-Weg
        "d009": [("jogress", "e009"), ("immer", "e017")], "e009": [("immer", "f057")],
        "d020": [("immer", "e017")], "e017": [("immer", "f020")],
    }},
    "wormmon": {"egg": "Wormmon", "egg_model": "egg12", "start": "a008", "evo": {
        "a008": [("immer", "b006")], "b006": [("immer", "c011")],
        "c011": [("immer", "d011")],
        "d011": [("jogress", "e009"), ("kraft", "e037"), ("immer", "e005")],
        "e009": [("immer", "f057")], "e037": [("immer", "f040")], "e005": [("immer", "f007")],
    }},
    "gomamon": {"egg": "Gomamon", "egg_model": "egg10", "start": "a010", "evo": {
        "a010": [("immer", "b012")], "b012": [("immer", "c006")],
        "c006": [("kraft", "d006"), ("geist", "d032")],
        "d006": [("wild", "e053"), ("immer", "e006")], "e006": [("immer", "f008")],
        "d032": [("wild", "e053"), ("immer", "e036")], "e036": [("immer", "f011")],
        "e053": [("immer", "f039")],
    }},
    "guilmon": {"egg": "Guilmon", "egg_model": "egg06", "start": "a006", "evo": {
        "a006": [("immer", "b007")], "b007": [("immer", "c012")],
        "c012": [("immer", "d010")],
        # Growlmon teilt sich: Kraft -> WarGrowlmon, Geist -> Drachen-Weg, viele Fehler -> wild
        "d010": [("wild", "e049"), ("geist", "e028"), ("immer", "e011")],
        "e011": [("immer", "f014")], "e028": [("immer", "f073")], "e049": [("immer", "f051")],
    }},
    "renamon": {"egg": "Renamon", "egg_model": "egg07", "start": "a004", "evo": {
        "a004": [("immer", "b011")], "b011": [("immer", "c015")],
        "c015": [("kraft", "d049"), ("geist", "d015")],
        "d049": [("immer", "e052")], "e052": [("immer", "f052")],
        "d015": [("immer", "e014")], "e014": [("immer", "f017")],
    }},
    "demidevimon": {"egg": "DemiDevimon", "egg_model": "egg05", "start": "a009", "evo": {
        "a009": [("immer", "b010")], "b010": [("immer", "c027")],
        "c027": [("wild", "d056"), ("kraft", "d019"), ("geist", "d018")],
        "d019": [("immer", "e018")], "e018": [("immer", "f021")],
        "d018": [("immer", "e019")], "e019": [("immer", "f022")],
        "d056": [("immer", "f030")],
    }},
}

# Faul-Weg, gilt für alle Linien
FAUL_EVO = {
    "d059": [("comeback", "e056"), ("immer", "e055")],
    "d061": [("comeback", "e056"), ("immer", "e055")],
    "e055": [("numemon", "f055"), ("immer", "f062")],
}
FAUL_TRAINING, FAUL_PFLEGE, FAUL_ULTIMATE = "d059", "d061", "e055"

# Formwechsel nach einer perfekten Woche
FORM_CHANGE = {"f014": "g013"}
# Formen, die auf einen Jogress-Partner warten
JOGRESS_FORMS = {"d009": "d011", "d011": "d009"}
JOGRESS_TARGET = "e009"  # Paildramon


def stage_of(form: str) -> str:
    return "egg" if form == "egg" else STAGE_OF_PREFIX[form[0]]


def name_of(form: str) -> str:
    return "Digi-Ei" if form == "egg" else NAMES.get(form, form)


def all_forms() -> list[str]:
    forms = set(NAMES)
    return sorted(forms)
