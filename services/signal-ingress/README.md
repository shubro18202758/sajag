# signal-ingress — Mumbai corridor traffic feed (Rust → NATS)

Aggregates traffic observations from four feed types, runs the Tier-1 inline
anomaly detector, and publishes Arrow IPC batches on NATS
`corridor.traffic.live` (consumed by traffic-oracle) plus a JSON document per
flagged row on `corridor.traffic.anomaly`.

| NATS subject | Payload | Consumer |
|---|---|---|
| `corridor.traffic.live` | Arrow IPC record batches (`timestamp_ms`, `lon`, `lat`, `segment_id`, `speed_kmh`, `congestion_index`, `source`, `data_quality`, `confidence`) | traffic-oracle ingest → `traffic.observations` + Valkey `traffic:latest:{sid}` |
| `corridor.traffic.anomaly` | one JSON document per flagged row (contract C-H, below) | traffic-oracle → `traffic.anomaly_log` |

The broker is `NATS_URL` (in the argus stack the compose service DNS of the
project's own NATS, `nats://nats:4222` on its bridge network, published to
the host as 127.0.0.1:4223). The emulator's showcase plane,
`corridor.traffic.emulated`, is NOT published here.

## Edge-synthetic mode (what runs today)

No live ITMS, fleet AVL, crowd or mapping-provider connector is wired yet, so
every collector runs in **edge-synthetic mode** and every row is published
with `data_quality = synthetic` (ordinal 2; rows the detector flags become
`anomalous`, ordinal 1). Nothing here is presented as a measurement: the
oracle keeps these rows out of the REAL hourly aggregates (they roll up into
`traffic.hourly_aggregates_synthetic`, migration 019) and the deck labels
them SIMULATED FEED.

All four collectors observe one shared congestion field over the Mumbai
road network (`src/feeds/city.rs`), each through its own sensor model:

| Feed (`source` ordinal) | Model |
|---|---|
| government ITMS (0) | one fixed station per segment midpoint, 15 s cycle, phase-staggered (every segment reports in any 15 s window), detector noise |
| mapping provider (1) | 5-minute segment-speed snapshot for every segment, ±5% provider smoothing |
| fleet GPS (2) | 8 AVL vehicles at 1 Hz driving along the segment polylines, turning at shared junction nodes (one-way respected), mean-reverting speed around the prevailing speed |
| crowdsource (3) | 60 s bursts on trunk/primary roads, more reports in jams, 10-60 s stale, ±10% speed error, ~5% exaggerated reports; phone-GPS position error 12 m σ, truncated at the 30 m on-road bar (`ON_ROAD_BAR_M`) so a report never leaves the road it reports on |

The field is `demand(IST time of day, weekday) × sensitivity(segment) + drift`:
a MODELLED weekday profile in IST (UTC+05:30) — an assumption, not a
measurement, and not calibrated to Mumbai counts — with a late-morning peak
(~10:15) and a heavier evening peak (~19:00), per-class and per-segment
sensitivity, and smooth per-segment drift. `INGRESS_CITY_SEED`
changes the city's per-segment character; the default is fixed.

## The network table — the real OpenStreetMap road network

`src/feeds/segments_mumbai.rs` is GENERATED: the Mumbai network's 86
segments, ids 1001–1086 (Marine Drive, the Coastal Road and the Bandra–Worli
Sea Link, the Western and Eastern Express Highways, Dr Ambedkar Road through
Hindmata and Dadar TT, LBS Marg, SV Road, JVLR, SCLR, the Eastern Freeway to
the Atal Setu interchange, the Sahar Elevated Road to Airport T2, ...), with
their ids, attributes (name, class, lanes, speed limit, one-way), geodesic
lengths, ST_LineInterpolatePoint midpoints, full polylines and endpoint
nodes (`NODE_COUNT` 72: every endpoint is one of the network's 72
junctions; a shared endpoint is one node). The network is one connected
piece. Its routing geometry IS the OpenStreetMap road between real junction
nodes — drawn by `scripts/gen_osm_network.py --city mumbai` from the
committed Overpass extracts — so the ingress readings land on the real
roadway. Road geometry: © OpenStreetMap contributors, ODbL 1.0
(https://www.openstreetmap.org/copyright), stated in the generated header.
The ingress has no database access at runtime.

The generator needs no database: by default it reads the network evidence
`scripts/data/osm_network.json` (each segment's `line` is exactly the
`geom` the corridor-store seed writes) and computes what the store would
return — the WGS84 geodesic length (`ST_Length(geom::geography)`), the
planar midpoint (`ST_LineInterpolatePoint(geom, 0.5)`), the extent and the
endpoint nodes — rounded the way PostgreSQL rounds. The database path stays
for drift checks against a seeded store (read-only); both give the same
bytes (checked against PostGIS 3.6: identical file).

```bash
python3 scripts/gen_ingress_segments.py                          # regenerate (offline)
python3 scripts/gen_ingress_segments.py --network N.json --out X.rs
python3 scripts/gen_ingress_segments.py --check                  # exit 1 on drift
python3 scripts/gen_ingress_segments.py --check --container sajag-postgis  # vs a store
```

Regenerate and rebuild the image whenever the corridor network changes.

## Anomaly detection and the anomaly document (contract C-H)

Thresholds: `config/anomaly_detector.yaml`, compiled into the binary and
installed at `/etc/signal-ingress/anomaly_detector.yaml` in the image
(`ANOMALY_CONFIG_PATH` overrides). Each source is judged against its own
recent history on a segment (the last 30 minutes, at most 50 readings); the
z-score and congestion-IQR checks start once that history holds
`min_observations` readings, fewer for the 5-minute mapping snapshots
(`source_min_observations`). The road-class and spatial checks use the
segment's speed limit and geometry.

`corridor.traffic.anomaly` documents keep the observation fields
(`segment_id` string, `timestamp_ms`, `lon`, `lat`, `speed_kmh`,
`congestion_index`, `source`, `data_quality`, `confidence`) and add
`anomaly_flags` (values only from future_timestamp, stale_data, speed_jump,
phantom_reading, speed_zscore, congestion_outlier, road_class_mismatch,
spatial_mismatch — the traffic.anomaly_log vocabulary), `severity`
(low | medium | high) and, additively, `feed_quality`: the reading's data
quality BEFORE the detector relabelled it `Anomalous` (`"Synthetic"` on
these simulated feeds, `"Real"` on a live connector;
`src/normalize/schema_align.rs`). A flag raised on simulated data is
therefore never mistaken for a field anomaly — the oracle stores it in
`traffic.anomaly_log.details` and the city picture labels the anomaly with
it. The field is omitted when unknown; consumers tolerate its absence.

## Build and test

```bash
docker run --rm -v $PWD/services/signal-ingress:/src -w /src rust:alpine \
  sh -c 'apk add -q musl-dev pkgconfig build-base && cargo test --locked'
docker build -f infra/docker/Dockerfile.signal-ingress services/signal-ingress
```

`cargo test --locked` on this tree: **121 passed, 0 failed** — 50 library
unit tests, 7 in `tests/mumbai_feed_tests.rs`, 45 in
`tests/anomaly_tests.rs` and 19 in `tests/pipeline_tests.rs` (rust:alpine,
2026-10-30, on the 86-segment Mumbai network). TLS is
rustls (no OpenSSL). `tests/mumbai_feed_tests.rs`
drives all four feeds through the detector over simulated IST hours and
checks what the live acceptance probe checks: ≥35 distinct segments per
20 s window, the Mumbai envelope (cities/mumbai/city.json bbox), anomalous
share, fleet speed vs limit, the C-H flags — and every row within the 30 m
on-road bar of its own segment's real geometry.
