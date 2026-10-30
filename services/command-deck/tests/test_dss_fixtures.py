"""The dss fixtures meet the frozen C-U contract (FIX-E-DSSCARD item 3).

Every ``tests/fixtures/dss/*.json`` is a DecisionSupport the oracle could
have produced: it validates against ``osint_common.types.DecisionSupport``
(pydantic, ``extra="forbid"`` — the deliberately-extra synthetic/note keys
of the old fixtures broke validation and hid the invalid best_blocked), the
blocked best scores ABOVE the pick (it ranks after it only because it cannot
be resourced — the engine never reports a blocked response that scored
below the pick), and the public-safety floor is one of the merged modes.

The deck parser's own tolerance (unknown fields ignored) is pinned where it
belongs, in tests/dss.unit.mjs over an injected extra field — these files
carry none.

Run (from services/command-deck):

    PYTHONPATH=<worktree>/services/osint-common/src:<worktree>/services/traffic-oracle/src \\
        <gate venv>/bin/python -m pytest -q -p no:cacheprovider tests/test_dss_fixtures.py
"""

import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
DECK = HERE.parent
OSINT_COMMON_SRC = DECK.parent / "osint-common" / "src"
if str(OSINT_COMMON_SRC) not in sys.path:
    sys.path.insert(0, str(OSINT_COMMON_SRC))
TRAFFIC_ORACLE_SRC = DECK.parent / "traffic-oracle" / "src"
if str(TRAFFIC_ORACLE_SRC) not in sys.path:
    sys.path.insert(0, str(TRAFFIC_ORACLE_SRC))

from osint_common.types import DecisionSupport  # noqa: E402
from traffic_oracle.decision_support import mcda  # noqa: E402

FIXTURES = sorted((HERE / "fixtures" / "dss").glob("*.json"))


def load(name: str) -> dict:
    return json.loads((HERE / "fixtures" / "dss" / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_validates_against_cu(path: pathlib.Path) -> None:
    """One fixture = one DecisionSupport the frozen contract accepts."""
    DecisionSupport.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_carries_no_deliberately_extra_fields(path: pathlib.Path) -> None:
    """``extra="forbid"``: no synthetic/note keys in the committed files — the
    deck parser's tolerance is tested separately, over an injected field."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "synthetic" not in raw and "note" not in raw
    assert "future_field" not in raw.get("situation", {})


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_best_blocked_scores_above_the_pick(path: pathlib.Path) -> None:
    """The blocked best is ranked after the pick ONLY because it cannot be
    resourced — it never scores below the pick the officer is shown."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    rec = raw["recommendation"]
    blocked = rec.get("best_blocked")
    if blocked is None:
        pytest.skip("no blocked best in this fixture")
    closeness = {c["coa_id"]: c["score"]["closeness"] for c in raw["coa_set"]}
    pick = closeness[rec["top_coa_id"]]
    assert blocked["closeness"] is not None and pick is not None
    assert blocked["closeness"] > pick, (
        f"{path.name}: best_blocked {blocked['coa_id']} ({blocked['closeness']}) "
        f"must outscore the pick {rec['top_coa_id']} ({pick})"
    )


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_public_safety_floor_is_a_merged_mode(path: pathlib.Path) -> None:
    """The deck reads the structured floor (hold | verify | none); a fixture
    without one would silently render no line."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["recommendation"].get("public_safety_floor") in {"hold", "verify", "none"}


def test_fixtures_exist() -> None:
    assert {p.name for p in FIXTURES} == {"dss_road_accident.json", "dss_weather_hazard.json"}


# ── the engine-emission shape (fix round 2: the fixture must be an output the engine can produce) ──


def _scored_and_vetoed(raw: dict) -> tuple[list[dict], list[dict]]:
    rows = raw["coa_set"]
    return [c for c in rows if not c["ethics"]["vetoed"]], [c for c in rows if c["ethics"]["vetoed"]]


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_ranking_is_what_the_engine_ranks(path: pathlib.Path) -> None:
    """The order is ``mcda.rank_coas`` over the fixture's own closeness values
    (with the do-nothing baseline held while the floor holds), the vetoed COAs
    appended after — exactly the engine's ``ranked_ids`` assembly
    (traffic_oracle/decision_support/engine.py)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    rec = raw["recommendation"]
    scored, vetoed = _scored_and_vetoed(raw)
    closeness = [c["score"]["closeness"] for c in scored]
    feasible = [c["resource_feasibility"]["feasible"] for c in scored]
    baseline = next((i for i, c in enumerate(scored) if c["kind"] == "baseline"), None)
    hold = rec.get("public_safety_floor") == "hold" and baseline is not None
    ranking = mcda.rank_coas(closeness, feasible, baseline=baseline if hold else None)
    engine_ids = [scored[i]["coa_id"] for i in ranking.order]
    engine_ids += [c["coa_id"] for c in vetoed]
    assert rec["ranked_coa_ids"] == engine_ids, (
        f"{path.name}: ranked_coa_ids {rec['ranked_coa_ids']} is not the engine's order {engine_ids}"
        + (" (floor hold: the baseline ranks below every feasible response)" if hold else "")
    )
    assert rec["top_coa_id"] == engine_ids[0]
    assert rec["margin"] == pytest.approx(round(float(ranking.margin), 4)), (
        f"{path.name}: margin {rec['margin']} != the engine's {round(float(ranking.margin), 4)}"
    )


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_ranks_and_closeness_are_engine_emissions(path: pathlib.Path) -> None:
    """Per-COA emissions: ``score.rank`` is the position in ranked_coa_ids; a
    vetoed COA's closeness is ``null`` (the engine never scores one); a
    non-vetoed closeness is a number in [0, 1]; the blocked best's closeness
    is the named COA's own."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    rec = raw["recommendation"]
    closeness = {c["coa_id"]: c["score"]["closeness"] for c in raw["coa_set"]}
    for coa in raw["coa_set"]:
        cid = coa["coa_id"]
        assert coa["score"]["rank"] == rec["ranked_coa_ids"].index(cid) + 1, f"{path.name}: {cid} rank"
        if coa["ethics"]["vetoed"]:
            assert closeness[cid] is None, f"{path.name}: vetoed {cid} carries a closeness; the engine emits null"
        else:
            assert closeness[cid] is not None and 0.0 <= closeness[cid] <= 1.0, f"{path.name}: {cid} closeness"
    blocked = rec.get("best_blocked")
    if blocked is not None:
        assert blocked["closeness"] == closeness[blocked["coa_id"]], f"{path.name}: best_blocked closeness mismatch"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_closeness_is_the_engines_topsis(path: pathlib.Path) -> None:
    """Every scored COA's closeness is ``mcda.topsis`` over the fixture's own attributes and AHP weights (the engine's
    ``compute`` matrix, all nine criteria) — a hand-set closeness, e.g. a blocked best that cannot outscore the pick on
    its own attributes, fails here."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    weights = {c["id"]: c["weight"] for c in raw["criteria"]}
    assert set(weights) == set(mcda.CRITERION_IDS), f"{path.name}: the engine emits all nine criteria"
    scored, _ = _scored_and_vetoed(raw)
    matrix = [[c["attributes"][k] for k in mcda.CRITERION_IDS] for c in scored]
    top = mcda.topsis(matrix, [weights[k] for k in mcda.CRITERION_IDS])
    for coa, closeness in zip(scored, top.closeness):
        assert coa["score"]["closeness"] == pytest.approx(closeness, abs=0.005), (
            f"{path.name}: {coa['coa_id']} closeness {coa['score']['closeness']} != TOPSIS {closeness:.4f}"
        )


# ── FIX-H-DECK: the fixtures carry what today's engine emits (FIX-G-ORACLE HON-7/8/9) ──


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_criteria_labels_are_the_engines(path: pathlib.Path) -> None:
    """The criteria table says what each criterion is: the engine's own labels, including the two that are
    fixed priors, not simulated outcomes ("… (fixed prior by COA actions, not simulated)", "… (nominal time
    by COA kind, not a unit ETA)") — a fixture with the old labels shows an officer a claim the engine dropped."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    labels = {c["id"]: c["label"] for c in raw["criteria"]}
    assert labels == {cid: label for cid, label, _direction in mcda.CRITERIA}, f"{path.name}: criteria labels differ from the engine's"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_108_delay_only_for_a_coa_that_sends_a_108(path: pathlib.Path) -> None:
    """HON-9: the 108 delay is the COA's OWN 108's — a COA that dispatches no ambulance has none to delay
    (0 s, green corridor intact); the engine stopped applying +180/-60 s to every closure COA."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    for coa in raw["coa_set"]:
        sends_108 = any(
            a.get("verb") == "dispatch" and str((a.get("params") or {}).get("agency", "")).lower() in {"ambulance", "108"}
            for a in coa["actions"]
        )
        impact = coa["predicted_outcome"]["emergency_impact"]
        if not sends_108:
            assert impact["ambulance_delay_sec"] == 0, f"{path.name}: {coa['coa_id']} sends no 108 yet carries a 108 delay"
            assert impact["green_corridor_ok"] is True, f"{path.name}: {coa['coa_id']} sends no 108 yet breaks the green corridor"
