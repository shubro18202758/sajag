# Third-party notices — corridor-store seed data

## OpenStreetMap (ODbL 1.0)

Sajag's Mumbai road network (City Pack `cities/mumbai/`) is traced on OpenStreetMap:

> Road data © OpenStreetMap contributors, available under the
> Open Database License 1.0 (ODbL) —
> https://www.openstreetmap.org/copyright ·
> https://opendatacommons.org/licenses/odbl/1-0/

What is derived from it: every segment's routing geometry
(`corridor.road_segments.geom`, `geom_source = 'osm'`, the OSM way ids and the
extract's `osm_base` in `geom_meta`), the junction positions
(`corridor.junctions.osm_node_id`, each the OSM node where the junction's roads
meet), the junction movements and road graph built on them, which junctions
are signalised (an OSM `highway=traffic_signals` node within 80 m), the
MODELLED camera sites placed on the real approaches, and the agency station
positions (OSM police stations, traffic guards, fire stations and hospitals
tagged `emergency=yes`) — and, in a store the network step converts, the
positions of the EMULATED camera reads it re-anchors onto those lines
(`corridor.vehicle_sightings.position`, source `emulated_anpr`, and the same
reads inside the runs' recorded tapes, `emulator.emulation_runs.tape`: each
keeps its fraction along its segment, now interpolated on OSM-derived
geometry; these live only in the store, never in a repo file, and a
`live_anpr` read is never moved). Segment names, one-way flags and road
classes follow the OSM ways; lanes and speed limits fall back to MODELLED
class defaults where OSM carries none (`scripts/data/osm_network.json`
records which, per segment). Signal programs are MODELLED (standard cycle
templates by approach class, source `osm_assumed`), not a controller's
timings; camera sites are MODELLED because real CCTV positions are not public.
Junction names come from the pack's `landmarks.json` (EN and Marathi); a
station's Marathi name is OSM's `name:mr` where OSM carries one, else the
pack's.

Source: four Overpass API extracts (`overpass-api.de`, mirrors
`maps.mail.ru` and `overpass.kumi.systems`), `osm_base` city 2026-10-30T09:08:38Z,
airport 2026-10-30T09:10:40Z, stations 2026-10-30T09:08:38Z, subways 2026-07-24T11:04:51Z
(the mirror's database date). `scripts/gen_osm_network.py --city mumbai` resolves the curated spec
`cities/mumbai/corridors.json` on them and writes every file below
(`scripts/city_build.py mumbai` runs it with every other derived file). The
extracts themselves are committed in the pack (`cities/mumbai/osm/*.overpass.json.gz`),
so a clone regenerates the same files offline and `--verify` checks them
against a regeneration; re-run the generator with `--fetch --cache DIR` (an
empty DIR) for a newer extract, which rewrites the files and the snapshot
together. The Kolkata network the platform was first built on is kept as a
second pack (`cities/kolkata/`, with its own extracts) that the portability
test builds (`scripts/city_build.py kolkata --out DIR`); `cities/ahmedabad/`
is an older pack with its own extracts.

| File | What it carries | Where it is credited |
| --- | --- | --- |
| `seed/sample_corridor.sql` | the network rows of a fresh install | file header |
| `seed/reanchor_osm_network.sql` | the idempotent network step that converts an existing store (and re-anchors its EMULATED reads onto the new lines) | file header |
| `seed/display_geometry_osm.sql` | superseded display lines (now only clears one a store still carries) | file header |
| `cities/mumbai/osm/*.overpass.json.gz`, `cities/kolkata/osm/*.overpass.json.gz`, `cities/ahmedabad/osm/*.overpass.json.gz` | the Overpass extracts the networks are built from, unmodified (gzip of the request and the response) | the response's own `osm3s.copyright` (openstreetmap.org, ODbL) and this notice |
| `cities/mumbai/network.json`, `cities/kolkata/network.json` | each pack's network in compact form | `attribution` |
| `scripts/data/osm_network_map.json` | the resolved mapping table: OSM node per junction, road per segment, cameras, stations, evidence | `attribution` |
| `scripts/data/osm_network.json` | the evidence: traced paths, OSM way and node ids, validation metrics | `attribution` |
| `scripts/data/osint_gazetteer.json` | the OSINT place gazetteer (`scripts/gen_osint_gazetteer.py`): the network's junctions' and road segments' OSM names and points, plus hand-placed neighbourhood and landmark points; seeds `osint.gazetteer` | `meta.licence` ("© OpenStreetMap contributors, ODbL 1.0") and `meta.source` |
| `services/signal-ingress/src/feeds/segments_mumbai.rs` | the ingress feeds' polylines (`scripts/gen_ingress_segments.py`, from `scripts/data/osm_network.json`; offline by default) | module header |
| `scripts/data/route_acceptance_pairs.json` | routes over the network (`scripts/poi_route_matrix.py`) | `attribution` |
| `scripts/scenario_library.json` | the twin's network facts (`python -m traffic_oracle.simulation export`) | `attribution` |

Share-alike: the OSM-derived data in these files remains under ODbL 1.0
(section 4.4), whatever licence covers the code around it (the repository's
MIT `LICENSE`). A map drawn from it (the God's-eye canvas) is a Produced Work
and credits OpenStreetMap on screen; the deck's own notice is
`services/command-deck/src/lib/gods-eye/NOTICE.md`.
