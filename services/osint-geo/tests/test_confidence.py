"""The geocode confidence: the formula exactly as SPEC §1.4 step 6, the buckets, and monotonicity."""

from __future__ import annotations

import itertools
import math
import random

import pytest

from osint_geo import confidence
from osint_geo.confidence import bucket, margin, score, snap_quality, specificity


def test_weights_are_the_spec_formula():
    assert dict(confidence.WEIGHTS) == {"match": 0.30, "specificity": 0.25, "margin": 0.20, "snap": 0.15,
                                        "locality": 0.10}
    assert math.isclose(sum(confidence.WEIGHTS.values()), 1.0)


@pytest.mark.parametrize(
    "parts",
    [
        (1.0, 1.0, 1.0, 1.0, 1.0),
        (0.0, 0.0, 0.0, 0.0, 0.0),
        (1.0, 0.95, 0.0, 1.0, 0.3),
        (0.93, 0.8, 0.42, 0.6, 1.0),
        (0.5, 0.55, 1.0, 0.0, 0.3),
    ],
)
def test_score_is_the_weighted_sum(parts):
    m, s, g, q, loc = parts
    assert score(m, s, g, q, loc) == pytest.approx(0.30 * m + 0.25 * s + 0.20 * g + 0.15 * q + 0.10 * loc)
    assert 0.0 <= score(m, s, g, q, loc) <= 1.0


def test_the_kolkata_figures():
    # the EM Bypass case (osint_common.testing): an exact road alias on the network, a tie between its own four
    # mentions, a national aggregator -> 0.68 medium (the fixture's figure)
    r = round(score(1.0, specificity("road"), 0.0, snap_quality(0.0, on_network=True), confidence.NON_LOCAL), 3)
    assert r == 0.68 and bucket(r) == "medium"
    # the Gariahat robbery: an exact junction on the network -> 0.7175, reported 0.718 (the PoC's rounding)
    j = round(score(1.0, specificity("junction"), 0.0, snap_quality(0.0, on_network=True), confidence.NON_LOCAL), 3)
    assert j == 0.718 and bucket(j) == "medium"
    # New Market, 65.1 m from Jawaharlal Nehru Road's anchor, named once by a national outlet -> 0.926 high
    n = round(score(1.0, specificity("landmark"), 1.0, snap_quality(65.1), confidence.NON_LOCAL), 3)
    assert n == 0.926 and bucket(n) == "high"
    # a bare area word (a neighbourhood: no road anchor, no snap credit) in a national outlet's title and text (a
    # tie with itself) -> 0.468 low
    a = round(score(1.0, specificity("neighbourhood"), 0.0, snap_quality(None), confidence.NON_LOCAL), 3)
    assert a == 0.468 and bucket(a) == "low"
    # a single unambiguous mention of a junction in a local source -> 0.988 high
    assert round(score(1.0, 0.95, 1.0, 1.0, confidence.LOCAL), 3) == 0.988


@pytest.mark.parametrize(
    "value,want",
    [(1.0, "high"), (0.75, "high"), (0.7499, "medium"), (0.5, "medium"), (0.4999, "low"), (0.4, "low"),
     (0.25, "low"), (0.0, "low")],
)
def test_buckets(value, want):
    assert bucket(value) == want


def test_monotone_in_every_component():
    rng = random.Random(20261024)
    grid = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
    for _ in range(400):
        base = [rng.choice(grid) for _ in range(5)]
        for i in range(5):
            for up in grid:
                if up < base[i]:
                    continue
                raised = list(base)
                raised[i] = up
                assert score(*raised) >= score(*base) - 1e-12
                order = ["low", "medium", "high"]
                assert order.index(bucket(score(*raised))) >= order.index(bucket(score(*base)))


def test_every_component_counts():
    zero = [0.0] * 5
    for i, w in enumerate((0.30, 0.25, 0.20, 0.15, 0.10)):
        one = list(zero)
        one[i] = 1.0
        assert score(*one) == pytest.approx(w)


@pytest.mark.parametrize("bad", [-0.01, 1.01, float("nan"), float("inf"), True, "0.5", None])
def test_components_must_be_units(bad):
    with pytest.raises(ValueError):
        score(bad, 1.0, 1.0, 1.0, 1.0)
    with pytest.raises(ValueError):
        bucket(bad)


def test_snap_quality_curve():
    assert snap_quality(None, on_network=True) == snap_quality(0.0) == 1.0
    assert snap_quality(190.5) == pytest.approx(1 - 190.5 / 2500)
    assert snap_quality(900.0) == pytest.approx(1 - 900 / 2500)
    # F-HONEST OSINT-3: beyond 900 m a place is not on its segment and earns no snap quality (was the 0.4 floor)
    assert snap_quality(900.1) == snap_quality(1500.0) == snap_quality(2500.0) == 0.0
    assert snap_quality(2500.1) == snap_quality(None) == snap_quality(float("nan")) == snap_quality(-1.0) == 0.0
    last = 2.0
    for d in range(0, 3001, 25):
        q = snap_quality(float(d))
        assert q <= last
        last = q


def test_margin():
    assert margin(0.8, None) == 1.0  # a single reading
    assert margin(0.8, 0.8) == 0.0  # a tie (a place mentioned twice ties with itself)
    assert margin(0.8, 0.4) == pytest.approx(0.5)
    assert margin(0.8, 0.9) == 0.0 and margin(0.0, 0.0) == 0.0
    for top, second in itertools.product([0.2, 0.5, 0.9], [0.0, 0.1, 0.5, 0.9]):
        assert 0.0 <= margin(top, second) <= 1.0


def test_specificity_order():
    s = confidence.SPECIFICITY
    assert s["landmark"] == s["poi"] == 1.0 > s["junction"] > s["road"] > s["neighbourhood"] > s["admin"]
    assert specificity("unknown") == 0.5


def test_area_caps_stay_below_the_formula():
    # an area-level geocode carries the cap of its level, never more (plan R28)
    from osint_geo.resolver import DISTRICT_MUMBAI, DISTRICT_MUMBAI_SUBURBAN, STATE_MAHARASHTRA

    assert DISTRICT_MUMBAI.confidence == DISTRICT_MUMBAI_SUBURBAN.confidence == 0.4
    assert STATE_MAHARASHTRA.confidence == 0.25
    levels = (DISTRICT_MUMBAI, DISTRICT_MUMBAI_SUBURBAN, STATE_MAHARASHTRA)
    assert {bucket(level.confidence) for level in levels} == {"low"}
    # the two city districts carry a representative point; the state none
    assert DISTRICT_MUMBAI.lon is not None and DISTRICT_MUMBAI_SUBURBAN.lon is not None
    assert STATE_MAHARASHTRA.lon is None and STATE_MAHARASHTRA.lat is None
