"""The Mithi river and Mumbai's waterlogging signal: an EMULATED gauge and a news count (aggregate).

**Why.** The Mithi runs from Powai and Vihar through Saki Naka, Kurla (Kranti Nagar) and the Bandra Kurla Complex into
Mahim creek; its lower reach is tidal. When a heavy burst meets a high tide it overtops at Kurla, and people are moved
out of Kranti Nagar: on 18–19 Aug 2025 the river was reported at about 3.9 m against a 4 m danger mark (some reports:
crossed it) and 350–500 people were evacuated near Kurla (The Statesman, HT, Business Today; 19–20 Aug 2025).

**No public live gauge.** The Mithi's level sensors belong to the BMC and to IFLOWS-Mumbai (the flood warning system
the Ministry of Earth Sciences built with the BMC); neither publishes an open feed, and the Central Water Commission
has no Mithi station. So the gauge here is **EMULATED**, and says so: a deterministic stand-in whose shape follows
the modelled Apollo Bunder tide (``tide_model.py``; the lower Mithi rises and falls with Mahim creek). It is never a
measurement, never a forecast, and the danger mark beside it is the reported one (4 m at Kurla), given for context.
A real feed replaces ``emulated_mithi`` without changing the view.

**News signal.** Four Mumbai outlets (Mid-day, Times of India Mumbai, Hindustan Times Mumbai; ABP Majha Mumbai in
Marathi) are read at most once per 30 minutes and the items of the last 72 hours that mention the Mithi or
waterlogging are COUNTED. Only the count, the outlet and the link are kept (events, not people). Label: AGGREGATE.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from cityfeeds.geo import MUMBAI, haversine_km
from cityfeeds.tide_model import TideModel

__all__ = ["STATIONS", "NEWS_FEEDS", "fetch_news", "river_view", "count_mentions", "MITHI_TERMS", "emulated_mithi",
           "LABEL"]

LABEL = "EMULATED"

#: the emulated gauge(s): the landmark id, where, the reported danger mark (context only)
STATIONS: list[dict[str, Any]] = [
    {"code": "mithi_kurla", "name": "Mithi at Kurla (Kranti Nagar)", "name_mr": "मिठी नदी, कुर्ला (क्रांती नगर)",
     "river": "Mithi", "role": "lower Mithi, tidal; overtops into Kranti Nagar in a heavy burst at high tide",
     "lat": 19.073, "lon": 72.878, "danger_m": 4.0,
     "danger_source": "reported danger mark at Kurla, 18–19 Aug 2025 (The Statesman; Hindustan Times)"},
]

NEWS_FEEDS = [
    ("midday_mumbai", "https://www.mid-day.com/Resources/midday/rss/mumbai-news.xml", "mid-day.com", "en"),
    ("toi_mumbai", "https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms", "timesofindia.indiatimes.com", "en"),
    ("ht_mumbai", "https://www.hindustantimes.com/feeds/rss/cities/mumbai-news/rssfeed.xml", "hindustantimes.com", "en"),
    ("abp_majha_mumbai", "https://marathi.abplive.com/news/mumbai/feed", "marathi.abplive.com", "mr"),
]

MITHI_TERMS = re.compile(r"\bMithi\b|waterlog\w*|water-?logg\w*|subway (?:shut|closed|flooded)|Andheri subway|Milan subway|"
                         r"Hindmata|मिठी|पाणी साच\w*|पाणी तुंब\w*|जलभराव|सबवे", re.I)
MITHI_TERMS_TEXT = ("Mithi, waterlogging, subway shut/closed/flooded, Andheri subway, Milan subway, Hindmata; "
                    "मिठी, पाणी साचले, पाणी तुंबले, सबवे; जलभराव")
_DOCTYPE = re.compile(r"<!DOCTYPE[^>[]*(\[[^]]*\])?>", re.I | re.S)

_TIDE = TideModel()
#: the emulated gauge's resting level and its tidal swing per metre of sea level (assumptions; EMULATED)
_BASE_M = 1.6
_TIDE_GAIN = 0.25


def emulated_mithi(now: datetime) -> dict[str, Any]:
    """The EMULATED Kurla gauge: base + tidal swing from the modelled Apollo Bunder tide, every 15 min for 6 h back."""
    t0 = now.astimezone(UTC).replace(second=0, microsecond=0)
    t0 -= timedelta(minutes=t0.minute % 15)
    series = []
    for k in range(24, -1, -1):
        t = t0 - timedelta(minutes=15 * k)
        series.append((t.isoformat(), round(_BASE_M + _TIDE_GAIN * (_TIDE.level(t) - _TIDE.mean_level), 2)))
    return {"stations": {"mithi_kurla": {"series": series[::-1]}}, "label": LABEL}


def _items(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(_DOCTYPE.sub("", xml_text))
    items = []
    for it in root.iter("item"):
        def tx(tag: str) -> str:
            el = it.find(tag)
            return (el.text or "").strip() if el is not None else ""
        items.append({"title": tx("title"), "link": tx("link"), "description": tx("description"), "pubDate": tx("pubDate")})
    return items


async def fetch_news(client: httpx.AsyncClient) -> dict[str, Any]:
    out: dict[str, Any] = {"feeds": {}, "errors": {}}
    for fid, url, publisher, lang in NEWS_FEEDS:
        try:
            r = await client.get(url)
            r.raise_for_status()
            out["feeds"][fid] = {"publisher": publisher, "lang": lang, "items": _items(r.text)}
        except Exception as exc:  # noqa: BLE001
            out["errors"][fid] = f"{type(exc).__name__}: {exc}"[:160]
    if not out["feeds"]:
        raise RuntimeError("no news feed answered")
    return out


def count_mentions(news: dict | None, now: datetime, hours: int = 72) -> dict[str, Any]:
    """Aggregate only: how many recent items mention the Mithi or waterlogging, per outlet, with their links."""
    total = 0
    scanned = 0
    per: dict[str, int] = {}
    links: list[dict[str, str]] = []
    for fid, f in (news or {}).get("feeds", {}).items():
        for it in f.get("items", []):
            try:
                at = parsedate_to_datetime(it["pubDate"]) if it.get("pubDate") else None
            except Exception:  # noqa: BLE001
                at = None
            if at is not None and at.tzinfo is None:
                at = at.replace(tzinfo=UTC)
            if at is not None and at < now - timedelta(hours=hours):
                continue
            scanned += 1
            if MITHI_TERMS.search(f"{it.get('title', '')} {it.get('description', '')}"):
                total += 1
                per[f["publisher"]] = per.get(f["publisher"], 0) + 1
                if len(links) < 8:
                    links.append({"publisher": f["publisher"], "link": it.get("link", ""),
                                  "at": at.isoformat() if at else None})
    return {"label": "AGGREGATE", "window_h": hours, "items_scanned": scanned, "mentions": total, "by_outlet": per,
            "links": links, "outlets_read": sorted((news or {}).get("feeds", {}).keys()),
            "outlets_down": sorted((news or {}).get("errors", {}).keys()),
            "terms": MITHI_TERMS_TEXT}


def river_view(raw: dict | None, news: dict | None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    raw = raw if raw is not None else emulated_mithi(now)
    clat, clon = MUMBAI
    stations = []
    worst = "normal"
    order = {"normal": 0, "no_threshold": 0, "above_warning": 2, "above_danger": 3}
    for st in STATIONS:
        ser = ((raw.get("stations") or {}).get(st["code"]) or {}).get("series") or []
        level, at = (ser[0][1], ser[0][0]) if ser else (None, None)
        trend = None
        if len(ser) >= 13:
            d = level - ser[12][1]  # three hours earlier
            trend = "rising" if d > 0.02 else "falling" if d < -0.02 else "steady"
        dl = st["danger_m"]
        status = "no_threshold" if level is None else ("above_danger" if level >= dl else "normal")
        if order.get(status, 0) > order.get(worst, 0):
            worst = status
        stations.append({
            "code": st["code"], "name": st["name"], "name_mr": st["name_mr"], "river": st["river"], "role": st["role"],
            "lat": st["lat"], "lon": st["lon"], "distance_km": round(haversine_km(clat, clon, st["lat"], st["lon"]), 1),
            "reservoir": False, "level_m": level, "observed_at": at, "trend": trend,
            "warning_m": None, "danger_m": dl, "danger_source": st["danger_source"], "frl_m": None,
            "to_warning_m": None, "to_danger_m": round(dl - level, 2) if level is not None else None,
            "status": status, "label": LABEL,
            "note": "EMULATED: no public live Mithi gauge; the shape follows the modelled tide. Not a measurement.",
        })
    above = [s for s in stations if s["status"] in ("above_warning", "above_danger")]
    mentions = count_mentions(news, now) if news else {"label": "UNAVAILABLE", "mentions": None}
    return {
        "label": LABEL,
        "what": "the Mithi at Kurla: an EMULATED gauge (no public live feed; IFLOWS-Mumbai and BMC sensors are the real "
                "source) against the reported 4 m danger mark; Mumbai news mentions of the Mithi and waterlogging",
        "status": worst,
        "above_warning": len(above), "stations_read": len(stations),
        "stations": stations,
        "station_errors": {},
        "news": mentions,
        # the deck's river panel still reads the old key name; same count (compatibility only)
        "dvc_news": mentions,
        "feed_note": "the BMC's and IFLOWS-Mumbai's river sensors are not public; until access is granted the gauge is "
                     "EMULATED and labelled",
        "sources": {"iflows": {"publisher": "IFLOWS-Mumbai (Ministry of Earth Sciences with the BMC)",
                               "note": "flood warning system with river and rain sensors; no open feed"},
                    "context": {"publisher": "The Statesman; Hindustan Times; Business Today",
                                "note": "18–19 Aug 2025: Mithi about 3.9 m against the 4 m danger mark at Kurla; "
                                        "350–500 evacuated near Kranti Nagar (figures differ by report)"}},
    }
