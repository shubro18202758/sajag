"""Mumbai's tide: the MODELLED Apollo Bunder tide, checked against the BMC's PUBLISHED high-tide advisories.

* **Modelled.** ``tide_model.py`` is a byte-for-byte copy of ``services/hydro/src/hydro/tide.py`` (a test keeps the two
  identical): the Apollo Bunder (Mumbai harbour) harmonic model — Admiralty constants as tabulated by Unnikrishnan
  (2022, Current Science 123(8)), N2/K2 inferred, mean level fitted. It runs here, on this box, with no call out.
  The next 48 hours of high and low waters, the level now, and whether the outfall gates are shut (≥ 4.5 m, the BMC's
  high-tide threshold). Label: MODELLED (approximate).
* **Published.** The Mumbai Port Authority's tide tables are not published in a machine-readable form, and the BMC's
  high-tide calendar comes out as a press note before each monsoon. What can be cited is what the BMC published and
  the press printed: the high-tide spells of 24–28 June and 24–27 July 2025 (times and heights) and the full tide table
  of 24 July 2025 (Free Press Journal, citing the BMC). They are shown as PUBLISHED, with their source, and the model is
  compared with them (nearest modelled extreme of the same kind: minutes and metres apart) — the sanity check of the
  model. The BMC's 2026 calendar (its spells and peak, as reported) is listed beside them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from cityfeeds.tide_model import GATE_CLOSE_LEVEL_M, LABEL, SOURCES, TideModel

__all__ = ["PUBLISHED", "BMC_2026", "compare", "tide_table_view", "MODEL"]

IST = ZoneInfo("Asia/Kolkata")
MODEL = TideModel()

_FPJ_JUNE = {"publisher": "Free Press Journal, citing the BMC", "date": "2025-06-23",
             "url": "https://www.freepressjournal.in/mumbai/mumbaikars-alert-bmc-warns-of-5-day-high-tide-spell-from-"
                    "june-2428-waves-to-cross-475-metres"}
_FPJ_JULY = {"publisher": "Free Press Journal, citing the BMC", "date": "2025-07-24",
             "url": "https://www.freepressjournal.in/mumbai/mumbai-rains-city-to-experience-high-tide-149-feet-bmc-"
                    "issues-alert-till-july-31"}


def _row(kind: str, y: int, mo: int, d: int, h: int, mi: int, level: float, src: dict) -> dict[str, Any]:
    return {"kind": kind, "at": datetime(y, mo, d, h, mi, tzinfo=IST).isoformat(), "level_m": level,
            "source": src["publisher"] + ", " + src["date"], "url": src["url"]}


#: high and low waters the BMC published (as printed), IST, metres above chart datum
PUBLISHED: list[dict[str, Any]] = [
    _row("high", 2025, 6, 24, 11, 15, 4.59, _FPJ_JUNE), _row("high", 2025, 6, 25, 12, 5, 4.71, _FPJ_JUNE),
    _row("high", 2025, 6, 26, 12, 55, 4.75, _FPJ_JUNE), _row("high", 2025, 6, 27, 13, 40, 4.73, _FPJ_JUNE),
    _row("high", 2025, 6, 28, 14, 26, 4.64, _FPJ_JUNE),
    _row("low", 2025, 7, 24, 5, 7, 0.43, _FPJ_JULY), _row("high", 2025, 7, 24, 11, 58, 4.57, _FPJ_JULY),
    _row("low", 2025, 7, 24, 18, 13, 1.62, _FPJ_JULY), _row("high", 2025, 7, 24, 23, 40, 3.72, _FPJ_JULY),
    _row("high", 2025, 7, 25, 12, 40, 4.66, _FPJ_JULY), _row("high", 2025, 7, 26, 13, 20, 4.67, _FPJ_JULY),
    _row("high", 2025, 7, 27, 13, 56, 4.60, _FPJ_JULY),
]

#: the BMC's 2026 high-tide calendar as reported (no times were printed): spells and heights
BMC_2026 = {
    "spells": [{"dates": "14–19 June 2026", "heights_m": "4.64–4.87"}, {"dates": "13–18 July 2026", "heights_m": "up to 4.89"},
               {"dates": "12–16 August 2026", "heights_m": "4.50–4.83"},
               {"dates": "10–28 September 2026", "heights_m": "the season's most active spell (heights not printed)"}],
    "peak": {"date": "2026-07-16", "level_m": 4.89},
    "source": "Free Press Journal, 13 Jun 2026, citing the BMC's 2026 high-tide calendar",
    "url": "https://www.freepressjournal.in/mumbai/mumbai-monsoon-alert-bmc-releases-2026-high-tide-schedule-citizens-"
           "advised-to-stay-away-from-sea-during-peak-tides",
}


def compare(published: list[dict], modelled: list[dict]) -> dict[str, Any]:
    """Each published extreme vs the nearest modelled extreme of the same kind: minutes and metres apart."""
    pairs = []
    for p in published:
        pt = datetime.fromisoformat(p["at"])
        same = [m for m in modelled if m["kind"] == p["kind"]]
        if not same:
            continue
        m = min(same, key=lambda m: abs((datetime.fromisoformat(m["at"]) - pt).total_seconds()))
        pairs.append({"kind": p["kind"], "published_at": p["at"], "modelled_at": m["at"],
                      "dt_min": round((datetime.fromisoformat(m["at"]) - pt).total_seconds() / 60),
                      "published_m": p["level_m"], "modelled_m": m["level_m"],
                      "dh_m": round(m["level_m"] - p["level_m"], 2)})
    if not pairs:
        return {"pairs": [], "mean_abs_dt_min": None, "mean_abs_dh_m": None}
    return {"pairs": pairs,
            "mean_abs_dt_min": round(sum(abs(x["dt_min"]) for x in pairs) / len(pairs)),
            "max_abs_dt_min": max(abs(x["dt_min"]) for x in pairs),
            "mean_abs_dh_m": round(sum(abs(x["dh_m"]) for x in pairs) / len(pairs), 2),
            "max_abs_dh_m": max(abs(x["dh_m"]) for x in pairs)}


def _extremes(start: datetime, hours: float) -> list[dict[str, Any]]:
    return [{"kind": e.kind, "at": e.at.astimezone(IST).isoformat(), "level_m": e.level_m}
            for e in MODEL.extremes(start, hours)]


def _published_check() -> dict[str, Any]:
    days = sorted({datetime.fromisoformat(p["at"]).date() for p in PUBLISHED})
    modelled: list[dict[str, Any]] = []
    for d in days:
        modelled += _extremes(datetime(d.year, d.month, d.day, tzinfo=IST) - timedelta(hours=3), 30)
    return compare(PUBLISHED, modelled)


_CHECK = _published_check()  # fixed published rows: computed once


def tide_table_view(now: datetime | None = None, hours: float = 48) -> dict[str, Any]:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    level = MODEL.level(now)
    return {
        "published": {"label": "PUBLISHED", "status": 200, "highs_lows": PUBLISHED,
                      "publisher": "BMC (high-tide advisories as printed by the press)",
                      "result": f"{len(PUBLISHED)} BMC-published high and low waters (June–July 2025) with their "
                                "sources; the 2026 calendar's spells beside them",
                      "bmc_2026": BMC_2026, "checked_at": None, "mode": "PUBLISHED"},
        "modelled": {"label": "MODELLED", "sub_label": LABEL,
                     "source": "Apollo Bunder harmonic tide model (tide_model.py, a copy of the hydro service's tide.py)",
                     "station": MODEL.station_name, "datum": MODEL.datum,
                     "now": {"t": now.isoformat(), "level_m": round(level, 2), "gate_closed": MODEL.gate_closed(now),
                             "outfall_restriction": round(MODEL.outfall_restriction(now), 2),
                             "rising": MODEL.level(now + timedelta(minutes=10)) > level},
                     "gate_close_level_m": GATE_CLOSE_LEVEL_M,
                     "highs_lows": _extremes(now, hours), "sources": SOURCES, "error": None},
        "comparison": {"status": "the model against the BMC's published 2025 tides", **_CHECK,
                       "method": "nearest modelled extreme of the same kind; minutes and metres apart"},
    }
