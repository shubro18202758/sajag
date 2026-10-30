"""BMC storm-water pumping stations — pump state. **EMULATED until access is granted.**

The BMC runs six major storm-water pumping stations on the sea outfalls (Haji Ali, Love Grove, Cleveland
Bunder, Britannia, Irla, Gazdarbandh: 43 pumps, aggregate capacity 2.58 lakh litres per second — BMC via
PTI, 19 Aug 2025) and about ten mini pumping stations at chronic low spots (PTI, 28 May 2025: Rs 10 lakh
penalties at Hindmata, Gandhi Market, Yellow Gate and Chunabhatti after the 26 May 2025 rain). Their live
state is not public: the real feed is the BMC's pumping-station telemetry and the IFLOWS-Mumbai flood
warning system, which Sajag has no access to. ``FfewsAdapter`` is the interface a real feed will implement
(the name is kept from the platform's first city); ``EmulatedFfews`` is the stand-in used until then, and
everything it returns says ``EMULATED`` — station names are real, their per-station pump counts and state
are invented (the six major stations' invented counts add up to the published 43).

Coordinates: the six major stations from ``cities/mumbai/landmarks.json``; the mini stations placed by hand
at the named spot (APPROXIMATE, ±0.5 km). They only decide which segments a station serves (nearest station
within ``CATCHMENT_M``). Capacities are given only where published (the six stations' aggregate).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from hydro.network import haversine_m

__all__ = ["PumpStation", "PumpState", "FfewsAdapter", "EmulatedFfews", "STATIONS", "LABEL", "CATCHMENT_M"]

LABEL = "EMULATED"
CATCHMENT_M = 3500.0
#: BMC via PTI (ThePrint), 19 Aug 2025: six stations, 43 pumps, 2.58 lakh l/s in aggregate
SOURCE_MAJOR = "https://theprint.in/india/mumbai-receives-over-200-mm-of-rain-in-11-hours/2724336"
#: PTI (The Week), 28 May 2025: penalties on four mini pumping station operators
SOURCE_MINI = "https://www.theweek.in/wire-updates/national/2025/05/28/bom2-mh-waterlogging-penalty.html"
MAJOR_PUMPS_TOTAL = 43
MAJOR_CAPACITY_LPS = 258000


@dataclass(frozen=True)
class PumpStation:
    id: str
    name: str
    lat: float
    lon: float
    capacity_cusec: float | None
    source: str
    kind: str = "major"            # "major" (sea outfall) | "mini" (low spot)
    location: str = "approximate"  # "landmark" (cities/mumbai/landmarks.json) | "approximate"
    #: invented pump count (EMULATED); None → seeded 4..12
    pumps: int | None = None


#: BMC storm-water pumping stations named in public sources. ``capacity_cusec`` stays None: only the six
#: major stations' aggregate is published (MAJOR_CAPACITY_LPS). Pump counts are EMULATED (they sum to 43).
STATIONS: list[PumpStation] = [
    PumpStation("haji_ali_ps", "Haji Ali pumping station", 18.981, 72.813, None, SOURCE_MAJOR, "major", "landmark", 8),
    PumpStation("love_grove_ps", "Love Grove pumping station", 19.008, 72.815, None, SOURCE_MAJOR, "major", "landmark", 9),
    PumpStation("cleveland_bunder_ps", "Cleveland Bunder pumping station", 19.015, 72.815, None, SOURCE_MAJOR, "major",
                "landmark", 6),
    PumpStation("britannia_ps", "Britannia pumping station (Reay Road)", 18.969, 72.847, None, SOURCE_MAJOR, "major",
                "landmark", 6),
    PumpStation("irla_ps", "Irla pumping station", 19.101, 72.833, None, SOURCE_MAJOR, "major", "landmark", 7),
    PumpStation("gazdarbandh_ps", "Gazdarbandh pumping station (Khar)", 19.076, 72.829, None, SOURCE_MAJOR, "major",
                "landmark", 7),
    PumpStation("hindmata_mps", "Hindmata mini pumping station", 19.0056, 72.8398, None, SOURCE_MINI, "mini",
                "approximate", 3),
    PumpStation("gandhi_market_mps", "Gandhi Market mini pumping station (Matunga)", 19.0306, 72.8590, None,
                SOURCE_MINI, "mini", "approximate", 3),
    PumpStation("yellow_gate_mps", "Yellow Gate mini pumping station", 18.9447, 72.8405, None, SOURCE_MINI, "mini",
                "approximate", 2),
    PumpStation("chunabhatti_mps", "Chunabhatti mini pumping station", 19.0526, 72.8726, None, SOURCE_MINI, "mini",
                "approximate", 2),
]


@dataclass
class PumpState:
    station: PumpStation
    pumps_total: int
    pumps_running: int
    pumps_available: int
    sump_level_pct: float | None
    observed_at: datetime
    label: str

    @property
    def availability(self) -> float:
        return self.pumps_available / self.pumps_total if self.pumps_total else 0.0

    def as_dict(self) -> dict:
        s = self.station
        return {"id": s.id, "name": s.name, "kind": s.kind, "lat": s.lat, "lon": s.lon, "location": s.location,
                "capacity_cusec": s.capacity_cusec, "pumps_total": self.pumps_total,
                "pumps_available": self.pumps_available, "pumps_running": self.pumps_running,
                "availability": round(self.availability, 2), "sump_level_pct": self.sump_level_pct,
                "observed_at": self.observed_at.isoformat(), "label": self.label, "source": s.source}


class FfewsAdapter(Protocol):
    label: str

    def states(self, at: datetime, rain_mm_h: float = 0.0) -> list[PumpState]: ...


class EmulatedFfews:
    """Deterministic stand-in: each station has a fixed pump count; one pump at a station is down for
    maintenance on a rotating, seeded schedule; in rain every available pump runs. EMULATED."""

    label = LABEL

    def __init__(self, seed: int = 1916) -> None:
        self.seed = seed

    def _h(self, *parts: object) -> int:
        return int.from_bytes(hashlib.blake2b("|".join(map(str, parts)).encode(), digest_size=4).digest(), "little")

    def states(self, at: datetime, rain_mm_h: float = 0.0) -> list[PumpState]:
        at = at.astimezone(UTC)
        day = at.date().isoformat()
        out = []
        for st in STATIONS:
            total = st.pumps if st.pumps is not None else 4 + self._h(self.seed, st.id) % 9  # invented
            down = 1 if self._h(self.seed, st.id, day) % 5 == 0 else 0
            avail = total - down
            running = avail if rain_mm_h > 2.0 else min(avail, 1 + self._h(self.seed, st.id, at.hour) % 2)
            sump = round(min(100.0, 20.0 + 6.0 * rain_mm_h), 1)
            out.append(PumpState(st, total, running, avail, sump, at, LABEL))
        return out


def station_for(lat: float, lon: float) -> tuple[PumpStation | None, float]:
    best, bd = None, float("inf")
    for st in STATIONS:
        d = haversine_m(lat, lon, st.lat, st.lon)
        if d < bd:
            best, bd = st, d
    return (best, bd) if bd <= CATCHMENT_M else (None, bd)
