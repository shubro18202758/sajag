"""AI-proposal decisions — the named officer's decision on a proposal of the on-premises AI services, recorded.

The forecast (pre-emptive diversion), hydro (waterlogging reroute, ambulance window, live-wire hazard request,
public advisory draft) and twin (signal timing) services only COMPUTE: each returns proposals in the platform's
decision-support vocabulary (``state: proposed``, ``human_gate.required_role: duty_officer``).  The deck shows them
to the duty officer as decision cards; this module is where the officer's answer is recorded.  Mounted by
``coordination.py``'s guarded mount.

    POST /api/v1/ai-proposals/decision     HUMAN-GATED: a named officer approves or rejects ONE proposal
         {proposal: {proposal_id, source: forecast|hydro|twin, kind, subject_urn, summary, labels[], state:
         proposed, evidence?}, decision: approve|reject, note? (required for reject), officer?}
         + x-sajag-officer (the deck-verified loopback header, units/router.py)
         → 200 {log_id, proposal_id, source, kind, subject_urn, decision, officer, actor_source, claimed_officer,
                note, decided_at, actuated: false, outcome: "recorded"}
    GET  /api/v1/ai-proposals/decisions?limit=1..200&source=   → {decisions: [...]}, newest first

The decision's order of checks is FROZEN (it mirrors the C-U decision-support decision):

1. the body's shape → 422 (pydantic; unknown keys refused; a reject carries a non-blank note; the evidence is
   JSON without NaN, at most 32 KB, and carries no person key at any depth);
2. a named officer — the loopback-verified ``x-sajag-officer``, else the body ``officer`` — otherwise
   **409 officer-required, before any lookup** (no pool, no table is touched);
3. the store → 503 when the pool is missing or migration 026 is not applied;
4. one INSERT … ON CONFLICT (proposal_id) DO NOTHING: a proposal already decided → **409 already-decided**, with
   the earlier decision, officer and time (race-safe: the UNIQUE proposal_id decides, never a read-then-write).

It NEVER actuates anything: no signal program, no dispatch, no event, no advisory is written here.  The AI
proposes, a named officer decides, the decision is recorded (``actuated: false``); any follow-up action stays a
separate, human-gated step in its own home.  A twin timing an officer approves is recorded as approved — the
platform's signal writer applies band plans, never a twin program.  Proposals are about roads and places only;
the stored evidence is what the officer saw.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from traffic_oracle import events
from traffic_oracle.city.common import relation_exists
from traffic_oracle.units.router import authenticated_officer

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["ai-proposals"])

__all__ = ["AI_PROPOSAL_LOG", "EVIDENCE_MAX_BYTES", "REFUSAL_CODES", "router"]

#: The 026 table this module writes and reads.
AI_PROPOSAL_LOG = "decision.ai_proposal_decision_log"

#: The decision's 409 codes.
REFUSAL_CODES = ("officer-required", "already-decided")

#: The evidence an officer saw, serialised (UTF-8 JSON).
EVIDENCE_MAX_BYTES = 32 * 1024

_REASONS = {
    "officer-required": "a named duty officer decides an AI proposal (x-sajag-officer or officer)",
    "already-decided": "this proposal was already decided: one proposal, one decision",
}

#: NUL (Postgres cannot store it), other control characters and the bidi controls; tabs and line breaks kept.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f‪-‮⁦-⁩]")

#: Keys that name a person, refused at any depth of the evidence when osint_common is not installed.
_PERSON_KEY_FALLBACK = re.compile(r"author|person|owner|handle|face|biometric|phone|email|aadhaar", re.I)

_SQL_INSERT = (
    "INSERT INTO decision.ai_proposal_decision_log (proposal_id, source, kind, subject_urn, summary, labels, "
    "evidence, decision, officer, actor_source, note) VALUES ($1, $2, $3, $4, $5, $6::text[], $7::jsonb, $8, $9, "
    "$10, $11) ON CONFLICT (proposal_id) DO NOTHING RETURNING log_id, decided_at"
)
_SQL_EXISTING = (
    "SELECT log_id, decision, officer, decided_at FROM decision.ai_proposal_decision_log WHERE proposal_id = $1"
)
_SQL_LIST = (
    "SELECT log_id, proposal_id, source, kind, subject_urn, decision, officer, note, decided_at, labels "
    "FROM decision.ai_proposal_decision_log WHERE ($2::text IS NULL OR source = $2) "
    "ORDER BY decided_at DESC, log_id DESC LIMIT $1"
)


# ---------------------------------------------------------------------------
# the body (step 1: shape → 422)
# ---------------------------------------------------------------------------


def _clean(v: str | None, *, field: str) -> str | None:
    if v is not None and _CONTROL.search(v):
        raise ValueError(f"{field} must not contain control characters")
    return v


def _named_officer(v: Any) -> str | None:
    """The named-officer rule (2..64 characters, no control or bidi characters); blank reads as ``None``."""
    if v is None:
        return None
    s = " ".join(str(v).split())
    if not s:
        return None
    if any(unicodedata.category(c) == "Cc" for c in s) or _CONTROL.search(s):
        raise ValueError("officer must not contain control characters")
    if not 2 <= len(s) <= 64:
        raise ValueError("officer must be 2..64 characters (a named human officer)")
    return s


def _assert_no_person_keys(obj: Any) -> None:
    try:
        from osint_common.ethics import assert_no_person_keys  # noqa: PLC0415 — optional library
    except ImportError:  # pragma: no cover — the OSINT libraries are not deployed: the local denylist
        def assert_no_person_keys(o: Any, depth: int = 0) -> None:
            if depth > 64:
                raise ValueError("invalid:nesting deeper than 64 levels") from None
            if isinstance(o, dict):
                for k, val in o.items():
                    if _PERSON_KEY_FALLBACK.search(str(k)):
                        raise ValueError(f"forbidden_key:{str(k)[:64]}")
                    assert_no_person_keys(val, depth + 1)
            elif isinstance(o, list | tuple):
                for val in o:
                    assert_no_person_keys(val, depth + 1)
    assert_no_person_keys(obj)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AiProposal(_Model):
    """The proposal as the officer saw it (roads and places only)."""

    proposal_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")
    source: Literal["forecast", "hydro", "twin"]
    kind: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9_]+$")
    subject_urn: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1500)
    labels: list[Annotated[str, Field(min_length=1, max_length=40)]] = Field(default_factory=list, max_length=8)
    state: Literal["proposed"]
    evidence: dict[str, Any] | None = None

    @field_validator("subject_urn", "summary")
    @classmethod
    def _text(cls, v: str, info: Any) -> str:
        return _clean(v, field=info.field_name) or v

    @field_validator("labels")
    @classmethod
    def _labels(cls, v: list[str]) -> list[str]:
        for label in v:
            _clean(label, field="labels")
        return v

    @field_validator("evidence")
    @classmethod
    def _evidence(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is None:
            return None
        _assert_no_person_keys(v)
        try:
            blob = json.dumps(v, allow_nan=False, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"evidence must be JSON-serialisable (no NaN): {exc}") from exc
        if len(blob.encode("utf-8")) > EVIDENCE_MAX_BYTES:
            raise ValueError(f"evidence must be at most {EVIDENCE_MAX_BYTES} bytes of JSON")
        if "\x00" in blob or "\\u0000" in blob:
            raise ValueError("evidence must not contain NUL")
        return v


class AiProposalDecisionRequest(_Model):
    """``POST /api/v1/ai-proposals/decision`` body. The officer is optional HERE because the route checks it next
    (step 2, 409 officer-required, header first, before any lookup); a blank officer reads as none."""

    proposal: AiProposal
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=500)
    officer: Annotated[str | None, BeforeValidator(_named_officer)] = None

    @field_validator("note")
    @classmethod
    def _note(cls, v: str | None) -> str | None:
        return _clean(v, field="note")

    @model_validator(mode="after")
    def _shape(self) -> AiProposalDecisionRequest:
        if self.decision == "reject" and not (self.note and self.note.strip()):
            raise ValueError("reject carries a note (why), at most 500 characters")
        return self


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _refuse(code: str, **extra: Any) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": code, "reason": _REASONS.get(code, code), **extra})


def _pool(request: Request) -> Any:
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database pool unavailable")
    return pool


async def _require_store(conn: Any) -> None:
    try:
        present = await relation_exists(conn, AI_PROPOSAL_LOG)
    except Exception:  # noqa: BLE001 — an unreadable store is an absent one
        present = False
    if not present:
        raise HTTPException(status_code=503, detail="ai proposal decision log not migrated (026)")


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value is not None else None)


# ---------------------------------------------------------------------------
# POST /api/v1/ai-proposals/decision — HUMAN-GATED, never actuates
# ---------------------------------------------------------------------------


@router.post("/api/v1/ai-proposals/decision")
async def decide_ai_proposal(body: AiProposalDecisionRequest, request: Request) -> Any:
    """A named officer approves or rejects one AI proposal; the decision is recorded, nothing is actuated."""
    # (2) a NAMED officer first — before anything is looked up
    header = authenticated_officer(request)
    if header is None and body.officer is None:
        return _refuse("officer-required")
    actor, detail = events._human_actor(request, body.officer)
    actor_source = (detail or {}).get("actor_source", "body")
    note = body.note.strip() if body.note and body.note.strip() else None
    p = body.proposal
    evidence = json.dumps(p.evidence, allow_nan=False, ensure_ascii=False) if p.evidence is not None else None
    # (3) the store
    pool = _pool(request)
    async with pool.acquire() as conn:
        await _require_store(conn)
        # (4) one row, race-safe on the UNIQUE proposal_id
        row = await conn.fetchrow(
            _SQL_INSERT,
            p.proposal_id,
            p.source,
            p.kind,
            p.subject_urn,
            p.summary,
            list(p.labels),
            evidence,
            body.decision,
            actor,
            actor_source,
            note,
        )
        if row is None:
            earlier = await conn.fetchrow(_SQL_EXISTING, p.proposal_id)
            return _refuse(
                "already-decided",
                proposal_id=p.proposal_id,
                decision=earlier["decision"] if earlier else None,
                officer=earlier["officer"] if earlier else None,
                decided_at=_iso(earlier["decided_at"]) if earlier else None,
            )
    result = {
        "log_id": row["log_id"],
        "proposal_id": p.proposal_id,
        "source": p.source,
        "kind": p.kind,
        "subject_urn": p.subject_urn,
        "decision": body.decision,
        "officer": actor,
        "actor_source": actor_source,
        "claimed_officer": (detail or {}).get("claimed_officer"),
        "note": note,
        "decided_at": _iso(row["decided_at"]),
        "actuated": False,
        "outcome": "recorded",
    }
    logger.info(
        "ai_proposal.decided",
        proposal_id=p.proposal_id,
        source=p.source,
        kind=p.kind,
        decision=body.decision,
        officer=actor,
        actor_source=actor_source,
    )
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/ai-proposals/decisions — the record, newest first
# ---------------------------------------------------------------------------


@router.get("/api/v1/ai-proposals/decisions")
async def list_ai_proposal_decisions(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    source: Literal["forecast", "hydro", "twin"] | None = Query(default=None),
) -> dict[str, Any]:
    """The recorded decisions, newest first (optionally one service's)."""
    pool = _pool(request)
    async with pool.acquire() as conn:
        await _require_store(conn)
        rows = await conn.fetch(_SQL_LIST, limit, source)
    return {
        "decisions": [
            {
                "log_id": r["log_id"],
                "proposal_id": r["proposal_id"],
                "source": r["source"],
                "kind": r["kind"],
                "subject_urn": r["subject_urn"],
                "decision": r["decision"],
                "officer": r["officer"],
                "note": r["note"],
                "decided_at": _iso(r["decided_at"]),
                "labels": list(r["labels"] or []),
            }
            for r in rows
        ]
    }
