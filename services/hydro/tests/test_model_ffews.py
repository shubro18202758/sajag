from datetime import UTC, datetime

import numpy as np

from hydro.ffews import LABEL, MAJOR_PUMPS_TOTAL, STATIONS, EmulatedFfews, station_for
from hydro.model import CLASS_BANDS, C_MIN, classify, simulate


def test_classify_edges():
    assert classify(np.array([0.0, 1.99, 2.0, 9.9, 10.0, 29.9, 30.0, 80.0])).tolist() == [0, 0, 1, 1, 2, 2, 3, 3]
    assert CLASS_BANDS[2] == "10–30 cm"


def test_capacities_are_the_bmc_design_figures():
    from hydro.model import C_MAX, CAPACITY_SOURCES
    assert C_MIN == 25.0 * 0.5 and C_MAX == 50.0 * 1.0  # legacy 25 mm/h at run-off 0.5; BRIMSTOWAD 50 at 1
    assert all(s["url"].startswith("https://") for s in CAPACITY_SOURCES)


def test_graded_outfall_restriction_sits_between_open_and_shut():
    r = np.full(8, 40.0)
    open_, half, shut = (simulate(r, np.full(8, g), 1.0, 0.5).depth_cm[-1] for g in (0.0, 0.5, 1.0))
    assert open_ < half < shut


def test_dry_and_light_rain_stay_dry():
    assert simulate(np.zeros(8), np.zeros(8), 1.0, 0.8).classes.max() == 0
    # rain below the drainage floor never ponds
    assert simulate(np.full(16, C_MIN * 0.9), np.zeros(16), 1.0, 1.0).depth_cm.max() == 0


def test_more_rain_tide_and_pump_loss_make_it_worse():
    r = np.full(8, 40.0)
    base = simulate(r, np.zeros(8), 1.0, 0.5).depth_cm[-1]
    assert simulate(r * 1.5, np.zeros(8), 1.0, 0.5).depth_cm[-1] > base
    assert simulate(r, np.ones(8), 1.0, 0.5).depth_cm[-1] > base          # gates shut at high tide
    assert simulate(r, np.zeros(8), 0.0, 0.5).depth_cm[-1] > base         # pumps down
    assert simulate(r, np.zeros(8), 1.0, 0.9).depth_cm[-1] > base         # more susceptible


def test_elevated_never_ponds_and_water_recedes():
    assert simulate(np.full(8, 90.0), np.ones(8), 0.0, 1.0, elevated=True).depth_cm.max() == 0
    run = simulate(np.r_[np.full(8, 60.0), np.zeros(16)], np.zeros(24), 1.0, 0.5)
    assert run.depth_cm[-1] < run.depth_cm[7]


def test_emulated_ffews_is_labelled_and_deterministic():
    f = EmulatedFfews()
    t = datetime(2026, 10, 28, 12, tzinfo=UTC)
    a, b = f.states(t, 10.0), f.states(t, 10.0)
    assert [x.as_dict() for x in a] == [x.as_dict() for x in b]
    for s in a:
        d = s.as_dict()
        assert d["label"] == LABEL == "EMULATED" and d["location"] in ("landmark", "approximate")
        assert 0 <= s.pumps_running <= s.pumps_available <= s.pumps_total
        assert s.pumps_running == s.pumps_available  # in rain every available pump runs
        assert d["source"].startswith("http")
    assert len(STATIONS) >= 10


def test_bmc_stations_match_the_published_figures():
    major = [s for s in STATIONS if s.kind == "major"]
    assert {s.id for s in major} == {"haji_ali_ps", "love_grove_ps", "cleveland_bunder_ps", "britannia_ps",
                                     "irla_ps", "gazdarbandh_ps"}
    # the invented per-station counts add up to the BMC's published 43 pumps
    assert sum(s.pumps for s in major) == MAJOR_PUMPS_TOTAL == 43
    assert {s.id for s in STATIONS if s.kind == "mini"} >= {"hindmata_mps", "gandhi_market_mps", "yellow_gate_mps",
                                                           "chunabhatti_mps"}
    assert all(s.capacity_cusec is None for s in STATIONS)  # no per-station capacity is published


def test_station_catchment():
    st, d = station_for(19.0056, 72.8400)  # Hindmata
    assert st is not None and st.id == "hindmata_mps" and d < 300
    st, d = station_for(19.229, 72.857)    # Borivali: no station within the catchment radius
    assert st is None
