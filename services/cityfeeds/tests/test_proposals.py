"""Proposals are drafts for a named officer: the shape, the three languages (Marathi, English, Hindi) and the
triggers, on Mumbai's roads and posts from the city pack."""

from datetime import UTC, datetime

from cityfeeds.proposals import ARTERIALS, air_advisory, cyclone_preposition, heat_shift

AT = datetime(2026, 11, 8, 14, 30, tzinfo=UTC)
DEVANAGARI = range(0x0900, 0x0980)
BENGALI = range(0x0980, 0x0A00)


def _gate_ok(p):
    assert p["state"] == "proposed" and p["recommendation"]["decision"] == "await_officer"
    assert p["human_gate"] == {"state": "proposed", "required_role": "duty_officer", "officer": None, "decided_at": None}
    assert all(a["requires_officer"] and a["reversible"] for a in p["actions"])


def _marathi(text):
    assert any(ord(c) in DEVANAGARI for c in text) and not any(ord(c) in BENGALI for c in text)


def _air(band, aqi):
    names = {"poor": ("Poor", "वाईट", "खराब"), "very_poor": ("Very poor", "अतिशय वाईट", "बहुत खराब")}[band]
    city = {"aqi": aqi, "band": band, "band_en": names[0], "band_mr": names[1], "band_hi": names[2]}
    return {"city": city, "next_48h_worst": None, "naqi_source": {"url": "https://cpcb.nic.in/National-Air-Quality-Index/"}}


def test_air_advisory_three_languages_and_duty_note():
    p = air_advisory(_air("very_poor", 342), datetime(2026, 11, 20, 9, 0, tzinfo=UTC), ["LIVE", "MODELLED", "INDICATIVE"])
    _gate_ok(p)
    _marathi(p["text"]["mr"])
    assert "(मसुदा)" in p["text"]["mr"] and "मुंबई" in p["text"]["mr"] and "रुग्णवाहिका (108)" in p["text"]["mr"]
    assert p["text"]["hi"].endswith("।") and "मुंबई" in p["text"]["hi"]
    assert "Mumbai's air" in p["text"]["en"] and "342" in p["text"]["en"] and "ambulance (108)" in p["text"]["en"]
    assert any(a["target_urn"] == "agency:mtp" for a in p["actions"])
    assert p["subject_urn"] == "place:mumbai"


def test_heat_shift_on_an_imd_heatwave_day():
    heat = {"peak_48h": {"heat_index": 39.0, "at_ist": "2027-05-02T14:00"}, "in_season": True,
            "imd_heatwave_days": [{"point": "santacruz", "date": "2027-05-02",
                                   "imd": {"tmax": 39.1, "departure": 4.8, "level": "heatwave"}}]}
    p = heat_shift(heat, AT, ["LIVE", "MODELLED"])
    _gate_ok(p)
    roster = p["actions"][0]
    assert roster["verb"] == "duty_roster" and roster["params"]["turn_max_min"] == 120 and len(roster["params"]["posts"]) == 8
    assert {x["name"] for x in roster["params"]["posts"]} >= {"Dadar TT Circle", "Haji Ali junction"}
    assert roster["target_urn"] == "agency:mtp"
    _marathi(p["text"]["mr"])


def test_heat_outside_the_seasons_needs_danger():
    heat = {"peak_48h": {"heat_index": 36.0, "at_ist": "2027-08-02T14:00"}, "in_season": False, "imd_heatwave_days": []}
    assert "outside Mumbai's heat seasons" in heat_shift(heat, AT, [])["none"]


def test_cyclone_preposition_only_when_close():
    far = {"nearest": {"name": "X", "alertlevel": "red", "distance_km": 972, "bearing": "SW", "eventid": 1,
                       "closest_approach": {"distance_km": 700}, "city_in_wind_buffer_kmh": None}}
    none = cyclone_preposition(far, AT, [])
    assert "none" in none and "Mumbai" in none["none"]
    near = {"nearest": {**far["nearest"], "distance_km": 240, "closest_approach": {"distance_km": 40},
                        "city_in_wind_buffer_kmh": 90}}
    p = cyclone_preposition(near, AT, ["LIVE", "MODELLED"])
    _gate_ok(p)
    assert len(p["actions"]) == len(ARTERIALS) == 10 and p["situation"]["in_wind_buffer_kmh"] == 90
    assert all(a["verb"] == "preposition" and a["target_urn"].startswith("segment:") for a in p["actions"])
    assert "Mumbai inside the 90 km/h wind buffer" in p["summary"]
    assert "BMC" in p["actions"][0]["params"]["team"]


def test_news_signal_counts_mentions_only():
    from cityfeeds.river import count_mentions
    news = {"feeds": {"abp": {"publisher": "marathi.abplive.com", "items": [
        {"title": "हिंदमाता परिसरात पाणी साचले", "description": "", "link": "https://x/1", "pubDate": "Fri, 30 Oct 2026 10:00:00 +0530"},
        {"title": "Mithi river crosses danger mark at Kurla", "description": "", "link": "https://x/2", "pubDate": "Fri, 30 Oct 2026 09:00:00 +0530"},
        {"title": "Unrelated city news", "description": "", "link": "https://x/3", "pubDate": "Fri, 30 Oct 2026 08:00:00 +0530"},
        {"title": "Andheri subway closed after waterlogging", "description": "", "link": "https://x/4", "pubDate": "Mon, 19 Oct 2026 08:00:00 +0530"},
    ]}}, "errors": {"ht": "403"}}
    r = count_mentions(news, datetime(2026, 10, 30, 12, 0, tzinfo=UTC))
    assert r["label"] == "AGGREGATE" and r["mentions"] == 2 and r["items_scanned"] == 3
    assert r["by_outlet"] == {"marathi.abplive.com": 2} and r["outlets_down"] == ["ht"]
    assert all(set(x) == {"publisher", "link", "at"} for x in r["links"])  # no headline, no person


def test_diwali_night_drafts_from_moderate_and_names_the_smoke():
    from cityfeeds.proposals import festival_near
    air = {"city": {"aqi": 75, "band": "satisfactory", "band_en": "Satisfactory", "band_mr": "समाधानकारक", "band_hi": "संतोषजनक"},
           "next_48h_worst": {"naqi": {"aqi": 160, "band": "moderate", "band_en": "Moderate", "band_mr": "मध्यम", "band_hi": "मध्यम"}},
           "naqi_source": {}}
    ordinary = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
    assert festival_near(ordinary) is None and "none" in air_advisory(air, ordinary, [])
    night = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)  # 17:30 IST, Diwali
    assert festival_near(night)["date"] == "2026-11-08"
    p = air_advisory(air, night, ["LIVE", "MODELLED", "INDICATIVE"])
    _gate_ok(p)
    assert "firecracker smoke" in p["text"]["en"] and "फटाक्यांच्या धुरामुळे" in p["text"]["mr"] and "पटाखों" in p["text"]["hi"]
    assert "दिवाळी" in p["text"]["mr"] and p["basis"]["festival"]["en"] == "Diwali"
    _marathi(p["text"]["mr"])
