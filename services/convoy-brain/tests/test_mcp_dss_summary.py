"""city_decision_support after audit B (FIX-AUDIT-B): summary, pending proposal, 27B cooldown.

What this suite pins:
    summary     the masked summary exposes the structured best_blocked
                ({coa_id, label, closeness, missing[], unblock_action}),
                public_safety_floor and the DSS labels; the decision homes
                include /gods-eye
    masking     a registration mark in the dissent, the value-of-information
                why, the top COA label or the best-blocked label/missing is
                masked at egress (each field on its own)
    no-supersede  a subject that already carries a PROPOSED, unexpired DSS
                gets that proposal back (GET) marked reused — no POST, no 27B
                call; an expired or decided one is regenerated, and a pending
                one the read cannot confirm is reported as superseded
    cooldown    the forced 27B COA-strategy checkpoint runs at most once per
                subject per DSS_PRIOR_COOLDOWN_SEC
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta

import httpx

from convoy_brain.decider import CheckpointResult
from convoy_brain.llm.decider_client import DeciderAnswer
from convoy_brain.mcp import server
from convoy_brain.mcp.server import ToolExecutor

OSINT_ID = "1b94e9d2-7e11-4174-a735-7dd3be3189cf"
URN = f"osint_event:{OSINT_ID}"
ENTITY = f"/api/v1/city/entity/osint_event/{OSINT_ID}"
GENERATE = f"/api/v1/decision-support/{URN}/generate"
PENDING_ID = "5b0c7a1e-2f44-4c1d-8e3a-9a6f0d2b7c11"
NEW_ID = "9f2c6f30-1e5f-4a3a-9d8e-2f7ab1c33d10"
GET_PENDING = f"/api/v1/decision-support/{PENDING_ID}"


class Recorder:
    """MockTransport handler: routes by (method, path), records every request."""

    def __init__(self, routes: dict[tuple[str, str], object]) -> None:
        self.routes = routes
        self.seen: list[tuple[str, str, object]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.seen.append((request.method, request.url.path, body))
        handler = self.routes.get((request.method, request.url.path))
        if handler is None:
            return httpx.Response(404, json={"detail": "Not Found"})
        if isinstance(handler, httpx.Response):
            return handler
        return httpx.Response(200, json=handler)

    def posts(self) -> list[tuple[str, object]]:
        return [(path, body) for method, path, body in self.seen if method == "POST"]

    def gets(self) -> list[str]:
        return [path for method, path, _b in self.seen if method == "GET"]


class FakeDecider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    result: CheckpointResult | None = None  # None: a served "standard" answer

    async def checkpoint(self, **kwargs):
        self.calls.append(kwargs)
        if self.result is not None:
            return self.result
        return CheckpointResult(tier="decider", answers={"coa_strategy": DeciderAnswer(
            name="coa_strategy", type="choice", value="standard",
            probability=0.61, confidence=0.83)})


def executor_with(recorder: Recorder, decider=None) -> ToolExecutor:
    return ToolExecutor(
        traffic_oracle_url="http://127.0.0.1:8114",
        client=httpx.AsyncClient(base_url="http://127.0.0.1:8114",
                                 transport=httpx.MockTransport(recorder)),
        decider_brain=decider,
    )


def dossier(dss: dict | None = None, credibility: float = 0.65) -> dict:
    props = {
        "event_class": "road_accident",
        "subtype": "affray+collision",
        "toponym": "Sector V (Salt Lake)",
        "credibility": credibility,
        "verification_state": "NEWS-REPORTED",
        "summary": "Car crashes into three vehicles near Sector V on Salt Lake Bypass",
        "second_order": [],
    }
    if dss is not None:
        props["dss"] = dss
    return {"entity": {"urn": URN, "kind": "osint_event",
                       "label": "Road accident · Sector V (Salt Lake)",
                       "props": props}, "related": [], "audit": []}


def props_dss(state: str = "proposed", expires_in_min: float = 30.0,
              dss_id: str = PENDING_ID) -> dict:
    """A C-T DssSummary as the dossier carries it."""
    expires = datetime.now(UTC) + timedelta(minutes=expires_in_min)
    generated = expires - timedelta(minutes=45)
    return {"dss_id": dss_id, "state": state, "top_coa_id": "coa_min",
            "top_coa_label": "Driver and citizen advisory only (VMS + app push)",
            "generated_at": generated.isoformat().replace("+00:00", "Z"), "horizon_min": 45,
            "expires_at": expires.isoformat().replace("+00:00", "Z")}


#: The Sector V proposal's shape (no unit free, the floor holding), with a
#: plate in every free-text field.
DSS_DOC = {
    "dss_id": NEW_ID,
    "event_urn": URN,
    "state": "proposed",
    "coa_set": [
        {"coa_id": "coa_base", "kind": "baseline", "label": "Monitor only (do nothing)",
         "resource_feasibility": {"feasible": True, "shortfalls": []},
         "ethics": {"vetoed": False, "veto_reason": None}},
        {"coa_id": "coa_min", "kind": "minimal",
         "label": "Advisory only — VMS names car MH01AB1234 in the service lane",
         "resource_feasibility": {"feasible": True, "shortfalls": []},
         "ethics": {"vetoed": False, "veto_reason": None}},
        {"coa_id": "coa_std", "kind": "standard",
         "label": "Advisory + 108 ambulance + 1 patrol to car mh05cd5678",
         "resource_feasibility": {"feasible": False,
                                  "shortfalls": ["ambulance: need 1, 0 free",
                                                 "police: need 1, 0 free"]},
         "ethics": {"vetoed": False, "veto_reason": None}},
    ],
    "recommendation": {
        "ranked_coa_ids": ["coa_min", "coa_base", "coa_std"],
        "top_coa_id": "coa_min",
        "margin": 0.0,
        "value_of_information": {
            "evoi": -0.188, "advise_gather": False,
            "why": "acting now: verifying first is not available this cycle; the "
                   "reports name MH-08-EF-4321",
        },
        "dissent": "Runner-up is coa_base: the floor holds it below car "
                   "MH.06.EM.9001's advisory. More text.",
        "decision": "await_officer",
        "strategy_prior": None,
        "best_blocked": {
            "coa_id": "coa_std",
            "label": "Advisory + 108 ambulance + 1 patrol to car mh05cd5678",
            "closeness": 0.8555,
            "missing": ["ambulance: need 1, 0 free", "police: need 1, 0 free near MH07GH2468"],
            "unblock_action": "request_units",
        },
        "public_safety_floor": "hold",
    },
    "human_gate": {"state": "proposed", "required_role": "duty_officer"},
    "labels": ["NEWS-REPORTED", "SIMULATED"],
}


async def run(recorder: Recorder, decider=None, executor: ToolExecutor | None = None) -> dict:
    ex = executor or executor_with(recorder, decider)
    try:
        return await ex.execute("city_decision_support", {"event_urn": URN})
    finally:
        if executor is None:
            await ex.close()


# ── the summary ──────────────────────────────────────────────────────────────


class TestSummary:
    async def test_exposes_best_blocked_floor_and_labels(self):
        recorder = Recorder({("GET", ENTITY): dossier(), ("POST", GENERATE): DSS_DOC})
        result = await run(recorder)
        bb = result["best_blocked"]
        assert bb["coa_id"] == "coa_std"
        assert bb["closeness"] == 0.8555
        assert bb["unblock_action"] == "request_units"
        assert bb["missing"][0] == "ambulance: need 1, 0 free"
        assert result["public_safety_floor"] == "hold"
        assert result["labels"] == ["NEWS-REPORTED", "SIMULATED"]
        assert result["reused"] is False and result["superseded"] is None

    async def test_no_best_blocked_and_a_proposal_predating_the_floor_field(self):
        doc = copy.deepcopy(DSS_DOC)
        doc["recommendation"]["best_blocked"] = None
        del doc["recommendation"]["public_safety_floor"]
        recorder = Recorder({("GET", ENTITY): dossier(), ("POST", GENERATE): doc})
        result = await run(recorder)
        assert result["best_blocked"] is None
        assert result["public_safety_floor"] is None  # not reported, never guessed

    async def test_the_decision_homes_include_gods_eye(self):
        recorder = Recorder({("GET", ENTITY): dossier(), ("POST", GENERATE): DSS_DOC})
        result = await run(recorder)
        assert result["home"] == "Decide it in the Inbox (/ or /gods-eye), or in Decisions (/ops)"
        assert "/gods-eye" in server._DSS_HOME


# ── masking at egress, one field at a time ───────────────────────────────────


class TestMasking:
    async def summary(self) -> dict:
        recorder = Recorder({("GET", ENTITY): dossier(), ("POST", GENERATE): DSS_DOC})
        return await run(recorder)

    async def test_a_plate_in_the_dissent_is_masked(self):
        result = await self.summary()
        assert "9001" not in result["dissent"] and "MH.06.EM.•••1" in result["dissent"]

    async def test_a_plate_in_the_advise_gather_why_is_masked(self):
        result = await self.summary()
        why = result["advise_gather_why"]
        assert "4321" not in why and "MH-08-EF-•••1" in why

    async def test_a_plate_in_the_top_coa_label_is_masked(self):
        result = await self.summary()
        assert "1234" not in result["top_coa_label"] and "MH01AB•••4" in result["top_coa_label"]

    async def test_plates_in_the_best_blocked_label_and_missing_are_masked(self):
        result = await self.summary()
        bb = result["best_blocked"]
        assert "5678" not in bb["label"] and "mh05cd•••8" in bb["label"]
        assert "2468" not in bb["missing"][1] and "MH07GH•••8" in bb["missing"][1]

    async def test_no_raw_plate_leaves_the_tool(self):
        egress = json.dumps(await self.summary(), ensure_ascii=False)
        for raw in ("MH01AB1234", "mh05cd5678", "MH-08-EF-4321", "MH.06.EM.9001", "MH07GH2468"):
            assert raw not in egress


# ── a pending proposal is never silently superseded ─────────────────────────


class TestPendingProposal:
    async def test_a_proposed_unexpired_dss_is_read_back_not_regenerated(self):
        pending = dict(copy.deepcopy(DSS_DOC), dss_id=PENDING_ID)
        recorder = Recorder({("GET", ENTITY): dossier(props_dss()), ("GET", GET_PENDING): pending,
                             ("POST", GENERATE): DSS_DOC})
        decider = FakeDecider()
        result = await run(recorder, decider)
        assert recorder.posts() == []  # nothing generated, nothing superseded
        assert decider.calls == []  # and no 27B checkpoint forced
        assert GET_PENDING in recorder.gets()
        assert result["ok"] is True and result["dss_id"] == PENDING_ID
        assert result["state"] == "proposed"
        assert result["reused"] is True
        assert "reused, not regenerated" in result["note"] and PENDING_ID in result["note"]
        assert result["best_blocked"]["coa_id"] == "coa_std"  # the same masked summary
        assert "9001" not in json.dumps(result)

    async def test_an_expired_pending_dss_is_regenerated(self):
        recorder = Recorder({("GET", ENTITY): dossier(props_dss(expires_in_min=-1)),
                             ("POST", GENERATE): DSS_DOC})
        decider = FakeDecider()
        result = await run(recorder, decider)
        assert [p for p, _b in recorder.posts()] == [GENERATE]
        assert GET_PENDING not in recorder.gets()
        assert len(decider.calls) == 1
        assert result["reused"] is False and result["superseded"] is None

    async def test_a_decided_dss_is_regenerated_without_claiming_a_supersede(self):
        decided = dict(copy.deepcopy(DSS_DOC), dss_id=PENDING_ID, state="approved")
        recorder = Recorder({("GET", ENTITY): dossier(props_dss()), ("GET", GET_PENDING): decided,
                             ("POST", GENERATE): DSS_DOC})
        result = await run(recorder)
        assert [p for p, _b in recorder.posts()] == [GENERATE]
        assert result["dss_id"] == NEW_ID and result["reused"] is False
        assert result["superseded"] is None

    async def test_a_pending_dss_the_read_cannot_confirm_is_reported_superseded(self):
        recorder = Recorder({("GET", ENTITY): dossier(props_dss()), ("POST", GENERATE): DSS_DOC})
        result = await run(recorder)  # the GET of the pending proposal answers 404
        assert [p for p, _b in recorder.posts()] == [GENERATE]
        assert result["dss_id"] == NEW_ID
        assert result["superseded"] == PENDING_ID
        assert "superseded" in result["note"]

    async def test_a_proposal_of_another_subject_is_never_reused(self):
        other = dict(copy.deepcopy(DSS_DOC), dss_id=PENDING_ID,
                     event_urn="osint_event:00000000-0000-4000-8000-000000000000")
        recorder = Recorder({("GET", ENTITY): dossier(props_dss()), ("GET", GET_PENDING): other,
                             ("POST", GENERATE): DSS_DOC})
        result = await run(recorder)
        assert [p for p, _b in recorder.posts()] == [GENERATE]
        assert result["reused"] is False
        # not this subject's proposal, so generating cannot supersede it
        assert result["superseded"] is None


# ── the forced 27B checkpoint's per-subject cooldown ─────────────────────────


class TestPriorCooldown:
    def executor(self, recorder: Recorder, decider: FakeDecider, now: list[float]) -> ToolExecutor:
        ex = executor_with(recorder, decider)
        ex._clock = lambda: now[0]
        return ex

    async def test_one_forced_checkpoint_per_subject_inside_the_window(self):
        recorder = Recorder({("GET", ENTITY): dossier(), ("POST", GENERATE): DSS_DOC})
        decider = FakeDecider()
        now = [1000.0]
        ex = self.executor(recorder, decider, now)
        first = await run(recorder, executor=ex)
        now[0] += 30.0
        second = await run(recorder, executor=ex)
        assert len(decider.calls) == 1
        assert decider.calls[0]["force"] is True
        # the same opinion goes with the second generation (the oracle then
        # reuses the identical proposal)
        assert recorder.posts()[0][1] == recorder.posts()[1][1]
        assert recorder.posts()[1][1]["strategy_prior"]["kind"] == "standard"
        assert "reused" in second["ai_pick"] and "per subject" in second["ai_pick"]
        assert "reused" not in first["ai_pick"]
        # past the window the 27B is asked again
        now[0] += server.DSS_PRIOR_COOLDOWN_SEC
        await run(recorder, executor=ex)
        assert len(decider.calls) == 2
        await ex.close()

    async def test_a_changed_situation_inside_the_window_gets_no_stale_opinion(self):
        routes = {("GET", ENTITY): dossier(), ("POST", GENERATE): DSS_DOC}
        recorder = Recorder(routes)
        decider = FakeDecider()
        now = [1000.0]
        ex = self.executor(recorder, decider, now)
        await run(recorder, executor=ex)
        # an official source raised the credibility
        routes[("GET", ENTITY)] = dossier(credibility=0.9)
        now[0] += 10.0
        result = await run(recorder, executor=ex)
        assert len(decider.calls) == 1  # not re-forced
        # and the old opinion is not attached
        assert recorder.posts()[1][1] == {"requested_by": "brain"}
        assert result["strategy_prior"] is None
        assert "situation has changed" in result["ai_pick"]
        await ex.close()

    async def test_a_withheld_opinion_is_not_re_forced_inside_the_window(self):
        recorder = Recorder({("GET", ENTITY): dossier(), ("POST", GENERATE): DSS_DOC})
        decider = FakeDecider()
        decider.result = CheckpointResult(tier="novelty_latched", answers={},
                                          degraded_reason="novel situation: answer withheld")
        now = [1000.0]
        ex = self.executor(recorder, decider, now)
        await run(recorder, executor=ex)
        now[0] += 20.0
        result = await run(recorder, executor=ex)
        assert len(decider.calls) == 1
        assert result["strategy_prior"] is None
        assert "gave no usable opinion" in result["ai_pick"]
        await ex.close()

    async def test_the_cooldown_is_per_subject(self):
        other_id = "4508d86d-566b-438f-8414-b3d67fd7e6e4"
        other_entity = f"/api/v1/city/entity/osint_event/{other_id}"
        other_doc = dict(copy.deepcopy(DSS_DOC), event_urn=f"osint_event:{other_id}")
        recorder = Recorder({
            ("GET", ENTITY): dossier(), ("POST", GENERATE): DSS_DOC,
            ("GET", other_entity): dossier(),
            ("POST", f"/api/v1/decision-support/osint_event:{other_id}/generate"): other_doc,
        })
        decider = FakeDecider()
        ex = self.executor(recorder, decider, [1000.0])
        await ex.execute("city_decision_support", {"event_urn": URN})
        await ex.execute("city_decision_support", {"event_urn": f"osint_event:{other_id}"})
        assert [c["movement_id"] for c in decider.calls] == [
            f"dss:{URN}", f"dss:osint_event:{other_id}"]
        assert set(ex._dss_prior_asked) == {URN, f"osint_event:{other_id}"}  # one window each
        await ex.close()
