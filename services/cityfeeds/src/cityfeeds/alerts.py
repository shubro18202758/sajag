"""Official alerts for Mumbai from NDMA Sachet, India's Common Alerting Protocol (CAP) feed: LIVE, filtered.

**What.** Sachet (sachet.ndma.gov.in) is the National Disaster Management Authority's integrated alert system: IMD's
regional centres, the state disaster management authorities and others publish CAP 1.2 alerts there. Its public RSS
(``/cap_public_website/rss/rss_india.xml``, the latest 100 alerts for India, no key) lists each alert's text, its
issuing office (the RSS ``author``: "IMD Mumbai", "Maharashtra SDMA", …), the time and a link to the CAP XML. Checked
from this box on 30 Oct 2026: 200, 100 items, four from IMD Mumbai (nowcasts for Thane, Ahilyanagar and Nashik).

**Filter.** An alert is kept when its issuer is a Maharashtra office (IMD Mumbai, Maharashtra SDMA, the Regional
Meteorological Centre Mumbai) or its text names Maharashtra or a Mumbai-region district (Mumbai, Mumbai Suburban,
Thane, Palghar, Raigad; in English, Marathi or Hindi). It is **for Mumbai** when the text or the CAP area names Mumbai
or Mumbai Suburban. For at most :data:`MAX_CAP` kept alerts per refresh the CAP XML is read for the English headline,
severity, urgency, area and validity; nothing else is fetched.

Events, never people: an alert is about a place and a hazard. Label: LIVE (NDMA Sachet), issuer named on every item.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

__all__ = ["fetch_alerts", "alerts_view", "parse_rss", "parse_cap", "is_maharashtra", "is_mumbai", "MAX_CAP",
           "SACHET_SOURCE"]

MAX_CAP = 6
SACHET_SOURCE = {"publisher": "National Disaster Management Authority — Sachet (CAP)", "url": "https://sachet.ndma.gov.in/",
                 "feed": "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"}

_ISSUER = re.compile(r"IMD Mumbai|Maharashtra|RMC Mumbai|Regional Meteorological Centre,? Mumbai", re.I)
_REGION = re.compile(r"Maharashtra|Mumbai|Thane|Palghar|Raigad|महाराष्ट्र|मुंबई|ठाणे|ठाण्या|पालघर|रायगड", re.I)
_MUMBAI = re.compile(r"Mumbai|मुंबई|बृहन्मुंबई", re.I)
#: "Mantralaya Mumbai" signs every Maharashtra alert; it says who sent it, not where it applies
_SIGNATURE = re.compile(r"मंत्रालय[,.\s]*मुंबई\s*\.?|Mantralaya,?\s*Mumbai", re.I)
_CAP = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}


def parse_rss(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    out = []
    for it in root.iter("item"):
        def tx(tag: str) -> str:
            el = it.find(tag)
            return (el.text or "").strip() if el is not None else ""
        author = tx("author")
        issuer = author.split("(", 1)[1].rstrip(")").strip() if "(" in author else author
        try:
            at = parsedate_to_datetime(tx("pubDate")).astimezone(UTC).isoformat() if tx("pubDate") else None
        except (TypeError, ValueError):
            at = None
        out.append({"id": tx("guid"), "text": tx("title"), "category": tx("category"), "issuer": issuer,
                    "cap_url": tx("link"), "published_at": at})
    return out


def is_maharashtra(item: dict[str, Any]) -> bool:
    return bool(_ISSUER.search(item.get("issuer") or "") or _REGION.search(_SIGNATURE.sub("", item.get("text") or "")))


def is_mumbai(item: dict[str, Any]) -> bool:
    hay = " ".join([_SIGNATURE.sub("", item.get("text") or ""), item.get("headline_en") or "", item.get("area") or ""])
    return bool(_MUMBAI.search(hay))


def parse_cap(xml_text: str) -> dict[str, Any]:
    """The first English ``info`` block (else the first): headline, event, severity, urgency, certainty, validity, area."""
    root = ET.fromstring(xml_text)
    infos = root.findall("cap:info", _CAP)
    info = next((i for i in infos if (i.findtext("cap:language", "", _CAP) or "").lower().startswith("en")),
                infos[0] if infos else None)
    if info is None:
        return {}
    g = lambda tag: (info.findtext(f"cap:{tag}", "", _CAP) or "").strip()  # noqa: E731
    areas = [(a.findtext("cap:areaDesc", "", _CAP) or "").strip() for a in info.findall("cap:area", _CAP)]
    return {"headline_en": g("headline"), "event": g("event"), "severity": g("severity"), "urgency": g("urgency"),
            "certainty": g("certainty"), "effective": g("effective"), "expires": g("expires"),
            "area": "; ".join(a for a in areas if a)}


async def fetch_alerts(client: httpx.AsyncClient, rss_url: str) -> dict[str, Any]:
    r = await client.get(rss_url)
    r.raise_for_status()
    items = parse_rss(r.text)
    kept = [i for i in items if is_maharashtra(i)]
    for it in kept[:MAX_CAP]:
        if not it.get("cap_url", "").startswith("https://sachet.ndma.gov.in/"):
            continue
        try:
            c = await client.get(it["cap_url"])
            c.raise_for_status()
            it.update(parse_cap(c.text))
        except Exception as exc:  # noqa: BLE001 — the RSS text still stands
            it["cap_error"] = f"{type(exc).__name__}"[:60]
    return {"items_in_feed": len(items), "kept": kept}


def _active(it: dict[str, Any], now: datetime) -> bool:
    exp = it.get("expires")
    if not exp:
        return True
    try:
        return datetime.fromisoformat(exp) >= now
    except ValueError:
        return True


def alerts_view(raw: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    rows = []
    for it in (raw or {}).get("kept") or []:
        rows.append({**it, "for_mumbai": is_mumbai(it), "active": _active(it, now), "label": "LIVE"})
    rows.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    mumbai = [r for r in rows if r["for_mumbai"] and r["active"]]
    return {
        "label": "LIVE" if raw is not None else "UNAVAILABLE",
        "what": "official CAP alerts (IMD, the SDMAs) from NDMA Sachet, kept when issued for Maharashtra or naming the "
                "Mumbai region; 'for_mumbai' when the text or area names Mumbai",
        "items_in_feed": (raw or {}).get("items_in_feed"),
        "maharashtra": len(rows),
        "mumbai_active": len(mumbai),
        "items": rows[:20],
        "source": SACHET_SOURCE,
    }
