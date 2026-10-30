"""Traffic notices about places and roads, from the Mumbai Traffic Police's public site.

Checked from this box on 30 Oct 2026:

* **Mumbai Traffic Police** (trafficpolicemumbai.maharashtra.gov.in, a government S3WaaS site; ``robots.txt``
  disallows only ``/wp-admin/``): the home page and its "सूचना" (notices) page list the department's public
  notices as links (PDFs and notice pages). One read every 6 hours. Only links whose text reads as a traffic notice
  (advisory, diversion, closure, restriction, notification; वाहतूक, बदल, वळव, बंद, अधिसूचना, निर्बंध, मार्ग) are
  kept, never the page's menu, and never anything about a person (recruitment, awards, names). Each item is the
  notice's own title and link. On 30 Oct 2026 the site listed no current traffic notice (its notices page was last
  updated on 28 Aug 2025; day-to-day advisories go out on the department's social-media accounts, which are not read
  here) — the view says so instead of showing anything.
* **BMC**: the portal (portal.mcgm.gov.in) and the disaster-management site (dm.mcgm.gov.in) are script-rendered
  apps with no public notice feed; they are not read. Label: LIVE (MTP public page), with the count it found.
"""

from __future__ import annotations

import html
import re
from datetime import date
from typing import Any
from urllib.parse import urljoin

import httpx

__all__ = ["fetch_notices", "notices_view", "mtp_advisories", "MTP_URL", "MTP_NOTICES_URL", "ADVISORY", "PERSON_WORDS"]

MTP_URL = "https://trafficpolicemumbai.maharashtra.gov.in/"
MTP_NOTICES_URL = MTP_URL + "%e0%a4%b8%e0%a5%82%e0%a4%9a%e0%a4%a8%e0%a4%be/"  # /सूचना/
ADVISORY = re.compile(r"\b(advisor\w*|diversion|divert\w*|closure|closed|restriction\w*|notification|traffic "
                      r"arrangement\w*)\b|वाहतूक|वळव\w*|बंद|अधिसूचना|निर्बंध|मार्गात बदल|पर्यायी मार्ग", re.I)
PERSON_WORDS = re.compile(r"\b(recruit\w*|candidate|award\w*|appointment|transfer|promotion|tender|deaths?|"
                          r"obituary)\b|भरती|पुरस्कार|सन्मान|बदली|पदोन्नती|निविदा", re.I)
_DATE_IN_NAME = re.compile(r"(\d{2})[._-](\d{2})[._-](\d{4})|/(20\d{2})/(\d{2})/")


def _date(href: str, text: str = "") -> str | None:
    m = _DATE_IN_NAME.search(text) or _DATE_IN_NAME.search(href)
    if not m:
        return None
    try:
        if m.group(1):
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        return f"{m.group(4)}-{m.group(5)}"  # an upload folder: month only
    except ValueError:
        return None


async def fetch_notices(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url)
    r.raise_for_status()
    pages = [r.text]
    if url.rstrip("/") + "/" == MTP_URL:
        try:  # the notices page as well (same host, same polite schedule)
            n = await client.get(MTP_NOTICES_URL)
            if n.status_code == 200:
                pages.append(n.text)
        except httpx.HTTPError:
            pass
    return "\n".join(pages)


def mtp_advisories(page: str | None, base_url: str = MTP_URL) -> list[dict[str, Any]]:
    """The site's current traffic notices (title and link), never its menu, its recruitment or award pages."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    live = re.sub(r"<!--.*?-->|<script.*?</script>|<style.*?</style>", "", page or "", flags=re.S)
    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', live, re.S | re.I):
        href, text = m.group(1).strip(), " ".join(html.unescape(re.sub(r"<[^>]+>", " ", m.group(2))).split())
        if len(text) < 12 or not ADVISORY.search(text) or PERSON_WORDS.search(text):
            continue
        if not (href.lower().endswith(".pdf") or "/notice/" in href or "/document/" in href):
            continue  # a menu entry, not a notice
        link = urljoin(base_url, href.replace(" ", "%20"))
        if not (link.startswith(base_url) or link.startswith("https://cdnbbsr.s3waas.gov.in/")) or link in seen:
            continue
        seen.add(link)
        items.append({"title": text[:200], "link": link, "date": _date(href, text),
                      "publisher": "Mumbai Traffic Police", "label": "LIVE"})
    return items[:20]


def notices_view(page: str | None, error: str | None = None) -> dict[str, Any]:
    items = mtp_advisories(page) if page else []
    return {
        "label": "LIVE" if page else "UNAVAILABLE",
        "what": "the Mumbai Traffic Police's public traffic notices (titles and links only)",
        "items": items,
        "sources": [
            {"publisher": "Mumbai Traffic Police", "url": MTP_URL, "robots": "disallows /wp-admin/ only",
             "status": (f"read: {len(items)} current notice{'' if len(items) == 1 else 's'}"
                        + ("" if items else " (the site lists none; advisories go out on social media, not read here)")
                        if page else f"no answer: {error or 'not read yet'}")},
            {"publisher": "BMC", "url": "https://portal.mcgm.gov.in/",
             "status": "not read: script-rendered portal, no public notice feed"},
        ],
    }
