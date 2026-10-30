from datetime import UTC, date, datetime, timedelta

import numpy as np

from forecast.calendar import ganeshotsav_day, marathon_day, mount_mary_fair, visarjan_day
from forecast.synthetic import LABEL, SyntheticCity, align

END = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def _ist(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=UTC) - timedelta(minutes=330)


def test_deterministic_regardless_of_window(net):
    sid = sorted(net.segments)[len(net.segments) // 2]
    sim = SyntheticCity(net, seed=7)
    a = sim.history(sid, END - timedelta(days=3), END)
    b = sim.history(sid, END - timedelta(days=1), END)
    assert np.allclose(a.vc[-96:], b.vc[-96:])
    assert a.label == LABEL == "SIMULATED"
    assert "Mumbai" in a.source
    c = SyntheticCity(net, seed=8).history(sid, END - timedelta(days=1), END)
    assert not np.allclose(c.vc, b.vc)


def test_shapes_bounds_and_covariates(net):
    sim = SyntheticCity(net)
    sids = sorted(net.segments)[:3]
    hs = sim.histories(sids, END - timedelta(days=2), END)
    for h in hs.values():
        assert h.n == 2 * 96 + 1
        assert np.all((h.vc >= 0.03) & (h.vc <= 1.8))
        assert np.all(h.speed > 0) and np.all(h.speed <= h.free_flow_kmh + 1e-9)
        assert set(h.covariates()) == {"rain_mm_h", "gate_closed", "event"}
        assert set(np.unique(h.gate_closed)) <= {0.0, 1.0}
        assert h.time_at(h.n - 1) == align(END)


def test_office_peak_above_night(net):
    sim = SyntheticCity(net)
    start, end = datetime(2026, 10, 26, 18, 30, tzinfo=UTC), datetime(2026, 10, 27, 18, 15, tzinfo=UTC)
    gaps = []
    for sid in sorted(net.segments):
        h = sim.history(sid, start, end)
        ist_hour = [(h.time_at(i) + timedelta(minutes=330)).hour for i in range(h.n)]
        night = np.mean([v for v, hr in zip(h.vc, ist_hour) if 2 <= hr < 5])
        peak = np.mean([v for v, hr in zip(h.vc, ist_hour) if 17 <= hr < 20])
        gaps.append(peak - night)
    assert np.mean(gaps) > 0.3


def test_mumbai_calendar():
    # Ganesh Chaturthi 14 Sep 2026 (Maharashtra GAD notification) … Anant Chaturdashi 25 Sep 2026
    assert ganeshotsav_day(date(2026, 9, 13)) == 0
    assert ganeshotsav_day(date(2026, 9, 14)) == 1
    assert ganeshotsav_day(date(2026, 9, 15)) == 2  # 1½-day immersion
    assert ganeshotsav_day(date(2026, 9, 16)) == 1
    assert ganeshotsav_day(date(2026, 9, 25)) == 3 and visarjan_day(date(2026, 9, 25)) == 2
    assert ganeshotsav_day(date(2026, 9, 26)) == 0
    assert ganeshotsav_day(date(2025, 9, 6)) == 3  # Anant Chaturdashi 2025
    assert marathon_day(date(2026, 1, 18)) and marathon_day(date(2027, 1, 17))
    assert not marathon_day(date(2026, 1, 25))
    assert mount_mary_fair(date(2026, 9, 13)) and mount_mary_fair(date(2026, 9, 20))
    assert not mount_mary_fair(date(2026, 9, 12)) and not mount_mary_fair(date(2026, 9, 21))


def test_ganeshotsav_nights_load_pandal_roads(mini_net):
    sim = SyntheticCity(mini_net)
    # Dr Ambedkar Road by Lalbaugcha Raja: 22:00 IST on a festival Wednesday vs two weeks later
    t_fest, t_norm = _ist(2026, 9, 16, 22), _ist(2026, 9, 30, 22)
    hf = sim.history(9001, t_fest - timedelta(hours=2), t_fest)
    hn = sim.history(9001, t_norm - timedelta(hours=2), t_norm)
    assert hf.vc[-8:].mean() > hn.vc[-8:].mean() + 0.1
    assert hf.event[-1] == 1.0 and hn.event[-1] == 0.0


def test_anant_chaturdashi_loads_the_procession_and_spares_the_suburbs(mini_net):
    sim = SyntheticCity(mini_net)
    # the Lalbaug → Girgaon Chowpatty road at 21:00 IST on Anant Chaturdashi vs two Fridays later
    t_imm, t_norm = _ist(2026, 9, 25, 21), _ist(2026, 10, 9, 21)
    hi = sim.history(9003, t_imm - timedelta(hours=2), t_imm)
    hn = sim.history(9003, t_norm - timedelta(hours=2), t_norm)
    assert hi.vc[-8:].mean() > hn.vc[-8:].mean() + 0.15
    assert hi.event[-1] == 1.0 and hn.event[-1] == 0.0
    # still loaded at 03:00 the next morning (the processions run through the night)
    t_late = _ist(2026, 9, 26, 3)
    assert sim.history(9003, t_late - timedelta(hours=1), t_late).event[-1] == 1.0
    # a road in Powai is untouched by the festival
    assert sim.history(9005, t_imm - timedelta(hours=2), t_imm).event.sum() == 0.0


def test_marathon_morning_marks_the_route(mini_net):
    sim = SyntheticCity(mini_net)
    t = _ist(2026, 1, 18, 7)
    h = sim.history(9004, t - timedelta(hours=1), t)  # Churchgate–Wankhede, by Marine Drive
    assert h.event[-1] == 1.0
    assert sim.history(9004, t - timedelta(days=7, hours=1), t - timedelta(days=7)).event[-1] == 0.0


def test_rain_raises_vc_and_high_tide_makes_flood_spots_worse(mini_net):
    sim = SyntheticCity(mini_net)
    start, end = END - timedelta(hours=6), END
    n = 25
    dry = sim.history(9002, start, end, rain=np.zeros(n), gates=np.zeros(n))
    wet_open = sim.history(9002, start, end, rain=np.full(n, 40.0), gates=np.zeros(n))
    wet_shut = sim.history(9002, start, end, rain=np.full(n, 40.0), gates=np.ones(n))
    assert np.all(wet_open.vc >= dry.vc - 1e-9)
    assert wet_open.vc.mean() > dry.vc.mean() + 0.05
    # Hindmata–Dadar TT is a chronic flooding spot: shut outfalls (high tide) cut capacity further
    assert sim._seg_params[9002]["low_lying"] >= 0.55
    assert wet_shut.vc[-8:].mean() > wet_open.vc[-8:].mean() + 0.02


def test_monsoon_months_are_wet_and_the_dry_season_is_dry(mini_net):
    sim = SyntheticCity(mini_net)
    july = sim.city_rain(datetime(2026, 7, 1, tzinfo=UTC), 30 * 96).sum()
    feb = sim.city_rain(datetime(2026, 2, 1, tzinfo=UTC), 28 * 96).sum()
    assert july > 10 * max(feb, 1.0)


def test_on_the_mumbai_network_lalbaug_loads_on_festival_nights_and_hindmata_floods(net):
    sim = SyntheticCity(net)
    # Dr Ambedkar Road at Lalbaug (1064, Lalbaug → Parel): 22:00 IST on a festival Wednesday vs two weeks later
    t_fest, t_norm = _ist(2026, 9, 16, 22), _ist(2026, 9, 30, 22)
    hf = sim.history(1064, t_fest - timedelta(hours=2), t_fest)
    hn = sim.history(1064, t_norm - timedelta(hours=2), t_norm)
    assert hf.vc[-8:].mean() > hn.vc[-8:].mean() + 0.1 and hf.event[-1] == 1.0
    # Hindmata – Dadar TT (1066) is a chronic flooding spot; the Western Express Highway at Borivali is not
    assert sim._seg_params[1066]["low_lying"] >= 0.55
    far = [sid for sid, s in net.segments.items() if s.midpoint[0] > 19.2]
    assert far and all(sim._seg_params[sid]["low_lying"] <= 0.6 for sid in far)
