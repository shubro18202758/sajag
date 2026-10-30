"""Living City tests: the deterministic day program and the supervisor.

Program (pure): the same IST date and city seed give the identical program;
two to three causes overlap at every minute of the day on disjoint roads;
about forty slots; 108 requests never more than 30 minutes apart; Mumbai's
rhythm shapes what happens — office peaks into BBD Bag–Esplanade and Sector
V, the IT night-shift change, the school week, monsoon waterlogging that is
worse at high tide, pre-monsoon storms, Ganeshotsav nights at the mandals
and the year's end on Marine Drive — at Mumbai places named in English and
Marathi.

Supervisor (fake seams, driven tick by tick): slots open as corridor
events through C-F with living-city provenance; two Mumbai Traffic Police beats
publish C-A docs; the ANPR trickle crosses stop lines only on green at a
compliant speed; deliberate violators are planned causes and an UNPLANNED
rule hit retires its camera; 108 requests land as 'requested' dispatches
and a request still waiting for an officer when its slot closes is
re-filed on an open slot; a manual run pre-empts overlapping slots; stop /
day rollover close everything through C-F; a seed-network mismatch fails
loudly.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import pytest

from event_emulator.ambient import (
    _FLEET,
    _NS,
    IST,
    PATROLS,
    SITES,
    SLOT_KINDS,
    LivingCity,
    build_day_program,
    patrols_for,
    _plate,
    day_seed_for,
    trickle_read,
)
from event_emulator.nats_seam import UNITS_EMULATED_SUBJECT
from event_emulator.runner import RunnerDeps
from event_emulator.tape import movement_states_at
from event_emulator.city import (
    EARMARK_EXERCISE_PLATE,
    PLACES,
    PUJA_NIGHTS,
    STOLEN_FIR_PLATE,
    unit_label,
    unit_role,
)
from fakes import FakeNats, FakeOracle, FakeStore, FakeTwin, FakeValkey, NoSleep
from mumbai import KEYS, SEGMENTS, between, legal_path, segment_named

SEED = 400001
DAY = date(2026, 10, 22)

#: A stop-line camera at Hindmata on the Dr Ambedkar Road approach from
#: Parel, and a mid-block camera on the Sea Link (northbound) (the Mumbai
#: network's ids, tests/data/mumbai_network_slim.json).
PARK_ST = KEYS["hindmata"]
JLN_SOUTH = between("hindmata", "parel")
JLN_NORTH = between("dadar_tt", "hindmata")
PARK_STREET = between("hindmata", "kem")
BRABOURNE = segment_named("Bandra-Worli Sea Link (northbound)")
PROGRAM = {"cycle_sec": 100, "offset_sec": 0,
           "phases": [{"green_sec": 47, "movements": ["through"]},
                      {"green_sec": 38, "movements": ["cross"]}]}
CAMERAS = [
    {"camera_id": "EM-CAM-01", "lon": 72.8197, "lat": 19.0412, "junction_id": None,
     "heading_deg": None, "segment_id": BRABOURNE, "speed_limit_kmh": 40.0, "oneway": True,
     "bearing_deg": 345.0, "signal_junction_id": None},
    {"camera_id": "EM-J19", "lon": 72.8396, "lat": 19.00545, "junction_id": PARK_ST,
     "heading_deg": 14.7, "segment_id": JLN_SOUTH, "speed_limit_kmh": 40.0, "oneway": False,
     "bearing_deg": 194.7, "signal_junction_id": PARK_ST},
]
LEGS = {PARK_ST: [
    {"segment_id": JLN_NORTH, "road_class": "trunk", "bearing_deg": 33.5},
    {"segment_id": JLN_SOUTH, "road_class": "trunk", "bearing_deg": 194.7},
    {"segment_id": PARK_STREET, "road_class": "secondary", "bearing_deg": 136.0},
]}
STOP = "EM-J19"
SITE_BY_ID = {site.site_id: site for site in SITES}
#: A Ganeshotsav night of 2025 (city.PUJA_NIGHTS), the eve of Anant Chaturdashi.
PUJA_ASHTAMI = date(2025, 9, 5)


# ── the day program (pure) ──────────────────────────────────────────────────


class TestDayProgram:
    def test_same_date_and_seed_identical(self):
        assert build_day_program(SEED, DAY).to_json() == build_day_program(SEED, DAY).to_json()

    def test_date_and_seed_both_matter(self):
        base = build_day_program(SEED, DAY).to_json()
        assert build_day_program(SEED, DAY + timedelta(days=1)).to_json() != base
        assert build_day_program(SEED + 1, DAY).to_json() != base
        assert day_seed_for(SEED, DAY) != day_seed_for(SEED, DAY + timedelta(days=1))

    @pytest.mark.parametrize("offset", range(0, 365, 23))
    def test_two_to_three_causes_on_disjoint_roads(self, offset):
        d = date(2026, 1, 1) + timedelta(days=offset)
        p = build_day_program(SEED, d)
        assert 30 <= len(p.slots) <= 56
        t = p.day_start
        while t < p.day_start + timedelta(days=1):
            active = p.active_at(t)
            assert 2 <= len(active) <= 3, (d, t)
            segs = [s for slot in active for s in slot.route_segment_ids]
            assert len(segs) == len(set(segs)), (d, t)
            t += timedelta(minutes=5)

    def test_ambulance_requests_every_25_minutes(self):
        p = build_day_program(SEED, DAY)
        gaps = [(b.at - a.at).total_seconds() / 60.0
                for a, b in zip(p.ambulance_requests, p.ambulance_requests[1:])]
        assert max(gaps) < 30.0 and 20.0 < sum(gaps) / len(gaps) < 26.0
        for a in p.ambulance_requests:
            target = next(s for s in p.slots if s.slot_id == a.slot_id)
            assert target.active_at(a.at)
            assert a.unit_id.startswith("108-EM") and a.waypoint_junction is not None

    def test_density_one_is_the_baseline_program(self):
        assert build_day_program(SEED, DAY, density=1).to_json() == \
            build_day_program(SEED, DAY).to_json()

    @pytest.mark.parametrize("offset", range(0, 365, 41))
    def test_a_denser_day_keeps_the_baseline_lanes_and_adds_causes(self, offset):
        d = date(2026, 1, 1) + timedelta(days=offset)
        base = build_day_program(SEED, d)
        for level, lanes, most in ((2, 5, 5), (3, 7, 7)):
            p = build_day_program(SEED, d, density=level)
            assert p.to_json() == build_day_program(SEED, d, density=level).to_json()
            # the baseline three lanes are drawn first, identically
            assert [s for s in p.slots if s.lane < 3] == list(base.slots)
            assert {s.lane for s in p.slots} <= set(range(lanes))
            assert len(p.slots) > len(base.slots)
            t, counts = p.day_start, []
            while t < p.day_start + timedelta(days=1):
                active = p.active_at(t)
                assert 2 <= len(active) <= most, (d, level, t)
                segs = [s for slot in active for s in slot.route_segment_ids]
                assert len(segs) == len(set(segs)), (d, level, t)  # still disjoint roads
                counts.append(len(active))
                t += timedelta(minutes=5)
            assert sum(counts) / len(counts) > 3.0
            for a in p.ambulance_requests:
                target = next(s for s in p.slots if s.slot_id == a.slot_id)
                assert target.active_at(a.at)

    def test_density_cadences(self):
        def mean_gap(rows):
            gaps = [(b.at - a.at).total_seconds() / 60.0 for a, b in zip(rows, rows[1:])]
            return sum(gaps) / len(gaps)

        p2 = build_day_program(SEED, DAY, density=2)
        p3 = build_day_program(SEED, DAY, density=3)
        assert 13.0 < mean_gap(p2.ambulance_requests) < 16.0
        assert 9.0 < mean_gap(p3.ambulance_requests) < 12.0
        assert 9.0 < mean_gap(p2.violations) < 13.0
        assert 7.0 < mean_gap(p3.violations) < 11.0
        with pytest.raises(ValueError):
            build_day_program(SEED, DAY, density=4)

    def test_every_beat_is_a_legal_chain_of_two_way_roads_beyond_the_first_two(self):
        assert len(PATROLS) == 18 and len({p[0] for p in PATROLS}) == 18
        assert patrols_for(1) == PATROLS[:2] and patrols_for(2) == patrols_for(3) == PATROLS
        for unit_id, beat, route in PATROLS:
            assert legal_path(list(route)), unit_id
            for a, b in zip(route, route[1:]):          # consecutive roads meet
                ends_a = {SEGMENTS[a]["from_junction"], SEGMENTS[a]["to_junction"]}
                ends_b = {SEGMENTS[b]["from_junction"], SEGMENTS[b]["to_junction"]}
                assert ends_a & ends_b, (unit_id, a, b)
            assert unit_role(unit_id).agency in ("traffic", "police", "ambulance")
            assert len(unit_label(unit_id, beat)) <= 80, unit_id
        for unit_id, _beat, route in PATROLS[2:]:     # driven back and forth
            assert not any(SEGMENTS[s]["oneway"] for s in route), unit_id

    def test_violators_are_rare(self):
        p = build_day_program(SEED, DAY)
        assert 70 <= len(p.violations) <= 100      # ~1 per 15-19 min
        assert {v.kind for v in p.violations} == {"speed", "red_light"}

    def test_slot_shape(self):
        p = build_day_program(SEED, DAY)
        kinds = Counter(s.kind for s in p.slots)
        assert set(kinds) <= set(SLOT_KINDS)
        for s in p.slots:
            assert s.slot_id.startswith("20261022-L")
            assert s.ends_at > s.starts_at
            assert s.event_kind in ("mass_gathering", "work_zone", "egress_surge")

    def test_every_slot_is_a_mumbai_place_named_in_marathi(self):
        marathi = re.compile(r"[\u0900-\u097F]")
        for d in (DAY, PUJA_ASHTAMI, date(2026, 7, 14), date(2026, 12, 31)):
            for s in build_day_program(SEED, d).slots:
                assert marathi.search(s.title_mr), s.title
                site = SITE_BY_ID[s.site_id]
                assert site.name in s.title and site.name_mr in s.title_mr
                assert s.place is None or s.place in PLACES
                for sid in s.route_segment_ids:
                    assert sid in SEGMENTS, (s.site_id, sid)

    def test_sites_sit_on_their_roads(self):
        for site in SITES:
            for j in site.junctions:
                assert any(j in (SEGMENTS[sid]["from_junction"], SEGMENTS[sid]["to_junction"])
                           for sid in site.segments), site.site_id
            if site.kind == "festival_crowd":
                assert site.festival in ("puja", "year_end") and site.place in PLACES

    def test_patrol_beats_are_legal_chains(self):
        for _unit, _beat, route in PATROLS:
            assert legal_path(list(route)), route

    def test_office_peaks_on_working_days(self):
        # into and out of BBD Bag–Esplanade and Sector V, about 09:30–11:30
        # and 17:30–20:00, Monday to Saturday (Saturday lighter), never Sunday
        seen = 0
        for k in range(28):
            d = date(2026, 11, 2) + timedelta(days=k)
            for s in build_day_program(SEED, d).slots:
                if s.kind != "office_rush":
                    continue
                seen += 1
                h = s.starts_at.astimezone(IST)
                hour = h.hour + h.minute / 60.0
                assert d.weekday() < 6, d
                assert 9.5 <= hour < 11.5 or 17.5 <= hour < 20.0, (d, h)
                assert s.title.startswith("Office rush")
        assert seen >= 28

    def test_it_shift_changes_include_the_night_shift(self):
        starts = []
        for k in range(28):
            d = date(2026, 11, 2) + timedelta(days=k)
            starts += [s.starts_at.astimezone(IST) for s in build_day_program(SEED, d).slots
                       if s.kind == "it_shift_change"]
        hours = [t.hour + t.minute / 60.0 for t in starts]
        assert all(8.5 <= h < 10 or 18 <= h < 19.5 or 21 <= h < 23.5 or 5.5 <= h < 7
                   for h in hours)
        assert any(21 <= h < 23.5 for h in hours)          # the night-shift change

    def test_monsoon_waterlogging_worse_at_high_tide(self):
        rains = []
        for k in range(0, 120, 3):                          # June to September
            d = date(2026, 6, 1) + timedelta(days=k)
            rains += [s for s in build_day_program(SEED, d).slots if s.kind == "waterlogging"]
        assert len(rains) > 40
        for s in rains:
            assert s.weather["code"] == "RAIN" and s.weather["tide_source"] == "MODELLED"
        tides = [s.weather["tide_index"] for s in rains]
        # likelier while the river is high …
        assert sum(tides) / len(tides) > 0.55
        # … and it drains slower then (the outfalls are shut)
        high = [s for s in rains if s.weather["tide_index"] >= 0.7]
        low = [s for s in rains if s.weather["tide_index"] <= 0.3]
        dur = lambda xs: sum((x.ends_at - x.starts_at).total_seconds() for x in xs) / len(xs)  # noqa: E731
        assert high and low and dur(high) > dur(low)
        assert any(s.title.startswith("Heavy rain at high tide") for s in rains)

    def test_dry_season_and_pre_monsoon_storms(self):
        for k in range(0, 30, 2):                           # April: dry
            p = build_day_program(SEED, date(2026, 4, 1) + timedelta(days=k))
            assert all(s.weather is None or s.weather.get("code") != "STORM" for s in p.slots
                       if s.kind == "waterlogging")
        for k in range(0, 31, 2):                           # May evenings
            for s in build_day_program(SEED, date(2026, 5, 1) + timedelta(days=k)).slots:
                if s.kind == "waterlogging":
                    assert s.weather["code"] == "STORM"
                    assert s.title.startswith("Pre-monsoon thunderstorm")
                    assert 15 <= s.starts_at.astimezone(IST).hour < 21

    def test_school_week(self):
        sunday = build_day_program(SEED, date(2026, 10, 25))
        assert not any(s.kind == "school_egress" for s in sunday.slots)
        for s in build_day_program(SEED, DAY).slots:
            if s.kind == "school_egress":
                h = s.starts_at.astimezone(IST)
                assert 7 <= h.hour < 18

    def test_puja_nights_bring_crowds_to_the_pandals(self):
        p = build_day_program(SEED, PUJA_ASHTAMI)
        crowds = [s for s in p.slots if s.kind == "festival_crowd"]
        assert len(crowds) >= 3
        for s in crowds:
            h = s.starts_at.astimezone(IST).hour
            assert h >= 18 or h < 4, s.starts_at
            assert SITE_BY_ID[s.site_id].festival == "puja"
            assert s.title.startswith("Ganeshotsav night crowd") and s.crowd_class == "EXTREME"
            assert s.title_mr.startswith("गणेशोत्सवाच्या रात्रीची गर्दी")
        # the mandals and the visarjan route both draw crowds over the three nights
        places = {s.place for n in PUJA_NIGHTS[2025]
                  for s in build_day_program(SEED, n).slots if s.kind == "festival_crowd"}
        assert places & {"lalbaugcha_raja", "parel", "gsb_kings_circle"}
        assert places & {"girgaon_chowpatty", "lalbaug", "jj_hospital"}
        # schools close on the visarjan day; not a festival crowd on an
        # ordinary night
        visarjan = build_day_program(SEED, PUJA_NIGHTS[2025][-1])
        assert not any(s.kind == "school_egress" for s in visarjan.slots)
        assert not any(s.kind == "festival_crowd" for s in build_day_program(SEED, DAY).slots)

    def test_the_puja_calendar_can_be_overridden(self):
        ordinary = date(2026, 11, 11)
        assert not any(s.kind == "festival_crowd"
                       for s in build_day_program(SEED, ordinary).slots)
        p = build_day_program(SEED, ordinary, (ordinary,))
        assert any(s.kind == "festival_crowd" for s in p.slots)

    def test_new_years_eve_on_marine_drive(self):
        p = build_day_program(SEED, date(2026, 12, 31))
        crowds = [s for s in p.slots if s.kind == "festival_crowd"]
        assert crowds
        assert all(SITE_BY_ID[s.site_id].festival == "year_end" for s in crowds)
        assert all(s.place in ("marine_drive", "girgaon_chowpatty", "churchgate") for s in crowds)

    def test_day_seed_is_exact_in_a_browser(self):
        # JSON numbers above 2**53 lose digits in JavaScript (the deck)
        for offset in range(0, 400, 7):
            assert 0 <= day_seed_for(SEED, DAY + timedelta(days=offset)) < 2**53

    def test_trickle_is_pure_and_em_marked(self):
        seed = day_seed_for(SEED, DAY)
        reads = [trickle_read(SEED, seed, t) for t in range(500)]
        assert reads == [trickle_read(SEED, seed, t) for t in range(500)]
        assert all(r.plate[4:6] == "EM" for r in reads)
        assert {STOLEN_FIR_PLATE, EARMARK_EXERCISE_PLATE}.isdisjoint({r.plate for r in reads})
        assert all(r.plate.startswith("MH") for r in reads)
        assert len({r.plate for r in reads}) > 100


# ── the supervisor ──────────────────────────────────────────────────────────


def _city(store=None, reserved=None, rules=None, density=1):
    store = store or FakeStore(cameras=[dict(c) for c in CAMERAS], programs={PARK_ST: PROGRAM},
                               legs=LEGS)
    oracle = FakeOracle(store=store, rules=rules)
    nats = FakeNats()
    deps = RunnerDeps(store=store, valkey=FakeValkey(), twin=FakeTwin(), nats=nats,
                      oracle=oracle, sleep=NoSleep())
    city = LivingCity(deps, city_seed=SEED, reserved_routes=reserved or (lambda: {}),
                      density=density)
    return city, store, oracle, nats


def _at(hh: int, mm: int = 0, ss: int = 0, d: date = DAY) -> datetime:
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=IST).astimezone(timezone.utc)


def _trickle_ids(city: LivingCity, start: datetime, ticks: int) -> set[str]:
    """The read ids of the background trickle over a tick range (the
    supervisor keys them by IST date + tick index + session run)."""
    import uuid

    day_start = city.program_for(DAY).day_start
    first = int((start - day_start).total_seconds() // 5)
    return {str(uuid.uuid5(_NS, f"read|{DAY}|tick:{first + k}|run:{city.run_id}"))
            for k in range(ticks + 1)}


async def _run(city, start: datetime, ticks: int, step: float = 5.0) -> datetime:
    await city._open_session(start)
    t = start
    for _ in range(ticks):
        await city.tick(t)
        t += timedelta(seconds=step)
    return t


class TestSupervisor:
    async def test_slots_open_as_living_city_events(self):
        city, store, oracle, nats = _city()
        await _run(city, _at(18, 30), 1)
        sess = city._session
        assert sess is not None and sess.run_id is not None
        assert store.runs[sess.run_id]["spec"]["mode"] == "living_city"
        active = city.status_doc()["active_slots"]
        assert 2 <= len(active) <= 3
        for slot in active:
            ev = store.events[slot["event_id"]]
            meta = ev["metadata"]
            assert meta["source"] == "event-emulator" and meta["mode"] == "living_city"
            assert meta["slot"] == slot["slot_id"] and meta["run_id"] == sess.run_id
            assert ev["status"] == "active" and ev["protection_class"] == "none"
            assert ev["movement_id"] is None
        assert all(t[3] == "event-emulator (system)" for t in oracle.transitions)
        assert not store.movements                     # slots write no movements

    async def test_patrols_publish_c_a_docs(self):
        city, store, oracle, nats = _city()
        await _run(city, _at(9, 0), 3)
        docs = [d for s, d, _r in nats.json_docs if s == UNITS_EMULATED_SUBJECT]
        assert len(docs) == 6
        # the baseline city: its first two Mumbai Traffic Police beats
        assert city.patrols == PATROLS[:2]
        assert {d["unit_id"] for d in docs} == {"MTP-EM-LC1", "MTP-EM-LC2"}
        for d in docs:
            assert d["agency"] == "traffic" and d["source"] == "emulated"
            assert d["label"].startswith("Mumbai Traffic Police MTP-EM-LC")
            assert d["status"] == "patrol" and d["run_id"] == city.run_id
        # they move
        first = [d["position"] for d in docs if d["unit_id"] == "MTP-EM-LC1"]
        assert first[0] != first[-1]

    async def test_a_denser_city_rides_every_unit_labelled_by_agency(self):
        city, store, oracle, nats = _city(density=2)
        await _run(city, _at(9, 0), 3)
        docs = [d for s, d, _r in nats.json_docs if s == UNITS_EMULATED_SUBJECT]
        assert {d["unit_id"] for d in docs} == {p[0] for p in PATROLS}
        assert len(docs) == 3 * len(PATROLS) == 54
        by_agency = Counter(d["agency"] for d in docs[: len(PATROLS)])
        assert by_agency == {"traffic": 11, "police": 3, "ambulance": 4}
        for d in docs:
            assert d["source"] == "emulated" and d["run_id"] == city.run_id
            assert len(d["label"]) <= 80                 # the oracle's C-A label cap
            if d["agency"] == "traffic":
                assert d["label"].startswith(f"Mumbai Traffic Police {d['unit_id']} · ")
                assert d["status"] == "patrol" and d["unit_id"].startswith("MTP-EM-LC")
            elif d["agency"] == "police":
                assert d["label"].startswith(f"Mumbai Police PCR {d['unit_id']} · ")
                assert d["status"] == "patrol" and d["unit_id"].startswith("MP-EM-PCR")
            else:
                assert d["label"].startswith(f"Ambulance (108) {d['unit_id']} · standby circuit, ")
                # on a standby circuit, never on a call: 'available', not en route
                assert d["status"] == "available" and d["unit_id"].startswith("108-EM-LC")
        # never the 108 request pool's ids
        assert not {d["unit_id"] for d in docs} & {f"108-EM{i:02d}" for i in range(1, 7)}
        # each unit moves along its beat
        for uid in ("MTP-EM-LC9", "MP-EM-PCR2", "108-EM-LC3"):
            pos = [d["position"] for d in docs if d["unit_id"] == uid]
            assert pos[0] != pos[-1], uid
        doc = city.status_doc()
        assert doc["density"] == 2 and doc["units"] == [p[0] for p in PATROLS]

    async def test_patrols_ride_the_network_after_it_changes(self):
        # the store's network is converted under the running city (WP-20):
        # the beats re-chain their lines on the new key, without a restart
        city, store, oracle, nats = _city()
        await _run(city, _at(9, 0), 1)
        beat = PATROLS[0]
        before = await city._patrol_line(beat[0], beat[2])
        moved = {s: [(lon + 0.01, lat), (lon + 0.02, lat)]
                 for s, (lon, lat) in store.anchors.items()}
        store.paths.update(moved)
        assert await city._patrol_line(beat[0], beat[2]) == before   # same key: cached
        store.network = "osm"
        after = await city._patrol_line(beat[0], beat[2])
        assert after != before and after[0] in [p for s in beat[2] for p in moved[s]]

    async def test_dispatched_patrol_is_handed_over(self):
        store = FakeStore(cameras=[dict(c) for c in CAMERAS], programs={PARK_ST: PROGRAM},
                          legs=LEGS, dispatched={"MTP-EM-LC2"})
        city, store, oracle, nats = _city(store=store)
        await _run(city, _at(9, 0), 2)
        units = {d["unit_id"] for s, d, _r in nats.json_docs if s == UNITS_EMULATED_SUBJECT}
        assert units == {"MTP-EM-LC1"}

    async def test_trickle_obeys_the_light_and_the_limit(self):
        city, store, oracle, nats = _city()
        start = _at(11, 0)
        await _run(city, start, 240)                  # 20 minutes of ticks
        ids = _trickle_ids(city, start, 240)
        reads = [b for b, _r in oracle.sighting_bodies]
        trickle = [b for b in reads if b["read_id"] in ids]
        assert len(trickle) >= 200
        at_stopline = [b for b in trickle if b["camera_id"] == STOP]
        assert at_stopline, "the stop-line camera reads on its greens"
        for b in at_stopline:
            epoch = datetime.fromisoformat(b["t"]).timestamp()
            assert movement_states_at(100, 0, PROGRAM["phases"], epoch)["through"] == "green"
            assert b["heading"] == 14.7
        limits = {c["camera_id"]: c["speed_limit_kmh"] for c in CAMERAS}
        for b in trickle:
            assert b["speed_kmh"] <= limits[b["camera_id"]] * 0.9 + 0.05
            assert b["source"] == "emulated_anpr" and b["run_id"] == city.run_id
            assert b["plate"][4:6] == "EM"
            assert datetime.fromisoformat(b["t"]) <= start + timedelta(seconds=5 * 240)

    async def test_violators_are_planned_causes(self):
        city, store, oracle, nats = _city()
        start = _at(11, 0)
        await _run(city, start, 240)
        ids = _trickle_ids(city, start, 240)
        violators = [b for b, _r in oracle.sighting_bodies if b["read_id"] not in ids]
        due = [v for v in city.program_for(DAY).violations
               if start < v.at <= start + timedelta(seconds=5 * 239)]
        assert violators and len(violators) == len(due)
        assert city.counters["violations_planned"] == len(due)
        for b in violators:
            epoch = datetime.fromisoformat(b["t"]).timestamp()
            if b["camera_id"] == STOP:            # ran the red
                assert movement_states_at(100, 0, PROGRAM["phases"], epoch)["through"] == "red"
            else:                                      # sped past a mid-block camera
                assert b["speed_kmh"] > 40.0 + 10.0

    async def test_violators_can_be_switched_off(self):
        city, store, oracle, nats = _city()
        city.violators = False
        start = _at(11, 0)
        await _run(city, start, 240)
        ids = _trickle_ids(city, start, 240)
        assert all(b["read_id"] in ids for b, _r in oracle.sighting_bodies)   # trickle only
        due = [v for v in city.program_for(DAY).violations
               if start < v.at <= start + timedelta(seconds=5 * 239)]
        assert due and city.counters["violations_suppressed"] == len(due)
        assert city.counters["violations_planned"] == 0
        assert city.status_doc()["violators"] is False

    async def test_unplanned_rule_hit_retires_the_camera(self):
        def rules(read):
            # an oracle that disagrees with the replica: every stop-line
            # read is a red-light violation
            return ["R_SIGNAL_VIOLATION"] if read["camera_id"] == STOP else []

        city, store, oracle, nats = _city(rules=rules)
        start = _at(11, 0)
        await _run(city, start, 240)
        ids = _trickle_ids(city, start, 240)
        trickle = [b for b, _r in oracle.sighting_bodies if b["read_id"] in ids]
        first = next(i for i, b in enumerate(trickle) if b["camera_id"] == STOP)
        assert all(b["camera_id"] != STOP for b in trickle[first + 1:])
        assert STOP in city.status_doc()["excluded_cameras"]
        assert city.counters["unplanned_R_SIGNAL_VIOLATION"] == 1

    async def test_a_stolen_violator_is_a_sighting_never_an_unplanned_hit(self):
        def rules(read):
            # the oracle's penal rules: the violator sped, or ran the red
            if read["camera_id"] == STOP:
                epoch = datetime.fromisoformat(read["t"]).timestamp()
                red = movement_states_at(100, 0, PROGRAM["phases"], epoch)["through"] == "red"
                return ["R_SIGNAL_VIOLATION"] if red else []
            return ["R_SPD_SEGMENT"] if read["speed_kmh"] > 40.0 + 10.0 else []

        city, store, oracle, nats = _city(rules=rules)
        start = _at(11, 0)
        due = [v for v in city.program_for(DAY).violations
               if start < v.at <= start + timedelta(seconds=5 * 239)]
        assert due
        # an officer's FIR earmark on every one of today's violators: the
        # oracle answers R_STOLEN_SIGHTING and WITHHOLDS the penal rule (C-N)
        oracle.earmarked.update(
            {_plate(SEED, v.pick % _FLEET)[0]: "stolen_vehicle" for v in due})
        await _run(city, start, 240)
        c = city.counters
        assert c["violations_planned"] == len(due)
        # caught all the same — the e-challan withheld, never a miss
        assert c["violations_flagged"] == c["violations_withheld"] == len(due)
        assert c["stolen_sightings"] >= len(due)
        assert not [k for k in c if k.startswith("unplanned_")], dict(c)
        assert city.status_doc()["excluded_cameras"] == []

    async def test_ambulance_requests_wait_for_an_officer(self):
        city, store, oracle, nats = _city()
        program = city.program_for(DAY)
        req = program.ambulance_requests[40]
        start = req.at - timedelta(seconds=20)
        await _run(city, start, 10)
        assert len(oracle.dispatches) == 1
        event_id, body = oracle.dispatches[0]
        assert body["agency"] == "ambulance" and body["unit_id"] == req.unit_id
        assert body["requested_by"] == "108 control (emulated)"
        assert "EMULATED" in body["note"]
        assert store.events[event_id]["metadata"]["mode"] == "living_city"
        assert city.counters["dispatch_requested"] == 1

    async def test_manual_run_preempts_overlapping_slots(self):
        reserved: dict = {}
        city, store, oracle, nats = _city(reserved=lambda: reserved)
        t = await _run(city, _at(18, 30), 1)
        active = city.status_doc()["active_slots"]
        victim = active[0]
        reserved[99] = ("ganesh_visarjan_girgaon", frozenset(victim["route_segment_ids"]))
        await city.tick(t)
        assert store.events[victim["event_id"]]["status"] == "completed"
        assert city.status_doc()["preempted"] == {victim["slot_id"]: 99}
        note = [tr for tr in oracle.transitions if tr[0] == victim["event_id"]][-1][4]
        assert "pre-empted by emulator run 99" in note
        # it does not come back while the run holds the road
        await city.tick(t + timedelta(seconds=5))
        doc = city.status_doc()
        assert victim["slot_id"] not in {s["slot_id"] for s in doc["active_slots"]}
        assert doc["yielded"] == [victim["slot_id"]]
        # the run ends: the slot (window still open) resumes as a FRESH event
        reserved.clear()
        await city.tick(t + timedelta(seconds=10))
        resumed = next(s for s in city.status_doc()["active_slots"]
                       if s["slot_id"] == victim["slot_id"])
        assert resumed["event_id"] != victim["event_id"]
        ev = store.events[resumed["event_id"]]
        assert ev["status"] == "active" and ev["metadata"]["resumed_after_run"] == 99
        assert store.events[victim["event_id"]]["status"] == "completed"
        assert city.status_doc()["yielded"] == []
        assert city.counters["slots_resumed"] == 1

    async def test_an_oracle_outage_heals(self):
        city, store, oracle, nats = _city()
        oracle.down = True
        t = await _run(city, _at(18, 30), 1)
        doc = city.status_doc()
        assert len(doc["active_slots"]) >= 2      # opened (store), not yet active
        assert all(s["event_status"] == "planning" for s in doc["active_slots"])
        assert all(store.events[s["event_id"]]["status"] == "planning"
                   for s in doc["active_slots"])
        assert city.counters["events_activate_failed"] == len(doc["active_slots"])
        oracle.down = False
        t = t + timedelta(seconds=31)              # the next heal pass
        await city.tick(t)
        assert all(store.events[s["event_id"]]["status"] == "active"
                   for s in city.status_doc()["active_slots"])
        assert city.counters["events_activated_late"] == len(doc["active_slots"])
        # a close that fails while the oracle is down is retried, not lost
        victim = city.status_doc()["active_slots"][0]
        oracle.down = True
        await city.stop()
        assert store.events[victim["event_id"]]["status"] == "active"
        assert city.counters["events_close_failed"] >= 1

    async def test_close_retried_by_the_running_session(self):
        reserved: dict = {}
        city, store, oracle, nats = _city(reserved=lambda: reserved)
        t = await _run(city, _at(18, 30), 1)
        victim = city.status_doc()["active_slots"][0]
        oracle.down = True
        reserved[7] = ("cyclone_landfall_recovery", frozenset(victim["route_segment_ids"]))
        await city.tick(t)                         # pre-empt: the close fails
        assert store.events[victim["event_id"]]["status"] == "active"
        oracle.down = False
        await city.tick(t + timedelta(seconds=31))
        assert store.events[victim["event_id"]]["status"] == "completed"
        assert city._session.unclosed == {}

    async def test_session_ledgered_once_the_store_answers(self):
        city, store, oracle, nats = _city()
        real_insert = store.insert_run

        async def broken(**kw):
            raise ConnectionError("store down")

        store.insert_run = broken
        t = await _run(city, _at(9, 0), 1)
        assert city.run_id is None and "ledger" in (city.last_error or "")
        store.insert_run = real_insert
        await city.tick(t + timedelta(seconds=31))
        assert city.run_id is not None
        assert store.runs[city.run_id]["spec"]["mode"] == "living_city"

    async def test_day_rollover_finishes_the_session(self):
        city, store, oracle, nats = _city()
        await _run(city, _at(23, 59, 50), 1)
        first = city.run_id
        await city.tick(_at(0, 0, 5, d=DAY + timedelta(days=1)))
        assert city.run_id != first
        assert store.runs[first]["status"] == "completed"
        assert city._session.date_ist == DAY + timedelta(days=1)

    async def test_next_causes_look_past_ist_midnight(self):
        city, store, oracle, nats = _city()
        now = _at(23, 30)
        city._now = lambda: now
        await _run(city, now, 1)
        midnight = _at(0, 0, d=DAY + timedelta(days=1))
        causes = city.status_doc()["next_causes"]
        assert causes and all(now <= datetime.fromisoformat(c["at"]) < now + timedelta(minutes=90)
                              for c in causes)
        assert any(datetime.fromisoformat(c["at"]) >= midnight for c in causes)

    async def test_an_officer_cancelled_event_is_left_closed(self):
        city, store, oracle, nats = _city()
        oracle.down = True
        t = await _run(city, _at(18, 30), 1)
        victim = city.status_doc()["active_slots"][0]
        oracle.down = False
        # a duty officer cancels the still-planning event from the ops wall
        await oracle.event_status(victim["event_id"], "cancelled", "duty officer")
        await city.tick(t + timedelta(seconds=31))           # the heal pass
        doc = city.status_doc()
        assert victim["slot_id"] not in {s["slot_id"] for s in doc["active_slots"]}
        assert all(s["event_status"] == "active" for s in doc["active_slots"])
        assert city.counters["events_closed_by_officer"] == 1
        await city.tick(t + timedelta(seconds=36))
        assert victim["slot_id"] not in {s["slot_id"] for s in city.status_doc()["active_slots"]}
        assert store.events[victim["event_id"]]["status"] == "cancelled"

    async def test_start_stop_and_orphans(self):
        store = FakeStore(cameras=[dict(c) for c in CAMERAS], programs={PARK_ST: PROGRAM}, legs=LEGS)
        # an earlier session's slot left open by a crash
        await store.upsert_corridor_event(
            "20000000-0000-0000-0000-000000000001", None, "work_zone", "none", "LOW",
            "orphan slot", _at(10), _at(12),
            {"source": "event-emulator", "mode": "living_city", "run_id": 1234})
        store.events["20000000-0000-0000-0000-000000000001"]["status"] = "active"
        city, store, oracle, nats = _city(store=store)
        await city.start()
        await asyncio.sleep(0.1)
        assert store.events["20000000-0000-0000-0000-000000000001"]["status"] == "completed"
        doc = city.status_doc()
        assert doc["status"] == "running" and doc["active_slots"]
        opened = [s["event_id"] for s in doc["active_slots"]]
        stopped = await city.stop()
        assert stopped["status"] == "stopped" and stopped["active_slots"] == []
        assert all(store.events[e]["status"] == "completed" for e in opened)
        rid = doc["run_id"]
        assert store.runs[rid]["status"] == "stopped"


# ── 108 requests outlive their slot ─────────────────────────────────────────


def _filed(oracle: FakeOracle) -> list[tuple[str, dict]]:
    """(dispatch id, row) in filing order."""
    return list(oracle.dispatch_rows.items())


async def _one_request(city: LivingCity, oracle: FakeOracle, index: int = 40):
    """Run the city up to program request ``index`` (filed, 'requested')."""
    req = city.program_for(DAY).ambulance_requests[index]
    t = await _run(city, req.at - timedelta(seconds=20), 10)
    assert len(oracle.dispatches) == 1
    did, row = _filed(oracle)[0]
    return req, t, did, row


class TestRequestsOutliveTheirSlot:
    async def test_a_preempted_slot_refiles_its_pending_request(self):
        reserved: dict = {}
        city, store, oracle, nats = _city(reserved=lambda: reserved)
        req, t, first_id, first = await _one_request(city, oracle)
        slot = next(s for s in city.status_doc()["active_slots"]
                    if s["event_id"] == first["event_id"])
        reserved[99] = ("vvip_convoy_base", frozenset(slot["route_segment_ids"]))
        await city.tick(t)
        # the oracle's auto-close cancelled it with the pre-empted event …
        assert oracle.dispatch_rows[first_id]["status"] == "cancelled"
        # … and 108 re-filed it at once on a slot that is still open
        assert len(oracle.dispatches) == 2
        new_id, new = _filed(oracle)[1]
        assert new["event_id"] != first["event_id"]
        assert store.events[new["event_id"]]["status"] == "active"
        assert store.events[new["event_id"]]["metadata"]["mode"] == "living_city"
        body = new["body"]
        assert body["unit_id"] == req.unit_id and body["agency"] == "ambulance"
        assert body["requested_by"] == "108 control (emulated)"
        assert "re-filed (filing 2)" in body["note"] and first_id in body["note"]
        assert "pre-empted by emulator run 99" in body["note"] and "EMULATED" in body["note"]
        assert len(body["note"]) <= 500 and body.get("waypoint_junction")
        assert new["status"] == "requested"            # an officer still decides
        assert city.counters["dispatch_released"] == 1
        assert city.counters["dispatch_refiled"] == 1
        # once filed, it is not filed again on later ticks
        await city.tick(t + timedelta(seconds=5))
        assert len(oracle.dispatches) == 2 and city.status_doc()["refiling"] == []

    async def test_a_decided_request_is_never_refiled(self):
        reserved: dict = {}
        city, store, oracle, nats = _city(reserved=lambda: reserved)
        req, t, first_id, first = await _one_request(city, oracle)
        oracle.decide(first_id, "approved")           # the duty officer approved it
        slot = next(s for s in city.status_doc()["active_slots"]
                    if s["event_id"] == first["event_id"])
        reserved[99] = ("vvip_convoy_base", frozenset(slot["route_segment_ids"]))
        await city.tick(t)
        assert oracle.dispatch_rows[first_id]["status"] == "cancelled"
        assert len(oracle.dispatches) == 1
        assert city.counters["dispatch_refiled"] == 0 and city.counters["dispatch_released"] == 0

    async def test_a_request_with_no_open_slot_waits_then_expires(self):
        reserved: dict = {}
        city, store, oracle, nats = _city(reserved=lambda: reserved)
        req, t, first_id, first = await _one_request(city, oracle)
        # a run holds EVERY living-city road: nothing can carry the request
        reserved[99] = ("vvip_convoy_base",
                        frozenset(s for site in SITES for s in site.segments))
        await city.tick(t)
        assert city.status_doc()["active_slots"] == []
        assert [r["replaces"] for r in city.status_doc()["refiling"]] == [first_id]
        for k in range(1, 23):                        # 22 minutes, a tick a minute
            await city.tick(t + timedelta(minutes=k))
        assert len(oracle.dispatches) == 1
        assert city.counters["dispatch_refile_expired"] == 1
        assert city.status_doc()["refiling"] == []

    async def test_the_ist_rollover_refiles_onto_the_next_days_slots(self):
        # a day whose last 108 request is late enough to still be waiting
        # at midnight (re-filed within 20 minutes of the first ask)
        for offset in range(0, 30):
            d = DAY + timedelta(days=offset)
            late = [a for a in build_day_program(SEED, d).ambulance_requests
                    if a.at.astimezone(IST).hour == 23 and a.at.astimezone(IST).minute >= 42]
            if late:
                break
        else:
            raise AssertionError("no late 108 request in 30 days")
        req = late[-1]
        city, store, oracle, nats = _city()
        t = await _run(city, req.at - timedelta(seconds=10), 4)
        assert len(oracle.dispatches) == 1
        first_id = _filed(oracle)[0][0]
        midnight = datetime.combine(d + timedelta(days=1), datetime.min.time(), IST)
        while t <= midnight + timedelta(seconds=5):
            await city.tick(t)
            t += timedelta(seconds=5)
        assert oracle.dispatch_rows[first_id]["status"] == "cancelled"
        refiled = [(did, row) for did, row in _filed(oracle)[1:]
                   if "IST day ended" in row["body"]["note"]]
        assert refiled
        did, row = refiled[-1]
        meta = store.events[row["event_id"]]["metadata"]
        assert meta["date_ist"] == (d + timedelta(days=1)).isoformat()
        assert meta["run_id"] == city.run_id and row["status"] == "requested"

    async def test_stop_clears_what_was_waiting(self):
        reserved: dict = {}
        city, store, oracle, nats = _city(reserved=lambda: reserved)
        req, t, first_id, first = await _one_request(city, oracle)
        await city.stop()
        assert oracle.dispatch_rows[first_id]["status"] == "cancelled"
        assert city.status_doc()["refiling"] == []
        assert len(oracle.dispatches) == 1


# ── the seed network check ──────────────────────────────────────────────────


class TestNetworkCheck:
    async def test_the_seed_network_passes(self):
        city, store, oracle, nats = _city()
        await _run(city, _at(9, 0), 1)
        assert city.detail is None and city.health_doc()["detail"] is None

    async def test_a_mismatch_fails_loudly_and_skips_unknown_roads(self):
        adjacency = await FakeStore().segment_junction_ids()
        gone = next(site for site in SITES if site.kind == "breakdown").segments[0]
        del adjacency[gone]                           # a road reseeded away
        sf = next(site for site in SITES if site.kind == "signal_fault")
        jid = sf.junctions[0]
        for s in sf.segments:                         # its junction renumbered
            adjacency.get(s, set()).discard(jid)
        store = FakeStore(cameras=[dict(c) for c in CAMERAS], programs={PARK_ST: PROGRAM},
                          legs=LEGS, adjacency=adjacency)
        city, store, oracle, nats = _city(store=store)
        program = city.program_for(DAY)
        slot = next(s for s in program.slots if gone in s.route_segment_ids)
        await _run(city, slot.starts_at + timedelta(minutes=1), 1)
        detail = city.status_doc()["detail"]
        assert detail.startswith("seed network mismatch")
        assert f"[{gone}]" in detail and f"{sf.site_id}:J{jid}" in detail
        assert city.health_doc()["detail"] == detail
        opened = {s["slot_id"] for s in city.status_doc()["active_slots"]}
        assert slot.slot_id not in opened
        assert city.counters["slots_unknown_roads"] >= 1
        # no event was ever opened on the unknown road
        assert store.event_routes and all(gone not in r for r in store.event_routes.values())
