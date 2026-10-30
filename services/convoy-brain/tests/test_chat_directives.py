"""Agentic God's-eye over the chat stream (wave 3, contract C-D2).

What this suite pins, over the real FastAPI routes and the deck's wire form:
    directive   'show me the stolen vehicle on the map' streams a directive
                line {id, verb, args, label, provenance{session_id, tier,
                confidence, tool_call_id}} with a vehicle URN — the stolen
                one — before the done line, whatever tool the decider picks:
                a deterministic grounding lookup resolves the kind named and a
                post-step proposes the camera move (tier 'heuristic')
    tiers       a canvas verb the strategic tier chose streams with tier
                'decider' and its pick confidence; a mis-copied uuid is
                snapped to the entity the turn resolved; no duplicate move
    citations   done.citations lists the URNs the tool results named
                (plate-masked labels)
    ack         POST /chat/directives/ack records the human's answer (applied /
                dismissed) in the bound movement's decisions_log; repeats 409,
                unknowns 404, another session's 422; a loopback x-sajag-officer
                wins over the body officer, which is kept as claimed_officer
    grounding   event_id puts 'Selected corridor event: …' in the session and
                scopes the event tools; context_urn resolves the dossier; both
                are in the session-reuse key
    rescue      a final answer cut before its JSON closed keeps its complete
                reasoning (tier gemma_final_rescued), never the heuristic floor
"""

from __future__ import annotations

import json

import pytest
from conftest import FakeContextStore, FakeExecutor
from test_orchestrator import FINAL_OK, ScriptBridge, ScriptDecider

from convoy_brain import __main__ as brain_main
from convoy_brain.decider import DeciderBrain
from convoy_brain.memory.convoy_context import ConvoyContext
from convoy_brain.orchestrator import (
    SIMULATED_FEED_NOTE,
    Orchestrator,
    _clip_words,
    _near_miss,
    _scrub_unverifiable,
    _simulated_source,
)

STOLEN = "1b94e9d2-7e11-4174-a735-7dd3be3189cf"
OTHER = "2b94e9d2-7e11-4174-a735-7dd3be3189cf"
PURSUIT = "4508d86d-566b-438f-8414-b3d67fd7e6e4"

VEHICLES = {
    "count": 2, "total": 2, "entities": [
        {"urn": f"vehicle:{OTHER}", "kind": "vehicle", "label": "MH01AB•••4",
         "state": "pending_fine",
         "source": "live", "lon": 72.88, "lat": 19.03, "props": {"earmark_state": "pending_fine"}},
        {"urn": f"vehicle:{STOLEN}", "kind": "vehicle", "label": "MH06EM•••1", "state": "flagged",
         "source": "emulated", "lon": 72.875356, "lat": 19.02503,
         "props": {"earmark_state": "flagged", "lawful_basis": "stolen_vehicle_fir"}},
    ],
}
EVENTS = {"events": [{
    "urn": f"event:{PURSUIT}", "event_id": PURSUIT, "event_kind": "vehicle_pursuit",
    "status": "planning", "title": "PURSUIT — stolen MH06EM•••1 (FIR 4401/2026)",
    "routes": [{"label": "Howrah Bridge sweep belt", "segment_ids": [1001, 1008, 1009]}],
    "phases": [], "vehicle_urn": f"vehicle:{STOLEN}", "vehicle_label": "vehicle MH06EM•••1",
}], "count": 1, "total_active": 1}


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("MODEL_HOST_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("LLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("TRAFFIC_ORACLE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("EMBEDDING_SERVICE_URL", "http://127.0.0.1:1")
    monkeypatch.setattr(brain_main, "ConvoyContextStore", lambda valkey_url: FakeContextStore())
    return brain_main.create_app()


def wire(app, bridge, executor, decider):
    store = app.state.context_store
    app.state.orchestrator = Orchestrator(
        bridge, executor, store, decider_brain=DeciderBrain(decider, min_interval_sec=0)
    )
    return store


def stream(client, body: dict) -> list[dict]:
    with client.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        lines = [line for line in response.iter_lines() if line.strip()]
    assert all(line.startswith('{"type":"') for line in lines)
    return [json.loads(line) for line in lines]


def directives(events: list[dict]) -> list[dict]:
    return [e["data"] for e in events if e["type"] == "directive"]


class TestMapDirective:
    def test_stolen_vehicle_directive_whatever_the_decider_picks(self, app):
        from starlette.testclient import TestClient

        with TestClient(app) as client:
            executor = FakeExecutor(routes={"city_query_entities": VEHICLES})
            wire(app, ScriptBridge(replies=[json.dumps(FINAL_OK)]), executor,
                 ScriptDecider("final_answer"))
            events = stream(client, {"message": "show me the stolen vehicle on the map"})

        kinds = [e["type"] for e in events]
        assert kinds[-1] == "done" and "directive" in kinds
        assert kinds.index("tool_result") < kinds.index("directive") < kinds.index("done")
        # the grounding lookup ran first, read-only, on the kind the message named
        assert executor.calls[0] == ("city_query_entities", {"kinds": ["vehicle"], "limit": 20})
        [move] = directives(events)
        assert move["verb"] in ("canvas_track_entity", "canvas_fly_to")
        assert move["args"]["urn"] == f"vehicle:{STOLEN}"  # 'stolen' outranks the other car
        assert move["id"].startswith("dir_") and move["label"] == "track MH06EM•••1"
        prov = move["provenance"]
        assert prov["session_id"] == events[-1]["data"]["session_id"]
        assert prov["tier"] == "heuristic" and prov["confidence"] is None
        assert prov["tool_call_id"] == "call_1_city_query_entities"
        citations = events[-1]["data"]["citations"]
        assert citations[0] == {"urn": f"vehicle:{STOLEN}", "label": "MH06EM•••1"}
        assert "MH06EM9001" not in json.dumps(events)

    def test_a_typed_plate_is_matched_not_ranked(self, app):
        from starlette.testclient import TestClient

        matched = {"count": 1, "total": 1, "match": "MH01AB1234",
                   "entities": [VEHICLES["entities"][0]]}
        with TestClient(app) as client:
            executor = FakeExecutor(routes={"city_query_entities": matched})
            wire(app, ScriptBridge(replies=[json.dumps(FINAL_OK)]), executor,
                 ScriptDecider("final_answer"))
            events = stream(client, {"message": "where is mh 01 ab 1234?"})
        assert executor.calls[0][1]["match"] == "MH01AB1234"
        assert directives(events)[0]["args"]["urn"] == f"vehicle:{OTHER}"

    def test_a_decider_chosen_canvas_verb_keeps_its_tier_and_is_not_duplicated(self, app):
        from starlette.testclient import TestClient

        from convoy_brain.mcp.server import canvas_directive

        mis_copied = "vehicle:1b94e92-7e11-4174-a735-7dd3be3189cf"  # live: a dropped 'd'
        with TestClient(app) as client:
            executor = FakeExecutor(routes={
                "city_query_entities": VEHICLES,
                "canvas_track_entity": lambda args: canvas_directive("canvas_track_entity", args),
            })
            wire(app, ScriptBridge(replies=[
                json.dumps({"arguments": {"urn": mis_copied}}),
                json.dumps(FINAL_OK),
            ]), executor, ScriptDecider(["canvas_track_entity", "final_answer"]))
            events = stream(client, {"message": "track the stolen vehicle"})
        moves = directives(events)
        assert len(moves) == 1
        assert moves[0]["args"]["urn"] == f"vehicle:{STOLEN}"
        [card] = [e["data"] for e in events
                  if e["type"] == "tool_result" and e["data"].get("name") == "canvas_track_entity"]
        assert "track MH06EM•••1" in card["summary"] and STOLEN not in card["summary"]
        assert moves[0]["provenance"]["tier"] == "decider"
        assert moves[0]["provenance"]["confidence"] == 0.9
        assert any("names no resolved entity" in e["data"]["text"]
                   for e in events if e["type"] == "thought")
        assert executor.calls[-1] == ("canvas_track_entity", {"urn": f"vehicle:{STOLEN}"})

    def test_a_well_formed_unlisted_urn_is_never_swapped(self, app):
        # A real vehicle this turn's lookup did not list is not a typo of the
        # stolen one: the drafted URN stands (the deck resolves it or drops it).
        from starlette.testclient import TestClient

        from convoy_brain.mcp.server import canvas_directive

        unlisted = "vehicle:9c0d7a4e-1f2b-4c3d-8e9f-0a1b2c3d4e5f"
        with TestClient(app) as client:
            executor = FakeExecutor(routes={
                "city_query_entities": VEHICLES,
                "canvas_track_entity": lambda args: canvas_directive("canvas_track_entity", args),
            })
            wire(app, ScriptBridge(replies=[
                json.dumps({"arguments": {"urn": unlisted}}),
                json.dumps(FINAL_OK),
            ]), executor, ScriptDecider(["canvas_track_entity", "final_answer"]))
            events = stream(client, {"message": "track that vehicle"})
        assert executor.calls[-1] == ("canvas_track_entity", {"urn": unlisted})
        assert [m["args"]["urn"] for m in directives(events)] == [unlisted]
        assert not any("names no resolved entity" in e["data"]["text"]
                       for e in events if e["type"] == "thought")

    def test_only_a_near_miss_is_snapped(self):
        stolen, other = f"vehicle:{STOLEN}", f"vehicle:{OTHER}"
        # one dropped character of the stolen car's uuid: that car
        assert _near_miss("vehicle:1b94e92-7e11-4174-a735-7dd3be3189cf", [other, stolen]) == stolen
        # a truncated uuid is no near miss of anything
        assert _near_miss("vehicle:1b94e9d2", [other, stolen]) is None
        # equally near two entities: not a typo of either
        assert _near_miss("vehicle:0b94e9d2-7e11-4174-a735-7dd3be3189cf", [other, stolen]) is None

    def test_no_map_intent_no_directive(self, app):
        from starlette.testclient import TestClient

        with TestClient(app) as client:
            executor = FakeExecutor(routes={"city_query_entities": VEHICLES})
            wire(app, ScriptBridge(replies=[
                json.dumps({"arguments": {"kinds": ["vehicle"]}}), json.dumps(FINAL_OK),
            ]), executor, ScriptDecider(["city_query_entities", "final_answer"]))
            events = stream(client, {"message": "how many earmarked vehicles are there?"})
        assert directives(events) == []
        assert events[-1]["data"]["citations"]  # the tool still named them


class TestDirectiveAck:
    def issue(self, app, client, movement_id=None):
        store = wire(app, ScriptBridge(replies=[json.dumps(FINAL_OK)]),
                     FakeExecutor(routes={"city_query_entities": VEHICLES}),
                     ScriptDecider("final_answer"))
        body = {"message": "show me the stolen vehicle on the map"}
        if movement_id:
            body["movement_id"] = movement_id
        events = stream(client, body)
        return store, directives(events)[0], events[-1]["data"]["session_id"]

    def test_applied_is_audited_into_the_movement(self, app):
        from starlette.testclient import TestClient

        with TestClient(app, base_url="http://127.0.0.1") as client:
            app.state.context_store.contexts["m-1"] = ConvoyContext(
                movement_id="m-1", vvip_class="Z")
            store, move, session = self.issue(app, client, movement_id="m-1")
            ack = client.post("/chat/directives/ack", json={
                "session_id": session, "directive_id": move["id"], "decision": "applied",
                "officer": "Typed Name",
            }, headers={"x-sajag-officer": "Duty%20Officer%20%E0%A6%B0%E0%A6%BE%E0%A6%9C"})
            assert ack.status_code == 200, ack.text
            assert ack.json()["officer"] == "Duty Officer রাজ"
            assert ack.json()["recorded_in"] == "decisions_log"
            row = next(d for d in store.contexts["m-1"].decisions_log
                       if d.get("phase") == "canvas_directive")
            assert row["action"] == "directive_applied" and row["verb"] == move["verb"]
            assert row["officer"] == "Duty Officer রাজ" and row["claimed_officer"] == "Typed Name"
            assert row["tier"] == "heuristic"
            again = client.post("/chat/directives/ack", json={
                "session_id": session, "directive_id": move["id"], "decision": "dismissed"})
            assert again.status_code == 409 and again.json()["decision"] == "applied"

    def test_unknown_foreign_and_malformed_acks(self, app):
        from starlette.testclient import TestClient

        with TestClient(app, base_url="http://127.0.0.1") as client:
            _store, move, session = self.issue(app, client)
            assert client.post("/chat/directives/ack", json={
                "session_id": session, "directive_id": "dir_nope", "decision": "applied",
            }).status_code == 404
            assert client.post("/chat/directives/ack", json={
                "session_id": "another", "directive_id": move["id"], "decision": "applied",
            }).status_code == 422
            assert client.post("/chat/directives/ack", json={
                "session_id": session, "directive_id": move["id"], "decision": "auto",
            }).status_code == 422
            bidi = client.post("/chat/directives/ack", json={
                "session_id": session, "directive_id": move["id"], "decision": "dismissed",
            }, headers={"x-sajag-officer": "Officer%E2%80%AEA"})
            assert bidi.status_code == 422
            ok = client.post("/chat/directives/ack", json={
                "session_id": session, "directive_id": move["id"], "decision": "dismissed",
            })
            assert ok.status_code == 200 and ok.json()["recorded_in"] == "brain log"


class TestSelectionGrounding:
    async def test_event_id_is_stated_and_scopes_the_event_tools(self, fake_store):
        executor = FakeExecutor(routes={"get_active_corridor_events": EVENTS})
        bridge = ScriptBridge(replies=[
            json.dumps({"arguments": {"event_kind": "protected_movement"}}),
            json.dumps(FINAL_OK),
        ])
        orch = Orchestrator(bridge, executor, fake_store, decider_brain=DeciderBrain(
            ScriptDecider(["get_active_corridor_events", "final_answer"]), min_interval_sec=0))
        state = await orch.open_session(event_id=PURSUIT.upper())
        assert state.event_id == PURSUIT
        assert (f"Selected corridor event: {PURSUIT} (vehicle_pursuit, planning, PURSUIT — stolen "
                "MH06EM•••1 (FIR 4401/2026)), spines Howrah Bridge sweep belt: 1001, 1008, 1009"
                ) in state.system_prompt
        await orch.process_turn(state.session_id, "status of corridor")
        # the session resolve, then the turn's call: scoped to the selection,
        # and the drafted kind filter that would have hidden it dropped
        assert executor.calls[0] == ("get_active_corridor_events", {"event_id": PURSUIT})
        assert executor.calls[1] == ("get_active_corridor_events", {"event_id": PURSUIT})

    async def test_a_question_about_all_events_keeps_the_whole_board(self, fake_store):
        executor = FakeExecutor(routes={"get_active_corridor_events": EVENTS})
        bridge = ScriptBridge(replies=[json.dumps({"arguments": {}}), json.dumps(FINAL_OK)])
        orch = Orchestrator(bridge, executor, fake_store, decider_brain=DeciderBrain(
            ScriptDecider(["get_active_corridor_events", "final_answer"]), min_interval_sec=0))
        state = await orch.open_session(event_id=PURSUIT)
        await orch.process_turn(state.session_id, "which events are active?")
        assert executor.calls[-1] == ("get_active_corridor_events", {})

    async def test_the_linked_vehicle_is_cited_by_its_masked_plate(self, fake_store):
        """A citation chip reads 'vehicle MH06EM•••1', not the vehicle's uuid."""
        executor = FakeExecutor(routes={"get_active_corridor_events": EVENTS})
        # cited because the answer names it (HON-13: no padding with entities
        # the answer is not about)
        answer = dict(FINAL_OK, reasoning="The pursuit of vehicle MH06EM•••1 is planning.")
        bridge = ScriptBridge(replies=[json.dumps({"arguments": {}}), json.dumps(answer)])
        orch = Orchestrator(bridge, executor, fake_store, decider_brain=DeciderBrain(
            ScriptDecider(["get_active_corridor_events", "final_answer"]), min_interval_sec=0))
        state = await orch.open_session(event_id=PURSUIT)
        result = await orch.process_turn(state.session_id, "status of corridor")
        labels = {c["urn"]: c["label"] for c in result["citations"]}
        assert labels[f"vehicle:{STOLEN}"] == "vehicle MH06EM•••1"
        assert all(label != urn for urn, label in labels.items())

    async def test_context_urn_resolves_the_dossier(self, fake_store):
        dossier = {"entity": VEHICLES["entities"][1], "related": [
            {"relation": "pursuit", "urn": f"event:{PURSUIT}", "kind": "event",
             "label": "PURSUIT — stolen MH06EM•••1", "state": "planning"}],
            "audit": [{"actor": "EM-CAM-02", "text": "ANPR hit · STOLEN VEHICLE · MH06EM•••1"}]}
        executor = FakeExecutor(routes={"city_get_dossier": dossier})
        bridge = ScriptBridge(replies=[json.dumps(FINAL_OK)])
        orch = Orchestrator(bridge, executor, fake_store, decider_brain=DeciderBrain(
            ScriptDecider("final_answer"), min_interval_sec=0))
        state = await orch.open_session(context_urn=f"vehicle:{STOLEN}")
        assert executor.calls == [("city_get_dossier", {"urn": f"vehicle:{STOLEN}"})]
        assert f"Context entity (the operator is asking about it): vehicle:{STOLEN} — MH06EM•••1" \
            in state.system_prompt
        assert "lawful_basis stolen_vehicle_fir" in state.system_prompt
        result = await orch.process_turn(state.session_id, "Explain this")
        assert result["citations"][0]["urn"] == f"vehicle:{STOLEN}"

    async def test_event_and_context_are_part_of_the_reuse_key(self, fake_store):
        executor = FakeExecutor(routes={"get_active_corridor_events": EVENTS,
                                        "city_get_dossier": {"entity": None}})
        orch = Orchestrator(ScriptBridge(), executor, fake_store, decider_brain=None)
        first = await orch.open_session(session_id="s-a", event_id=PURSUIT)
        assert (await orch.open_session(session_id="s-a")).session_id == "s-a"
        assert (await orch.open_session(session_id="s-a", event_id=PURSUIT)).session_id == "s-a"
        other = await orch.open_session(session_id="s-a", event_id=STOLEN)
        assert other.session_id != first.session_id and other.event_id == STOLEN
        ctx = await orch.open_session(session_id=other.session_id, context_urn="junction:3")
        assert ctx.session_id != other.session_id and ctx.context_urn == "junction:3"


class TestFinalAnswerRescue:
    async def test_a_cut_reply_keeps_its_complete_reasoning(self, fake_store):
        cut = ('{"action": "status_report", "reasoning": "The pursuit PURSUIT — stolen '
               'MH06EM•••1 is planning; its sweep belt covers segments 1001, 1008 and 1009.", '
               '"tool_calls_made": ["get_active_corridor_e')
        # the answer stands on a tool result (the grounding check removes
        # what no source reported: here the board names the pursuit, its
        # vehicle and its spine)
        orch = Orchestrator(ScriptBridge(replies=[json.dumps({"arguments": {}}), cut]),
                            FakeExecutor(routes={"get_active_corridor_events": EVENTS}),
                            fake_store,
                            decider_brain=DeciderBrain(
                                ScriptDecider(["get_active_corridor_events", "final_answer"]),
                                min_interval_sec=0))
        await orch.create_session("s1")
        result = await orch.process_turn("s1", "status?")
        assert result["action"] == "status_report"
        assert result["reasoning"].startswith("The pursuit PURSUIT — stolen MH06EM•••1 is planning")
        assert "gemma_final_rescued" in result["tiers_used"]
        assert "gemma_final_rescued" in result["tiers"]
        assert "could not compose" not in result["reasoning"]

    async def test_a_reply_without_a_closed_reasoning_falls_to_the_floor(self, fake_store):
        orch = Orchestrator(ScriptBridge(replies=['{"action": "x", "reasoning": "half a sen']),
                            FakeExecutor(), fake_store,
                            decider_brain=DeciderBrain(ScriptDecider("final_answer"),
                                                       min_interval_sec=0))
        await orch.create_session("s1")
        result = await orch.process_turn("s1", "status?")
        assert result["action"] == "degraded_text_response"

    async def test_data_is_optional_and_defaulted(self, fake_store):
        from convoy_brain.llm.schemas import load_schema

        schema = load_schema("orchestrator_final")
        assert "data" not in schema["required"] and "data" not in schema["properties"]
        assert list(schema["properties"])[:2] == ["action", "reasoning"]
        assert schema["properties"]["reasoning"]["maxLength"] == 1200
        assert schema["properties"]["tool_calls_made"]["maxItems"] == 8
        pa = schema["properties"]["protocol_assessment"]["properties"]
        assert pa["protocol_violations"]["maxItems"] == 8
        reply = {k: v for k, v in FINAL_OK.items() if k != "data"}
        orch = Orchestrator(ScriptBridge(replies=[json.dumps(reply)]), FakeExecutor(), fake_store,
                            decider_brain=DeciderBrain(ScriptDecider("final_answer"),
                                                       min_interval_sec=0))
        await orch.create_session("s1")
        assert (await orch.process_turn("s1", "status?"))["data"] == {}

    async def test_a_figure_free_answer_is_grounded_in_the_tool_data(self, fake_store):
        live = {"observations": [{"segment_id": 1012, "congestion_idx": 0.62, "speed_kmh": 21.0,
                                  "road_name": "Sahid Khudiram Bose Road"}]}
        bridge = ScriptBridge(replies=[
            json.dumps({"arguments": {"segment_ids": [1012]}}),
            json.dumps(dict(FINAL_OK, reasoning="Traffic is moving normally on the corridor.")),
        ])
        orch = Orchestrator(bridge, FakeExecutor(routes={"get_live_traffic": live}), fake_store,
                            decider_brain=DeciderBrain(
                                ScriptDecider(["get_live_traffic", "final_answer"]),
                                min_interval_sec=0))
        await orch.create_session("s1")
        result = await orch.process_turn("s1", "live traffic on segment 1012")
        assert "(Data: get_live_traffic: 1 observation(s)" in result["reasoning"]
        assert "Sahid Khudiram Bose Road (1012) at 0.62" in result["reasoning"]

    async def test_a_plate_the_model_writes_is_masked(self, fake_store):
        """Live repeat run 4: Gemma joined 'MH06EM' and the FIR year into
        'MH06EM-2026' — whatever the model writes, a plate leaves masked."""
        reply = dict(FINAL_OK, reasoning="The pursuit is planning; the plate is MH06EM-2026.")
        orch = Orchestrator(ScriptBridge(replies=[json.dumps(reply)]), FakeExecutor(), fake_store,
                            decider_brain=DeciderBrain(ScriptDecider("final_answer"),
                                                       min_interval_sec=0))
        await orch.create_session("s1")
        result = await orch.process_turn("s1", "status?")
        assert "MH06EM-2026" not in result["reasoning"]
        assert "MH06EM-•••6" in result["reasoning"]

    def test_a_long_summary_is_cut_between_words_never_inside_a_figure(self):
        summary = ("get_active_corridor_events: vehicle pursuit 'PURSUIT — stolen MH06EM•••1 "
                   "(FIR 4401/2026, Hare Street PS)' — status planning; spine(s) Howrah Bridge "
                   "sweep belt: segments 1001, 1008, 1009, 1010")
        limit = summary.index("1001") + 2  # the cap falls inside '1001'
        clipped = _clip_words(summary, limit)
        assert clipped.endswith("segments …") and len(clipped) <= limit + 2
        assert _clip_words("short", 190) == "short"

    async def test_an_answer_from_a_simulated_feed_says_so(self, fake_store):
        """predict_traffic_flow on the synthetic feed: Gemma's prose left the
        label out (live repeat run 4) — the answer must still say it."""
        forecast = {"predictions": {"1012": {"30": {"speed_kmh": 46.1, "congestion_idx": 0.07}}},
                    "provenance": {"rung": "foundation", "simulated_feed": True,
                                   "input_quality": {"synthetic": 1}}}
        bridge = ScriptBridge(replies=[
            json.dumps({"arguments": {"segment_ids": [1012]}}),
            json.dumps(dict(FINAL_OK, reasoning="Segment 1012 shows congestion 0.07 at T+30.")),
        ])
        orch = Orchestrator(bridge, FakeExecutor(routes={"predict_traffic_flow": forecast}),
                            fake_store, decider_brain=DeciderBrain(
                                ScriptDecider(["predict_traffic_flow", "final_answer"]),
                                min_interval_sec=0))
        await orch.create_session("s1")
        result = await orch.process_turn("s1", "forecast for segment 1012")
        assert result["reasoning"].startswith("Segment 1012 shows congestion 0.07 at T+30.")
        assert result["reasoning"].endswith(SIMULATED_FEED_NOTE)

    async def test_a_real_feed_or_a_labelled_answer_is_left_alone(self, fake_store):
        real = {"entries": [{"band": "GREEN", "emulated": False, "t": "2026-10-22T22:25:45Z"}]}
        said = "Band GREEN for 12 rows; the vehicle feed is EMULATED."
        for payload, prose in ((real, "Band GREEN for 12 rows."),
                               ({"entities": [{"source": "emulated"}]}, said)):
            bridge = ScriptBridge(replies=[json.dumps({"arguments": {}}),
                                           json.dumps(dict(FINAL_OK, reasoning=prose))])
            orch = Orchestrator(bridge, FakeExecutor(routes={"get_situation_log": payload}),
                                fake_store, decider_brain=DeciderBrain(
                                    ScriptDecider(["get_situation_log", "final_answer"]),
                                    min_interval_sec=0))
            await orch.create_session("s1")
            result = await orch.process_turn("s1", "situation log")
            assert result["reasoning"] == prose  # no second label, nothing appended

    def test_raw_coordinates_read_as_the_map_position(self):
        # live stolen-vehicle answer: "It was last seen at 19.02503, 72.875356."
        assert _scrub_unverifiable("It was last seen at 19.02503, 72.875356.") == (
            "It was last seen at the position shown on the map.")
        assert _scrub_unverifiable("Parked at coordinates (72.8754, 19.0250) now.") == (
            "Parked at the position shown on the map now.")
        # congestion values, speeds and segment ids are not coordinates
        kept = "Congestion 0.142, 0.213 on segments 1004, 1005 at 22.5 km/h."
        assert _scrub_unverifiable(kept) == kept

    async def test_a_not_emulated_claim_is_dropped_and_the_label_kept(self, fake_store):
        # live status run 5 ended "The data is not emulated." on the synthetic
        # feed: the claim goes, and it can no longer suppress the label
        forecast = {"predictions": {"1012": {"30": {"speed_kmh": 46.1, "congestion_idx": 0.07}}},
                    "provenance": {"simulated_feed": True}}
        prose = "Segment 1012 shows congestion 0.07 at T+30. The data is not emulated."
        bridge = ScriptBridge(replies=[
            json.dumps({"arguments": {"segment_ids": [1012]}}),
            json.dumps(dict(FINAL_OK, reasoning=prose)),
        ])
        orch = Orchestrator(bridge, FakeExecutor(routes={"predict_traffic_flow": forecast}),
                            fake_store, decider_brain=DeciderBrain(
                                ScriptDecider(["predict_traffic_flow", "final_answer"]),
                                min_interval_sec=0))
        await orch.create_session("s1")
        result = await orch.process_turn("s1", "forecast for segment 1012")
        assert "not emulated" not in result["reasoning"]
        assert result["reasoning"] == (
            "Segment 1012 shows congestion 0.07 at T+30. " + SIMULATED_FEED_NOTE)
        for claim in ("These readings aren't simulated.", "It is non-synthetic data.",
                      "This is not a simulated feed."):
            scrubbed = _scrub_unverifiable(f"Band GREEN on 12 rows. {claim}")
            assert scrubbed == "Band GREEN on 12 rows."

    async def test_an_event_called_active_carries_its_reported_status(self, fake_store):
        # 'Explain this' (live, twice): "there is an active pursuit" for a
        # pursuit the tools report as planning
        prose = ("The pursuit covers segments 1001 and 1008; there is an active pursuit of "
                 "the vehicle. No active events block the corridor.")
        bridge = ScriptBridge(replies=[json.dumps({"arguments": {}}),
                                       json.dumps(dict(FINAL_OK, reasoning=prose))])
        orch = Orchestrator(bridge, FakeExecutor(routes={"get_active_corridor_events": EVENTS}),
                            fake_store, decider_brain=DeciderBrain(
                                ScriptDecider(["get_active_corridor_events", "final_answer"]),
                                min_interval_sec=0))
        await orch.create_session("s1")
        result = await orch.process_turn("s1", "what is happening with this vehicle?")
        assert "there is a pursuit (status planning) of the vehicle" in result["reasoning"]
        assert "No active events block the corridor." in result["reasoning"]  # true: kept

    def test_simulated_markers(self):
        assert _simulated_source({"observations": [{"data_quality": "synthetic"}]})
        assert _simulated_source({"units": [{"source": "emulated"}]})
        assert _simulated_source({"provenance": "synthetic", "aggregates": []})
        assert _simulated_source({"provenance": {"input_quality": {"synthetic": 4, "real": 0}}})
        assert not _simulated_source({"provenance": {"input_quality": {"synthetic": 0}}})
        assert not _simulated_source({"entries": [{"emulated": False}], "source": "live"})

    async def test_the_floor_answer_from_a_simulated_feed_says_so(self, fake_store):
        forecast = {"predictions": {"1012": {"30": {"speed_kmh": 46.1, "congestion_idx": 0.07}}},
                    "provenance": {"simulated_feed": True}}
        bridge = ScriptBridge(replies=[json.dumps({"arguments": {"segment_ids": [1012]}}),
                                       "not json at all"])
        orch = Orchestrator(bridge, FakeExecutor(routes={"predict_traffic_flow": forecast}),
                            fake_store, decider_brain=DeciderBrain(
                                ScriptDecider(["predict_traffic_flow", "final_answer"]),
                                min_interval_sec=0))
        await orch.create_session("s1")
        result = await orch.process_turn("s1", "forecast for segment 1012")
        assert "heuristic_final" in result["tiers_used"]
        # labelled exactly once: the forecast summary itself now says
        # SIMULATED FEED (HON-17), so the note is not appended a second time
        assert "(SIMULATED FEED)" in result["reasoning"]
        assert result["reasoning"].count("SIMULATED FEED") == 1
