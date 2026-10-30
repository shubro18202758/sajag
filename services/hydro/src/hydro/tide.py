"""Harmonic tide models — MODELLED (approximate). Default station: **Apollo Bunder, Mumbai harbour**.

Why it matters: Mumbai's storm-water drains empty into the Arabian Sea, Mahim creek and Thane creek through
outfalls that are submerged at high tide; their flood gates are shut so the sea cannot back up, and the
low spots then drain by pumps alone. A heavy burst at high tide is what floods the same places every
monsoon. In the BMC's words, waterlogging is unavoidable when heavy rain coincides with a ~4.5 m high
tide (Free Press Journal, 2025), and the BMC lists every tide above 4.5 m as a high-tide day.

**Apollo Bunder constants (cited).** M2 1.23 m / 345°, S2 0.48 m / 25°, K1 0.42 m / 55°, O1 0.20 m / 52°,
from the Admiralty Tide Tables as tabulated for Mumbai (Apollo Bandar) by A. S. Unnikrishnan, "Perigean
spring tides along the Indian coast", Current Science 123(8), 25 Oct 2022. The phases are read as
referred to Indian Standard Time (zone −0530), as the Indian ports' tables give them: the Greenwich lag is
``g − ω·5.5 h``. That reading is an inference, checked below — read as Greenwich lags, high water came
~5.5 h late on every check date.

**Inferred (the MODELLED part).**

* N2 and K2 by the standard inference from M2 and S2 (equilibrium ratios N2/M2 = 0.194, K2/S2 = 0.272;
  g(N2) = g(M2) − ½·(g(S2) − g(M2)), g(K2) = g(S2)). Without them the modelled high water drifted ~40
  min over a five-day spring spell; with them it stays within ~20 min;
* the mean level ``AB_MEAN_LEVEL_M`` 2.61 m above chart datum, FITTED to the BMC's published monsoon
  high waters (one parameter; the timing checks below are independent of it).

**Check against published Mumbai tide tables** (the BMC's high-tide advisories as printed by the Free
Press Journal; ``tests/test_tide.py``): 24–28 June 2025 (4.59–4.75 m, 11:15–14:26 IST) and 24–27 July
2025 (4.57–4.67 m), plus the full 24 July 2025 day (low 05:07, high 11:58, low 18:13, high 23:40).
Modelled high waters land within 20 min and 0.1 m, low waters within 5 min and ~0.2 m.

**Outfalls.** ``gate_closed`` is true at or above ``GATE_CLOSE_LEVEL_M`` (4.5 m, the BMC's high-tide
threshold). The outfalls start to back up well before that (a 3.41 m morning tide with heavy rain still
flooded Andheri Subway, Hindmata and King's Circle in June 2025), so ``outfall_restriction`` grades the
loss of gravity discharge linearly from ``OUTFALL_IMPEDED_FROM_M`` (3.4 m, 0) to 4.5 m (1): a labelled
assumption, not a survey of outfall inverts.

The Kolkata pack's Hooghly stations (Garden Reach, transferred from the Diamond Harbour constants of Khan
et al. 2021, NHESS 21:2523–2541) stay available as ``station="garden_reach"`` / ``"diamond_harbour"``.

Nodal corrections (f, u) use the standard Doodson/Schureman series; astronomical arguments use the mean
longitudes of the Moon (s), Sun (h), lunar perigee (p) and node (N).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

__all__ = [
    "CONSTITUENTS_AB",
    "AB_MEAN_LEVEL_M",
    "OUTFALL_IMPEDED_FROM_M",
    "STATIONS",
    "CONSTITUENTS_DH",
    "GR_LAG_H",
    "GR_AMPLITUDE_RATIO",
    "GR_MEAN_LEVEL_M",
    "GR_M4_RATIO",
    "GATE_CLOSE_LEVEL_M",
    "FRESHET_OFFSET_M",
    "TideModel",
    "TideExtreme",
    "LABEL",
    "SOURCES",
]

LABEL = "MODELLED (approximate)"

#: name → (amplitude m, phase lag ° referred to IST (zone −0530), speed °/h) at Apollo Bunder, Mumbai —
#: Admiralty Tide Tables via Unnikrishnan (2022), Current Science 123(8); N2 and K2 INFERRED (module doc)
CONSTITUENTS_AB: dict[str, tuple[float, float, float]] = {
    "M2": (1.23, 345.0, 28.9841042),
    "S2": (0.48, 25.0, 30.0000000),
    "K1": (0.42, 55.0, 15.0410686),
    "O1": (0.20, 52.0, 13.9430356),
    "N2": (round(0.194 * 1.23, 3), 345.0 - 0.5 * ((25.0 - 345.0) % 360.0), 28.4397295),
    "K2": (round(0.272 * 0.48, 3), 25.0, 30.0821373),
}
#: IST is 5.5 h ahead of UTC: a zone-time phase converts to a Greenwich lag by g − ω·5.5
AB_ZONE_HOURS = 5.5
#: mean level above chart datum, FITTED to the BMC's 2025 monsoon high waters (module doc)
AB_MEAN_LEVEL_M = 2.61
#: the outfalls start to back up from here (assumption; module doc)
OUTFALL_IMPEDED_FROM_M = 3.4

#: name → (amplitude m, Greenwich phase lag g °, speed °/h) at Diamond Harbour — Khan et al. 2021, Table S1
CONSTITUENTS_DH: dict[str, tuple[float, float, float]] = {
    "M2": (1.57, 168.0, 28.9841042),
    "S2": (0.68, 210.0, 30.0000000),
    "K1": (0.15, 285.0, 15.0410686),
    "O1": (0.07, 258.0, 13.9430356),
}

GR_LAG_H = 2.0 + 38.0 / 60.0
#: the Kolkata pack's Hooghly gate level (Garden Reach; The Telegraph, port official)
GR_GATE_CLOSE_LEVEL_M = 5.0
GR_AMPLITUDE_RATIO = 0.80
GR_MEAN_LEVEL_M = 3.7
#: fitted M4 amplitude as a fraction of the Garden Reach M2 amplitude (MODELLED; see the module doc)
GR_M4_RATIO = 0.18
#: Apollo Bunder: the BMC's high-tide threshold (tides above 4.5 m are its listed high-tide days)
GATE_CLOSE_LEVEL_M = 4.5
#: month → metres added to the Hooghly mean level (monsoon freshet; MODELLED assumption; Kolkata pack only)
FRESHET_OFFSET_M: dict[int, float] = {7: 0.3, 8: 0.6, 9: 0.6, 10: 0.3}

SOURCES: list[dict[str, str]] = [
    {"what": "M2/S2/K1/O1 at Mumbai (Apollo Bandar), Admiralty Tide Tables",
     "ref": "Unnikrishnan, A. S. (2022), Perigean spring tides along the Indian coast, Current Science 123(8)",
     "url": "https://i-scholar.in/index.php/CURS/article/download/216099/200261"},
    {"what": "BMC high-tide advisory, 24–28 June 2025 (times and heights; the fit and timing check)",
     "ref": "Free Press Journal, 23 Jun 2025, citing the BMC",
     "url": "https://www.freepressjournal.in/mumbai/mumbaikars-alert-bmc-warns-of-5-day-high-tide-spell-from-"
            "june-2428-waves-to-cross-475-metres"},
    {"what": "BMC high-tide advisory, 24–27 July 2025, and the full 24 July tide table",
     "ref": "Free Press Journal, 24 Jul 2025, citing the BMC",
     "url": "https://www.freepressjournal.in/mumbai/mumbai-rains-city-to-experience-high-tide-149-feet-bmc-"
            "issues-alert-till-july-31"},
    {"what": "Tides above 4.5 m with heavy rain flood the city (BMC); the 2026 high-tide calendar",
     "ref": "Free Press Journal, 13 Jun 2026, citing the BMC",
     "url": "https://www.freepressjournal.in/mumbai/mumbai-monsoon-alert-bmc-releases-2026-high-tide-schedule-"
            "citizens-advised-to-stay-away-from-sea-during-peak-tides"},
]

SOURCES_GR: list[dict[str, str]] = [
    {"what": "M2/S2/K1/O1 observed at Diamond Harbour",
     "ref": "Khan et al. (2021), Nat. Hazards Earth Syst. Sci. 21:2523–2541, Supplement Table S1",
     "url": "https://nhess.copernicus.org/articles/21/2523/2021/nhess-21-2523-2021-supplement.pdf"},
    {"what": "Garden Reach vs Diamond Harbour predicted high/low waters (lag, range, mean level)",
     "ref": "tide-forecast.com predictions for 28 Oct 2026 (third-party; datum 'MLLW')",
     "url": "https://www.tide-forecast.com/locations/Calcutta-Garden-Reach-India/tides/latest"},
    {"what": "Gate-closure level ~5 m at Garden Reach",
     "ref": "The Telegraph (Kolkata), port official quoted on Hooghly tide and sluice gates",
     "url": "https://obeta.ttef.in/my-kolkata/news/hooghly-tide-helps-water-drain-out-faster-in-kolkata/cid/1864513"},
    {"what": "Kidderpore spring/neap ranges, dry season and rains",
     "ref": "Cunningham (1904), A Treatise on the Principles and Practice of Dock Engineering",
     "url": "https://tekniskkulturarv.dk/book/c3fb3acc-28e6-490b-8092-5f3a342494c2?page=74"},
]

_J2000 = datetime(2000, 1, 1, 12, tzinfo=UTC)


def _astro(t: datetime) -> tuple[float, float, float, float, float]:
    """(T, s, h, p, N) in degrees at UTC time t; T = hour angle of the mean sun."""
    days = (t - _J2000).total_seconds() / 86400.0
    c = days / 36525.0
    s = 218.3164477 + 481267.88123421 * c
    h = 280.4664567 + 36000.76982779 * c
    p = 83.3532465 + 4069.0137287 * c
    n = 125.0445479 - 1934.1362891 * c
    hours = t.hour + t.minute / 60.0 + t.second / 3600.0 + t.microsecond / 3.6e9
    big_t = 180.0 + 15.0 * hours
    return big_t, s % 360, h % 360, p % 360, n % 360


def _v_f_u(name: str, t: datetime) -> tuple[float, float, float]:
    """Equilibrium argument V (°), nodal factor f and nodal angle u (°) for a constituent."""
    big_t, s, h, _p, n = _astro(t)
    nr = math.radians(n)
    if name == "M2":
        v = 2 * big_t - 2 * s + 2 * h
        f = 1.0004 - 0.0373 * math.cos(nr) + 0.0002 * math.cos(2 * nr)
        u = -2.14 * math.sin(nr)
    elif name == "N2":
        v = 2 * big_t - 3 * s + 2 * h + _p
        f = 1.0004 - 0.0373 * math.cos(nr) + 0.0002 * math.cos(2 * nr)
        u = -2.14 * math.sin(nr)
    elif name == "K2":
        v = 2 * big_t + 2 * h
        f = 1.0241 + 0.2863 * math.cos(nr) + 0.0083 * math.cos(2 * nr) - 0.0015 * math.cos(3 * nr)
        u = -17.74 * math.sin(nr) + 0.68 * math.sin(2 * nr) - 0.04 * math.sin(3 * nr)
    elif name == "M4":
        v2, f2, u2 = _v_f_u("M2", t)
        v, f, u = 2 * v2, f2 * f2, 2 * u2
    elif name == "S2":
        v, f, u = 2 * big_t, 1.0, 0.0
    elif name == "K1":
        v = big_t + h - 90.0
        f = 1.0060 + 0.1150 * math.cos(nr) - 0.0088 * math.cos(2 * nr) + 0.0006 * math.cos(3 * nr)
        u = -8.86 * math.sin(nr) + 0.68 * math.sin(2 * nr) - 0.07 * math.sin(3 * nr)
    elif name == "O1":
        v = big_t - 2 * s + h + 90.0
        f = 1.0089 + 0.1871 * math.cos(nr) - 0.0147 * math.cos(2 * nr) + 0.0014 * math.cos(3 * nr)
        u = 10.80 * math.sin(nr) - 1.34 * math.sin(2 * nr) + 0.19 * math.sin(3 * nr)
    else:  # pragma: no cover - only these constituents are defined
        raise KeyError(name)
    return v % 360.0, f, u


@dataclass(frozen=True)
class TideExtreme:
    kind: str  # "high" | "low"
    at: datetime
    level_m: float


#: station id → (name, outfalls, gate level m)
STATIONS: dict[str, dict[str, object]] = {
    "apollo_bunder": {"name": "Apollo Bunder (Mumbai harbour)", "sea": "Arabian Sea",
                      "gate_close_level_m": GATE_CLOSE_LEVEL_M, "impeded_from_m": OUTFALL_IMPEDED_FROM_M,
                      "datum": "chart datum (the BMC's tide tables use the same datum)"},
    "garden_reach": {"name": "Garden Reach (Hooghly), transferred from Diamond Harbour", "sea": "Hooghly",
                     "gate_close_level_m": GR_GATE_CLOSE_LEVEL_M, "impeded_from_m": GR_GATE_CLOSE_LEVEL_M,
                     "datum": "the third-party predictions' datum (approximately chart datum)"},
    "diamond_harbour": {"name": "Diamond Harbour (Hooghly)", "sea": "Hooghly",
                        "gate_close_level_m": GR_GATE_CLOSE_LEVEL_M, "impeded_from_m": GR_GATE_CLOSE_LEVEL_M,
                        "datum": "the third-party predictions' datum (approximately chart datum)"},
}


class TideModel:
    """Harmonic tide at a station: Apollo Bunder, Mumbai (``station='apollo_bunder'``, the default; cited
    constants, N2/K2 inferred, mean level fitted), or the Kolkata pack's Hooghly stations (Garden Reach, the
    MODELLED transfer, and Diamond Harbour, the cited constants)."""

    def __init__(self, station: str = "apollo_bunder", freshet: bool = True) -> None:
        if station not in STATIONS:
            raise ValueError(station)
        self.station = station
        self.station_name = str(STATIONS[station]["name"])
        self.gate_level = float(STATIONS[station]["gate_close_level_m"])  # type: ignore[arg-type]
        self.impeded_from = float(STATIONS[station]["impeded_from_m"])  # type: ignore[arg-type]
        self.datum = str(STATIONS[station]["datum"])
        # the monsoon freshet is a Hooghly effect; the open-sea station has none
        self.freshet = freshet and station != "apollo_bunder"
        self.sources = SOURCES if station == "apollo_bunder" else SOURCES_GR
        if station == "apollo_bunder":
            self.mean_level = AB_MEAN_LEVEL_M
            self.consts = {k: (a, (g - w * AB_ZONE_HOURS) % 360.0, w) for k, (a, g, w) in CONSTITUENTS_AB.items()}
        elif station == "garden_reach":
            self.mean_level = GR_MEAN_LEVEL_M
            self.consts = {
                k: (a * GR_AMPLITUDE_RATIO, (g + w * GR_LAG_H) % 360.0, w)
                for k, (a, g, w) in CONSTITUENTS_DH.items()
            }
            a2, g2, w2 = self.consts["M2"]
            self.consts["M4"] = (GR_M4_RATIO * a2, (2 * g2 - 90.0) % 360.0, 2 * w2)
        else:
            # Diamond Harbour's mean level is not used by the city model; low waters ≈ 0.4 m, highs
            # ≈ 5.4 m in the same third-party predictions → 2.9 m (approximate)
            self.mean_level = 2.9
            self.consts = dict(CONSTITUENTS_DH)

    def level(self, t: datetime) -> float:
        if t.tzinfo is None:
            raise ValueError("aware datetime required")
        t = t.astimezone(UTC)
        z = self.mean_level + (FRESHET_OFFSET_M.get(t.astimezone(_IST).month, 0.0) if self.freshet else 0.0)
        for name, (a, g, _w) in self.consts.items():
            v, f, u = _v_f_u(name, t)
            z += f * a * math.cos(math.radians(v + u - g))
        return z

    def series(self, start: datetime, hours: float, step_min: int = 15) -> list[tuple[datetime, float]]:
        n = int(hours * 60 // step_min) + 1
        return [(start + timedelta(minutes=step_min * i), self.level(start + timedelta(minutes=step_min * i)))
                for i in range(n)]

    def gate_closed(self, t: datetime) -> bool:
        """Outfall flood gates shut (the station's gate level)."""
        return self.level(t) >= self.gate_level

    def outfall_restriction(self, t: datetime) -> float:
        """0 (outfalls discharge freely) … 1 (gates shut): linear between the station's impeded-from level
        and its gate level (MODELLED assumption; a step at the gate level where the two coincide)."""
        z = self.level(t)
        if z >= self.gate_level:
            return 1.0
        if z <= self.impeded_from or self.gate_level <= self.impeded_from:
            return 0.0
        return (z - self.impeded_from) / (self.gate_level - self.impeded_from)

    def extremes(self, start: datetime, hours: float) -> list[TideExtreme]:
        """High and low waters in [start, start+hours], found on a 6-min grid and refined."""
        step = timedelta(minutes=6)
        n = int(hours * 10) + 2
        times = [start - step + step * i for i in range(n + 1)]
        vals = [self.level(x) for x in times]
        out: list[TideExtreme] = []
        for i in range(1, len(vals) - 1):
            a, b, c = vals[i - 1], vals[i], vals[i + 1]
            kind = "high" if (b >= a and b > c) else "low" if (b <= a and b < c) else None
            if kind is None:
                continue
            # parabolic refinement
            denom = a - 2 * b + c
            off = 0.5 * (a - c) / denom if denom != 0 else 0.0
            at = times[i] + timedelta(seconds=off * step.total_seconds())
            if start <= at <= start + timedelta(hours=hours):
                out.append(TideExtreme(kind=kind, at=at, level_m=round(self.level(at), 2)))
        return out


_IST = __import__("zoneinfo").ZoneInfo("Asia/Kolkata")
