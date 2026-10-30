"""Heat index (NWS Rothfusz) and IMD's coastal-station heatwave test at Santacruz."""

import pytest

from cityfeeds.heat import HEAT_SEASON, POINTS, SANTACRUZ_NORMAL_MAX, heat_index_c, hi_band, imd_heatwave


def test_heat_index_matches_the_nws_table():
    # NWS heat-index chart: 90 °F at 70 % RH reads 105–106 °F (40.6–41.1 °C)
    assert 40.4 <= heat_index_c(32.22, 70) <= 41.2
    # cool and dry: the simple formula, close to the air temperature
    assert abs(heat_index_c(20.0, 40) - 19.4) < 1.0
    assert heat_index_c(None, 50) is None


def test_bands():
    assert hi_band(26.0) == "normal" and hi_band(30.0) == "caution" and hi_band(35.0) == "extreme_caution"
    assert hi_band(45.0) == "danger" and hi_band(60.0) == "extreme_danger"


def test_points_are_the_two_imd_observatories_and_seasons():
    assert [p["id"] for p in POINTS] == ["santacruz", "colaba"]
    assert all(18.85 < p["lat"] < 19.15 and 72.8 < p["lon"] < 72.9 for p in POINTS)
    assert HEAT_SEASON == (3, 4, 5, 10, 11)  # pre-monsoon and "October heat"


@pytest.mark.parametrize(("tmax", "month", "level"), [
    (36.9, 10, "none"),         # below 37 °C: never a coastal heatwave on departure alone
    (39.4, 10, "heatwave"),     # October normal 34.9 → departure 4.5
    (39.3, 10, "none"),         # departure 4.4
    (41.5, 10, "severe"),       # departure 6.6 > 6.4
    (37.0, 8, "severe"),        # August normal 29.0 → departure 8.0 > 6.4
    (45.0, 6, "heatwave"),      # ≥ 45 °C whatever the normal
    (47.0, 4, "severe"),        # ≥ 47 °C
])
def test_imd_coastal_criteria(tmax, month, level):
    r = imd_heatwave(tmax, month)
    assert r["level"] == level and r["label"] == "MODELLED"
    assert r["normal_max"] == SANTACRUZ_NORMAL_MAX[month]
