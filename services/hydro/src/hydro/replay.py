"""Replay of the 18–19 August 2025 Mumbai storm — the nowcast model run on the real dates.

What happened (as reported; every figure carries its source in ``SRC``):

* IMD (via the Free Press Journal, 19 Aug 08:39): 20:30 IST on 18 Aug to 05:30 on 19 Aug — Vikhroli 194.5
  mm, Santacruz 185, Juhu 173.5, Byculla 167, Bandra 157, Colaba 79.8, Mahalaxmi 71.9.
* IMD (via PTI, 19 Aug 09:40): 24 h to 08:30 on 19 Aug — Vikhroli 255.5 mm, Byculla 241, Santacruz 238.2,
  Juhu 221.5, Bandra 211, Colaba 110.4, Mahalaxmi 72.5.
* IMD (via PTI, 20 Aug): 24 h to 08:30 on 20 Aug — Vikhroli 229.5 mm, Santacruz 209, Byculla 193.5, Juhu
  150, Bandra 137.5, Colaba 107.4.
* BMC (via PTI, 19 Aug 18:01): 04:00–15:00 on 19 Aug — Vikhroli East 268 mm, Marol 262, Powai 257, Versova
  250, F-South (Forsbery reservoir) 220; the six major pumping stations (43 pumps) ran over 761 pump-hours
  in 16–19 Aug and 540 mobile pumps worked on the 19th. The Chief Minister's office: more than 150 mm
  between 04:00 and 11:00. The Mithi rose to 3.9 m (danger mark 4 m) and about 350 people were moved
  from Kranti Nagar, Kurla (Business Today, 19 Aug).
* The BMC's tide table for the morning high water: 3.75 m at 09:16 (as reported; the model gives 09:04,
  3.97 m — see ``tide``).

Two runs, both honest about their rain:

* ``open_meteo_archive`` — Open-Meteo's historical archive (reanalysis / NWP based) hourly precipitation
  at the fixed point set (a live call). Gridded products smooth a convective monsoon storm; the run reports
  what the grid carried and what the model makes of it.
* ``imd_gauge_anchored`` — the same model driven by the observed totals: the IMD stations' windows above
  (OBSERVED), spread over 15-minute steps (MODELLED): inside each window in proportion to the Open-Meteo
  archive's hourly rain at the nearest point (gauge totals, archive timing — flat where the archive is
  dry); the part of the 24-h total to 08:30 not in the overnight window is put in 05:30–08:30 (some of it
  fell on 18 Aug, so this leans early); the 24-h total to 08:30 on 20 Aug is put 75 % in 08:30–15:00 and
  25 % in 15:00–20:30 (between the 61 % and 82 % implied by the BMC's 04:00–15:00 gauges and the CMO's
  04:00–11:00 figure). Station positions are APPROXIMATE (±1 km). 40–65 mm in an hour was reported over
  Parel, Dadar and Worli that morning, a check on the modelled peaks.
* ``imd_gauge_flat_sensitivity`` — the same totals flat within each window, to show how much the timing
  matters.

Tide: the Apollo Bunder model for those dates (MODELLED). Pumps: all available — the BMC reported its
pumping stations working through the storm; the EMULATED adapter is not consulted.

The model's flags are compared with places the news reported waterlogged or closed (``REPORTED``), with the
time of the first report found. A report's time is when it was published, not when the water rose, so a
"lead before the first report" is an upper bound on the real lead; an evening round-up published after the
replay window gives no lead at all (it says where, not when). News names places, not every street: a
flag with no report is not counted as a false alarm.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from hydro.model import CLASS_BANDS
from hydro.network import haversine_m
from hydro.nowcast import Hydro
from hydro.rain import POINTS, RainPoint, idw, quarter_series

__all__ = ["EVENTS", "DEFAULT_EVENT", "REPORTED", "IMD_STATIONS", "IMD_WINDOWS", "BMC_0400_1500",
           "C_SPLIT", "MAY_STATIONS", "MAY_12H", "MAY_HOUR_0910", "REPORTED_MAY", "station_series", "replay"]

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_EVENT = "2025-08-19"
EVENTS = {"2025-08-19": {"start_ist": datetime(2025, 8, 18, 20, 0, tzinfo=IST),
                         "end_ist": datetime(2025, 8, 19, 21, 0, tzinfo=IST),
                         "title": "Mumbai storm, 18–19 August 2025",
                         "snapshot_ist": datetime(2025, 8, 19, 7, 30, tzinfo=IST)},
          "2025-05-26": {"start_ist": datetime(2025, 5, 25, 22, 0, tzinfo=IST),
                         "end_ist": datetime(2025, 5, 26, 15, 0, tzinfo=IST),
                         "title": "Mumbai's earliest monsoon onset in decades, 26 May 2025",
                         "snapshot_ist": datetime(2025, 5, 26, 8, 0, tzinfo=IST)}}

SRC = {
    "fpj_imd_0839": {"publisher": "Free Press Journal (IMD 20:30–05:30 figures; places)", "date": "2025-08-19",
                     "time_ist": "08:39",
                     "url": "https://www.freepressjournal.in/mumbai/mumbai-rains-city-reels-under-relentless-"
                            "downpour-sion-matunga-dadar-byculla-flooded-andheri-subway-closed-schools-colleges-"
                            "shut-as-imd-issues-red-alert"},
    "pti_imd_24h_0819": {"publisher": "PTI via Editorji (IMD 24 h to 08:30, 19 Aug)", "date": "2025-08-19",
                         "time_ist": "09:40",
                         "url": "https://www.editorji.com/amp/india-news/maharashtra/heavy-rains-in-mumbai-"
                                "suburbs-record-over-200-mm-downpour-in-24-hrs-vikhroli-tops-chart-1755576650357"},
    "pti_imd_24h_0820": {"publisher": "PTI via The Week (IMD 24 h to 08:30, 20 Aug)", "date": "2025-08-20",
                         "url": "https://www.theweek.in/wire-updates/national/2025/08/20/bom5-mh-rains-data.html"},
    "pti_bmc_0819": {"publisher": "PTI via ThePrint (BMC gauges 04:00–15:00; pumping)", "date": "2025-08-19",
                     "time_ist": "18:01",
                     "url": "https://theprint.in/india/mumbai-receives-over-200-mm-of-rain-in-11-hours/2724336"},
    "bt_0819": {"publisher": "Business Today (CMO: 150 mm 04:00–11:00; Mithi 3.9 m; Kurla relocations)",
                "date": "2025-08-19", "time_ist": "15:53",
                "url": "https://www.businesstoday.in/india/story/mumbai-rains-inundate-roads-lead-to-flight-and-"
                       "train-delays-350-people-from-kurla-relocated-top-points-490083-2025-08-19"},
    "indiacom_1020": {"publisher": "India.com", "date": "2025-08-19", "time_ist": "10:20",
                      "url": "https://www.india.com/news/india/mumbai-rains-roads-subways-closed-mumbai-palghar-"
                             "thane-raigad-nasik-pune-satara-mrunaltai-gore-flyover-at-goregaon-lokhandwala-veera-"
                             "desai-roadandheri-matunga-chembur-khar-dadar-east-kurla-8019474/"},
    "watchers": {"publisher": "Watchers", "date": "2025-08-19", "time_ist": "20:05",
                 "url": "https://watchers.news/2025/08/19/extreme-rainfall-paralyzes-mumbai-three-dead-two-missing/"},
    "fpj_0526_2315": {"publisher": "Free Press Journal (12-h station totals; places; pumps not running)",
                      "date": "2025-05-26", "time_ist": "23:15",
                      "url": "https://www.freepressjournal.in/mumbai/monsoon-mayhem-mumbai-flooded-after-early-rains-"
                             "bmc-blames-imd-faces-flak-for-unpreparedness"},
    "fpj_0526_1112": {"publisher": "Free Press Journal (09:00–10:00 hourly figures; BMC-reported spots)",
                      "date": "2025-05-26", "time_ist": "11:12",
                      "url": "https://www.freepressjournal.in/mumbai/mumbai-rains-city-lashed-by-heavy-showers-"
                             "nariman-point-records-104-mm-in-one-hour"},
    "newsarena_0526": {"publisher": "News Arena India", "date": "2025-05-26", "time_ist": "20:25",
                       "url": "https://newsarenaindia.com/nation/mumbai-paralysed-by-record-rain-on-monsoon-s-first-"
                              "day/45518"},
    "pti_0528": {"publisher": "PTI via The Week (mini pumping stations failed on 26 May)", "date": "2025-05-28",
                 "url": "https://www.theweek.in/wire-updates/national/2025/05/28/bom2-mh-waterlogging-penalty.html"},
    "pti_tide_0527": {"publisher": "PTI via Editorji (BMC: 27 May high tides 4.88 m at 12:13, 4.18 m at 23:56)",
                      "date": "2025-05-27",
                      "url": "https://www.editorji.com/amp/india-news/mumbai-rains-brief-halt-high-tide-alert-issued-"
                             "1748322079762"},
    "tide_bmc": {"publisher": "BMC tide timing as reported (3.75 m at 09:16; one outlet dates it 20 Aug)",
                 "date": "2025-08-19",
                 "url": "https://www.freepressjournal.in/mumbai/mumbai-rains-400-families-evacuated-as-mithi-"
                        "river-crosses-danger-mark"},
}

#: IMD stations (id, name, lat, lon) — positions APPROXIMATE (±1 km)
IMD_STATIONS = [
    ("santacruz", "Santacruz observatory", 19.090, 72.850), ("colaba", "Colaba observatory", 18.900, 72.817),
    ("vikhroli", "Vikhroli", 19.110, 72.928), ("byculla", "Byculla", 18.979, 72.835),
    ("juhu", "Juhu", 19.098, 72.834), ("bandra", "Bandra", 19.055, 72.835),
    ("mahalaxmi", "Mahalaxmi", 18.983, 72.819),
]

#: OBSERVED station totals (mm) by window; None = not reported
IMD_WINDOWS: dict[str, dict[str, float | None]] = {
    # 18 Aug 20:30 → 19 Aug 05:30 IST (fpj_imd_0839)
    "night": {"vikhroli": 194.5, "santacruz": 185.0, "juhu": 173.5, "byculla": 167.0, "bandra": 157.0,
              "colaba": 79.8, "mahalaxmi": 71.9},
    # 24 h to 19 Aug 08:30 IST (pti_imd_24h_0819)
    "day1_24h": {"vikhroli": 255.5, "santacruz": 238.2, "byculla": 241.0, "juhu": 221.5, "bandra": 211.0,
                 "colaba": 110.4, "mahalaxmi": 72.5},
    # 24 h to 20 Aug 08:30 IST (pti_imd_24h_0820)
    "day2_24h": {"vikhroli": 229.5, "santacruz": 209.0, "byculla": 193.5, "juhu": 150.0, "bandra": 137.5,
                 "colaba": 107.4, "mahalaxmi": None},
}
#: BMC gauges, 19 Aug 04:00–15:00 IST (pti_bmc_0819) — context and the split check, not a model input
BMC_0400_1500 = {"Vikhroli East": 268.0, "Marol": 262.0, "Passpoli (Powai)": 257.0, "Versova": 250.0,
                 "Forsbery reservoir (F-South)": 220.0}
#: share of the 24 h to 20 Aug 08:30 placed in 08:30–15:00 on 19 Aug (MODELLED; module doc)
C_SPLIT = 0.75

#: places reported waterlogged or closed, with the earliest report found (point within 600 m of a road
#: segment, bridge decks excluded)
REPORTED: list[dict[str, Any]] = [
    {"name": "King's Circle (Matunga)", "lat": 19.0278, "lon": 72.85649, "reported_ist": "06:20",
     "src": ["fpj_imd_0839", "indiacom_1020"], "what": "water on the road at 06:20 (post quoted by FPJ)"},
    {"name": "Andheri Subway", "lat": 19.1148, "lon": 72.84742, "reported_ist": "08:39",
     "src": ["fpj_imd_0839", "indiacom_1020"], "what": "closed to traffic"},
    {"name": "Gandhi Market (Sion–Matunga)", "lat": 19.0306, "lon": 72.8590, "reported_ist": "08:39",
     "src": ["fpj_imd_0839", "indiacom_1020"], "what": "knee-deep water"},
    {"name": "Byculla", "lat": 18.9790, "lon": 72.8350, "reported_ist": "08:39",
     "src": ["fpj_imd_0839", "watchers"], "what": "knee-deep water"},
    {"name": "Dadar (Dadar TT, Hindu Colony)", "lat": 19.01753, "lon": 72.84811, "reported_ist": "08:39",
     "src": ["fpj_imd_0839", "indiacom_1020"], "what": "knee-deep water"},
    {"name": "Vile Parle", "lat": 19.0990, "lon": 72.8440, "reported_ist": "08:39", "src": ["fpj_imd_0839"],
     "what": "knee-deep water"},
    {"name": "Sion", "lat": 19.04231, "lon": 72.86345, "reported_ist": "08:39", "src": ["fpj_imd_0839"],
     "what": "flooded (headline: Sion, Matunga)"},
    {"name": "Hindmata (Dadar East)", "lat": 19.00561, "lon": 72.83976, "reported_ist": "10:20",
     "src": ["indiacom_1020"], "what": "waterlogged"},
    {"name": "Khar", "lat": 19.0700, "lon": 72.8370, "reported_ist": "10:20", "src": ["indiacom_1020"],
     "what": "parts waterlogged"},
    {"name": "Chembur", "lat": 19.062, "lon": 72.9, "reported_ist": "10:20", "src": ["indiacom_1020", "watchers"],
     "what": "parts waterlogged"},
    {"name": "Kurla (Kranti Nagar, by the Mithi)", "lat": 19.073, "lon": 72.878, "reported_ist": "15:53",
     "src": ["bt_0819", "watchers"], "what": "Mithi at 3.9 m; about 350 people moved"},
    {"name": "Wadala", "lat": 19.0170, "lon": 72.8650, "reported_ist": "20:05", "src": ["watchers"],
     "what": "waterlogged"},
    {"name": "Goregaon (Oberoi junction, WEH)", "lat": 19.1736, "lon": 72.8605, "reported_ist": "20:05",
     "src": ["watchers"], "what": "traffic slowed by waterlogging (Mumbai Traffic Police post)"},
    {"name": "Sewri station", "lat": 19.0000, "lon": 72.8570, "reported_ist": "10:20", "src": ["indiacom_1020"],
     "what": "waterlogged"},
    {"name": "N M Joshi Marg", "lat": 18.9935, "lon": 72.8285, "reported_ist": "10:20", "src": ["indiacom_1020"],
     "what": "waterlogged"},
    {"name": "Poisar Subway (Kandivali)", "lat": 19.2050, "lon": 72.8520, "reported_ist": "10:20",
     "src": ["indiacom_1020"], "what": "closed to vehicles"},
]


# ── 26 May 2025 ─────────────────────────────────────────────────────────────
#: rain stations named in the reports (id, name, lat, lon) — positions APPROXIMATE (±1 km)
MAY_STATIONS = [
    ("nariman_point", "Nariman Point", 18.9256, 72.8242), ("csmt", "CSMT", 18.9398, 72.8355),
    ("colaba", "Colaba", 18.9070, 72.8150), ("grant_road", "Grant Road", 18.9630, 72.8150),
    ("malabar_hill", "Malabar Hill", 18.9550, 72.8030), ("worli", "Worli", 19.0100, 72.8170),
    ("haji_ali", "Haji Ali", 18.9781, 72.8114), ("santacruz", "Santacruz", 19.0820, 72.8410),
    ("dadar", "Dadar", 19.0186, 72.8436), ("bandra", "Bandra", 19.0544, 72.8406),
    ("dharavi", "Dharavi", 19.0420, 72.8540), ("chembur", "Chembur", 19.0620, 72.9000),
    ("lower_parel", "Lower Parel", 18.9950, 72.8300), ("kurla", "Kurla", 19.0650, 72.8790),
]
#: OBSERVED 12-h totals, 23:00 on 25 May → 11:00 on 26 May IST (fpj_0526_2315; the window is stated for the
#: top four, the rest are listed with them)
MAY_12H = {"nariman_point": 252.0, "csmt": 215.0, "colaba": 207.0, "grant_road": 202.0, "malabar_hill": 136.0,
           "worli": 130.0, "haji_ali": 123.0, "santacruz": 107.0, "dadar": 103.0, "bandra": 90.0,
           "dharavi": 89.0, "chembur": 82.0, "lower_parel": 81.0, "kurla": 76.0}
#: OBSERVED 09:00–10:00 IST (fpj_0526_1112)
MAY_HOUR_0910 = {"nariman_point": 104.0, "colaba": 83.0, "csmt": 80.0, "malabar_hill": 63.0}
#: pump availability as reported for 26 May: the Hindmata, Gandhi Market and Yellow Gate mini stations were not
#: running and Chunabhatti's ran below capacity (pti_0528; fpj_0526_2315); the major stations are not reported
#: down (assumed available)
MAY_PUMPS = {"hindmata_mps": 0.0, "gandhi_market_mps": 0.0, "yellow_gate_mps": 0.0, "chunabhatti_mps": 0.5}

REPORTED_MAY: list[dict[str, Any]] = [
    {"name": "Sion Circle", "lat": 19.04231, "lon": 72.86345, "reported_ist": "11:12",
     "src": ["fpj_0526_1112", "fpj_0526_2315"], "what": "waterlogged (BMC)"},
    {"name": "Dadar TT", "lat": 19.01753, "lon": 72.84811, "reported_ist": "11:12",
     "src": ["fpj_0526_1112", "fpj_0526_2315"], "what": "waterlogged (BMC)"},
    {"name": "Five Gardens (Dadar)", "lat": 19.0215, "lon": 72.8517, "reported_ist": "11:12",
     "src": ["fpj_0526_1112"], "what": "waterlogged (BMC)"},
    {"name": "Worli", "lat": 19.00629, "lon": 72.81826, "reported_ist": "11:12", "src": ["fpj_0526_1112"],
     "what": "waterlogged (BMC); the Worli underground metro station flooded"},
    {"name": "Mantralaya / Nariman Point", "lat": 18.9275, "lon": 72.8255, "reported_ist": "20:25",
     "src": ["newsarena_0526", "fpj_0526_2315"], "what": "waterlogged"},
    {"name": "Hindmata (Dadar East)", "lat": 19.00561, "lon": 72.83976, "reported_ist": "23:15",
     "src": ["fpj_0526_2315", "pti_0528"], "what": "severe waterlogging; its pumps were not yet running"},
    {"name": "King's Circle (Matunga)", "lat": 19.0278, "lon": 72.85649, "reported_ist": "23:15",
     "src": ["fpj_0526_2315"], "what": "waterlogged"},
    {"name": "Gandhi Market (Sion–Matunga)", "lat": 19.0306, "lon": 72.8590, "reported_ist": "23:15",
     "src": ["fpj_0526_2315", "pti_0528"], "what": "waterlogged; its pumping system failed"},
    {"name": "KEM Hospital (Parel)", "lat": 19.0026, "lon": 72.842, "reported_ist": "23:15",
     "src": ["fpj_0526_2315"], "what": "rainwater entered the hospital"},
    {"name": "CSMT exit", "lat": 18.9398, "lon": 72.8355, "reported_ist": "23:15", "src": ["fpj_0526_2315"],
     "what": "waterlogged"},
    {"name": "Churchgate station", "lat": 18.9353, "lon": 72.8274, "reported_ist": "23:15",
     "src": ["fpj_0526_2315"], "what": "waterlogged"},
    {"name": "Below the JJ flyover", "lat": 18.9600, "lon": 72.8330, "reported_ist": "23:15",
     "src": ["fpj_0526_2315"], "what": "waterlogged"},
    {"name": "Breach Candy (old US consulate)", "lat": 18.9690, "lon": 72.8060, "reported_ist": "23:15",
     "src": ["fpj_0526_2315"], "what": "waterlogged"},
    {"name": "Oval Maidan roads", "lat": 18.9290, "lon": 72.8290, "reported_ist": "23:15",
     "src": ["fpj_0526_2315"], "what": "waterlogged"},
    {"name": "Masjid Bunder", "lat": 18.9500, "lon": 72.8380, "reported_ist": "23:15", "src": ["fpj_0526_2315"],
     "what": "mini pumping station not working; water on the tracks"},
    {"name": "Wadala", "lat": 19.0170, "lon": 72.8650, "reported_ist": "23:15", "src": ["fpj_0526_2315"],
     "what": "waterlogged (visuals)"},
]


def _ist(y: int, mo: int, d: int, h: int, mi: int) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=IST)


def _filled(window: str) -> dict[str, float]:
    """A window's station totals, the unreported ones filled by IDW from the reported (MODELLED)."""
    vals = IMD_WINDOWS[window]
    known = [(k, v) for k, v in vals.items() if v is not None]
    pos = {k: (la, lo) for k, _n, la, lo in IMD_STATIONS}
    out = {k: float(v) for k, v in known}
    for k, v in vals.items():
        if v is None:
            w = np.array([1.0 / max(haversine_m(*pos[k], *pos[j]), 300.0) ** 2 for j, _ in known])
            out[k] = float(np.sum(w * np.array([x for _, x in known])) / w.sum())
    return out


Piece = tuple[list[tuple[datetime, datetime]], float, bool]  # (intervals, mm, timed by the archive?)


def _pieces(station: str, event: str = DEFAULT_EVENT) -> list[Piece]:
    if event == "2025-05-26":
        a, b = _ist(2025, 5, 25, 23, 0), _ist(2025, 5, 26, 11, 0)
        h0, h1 = _ist(2025, 5, 26, 9, 0), _ist(2025, 5, 26, 10, 0)
        total = MAY_12H[station]
        hour = MAY_HOUR_0910.get(station)
        if hour is None:
            return [([(a, b)], total, True)]
        return [([(h0, h1)], hour, False), ([(a, h0), (h1, b)], max(0.0, total - hour), True)]
    night, d1, d2 = _filled("night"), _filled("day1_24h"), _filled("day2_24h")
    resid = max(0.0, d1[station] - night[station])
    return [
        ([(_ist(2025, 8, 18, 20, 30), _ist(2025, 8, 19, 5, 30))], night[station], True),
        ([(_ist(2025, 8, 19, 5, 30), _ist(2025, 8, 19, 8, 30))], resid, True),
        ([(_ist(2025, 8, 19, 8, 30), _ist(2025, 8, 19, 15, 0))], C_SPLIT * d2[station], True),
        ([(_ist(2025, 8, 19, 15, 0), _ist(2025, 8, 19, 20, 30))], (1.0 - C_SPLIT) * d2[station], True),
    ]


def station_series(station: str, start_utc: datetime, n: int, step_min: int = 15,
                   timing: np.ndarray | None = None, event: str = DEFAULT_EVENT) -> np.ndarray:
    """mm/h at an IMD station on the 15-min grid (grid times are interval ends): each window's total
    (OBSERVED; module doc) spread over the window (MODELLED) — in proportion to ``timing`` (the Open-Meteo
    archive's rain at the nearest point on the same grid) where that carries rain in the window, else flat.
    Every window keeps its observed total either way."""
    out = np.zeros(n)
    dt = step_min / 60.0
    mids = [start_utc + timedelta(minutes=step_min * i) - timedelta(minutes=step_min / 2) for i in range(n)]
    for spans, mm, timed in _pieces(station, event):
        idx = [i for i, t in enumerate(mids) if any(a <= t < b for a, b in spans)]
        if not idx:
            continue
        w = (np.array([timing[i] for i in idx], dtype=float) if (timing is not None and timed)
             else np.zeros(len(idx)))
        if w.sum() * dt < 1.0:  # the archive is (nearly) dry here: flat
            w = np.ones(len(idx))
        out[idx] = mm * w / (w.sum() * dt)
    return out


def _match(hydro: Hydro, rep: dict) -> list[int]:
    if "road" in rep:
        return [sid for sid, s in hydro.net.segments.items() if s.road_name.split(" (")[0] == rep["road"]]
    best = []
    for sid, s in hydro.net.segments.items():
        if hydro.sus.get(str(sid), {}).get("elevated"):
            continue  # a reported waterlogged place is never a bridge deck or a flyover
        d = min(haversine_m(rep["lat"], rep["lon"], lat, lon) for lon, lat in s.line) if s.line else 1e9
        if d <= 600.0:
            best.append(sid)
    return best


def _event_spec(event: str) -> dict[str, Any]:
    """Per-event inputs: rain stations, reported places, pump availability and what was officially said."""
    if event == "2025-05-26":
        return {
            "stations": MAY_STATIONS, "reported": REPORTED_MAY, "availability": dict(MAY_PUMPS),
            "gauge_label": "OBSERVED totals (12-h station totals and the 09:00–10:00 hour, as reported) · 15-min "
                           "shape MODELLED",
            "gauge_sources": [SRC["fpj_0526_2315"], SRC["fpj_0526_1112"]],
            "shape": ("the 09:00–10:00 hour as observed where reported (Nariman Point, Colaba, CSMT, Malabar Hill); "
                      "the rest of each 23:00–11:00 total in proportion to the Open-Meteo archive's hourly rain at "
                      "the nearest point; no rain after 11:00 (not reported per station)"),
            "ref_station": "nariman_point",
            "official": {"bmc_12h_2300_1100_mm": dict(MAY_12H), "hour_0900_1000_mm": dict(MAY_HOUR_0910),
                         "imd": "Colaba observatory 144.3 mm and Santacruz 74.3 mm up to 17:30 (FPJ)",
                         "metro": "the underground Acharya Atre Chowk (Worli) metro station flooded; services "
                                  "Acharya Atre Chowk–Worli suspended (a station, not a road: not scored)",
                         "sources": [SRC["fpj_0526_2315"], SRC["fpj_0526_1112"], SRC["newsarena_0526"]]},
            "pumps": {"label": "AS REPORTED for 26 May — the EMULATED adapter is not used",
                      "availability": dict(MAY_PUMPS),
                      "basis": "Hindmata, Gandhi Market and Yellow Gate mini pumping systems were not running and "
                               "Chunabhatti's ran below capacity (PTI, 28 May 2025; FPJ, 26 May 2025); the major "
                               "stations are not reported down (assumed available)",
                      "sources": [SRC["pti_0528"], SRC["fpj_0526_2315"]]},
            "tide_reported": "BMC (via PTI) for the next day, 27 May: 4.88 m at 12:13 and 4.18 m at 23:56",
            "tide_source": SRC["pti_tide_0527"],
        }
    return {
        "stations": IMD_STATIONS, "reported": REPORTED, "availability": {},
        "gauge_label": "OBSERVED totals (IMD station windows, as reported) · 15-min shape MODELLED",
        "gauge_sources": [SRC["fpj_imd_0839"], SRC["pti_imd_24h_0819"], SRC["pti_imd_24h_0820"]],
        "shape": ("each IMD window's observed total spread in proportion to the Open-Meteo archive's hourly rain at "
                  "the nearest point (gauge totals, archive timing); windows: residual of the 24 h to 08:30 in "
                  f"05:30–08:30; 24 h to 20 Aug 08:30 split {C_SPLIT:.0%} / {1 - C_SPLIT:.0%} over 08:30–15:00 / "
                  "15:00–20:30"),
        "ref_station": "santacruz",
        "official": {"imd_24h_to_0830_19aug_mm": dict(IMD_WINDOWS["day1_24h"]),
                     "imd_night_2030_0530_mm": dict(IMD_WINDOWS["night"]),
                     "imd_24h_to_0830_20aug_mm": {k: v for k, v in IMD_WINDOWS["day2_24h"].items() if v is not None},
                     "bmc_0400_1500_19aug_mm": dict(BMC_0400_1500),
                     "cmo": "more than 150 mm between 04:00 and 11:00 on 19 Aug",
                     "mithi": "3.9 m against a 4 m danger mark; about 350 people moved from Kranti Nagar, Kurla",
                     "sources": [SRC["fpj_imd_0839"], SRC["pti_imd_24h_0819"], SRC["pti_imd_24h_0820"],
                                 SRC["pti_bmc_0819"], SRC["bt_0819"]]},
        "pumps": {"assumed_availability": 1.0, "label": "EMULATED adapter not used — all pumps assumed available",
                  "basis": "BMC (via PTI): the six major stations' 43 pumps ran over 761 pump-hours in 16–19 Aug; "
                           "540 mobile pumps worked on the 19th",
                  "source": SRC["pti_bmc_0819"]},
        "tide_reported": "BMC tide timing as reported: 3.75 m at 09:16 (one outlet dates it 20 Aug)",
        "tide_source": SRC["tide_bmc"],
    }


async def replay(hydro: Hydro, event: str = DEFAULT_EVENT) -> dict[str, Any]:
    if event not in EVENTS:
        raise KeyError(event)
    ev = EVENTS[event]
    spec = _event_spec(event)
    step = hydro.step
    start = ev["start_ist"].astimezone(UTC)
    n = int((ev["end_ist"] - ev["start_ist"]).total_seconds() // (60 * step)) + 1
    times = [start + timedelta(minutes=step * i) for i in range(n)]
    availability: dict[str, float] = spec["availability"]
    reported: list[dict[str, Any]] = spec["reported"]
    stations = spec["stations"]
    day = ev["start_ist"].date()

    runs: dict[str, Any] = {}
    pts: list[RainPoint] = []
    # ── run A: Open-Meteo archive ─────────────────────────────────────────
    try:
        arc = await hydro.rain.archive_hourly(POINTS, day, day + timedelta(days=1))
        pts = [RainPoint(p["id"], p["lat"], p["lon"], times, quarter_series(p["times"], p["mm"], start, n, step))
               for p in arc["points"]]
        rain_a = {sid: idw(pts, *hydro.net.segments[sid].midpoint) for sid in hydro.net.segments}
        city_total = float(np.mean([np.sum(p.mm_h) * step / 60 for p in pts]))
        max_total = float(max(np.sum(p.mm_h) * step / 60 for p in pts))
        peak = float(max(p.mm_h.max() for p in pts))
        ref = spec["ref_station"]
        gauge_ref = float(np.sum(station_series(ref, start, n, step, event=event)) * step / 60)
        ref_name = next(nm for k, nm, *_ in stations if k == ref)
        runs["open_meteo_archive"] = _run(hydro, times, rain_a, availability, reported, {
            "label": "ARCHIVE (Open-Meteo historical archive, reanalysis/NWP based)",
            "source": hydro.rain.archive_url, "model": arc["model"],
            "grid_cells": sorted({f"{a:.3f},{b:.3f}" for a, b in arc["grid"]}),
            "window_total_mm_city_mean": round(city_total, 1), "window_total_mm_max_point": round(max_total, 1),
            "peak_mm_h_any_point": round(peak, 1),
            "finding": (f"The archive's gridded rain over the window is {city_total:.0f} mm (city mean; "
                        f"{max_total:.0f} mm at its wettest point, peak {peak:.0f} mm/h) against about "
                        f"{gauge_ref:.0f} mm at {ref_name} from the reported gauge totals over the same hours. The "
                        "model is driven by its rain, so this run shows what a nowcast fed only by such a product "
                        "would have seen — the case for wiring the BMC's own rain gauges into the pilot."),
        })
    except Exception as exc:  # noqa: BLE001
        runs["open_meteo_archive"] = {"error": f"{type(exc).__name__}: {exc}"[:300]}

    # ── run B: gauge-anchored (totals OBSERVED; timing from the archive where it has rain) ──
    def nearest_timing(lat: float, lon: float) -> np.ndarray | None:
        if not pts:
            return None
        return min(pts, key=lambda p: haversine_m(lat, lon, p.lat, p.lon)).mm_h

    st_pts = [RainPoint(k, la, lo, times, station_series(k, start, n, step, nearest_timing(la, lo), event))
              for k, _nm, la, lo in stations]
    rain_b = {sid: idw(st_pts, *hydro.net.segments[sid].midpoint) for sid in hydro.net.segments}
    runs["imd_gauge_anchored"] = _run(hydro, times, rain_b, availability, reported, {
        "label": spec["gauge_label"], "sources": spec["gauge_sources"],
        "station_window_totals_mm": {p.id: round(float(np.sum(p.mm_h) * step / 60), 1) for p in st_pts},
        "station_peak_mm_h": {p.id: round(float(p.mm_h.max()), 1) for p in st_pts},
        "shape": spec["shape"] if pts else "archive unavailable: flat within each window",
    })
    # sensitivity: the same totals without the archive's timing — the bursts flattened out
    flat_pts = [RainPoint(k, la, lo, times, station_series(k, start, n, step, None, event))
                for k, _nm, la, lo in stations]
    rain_f = {sid: idw(flat_pts, *hydro.net.segments[sid].midpoint) for sid in hydro.net.segments}
    flat = _run(hydro, times, rain_f, availability, reported, {})
    runs["imd_gauge_flat_sensitivity"] = {
        "label": "SENSITIVITY — the same OBSERVED totals, flat within each window",
        "station_peak_mm_h": {p.id: round(float(p.mm_h.max()), 1) for p in flat_pts},
        "peak_class_counts": flat["peak_class_counts"], "flagged_segments": flat["flagged_segments"],
        "reported_hits": f"{flat['reported_check']['flagged']}/{flat['reported_check']['on_network']}",
        "finding": ("The same totals without the archive's timing: the drains' design rates (12.5–50 mm/h of "
                    "runoff) are crossed by the bursts, not by the window means, so the timing within the hour — "
                    "what a live gauge feed adds — moves the result."),
    }
    runs["imd_gauge_anchored"]["snapshot"] = _snapshot(hydro, times, rain_b, availability, ev["snapshot_ist"])
    restr = [hydro.tide.outfall_restriction(t - timedelta(minutes=step / 2)) for t in times]
    impeded = [t for t, r in zip(times, restr) if r > 0]
    shut = [t for t, r in zip(times, restr) if r >= 1.0]
    highs = [e for e in hydro.tide.extremes(start, (n - 1) * step / 60) if e.kind == "high"]
    return {
        "event": event,
        "title": ev["title"],
        "window_ist": [ev["start_ist"].isoformat(), ev["end_ist"].isoformat()],
        "official": spec["official"],
        "tide": {"label": "MODELLED (approximate)", "station": hydro.tide.station_name,
                 "high_waters_ist": [{"at": e.at.astimezone(IST).isoformat(timespec="minutes"),
                                      "level_m": e.level_m} for e in highs],
                 "outfalls_impeded_ist": [[a.astimezone(IST).isoformat(timespec="minutes"),
                                           b.astimezone(IST).isoformat(timespec="minutes")]
                                          for a, b in _spans(impeded, step)],
                 "gates_shut_ist": [[a.astimezone(IST).isoformat(timespec="minutes"),
                                     b.astimezone(IST).isoformat(timespec="minutes")] for a, b in _spans(shut, step)],
                 "reported": spec["tide_reported"], "reported_source": spec["tide_source"]},
        "pumps": spec["pumps"],
        "runs": runs,
        "sources": SRC,
        "honesty": ("News reports name places, not every street, and the network has 86 arterial segments: a "
                    "flag with no report is not called a false alarm, and an off-network report is listed but "
                    "not scored. A report's time is its publication time, so a lead before it is an upper bound. "
                    "Station positions are approximate and the 15-minute shape is modelled."),
    }


def _spans(ts: list[datetime], step: int) -> list[tuple[datetime, datetime]]:
    spans: list[tuple[datetime, datetime]] = []
    for t in ts:
        if spans and (t - spans[-1][1]) <= timedelta(minutes=step):
            spans[-1] = (spans[-1][0], t)
        else:
            spans.append((t, t))
    return spans


def _median(xs: list[int | None]) -> int | None:
    v = sorted(x for x in xs if x is not None)
    return v[len(v) // 2] if v else None


def _first(times: list[datetime], cls: np.ndarray, k: int) -> str | None:
    idx = np.nonzero(cls >= k)[0]
    return times[int(idx[0])].astimezone(IST).strftime("%Y-%m-%d %H:%M") if idx.size else None


def _run(hydro: Hydro, times: list[datetime], rain_for: dict[int, np.ndarray],
         availability: dict[str, float], reported: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    core = hydro.run_segments(times, rain_for, availability)
    segs = []
    for sid in sorted(hydro.net.segments):
        st, _a, run = core["runs"][sid]
        peak_i = int(np.argmax(run.depth_cm))
        segs.append({
            "segment_id": sid, "road_name": st["seg"].road_name,
            "place": hydro.net.junction_name(st["seg"].to_junction),
            "rain_total_mm": round(float(np.sum(rain_for[sid]) * hydro.step / 60), 1),
            "peak_class": int(run.classes.max()), "peak_depth_cm": round(float(run.depth_cm[peak_i]), 1),
            "peak_band": CLASS_BANDS[int(run.classes.max())],
            "peak_at_ist": times[peak_i].astimezone(IST).strftime("%Y-%m-%d %H:%M"),
            "first_class1_ist": _first(times, run.classes, 1),
            "first_class2_ist": _first(times, run.classes, 2),
            "first_class3_ist": _first(times, run.classes, 3),
            "elevated": bool(st["sus"].get("elevated", False)),
        })
    by = {s["segment_id"]: s for s in segs}
    checks = []
    day = times[-1].astimezone(IST).date()
    for rep in reported:
        m = _match(hydro, rep)
        flagged = [by[s] for s in m if by[s]["peak_class"] >= 2]
        first = sorted(f["first_class2_ist"] for f in flagged if f["first_class2_ist"])
        lead = None
        roundup = False
        if rep.get("reported_ist"):
            hh, mm = (int(x) for x in rep["reported_ist"].split(":"))
            rep_t = datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST)
            # an evening round-up published after the replay window says where, not when: no lead from it
            roundup = rep_t > times[-1]
            if first and not roundup:
                flag_t = datetime.strptime(first[0], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
                lead = int((rep_t - flag_t).total_seconds() // 60)
        checks.append({
            "reported": rep["name"], "what": rep.get("what"), "reported_by_ist": rep.get("reported_ist"),
            "roundup_after_window": roundup,
            "sources": [SRC[s]["publisher"] + ", " + SRC[s]["date"] for s in rep["src"]],
            "segments": m, "on_network": bool(m),
            "flagged": bool(flagged) if m else None,
            "first_flag_ist": first[0] if first else None,
            "lead_before_first_report_min": lead,
            # HINDSIGHT: a nowcast fed the observed rain as a perfect forecast shows the flag up to one horizon
            # before the modelled depth crossing
            "warning_lead_perfect_nowcast_min": (lead + hydro.horizon) if lead is not None else None,
            "max_class": max((by[s]["peak_class"] for s in m), default=None),
        })
    scored = [c for c in checks if c["on_network"]]
    hits = sum(1 for c in scored if c["flagged"])
    counts = {str(k): sum(1 for s in segs if s["peak_class"] == k) for k in range(4)}
    flagged_ids = [s["segment_id"] for s in segs if s["peak_class"] >= 2]
    return {
        **meta,
        "peak_class_counts": counts,
        "flagged_segments": len(flagged_ids),
        "earliest_flag_ist": min((s["first_class2_ist"] for s in segs if s["first_class2_ist"]), default=None),
        "reported_check": {"on_network": len(scored), "flagged": hits,
                           "hit_rate": round(hits / len(scored), 3) if scored else None,
                           "missed": [c["reported"] for c in scored if not c["flagged"]],
                           "median_warning_lead_perfect_nowcast_min": _median(
                               [c["warning_lead_perfect_nowcast_min"] for c in scored]),
                           "median_lead_before_first_report_min": (
                               sorted(c["lead_before_first_report_min"] for c in scored
                                      if c["lead_before_first_report_min"] is not None)[
                                   len([c for c in scored if c["lead_before_first_report_min"] is not None]) // 2]
                               if any(c["lead_before_first_report_min"] is not None for c in scored) else None),
                           "off_network": [c["reported"] for c in checks if not c["on_network"]],
                           "items": checks},
        "segments": segs,
    }


def _snapshot(hydro: Hydro, times: list[datetime], rain_for: dict[int, np.ndarray], availability: dict[str, float],
              at: datetime) -> dict[str, Any]:
    """What the officer would have seen at ``at`` if the observed rain had been nowcast perfectly: the
    nowcast view (risk within the horizon, lead times) and its proposals. Hindsight, labelled so."""
    core = hydro.run_segments(times, rain_for, availability)
    now_idx = max(i for i, t in enumerate(times) if t <= at)
    end_idx = min(len(times) - 1, now_idx + hydro.horizon // hydro.step)
    results = []
    for sid in sorted(hydro.net.segments):
        st, a, run = core["runs"][sid]
        results.append(hydro._result(sid, st, a, run, times, now_idx, end_idx, rain_for[sid], core["gates"],
                                     "OBSERVED (hindsight)", [], at.astimezone(UTC)))
    flagged = {r["segment_id"] for r in results if r["risk_class"] >= 2}
    props = hydro._proposals(results, flagged, at.astimezone(UTC), ["HINDSIGHT", "MODELLED"])
    leads = sorted(r["lead_time_deep_min"] for r in results if r["segment_id"] in flagged)
    top = sorted((r for r in results if r["segment_id"] in flagged), key=lambda r: (-r["risk_class"], r["lead_time_min"]))
    return {
        "at_ist": at.isoformat(),
        "label": "HINDSIGHT — the observed rain used as if it had been a perfect nowcast",
        "flagged_within_horizon": len(flagged),
        "flagged_now": sum(1 for r in results if r["risk_class_now"] >= 2),
        "lead_time_to_deep_min": {"min": leads[0], "median": leads[len(leads) // 2], "max": leads[-1]} if leads else None,
        "top": [{k: r[k] for k in ("segment_id", "road_name", "place", "risk_class", "expected_depth_band",
                                   "lead_time_min", "lead_time_deep_min")} for r in top[:8]],
        "proposal_counts": {k: sum(1 for p in props if p["kind"] == k) for k in sorted({p["kind"] for p in props})},
        "proposal_examples": [p["summary"] for p in props if p["kind"] != "public_advisory_draft"][:4],
        "advisory_draft": next((p["text"] for p in props if p["kind"] == "public_advisory_draft"), None),
        # the proposals themselves for the eight most urgent roads and the advisory (an officer exercise on
        # the console: HINDSIGHT-labelled, never today's city)
        "proposals": [p for p in props if p["kind"] == "public_advisory_draft"
                      or p.get("subject_urn") in {f"segment:{r['segment_id']}" for r in top[:8]}],
    }
