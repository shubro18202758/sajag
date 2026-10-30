"""Mumbai, as the emulator needs it: one place for the city's constants.

Names, ids and formats follow the Mumbai city pack (``cities/mumbai/
city.json`` and ``landmarks.json``): the emulator never invents a place,
an agency or a plate format of its own.  ``tests/test_city.py`` checks the
copies below against the pack whenever the repository is present.

Everything the emulator produces is EMULATED (a feed stand-in) or
SIMULATED (a scenario); the few numbers here that model the city (the tide
phase, the Ganeshotsav calendar) say so where they are defined.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

__all__ = [
    "IST",
    "UNIT_ROLES",
    "UnitRole",
    "unit_label",
    "unit_role",
    "CITY_ID",
    "CITY_NAME",
    "FALLBACK_ANCHOR",
    "M_PER_DEG_LAT",
    "M_PER_DEG_LON",
    "PLATE_STATE",
    "PLATE_RTO_CODES",
    "PLATE_MARKER",
    "emulated_plate",
    "STOLEN_FIR_PLATE",
    "EARMARK_EXERCISE_PLATE",
    "STOLEN_FIR_REF",
    "PATROL_AGENCY",
    "PATROL_AGENCY_LABEL",
    "PATROL_UNIT_PREFIX",
    "PLACES",
    "place_name",
    "PUJA_NIGHTS",
    "puja_night_of",
    "is_monsoon",
    "M2_PERIOD_SEC",
    "tide_index",
]

#: India Standard Time: a fixed offset, no DST (no tz database needed).
IST = timezone(timedelta(hours=5, minutes=30))

CITY_ID = "mumbai"
CITY_NAME = {"en": "Mumbai", "mr": "मुंबई", "hi": "मुंबई"}

#: (lon, lat) of CSMT (landmarks.json ``csmt``): where an anchor-less tape
#: places its reads, deterministic on every host.
FALLBACK_ANCHOR = (72.8355, 18.9398)

#: Metres per degree on Mumbai's latitude belt: 111 320 m per degree of
#: latitude; longitude shrinks by cos(19.0176 deg) = 0.9454 (the pack's
#: centre; a fixed factor, so every host computes identical positions).
M_PER_DEG_LAT = 111320.0
M_PER_DEG_LON = 111320.0 * 0.9454

# ── number plates (city.json ``plates``) ────────────────────────────────────

#: Maharashtra marks: ``MH NN X[X] NNNN``.  The emulator writes them compact
#: (``MH01EM1234``, the form the oracle normalises every read to).
PLATE_STATE = "MH"
#: Plausible Mumbai office codes only (MH-01, MH-02, MH-03, MH-47; city.json
#: ``plates``).  The emulator never infers an office, a district or an owner
#: from a code.
PLATE_RTO_CODES = ("01", "02", "03", "47")
#: Every emulated plate carries the EM series right after the office code,
#: so a synthetic mark is self-labelling wherever it surfaces (``plate[4:6]``).
PLATE_MARKER = "EM"


def emulated_plate(rto: str, number: int) -> str:
    """An emulated MH mark: ``MH`` + office code + ``EM`` + 4 digits."""
    if rto not in PLATE_RTO_CODES:
        raise ValueError(f"office code {rto!r} is not one the emulator uses")
    return f"{PLATE_STATE}{rto}{PLATE_MARKER}{int(number) % 10000:04d}"


#: The demo plate a stolen-vehicle FIR names (the watchlist sweep's premise:
#: its stolen-FIR earmark is ensured at t0 as a labelled EMULATED
#: precondition, so its reads are evidence-only sightings, never a fine).
STOLEN_FIR_PLATE = "MH01EM9001"
#: The demo plate an operator earmark exercise names: its reads hit only once
#: a named duty officer has earmarked it.  The emulator never does.
EARMARK_EXERCISE_PLATE = "MH02EM4321"
#: The (emulated) FIR the sweep's premise names: a scenario reference, not a
#: real case.
STOLEN_FIR_REF = "FIR 4401/2026, Azad Maidan PS"

# ── agencies (city.json ``agencies``) ───────────────────────────────────────

#: Emulated patrol beats are Mumbai Traffic Police units: the C-A agency
#: code ``traffic`` (the oracle's closed agency registry).
PATROL_AGENCY = "traffic"
PATROL_AGENCY_LABEL = "Mumbai Traffic Police"
#: Unit ids carry the EM marker like every emulated plate.
PATROL_UNIT_PREFIX = "MTP-EM"


@dataclass(frozen=True)
class UnitRole:
    """What a living-city field unit is, from its id prefix (C-A agency code,
    label prefix, C-A status while it rides its beat, beat speed).  Speeds
    are MODELLED urban averages, not measurements."""

    agency: str
    label: str
    status: str
    speed_kmh: float
    beat_word: str


#: The living city's emulated field units by unit-id prefix (longest prefix
#: first).  Agencies are the oracle's closed C-A registry; statuses its
#: closed vocabulary ('available' is an ambulance (108) on a standby
#: circuit, not on a call).  Every id carries the EM marker.
UNIT_ROLES: tuple[tuple[str, UnitRole], ...] = (
    ("MP-EM-PCR", UnitRole("police", "Mumbai Police PCR", "patrol", 22.0, "beat")),
    ("108-EM-LC", UnitRole("ambulance", "Ambulance (108)", "available", 24.0, "standby circuit")),
    (PATROL_UNIT_PREFIX, UnitRole(PATROL_AGENCY, PATROL_AGENCY_LABEL, "patrol", 18.0, "beat")),
)


def unit_role(unit_id: str) -> UnitRole:
    """The role of a living-city unit id (ValueError on an unknown prefix)."""
    for prefix, role in UNIT_ROLES:
        if unit_id.startswith(prefix):
            return role
    raise ValueError(f"no living-city role for unit id {unit_id!r}")


def unit_label(unit_id: str, beat: str) -> str:
    """The unit's C-A label: '<agency> <id> · <beat> beat' (traffic and
    police) or '<agency> <id> · standby circuit, <roads>' (ambulance)."""
    role = unit_role(unit_id)
    if role.beat_word == "beat":
        return f"{role.label} {unit_id} · {beat} beat"
    return f"{role.label} {unit_id} · {role.beat_word}, {beat}"

# ── places (landmarks.json, verbatim) ───────────────────────────────────────

#: The landmarks the scenarios and the living city name, copied verbatim
#: from ``cities/mumbai/landmarks.json`` (id -> en / mr).
PLACES: dict[str, dict[str, str]] = {
    "csmt": {"en": "CSMT (Chhatrapati Shivaji Maharaj Terminus)", "mr": "छत्रपती शिवाजी महाराज टर्मिनस"},
    "churchgate": {"en": "Churchgate", "mr": "चर्चगेट"},
    "dadar": {"en": "Dadar station", "mr": "दादर स्थानक"},
    "dadar_tt": {"en": "Dadar TT Circle", "mr": "दादर टीटी सर्कल"},
    "hindmata": {"en": "Hindmata (Dadar East)", "mr": "हिंदमाता (दादर पूर्व)"},
    "parel": {"en": "Parel", "mr": "परळ"},
    "lalbaug": {"en": "Lalbaug", "mr": "लालबाग"},
    "kings_circle": {"en": "King's Circle (Matunga)", "mr": "किंग्ज सर्कल (माटुंगा)"},
    "sion_circle": {"en": "Sion Circle", "mr": "सायन सर्कल"},
    "mahim_causeway": {"en": "Mahim Causeway", "mr": "माहीम कॉजवे"},
    "kalanagar": {"en": "Kalanagar (Bandra East)", "mr": "कलानगर (वांद्रे पूर्व)"},
    "bkc": {"en": "Bandra Kurla Complex (BKC)", "mr": "वांद्रे कुर्ला संकुल"},
    "haji_ali": {"en": "Haji Ali junction", "mr": "हाजी अली जंक्शन"},
    "worli_naka": {"en": "Worli Naka", "mr": "वरळी नाका"},
    "acharya_atre_chowk": {"en": "Acharya Atre Chowk (Worli)", "mr": "आचार्य अत्रे चौक (वरळी)"},
    "milan_subway": {"en": "Milan Subway (Santacruz)", "mr": "मिलन सबवे (सांताक्रूझ)"},
    "andheri_subway": {"en": "Andheri Subway", "mr": "अंधेरी सबवे"},
    "andheri": {"en": "Andheri station", "mr": "अंधेरी स्थानक"},
    "weh_andheri": {"en": "Western Express Highway (Andheri)", "mr": "पश्चिम द्रुतगती महामार्ग (अंधेरी)"},
    "bandra": {"en": "Bandra station", "mr": "वांद्रे स्थानक"},
    "kurla": {"en": "Kurla station", "mr": "कुर्ला स्थानक"},
    "ltt": {"en": "Lokmanya Tilak Terminus (LTT)", "mr": "लोकमान्य टिळक टर्मिनस"},
    "ghatkopar": {"en": "Ghatkopar", "mr": "घाटकोपर"},
    "chembur": {"en": "Chembur", "mr": "चेंबूर"},
    "powai": {"en": "Powai (JVLR)", "mr": "पवई (जेव्हीएलआर)"},
    "borivali": {"en": "Borivali station", "mr": "बोरिवली स्थानक"},
    "airport_t2": {"en": "Mumbai Airport T2", "mr": "मुंबई विमानतळ टी२"},
    "airport_t1": {"en": "Mumbai Airport T1 (Santacruz)", "mr": "मुंबई विमानतळ टी१ (सांताक्रूझ)"},
    "sea_link": {"en": "Bandra–Worli Sea Link", "mr": "वांद्रे–वरळी सागरी सेतू"},
    "atal_setu": {"en": "Atal Setu (Sewri end)", "mr": "अटल सेतू (शिवडी टोक)"},
    "mantralaya": {"en": "Mantralaya", "mr": "मंत्रालय"},
    "bmc_hq": {"en": "BMC headquarters", "mr": "बृहन्मुंबई महानगरपालिका मुख्यालय"},
    "police_hq": {"en": "Mumbai Police headquarters (Crawford Market)", "mr": "मुंबई पोलीस मुख्यालय (क्रॉफर्ड मार्केट)"},
    "traffic_hq": {"en": "Mumbai Traffic Police headquarters (Worli)", "mr": "मुंबई वाहतूक पोलीस मुख्यालय (वरळी)"},
    "wankhede": {"en": "Wankhede Stadium", "mr": "वानखेडे स्टेडियम"},
    "marine_drive": {"en": "Marine Drive", "mr": "मरीन ड्राइव्ह"},
    "girgaon_chowpatty": {"en": "Girgaon Chowpatty", "mr": "गिरगाव चौपाटी"},
    "gateway": {"en": "Gateway of India", "mr": "गेटवे ऑफ इंडिया"},
    "shivaji_park": {"en": "Shivaji Park", "mr": "शिवाजी पार्क"},
    "juhu_beach": {"en": "Juhu Beach", "mr": "जुहू चौपाटी"},
    "lalbaugcha_raja": {"en": "Lalbaugcha Raja", "mr": "लालबागचा राजा"},
    "gsb_kings_circle": {"en": "GSB Seva Mandal (King's Circle)", "mr": "जीएसबी सेवा मंडळ (किंग्ज सर्कल)"},
    "kem": {"en": "KEM Hospital", "mr": "केईएम रुग्णालय"},
    "sion_hospital": {"en": "Sion Hospital (LTMGH)", "mr": "सायन रुग्णालय"},
    "jj_hospital": {"en": "JJ Hospital", "mr": "जे.जे. रुग्णालय"},
    "nair_hospital": {"en": "Nair Hospital", "mr": "नायर रुग्णालय"},
    "cooper_hospital": {"en": "Cooper Hospital", "mr": "कूपर रुग्णालय"},
    "haji_ali_ps": {"en": "Haji Ali pumping station", "mr": "हाजी अली उदंचन केंद्र"},
    "irla_ps": {"en": "Irla pumping station", "mr": "इर्ला उदंचन केंद्र"},
    "love_grove_ps": {"en": "Love Grove pumping station", "mr": "लव्ह ग्रोव्ह उदंचन केंद्र"},
    "cleveland_bunder_ps": {"en": "Cleveland Bunder pumping station", "mr": "क्लिव्हलँड बंदर उदंचन केंद्र"},
    "britannia_ps": {"en": "Britannia pumping station (Reay Road)", "mr": "ब्रिटानिया उदंचन केंद्र (रे रोड)"},
    "gazdarbandh_ps": {"en": "Gazdarbandh pumping station (Khar)", "mr": "गझदरबंध उदंचन केंद्र (खार)"},
    "mithi_kurla": {"en": "Mithi River (Kurla)", "mr": "मिठी नदी (कुर्ला)"},
    "apollo_bunder": {"en": "Apollo Bunder tide station", "mr": "अपोलो बंदर भरती केंद्र"},
    "raj_bhavan": {"en": "Raj Bhavan (Malabar Hill)", "mr": "राजभवन (मलबार हिल)"},
}


def place_name(place_id: str, lang: str = "en") -> str:
    """A landmark's canonical name (``KeyError`` for an unknown id: the
    emulator never names a place the city pack does not)."""
    return PLACES[place_id][lang]


# ── the city's calendar ─────────────────────────────────────────────────────

#: Ganeshotsav's three busiest nights by year: the two nights before Anant
#: Chaturdashi and the visarjan night itself, when the Lalbaugcha Raja
#: queues and the processions to the chowpatties peak.  (The festival nights
#: keep the code name PUJA_NIGHTS / ``puja`` and the EMULATOR_PUJA_NIGHTS
#: override.)  2025 is the observed calendar (Anant Chaturdashi 6 Sep 2025);
#: 2026 is an APPROXIMATION from the lunar calendar (±1 day: Ganesh
#: Chaturthi 14 Sep, Anant Chaturdashi 25 Sep) — confirm against the year's
#: almanac, or override with EMULATOR_PUJA_NIGHTS.  A festival night runs
#: 18:00 to 04:00 the next morning.
PUJA_NIGHTS: dict[int, tuple[date, ...]] = {
    2025: (date(2025, 9, 4), date(2025, 9, 5), date(2025, 9, 6)),
    2026: (date(2026, 9, 23), date(2026, 9, 24), date(2026, 9, 25)),
}

#: Festival crowds peak from 18:00 into the small hours.
PUJA_NIGHT_START_H = 18.0
PUJA_NIGHT_END_H = 4.0


def puja_night_of(d: date, hour: float, nights: tuple[date, ...] | None = None) -> date | None:
    """The festival night (its evening's date) that IST ``d`` at ``hour`` falls
    in, or None.  ``nights`` overrides the calendar (the config's list)."""
    pool = nights if nights is not None else PUJA_NIGHTS.get(d.year, ()) + PUJA_NIGHTS.get(
        d.year - 1, ())
    if hour >= PUJA_NIGHT_START_H and d in pool:
        return d
    prev = d - timedelta(days=1)
    if hour < PUJA_NIGHT_END_H and prev in pool:
        return prev
    return None


def is_monsoon(d: date) -> bool:
    """Mumbai's south-west monsoon months: June to September."""
    return 6 <= d.month <= 9


#: Mumbai drains to the Arabian Sea: at high water the sea outfalls close and
#: the storm-water pumps carry the load, so rain then waterlogs worse (BMC:
#: a heavy burst at a ~4.5 m tide floods the low spots).  The emulator uses
#: a MODELLED semidiurnal phase (the M2 period, 12 h 25 min) from a fixed
#: reference high water; it is not the Apollo Bunder tide table (the hydro
#: service carries the real tide model).
M2_PERIOD_SEC = 44712.0
_TIDE_REFERENCE_HW = datetime(2026, 1, 1, 6, 0, tzinfo=IST)


def tide_index(t: datetime) -> float:
    """MODELLED tide phase at ``t``: 1.0 at high water, 0.0 at low water."""
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    phase = ((t - _TIDE_REFERENCE_HW).total_seconds() % M2_PERIOD_SEC) / M2_PERIOD_SEC
    return round(0.5 * (1.0 + math.cos(2.0 * math.pi * phase)), 4)
