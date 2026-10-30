"""The emulator keeps working when the oracle requires a named officer — no network.

infra/compose.argus-override.yml passes VVIP_REQUIRE_OFFICER (default 1) to the
traffic-oracle as well as the brain (F-CONN-02). With it on, the oracle answers
422 to an earmark create (vehicles/__init__.py) whose ``earmarked_by`` is
missing, and to a write whose actor fails its named-actor rule
(city/common.py named_actor: whitespace collapsed, 2..max characters, no
control or bidi character; max 120 for earmarks, 64 for the other writes).

The emulator's only officer-gated oracle write is the scenario-precondition
earmark of the Stolen-Vehicle ANPR Sweep, and it always names its system
actor in the body — never an x-sajag-officer header, which only the deck sets
from a verified operator session. This pins both, against a MockTransport
oracle that enforces the rule exactly as VVIP_REQUIRE_OFFICER=1 does.
"""

from __future__ import annotations

import asyncio
import json
import unicodedata

import httpx

from event_emulator.runner import SCENARIO_EARMARKER, ensure_stolen_earmark
from event_emulator.store import SYSTEM_ACTOR
from event_emulator.twin_seam import OracleSeam, SafeHttpClient

BASE = "http://localhost:8121"  # the seam's internal-endpoint allowlist
STOLEN = "MH01EM9001"


def _named_actor_ok(value: object, max_len: int) -> bool:
    """The oracle's named-actor rule (city/common.py named_actor)."""
    if not isinstance(value, str):
        return False
    trimmed = " ".join(value.split())
    if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in trimmed):
        return False
    return 2 <= len(trimmed) <= max_len


def _officer_required_oracle(seen: list[httpx.Request]):
    """An oracle with VVIP_REQUIRE_OFFICER=1: an unnamed earmark is a 422."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET" and request.url.path == "/api/v1/vehicles":
            return httpx.Response(200, json={"vehicles": []})
        if request.method == "POST" and request.url.path.endswith("/earmark"):
            body = json.loads(request.content)
            if body.get("earmarked_by") is None:
                return httpx.Response(422, json={
                    "detail": "earmarked_by is required — a named officer earmarks a vehicle "
                              "(VVIP_REQUIRE_OFFICER=1)"})
            if not _named_actor_ok(body["earmarked_by"], 120):
                return httpx.Response(422, json={"detail": "earmarked_by must be 2..120 characters"})
            return httpx.Response(200, json={"earmark_id": "e-1",
                                             "earmarked_by": body["earmarked_by"]})
        return httpx.Response(404, json={"detail": "not modelled"})

    return handler


class TestRequireOfficer:
    def test_the_system_actors_pass_the_named_actor_rule(self):
        # earmarks allow 120 characters; status transitions (C-F) allow 64
        assert _named_actor_ok(SCENARIO_EARMARKER, 120)
        assert _named_actor_ok(SYSTEM_ACTOR, 64)

    def test_the_precondition_earmark_is_accepted_with_the_officer_required(self):
        seen: list[httpx.Request] = []
        client = SafeHttpClient((BASE,), transport=httpx.MockTransport(_officer_required_oracle(seen)))
        seam = OracleSeam(client, BASE, SYSTEM_ACTOR)
        entry = asyncio.run(ensure_stolen_earmark(
            seam, STOLEN, fir_ref="FIR 4401/2026, Azad Maidan PS",
            use_case_id="watchlist_anpr_sweep", run_id=3))
        asyncio.run(client.close())
        assert entry["result"] == "delivered" and entry["earmark"] == "created", entry
        assert entry["earmarked_by"] == SCENARIO_EARMARKER
        post = [r for r in seen if r.method == "POST"]
        assert len(post) == 1
        assert json.loads(post[0].content)["earmarked_by"] == SCENARIO_EARMARKER

    def test_the_emulator_never_claims_a_deck_verified_officer(self):
        seen: list[httpx.Request] = []
        client = SafeHttpClient((BASE,), transport=httpx.MockTransport(_officer_required_oracle(seen)))
        seam = OracleSeam(client, BASE, SYSTEM_ACTOR)
        asyncio.run(ensure_stolen_earmark(
            seam, STOLEN, fir_ref="FIR 4401/2026, Azad Maidan PS",
            use_case_id="watchlist_anpr_sweep", run_id=None))
        asyncio.run(client.close())
        assert seen, "the oracle was never called"
        for request in seen:
            assert "x-sajag-officer" not in {k.lower() for k in request.headers}
