from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from hydro.tide import GATE_CLOSE_LEVEL_M, GR_GATE_CLOSE_LEVEL_M, LABEL, OUTFALL_IMPEDED_FROM_M, TideModel

IST = ZoneInfo("Asia/Kolkata")


def _ex(model, start, hours):
    return [(e.kind, e.at.astimezone(IST), e.level_m) for e in model.extremes(start, hours)]


def _minutes(a, b):
    return abs((a - b).total_seconds()) / 60


def test_garden_reach_matches_published_predictions_28_oct_2026():
    """tide-forecast.com, Garden Reach 28 Oct 2026 (IST): HW 02:26 5.79 m, LW 09:56 1.98 m, HW 14:42 5.39 m,
    LW 22:04 2.01 m. The model is approximate: within 30 min and 0.3 m."""
    m = TideModel("garden_reach", freshet=False)
    got = _ex(m, datetime(2026, 10, 28, 0, 0, tzinfo=IST), 24)
    want = [("high", (2, 26), 5.79), ("low", (9, 56), 1.98), ("high", (14, 42), 5.39), ("low", (22, 4), 2.01)]
    assert [g[0] for g in got] == [w[0] for w in want]
    for (k, t, lv), (wk, (hh, mm), wl) in zip(got, want):
        assert _minutes(t, datetime(2026, 10, 28, hh, mm, tzinfo=IST)) <= 30, (k, t)
        assert abs(lv - wl) <= 0.3


def test_diamond_harbour_cited_constants_phase_convention():
    """The cited Diamond Harbour constants read as Greenwich phases put high water within an hour of the
    published prediction (12:04 IST on 28 Oct 2026) — the check on the phase-convention inference."""
    m = TideModel("diamond_harbour", freshet=False)
    highs = [t for k, t, _ in _ex(m, datetime(2026, 10, 28, 6, 0, tzinfo=IST), 12) if k == "high"]
    assert highs and _minutes(highs[0], datetime(2026, 10, 28, 12, 4, tzinfo=IST)) <= 60


def test_flood_shorter_than_ebb():
    m = TideModel("garden_reach", freshet=False)
    ex = m.extremes(datetime(2026, 10, 28, 0, 0, tzinfo=IST), 26)
    floods = [(b.at - a.at).total_seconds() / 3600 for a, b in zip(ex, ex[1:]) if a.kind == "low"]
    ebbs = [(b.at - a.at).total_seconds() / 3600 for a, b in zip(ex, ex[1:]) if a.kind == "high"]
    assert all(4.5 <= f <= 5.8 for f in floods) and all(6.4 <= e <= 7.6 for e in ebbs)


def test_gate_closure_on_23_sep_2025_covers_the_reported_closure():
    """Reported: lock gate closed 00:30–04:00 IST; high tide around 13:30 IST (Mayor, 23 Sep 2025)."""
    m = TideModel("garden_reach")
    t = datetime(2025, 9, 22, 20, 0, tzinfo=IST)
    closed = [t + timedelta(minutes=15 * i) for i in range(80) if m.gate_closed(t + timedelta(minutes=15 * i))]
    night = [c for c in closed if c.hour < 8]
    assert night[0] <= datetime(2025, 9, 23, 0, 45, tzinfo=IST)
    assert night[-1] >= datetime(2025, 9, 23, 3, 45, tzinfo=IST)
    highs = [e.at.astimezone(IST) for e in m.extremes(datetime(2025, 9, 23, 9, 0, tzinfo=IST), 8) if e.kind == "high"]
    assert highs and _minutes(highs[0], datetime(2025, 9, 23, 13, 30, tzinfo=IST)) <= 60


def test_freshet_raises_monsoon_levels_and_labels():
    t = datetime(2025, 9, 23, 2, 0, tzinfo=IST)
    assert TideModel("garden_reach").level(t) > TideModel("garden_reach", freshet=False).level(t) + 0.5
    assert LABEL == "MODELLED (approximate)" and GR_GATE_CLOSE_LEVEL_M == 5.0
    assert TideModel("garden_reach").gate_level == 5.0
    s = TideModel().series(t, 2, 15)
    assert len(s) == 9


# ── Apollo Bunder (Mumbai), the default station ─────────────────────────────

#: the BMC's high-tide advisories as printed by the Free Press Journal (IST, metres above chart datum)
BMC_HIGHS_2025 = [
    ((2025, 6, 24, 11, 15), 4.59), ((2025, 6, 25, 12, 5), 4.71), ((2025, 6, 26, 12, 55), 4.75),
    ((2025, 6, 27, 13, 40), 4.73), ((2025, 6, 28, 14, 26), 4.64),
    ((2025, 7, 24, 11, 58), 4.57), ((2025, 7, 25, 12, 40), 4.66), ((2025, 7, 26, 13, 20), 4.67),
    ((2025, 7, 27, 13, 56), 4.60),
]


def _nearest(model, kind, when):
    ex = [e for e in model.extremes(when - timedelta(hours=6), 12) if e.kind == kind]
    return min(ex, key=lambda e: abs((e.at - when).total_seconds()))


def test_default_station_is_apollo_bunder():
    m = TideModel()
    assert m.station == "apollo_bunder" and "Apollo Bunder" in m.station_name
    assert m.gate_level == GATE_CLOSE_LEVEL_M == 4.5 and OUTFALL_IMPEDED_FROM_M == 3.4
    assert not m.freshet  # the Hooghly freshet never applies to the open sea


def test_apollo_bunder_matches_bmc_high_tide_advisories_2025():
    """Every BMC-listed high water of 24–28 June and 24–27 July 2025: within 20 min and 0.12 m."""
    m = TideModel()
    for (y, mo, d, hh, mm), lv in BMC_HIGHS_2025:
        want = datetime(y, mo, d, hh, mm, tzinfo=IST)
        got = _nearest(m, "high", want)
        assert _minutes(got.at, want) <= 20, (want, got)
        assert abs(got.level_m - lv) <= 0.12, (want, got)


def test_apollo_bunder_full_day_24_july_2025():
    """The printed 24 July 2025 table: LW 05:07 0.43 m, HW 11:58 4.57 m, LW 18:13 1.62 m, HW 23:40 3.72 m —
    the diurnal inequality comes out right (lows within 10 min and 0.25 m)."""
    m = TideModel()
    got = _ex(m, datetime(2025, 7, 24, 0, 0, tzinfo=IST), 24)
    want = [("low", (5, 7), 0.43), ("high", (11, 58), 4.57), ("low", (18, 13), 1.62), ("high", (23, 40), 3.72)]
    assert [g[0] for g in got] == [w[0] for w in want]
    for (k, t, lv), (_wk, (hh, mm), wl) in zip(got, want):
        assert _minutes(t, datetime(2025, 7, 24, hh, mm, tzinfo=IST)) <= 10, (k, t)
        assert abs(lv - wl) <= 0.25, (k, lv, wl)


def test_spring_tides_reach_the_bmc_high_tide_band():
    """Spring high waters around 4.5–5 m are expected at Mumbai; a quiet neap day stays well under 4.5 m."""
    m = TideModel()
    spring = max(e.level_m for e in m.extremes(datetime(2025, 6, 24, 0, 0, tzinfo=IST), 5 * 24) if e.kind == "high")
    assert 4.5 <= spring <= 5.1
    neap = max(e.level_m for e in m.extremes(datetime(2025, 8, 17, 0, 0, tzinfo=IST), 24) if e.kind == "high")
    assert neap < 4.2


def test_outfall_restriction_grades_between_impeded_and_gate_levels():
    m = TideModel()
    t0 = datetime(2025, 7, 24, 0, 0, tzinfo=IST)
    for i in range(0, 24 * 4):
        t = t0 + timedelta(minutes=15 * i)
        z, r = m.level(t), m.outfall_restriction(t)
        assert 0.0 <= r <= 1.0
        if z >= 4.5:
            assert r == 1.0 and m.gate_closed(t)
        elif z <= 3.4:
            assert r == 0.0 and not m.gate_closed(t)
        else:
            assert 0.0 < r < 1.0 and not m.gate_closed(t)
    # the Hooghly gate stays a step
    g = TideModel("garden_reach")
    assert all(g.outfall_restriction(t0 + timedelta(minutes=15 * i)) in (0.0, 1.0) for i in range(96))


def test_apollo_bunder_on_the_27_may_2025_bmc_tides():
    """BMC via PTI (Editorji, 27 May 2025): 4.88 m at 12:13 and 4.18 m at 23:56. An independent pre-monsoon
    check (the mean level was fitted on June–July): times within 10 min; the model reads ~0.2 m low in May."""
    m = TideModel()
    for (hh, mm), lv in (((12, 13), 4.88), ((23, 56), 4.18)):
        want = datetime(2025, 5, 27, hh, mm, tzinfo=IST)
        got = _nearest(m, "high", want)
        assert _minutes(got.at, want) <= 10 and abs(got.level_m - lv) <= 0.25, (want, got)
