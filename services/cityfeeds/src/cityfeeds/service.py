"""The city-feeds core: one polite fetcher, the per-feed views, the proposals and the god's-eye summary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from cityfeeds import air_observed as obs
from cityfeeds.air import air_view, fetch_air
from cityfeeds.alerts import alerts_view, fetch_alerts
from cityfeeds.config import Settings
from cityfeeds.cyclones import cyclones_view, fetch_cyclones
from cityfeeds.fetch import Fetched, Fetcher, load_fixture
from cityfeeds.fires import fetch_fires_area, fetch_fires_public, fires_view
from cityfeeds.heat import fetch_heat, heat_view
from cityfeeds.keys import KEYED, key, keyed_state, redact
from cityfeeds.notices import fetch_notices, notices_view
from cityfeeds.street_image import SEARCH_HALF_SIDE_M, PhotoRefused, StreetImages
from cityfeeds.proposals import air_advisory, cyclone_preposition, heat_shift
from cityfeeds.quakes import fetch_quakes, quakes_view
from cityfeeds.river import LABEL as RIVER_LABEL, fetch_news, river_view
from cityfeeds.tide_table import tide_table_view

__all__ = ["CityFeeds"]


def _as_of(f: Fetched) -> str | None:
    return f.fetched_at.isoformat() if f.fetched_at else None


class CityFeeds:
    def __init__(self, s: Settings, fetcher: Fetcher | None = None, clock=None) -> None:
        self.s = s
        self.f = fetcher or Fetcher(offline=s.offline, timeout=s.http_timeout_sec, cache_scale=s.cache_scale)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._street = StreetImages()
        self._street_error: str | None = None
        self._street_ok = False

    def now(self) -> datetime:
        return self._clock()

    @property
    def box(self) -> tuple[float, float, float, float]:
        s = self.s
        return (s.region_south, s.region_west, s.region_north, s.region_east)

    # ── raw fetches (cached, rate-limited; offline → recorded fixtures) ──
    async def _air(self, force=False) -> Fetched:
        return await self.f.get("air", lambda c: fetch_air(c, self.s.open_meteo_air_url), lambda: load_fixture("air.json"), force)

    async def _heat(self, force=False) -> Fetched:
        return await self.f.get("heat", lambda c: fetch_heat(c, self.s.open_meteo_forecast_url), lambda: load_fixture("heat.json"), force)

    async def _cyc(self, force=False) -> Fetched:
        return await self.f.get("cyclones", lambda c: fetch_cyclones(c, self.s.gdacs_list_url, self.s.gdacs_geometry_url, self.box),
                                lambda: load_fixture("gdacs.json"), force)

    async def _news(self, force=False) -> Fetched:
        return await self.f.get("news", fetch_news, lambda: load_fixture("news.json"), force)

    async def _quakes(self, force=False) -> Fetched:
        return await self.f.get("quakes", lambda c: fetch_quakes(c, self.s.usgs_url, self.s.quake_radius_km),
                                lambda: load_fixture("usgs.json"), force)

    async def _mtp(self, force=False) -> Fetched:
        return await self.f.get("mtp", lambda c: fetch_notices(c, self.s.mtp_url),
                                lambda: load_fixture("mtp_home.html"), force)

    async def _alerts(self, force=False) -> Fetched:
        return await self.f.get("alerts", lambda c: fetch_alerts(c, self.s.sachet_rss_url),
                                lambda: load_fixture("sachet.json"), force)

    async def _fires(self, force=False) -> Fetched:
        mk = key("firms")
        fetch = (lambda c: fetch_fires_area(c, mk)) if mk else fetch_fires_public
        return await self.f.get("fires", fetch, lambda: load_fixture("firms_mumbai.json"), force)

    #: keyed air providers: (feed id, keyed source id, fetch(client, key, now), parse)
    _AIR_OBSERVED = (("air_cpcb", "cpcb", lambda c, k, _now: obs.fetch_cpcb(c, k), obs.parse_cpcb),
                     ("air_waqi", "waqi", lambda c, k, _now: obs.fetch_waqi(c, k), obs.parse_waqi),
                     ("air_openaq", "openaq", obs.fetch_openaq, obs.parse_openaq))
    #: where the observed National AQI comes from, in order: CPCB's bulletin on data.gov.in, else OpenAQ's copy of
    #: the same CAAQMS data (24-hour means of its hourly values)
    _NAQI_FROM = {"cpcb": "CPCB CAAQMS station averages via data.gov.in; National AQI bands on PM2.5/PM10",
                  "openaq": "CPCB CAAQMS station data via OpenAQ: 24-hour means of the hourly PM2.5/PM10 "
                            f"(at least {obs.MIN_HOURS_24H} hours); National AQI bands"}

    async def _observed(self, force=False) -> dict[str, Any]:
        """Each keyed air provider: no key → no call ("needs <ENV>"); offline → no call (no recording exists)."""
        per: dict[str, dict[str, Any]] = {}
        providers: dict[str, Any] = {}
        calls = []
        for feed, src, fetch, parse in self._AIR_OBSERVED:
            k = key(src)
            if k is None or self.s.offline:
                providers[src] = {"state": keyed_state(src) if k is None else "offline: no call",
                                  "env": KEYED[src].env, "signup": KEYED[src].signup}
            else:
                calls.append((src, parse, self.f.get(feed, lambda c, _f=fetch, _k=k: _f(c, _k, self.now()),
                                                     lambda: None, force)))
        got = await asyncio.gather(*(c for _s, _p, c in calls))  # the keyed providers in parallel
        for (src, parse, _c), f in zip(calls, got):
            sites = parse(f.data) if f.ok else {}
            per[src] = sites
            providers[src] = {"state": keyed_state(src, error=f.error if not f.ok else None, live=f.ok),
                              "env": KEYED[src].env, "signup": KEYED[src].signup, "sites_matched": len(sites),
                              "fetched_at": _as_of(f), "stale": f.stale,
                              "error": redact(f.error) if f.error else None}
        return {"providers": dict(sorted(providers.items())), "sites": obs.match_stations(per)}

    def keyed_sources(self) -> dict[str, Any]:
        """Every keyed source and its state: ``live`` / ``needs <ENV>`` / ``error: <reason>`` (never the key)."""
        st = self.f.status()["feeds"]
        out: dict[str, Any] = {}
        for sid, ks in KEYED.items():
            feed = {"cpcb": "air_cpcb", "waqi": "air_waqi", "openaq": "air_openaq", "firms": "fires"}.get(sid)
            if sid == "mapillary":
                state = keyed_state(sid, error=self._street_error, live=self._street_ok)
            elif sid == "firms" and key(sid) is None:  # the public files need no key: say so, never "needs"
                fs = st.get("fires") or {}
                if fs.get("cache_age_sec") is not None:
                    state = "live (public files, no key; FIRMS_MAP_KEY optional)"
                elif fs.get("last_error"):
                    state = f"error: {redact(fs['last_error'])}"
                else:
                    state = "not read yet (public files, no key; FIRMS_MAP_KEY optional)"
            elif feed and key(sid) is not None:
                fs = st.get(feed) or {}
                state = keyed_state(sid, error=fs.get("last_error"), live=fs.get("cache_age_sec") is not None)
            else:
                state = keyed_state(sid)
            out[sid] = {"state": state, "env": ks.env, "what": ks.what, "signup": ks.signup,
                        "without_key": ks.without_key}
        return out

    # ── views ──
    def _labels(self, f: Fetched, *extra: str) -> list[str]:
        base = ["RECORDED"] if f.mode == "RECORDED" else ["LIVE"] if f.ok else ["UNAVAILABLE"]
        return base + list(extra)

    async def air(self, force=False) -> dict[str, Any]:
        f, o = await asyncio.gather(self._air(force), self._observed(force))
        now = self.now()
        v = air_view(f.data, now) if f.ok else {"label": "UNAVAILABLE", "stations": [], "city": None, "next_48h_worst": None}
        v["feed"] = f.meta()
        v["proposal"] = air_advisory(v, now, self._labels(f, "MODELLED", "INDICATIVE")) if f.ok else {"none": "air feed unavailable"}
        # OBSERVED beside MODELLED (additive): per site, each keyed provider's own measurement; none without a key
        for st in v.get("stations") or []:
            st["observed"] = o["sites"].get(st["id"])
        prov = next((p for p in self._NAQI_FROM if any((x.get(p) or {}).get("naqi") for x in o["sites"].values())),
                    None)
        ranked = {sid: x[prov] for sid, x in o["sites"].items() if prov and (x.get(prov) or {}).get("naqi")}
        worst = max(ranked.items(), key=lambda kv: kv[1]["naqi"]["aqi"], default=None)
        names = {st["id"]: (st.get("name") or "", st.get("name_mr") or "") for st in v.get("stations") or []}
        v["observed"] = {
            "label": "OBSERVED" if o["sites"] else "NONE",
            "what": "the stations' own measurements from the keyed services (CPCB via data.gov.in, WAQI, OpenAQ); "
                    "without a key a provider makes no call and the values above stay MODELLED",
            "providers": o["providers"],
            "sites_observed": len(o["sites"]),
            "city_naqi": ({"aqi": worst[1]["naqi"]["aqi"], "band": worst[1]["naqi"]["band"], "site": worst[0],
                           "prominent": worst[1]["naqi"]["prominent"], "at": worst[1]["at"], "label": "OBSERVED",
                           "sub_label": "INDICATIVE", "provider": prov, "source": self._NAQI_FROM[prov],
                           "site_name": names.get(worst[0], ("", ""))[0] or None,
                           "site_mr": names.get(worst[0], ("", ""))[1] or None}
                          if worst else None),
        }
        return v

    async def heat(self, force=False) -> dict[str, Any]:
        f = await self._heat(force)
        now = self.now()
        v = heat_view(f.data, now) if f.ok else {"label": "UNAVAILABLE", "points": [], "city": None}
        v["feed"] = f.meta()
        v["proposal"] = heat_shift(v, now, self._labels(f, "MODELLED")) if f.ok else {"none": "heat feed unavailable"}
        return v

    async def cyclones(self, force=False) -> dict[str, Any]:
        f = await self._cyc(force)
        now = self.now()
        v = cyclones_view(f.data, now) if f.ok else {"type": "FeatureCollection", "features": [], "label": "UNAVAILABLE",
                                                     "active": [], "floods": [], "nearest": None}
        v["feed"] = f.meta()
        v["proposal"] = cyclone_preposition(v, now, self._labels(f, "MODELLED")) if f.ok else {"none": "GDACS unavailable"}
        return v

    async def river(self, force=False) -> dict[str, Any]:
        """The Mithi gauge is EMULATED here (no public live feed; ``river.py``); the news count is LIVE."""
        n = await self._news(force)
        now = self.now()
        v = river_view(None, n.data if n.ok else None, now)
        v["feed"] = {"feed": "river", "mode": RIVER_LABEL, "stale": False, "error": None,
                     "fetched_at": now.isoformat(), "source": "EMULATED Mithi gauge (computed on this box)",
                     "home": "https://dm.mcgm.gov.in/"}
        v["news_feed"] = n.meta()
        return v

    async def quakes(self, force=False) -> dict[str, Any]:
        f = await self._quakes(force)
        v = quakes_view(f.data if f.ok else None, self.s.quake_radius_km, self.now())
        if not f.ok:
            v["label"] = "UNAVAILABLE"
        v["feed"] = f.meta()
        return v

    async def tide_table(self, force=False) -> dict[str, Any]:  # noqa: ARG002 — computed here, nothing to refresh
        now = self.now()
        v = tide_table_view(now)
        v["feed"] = {"feed": "tide", "mode": "MODELLED", "stale": False, "error": None, "fetched_at": now.isoformat(),
                     "source": "Apollo Bunder harmonic tide model (computed on this box)",
                     "home": "https://i-scholar.in/index.php/CURS/article/download/216099/200261"}
        return v

    async def notices(self, force=False) -> dict[str, Any]:
        f = await self._mtp(force)
        v = notices_view(f.data if f.ok else None, f.error)
        v["feed"] = f.meta()
        return v

    async def alerts(self, force=False) -> dict[str, Any]:
        f = await self._alerts(force)
        v = alerts_view(f.data if f.ok else None, self.now())
        v["feed"] = f.meta()
        return v

    async def fires(self, force=False) -> dict[str, Any]:
        f = await self._fires(force)
        v = fires_view(f.data if f.ok else None, self.now())
        v["feed"] = f.meta()
        v["key"] = self.keyed_sources()["firms"]
        return v

    async def street_image(self, lat: float, lon: float) -> dict[str, Any]:
        """The nearest public Mapillary photo to a point, or why there is none. Never calls the vision model."""
        base = {"lat": lat, "lon": lon, "source": "Mapillary (CC BY-SA 4.0)", "label": "Reference photo · not live"}
        tok = key("mapillary")
        if tok is None:
            return {**base, "state": keyed_state("mapillary"), "image": None, "signup": KEYED["mapillary"].signup}
        if self.s.offline:
            return {**base, "state": "offline: no call", "image": None}
        try:
            got = await self._street.near(self.f.client, tok, lat, lon)
        except Exception as exc:  # noqa: BLE001 — reported, never raised to the deck
            self._street_error = redact(f"{type(exc).__name__}: {exc}")[:160]
            return {**base, "state": keyed_state("mapillary", error=self._street_error), "image": None}
        self._street_error, self._street_ok = None, True
        return {**base, "state": "live", "image": got["image"], "cached": got["cached"],
                "searched_m": int(SEARCH_HALF_SIDE_M)}

    async def street_photo(self, lat: float, lon: float) -> tuple[int, dict[str, Any], dict[str, Any] | None]:
        """The bytes of the nearest public Mapillary photo, for the road-state panel (the deck's pages load images from
        their own origin only). ``(200, facts, photo)``, or ``(status, why, None)``: 503 without the token or offline
        (no call), 404 with no photo in the search box, 502 when Mapillary or its CDN gave nothing usable (the rules of
        ``street_image.fetch_photo``). Read into memory, kept only in the short photo cache; never stored, never sent
        to the vision model from here."""
        base = {"lat": lat, "lon": lon, "source": "Mapillary (CC BY-SA 4.0)", "label": "Reference photo · not live"}
        tok = key("mapillary")
        if tok is None:
            return 503, {**base, "state": keyed_state("mapillary"), "detail": keyed_state("mapillary")}, None
        if self.s.offline:
            return 503, {**base, "state": "offline: no call", "detail": "offline: no call"}, None
        none = 404, {**base, "state": "live", "detail": f"no public Mapillary photo within {SEARCH_HALF_SIDE_M:.0f} m",
                "searched_m": int(SEARCH_HALF_SIDE_M)}, None
        try:
            got = await self._street.near(self.f.client, tok, lat, lon)
            if got["image"] is None:
                return none
            try:
                photo = await self._street.photo(self.f.client, got["image"])
            except PhotoRefused as exc:
                # the thumbnail URL is signed and expires: a cached lookup's URL is asked for afresh, once
                if not (got["cached"] and exc.status in (403, 404, 410)):
                    raise
                got = await self._street.near(self.f.client, tok, lat, lon, fresh=True)
                if got["image"] is None:
                    return none
                photo = await self._street.photo(self.f.client, got["image"])
        except Exception as exc:  # noqa: BLE001 — reported, never raised to the deck
            self._street_error = redact(f"{type(exc).__name__}: {exc}")[:160]
            return 502, {**base, "state": keyed_state("mapillary", error=self._street_error),
                         "detail": self._street_error}, None
        self._street_error, self._street_ok = None, True
        return 200, {**base, "state": "live", "image": got["image"], "cached": photo["cached"]}, photo

    async def proposals(self) -> dict[str, Any]:
        a, h, c = await asyncio.gather(self.air(), self.heat(), self.cyclones())
        out, none = [], {}
        for k, v in (("air", a), ("heat", h), ("cyclone", c)):
            p = v.get("proposal") or {}
            if "proposal_id" in p:
                out.append(p)
            else:
                none[k] = p.get("none")
        return {"proposals": out, "not_drafted": none, "generated_at": self.now().isoformat()}

    async def summary(self) -> dict[str, Any]:
        """One object for the god's-eye chips: value, band, label, source and as-of time per chip."""
        a, h, c, r, q, t, al = await asyncio.gather(self.air(), self.heat(), self.cyclones(), self.river(),
                                                    self.quakes(), self.tide_table(), self.alerts())
        chips: dict[str, Any] = {}
        city = a.get("city")
        chips["air"] = {
            "value": city["aqi"] if city else None, "unit": "AQI", "band": city["band"] if city else None,
            "label": "MODELLED" if city else "UNAVAILABLE", "sub_label": "INDICATIVE",
            "source": "Open-Meteo air-quality (CAMS model) · CPCB National AQI bands",
            "as_of": a["feed"]["fetched_at"], "mode": a["feed"]["mode"], "stale": a["feed"]["stale"],
            "detail": {k: city[k] for k in ("worst_site", "worst_site_name", "worst_site_mr", "prominent", "pm25_24h", "pm10_24h",
                                            "band_en", "band_mr", "band_hi")} if city else None,
            "next_48h": (a.get("next_48h_worst") or {}).get("naqi"),
            "proposal": "proposal_id" in (a.get("proposal") or {}),
        }
        hc = h.get("city")
        chips["heat"] = {
            "value": hc["heat_index"] if hc else None, "unit": "°C", "band": hc["band"] if hc else None,
            "label": "MODELLED" if hc else "UNAVAILABLE", "source": "Open-Meteo forecast · NWS heat index · IMD heatwave criteria",
            "as_of": h["feed"]["fetched_at"], "mode": h["feed"]["mode"], "stale": h["feed"]["stale"],
            "detail": {"temp": hc["temp"], "rh": hc["rh"], "apparent": hc["apparent"], "peak_48h": h.get("peak_48h"),
                       "imd_heatwave_days": len(h.get("imd_heatwave_days") or []), "in_season": h.get("in_season")} if hc else None,
            "proposal": "proposal_id" in (h.get("proposal") or {}),
        }
        n = c.get("nearest")
        chips["cyclone"] = {
            "value": n["name"] if n else None, "unit": None, "band": n["alertlevel"] if n else ("none" if c["label"] != "UNAVAILABLE" else None),
            "label": c["label"], "source": "GDACS (EC JRC and UN OCHA)",
            "as_of": c["feed"]["fetched_at"], "mode": c["feed"]["mode"], "stale": c["feed"]["stale"],
            "detail": {"distance_km": n["distance_km"], "bearing": n["bearing"], "closest_km": (n.get("closest_approach") or {}).get("distance_km"),
                       "in_wind_buffer_kmh": n.get("city_in_wind_buffer_kmh"), "severity": n.get("severity"),
                       "active": len(c.get("active") or [])} if n else {"active": 0},
            "proposal": "proposal_id" in (c.get("proposal") or {}),
        }
        key = next((s for s in r["stations"] if s.get("code") == "mithi_kurla"), None)
        chips["river"] = {
            "value": r.get("above_warning"), "unit": "above danger", "band": r.get("status"), "label": r["label"],
            "source": "EMULATED Mithi gauge (no public live feed) · Mumbai news mentions",
            "as_of": r["feed"]["fetched_at"], "mode": r["feed"]["mode"], "stale": r["feed"]["stale"],
            "detail": {"stations_read": r.get("stations_read"), "news_mentions_72h": r["news"].get("mentions"),
                       "dvc_news_mentions_72h": r["news"].get("mentions"),
                       "key_station": {k: key.get(k) for k in ("name", "level_m", "warning_m", "danger_m", "to_danger_m",
                                                               "trend", "label")} if key else None},
        }
        chips["quake"] = {
            "value": q.get("count_30d") if q["label"] != "UNAVAILABLE" else None, "unit": "in 30 days",
            "band": ("recent" if q.get("count_30d") else "quiet") if q["label"] != "UNAVAILABLE" else None,
            "label": q["label"], "source": "USGS earthquake catalogue (500 km)",
            "as_of": q["feed"]["fetched_at"], "mode": q["feed"]["mode"], "stale": q["feed"]["stale"],
            "detail": {"latest": q.get("latest"), "count_365d": q.get("count_365d")},
        }
        nxt = next((e for e in t["modelled"]["highs_lows"] if e["kind"] == "high"), None)
        cmp_ = t["comparison"]
        chips["tide"] = {
            "value": nxt["level_m"] if nxt else None, "unit": "m",
            "band": "high_tide_day" if nxt and nxt["level_m"] >= t["modelled"]["gate_close_level_m"] else "normal",
            "label": "MODELLED" if nxt else "UNAVAILABLE",
            "source": f"Apollo Bunder tide model; within {cmp_.get('max_abs_dt_min')} min and "
                      f"{cmp_.get('max_abs_dh_m')} m of the BMC's published 2025 tides",
            "as_of": t["feed"]["fetched_at"], "mode": t["feed"]["mode"], "stale": t["feed"]["stale"],
            "detail": {"next_high_at": nxt["at"] if nxt else None, "published": t["published"]["label"],
                       "level_now_m": t["modelled"]["now"]["level_m"], "gate_closed_now": t["modelled"]["now"]["gate_closed"],
                       "gate_close_level_m": t["modelled"]["gate_close_level_m"]},
        }
        top = next((x for x in al.get("items") or [] if x.get("for_mumbai") and x.get("active")), None)
        chips["alert"] = {
            "value": al.get("mumbai_active") if al["label"] != "UNAVAILABLE" else None, "unit": "active for Mumbai",
            "band": (top.get("severity") or "alert").lower() if top else ("none" if al["label"] != "UNAVAILABLE" else None),
            "label": al["label"], "source": "NDMA Sachet (CAP): IMD Mumbai, Maharashtra SDMA",
            "as_of": al["feed"]["fetched_at"], "mode": al["feed"]["mode"], "stale": al["feed"]["stale"],
            "detail": {"maharashtra": al.get("maharashtra"),
                       "latest": {k: top.get(k) for k in ("issuer", "headline_en", "text", "severity", "expires")}
                       if top else None},
        }
        # additive: OBSERVED air beside the modelled chip (null until a keyed provider answers)
        chips["air"]["observed"] = (a.get("observed") or {}).get("city_naqi")
        return {"generated_at": self.now().isoformat(), "city": "mumbai", "chips": chips,
                "keyed_sources": {k: v["state"] for k, v in self.keyed_sources().items()}}

    async def warm(self) -> None:
        """Fill every cache once at start-up (never in offline mode), so the first deck poll is fast."""
        if self.s.offline:
            return
        try:
            await self.summary()
            await self.notices()
            await self.fires()
            await self.alerts()
        except Exception:  # noqa: BLE001 — a warm-up failure is just a cold cache
            pass

    async def keep_fresh(self, every_sec: float = 60.0) -> None:
        """Touch every feed once a minute: an expired cache starts its own background refresh (inside its limits),
        so a deck request never waits on an upstream."""
        if self.s.offline:
            return
        while True:
            await self.warm()
            await asyncio.sleep(every_sec)
