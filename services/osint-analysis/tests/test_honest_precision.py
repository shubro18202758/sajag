"""F-HONEST OSINT-3 (pipeline part): a situation carries only the precision its report gave.

A resolver once carried a neighbourhood as the road segment it snapped to two kilometres away, with ``area_level``
False. Below, the Kolkata shapes of the same fault: "Beleghata" (a neighbourhood) snapped to the EM Bypass, segment
1038, 1.3 km away; the Jodhpur Park pandal (a landmark) snapped to Rash Behari Avenue, segment 1033, 1.5 km away;
and, the control, Milan Mela Ground 415 m from the EM Bypass, segment 1036. The geocodes are exactly what such a
resolver answers (an injected resolver may still answer so); the pipeline must not pass them on.
"""

from __future__ import annotations

from analysis_fixtures import FakeResolver, make_signal, point
from osint_analysis.pipeline import run_pipeline

BELEGHATA = (88.393, 22.565)
JODHPUR_PARK_PANDAL = (88.366, 22.506)
MILAN_MELA_GROUND = (88.402, 22.54)


def _one(signals, geocodes):
    result = run_pipeline(signals, resolver=FakeResolver(geocodes))
    assert len(result.resolved) == 1
    return result.resolved[0]


def test_a_neighbourhood_is_area_level_without_a_segment():
    a = make_signal(title="Fire breaks out in a godown in Beleghata", publisher="news-a.example")
    b = make_signal(title="Fire breaks out at a Beleghata godown, tenders rushed", publisher="news-b.example")
    geos = [point(s, BELEGHATA, toponym="Beleghata", feature_type="neighbourhood", segment_id=1038,
                  residual_m=1293.0, snapped_to="Eastern Metropolitan Bypass", confidence=0.602) for s in (a, b)]
    r = _one([a, b], geos)
    assert r.is_event and r.toponym == "Beleghata"
    assert r.area_level is True and r.segment_id is None and r.junction_id is None
    assert r.rep_lon is not None  # the area's reference point stays


def test_a_landmark_beyond_900_m_keeps_no_segment():
    a = make_signal(title="Fire at a stall near the Jodhpur Park pandal", publisher="news-a.example")
    geos = [point(a, JODHPUR_PARK_PANDAL, toponym="Jodhpur Park Durga Puja", feature_type="landmark",
                  segment_id=1033, residual_m=1505.0, snapped_to="Rash Behari Avenue", confidence=0.64)]
    r = _one([a], geos)
    assert r.segment_id is None and r.area_level is False and r.toponym == "Jodhpur Park Durga Puja"


def test_a_landmark_within_900_m_keeps_its_segment():
    a = make_signal(title="Fire at a stall near Milan Mela Ground", publisher="news-a.example")
    geos = [point(a, MILAN_MELA_GROUND, toponym="Milan Mela Ground", feature_type="landmark", segment_id=1036,
                  residual_m=415.0, snapped_to="Eastern Metropolitan Bypass", confidence=0.7)]
    assert _one([a], geos).segment_id == 1036
