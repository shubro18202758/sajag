"""Record the offline fixtures (``src/cityfeeds/fixtures/``) from the live feeds, once, politely.

    PYTHONPATH=src python scripts/record_fixtures.py

Each fixture is the RAW answer the service's fetch function returns (GDACS polygons decimated to keep the file
small), so offline mode and the tests run the same parsing code as production. Re-record only on purpose: the
tests pin values from the recorded day (30 Oct 2026, Mumbai).
"""

from __future__ import annotations

import asyncio
import json
import re
import sys

import httpx

from cityfeeds.air import fetch_air
from cityfeeds.config import Settings
from cityfeeds.cyclones import fetch_cyclones
from cityfeeds.fetch import FIXTURES, USER_AGENT
from cityfeeds.geo import decimate
from cityfeeds.heat import fetch_heat
from cityfeeds.fires import fetch_fires_public
from cityfeeds.alerts import fetch_alerts
from cityfeeds.notices import fetch_notices
from cityfeeds.quakes import fetch_quakes
from cityfeeds.river import MITHI_TERMS, fetch_news


def _slim_gdacs(raw: dict) -> dict:
    for g in raw.get("geometry", {}).values():
        for f in g.get("features", []):
            geom = f.get("geometry") or {}
            if geom.get("type") == "Polygon":
                geom["coordinates"] = [decimate(geom["coordinates"][0], 120)]
            for k in ("htmldescription", "icon", "iconoverall"):
                (f.get("properties") or {}).pop(k, None)
    for f in raw.get("events", {}).get("features", []):
        (f.get("properties") or {}).pop("htmldescription", None)
    return raw


async def main(only: set[str]) -> None:
    s = Settings()
    box = (s.region_south, s.region_west, s.region_north, s.region_east)
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers={"user-agent": USER_AGENT}) as c:
        jobs = {
            "air.json": lambda: fetch_air(c, s.open_meteo_air_url),
            "heat.json": lambda: fetch_heat(c, s.open_meteo_forecast_url),
            "gdacs.json": lambda: fetch_cyclones(c, s.gdacs_list_url, s.gdacs_geometry_url, box),
            "news.json": lambda: fetch_news(c),
            "usgs.json": lambda: fetch_quakes(c, s.usgs_url, s.quake_radius_km),
            "mtp_home.html": lambda: fetch_notices(c, s.mtp_url),
            "sachet.json": lambda: fetch_alerts(c, s.sachet_rss_url),
            "firms_mumbai.json": lambda: fetch_fires_public(c),
        }
        for name, job in jobs.items():
            if only and name not in only:
                continue
            try:
                data = await job()
            except Exception as exc:  # noqa: BLE001
                print(f"{name}: FAILED {type(exc).__name__}: {exc}")
                continue
            if name == "gdacs.json":
                data = _slim_gdacs(data)
            if name == "mtp_home.html":  # the anchors outside HTML comments, scripts and styles: menu and notices
                live = re.sub(r"<!--.*?-->|<script.*?</script>|<style.*?</style>", "", data, flags=re.S)
                anchors = re.findall(r'<a[^>]*href="[^"]+"[^>]*>.*?</a>', live, re.S | re.I)
                data = "<!-- Mumbai Traffic Police home and notices pages, anchors only (comments dropped) -->\n" + \
                    "\n".join(a for a in anchors if len(a) < 800)
            if name == "news.json":  # dates only; a headline and its link are kept only when it mentions the Mithi or
                # waterlogging (the rest of a city's news — politics, crime, people — never lands in the repo)
                for f in data["feeds"].values():
                    f["items"] = [{"title": it["title"] if (hit := MITHI_TERMS.search(f"{it['title']} {it['description']}")) else "",
                                   "description": "", "link": it["link"] if hit else "", "pubDate": it["pubDate"]}
                                  for it in f["items"][:40]]
            path = FIXTURES / name
            if name.endswith(".json"):
                path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            else:
                path.write_text(data, encoding="utf-8")
            print(f"{name}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    asyncio.run(main(set(sys.argv[1:])))
