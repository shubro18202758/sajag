-- 023_osint_source_context_role.sql — the 'context' source role (Sajag v2, wave B; orchestrator fix-up).
--
-- A district- or state-level member (an area alert or district-level report) attached to a point-level
-- situation is CONTEXT: the operator sees "a district warning is in effect", but it never counts as
-- corroboration and never raises credibility or verification_state (osint_analysis.pipeline CONTEXT_ROLE;
-- osint_common.types.SourceRole). 021 created osint.event_sources with role IN ('primary', 'corroborating');
-- this widens that CHECK. 021 and 022 are already ledgered on the sandboxes, so the change is a new file.
--
-- Same grammar rules as 007/010/021: idempotent and additive, plain statements only (no DO blocks, no block
-- comments, no ';' inside literals) so naive ';'-splitters can apply it statement by statement.

ALTER TABLE osint.event_sources DROP CONSTRAINT IF EXISTS event_sources_role_check;

ALTER TABLE osint.event_sources ADD CONSTRAINT event_sources_role_check
    CHECK (role IN ('primary', 'corroborating', 'context'));
