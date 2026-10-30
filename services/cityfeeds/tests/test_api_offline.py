"""Every route, offline on the Mumbai fixtures recorded 30 Oct 2026 (no network)."""

import re
from datetime import UTC, datetime

CHIPS = {"air", "heat", "cyclone", "river", "quake", "tide", "alert"}
LABELS = {"LIVE", "MODELLED", "EMULATED", "UNAVAILABLE"}


def test_health(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["offline"] is True and h["city"] == "mumbai"
    assert set(h["fetcher"]["feeds"]) >= {"air", "cyclones", "alerts", "mtp"}
    assert "EMULATED" in h["labels"]["river"] and "MODELLED" in h["labels"]["tide_table"]


def test_summary_chips_are_complete_and_labelled(client):
    s = client.get("/feeds/summary").json()
    assert s["city"] == "mumbai" and set(s["chips"]) == CHIPS
    for k, c in s["chips"].items():
        assert c["label"] in LABELS, k
        assert c["source"] and c["mode"] in ("RECORDED", "EMULATED", "MODELLED"), k
        assert {"value", "band", "as_of"} <= set(c)
    air = s["chips"]["air"]
    assert air["unit"] == "AQI" and air["band"] == "satisfactory" and air["sub_label"] == "INDICATIVE"
    assert air["detail"]["worst_site"] == "sewri" and air["detail"]["worst_site_mr"] == "शिवडी"
    assert s["chips"]["cyclone"]["value"] is None and s["chips"]["cyclone"]["band"] == "none"
    river = s["chips"]["river"]
    assert river["label"] == "EMULATED" and river["mode"] == "EMULATED" and river["value"] == 0
    assert river["detail"]["key_station"]["danger_m"] == 4.0 and river["detail"]["key_station"]["label"] == "EMULATED"
    tide = s["chips"]["tide"]
    assert tide["label"] == "MODELLED" and tide["detail"]["published"] == "PUBLISHED" and 3.0 < tide["value"] < 5.2
    assert tide["detail"]["gate_close_level_m"] == 4.5
    assert s["chips"]["alert"]["label"] == "LIVE" and s["chips"]["alert"]["detail"]["maharashtra"] == 4


def test_air_sites_and_bands(client):
    a = client.get("/feeds/air").json()
    assert len(a["stations"]) == 12 and a["label"] == "MODELLED" and a["feed_label"] == "LIVE"
    assert {s["id"] for s in a["stations"]} >= {"colaba", "worli", "bkc", "kurla", "chakala_andheri", "borivali"}
    for s in a["stations"]:
        assert "OpenAQ" in s["coord_source"] and s["naqi"]["label"] == "INDICATIVE" and len(s["forecast"]) == 2
        assert 18.85 < s["lat"] < 19.3 and 72.75 < s["lon"] < 73.0
    assert a["grid_cells"] >= 1
    assert "not an official CPCB AQI" in a["naqi_label"] and a["naqi_source"]["url"].startswith("https://cpcb.nic.in")
    assert "none" in a["proposal"]  # Satisfactory on the recorded day: no draft, and it says why


def test_heat(client):
    h = client.get("/feeds/heat").json()
    assert [p["id"] for p in h["points"]] == ["santacruz", "colaba"]
    assert h["in_season"] is True and "October" in h["season"] and h["sources"]["imd"]["url"].endswith(".pdf")
    # October heat: a 48-h peak heat index of 37.2 °C (extreme caution) in season drafts the duty-shift proposal
    assert h["peak_48h"]["heat_index"] == 37.2 and h["proposal"]["kind"] == "heat_duty_shift_advisory"
    assert h["proposal"]["human_gate"]["officer"] is None


def test_cyclones_geojson(client):
    c = client.get("/feeds/cyclones").json()
    assert c["type"] == "FeatureCollection" and c["label"] == "LIVE"
    assert c["nearest"] is None and c["features"] == []  # nothing active over the Arabian Sea on the recorded day
    assert "Arabian Sea" in c["proposal"]["none"]


def test_river_is_emulated_and_says_so(client):
    r = client.get("/feeds/river").json()
    assert r["label"] == "EMULATED" and len(r["stations"]) == 1
    k = r["stations"][0]
    assert k["code"] == "mithi_kurla" and k["danger_m"] == 4.0 and k["status"] == "normal" and k["label"] == "EMULATED"
    assert "Not a measurement" in k["note"] and 0.5 < k["level_m"] < 3.0
    assert r["news"]["label"] == "AGGREGATE" and r["news"]["items_scanned"] == 100 and r["news"]["mentions"] == 0
    assert r["dvc_news"] == r["news"]  # the deck's old key, same value
    assert "IFLOWS" in r["what"]


def test_quakes(client):
    q = client.get("/feeds/quakes").json()
    assert q["count_30d"] == 1 and q["count_365d"] == 5
    assert all(f["properties"]["distance_km"] <= 500 for f in q["features"])


def test_tide_table_is_modelled_and_checked_against_the_bmc(client):
    t = client.get("/feeds/tide-table").json()
    assert t["published"]["label"] == "PUBLISHED" and len(t["published"]["highs_lows"]) == 12
    assert all("BMC" in r["source"] and r["url"].startswith("https://www.freepressjournal.in/") for r in
               t["published"]["highs_lows"])
    assert t["modelled"]["label"] == "MODELLED" and "Apollo Bunder" in t["modelled"]["station"]
    assert t["modelled"]["highs_lows"] and t["modelled"]["gate_close_level_m"] == 4.5
    c = t["comparison"]
    assert len(c["pairs"]) == 12 and c["max_abs_dt_min"] <= 20 and c["max_abs_dh_m"] <= 0.25
    assert t["published"]["bmc_2026"]["peak"] == {"date": "2026-07-16", "level_m": 4.89}


def test_alerts_are_maharashtra_and_mumbai_scoped(client):
    from cityfeeds.alerts import alerts_view
    from cityfeeds.fetch import load_fixture
    a = client.get("/feeds/alerts").json()
    assert a["label"] == "LIVE" and a["items_in_feed"] == 100 and a["maharashtra"] == 4
    assert all(i["issuer"] == "IMD Mumbai" and i["cap_url"].startswith("https://sachet.ndma.gov.in/") for i in a["items"])
    mum = [i for i in a["items"] if i["for_mumbai"]]
    assert len(mum) == 1 and "Mumbai Suburban" in mum[0]["area"]
    # the "Mantralaya Mumbai" signature on a Thane alert does not make it a Mumbai alert
    assert not next(i for i in a["items"] if i.get("area", "").startswith("Thane"))["for_mumbai"]
    # at 12:00 IST the Mumbai nowcast (valid to 12:30 IST) was active
    noon = alerts_view(load_fixture("sachet.json"), datetime(2026, 10, 30, 6, 30, tzinfo=UTC))
    assert noon["mumbai_active"] == 1


def test_fires_route_offline(client):
    f = client.get("/feeds/fires").json()
    assert f["type"] == "FeatureCollection" and f["feed"]["mode"] == "RECORDED"
    assert f["route"].startswith("public") and f["count"] == len(f["features"]) == 1
    assert "not a confirmed fire" in f["what"] and "Mumbai" in f["what"]


def test_street_image_route_says_what_it_needs(client, monkeypatch):
    monkeypatch.delenv("MAPILLARY_TOKEN", raising=False)
    r = client.get("/feeds/street-image", params={"lat": 19.0176, "lon": 72.848}).json()
    assert r["state"] == "needs MAPILLARY_TOKEN" and r["image"] is None
    assert client.get("/feeds/street-image", params={"lat": 22.56, "lon": 88.35}).status_code == 422  # Mumbai only


def test_health_lists_every_keyed_source(client, monkeypatch):
    for env in ("WAQI_TOKEN", "OPENAQ_API_KEY", "DATA_GOV_IN_API_KEY", "FIRMS_MAP_KEY", "MAPILLARY_TOKEN"):
        monkeypatch.delenv(env, raising=False)
    ks = client.get("/health").json()["keyed_sources"]
    assert set(ks) == {"waqi", "openaq", "cpcb", "firms", "mapillary"}
    assert all(v["state"] == f"needs {v['env']}" for k, v in ks.items() if k != "firms")
    assert "no key" in ks["firms"]["state"]  # FIRMS runs on its public files without a key


def test_notices_are_about_places_never_people(client):
    n = client.get("/feeds/notices").json()
    assert n["label"] == "LIVE"
    bad = re.compile(r"recruit|award|भरती|पुरस्कार|सन्मान", re.I)
    for it in n["items"]:
        assert not bad.search(it["title"]) and it["publisher"] == "Mumbai Traffic Police"
    # the recorded pages list no current traffic notice (only menus, recruitment and awards): the view says so
    assert n["items"] == [] and "lists none" in n["sources"][0]["status"]


def test_mtp_filter_keeps_traffic_notices_only():
    from cityfeeds.notices import mtp_advisories
    page = ('<a href="/wp-content/uploads/2026/09/visarjan.pdf">अनंत चतुर्दशी: वाहतूक मार्गात बदल व पर्यायी मार्ग</a>'
            '<a href="/wp-content/uploads/2026/09/bharti.pdf">पोलीस भरती 2026 अधिसूचना</a>'
            '<a href="/notice/x/">Traffic diversion at Gokhale Bridge, Andheri</a>'
            '<a href="/सूचना/">सूचना</a>')
    items = mtp_advisories(page)
    assert len(items) == 2 and items[0]["title"].startswith("अनंत चतुर्दशी") and items[1]["title"].startswith("Traffic")
    assert all(i["link"].startswith("https://trafficpolicemumbai.maharashtra.gov.in/") for i in items)


def test_proposals_route_explains_what_it_did_not_draft(client):
    p = client.get("/feeds/proposals").json()
    assert [x["kind"] for x in p["proposals"]] == ["heat_duty_shift_advisory"]
    assert set(p["not_drafted"]) == {"air", "cyclone"}
