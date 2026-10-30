"""Decision-support routes (contract C-U) — mounted by ``coordination.py``'s guarded mount when this imports.

    POST /api/v1/decision-support/{event_urn}/generate   compute-only (R2 allow-list), no officer
         {horizon_min?: 15..120 (45), seed?, strategy_prior?, requested_by?: deck|brain}
         → 201 a new DecisionSupport (it supersedes the subject's previous proposal)
         → 200 the existing proposal of the same subject and input fingerprint, < 10 minutes old
         → 404 unknown or held subject; 409 "event-closed"; 503 not deployed / not migrated
    GET  /api/v1/decision-support/{dss_id}               → DecisionSupport (lazily ``expired``); 404 unknown
    POST /api/v1/decision-support/{dss_id}/decision      HUMAN-GATED: a named officer decides
         {decision: approve|reject|defer, coa_id?, note?, officer} + x-sajag-officer
         → 200 {dss_id, state, coa_id, officer, decided_at, promoted_event_id, dispatch_ids[], next_steps[]}

The decision's order of checks is FROZEN (C-U; LG 25 relies on it):

1. the body's shape → 422 (FastAPI; approve names a ``coa_id``, reject and defer carry a note);
2. a named officer — the loopback-verified ``x-sajag-officer``, else the body ``officer`` — otherwise
   **409 officer-required, before any lookup**: an unknown or malformed ``dss_id`` without an officer is also
   409 officer-required;
3. the DSS row → 404 when the ``dss_id`` is unknown;
4. the state → 409 ``not-proposed`` (an expired DSS is not proposed: the lazy expiry is applied first);
5. approve: the COA → 409 ``unknown-coa`` | ``coa-vetoed`` | ``coa-infeasible``, then ``no-anchor``.

Approve is an ordered, idempotent sequence: (1) an unpromoted ``osint_event`` whose COA has a dispatch, closure,
diversion or signal-hold action is promoted with the same officer through OS-5's ``promote_osint_event``
(``already-promoted`` reuses the event; no pooled connection of ours is held while it runs); (2) in ONE
transaction holding the DSS row lock: one dispatch REQUEST per dispatch action (each then decided on its own),
the DSS → ``approved`` and one ``decision.dss_decision_log`` row.  A failure in (2) leaves the DSS proposed; a
retry reuses the promoted event and duplicates nothing.  Every other verb writes nothing and comes back in
``next_steps`` with its home.  Reject and defer write the state and a log row only.

The engine proposes; a named officer decides.  No route here acts on a person.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from osint_common.types import DssDecisionRequest, DssDecisionResult, DssGenerateRequest
from traffic_oracle import events
from traffic_oracle.city.common import as_uuid, decision_store_present
from traffic_oracle.decision_support import coa as coa_mod
from traffic_oracle.decision_support import engine, store
from traffic_oracle.osint import store as osint_store
from traffic_oracle.units.router import authenticated_officer

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["decision-support"])

__all__ = ["REFUSAL_CODES", "router"]

#: The decision's 409 codes (C-U).
REFUSAL_CODES = ("officer-required", "not-proposed", "coa-vetoed", "coa-infeasible", "unknown-coa", "no-anchor")

_REASONS = {
    "officer-required": "a named duty officer decides decision support (x-sajag-officer or officer)",
    "not-proposed": "this decision support is no longer proposed (decided, superseded or expired)",
    "coa-vetoed": "a vetoed course of action is listed, never approvable",
    "coa-infeasible": "a resource-infeasible course of action is listed, never approvable",
    "unknown-coa": "the coa_id names no course of action of this decision support",
    "no-anchor": "the course of action needs a road anchor (a segment or a junction) the subject does not have",
    "not-an-event": "the reported situation is held or superseded: it can no longer be promoted",
}


def _refuse(code: str) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": code, "reason": _REASONS.get(code, code)})


def _pool(request: Request) -> Any:
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database pool unavailable")
    return pool


async def _require_store(conn: Any) -> None:
    if not await decision_store_present(conn):
        raise HTTPException(status_code=503, detail="decision support store not migrated (022)")


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# POST /api/v1/decision-support/{event_urn}/generate — compute only
# ---------------------------------------------------------------------------


@router.post("/api/v1/decision-support/{event_urn}/generate")
async def generate_decision_support(
    event_urn: str, request: Request, body: DssGenerateRequest | None = None
) -> JSONResponse:
    """Compute one DecisionSupport for a subject (C-U): no officer, no action written."""
    req = body or DssGenerateRequest()
    subject = store.parse_subject(event_urn)
    if subject is None:
        raise HTTPException(status_code=404, detail="unknown subject: osint_event:<uuid> or event:<uuid>")
    kind, sid = subject
    pool = _pool(request)
    now = _now()
    seed = req.seed if req.seed is not None else engine.DEFAULT_SEED
    prior = req.strategy_prior.model_dump(mode="json") if req.strategy_prior is not None else None
    async with pool.acquire() as conn:
        await _require_store(conn)
        frame = await store.load_frame(conn, kind, sid, now=now)
        fp = engine.fingerprint(frame, horizon_min=req.horizon_min, seed=seed, strategy_prior=prior)
        existing = await store.reusable(conn, frame.event_urn, fp, now=now)
        if existing is not None:
            doc = await store.read_doc(conn, existing, now=now)
            if doc is not None and doc["state"] == "proposed":
                return JSONResponse(status_code=200, content=doc)
    # no pooled connection is held while the twin and the graph take theirs
    doc, war = await engine.generate(
        request, frame, horizon_min=req.horizon_min, seed=seed, strategy_prior=prior, now=now
    )
    async with pool.acquire() as conn:
        saved = await store.persist(
            conn, doc, fingerprint=fp, sim_runs=war.sim_runs, requested_by=req.requested_by, now=now
        )
        if not saved.created:
            # a concurrent identical generation won the race: answer with its proposal
            again = await store.read_doc(conn, saved.dss_id, now=now)
            if again is not None:
                return JSONResponse(status_code=200, content=again)
    logger.info(
        "dss.proposed",
        dss_id=doc["dss_id"],
        subject=frame.event_urn,
        method=doc["provenance"]["wargame_method"],
        requested_by=req.requested_by,
    )
    return JSONResponse(status_code=201, content=doc)


# ---------------------------------------------------------------------------
# GET /api/v1/decision-support/{dss_id}
# ---------------------------------------------------------------------------


@router.get("/api/v1/decision-support/{dss_id}")
async def get_decision_support(dss_id: str, request: Request) -> JSONResponse:
    """One DecisionSupport; a proposal past ``generated_at + horizon_min`` reads (and is written) ``expired``."""
    did = as_uuid(dss_id.strip())
    if did is None:
        raise HTTPException(status_code=404, detail=f"decision support {dss_id} not found")
    pool = _pool(request)
    async with pool.acquire() as conn:
        await _require_store(conn)
        doc = await store.read_doc(conn, str(did), now=_now())
    if doc is None:
        raise HTTPException(status_code=404, detail=f"decision support {did} not found")
    return JSONResponse(status_code=200, content=doc)


# ---------------------------------------------------------------------------
# POST /api/v1/decision-support/{dss_id}/decision — HUMAN-GATED
# ---------------------------------------------------------------------------


def _waypoint(situation: dict[str, Any], actions: list[dict[str, Any]]) -> int | None:
    """The junction a dispatch request names: the subject's, else the junction the COA's hold or check
    targets (a real ``corridor.junctions`` id), else none (segment-scoped)."""
    if situation.get("junction_id"):
        return int(situation["junction_id"])
    for a in actions:
        target = str(a.get("target_urn") or "")
        if a.get("verb") in ("signal_hold", "request_cctv") and target.startswith("junction:"):
            try:
                return int(target.split(":", 1)[1])
            except ValueError:
                return None
    return None


@router.post("/api/v1/decision-support/{dss_id}/decision")
async def decide_decision_support(dss_id: str, body: DssDecisionRequest, request: Request) -> Any:
    """A named officer approves exactly one COA, or rejects / defers the proposal (C-U; see the module)."""
    # (2) a NAMED officer first — before anything is looked up
    header = authenticated_officer(request)
    if header is None and body.officer is None:
        return _refuse("officer-required")
    actor, detail = events._human_actor(request, body.officer)
    # (3) the row
    did = as_uuid(dss_id.strip())
    if did is None:
        raise HTTPException(status_code=404, detail=f"decision support {dss_id} not found")
    did_s = str(did)
    pool = _pool(request)
    now = _now()
    note = body.note.strip() if body.note else None
    async with pool.acquire() as conn:
        await _require_store(conn)
        row = await store.get_row(conn, did_s)
        if row is None:
            raise HTTPException(status_code=404, detail=f"decision support {did_s} not found")
        # (4) the state, lazy expiry first
        if await store.expire_if_due(conn, row, now=now) != "proposed":
            return _refuse("not-proposed")
        event_urn = str(row["event_urn"])
        situation = store._js(row["situation"]) or {}
        chosen: dict[str, Any] | None = None
        promoted: str | None = None
        event_id: str | None = None
        if body.decision == "approve":
            # (5) the COA
            coas = {c["coa_id"]: c for c in await store.load_coas(conn, did_s)}
            chosen = coas.get(body.coa_id or "")
            if chosen is None:
                return _refuse("unknown-coa")
            if chosen["ethics"].get("vetoed"):
                return _refuse("coa-vetoed")
            if not chosen["resource_feasibility"].get("feasible"):
                return _refuse("coa-infeasible")
            needs_anchor = any(a.get("verb") in coa_mod.kinds.ANCHOR_VERBS for a in chosen["actions"])
            if needs_anchor and situation.get("segment_id") is None and situation.get("junction_id") is None:
                return _refuse("no-anchor")
            kind, sid = store.parse_subject(event_urn) or ("", "")
            if kind == "event":
                event_id = sid
            elif kind == "osint_event":
                current = await osint_store.get_row(conn, sid)
                if current is not None and current["promoted_event_id"] is not None:
                    promoted = str(current["promoted_event_id"])
                    event_id = promoted
    if body.decision == "approve" and chosen is not None:
        kind, sid = store.parse_subject(event_urn) or ("", "")
        needs_anchor = any(a.get("verb") in coa_mod.kinds.ANCHOR_VERBS for a in chosen["actions"])
        if kind == "osint_event" and promoted is None and needs_anchor:
            # step (1): promote with the same officer (OS-5); no pooled connection of ours is held
            from traffic_oracle.osint import promote  # noqa: PLC0415 — the OSINT surface is optional

            try:
                result = await promote.promote_osint_event(
                    request,
                    sid,
                    officer=body.officer,
                    note=(f"decision support {did_s}: {chosen['coa_id']}" + (f" — {note}" if note else ""))[:500],
                    dss_id=did_s,
                )
                promoted = str(result["event_id"])
            except promote.PromoteRefused as exc:
                if exc.code == "already-promoted" and exc.event_id:
                    promoted = exc.event_id
                elif exc.code in ("no-anchor", "not-an-event", "officer-required"):
                    return _refuse(exc.code)
                else:  # pragma: no cover — promote's codes are closed
                    raise
            event_id = promoted
    names = {
        str(a.get("target_urn")): str(situation["toponym"])
        for a in (chosen or {}).get("actions", [])
        if situation.get("toponym") and str(a.get("target_urn") or "").startswith("place:")
    }
    steps = coa_mod.next_steps(chosen["actions"], names) if chosen is not None else []
    async with pool.acquire() as conn:
        try:
            out = await store.decide(
                conn,
                did_s,
                decision=body.decision,
                actor=actor,
                detail=detail,
                note=note,
                coa=chosen,
                event_id=event_id,
                waypoint_junction=_waypoint(situation, chosen["actions"]) if chosen else None,
                promoted_event_id=promoted,
                next_steps=steps,
                now=now,
            )
        except store.Refused as exc:
            return _refuse(exc.code)
    result = DssDecisionResult(
        dss_id=did_s,
        state=out["state"],
        coa_id=(chosen or {}).get("coa_id"),
        officer=actor,
        decided_at=now,
        promoted_event_id=promoted,
        dispatch_ids=out["dispatch_ids"],
        next_steps=steps,
    ).model_dump(mode="json")
    logger.info(
        "dss.decided",
        dss_id=did_s,
        decision=body.decision,
        coa_id=result["coa_id"],
        officer=actor,
        actor_source=(detail or {}).get("actor_source", "body"),
        promoted_event_id=promoted,
        dispatch_requests=len(out["dispatch_ids"]),
    )
    return result
