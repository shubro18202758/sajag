-- 022_decision_support.sql
-- Decision support (Sajag v2, contract C-U): the decision schema, the object store of DecisionSupport proposals,
-- their courses of action (COAs), the simulation runs behind each COA, and the append-only decision log, plus
-- the 'osint' memory document kind.
--
--   decision.decision_support   one DecisionSupport per generation, at most ONE proposed per event_urn
--                               (partial unique index): a new proposal supersedes the event's previous one
--   decision.coa                one row per COA (actions, predicted outcome, feasibility, attributes, score, ethics)
--   decision.coa_sim_runs       the twin, cascade or surrogate run behind each COA (seed + metrics)
--   decision.dss_decision_log   append-only by convention: one row per officer decision (approve, reject, defer),
--                               written in the decision's own transaction
--   traffic.memory_docs         kind + 'osint' (the DB CHECK only, nothing writes osint memory yet, plan R21)
--
-- The engine proposes, a NAMED officer decides. The DSS itself writes no action: an approval creates dispatch
-- REQUESTS through the existing human-gated channel (each then decided on its own). No person, author, handle,
-- face or biometric column exists here (tests/test_migration_021_grammar.py scans every column), decided_by and
-- officer record the accountable duty officer who decided, never a subject of an event.
--
-- Idempotent and additive-only, the same grammar as 021 (007 header): IF NOT EXISTS everywhere, guarded DROP
-- CONSTRAINT IF EXISTS then ADD for the one replaced CHECK (memory_docs_kind_check, its name read from int3c and
-- from the newest live backup), no dollar-quoted blocks, no block comments, no semicolon or double hyphen inside a
-- literal. This file never changes once merged (a later schema change is 023+).

CREATE SCHEMA IF NOT EXISTS decision;

-- =============================================================================
-- DECISION SUPPORT (one per generation, state is lazily 'expired' on read after horizon_min)
-- =============================================================================

CREATE TABLE IF NOT EXISTS decision.decision_support (
    dss_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_urn         TEXT NOT NULL CHECK (event_urn LIKE 'osint_event:%' OR event_urn LIKE 'event:%'),
    state             TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN (
                          'proposed', 'approved', 'rejected', 'deferred', 'superseded', 'expired'
                      )),
    generated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    horizon_min       INT NOT NULL DEFAULT 45 CHECK (horizon_min BETWEEN 15 AND 120),
    seed              BIGINT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    situation         JSONB NOT NULL,
    criteria          JSONB NOT NULL,
    ahp               JSONB NOT NULL,
    recommendation    JSONB NOT NULL,
    provenance        JSONB NOT NULL,
    scoring_note      TEXT,
    labels            TEXT[] NOT NULL DEFAULT '{}',
    strategy_prior    JSONB,
    requested_by      TEXT NOT NULL DEFAULT 'deck' CHECK (requested_by IN ('deck', 'brain')),
    decided_by        TEXT,
    decided_at        TIMESTAMPTZ,
    decision_note     TEXT,
    chosen_coa_id     TEXT,
    superseded_by     UUID,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_decision_support_event
    ON decision.decision_support (event_urn, generated_at DESC);

-- one decision unit per event: at most one proposed DSS per subject
CREATE UNIQUE INDEX IF NOT EXISTS uq_decision_support_one_proposed
    ON decision.decision_support (event_urn)
    WHERE state = 'proposed';

-- =============================================================================
-- COURSES OF ACTION
-- =============================================================================

CREATE TABLE IF NOT EXISTS decision.coa (
    dss_id            UUID NOT NULL REFERENCES decision.decision_support(dss_id) ON DELETE CASCADE,
    coa_id            TEXT NOT NULL,
    kind              TEXT NOT NULL CHECK (kind IN (
                          'baseline', 'minimal', 'standard', 'aggressive', 'information'
                      )),
    label             TEXT NOT NULL,
    actions           JSONB NOT NULL DEFAULT '[]',
    predicted_outcome JSONB NOT NULL DEFAULT '{}',
    resource_feasibility JSONB NOT NULL DEFAULT '{}',
    attributes        JSONB NOT NULL DEFAULT '{}',
    score             JSONB NOT NULL DEFAULT '{}',
    ethics            JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (dss_id, coa_id)
);

-- =============================================================================
-- SIMULATION RUNS PER COA (sim_run_id is a soft link: twin runs are not always persisted)
-- =============================================================================

CREATE TABLE IF NOT EXISTS decision.coa_sim_runs (
    dss_id            UUID NOT NULL,
    coa_id            TEXT NOT NULL,
    sim_run_id        TEXT,
    method            TEXT NOT NULL CHECK (method IN ('twin', 'cascade', 'surrogate')),
    seed              BIGINT,
    metrics           JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dss_id, coa_id, method),
    FOREIGN KEY (dss_id, coa_id) REFERENCES decision.coa (dss_id, coa_id) ON DELETE CASCADE
);

-- =============================================================================
-- DECISION LOG (append-only by convention, never updated or deleted by the oracle)
-- =============================================================================

CREATE TABLE IF NOT EXISTS decision.dss_decision_log (
    log_id            BIGSERIAL PRIMARY KEY,
    dss_id            UUID NOT NULL REFERENCES decision.decision_support(dss_id),
    decision          TEXT NOT NULL CHECK (decision IN ('approve', 'reject', 'defer')),
    coa_id            TEXT,
    officer           TEXT NOT NULL,
    note              TEXT,
    at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    promoted_event_id UUID,
    dispatch_ids      UUID[] NOT NULL DEFAULT '{}',
    next_steps        JSONB NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_dss_decision_log_dss
    ON decision.dss_decision_log (dss_id, at);

CREATE INDEX IF NOT EXISTS idx_dss_decision_log_at
    ON decision.dss_decision_log (at DESC);

-- =============================================================================
-- TRAFFIC.MEMORY_DOCS: + the 'osint' document kind (004's inline CHECK, guarded DROP/ADD)
-- =============================================================================

ALTER TABLE traffic.memory_docs
    DROP CONSTRAINT IF EXISTS memory_docs_kind_check;

ALTER TABLE traffic.memory_docs
    ADD CONSTRAINT memory_docs_kind_check CHECK (kind IN (
        'incident', 'aar', 'decision', 'scenario_run', 'pattern',
        -- OSINT memory kind (022, nothing writes it yet, plan R21):
        'osint'
    ));
