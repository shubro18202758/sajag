"""The R2 rail after the DSS tool: the only new POST is compute-only generate.

Pins (plan §5.2 C-U, SPEC §4 human-approval gate):
    allowlist   POST_ALLOWLIST is the unchanged compute set; exactly ONE
                pattern is added — the DSS generate — and it accepts only
                well-formed osint_event:/event: uuid paths (no other kind,
                no traversal, no upper-case, nothing but /generate)
    refusal     _post refuses the officer paths (/decision, /promote, event
                lifecycle, dispatch, e-challan decisions) WITHOUT a request
                leaving the brain
    verbs       FORBIDDEN_TOOL_VERBS is unchanged and matches no tool name
    the tool    city_decision_support posts ONLY to the generate pattern and
                returns a masked summary that decides nothing
"""

from __future__ import annotations

import json
import re
import uuid

import httpx
import pytest

from convoy_brain.decider import CheckpointResult
from convoy_brain.llm.decider_client import DeciderAnswer
from convoy_brain.mcp.server import (
    FORBIDDEN_TOOL_VERBS,
    POST_ALLOWLIST,
    POST_ALLOWLIST_PATTERNS,
    TOOL_DEFINITIONS,
    ToolExecutionError,
    ToolExecutor,
)

OSINT_ID = "1b94e9d2-7e11-4174-a735-7dd3be3189cf"
EVENT_ID = "4508d86d-566b-438f-8414-b3d67fd7e6e4"
GENERATE = f"/api/v1/decision-support/osint_event:{OSINT_ID}/generate"

#: The unchanged compute set (pinned so no later WP widens it silently).
COMPUTE_POSTS = {
    "/api/v1/predict/flow",
    "/api/v1/predict/eta",
    "/api/v1/optimize/routes",
    "/api/v1/optimize/diversions",
    "/api/v1/evaluate/scenarios",
    "/api/v1/traffic/live",
    "/api/v1/simulate/twin",
}


class Recorder:
    """MockTransport handler: routes by (method, path), records every request."""

    def __init__(self, routes: dict[tuple[str, str], object] | None = None) -> None:
        self.routes = routes or {}
        self.seen: list[tuple[str, str, dict, object]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.seen.append((request.method, request.url.path, dict(request.url.params), body))
        handler = self.routes.get((request.method, request.url.path))
        if handler is None:
            return httpx.Response(404, json={"detail": "Not Found"})
        if isinstance(handler, httpx.Response):
            return handler
        return httpx.Response(200, json=handler)

    def posts(self) -> list[tuple[str, object]]:
        return [(path, body) for method, path, _p, body in self.seen if method == "POST"]


def executor_with(recorder: Recorder, decider=None) -> ToolExecutor:
    return ToolExecutor(
        traffic_oracle_url="http://127.0.0.1:8114",
        client=httpx.AsyncClient(base_url="http://127.0.0.1:8114",
                                 transport=httpx.MockTransport(recorder)),
        decider_brain=decider,
    )


class FakeDecider:
    """Scriptable DeciderBrain stand-in (records the checkpoint kwargs)."""

    def __init__(self, result: CheckpointResult | None) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def checkpoint(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def served_answer(value="standard", probability=0.61, confidence=0.83) -> CheckpointResult:
    return CheckpointResult(
        tier="decider",
        answers={"coa_strategy": DeciderAnswer(
            name="coa_strategy", type="choice", value=value,
            probability=probability, confidence=confidence)},
    )


SITUATION_DOSSIER = {
    "entity": {
        "urn": f"osint_event:{OSINT_ID}",
        "kind": "osint_event",
        "label": "Road accident · Salt Lake Bypass",
        "state": "surfaced",
        "source": "osint",
        "props": {
            "event_class": "road_accident",
            "subtype": "collision",
            "sajag_event_kind": "road_accident",
            "toponym": "Salt Lake Bypass",
            "credibility": 0.55,
            "verification_state": "NEWS-REPORTED",
            "summary": "Two cars collided near Sector V; car MH06EM9001 "
                       "blocked the service lane",
            "source_count": 2,
            "cross_type_corroborated": True,
            "second_order": [],
        },
    },
    "related": [],
    "audit": [],
}

DSS_BODY = {
    "dss_id": "9f2c6f30-1e5f-4a3a-9d8e-2f7ab1c33d10",
    "event_urn": f"osint_event:{OSINT_ID}",
    "state": "proposed",
    "coa_set": [
        {"coa_id": "coa-baseline", "kind": "baseline", "label": "Monitor only",
         "resource_feasibility": {"feasible": True, "shortfalls": []},
         "ethics": {"vetoed": False, "veto_reason": None}},
        {"coa_id": "coa-standard", "kind": "standard",
         "label": "Standard response — advisory plus one patrol to Salt Lake Bypass",
         "resource_feasibility": {"feasible": True, "shortfalls": []},
         "ethics": {"vetoed": False, "veto_reason": None}},
        {"coa_id": "coa-closure", "kind": "aggressive",
         "label": "Full closure of Salt Lake Bypass",
         "resource_feasibility": {"feasible": False,
                                  "shortfalls": ["2 patrols required, 1 available"]},
         "ethics": {"vetoed": True,
                    "veto_reason": "blocks the 108 ambulance corridor"}},
    ],
    "recommendation": {
        "ranked_coa_ids": ["coa-standard", "coa-baseline", "coa-closure"],
        "top_coa_id": "coa-standard",
        "value_of_information": {
            "evoi": -0.011, "info_cost": 0.2, "advise_gather": False,
            "why": "acting now dominates: an injured party makes waiting the "
                   "costlier loss",
        },
        "dissent": "The information COA is close behind: credibility 0.55 is "
                   "thin, and one more OFFICIAL source would flip the ranking. "
                   "Re-generate after the second report.",
    },
    "human_gate": {"state": "awaiting_officer", "required_role": "duty_officer"},
    "labels": ["NEWS-REPORTED"],
}


class TestGeneratePattern:
    def test_allowlist_set_is_unchanged_and_one_pattern_was_added(self):
        assert set(POST_ALLOWLIST) == COMPUTE_POSTS
        assert len(POST_ALLOWLIST_PATTERNS) == 1

    def test_pattern_shape_is_compute_only(self):
        assert "/generate$" in POST_ALLOWLIST_PATTERNS[0].pattern
        assert "decision-support" in POST_ALLOWLIST_PATTERNS[0].pattern

    @pytest.mark.parametrize("kind", ["osint_event", "event"])
    def test_accepts_well_formed_generate_paths(self, kind):
        rx = POST_ALLOWLIST_PATTERNS[0]
        assert rx.fullmatch(f"/api/v1/decision-support/{kind}:{uuid.uuid4()}/generate")

    @pytest.mark.parametrize("path", [
        f"/api/v1/decision-support/place:{OSINT_ID}/generate",      # not a subject kind
        f"/api/v1/decision-support/vehicle:{OSINT_ID}/generate",    # not a subject kind
        "/api/v1/decision-support/osint_event:not-a-uuid/generate",
        f"/api/v1/decision-support/osint_event:{OSINT_ID.upper()}/generate",
        f"/api/v1/decision-support/osint_event:{OSINT_ID}/decision",
        f"/api/v1/decision-support/osint_event:{OSINT_ID}/generate/extra",
        f"/api/v1/decision-support/osint_event:{OSINT_ID[:-1]}/generate",
        f"/api/v1/decision-support/osint_event:{OSINT_ID}0/generate",
        f"/api/v1/decision-support/osint_event:{OSINT_ID}/../decision",
        f"/api/v1/decision-support/osint_event:../../admin/generate",
        f"/api/v1/osint/events/{OSINT_ID}/promote",
        "//api/v1/decision-support/osint_event:x/generate",
    ])
    def test_refuses_malformed_and_officer_paths(self, path):
        assert POST_ALLOWLIST_PATTERNS[0].fullmatch(path) is None


class TestOfficerPathsUnreachable:
    @pytest.mark.parametrize("path", [
        f"/api/v1/decision-support/{uuid.uuid4()}/decision",
        f"/api/v1/decision-support/osint_event:{OSINT_ID}/decision",
        f"/api/v1/decision-support/event:{EVENT_ID}/decision",
        f"/api/v1/osint/events/{OSINT_ID}/promote",
        f"/api/v1/events/{EVENT_ID}/status",
        "/api/v1/dispatches",
        "/api/v1/enforcement/recommendations/x/decision",
        f"/api/v1/decision-support/osint_event:{OSINT_ID}/generate/x",
    ])
    async def test_refused_without_a_request(self, path):
        recorder = Recorder()
        executor = executor_with(recorder)
        await executor._ensure_client()
        with pytest.raises(ToolExecutionError) as exc:
            await executor._post(path, {"whatever": True})
        assert exc.value.retryable is False
        assert recorder.seen == []
        await executor.close()


class TestForbiddenVerbs:
    def test_forbidden_verbs_are_unchanged(self):
        assert FORBIDDEN_TOOL_VERBS.pattern == (
            "approve|decide|earmark|dispatch_request|withdraw|transition")
        assert FORBIDDEN_TOOL_VERBS.flags & re.IGNORECASE

    def test_no_tool_name_carries_a_forbidden_verb(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert [n for n in names if FORBIDDEN_TOOL_VERBS.search(n)] == []
        assert len(names) == 29


class TestCityDecisionSupportTool:
    def tool_def(self) -> dict:
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "city_decision_support")
        assert "event_urn" in tool["inputSchema"]["required"]
        return tool

    async def test_posts_only_to_the_generate_pattern_and_masks_egress(self):
        recorder = Recorder({
            ("GET", f"/api/v1/city/entity/osint_event/{OSINT_ID}"): SITUATION_DOSSIER,
            ("POST", GENERATE): DSS_BODY,
        })
        decider = FakeDecider(served_answer())
        executor = executor_with(recorder, decider=decider)
        result = await executor.execute("city_decision_support",
                                        {"event_urn": f"osint_event:{OSINT_ID}"})
        # the situation is read, then exactly one POST — to the pattern, with
        # the decider's prior and the brain's requested_by
        posts = recorder.posts()
        assert len(posts) == 1
        path, body = posts[0]
        assert POST_ALLOWLIST_PATTERNS[0].fullmatch(path) is not None
        assert body == {
            "strategy_prior": {"kind": "standard", "probability": 0.61,
                               "confidence": 0.83, "tier": "decider_27b"},
            "requested_by": "brain",
        }
        assert decider.calls[0]["movement_id"] == f"dss:osint_event:{OSINT_ID}"
        assert decider.calls[0]["force"] is True
        # the summary decides nothing and carries the honest label
        assert result["ok"] is True
        assert result["dss_id"] == DSS_BODY["dss_id"]
        assert result["state"] == "proposed"
        assert result["verification_state"] == "NEWS-REPORTED"
        assert result["top_coa_label"].startswith("Standard response")
        assert result["ranking"] == ["coa-standard", "coa-baseline", "coa-closure"]
        assert result["advise_gather"] is False
        assert result["advise_gather_why"].startswith("acting now dominates")
        assert result["dissent"] == (
            "The information COA is close behind: credibility 0.55 is thin, "
            "and one more OFFICIAL source would flip the ranking.")
        assert result["home"] == "Decide it in the Inbox (/ or /gods-eye), or in Decisions (/ops)"
        assert any("vetoed" in n for n in result["feasibility_notes"])
        assert any("resource-infeasible" in n for n in result["feasibility_notes"])
        # plates in any oracle text are masked at egress
        egress = json.dumps(result, ensure_ascii=False)
        assert "MH06EM9001" not in egress
        assert "MH06EM•••1" in egress
        await executor.close()

    async def test_without_a_decider_the_prior_is_omitted_and_said_so(self):
        recorder = Recorder({
            ("GET", f"/api/v1/city/entity/osint_event/{OSINT_ID}"): SITUATION_DOSSIER,
            ("POST", GENERATE): DSS_BODY,
        })
        executor = executor_with(recorder, decider=None)
        result = await executor.execute("city_decision_support",
                                        {"event_urn": f"osint_event:{OSINT_ID}"})
        assert recorder.posts()[0][1] == {"requested_by": "brain"}
        assert result["strategy_prior"] is None
        assert "not computed" in result["ai_pick"]
        await executor.close()

    async def test_a_withheld_answer_ships_no_prior(self):
        recorder = Recorder({
            ("GET", f"/api/v1/city/entity/osint_event/{OSINT_ID}"): SITUATION_DOSSIER,
            ("POST", GENERATE): DSS_BODY,
        })
        latched = CheckpointResult(
            tier="novelty_latched",
            answers={"coa_strategy": DeciderAnswer(
                name="coa_strategy", type="choice", value="aggressive",
                probability=0.9, confidence=0.9)},
            degraded_reason="novel situation: confident answer withheld",
        )
        executor = executor_with(recorder, decider=FakeDecider(latched))
        result = await executor.execute("city_decision_support",
                                        {"event_urn": f"osint_event:{OSINT_ID}"})
        assert recorder.posts()[0][1] == {"requested_by": "brain"}
        assert result["strategy_prior"] is None
        await executor.close()

    async def test_unknown_event_answers_not_found(self):
        recorder = Recorder({
            ("GET", f"/api/v1/city/entity/osint_event/{OSINT_ID}"):
                httpx.Response(404, json={"detail": f"osint_event:{OSINT_ID} not found"}),
        })
        executor = executor_with(recorder, decider=FakeDecider(served_answer()))
        result = await executor.execute("city_decision_support",
                                        {"event_urn": f"osint_event:{OSINT_ID}"})
        assert result["ok"] is False and result["not_found"] is True
        assert recorder.posts() == []
        await executor.close()

    async def test_event_closed_answers_typed_not_found_style(self):
        recorder = Recorder({
            ("GET", f"/api/v1/city/entity/osint_event/{OSINT_ID}"): SITUATION_DOSSIER,
            ("POST", GENERATE): httpx.Response(409, json={"detail": "event-closed"}),
        })
        executor = executor_with(recorder)
        result = await executor.execute("city_decision_support",
                                        {"event_urn": f"osint_event:{OSINT_ID}"})
        assert result["ok"] is False and result["event_closed"] is True
        await executor.close()

    async def test_malformed_urn_never_reaches_http(self):
        recorder = Recorder()
        executor = executor_with(recorder)
        for bad in (f"place:sg_highway", f"vehicle:{OSINT_ID}", "osint_event:x",
                    "nonsense", "", None, f"osint_event:../{OSINT_ID}"):
            with pytest.raises(ToolExecutionError) as exc:
                await executor.execute("city_decision_support", {"event_urn": bad})
            assert exc.value.retryable is False
        assert recorder.seen == []
        await executor.close()

    def test_the_description_says_read_compute_only_and_officer_decides(self):
        text = self.tool_def()["description"]
        assert "Read/compute only" in text
        assert "duty officer" in text
