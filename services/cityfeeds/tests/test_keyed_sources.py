"""The keyed and added sources, offline, on Mumbai: keyed air (CPCB/data.gov.in, WAQI, OpenAQ), NASA FIRMS,
Mapillary, the Mumbai Traffic Police notices and the NDMA Sachet alerts. No socket is opened: every exchange is an
``httpx.MockTransport``; keys are fake values set in the test's environment only."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from conftest import NOW

from cityfeeds.air import naqi
from cityfeeds.air_observed import parse_openaq
from cityfeeds.config import Settings
from cityfeeds.fetch import Fetcher, load_fixture
from cityfeeds.fires import METRO_BBOX, parse_csv
from cityfeeds.keys import KEYED, redact
from cityfeeds.service import CityFeeds

FX = Path(__file__).resolve().parent / "fixtures"
FAKE = {"DATA_GOV_IN_API_KEY": "fake-dgi-key-0001", "WAQI_TOKEN": "fake-waqi-token-0002",
        "OPENAQ_API_KEY": "fake-openaq-key-0003", "FIRMS_MAP_KEY": "fakefirmskey0004",
        "MAPILLARY_TOKEN": "MLY|fake|token0005"}
KEYED_HOSTS = {"api.data.gov.in", "api.waqi.info", "api.openaq.org", "graph.mapillary.com"}


def _j(name: str):
    return json.loads((FX / name).read_text(encoding="utf-8"))


class Upstream:
    """Answers like each service would; records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.fail: set[str] = set()

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        host, path = req.url.host, req.url.path
        if host in self.fail:
            return httpx.Response(403, json={"status": "error", "data": "Invalid key"})
        if host == "air-quality-api.open-meteo.com":
            return httpx.Response(200, json=load_fixture("air.json"))
        if host == "api.data.gov.in":
            return httpx.Response(200, json=_j("cpcb_mumbai.json"))
        if host == "api.waqi.info":
            return httpx.Response(200, json=_j("waqi_bounds.json"))
        if host == "api.openaq.org":
            if path == "/v3/locations":
                return httpx.Response(200, json=_j("openaq_locations.json"))
            if path == "/v3/locations/5001/latest":
                return httpx.Response(200, json=_j("openaq_latest_5001.json"))
            if path in ("/v3/sensors/9001/hours", "/v3/sensors/9002/hours"):
                return httpx.Response(200, json=_j(f"openaq_hours_{path.split('/')[3]}.json"))
        if host == "firms.modaps.eosdis.nasa.gov":
            modis = "MODIS" in path
            return httpx.Response(200, text=(FX / ("firms_modis.csv" if modis else "firms_area.csv")).read_text())
        if host == "graph.mapillary.com":
            return httpx.Response(200, json=_j("mapillary_images.json"))
        if host == "trafficpolicemumbai.maharashtra.gov.in":
            return httpx.Response(200, text=load_fixture("mtp_home.html"))
        return httpx.Response(404, text="no route in the test double")

    def to(self, host: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host == host]


@pytest.fixture
def upstream() -> Upstream:
    return Upstream()


@pytest.fixture
def live(upstream, monkeypatch):
    for env in FAKE:
        monkeypatch.delenv(env, raising=False)
    cf = CityFeeds(Settings(offline=False), fetcher=Fetcher(transport=httpx.MockTransport(upstream)), clock=lambda: NOW)
    yield cf


def _keys(monkeypatch, *envs: str) -> None:
    for e in envs:
        monkeypatch.setenv(e, FAKE[e])


def _no_key_anywhere(obj) -> None:
    text = json.dumps(obj, ensure_ascii=False, default=str)
    for v in FAKE.values():
        assert v not in text


# ── without keys: no call, and every keyed source says what it needs ─────────────────────────────────────────────


async def test_without_keys_nothing_keyed_is_called_and_each_says_what_it_needs(live, upstream):
    a = await live.air()
    ks = live.keyed_sources()
    assert {k: v["state"] for k, v in ks.items()} == {
        "waqi": "needs WAQI_TOKEN", "openaq": "needs OPENAQ_API_KEY", "cpcb": "needs DATA_GOV_IN_API_KEY",
        "firms": "not read yet (public files, no key; FIRMS_MAP_KEY optional)", "mapillary": "needs MAPILLARY_TOKEN"}
    assert all(v["signup"].startswith("https://") for v in ks.values())
    assert ks["firms"]["without_key"] and "public" in ks["firms"]["without_key"]
    assert a["label"] == "MODELLED" and a["observed"]["label"] == "NONE" and a["observed"]["city_naqi"] is None
    assert {p["state"] for p in a["observed"]["providers"].values()} == {
        "needs DATA_GOV_IN_API_KEY", "needs WAQI_TOKEN", "needs OPENAQ_API_KEY"}
    assert all(s["observed"] is None for s in a["stations"])
    img = await live.street_image(19.0176, 72.848)
    assert img["state"] == "needs MAPILLARY_TOKEN" and img["image"] is None
    assert not KEYED_HOSTS & {r.url.host for r in upstream.requests}
    s = await live.summary()
    assert s["keyed_sources"]["cpcb"] == "needs DATA_GOV_IN_API_KEY" and s["chips"]["air"]["observed"] is None
    assert s["chips"]["air"]["label"] == "MODELLED"  # unchanged contract
    await live.f.aclose()


# ── observed air ──────────────────────────────────────────────────────────────────────────────────────────────────


async def test_cpcb_observed_values_sit_beside_the_modelled_ones(live, upstream, monkeypatch):
    _keys(monkeypatch, "DATA_GOV_IN_API_KEY")
    a = await live.air()
    vm = next(s for s in a["stations"] if s["id"] == "worli")
    o = vm["observed"]["cpcb"]
    assert o["label"] == "OBSERVED" and o["upstream_name"] == "Worli, Mumbai - MPCB"
    assert o["pm25"] == 74 and o["pm10"] == 118 and o["naqi"]["band"] == "moderate" and o["at_tz"] == "IST"
    assert vm["naqi"]["label"] == "INDICATIVE" and a["label"] == "MODELLED"  # the modelled values stay as they are
    gh = next(s for s in a["stations"] if s["id"] == "sion")["observed"]["cpcb"]
    assert gh["pm25"] == 101 and gh["naqi"]["band"] == "poor"  # the pollutant_avg spelling is read too
    city = a["observed"]["city_naqi"]
    assert city["site"] == "sion" and city["label"] == "OBSERVED" and city["sub_label"] == "INDICATIVE"
    assert a["observed"]["providers"]["cpcb"]["state"] == "live"
    sent = upstream.to("api.data.gov.in")
    assert {r.url.params["filters[city]"] for r in sent} == {"Mumbai"}
    s = await live.summary()
    assert s["chips"]["air"]["observed"]["aqi"] == city["aqi"] and s["keyed_sources"]["cpcb"] == "live"
    _no_key_anywhere(s)
    _no_key_anywhere(a)
    await live.f.aclose()


async def test_waqi_and_openaq_are_matched_to_the_sites(live, upstream, monkeypatch):
    _keys(monkeypatch, "WAQI_TOKEN", "OPENAQ_API_KEY")
    a = await live.air()
    by = {s["id"]: s["observed"] for s in a["stations"]}
    assert by["worli"]["waqi"]["waqi_aqi"] == 152 and by["worli"]["waqi"]["scale"].startswith("US EPA")
    assert by["colaba"]["waqi"]["waqi_aqi"] == 88
    assert by["powai"] is None  # WAQI's "-" is no value, never a zero
    assert "CPCB/MPCB station" in by["worli"]["waqi"]["source"]
    fw = by["bkc"]["openaq"]
    assert fw["pm25_latest"] == 63.4 and fw["pm10_latest"] == 101.2
    assert fw["upstream_name"] == "Bandra Kurla Complex, Mumbai - MPCB" and fw["upstream_provider"] == "CPCB"
    oq = upstream.to("api.openaq.org")
    assert oq and all(r.headers["x-api-key"] == FAKE["OPENAQ_API_KEY"] for r in oq)
    assert all(FAKE["OPENAQ_API_KEY"] not in str(r.url) for r in oq)  # a header, never the URL
    _no_key_anywhere(a)
    await live.f.aclose()


async def test_openaq_reads_only_the_sensors_reporting_now(live, upstream, monkeypatch):
    _keys(monkeypatch, "OPENAQ_API_KEY")
    a = await live.air()
    fw = next(s for s in a["stations"] if s["id"] == "bkc")["observed"]["openaq"]
    # the retired sensor's 2022 value (168.4) sits in the same answer as today's 63.4: only today's is read
    assert fw["pm25_latest"] == 63.4 and fw["at"] == "2026-10-30T10:00:00Z"
    paths = [r.url.path for r in upstream.to("api.openaq.org")]
    assert "/v3/locations/5003/latest" not in paths  # a location silent since 2022 costs no call
    assert "/v3/sensors/9004/hours" not in paths and "/v3/sensors/9001/hours" in paths
    since = {r.url.params["datetime_from"] for r in upstream.to("api.openaq.org") if r.url.path.endswith("/hours")}
    assert since == {"2026-10-29T10:30:00Z"}  # the last 24 hours by the service's clock


async def test_openaq_24_hour_means_give_the_national_aqi_without_data_gov_in(live, upstream, monkeypatch):
    _keys(monkeypatch, "OPENAQ_API_KEY", "WAQI_TOKEN")
    a = await live.air()
    fw = next(s for s in a["stations"] if s["id"] == "bkc")["observed"]["openaq"]
    # 20 usable hours for PM2.5 (a zero and a gap do not count); PM10 has 12, under CPCB's 16-hour rule
    assert fw["pm25_24h"] == 65.0 and fw["hours_24h"] == {"pm25": 20, "pm10": 12} and fw["pm10_24h"] is None
    assert fw["naqi"] == naqi(65.0, None) and fw["naqi"]["band"] == "moderate"
    city = a["observed"]["city_naqi"]
    assert city["site"] == "bkc" and city["provider"] == "openaq" and city["aqi"] == fw["naqi"]["aqi"]
    assert city["label"] == "OBSERVED" and city["sub_label"] == "INDICATIVE" and "OpenAQ" in city["source"]
    assert live.keyed_sources()["cpcb"]["without_key"].startswith("OpenAQ carries the same CPCB station data")
    _no_key_anywhere(a)
    await live.f.aclose()


async def test_data_gov_in_stays_first_for_the_national_aqi(live, upstream, monkeypatch):
    _keys(monkeypatch, "OPENAQ_API_KEY", "DATA_GOV_IN_API_KEY")
    a = await live.air()
    city = a["observed"]["city_naqi"]
    assert city["provider"] == "cpcb" and city["site"] == "sion" and "data.gov.in" in city["source"]
    await live.f.aclose()


def test_openaq_gives_no_national_aqi_for_a_station_cpcb_does_not_run():
    raw = {"now": "2026-10-30T10:50:00Z", "locations": [_j("openaq_locations.json")["results"][0] | {"provider": {"name": "StateAir"}}],
           "latest": {"5001": _j("openaq_latest_5001.json")["results"]}, "hours": {"9001": _j("openaq_hours_9001.json")["results"]}}
    fw = parse_openaq(raw)["bkc"]
    assert fw["pm25_24h"] == 65.0 and fw["naqi"] is None and fw["source"] == "OpenAQ v3"


def test_openaq_drops_a_stopped_analyser_and_a_day_old_reading():
    loc = _j("openaq_locations.json")["results"][0]
    latest = [{"datetime": {"utc": "2026-10-30T10:00:00Z"}, "value": 0.0, "sensorsId": 9001},
              {"datetime": {"utc": "2026-10-29T07:00:00Z"}, "value": 99.0, "sensorsId": 9002}]
    assert parse_openaq({"now": "2026-10-30T10:50:00Z", "locations": [loc], "latest": {"5001": latest}}) == {}


async def test_a_refused_key_is_reported_without_the_key(live, upstream, monkeypatch):
    _keys(monkeypatch, "WAQI_TOKEN")
    upstream.fail.add("api.waqi.info")
    a = await live.air()
    st = a["observed"]["providers"]["waqi"]["state"]
    assert st.startswith("error: ") and "403" in st
    assert live.keyed_sources()["waqi"]["state"].startswith("error: ")
    _no_key_anywhere(a)
    _no_key_anywhere(live.f.status())
    await live.f.aclose()


def test_redact_scrubs_keys_and_query_strings(monkeypatch):
    _keys(monkeypatch, "WAQI_TOKEN", "FIRMS_MAP_KEY")
    msg = ("Client error '403' for url 'https://api.waqi.info/v2/map/bounds?latlng=1&token=fake-waqi-token-0002' "
           "and https://firms.modaps.eosdis.nasa.gov/api/area/csv/fakefirmskey0004/VIIRS_SNPP_NRT/1,2,3,4/2")
    out = redact(msg)
    assert "fake-waqi-token-0002" not in out and "fakefirmskey0004" not in out
    assert "<FIRMS_MAP_KEY>" in out and "?…" in out


# ── NASA FIRMS ────────────────────────────────────────────────────────────────────────────────────────────────────


def test_firms_rows_are_kept_to_the_metro_box():
    rows = parse_csv((FX / "firms_area.csv").read_text(), "VIIRS S-NPP")
    assert len(rows) == 2 and all(METRO_BBOX[0] <= r["lat"] <= METRO_BBOX[2] for r in rows)
    assert rows[0]["at"] == "2026-10-28T07:45:00+00:00" and rows[0]["frp_mw"] == 4.6 and rows[1]["daynight"] == "N"


async def test_firms_is_live_without_a_key_from_the_public_files(live, upstream):
    f = await live.fires()
    assert f["label"] == "LIVE" and f["route"].startswith("public") and f["window_h"] == 24
    assert set(f["files"].values()) == {"read"}
    assert f["count"] == 3 * 2 + 1  # three VIIRS files with two in-box rows each, one MODIS row
    for feat in f["features"]:
        p = feat["properties"]
        assert p["kind"] == "hotspot" and "not a confirmed fire" in p["note"] and feat["geometry"]["type"] == "Point"
        assert not {"name", "person", "owner"} & set(p)
    paths = [r.url.path for r in upstream.to("firms.modaps.eosdis.nasa.gov")]
    assert all(p.startswith("/data/active_fire/") and p.endswith("_South_Asia_24h.csv") for p in paths)
    assert f["key"]["state"] == "live (public files, no key; FIRMS_MAP_KEY optional)"
    await live.f.aclose()


async def test_firms_uses_the_area_api_with_a_key_and_never_shows_it(live, upstream, monkeypatch):
    _keys(monkeypatch, "FIRMS_MAP_KEY")
    f = await live.fires()
    paths = [r.url.path for r in upstream.to("firms.modaps.eosdis.nasa.gov")]
    assert paths and all(p.startswith(f"/api/area/csv/{FAKE['FIRMS_MAP_KEY']}/") and p.endswith("/2") for p in paths)
    assert f["route"].startswith("FIRMS area API") and f["window_h"] == 48 and f["key"]["state"] == "live"
    _no_key_anywhere(f)
    await live.f.aclose()


# ── Mapillary ─────────────────────────────────────────────────────────────────────────────────────────────────────


async def test_mapillary_returns_the_nearest_still_with_its_licence(live, upstream, monkeypatch):
    _keys(monkeypatch, "MAPILLARY_TOKEN")
    r = await live.street_image(19.0176, 72.848)
    im = r["image"]
    assert r["state"] == "live" and im["id"] == "333" and im["distance_m"] < 15  # the panorama is skipped
    assert im["label"] == "Reference photo · not live" and "CC BY-SA 4.0" in im["attribution"]
    assert im["page_url"] == "https://www.mapillary.com/app/?pKey=333" and im["captured_at"].startswith("2024-07-03")
    sent = upstream.to("graph.mapillary.com")
    assert len(sent) == 1 and sent[0].headers["authorization"] == f"OAuth {FAKE['MAPILLARY_TOKEN']}"
    assert "access_token" not in str(sent[0].url) and "creator" not in sent[0].url.params["fields"]
    again = await live.street_image(19.0176, 72.848)
    assert again["cached"] is True and len(upstream.to("graph.mapillary.com")) == 1
    assert live.keyed_sources()["mapillary"]["state"] == "live"
    _no_key_anywhere(r)
    await live.f.aclose()


# ── the Mumbai Traffic Police notices and the Sachet alerts ─────────────────────────────────────────────────────


async def test_mtp_page_is_read_live_and_lists_no_menu_item(live, upstream):
    n = await live.notices()
    assert n["label"] == "LIVE" and n["feed"]["mode"] == "LIVE" and n["items"] == []
    assert len(upstream.to("trafficpolicemumbai.maharashtra.gov.in")) == 2  # the home page and its notices page
    await live.f.aclose()


async def test_sachet_alerts_read_the_rss_and_a_few_cap_files(monkeypatch):
    rss = ('<rss><channel>'
           '<item><title>पुढील ३ तासांत मुंबई, मुंबई उपनगरमध्ये मुसळधार पावसाची शक्यता. मंत्रालय मुंबई.</title>'
           '<category>Met</category><link>https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1</link>'
           '<author>controlroom@ndma.gov.in (IMD Mumbai)</author><guid>1</guid><pubDate>Fri, 30 Oct 2026 09:00:00 GMT</pubDate></item>'
           '<item><title>Lightning likely in 6 Mandals</title><category>Met</category>'
           '<link>https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=2</link>'
           '<author>controlroom@ndma.gov.in (Andhra Pradesh SDMA)</author><guid>2</guid><pubDate>Fri, 30 Oct 2026 09:00:00 GMT</pubDate></item>'
           '</channel></rss>')
    cap = ('<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2"><cap:info><cap:language>en-IN</cap:language>'
           '<cap:event>Heavy Rain</cap:event><cap:severity>Severe</cap:severity><cap:urgency>Immediate</cap:urgency>'
           '<cap:certainty>Likely</cap:certainty><cap:effective>2026-10-30T14:30:00+05:30</cap:effective>'
           '<cap:expires>2026-10-30T17:30:00+05:30</cap:expires><cap:headline>Heavy rain likely over Mumbai and Mumbai Suburban'
           '</cap:headline><cap:area><cap:areaDesc>Mumbai,Mumbai Suburban districts of Maharashtra</cap:areaDesc></cap:area>'
           '</cap:info></cap:alert>')
    seen = []

    def sachet(req: httpx.Request) -> httpx.Response:
        seen.append(req.url)
        if req.url.path.endswith("rss_india.xml"):
            return httpx.Response(200, text=rss)
        return httpx.Response(200, text=cap)

    cf = CityFeeds(Settings(offline=False), fetcher=Fetcher(transport=httpx.MockTransport(sachet)), clock=lambda: NOW)
    a = await cf.alerts()
    assert a["label"] == "LIVE" and a["items_in_feed"] == 2 and a["maharashtra"] == 1 and a["mumbai_active"] == 1
    it = a["items"][0]
    assert it["issuer"] == "IMD Mumbai" and it["severity"] == "Severe" and it["for_mumbai"] and it["active"]
    assert it["headline_en"].startswith("Heavy rain likely over Mumbai")
    assert len(seen) == 2  # the RSS and one CAP file: the Andhra Pradesh alert is never fetched
    s = await cf.summary()
    assert s["chips"]["alert"]["value"] == 1 and s["chips"]["alert"]["band"] == "severe"
    await cf.f.aclose()


def test_every_keyed_source_names_its_env_var_and_signup():
    assert {k.env for k in KEYED.values()} == set(FAKE)
    for k in KEYED.values():
        assert k.signup.startswith("https://") and k.what
