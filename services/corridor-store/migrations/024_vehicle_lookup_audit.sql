-- 024_vehicle_lookup_audit.sql
-- The officer-only full-mark vehicle lookup audit trail (FIX-C-PLATESEARCH).
--
-- Every completed GET /api/v1/vehicles/lookup by a named duty officer writes
-- exactly one row here, found or not: WHO looked, WHEN, the MASKED mark, a
-- hash of the canonical mark, and the lawful-disclosure class of the answer.
-- The accountability rail (CONTEXT section 4): an officer action that
-- reveals data is recorded with the officer's name and time.
--
-- SCHEMA ONLY, additive, idempotent — safe on fresh installs and on the
-- ledgered live install.
--
-- Grammar constraint (007 header): consumed by naive ';'-splitters — no ';'
-- or '--' inside string literals, no dollar-quoted bodies, no block
-- comments; tests apply this file statement by statement.
--
-- Ethics rails (C6): vehicles only. The raw registration mark is NEVER
-- stored in clear text — mark_masked carries mask_plate's output and
-- mark_sha256 the lowercase hex sha256 of the canonical mark (length-CHECKed
-- at 64); no column in this table could hold a clear mark. There is
-- deliberately NO foreign key to corridor.vehicles: the audit must survive
-- vehicle reaping and must record lookups of UNKNOWN marks (found = false),
-- which have no vehicle row. disclosure reuses the DisclosureBasis
-- vocabulary plus 'none' (no lawful basis to show camera reads).

CREATE TABLE IF NOT EXISTS corridor.vehicle_lookup_audit (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    looked_up_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    officer       TEXT NOT NULL,
    mark_masked   TEXT NOT NULL,
    mark_sha256   TEXT NOT NULL CHECK (char_length(mark_sha256) = 64),
    found         BOOLEAN NOT NULL,
    disclosure    TEXT NOT NULL CHECK (disclosure IN ('active_earmark', 'evidence_only', 'none'))
);

CREATE INDEX IF NOT EXISTS idx_vehicle_lookup_audit ON corridor.vehicle_lookup_audit (looked_up_at DESC);
