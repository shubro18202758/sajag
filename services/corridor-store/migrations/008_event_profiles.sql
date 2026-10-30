-- 008_event_profiles.sql
-- Per-use-case corridor-event profile templates (core stream).
--
-- Seeds the eight canonical use-case profiles (from the scenario library
-- configs) as events.event_profiles: the archetypes the emulator and the
-- ops board instantiate corridor_events from.  A profile is a template —
-- event_kind + protection_class + crowd_class + representative route spine,
-- departure, closure policy and simulation knobs — never a live event row.
--
-- Idempotent: ON CONFLICT (profile_id) DO NOTHING (re-running never
-- overwrites operator edits to the template table).
--
-- GRAMMAR CONSTRAINT: no ';' inside string literals and no dollar-quoted
-- bodies — these files are also applied statement-by-statement by naive
-- `;`-splitters (see 007's header and tests/test_migration_pgvector).

CREATE TABLE IF NOT EXISTS events.event_profiles (
    profile_id       TEXT PRIMARY KEY,           -- e.g. 'ganesh_visarjan_girgaon'
    event_kind       TEXT NOT NULL CHECK (event_kind IN (
                         'protected_movement', 'procession', 'mass_gathering',
                         'race', 'ceremonial', 'egress_surge',
                         'emergency_evacuation', 'work_zone'
                     )),
    protection_class TEXT NOT NULL CHECK (protection_class IN (
                         'Z+', 'Z', 'Y', 'X', 'none'
                     )),
    crowd_class      TEXT NOT NULL CHECK (crowd_class IN (
                         'LOW', 'MEDIUM', 'HIGH', 'EXTREME'
                     )),
    name             TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    scenario_id      TEXT,                        -- twin scenario library key
    route_segment_ids BIGINT[] NOT NULL,
    departure_time   TIMESTAMPTZ NOT NULL,
    closure_policy   JSONB NOT NULL,
    horizon_min      SMALLINT NOT NULL CHECK (horizon_min BETWEEN 1 AND 60),
    duration_class   TEXT NOT NULL DEFAULT 'minutes' CHECK (duration_class IN (
                         'minutes', 'hours', 'multi_day', 'multi_week'
                     )),
    template         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO events.event_profiles (
    profile_id, event_kind, protection_class, crowd_class, name, description,
    scenario_id, route_segment_ids, departure_time, closure_policy,
    horizon_min, duration_class, template
) VALUES
    ('vvip_convoy_base', 'protected_movement', 'Z+', 'LOW',
     'VIP Movement — Mantralaya to Mumbai Airport T2 (base case)',
     'BASE CASE. A protected movement from Mantralaya along Marine Drive, the '
     'Coastal Road, the Bandra-Worli Sea Link and the Western Express Highway '
     'to the Sahar Elevated Road and Terminal 2. '
     'Maximum-protocol closure (180 s advance, full closure), default event '
     'rates, no weather — the reference every other use case generalizes.',
     'vvip_convoy_base', ARRAY[1001,1002,1006,1008,1011,1013,1014,1015,1020],
     '2026-11-02T04:40:00Z'::timestamptz,
     '{"advance_closure_sec": 180, "closure_type": "full_closure"}'::jsonb,
     45, 'minutes',
     '{"convoy_speed_kmh": 60, "n_replications": 10, "seed": 20261102}'::jsonb),
    ('ganesh_visarjan_girgaon', 'procession', 'X', 'EXTREME',
     'Ganeshotsav Visarjan — Lalbaug to Girgaon Chowpatty',
     'Anant Chaturdashi: immersion processions at walking pace from Lalbaug '
     'by Byculla, JJ, Nagpada and Opera House to Girgaon Chowpatty, with '
     'staged road closures and a heavy-vehicle restriction.',
     'ganesh_visarjan_girgaon', ARRAY[1063,1062,1081,1082,1083],
     '2026-10-18T13:30:00Z'::timestamptz,
     '{"advance_closure_sec": 120, "closure_type": "full_closure"}'::jsonb,
     60, 'hours',
     '{"convoy_speed_kmh": 8, "n_replications": 12, "seed": 20261018, '
     '"event_overrides": {"market": 2.5}}'::jsonb),
    ('gateway_ferry_transit', 'mass_gathering', 'X', 'HIGH',
     'Gateway and Ferry Wharf Transit — Holiday Crowds and Ferry Departures',
     'Holiday visitors walk from Churchgate and CSMT towards the Gateway of '
     'India and the ferry wharf on P D Mello Road, BEST buses and taxis queue '
     'at the drop-off points while the ferry queue is managed in stages.',
     'gateway_ferry_transit', ARRAY[1005,1060,1058],
     '2026-12-26T03:30:00Z'::timestamptz,
     '{"advance_closure_sec": 90, "closure_type": "signal_hold"}'::jsonb,
     60, 'multi_day',
     '{"convoy_speed_kmh": 40, "n_replications": 12, "seed": 20270113}'::jsonb),
    ('mumbai_marathon', 'race', 'X', 'HIGH',
     'Mumbai Marathon — CSMT, Marine Drive and Peddar Road',
     'Early-morning gun start at CSMT: the course along Marine Drive, '
     'Peddar Road, Haji Ali and Annie Besant Road to Worli is closed in the '
     'dark and reopens in stages behind the sweep (pace/sweep convoy at 12 km/h).',
     'mumbai_marathon', ARRAY[1005,1004,1002,1003,1084,1085,1075,1076],
     '2026-12-20T00:15:00Z'::timestamptz,
     '{"advance_closure_sec": 60, "closure_type": "full_closure"}'::jsonb,
     60, 'hours',
     '{"convoy_speed_kmh": 12, "n_replications": 10, "seed": 20261220}'::jsonb),
    ('shivaji_park_parade', 'ceremonial', 'Z', 'HIGH',
     'Republic Day / Maharashtra Day — Shivaji Park Parade',
     'Dignitaries reach the Shivaji Park parade ground from Worli by Senapati '
     'Bapat Marg and Dadar West before the flag while spectators fill the ground.',
     'shivaji_park_parade', ARRAY[1074,1072,1073],
     '2027-01-26T03:05:00Z'::timestamptz,
     '{"advance_closure_sec": 150, "closure_type": "full_closure"}'::jsonb,
     60, 'minutes',
     '{"convoy_speed_kmh": 40, "n_replications": 10, "seed": 20270126}'::jsonb),
    ('wankhede_egress', 'egress_surge', 'X', 'EXTREME',
     'Stadium Egress — Wankhede Match Night',
     'The 90-120 min egress surge after the last ball towards Churchgate, '
     'Marine Lines and CSMT: an ambulance with a green-corridor request moves '
     'against the dispersal wave under signal_hold.',
     'wankhede_egress', ARRAY[1005,1004,1002],
     '2026-03-08T14:35:00Z'::timestamptz,
     '{"advance_closure_sec": 60, "closure_type": "signal_hold"}'::jsonb,
     60, 'hours',
     '{"convoy_speed_kmh": 50, "n_replications": 12, "seed": 20260308}'::jsonb),
    ('cloudburst_high_tide', 'emergency_evacuation', 'X', 'MEDIUM',
     'Cloudburst at High Tide — Relief Corridor on Dr Ambedkar Road',
     'A heavy burst meets a high tide on the Arabian Sea: the outfalls close and '
     'Hindmata, Dadar TT and Kings Circle waterlog while a relief column runs '
     'Dr Ambedkar Road from Parel to Sion.',
     'cloudburst_high_tide', ARRAY[1065,1066,1067,1068,1069],
     '2025-09-23T00:50:00Z'::timestamptz,
     '{"advance_closure_sec": 60, "closure_type": "signal_hold"}'::jsonb,
     60, 'hours',
     '{"convoy_speed_kmh": 40, "n_replications": 10, "seed": 20250923, '
     '"event_overrides": {"breakdown": 1.8, "waterlogging": 3}, '
     '"weather": {"monsoon": true, "rain_intensity_mm_h": 40}}'::jsonb),
    ('metro_work_zone', 'work_zone', 'X', 'LOW',
     'Planned Infrastructure Work Zone — Metro Works on LBS Marg',
     'Months-long published lane loss for metro construction: an inspection '
     'convoy runs LBS Marg from Kurla by Kamani and Ghatkopar West to '
     'Gandhinagar while the work zones hold barricaded lanes.',
     'metro_work_zone', ARRAY[1040,1041,1042],
     '2025-08-14T03:45:00Z'::timestamptz,
     '{"advance_closure_sec": 60, "closure_type": "partial_closure"}'::jsonb,
     60, 'multi_week',
     '{"convoy_speed_kmh": 40, "n_replications": 8, "seed": 20250814, '
     '"event_overrides": {"market": 1.5}}'::jsonb)
ON CONFLICT (profile_id) DO NOTHING;
