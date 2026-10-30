"""Deterministic SIMULATED Mumbai traffic history (V/C, speed and covariates per segment, 15-min steps).

Everything here is labelled ``SIMULATED``: it exists so the forecaster, the baseline and the backtest can
run offline and reproducibly when the platform has no (or too little) recorded traffic. It is a
*modelled rhythm*, not a measurement:

* **office peaks** — weekday demand ramps to a morning peak (09:30–11:00 IST) and a longer evening peak
  (17:30–20:30); Saturday is lighter, Sunday lighter still; roads towards South Mumbai (Churchgate /
  Fort / Nariman Point) load inbound in the morning and outbound in the evening;
* **Ganeshotsav** — on the festival days (``calendar.py``) roads near the big pandals (Lalbaugcha Raja,
  GSB Seva Mandal at King's Circle) load from 17:00 to 02:00; on immersion days the roads to the
  immersion points (Girgaon Chowpatty, Dadar Chowpatty by Shivaji Park, Juhu) load in the evening, and on
  Anant Chaturdashi the Lalbaug → Girgaon procession roads load from late morning through the night;
  office peaks thin out; the event covariate is 1 there;
* **rain** — storm cells with a monsoon-shaped monthly frequency (June–September; July the wettest month,
  as in IMD's Santacruz climatology) cut capacity and a little demand; where a segment is low-lying —
  near one of the chronic flooding spots the BMC and the press name (Hindmata, King's Circle, Sion,
  Dadar TT, Parel, Milan and Andheri subways, Kurla by the Mithi; MUMBAI.md §2) — accumulated rain
  while the sea outfalls are shut at high tide (the tide model, ``tide.py``) cuts capacity further: the
  waterlogging-at-high-tide effect;
* **events** — SIMULATED Wankhede Stadium egress evenings (outside the monsoon) load the roads around
  Churchgate and Marine Lines; the Mumbai Marathon morning, New Year's Eve on Marine Drive / the
  chowpatties and the Mount Mary fair in Bandra load the roads near them (dates: ``calendar.py``);
* **incidents** — rare breakdowns that no covariate announces (forecast error the models must live with);
* AR(1) noise.

Determinism: every random draw is seeded by (seed, segment, IST day) or (seed, IST day), so the value at a
given instant does not depend on the window asked for.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import numpy as np

from forecast.bpr import speed_from_vc
from forecast.calendar import ganeshotsav_day, marathon_day, mount_mary_fair, new_year_eve, visarjan_day
from forecast.network import Network, Segment, haversine_m
from forecast.tide import TideModel

__all__ = ["History", "SyntheticCity", "LABEL", "align"]

LABEL = "SIMULATED"
_IST_MIN = 330
#: where the morning commute heads: Churchgate / Fort (South Mumbai's office district)
_CENTRE = (18.9353, 72.8274)
# Points below: cities/mumbai/landmarks.json ids and coordinates, unless marked approximate.
#: the big Ganeshotsav pandals
_PANDALS = {"lalbaugcha_raja": (18.9946, 72.8356), "gsb_kings_circle": (19.029, 72.856)}
#: immersion points (Dadar Chowpatty lies on the shore by Shivaji Park)
_IMMERSION = {"girgaon_chowpatty": (18.9548, 72.8136), "shivaji_park": (19.027, 72.838),
              "juhu_beach": (19.098, 72.826)}
#: the Anant Chaturdashi procession: Lalbaug → Girgaon Chowpatty (MODELLED as its landmark ends and
#: the Lalbaug–Girgaon midpoint; approximate)
_PROCESSION = [(18.9935, 72.8355), (18.9740, 72.8245), (18.9548, 72.8136)]
_WANKHEDE = (18.9389, 72.8258)
#: the marathon route's landmarks: CSMT, Marine Drive, Haji Ali, Worli Naka, the Sea Link (approximate)
_MARATHON = [(18.9398, 72.8355), (18.943, 72.823), (18.9827, 72.8125), (19.0068, 72.8186), (19.038, 72.817)]
_NEW_YEAR = [(18.943, 72.823), (18.9548, 72.8136), (18.922, 72.8347), (19.098, 72.826)]
#: Mount Mary Basilica, Bandra West (approximate; not a landmarks.json id)
_MOUNT_MARY = (19.0467, 72.8226)
#: chronic flooding spots (MUMBAI.md §2; landmarks.json ids)
_FLOOD_SPOTS = {
    "hindmata": (19.0049, 72.8424), "kings_circle": (19.0274, 72.8571), "sion_circle": (19.04, 72.864),
    "dadar_tt": (19.0176, 72.848), "parel": (18.996, 72.84), "milan_subway": (19.088, 72.842),
    "andheri_subway": (19.1183, 72.8467), "mithi_kurla": (19.073, 72.878),
}

_WEEKDAY = np.array([0.18, 0.12, 0.10, 0.10, 0.12, 0.18, 0.30, 0.45, 0.62, 0.80, 0.86, 0.80,
                     0.72, 0.70, 0.70, 0.72, 0.78, 0.86, 0.90, 0.90, 0.80, 0.62, 0.44, 0.30])
_SATURDAY = np.array([0.22, 0.15, 0.12, 0.10, 0.11, 0.15, 0.24, 0.36, 0.50, 0.62, 0.68, 0.70,
                      0.66, 0.64, 0.64, 0.68, 0.74, 0.82, 0.86, 0.84, 0.74, 0.58, 0.44, 0.32])
_SUNDAY = np.array([0.24, 0.16, 0.12, 0.10, 0.10, 0.12, 0.18, 0.26, 0.36, 0.46, 0.52, 0.56,
                    0.56, 0.54, 0.54, 0.58, 0.64, 0.72, 0.76, 0.74, 0.64, 0.50, 0.38, 0.30])
#: storm cells per day by month (MODELLED shape: a dry season, the south-west monsoon June–September)
_STORMS_PER_DAY = {1: 0.02, 2: 0.02, 3: 0.02, 4: 0.03, 5: 0.12, 6: 1.4, 7: 2.0, 8: 1.6, 9: 1.0,
                   10: 0.3, 11: 0.06, 12: 0.02}
_CLASS_SCALE = {"motorway": 0.86, "trunk": 0.92, "primary": 0.95, "secondary": 0.9, "tertiary": 0.8}


def _near(lat: float, lon: float, pts, radius_m: float) -> float:
    """1 at a point, falling linearly to 0 at ``radius_m``."""
    d = min(haversine_m(lat, lon, *p) for p in pts)
    return float(np.clip(1.0 - d / radius_m, 0.0, 1.0))


def align(t: datetime, step_min: int = 15) -> datetime:
    t = t.astimezone(UTC).replace(second=0, microsecond=0)
    return t - timedelta(minutes=t.minute % step_min)


def _rng(*parts: object) -> np.random.Generator:
    h = hashlib.blake2b("|".join(map(str, parts)).encode(), digest_size=8).digest()
    return np.random.default_rng(int.from_bytes(h, "little"))


@dataclass
class History:
    segment_id: int
    start: datetime  # UTC, step-aligned; times[i] = start + i·step
    step_min: int
    vc: np.ndarray
    speed: np.ndarray
    rain_mm_h: np.ndarray
    gate_closed: np.ndarray
    event: np.ndarray
    free_flow_kmh: float
    label: str
    source: str
    notes: list[str] = field(default_factory=list)

    @property
    def n(self) -> int:
        return int(self.vc.shape[0])

    def time_at(self, i: int) -> datetime:
        return self.start + timedelta(minutes=self.step_min * i)

    @property
    def end(self) -> datetime:
        """The time of the last step."""
        return self.time_at(self.n - 1)

    def covariates(self) -> dict[str, np.ndarray]:
        return {"rain_mm_h": self.rain_mm_h, "gate_closed": self.gate_closed, "event": self.event}

    def slice(self, i0: int, i1: int) -> "History":
        return History(self.segment_id, self.time_at(i0), self.step_min, self.vc[i0:i1], self.speed[i0:i1],
                       self.rain_mm_h[i0:i1], self.gate_closed[i0:i1], self.event[i0:i1],
                       self.free_flow_kmh, self.label, self.source, list(self.notes))


class SyntheticCity:
    """The SIMULATED world for one network and seed."""

    def __init__(self, network: Network, seed: int = 1853, step_min: int = 15) -> None:
        self.net = network
        self.seed = seed
        self.step = step_min
        self.tide = TideModel()  # the city's outfall tide station (Apollo Bunder for Mumbai; tide.py)
        self._seg_params = {sid: self._params(s) for sid, s in network.segments.items()}

    # ── per-segment constants ─────────────────────────────────────────────
    def _params(self, s: Segment) -> dict:
        r = _rng(self.seed, "seg", s.segment_id)
        lat, lon = s.midpoint
        fj, tj = self.net.junctions.get(s.from_junction), self.net.junctions.get(s.to_junction)
        inbound = 0.0
        if fj and tj:
            d_from = haversine_m(fj.lat, fj.lon, *_CENTRE)
            d_to = haversine_m(tj.lat, tj.lon, *_CENTRE)
            inbound = float(np.clip((d_from - d_to) / 2000.0, -1.0, 1.0))
        # low-lying: a random share everywhere, high near a chronic flooding spot
        flood_spot = _near(lat, lon, _FLOOD_SPOTS.values(), 900.0)
        return {
            "scale": _CLASS_SCALE.get(s.road_class, 0.9) * float(r.uniform(0.86, 1.12)),
            "inbound": inbound,
            "low_lying": float(max(0.6 * r.beta(2.0, 3.0), 0.55 + 0.45 * flood_spot if flood_spot > 0 else 0.0)),
            "ff": s.speed_limit_kmh * float(r.uniform(0.92, 1.05)),
            "pandal": _near(lat, lon, _PANDALS.values(), 1500.0),
            "immersion": _near(lat, lon, _IMMERSION.values(), 1500.0),
            "procession": _near(lat, lon, _PROCESSION, 900.0),
            "wankhede": haversine_m(lat, lon, *_WANKHEDE) < 1800.0,
            "marathon": _near(lat, lon, _MARATHON, 1200.0),
            "new_year": _near(lat, lon, _NEW_YEAR, 1500.0),
            "mount_mary": _near(lat, lon, [_MOUNT_MARY], 1500.0),
            "rain_mult": float(r.uniform(0.75, 1.25)),
        }

    # ── city-wide drivers (shared by all segments) ────────────────────────
    def _times(self, start: datetime, n: int) -> np.ndarray:
        base = int(start.timestamp() // 60)
        return base + self.step * np.arange(n)  # epoch minutes, UTC

    @staticmethod
    def _ist_days(minutes: np.ndarray) -> list[date]:
        ist = minutes + _IST_MIN
        return [date.fromordinal(date(1970, 1, 1).toordinal() + int(d)) for d in (ist // 1440)]

    def _storms(self, d: date) -> list[tuple[float, float, float, int]]:
        """(start minute-of-day IST, duration min, peak mm/h, id) for one IST day."""
        r = _rng(self.seed, "storm", d.isoformat())
        k = r.poisson(_STORMS_PER_DAY[d.month])
        hours = np.arange(24)
        # monsoon rain over Mumbai comes at any hour (no strong afternoon peak): a mild night bias
        w = np.where((hours >= 18) | (hours <= 5), 1.3, 1.0)
        w /= w.sum()
        out = []
        for i in range(k):
            h = r.choice(hours, p=w)
            out.append((float(h * 60 + r.uniform(0, 60)), float(r.uniform(60, 240)),
                        float(np.clip(r.lognormal(np.log(14.0), 0.75), 3.0, 100.0)), i))
        return out

    def city_rain(self, start: datetime, n: int) -> np.ndarray:
        """City-scale rain intensity (mm/h) at each step, before the per-segment multiplier."""
        mins = self._times(start, n)
        out = np.zeros(n)
        ist = mins + _IST_MIN
        for d in sorted({*self._ist_days(mins), *[x - timedelta(days=1) for x in self._ist_days(mins[:1])]}):
            day0 = (d.toordinal() - date(1970, 1, 1).toordinal()) * 1440
            for st, dur, peak, _ in self._storms(d):
                t = ist - (day0 + st)
                m = (t >= 0) & (t <= dur)
                # triangular hyetograph, peak at 35 % of the storm
                tp = 0.35 * dur
                out[m] += np.where(t[m] <= tp, peak * t[m] / tp, peak * (dur - t[m]) / (dur - tp))
        return out

    def gate_closed(self, start: datetime, n: int) -> np.ndarray:
        return np.array([1.0 if self.tide.gate_closed(start + timedelta(minutes=self.step * i)) else 0.0
                         for i in range(n)])

    # ── one segment ───────────────────────────────────────────────────────
    def history(self, sid: int, start: datetime, end: datetime, *, rain: np.ndarray | None = None,
                gates: np.ndarray | None = None) -> History:
        start = align(start, self.step)
        n = int((align(end, self.step) - start).total_seconds() // (60 * self.step)) + 1
        p = self._seg_params[sid]
        mins = self._times(start, n)
        ist = mins + _IST_MIN
        tod = (ist % 1440) / 60.0
        days = self._ist_days(mins)
        rain_city = self.city_rain(start, n) if rain is None else rain
        rain = rain_city * p["rain_mult"]
        gates = self.gate_closed(start, n) if gates is None else gates

        # demand profile by day type (linear interpolation between hourly knots)
        h0 = np.floor(tod).astype(int) % 24
        frac = tod - np.floor(tod)
        dow = np.array([d.weekday() for d in days])
        prof = np.empty(n)
        for table, mask in ((_WEEKDAY, dow < 5), (_SATURDAY, dow == 5), (_SUNDAY, dow == 6)):
            prof[mask] = (table[h0] * (1 - frac) + table[(h0 + 1) % 24] * frac)[mask]
        morning = np.exp(-0.5 * ((tod - 10.0) / 1.8) ** 2)
        evening = np.exp(-0.5 * ((tod - 19.0) / 2.0) ** 2)
        direction = 1.0 + 0.12 * p["inbound"] * (morning - evening)
        demand = prof * direction * p["scale"]

        # Ganeshotsav: the festival "night" runs 17:00–02:00, so the small hours belong to the day before
        night = (tod >= 17.0) | (tod < 2.0)
        fest_day = np.array([ganeshotsav_day(d) for d in days])
        fest = np.where(tod < 2.0, np.array([ganeshotsav_day(d - timedelta(days=1)) for d in days]), fest_day)
        imm = np.where(tod < 6.0, np.array([visarjan_day(d - timedelta(days=1)) for d in days]),
                       np.array([visarjan_day(d) for d in days]))
        demand = np.where((fest_day >= 1) & ~night & (tod >= 8.0), demand * 0.85, demand)
        fest_load = np.where(night & (fest >= 1), 0.04 + 0.18 * p["pandal"], 0.0)
        # immersions: intermediate ones in the evening near the chowpatties; Anant Chaturdashi from
        # 10:00 through to 06:00 next morning along the Lalbaug → Girgaon procession and at the beaches
        imm_evening = (imm == 1) & ((tod >= 17.0) | (tod < 1.0))
        anant = (imm == 2) & ((tod >= 10.0) | (tod < 6.0))
        imm_load = (np.where(imm_evening, 0.20 * p["immersion"], 0.0)
                    + np.where(anant, 0.30 * max(p["procession"], p["immersion"]), 0.0))
        demand = demand + fest_load + imm_load
        demand = demand * (1.0 - np.minimum(0.15, 0.003 * rain))

        # capacity: rain, then waterlogging where low-lying while the sea outfalls are shut
        k = int(60 // self.step) * 3
        rain_3h = np.convolve(rain, np.ones(k) * self.step / 60.0, mode="full")[:n]
        waterlog = p["low_lying"] * np.minimum(0.35, 0.004 * rain_3h) * np.where(gates > 0, 1.6, 1.0)
        cap = 1.0 - np.minimum(0.4, 0.010 * rain) - waterlog
        vc = demand / np.maximum(cap, 0.35)

        # events (SIMULATED)
        event = np.zeros(n)
        for d in sorted(set(days)):
            t = ist - (d.toordinal() - date(1970, 1, 1).toordinal()) * 1440  # minutes since IST midnight
            # Wankhede egress around 23:00 on a few evenings outside the monsoon
            if p["wankhede"] and d.month not in (6, 7, 8, 9):
                r = _rng(self.seed, "wankhede", d.isoformat())
                if r.random() < 0.08:
                    te = t - 23 * 60
                    m = (te >= 0) & (te <= 120)
                    event[m] = 1.0
                    vc[m] += 0.32 * np.exp(-te[m] / 70.0)
            # the marathon morning: closures on the route push traffic onto the roads beside it
            if marathon_day(d) and p["marathon"] > 0.2:
                m = (t >= 4 * 60) & (t <= 11 * 60)
                event[m] = 1.0
                vc[m] += 0.25 * p["marathon"]
            # New Year's Eve: 21:00 on 31 Dec to 03:00 on 1 Jan
            if new_year_eve(d) and p["new_year"] > 0.2:
                m = (t >= 21 * 60) & (t <= 27 * 60)
                event[m] = 1.0
                vc[m] += 0.30 * p["new_year"]
            # Mount Mary fair: afternoon and evening crowds in Bandra West
            if mount_mary_fair(d) and p["mount_mary"] > 0.2:
                m = (t >= 15 * 60) & (t <= 22 * 60)
                event[m] = 1.0
                vc[m] += 0.15 * p["mount_mary"]
        event = np.maximum(event, ((fest >= 1) & night & (p["pandal"] > 0.2)).astype(float))
        event = np.maximum(event, ((imm_evening | anant)
                                   & (max(p["immersion"], p["procession"]) > 0.2)).astype(float))

        # incidents (unannounced) and AR(1) noise, both seeded per IST day
        noise = np.zeros(n)
        for d in sorted(set(days)):
            idx = np.array([i for i, x in enumerate(days) if x == d])
            r = _rng(self.seed, "noise", sid, d.isoformat())
            e = r.normal(0.0, 0.028, size=96)
            z = np.empty(96)
            z[0] = e[0] / np.sqrt(1 - 0.85 ** 2)
            for i in range(1, 96):
                z[i] = 0.85 * z[i - 1] + e[i]
            pos = ((ist[idx] % 1440) // self.step).astype(int)
            noise[idx] = z[pos]
            for _ in range(r.poisson(0.15)):
                st, dur, amp = r.uniform(360, 1320), r.uniform(30, 90), r.uniform(0.15, 0.35)
                t = (ist[idx] % 1440) - st
                m = (t >= 0) & (t <= dur)
                noise[idx[m]] += amp
        vc = np.clip(vc + noise, 0.03, 1.8)
        speed = speed_from_vc(vc, p["ff"])
        return History(sid, start, self.step, vc, speed, rain, gates, event, p["ff"], LABEL,
                       f"synthetic Mumbai history (seed {self.seed})")

    def histories(self, sids: list[int], start: datetime, end: datetime) -> dict[int, History]:
        start = align(start, self.step)
        n = int((align(end, self.step) - start).total_seconds() // (60 * self.step)) + 1
        rain = self.city_rain(start, n)
        gates = self.gate_closed(start, n)
        return {sid: self.history(sid, start, end, rain=rain, gates=gates) for sid in sids}
