# osint-geo — the offline geo-resolver for Sajag's OSINT signals

Turns a `RawOsintSignal` (osint_common, X18) about Kolkata into a `Geocode` snapped to a real `segment_id` or
`junction_id` of the OpenStreetMap network Sajag routes on (`corridor.road_segments` 1001-1065,
`corridor.junctions` 1-49), with a calibrated confidence, or an honest `None`. It reads English, Marathi (मराठी),
Hindi and mixed text. Offline and deterministic: no paid or online geocoder, no network call, no secret. Places
only: nothing here reads, stores or returns a person.

```python
from osint_geo.gazetteer import load, Gazetteer          # .entries .by_id .protect_set (frozenset) .norm() .match()
from osint_geo.resolver import GazetteerResolver, resolve_text
from osint_geo.snap import load_network, snap            # snap(lon, lat) -> (segment_id, junction_id, name, residual_m)
from osint_geo.confidence import score, bucket

geocode = GazetteerResolver().resolve(signal)            # Geocode | None (osint_common.pipeline.GeoResolver)
resolve_text("Gariahat more")                            # GET /osint/gazetteer/resolve?q= candidates (C-T)
```

## Data files and path rules

| File | Owner | Rule (first hit wins) |
|---|---|---|
| `scripts/data/osint_gazetteer.json` (X19, ODbL) | this package's generator | argument → `$OSINT_GAZETTEER_PATH` → repo-rooted (walking up from the module) → `/repo/VVIP/scripts/data/` |
| `scripts/data/osm_network.json` (read only) | `scripts/gen_osm_network.py` | argument → `$OSINT_NETWORK_PATH` → repo-rooted → `/repo/VVIP/scripts/data/` |
| `cities/kolkata/gazetteer.json` (the City Pack's places) | edited by hand, read by the generator | the generator's input, never read at run time |

Both run-time files are loaded once per process (cached by path, behind a lock) and are immutable afterwards, so a
resolver is safe to share between threads. An explicit path or variable naming a missing file raises
`FileNotFoundError`; an invalid gazetteer raises `ValueError` (places only: any key outside the X19 field list is
refused at load).

## How a signal resolves

1. **Extract** — the title, the text and the connector's `raw_geo_hint.place_names` (the first 8, 200 characters
   each), read together in the proof of concept's order. A hint that is only a metro district's name ("Howrah",
   "হাওড়া" from a CAP alert's area) scopes the signal but is not read as a place, so a Howrah-district alert stays
   the district. The text is normalised (NFKC, lower case, Latin diacritics folded, format characters removed,
   punctuation → space, `NH-12` → `nh12`; Marathi and Devanagari kept). A Marathi case ending is read off when the
   stem is a place word (`বেহালার` of Behala, `কসবায়` in Kasba, `উল্টোডাঙাতেই`, `শিয়ালদায়`), also for a word the
   gazetteer itself carries inside a longer form (`গড়িয়াহাটের` stays whole only in `গড়িয়াহাটের মোড়`), while
   `শহরের` (of the city) and `রাস্তাতে` (on the road) name no place. A token-trie longest-match scan finds every
   non-overlapping surface form; the place grammar rewrites the generic words (`more`/`mor`/`মোড়`/`मोड़` →
   crossing, `setu`/`সেতু` → bridge, `rd`, `st`, `ave`, `thana`/`ps`/`থানা` → police station). **No form spans a
   sentence end** ("." "!" "?" or "।", but not the full stop of an initial or an abbreviation: `A.J.C. Bose Road`,
   `Dr. Suresh Sarkar Road`): "Fire at Gariahat. More details awaited" is the Gariahat neighbourhood, never
   "Gariahat more", and "Gariahat more than knee deep" is the neighbourhood too (`more than` is English).
2. **Candidates** — exact aliases; only when none match, `difflib` fuzzy matching (ratio ≥ 0.90, trigram
   prefilter) on the grammar's cue-bound names first ("near Eden Gardns"), then three- and two-word windows:
   multi-word only, never with a locality or newsroom word (`india`, `bengal`, `kolkata`, `city`, `news`, …) or
   only generic words in the window. This is the proof of concept's "India" ↔ "indira" guard, which Kolkata needs as
   much (Red Road is "Indira Gandhi Sarani"); no bare given name, surname, company or common word ("indira",
   "netaji", "hazra", "rashbehari", "exide", "airport", "medical") is an alias at all.
   **Context gate** (`resolver.CONTEXT_FORMS`, each with its reason): some forms name a Kolkata place only in a
   text about Kolkata: common words (`maidan`, any field; `বাইপাস`; `new town`), names many cities share (`mg road`,
   `park street`, `science city`, `new market`, `medical college`, `salt lake`, `red road`, `vip road`,
   `strand road`, `gt road`, `central avenue`, `eco park`, `jodhpur park`, `garia`, …) and every bare route code
   (`nh12`: a highway runs on through other districts and states). Their Latin variants (`newtown`, `saltlake`,
   `vip rd`, `strand rd`, `diamond harbor road`, `gariya`) and Marathi and Devanagari spellings (`ময়দান`, `मैदान`,
   `न्यू मार्केट`, `साइंस सिटी`, …; `osint_geo.translit`) are gated with them. They count only when the signal is
   placed **in the city**: by its metadata (`GazetteerResolver.city_scoped`: r/kolkata, KMC or Kolkata Police as
   the source, a geo hint naming Kolkata, Calcutta, Howrah or Bidhannagar, `area:kolkata`/`area:howrah`,
   `LGD:KOLKATA`/`LGD:HOWRAH`, a Kolkata PIN `700xxx`) or by its text naming the city (`resolver.CITY_WORDS`, any
   script, a case ending allowed: `কলকাতায়`). State-level evidence never opens the gate: SACHET, IMD or WBSDMA as
   the source, `LGD:WEST_BENGAL`, `GDELT_ADM1:IN28`, the 24 Parganas codes, a hint naming only West Bengal
   ("Siliguri, West Bengal, India"): Siliguri has a Science City too. So "Rally at Ramlila Maidan in Delhi",
   "रामलीला मैदान में रैली", "Shooting in Newtown, Connecticut" and "Fire at the medical college in Patna" are `None`,
   and "Waterlogging on Park Street in Kolkata" or the same text on r/kolkata resolve. With the gate closed a form is
   not read at all, exactly or fuzzily: a window that is a gated form never fuzzy-matches a longer one
   ("medical college hospital" is not "NRS Medical College Hospital"). The longer forms that carry the place
   ("Kolkata Medical College", "EM Bypass", "Park Street crossing", "Park Street police station", "Salt Lake
   Stadium") are never gated, and an operator's `resolve_text` query is about the city, so the gate is open there.
   **Another thing of the same name** (`resolver.NOT_A_PLACE_BEFORE`): "Howrah Mail", "Howrah Express" and "Howrah
   Rajdhani" are trains, "Howrah district" and "Howrah, West Bengal" (a dateline, a GDELT FullName) the district;
   none is the Howrah city area. **The state gate** (`resolver.STATE_GATED_FORMS`): a signal with state-level
   evidence and no city-level evidence does not read the bare "Howrah", "Behala" or "Dum Dum" (every spelling): a
   state-wide alert lists districts and blocks. "Howrah" in such an alert is no city word either, so "Heavy rain
   likely in Howrah, Hooghly and Nadia" from SACHET with `LGD:WEST_BENGAL` stays "West Bengal (state)" with no point,
   while `LGD:KOLKATA`'s "Waterlogging in Behala" and a national outlet's keep the Behala neighbourhood.
3. **Disambiguation** — `R = 0.25·in_bbox + 0.15·specificity + 0.20·coherence + 0.10·importance + 0.10·locality
   + 0.10·match` (research A6, the embedding-context term left to OS-4). Every mention is a reading; coherence picks
   the EM Bypass segment nearest Kasba (1035) of the road's four.
4. **Snap** — a junction keeps its `junction_id`, a road its `segment_id`; a City Pack place pre-linked to the
   network keeps that id (`anchor` `J<id>`/`S<id>`: Thanthania is on Bidhan Sarani 1058, the airport at junction
   49); another landmark attaches to the segment whose anchor (`ST_PointOnSurface` of its line, the point the oracle
   uses for a segment) is nearest, residual = geodesic metres to that anchor (with no anchor in reach, to the
   nearest road line), **only within 900 m**: farther it has no road anchor and no snap quality (F-HONEST OSINT-3:
   Ruby General Hospital, Dakshineswar, Eco Park). **A neighbourhood is an area** and never gets a road anchor;
   neither does a City Pack street off the network (`anchor` `area`: Amherst Street, Gariahat Road). A bare area word
   ("Gariahat", "Tollygunge", "Ultadanga", in any script) resolves to the area, never to the junction named after
   it (OSINT-1; the gazetteer lint refuses such a junction form): the junction is "Gariahat crossing", "Gariahat
   more", "গড়িয়াহাট মোড়". "Sealdah" alone is the station. **For `segment_id` consumers**: a landmark's
   `segment_id` is that network anchor, not always the nearest carriageway (Eden Gardens is on Sahid Khudiram Bose
   Road 1012 at 210.1 m from its anchor, 155.6 m from its line). Use the geocode's `lon`/`lat` for a distance and
   `snap.Network.line_distance_m(lon, lat, segment_id)` for the distance to a road line.
5. **Confidence** — `0.30·match + 0.25·specificity + 0.20·margin + 0.15·snap_quality + 0.10·source_locality`;
   `high` ≥ 0.75, `medium` ≥ 0.5, else `low`. A place named twice ties with itself (margin 0): repetition never
   inflates confidence. The synthetic EM Bypass crash near Kasba is 0.68 medium, the Gariahat crossing robbery 0.718
   medium (`osint_common.testing`). Source locality is 1.0 for a city- or state-scoped source (r/kolkata, KMC,
   Kolkata Police, SACHET, IMD, WBSDMA), a geo hint naming Kolkata, Howrah or West Bengal, an `area:` hint, a city
   or state admin code, or a Kolkata PIN; else 0.3 (the context gate reads city-level evidence only).

**Area level (plan R28)**, for an official source or GDELT with no finer toponym: `LGD:KOLKATA` (or a GDELT
`ActionGeo_FullName` naming Kolkata or the GNS spelling "Calcutta") → the Kolkata district point, `area_scope
"district"`, confidence 0.40; `LGD:HOWRAH` (or a FullName naming Howrah) → the Howrah district point, 0.40;
`LGD:NORTH_24_PARGANAS` / `LGD:SOUTH_24_PARGANAS` (Salt Lake, New Town, Behala and Garia, but also the
Sundarbans) → the district with **no point**, 0.30, once C-T accepts a district geocode without a point
(`resolver.DISTRICT_WITHOUT_POINT`; today `osint_common.types.Geocode` requires the point, so such an alert is
`None`, never a borrowed point and never an exception); `LGD:WEST_BENGAL` / `GDELT_ADM1:IN28` → `area_scope
"state"`, **no point**, confidence 0.25; any other code (`LGD:DARJEELING`, another state's `GDELT_ADM1`) → `None`.

## The gazetteer generator

```bash
python3 scripts/gen_osint_gazetteer.py --check    # gates: exit 1 when the committed file differs from a rebuild
python3 scripts/gen_osint_gazetteer.py --write    # after a network or City Pack change
python3 scripts/gen_osint_gazetteer.py --overpass # opt-in review of OSM place nodes the gazetteer lacks (never gates)
```

277 entries: the network's 49 junctions (gaz_ids 1-49) and 65 road segments (50-114), then the City Pack's 163
places in pack order (115-277: 72 areas, 64 landmarks, 27 police stations). The ids are positional, so **a new pack
place goes at the end** and existing places keep their order (`tests/test_gazetteer.py` pins the ids other streams
use). Each pack place carries English, Marathi and Hindi names, the romanised variants and misspellings seen in local
text (`gariahaat`, `shealdah`, `behalaa`, `tollyganj`, `bidhan nagar`) and an `anchor`; hand rows have approximate
points (`source: hand`), police stations come from the pack's OSM extract. A junction never carries a form a pack
place carries, nor the bare first word of its name (in Kolkata a surname, a person's name, a company or an area).
The lint refuses a multi-word phrase without a place-type word (so a person's name can never become a protected
"place"), a form not in normal form, a bare generic word, and a junction form shared with a pack place or with
another junction. The generator runs on the standard library alone (`osint_geo.gazetteer`, `translit` and `geom`),
so `--check` needs no numpy, pyproj or shapely.

## Tests

```bash
cd services/osint-geo && python -m pytest -q -p no:cacheprovider
```

All fixtures are synthetic: fictional `*.example` publishers, no real person's name, redacted placeholders only.
`tests/test_golden_kolkata.py` is the golden set: 41 headlines written for it (English, Marathi, Hindi and mixed)
with the geocode each must give (toponym, feature type, segment or junction, area scope), covering the low-lying
spots that waterlog at high tide (Thanthania, Amherst Street, Park Circus, Kalighat, Behala, Kasba, Garia,
Ultadanga, Mukundapur), bridges, stations, Durga Puja pandals, police stations, hospitals, junctions, roads, the
metro districts, state-level alerts and honest `None`s; the whole set resolves cold well within 2 s.

**Retired: the proof-of-concept parity check** (`tests/poc_parity.py`, `tests/test_poc_parity_geo.py`,
`tests/_poc.py`). It replayed the proof of concept's captured signals, read in place, and compared each geocode
with the proof of concept's own answer, which was built for another city's gazetteer and road network. None of
those places, ids or answers exists in Kolkata's gazetteer, so the check could only skip or fail, and passing it
would prove nothing about Kolkata. It is deleted, not skipped; the golden set above replaces it, and the rules it
guarded (an area word is never a junction pin, an area has no road anchor, no India ↔ indira match, the area
levels, the time budget) are asserted on Kolkata places in `test_resolver.py`, `test_fuzzy_stoplist.py` and
`test_golden_kolkata.py`.
