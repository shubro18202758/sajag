-- 026_ai_proposal_decision_log.sql
-- The decision log of the on-premises AI services' proposals (forecast, hydro, twin): one row per named
-- officer's decision on one proposal, written by POST /api/v1/ai-proposals/decision.
--
--   decision.ai_proposal_decision_log   one row per decided proposal (proposal_id UNIQUE: a proposal is decided
--                                       once, a second decision is refused 409 already-decided). It records
--                                       which service proposed, what kind, about which road or place (the
--                                       subject urn), the summary and the labels the officer saw, the evidence
--                                       as shown, approve or reject, the accountable duty officer and the note.
--
-- The AI proposes, a NAMED officer decides, and the decision is recorded. Nothing here actuates anything: no
-- signal program, no dispatch, no event is written by a row of this table, and a follow-up action stays its own
-- separate, human-gated step. Proposals are about roads and places only.
--
-- SCHEMA ONLY, idempotent: IF NOT EXISTS everywhere, additive only (the decision schema is 022's), safe on a
-- fresh install and on the ledgered live install. This file never changes once merged.
--
-- Grammar constraint (007 header): consumed by naive ';'-splitters, so no ';' or '--' inside string literals,
-- no dollar-quoted bodies, no block comments, every statement splittable on ';'.
--
-- Ethics rails (C6): no person, author, handle, face or biometric column. officer records the accountable duty
-- officer who decided, never a subject of a proposal. The evidence is what the officer saw about a road or a
-- place (the route refuses a person key at any depth).

CREATE SCHEMA IF NOT EXISTS decision;

CREATE TABLE IF NOT EXISTS decision.ai_proposal_decision_log (
    log_id        BIGSERIAL PRIMARY KEY,
    proposal_id   TEXT NOT NULL UNIQUE,
    source        TEXT NOT NULL CHECK (source IN ('forecast', 'hydro', 'twin')),
    kind          TEXT NOT NULL,
    subject_urn   TEXT NOT NULL,
    summary       TEXT NOT NULL,
    labels        TEXT[] NOT NULL DEFAULT '{}',
    evidence      JSONB,
    decision      TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
    officer       TEXT NOT NULL,
    actor_source  TEXT,
    note          TEXT,
    decided_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_proposal_decision_log_at
    ON decision.ai_proposal_decision_log (decided_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_proposal_decision_log_source
    ON decision.ai_proposal_decision_log (source, decided_at DESC);
