"""Synthetic defect sentences (fictional) for the defect text classifier and the seed script."""
import random
import re

CATEGORIES = ["Engine", "Hydraulics", "Avionics", "Landing gear", "Fuel", "Electrical", "Airframe", "Environmental control"]

# Aviation abbreviations are expanded before the text reaches TF-IDF.
ABBREV = {
    "hyd": "hydraulic", "mlg": "main landing gear", "nlg": "nose landing gear", "ecs": "environmental control system",
    "qty": "quantity", "eng": "engine", "gen": "generator", "batt": "battery", "nav": "navigation",
    "comm": "communication", "temp": "temperature", "press": "pressure", "ind": "indication", "sys": "system",
    "lh": "left", "rh": "right", "egt": "exhaust gas temperature", "apu": "auxiliary power unit",
    "mfd": "multi function display", "ins": "inertial navigation system", "cb": "circuit breaker",
}
_TOKEN = re.compile(r"[a-z0-9]+")


def expand(text: str) -> str:
    return " ".join(ABBREV.get(w, w) for w in _TOKEN.findall(text.lower()))


_SIDE = ["left", "right", "LH", "RH", "no. 1", "no. 2"]
_TEMPLATES = {
    "Engine": [
        "eng {n} EGT high on take-off", "eng {n} vibration above limit at cruise", "oil pressure fluctuating on eng {n}",
        "metal chips found on eng {n} magnetic plug", "eng {n} slow to start, hung start", "compressor stall heard on eng {n} during accel",
        "eng {n} oil consumption high", "nozzle actuator on eng {n} sticking", "eng {n} surge at high altitude",
        "borescope shows HPC blade nick on eng {n}", "eng {n} afterburner fails to light", "turbine blade tip rub found on eng {n}",
    ],
    "Hydraulics": [
        "hyd leak near {side} MLG actuator", "hyd press low on system {n}", "hyd fluid seep at {side} brake line union",
        "hyd pump {n} noisy, pressure drops", "hyd reservoir level low after flight", "hyd accumulator pre-charge low",
        "hyd leak at {side} aileron actuator seal", "hyd filter clog indicator popped on sys {n}", "hyd return line chafed near {side} wheel well",
        "hyd fluid contaminated, sample failed", "hyd leak near NLG steering actuator", "hyd pressure slow to build on sys {n}",
    ],
    "Avionics": [
        "radar display blank intermittently", "INS drift excessive after 1 hour", "nav system fails self test",
        "comm radio {n} weak transmit", "MFD {side} flickers in flight", "radar altimeter reads erratic",
        "IFF transponder no reply on test", "mission computer reset in flight", "HUD symbology jitters",
        "weapons interface bus fault on power-up", "GPS not acquiring satellites", "autopilot disengages by itself",
    ],
    "Landing gear": [
        "nose wheel steering sluggish", "{side} MLG tyre worn to limit", "NLG shimmy on taxi", "gear retraction slow, {side} MLG lags",
        "{side} MLG door not closing flush", "brake wear indicator at limit {side} wheel", "NLG shock strut low extension",
        "gear down-lock indication intermittent {side} MLG", "anti-skid fault light on landing", "{side} wheel bearing rough on spin check",
        "NLG tyre cut found on walk-round", "MLG uplock roller worn {side}",
    ],
    "Fuel": [
        "intermittent fuel qty indication", "fuel leak at {side} wing tank access panel", "fuel boost pump {n} low pressure",
        "fuel transfer from drop tank slow", "fuel qty gauge reads zero on {side} tank", "fuel smell in bay after refuel",
        "fuel filter bypass light on", "refuel valve stuck open on {side} tank", "fuel flow reading fluctuates eng {n}",
        "fuel tank vent blocked", "water found in fuel sample", "fuel pump {n} noisy on ground run",
    ],
    "Electrical": [
        "gen {n} drops off line in flight", "batt voltage low before start", "CB for pitot heat trips repeatedly",
        "{side} landing light inoperative", "wiring chafed behind instrument panel", "inverter fails on load",
        "gen {n} overheat warning", "external power will not connect", "cockpit lighting dimmer faulty",
        "bus tie contactor stuck", "batt charger fault light", "anti-collision light out",
    ],
    "Airframe": [
        "crack found on {side} wing root fairing", "corrosion on {side} fuselage skin panel", "loose rivets on {side} tail fin",
        "canopy seal torn", "dent on {side} leading edge from bird strike", "access panel fastener missing {side} side",
        "paint blistered on {side} intake lip", "delamination on radome", "{side} flap hinge bracket worn",
        "canopy scratch in pilot field of view", "skin wrinkle near {side} stabiliser", "drain hole blocked in aft fuselage",
    ],
    "Environmental control": [
        "ECS duct temp high on climb", "cockpit not cooling on ground", "cabin pressure fluctuates at altitude",
        "ECS bleed valve stuck", "oxygen system pressure low", "ECS turbine noisy", "smell of fumes from air conditioning",
        "avionics bay cooling fan failed", "cockpit temp control not responding", "ECS water separator blocked",
        "canopy demist weak", "cabin altitude warning in cruise",
    ],
}


def synthetic_defects(n: int = 200, seed: int = 42) -> list[tuple[str, str]]:
    """Returns n (text, category) pairs, balanced across the 8 categories."""
    rng = random.Random(seed)
    out = []
    per = n // len(CATEGORIES)
    for cat in CATEGORIES:
        for i in range(per):
            t = _TEMPLATES[cat][i % len(_TEMPLATES[cat])]
            text = t.format(side=rng.choice(_SIDE), n=rng.choice([1, 2]))
            if i >= len(_TEMPLATES[cat]):  # second pass: small wording changes so sentences are not identical
                text = rng.choice(["", "pilot reports ", "found on inspection: ", "after sortie, "]) + text + rng.choice(["", ", needs check", ", rectify", " again"])
            out.append((text, cat))
    rng.shuffle(out)
    return out
