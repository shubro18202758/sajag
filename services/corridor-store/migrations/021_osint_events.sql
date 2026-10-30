-- 021_osint_events.sql
-- OSINT event intelligence (Sajag v2): the osint schema of PLACES and SITUATIONS, the additive provenance
-- columns on events.corridor_events, the six reported-situation event kinds (contract C3 lockstep), and the
-- traffic.incidents relaxations.
--
--   osint.raw_signals       one row per RawOsintSignal (osint_common.types), already redacted at parse
--   osint.gazetteer         places only: roads, junctions, neighbourhoods, landmarks and their alias forms
--   osint.resolved_events   one row per fused situation, keyed by fused_event_id (stable across re-fusion)
--   osint.geocodes          per-signal resolution onto the real network, or an area at its real precision
--   osint.event_sources     the situation <-> signal link (role primary or corroborating)
--   events.corridor_events  + geotag, source_kind, credibility, verification_state, provenance
--   event_kind (both event tables) + reported_crime, public_disorder, road_accident, hazard, flooding,
--                           infra_failure
--   traffic.incidents       source + osint, incident_kind + road_rage, robbery, public_disorder
--
-- ETHICS (OSINT SPEC section 0 and 4): events are about places and situations, never persons. No table here has
-- a person, author, handle, username, byline, reporter, poster, uploader, suspect, accused, victim, owner,
-- driver-name, face, biometric or individual column (tests/test_migration_021_grammar.py scans every column).
-- Person names and ages are redacted at parse ([PERSON] and [AGE]) before anything reaches these tables, and
-- raw_signals.raw holds a sanitised scalar whitelist, never the untouched source record. Reported crime enters
-- only as a REPORTED situation for response: the database itself refuses sajag_event_kind crime_incident
-- (ANPR and watchlist origin only) and vehicle_pursuit (human-initiated only) on osint.resolved_events.
--
-- Idempotent and additive-only (the 007 header): every CREATE carries IF NOT EXISTS, every new column ADD
-- COLUMN IF NOT EXISTS, and every CHECK that replaces or adds a constraint is a guarded DROP CONSTRAINT IF
-- EXISTS followed by ADD CONSTRAINT. The constraint names dropped below were read from int3c and from the
-- newest live backup (offline) before this file was written. 001-020 are byte-immutable (ledger checksums),
-- and this file never changes once merged (a later schema change is 023+).
--
-- GRAMMAR CONSTRAINT (007 header): consumed by psql (initdb mount, scripts/migrate.py) AND by naive
-- splitters (corridor-store and embedding-service tests strip line comments, then split on semicolons), so it
-- stays in the plain-statement subset: no dollar-quoted blocks, no block comments, no semicolon inside a
-- literal, no double hyphen inside a literal.

CREATE SCHEMA IF NOT EXISTS osint;

-- =============================================================================
-- RAW SIGNALS (one per RawOsintSignal, signal_id = sha1(source:source_id))
-- =============================================================================

CREATE TABLE IF NOT EXISTS osint.raw_signals (
    signal_id         TEXT PRIMARY KEY,
    source            TEXT NOT NULL,
    source_id         TEXT NOT NULL,
    source_tier       TEXT NOT NULL,
    publisher         TEXT,
    url               TEXT,
    title             TEXT,
    body              TEXT,
    language          TEXT,
    published_at      TIMESTAMPTZ,
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_until       TIMESTAMPTZ,
    fetch_mode        TEXT NOT NULL DEFAULT 'live' CHECK (fetch_mode IN ('live', 'cached-sample')),
    pii_redactions    INT NOT NULL DEFAULT 0,
    raw_geo_hint      JSONB NOT NULL DEFAULT '{}',
    category_hint     JSONB NOT NULL DEFAULT '[]',
    tone              REAL,
    provenance_label  TEXT NOT NULL CHECK (provenance_label IN (
                          'OFFICIAL-VERIFIED', 'NEWS-REPORTED', 'UNVERIFIED-OSINT', 'SIMULATED', 'EMULATED'
                      )),
    credibility_prior REAL NOT NULL CHECK (credibility_prior BETWEEN 0 AND 1),
    license           TEXT,
    redistributable   BOOLEAN NOT NULL DEFAULT FALSE,
    raw               JSONB NOT NULL DEFAULT '{}',
    run_id            TEXT
);

CREATE INDEX IF NOT EXISTS idx_raw_signals_fetched
    ON osint.raw_signals (fetched_at);

CREATE INDEX IF NOT EXISTS idx_raw_signals_published
    ON osint.raw_signals (published_at);

-- =============================================================================
-- GAZETTEER (places only, seeded from scripts/data/osint_gazetteer.json)
-- =============================================================================

CREATE TABLE IF NOT EXISTS osint.gazetteer (
    gaz_id            BIGSERIAL PRIMARY KEY,
    canonical_name    TEXT NOT NULL,
    feature_type      TEXT NOT NULL CHECK (feature_type IN (
                          'road', 'junction', 'neighbourhood', 'landmark', 'admin', 'poi'
                      )),
    surface_forms     TEXT[] NOT NULL,
    name_norm         TEXT NOT NULL,
    lang_primary      TEXT,
    geom              GEOMETRY(Geometry, 4326) NOT NULL,
    segment_id        BIGINT REFERENCES corridor.road_segments(segment_id),
    junction_id       BIGINT REFERENCES corridor.junctions(junction_id),
    importance        REAL NOT NULL DEFAULT 0.5,
    source            TEXT NOT NULL,
    confidence_prior  REAL NOT NULL DEFAULT 0.8
);

CREATE INDEX IF NOT EXISTS idx_gazetteer_namenorm
    ON osint.gazetteer USING gin (name_norm gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_gazetteer_geom
    ON osint.gazetteer USING gist (geom);

-- =============================================================================
-- RESOLVED EVENTS (one per fused situation, surfaced = is_event and not superseded)
-- =============================================================================

CREATE TABLE IF NOT EXISTS osint.resolved_events (
    osint_event_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fused_event_id    TEXT NOT NULL UNIQUE,
    event_class       TEXT NOT NULL,
    subtype           TEXT,
    sajag_event_kind   TEXT,
    sajag_incident_kind TEXT,
    label             TEXT,
    summary           TEXT,
    toponym           TEXT,
    geom              GEOMETRY(Geometry, 4326),
    rep_lon           DOUBLE PRECISION,
    rep_lat           DOUBLE PRECISION,
    segment_id        BIGINT REFERENCES corridor.road_segments(segment_id),
    junction_id       BIGINT REFERENCES corridor.junctions(junction_id),
    window_start      TIMESTAMPTZ,
    window_end        TIMESTAMPTZ,
    credibility       REAL NOT NULL CHECK (credibility BETWEEN 0 AND 1),
    verification_state TEXT NOT NULL CHECK (verification_state IN (
                          'EMULATED', 'SIMULATED', 'UNVERIFIED-OSINT', 'NEWS-REPORTED',
                          'OFFICIAL-VERIFIED', 'CONFIRMED'
                      )),
    geocode_confidence REAL CHECK (geocode_confidence BETWEEN 0 AND 1),
    area_level        BOOLEAN NOT NULL DEFAULT FALSE,
    source_count      INT NOT NULL DEFAULT 1,
    source_tiers      TEXT[] NOT NULL DEFAULT '{}',
    independent_publishers INT NOT NULL DEFAULT 1,
    cross_type_corroborated BOOLEAN NOT NULL DEFAULT FALSE,
    correlated_classes TEXT[] NOT NULL DEFAULT '{}',
    is_event          BOOLEAN NOT NULL DEFAULT FALSE,
    held_reason       TEXT,
    attach_novel      BOOLEAN,
    corroborates_live_urn TEXT,
    second_order      JSONB NOT NULL DEFAULT '[]',
    labels            TEXT[] NOT NULL DEFAULT '{}',
    promoted_event_id UUID,
    superseded_by     UUID,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- the database itself refuses crime_incident (ANPR and watchlist origin) and vehicle_pursuit (human-initiated)
-- from OSINT: the sixteen kinds minus those two
ALTER TABLE osint.resolved_events
    DROP CONSTRAINT IF EXISTS resolved_events_sajag_event_kind_check;

ALTER TABLE osint.resolved_events
    ADD CONSTRAINT resolved_events_sajag_event_kind_check CHECK (
        sajag_event_kind IS NULL OR sajag_event_kind IN (
            'protected_movement', 'procession', 'mass_gathering',
            'race', 'ceremonial', 'egress_surge',
            'emergency_evacuation', 'work_zone',
            'reported_crime', 'public_disorder', 'road_accident',
            'hazard', 'flooding', 'infra_failure'
        ));

CREATE INDEX IF NOT EXISTS idx_resolved_geom
    ON osint.resolved_events USING gist (geom);

CREATE INDEX IF NOT EXISTS idx_resolved_class
    ON osint.resolved_events (event_class, created_at);

-- GET /api/v1/osint/events reads surfaced, not-superseded situations by window
CREATE INDEX IF NOT EXISTS idx_resolved_surfaced
    ON osint.resolved_events (is_event, window_end)
    WHERE superseded_by IS NULL;

-- =============================================================================
-- GEOCODES (per signal, area levels keep their real precision, plan R28)
-- =============================================================================

CREATE TABLE IF NOT EXISTS osint.geocodes (
    geocode_id        BIGSERIAL PRIMARY KEY,
    signal_id         TEXT NOT NULL REFERENCES osint.raw_signals(signal_id),
    toponym           TEXT,
    feature_type      TEXT,
    geom              GEOMETRY(Geometry, 4326),
    segment_id        BIGINT,
    junction_id       BIGINT,
    snapped_to        TEXT,
    confidence        REAL CHECK (confidence BETWEEN 0 AND 1),
    bucket            TEXT CHECK (bucket IN ('high', 'medium', 'low')),
    method            TEXT,
    residual_m        REAL,
    area_level        BOOLEAN NOT NULL DEFAULT FALSE,
    area_scope        TEXT CHECK (area_scope IS NULL OR area_scope IN ('district', 'state')),
    alternatives      JSONB NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_geocodes_signal
    ON osint.geocodes (signal_id);

-- =============================================================================
-- EVENT SOURCES (situation <-> signal)
-- =============================================================================

CREATE TABLE IF NOT EXISTS osint.event_sources (
    osint_event_id    UUID NOT NULL REFERENCES osint.resolved_events(osint_event_id),
    signal_id         TEXT NOT NULL REFERENCES osint.raw_signals(signal_id),
    role              TEXT NOT NULL CHECK (role IN ('primary', 'corroborating')),
    PRIMARY KEY (osint_event_id, signal_id)
);

CREATE INDEX IF NOT EXISTS idx_event_sources_signal
    ON osint.event_sources (signal_id);

-- =============================================================================
-- EVENTS.CORRIDOR_EVENTS: additive provenance columns (contract C-T)
-- source_kind stays NULL unless the creator supplies it (no inference)
-- =============================================================================

ALTER TABLE events.corridor_events ADD COLUMN IF NOT EXISTS geotag GEOMETRY(Point, 4326);

ALTER TABLE events.corridor_events ADD COLUMN IF NOT EXISTS source_kind TEXT;

ALTER TABLE events.corridor_events ADD COLUMN IF NOT EXISTS credibility REAL;

ALTER TABLE events.corridor_events ADD COLUMN IF NOT EXISTS verification_state TEXT;

ALTER TABLE events.corridor_events ADD COLUMN IF NOT EXISTS provenance JSONB;

CREATE INDEX IF NOT EXISTS idx_corridor_events_geotag
    ON events.corridor_events USING gist (geotag);

ALTER TABLE events.corridor_events
    DROP CONSTRAINT IF EXISTS corridor_events_source_kind_check;

ALTER TABLE events.corridor_events
    ADD CONSTRAINT corridor_events_source_kind_check CHECK (
        source_kind IS NULL OR source_kind IN ('operator', 'brain', 'emulator', 'osint')
    );

ALTER TABLE events.corridor_events
    DROP CONSTRAINT IF EXISTS corridor_events_credibility_check;

ALTER TABLE events.corridor_events
    ADD CONSTRAINT corridor_events_credibility_check CHECK (
        credibility IS NULL OR credibility BETWEEN 0 AND 1
    );

ALTER TABLE events.corridor_events
    DROP CONSTRAINT IF EXISTS corridor_events_verification_state_check;

ALTER TABLE events.corridor_events
    ADD CONSTRAINT corridor_events_verification_state_check CHECK (
        verification_state IS NULL OR verification_state IN (
            'EMULATED', 'SIMULATED', 'UNVERIFIED-OSINT', 'NEWS-REPORTED',
            'OFFICIAL-VERIFIED', 'CONFIRMED'
        ));

-- =============================================================================
-- EVENT-KIND CHECK RELAXATION (contract C3: exactly six additions, on BOTH tables, as 010 did)
-- =============================================================================

ALTER TABLE events.corridor_events
    DROP CONSTRAINT IF EXISTS corridor_events_event_kind_check;

ALTER TABLE events.corridor_events
    ADD CONSTRAINT corridor_events_event_kind_check CHECK (event_kind IN (
        'protected_movement', 'procession', 'mass_gathering',
        'race', 'ceremonial', 'egress_surge',
        'emergency_evacuation', 'work_zone',
        -- watchlist-anpr additions (010, C3):
        'crime_incident', 'vehicle_pursuit',
        -- OSINT reported-situation additions (021, C3):
        'reported_crime', 'public_disorder', 'road_accident',
        'hazard', 'flooding', 'infra_failure'
    ));

ALTER TABLE events.event_profiles
    DROP CONSTRAINT IF EXISTS event_profiles_event_kind_check;

ALTER TABLE events.event_profiles
    ADD CONSTRAINT event_profiles_event_kind_check CHECK (event_kind IN (
        'protected_movement', 'procession', 'mass_gathering',
        'race', 'ceremonial', 'egress_surge',
        'emergency_evacuation', 'work_zone',
        -- watchlist-anpr additions (010, C3):
        'crime_incident', 'vehicle_pursuit',
        -- OSINT reported-situation additions (021, C3):
        'reported_crime', 'public_disorder', 'road_accident',
        'hazard', 'flooding', 'infra_failure'
    ));

-- =============================================================================
-- TRAFFIC.INCIDENTS: the reported-incident home (guarded DROP/ADD exactly like 007)
-- =============================================================================

ALTER TABLE traffic.incidents
    DROP CONSTRAINT IF EXISTS incidents_source_check;

ALTER TABLE traffic.incidents
    ADD CONSTRAINT incidents_source_check CHECK (source IN (
        'live', 'scenario_run', 'import',
        -- OSINT reported incidents (021):
        'osint'
    ));

ALTER TABLE traffic.incidents
    DROP CONSTRAINT IF EXISTS incidents_incident_kind_check;

ALTER TABLE traffic.incidents
    ADD CONSTRAINT incidents_incident_kind_check CHECK (incident_kind IN (
        'congestion_spike', 'route_blockage', 'signal_failure',
        'protest', 'accident', 'weather', 'vvip_hold', 'other',
        -- event-agnostic additions (007):
        'crowd_surge', 'egress_surge', 'ambulance_hold', 'work_zone',
        -- OSINT reported-incident additions (021):
        'road_rage', 'robbery', 'public_disorder'
    ));
