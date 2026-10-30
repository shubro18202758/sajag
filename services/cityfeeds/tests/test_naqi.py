"""CPCB National AQI: the breakpoint table (CUPS/82/2014-15, Table 6) and the band rules."""

import pytest

from cityfeeds.air import band_of, naqi, sub_index


@pytest.mark.parametrize(("c", "aqi"), [(0, 0), (30, 50), (31, 51), (60, 100), (61, 101), (90, 200), (91, 201),
                                        (120, 300), (121, 301), (250, 400), (251, 401), (380, 500), (900, 500)])
def test_pm25_breakpoints(c, aqi):
    assert sub_index("pm25", c) == aqi


@pytest.mark.parametrize(("c", "aqi"), [(50, 50), (100, 100), (250, 200), (350, 300), (430, 400), (510, 500)])
def test_pm10_breakpoints(c, aqi):
    assert sub_index("pm10", c) == aqi


def test_values_between_the_integer_bounds_interpolate_upward():
    assert 50 <= sub_index("pm25", 30.5) <= 51
    assert sub_index("pm25", None) is None


def test_bands_and_prominent_pollutant():
    assert band_of(50)["id"] == "good" and band_of(51)["id"] == "satisfactory" and band_of(201)["id"] == "poor"
    assert band_of(450)["id"] == "severe"
    r = naqi(95.0, 120.0)  # PM2.5 sub-index 220 beats PM10's 113
    assert r["prominent"] == "PM2.5" and r["band"] == "poor" and r["label"] == "INDICATIVE"
    r = naqi(20.0, 300.0)
    assert r["prominent"] == "PM10" and r["band"] == "poor"
    assert naqi(None, None) is None


def test_every_band_names_three_languages():
    from cityfeeds.air import NAQI_BANDS
    for b in NAQI_BANDS:
        assert b["en"] and b["mr"] and b["hi"]
