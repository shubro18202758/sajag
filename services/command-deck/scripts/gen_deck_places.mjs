#!/usr/bin/env node
/**
 * Deck place-marks generator: the City Pack's named places become src/lib/city/places.generated.ts, the map's
 * labelled reference geography (the `landmarks` layer). Every row is a real place from the pack, never invented:
 *
 *   tier 1  landmarks.json (the canonical names and ids: bridges, stations, venues, crossings, pumping stations …)
 *   tier 2  gazetteer.json neighbourhoods (area names) and its venues, ghats, terminals, markets, bridges and the
 *           low-lying spots (the civic body's waterlogging hotspots) not already a landmark
 *   tier 3  network.json stations (police, traffic police, fire, hospitals, ambulance (108) bases, civic posts —
 *           OSM-sourced, the emulated posts say so) and the gazetteer's pandals
 *
 *   tier 2  the city's named places from OpenStreetMap (suburb and quarter nodes: the pack's osm/places extract, else
 *           the deck's scripts/data/<id>-places.overpass.json.gz) as area names, a gazetteer area winning a tie
 *   tier 3  osm/stations.overpass.json.gz (the pack's committed OpenStreetMap extract, ODbL): named police and traffic
 *           police stations, fire stations and hospitals (a hospital mapped as a building, or a public one by its
 *           name) not already placed — real places only, names as OSM writes them (an all-lower-case name title-cased)
 *
 * gazetteer.json, network.json and the OSM extract are optional: a pack that holds only landmarks.json gets its
 * landmarks.
 *
 *   node scripts/gen_deck_places.mjs            write the module (mumbai; --city <id> for another pack)
 *   node scripts/gen_deck_places.mjs --check    exit 1 when the committed module differs from the pack
 *   node scripts/gen_deck_places.mjs --stdout   print the module instead of writing it
 *
 * Deterministic (no timestamps): --check compares bytes. A place within 120 m of a higher-tier place with the same
 * (case-folded) name is dropped as a duplicate.
 */

import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const REPO = path.resolve(DECK, '..', '..');
const OUT = path.join(DECK, 'src', 'lib', 'city', 'places.generated.ts');
const argv = process.argv.slice(2);
const CITY = (() => {
	const i = argv.indexOf('--city');
	return i >= 0 && argv[i + 1] ? argv[i + 1] : 'mumbai';
})();

const read = (f) => JSON.parse(readFileSync(path.join(REPO, 'cities', CITY, f), 'utf8'));
/** An optional pack file: its parsed body, or `dflt` when the pack does not hold it. */
const readOpt = (f, dflt) => (existsSync(path.join(REPO, 'cities', CITY, f)) ? read(f) : dflt);
const round = (x) => Number(Number(x).toFixed(6));
const fold = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

const city = read('city.json');
const { south, west, north, east } = city.bbox;
const inBox = (p) => p.lat >= south && p.lat <= north && p.lon >= west && p.lon <= east;

/** Landmark kinds → the mark's kind (its glyph on the map). */
const LANDMARK_KIND = { junction: 'junction', bridge: 'bridge', terminal: 'terminal', venue: 'venue', hospital: 'hospital', ghat: 'ghat', pandal: 'pandal', hydro: 'hydro', lowlying: 'lowlying', low_lying_spot: 'lowlying', subway: 'lowlying', market: 'market', agency: 'landmark' };
/** An agency landmark wears its service's glyph when its id says which (police / traffic police HQ); else a plain disc. */
const agencyKind = (id) => (/traffic/.test(id) ? 'traffic' : /police/.test(id) ? 'police' : /fire/.test(id) ? 'fire' : 'landmark');
const GAZ_KIND = { neighbourhood: 'area', area: 'area', ward: 'area', venue: 'venue', ghat: 'ghat', beach: 'venue', terminal: 'terminal', station: 'terminal', market: 'market', bridge: 'bridge', flyover: 'bridge', subway: 'lowlying', low_lying_spot: 'lowlying', low_lying_street: 'lowlying', flood_spot: 'lowlying', pandal: 'pandal', visarjan_point: 'ghat', hospital: 'hospital', pumping_station: 'hydro', junction: 'junction' };
const GAZ_TIER = { area: 2, venue: 2, ghat: 2, terminal: 2, market: 2, bridge: 2, lowlying: 2, hydro: 2, junction: 2, pandal: 3, hospital: 3 };
const STATION_KIND = { police_station: 'police', fire_station: 'fire', hospital: 'hospital', ems_base: 'ems', jr_post: 'post' };

const rows = [];
const seen = [];
function add(row) {
	if (!inBox(row)) return;
	const f = fold(row.en);
	const near = (a, b) => Math.hypot((a.lon - b.lon) * 102_800, (a.lat - b.lat) * 110_600) < 120;
	if (seen.some((s) => near(s, row) && (s.f === f || f.startsWith(s.f) || s.f.startsWith(f)))) return;
	seen.push({ lon: row.lon, lat: row.lat, f });
	rows.push(row);
}

for (const l of read('landmarks.json').landmarks) {
	add({ id: `lm_${l.id}`, kind: l.kind === 'agency' ? agencyKind(l.id) : LANDMARK_KIND[l.kind] ?? 'landmark', tier: 1, lon: round(l.lon), lat: round(l.lat), en: l.en, mr: l.mr, hi: l.hi, src: 'landmarks' });
}
const lmIds = new Set(read('landmarks.json').landmarks.map((l) => l.id));
for (const p of readOpt('gazetteer.json', { places: [] }).places ?? []) {
	const kind = p.low_lying && p.kind === 'neighbourhood' ? 'area' : GAZ_KIND[p.kind];
	if (!kind || lmIds.has(p.id)) continue;
	add({ id: `gz_${p.id}`, kind, tier: GAZ_TIER[kind], lon: round(p.lon), lat: round(p.lat), en: p.en, mr: p.mr || p.en, hi: p.hi || p.en, src: 'gazetteer', ...(p.low_lying ? { lowLying: true } : {}) });
}
for (const s of readOpt('network.json', { stations: [] }).stations ?? []) {
	const kind = s.agency === 'traffic' ? 'traffic' : STATION_KIND[s.kind];
	if (!kind) continue;
	const id = `st_${String(s.station_id).toLowerCase().replace(/[^a-z0-9]+/g, '_')}`;
	add({ id, kind, tier: 3, lon: round(s.lon), lat: round(s.lat), en: s.name, mr: s.name_mr || s.name, hi: s.name, src: s.source === 'osm' ? 'network-osm' : 'network' });
}

// the city's named places from OpenStreetMap (suburb and quarter nodes) as area labels: the pack's own extract
// (cities/<id>/osm/places.overpass.json.gz) when it holds one, else the deck's (scripts/data/<id>-places.overpass.json.gz,
// fetched 30 Oct 2026, ODbL); a gazetteer area of the same name nearby wins (it was added first)
const OSM_PLACES = [path.join(REPO, 'cities', CITY, 'osm', 'places.overpass.json.gz'), path.join(DECK, 'scripts', 'data', `${CITY}-places.overpass.json.gz`)].find((f) => existsSync(f));
if (OSM_PLACES) {
	const body = JSON.parse(gunzipSync(readFileSync(OSM_PLACES)).toString('utf8'));
	const els = ((body.response ?? body).elements ?? []).filter((e) => ['suburb', 'quarter'].includes(e.tags?.place) && e.tags?.name);
	els.sort((a, b) => String(a.tags.name).localeCompare(String(b.tags.name)) || a.id - b.id);
	for (const e of els) {
		const t = e.tags;
		const en = String(t['name:en'] || t.name).trim();
		add({ id: `osm_place_${e.id}`, kind: 'area', tier: 2, lon: round(e.lon), lat: round(e.lat), en, mr: t['name:mr'] || en, hi: t['name:hi'] || en, src: 'network-osm' });
	}
}

// the pack's OpenStreetMap stations extract (osm/stations.overpass.json.gz): named services the network does not hold
const OSM_STATIONS = path.join(REPO, 'cities', CITY, 'osm', 'stations.overpass.json.gz');
if (existsSync(OSM_STATIONS)) {
	const body = JSON.parse(gunzipSync(readFileSync(OSM_STATIONS)).toString('utf8'));
	const els = (body.response ?? body).elements ?? [];
	/** A name that says no more than what the place is ("Police Station", "POLICE CHOWKI") is not a label. */
	const GENERIC = /^(?:the\s+)?(?:police|fire|traffic|station|chowk[iy]?|chowkey|beat|no\.?|\d+|office|post|outpost|hospital|clinic|brigade|stn|ps|thane|and|&|-|,|\s)+$/i;
	const titled = (n) => (n === n.toLowerCase() ? n.replace(/\b([a-z])/g, (c) => c.toUpperCase()) : n).replace(/\s+/g, ' ').trim();
	const PUBLIC_HOSPITAL = /(municipal|general|government|govt|corporation|bmc|mcgm|esic|railway|police|naval|military|medical college|trust)\b.*hospital|hospital.*(municipal|general)|rugnalaya/i;
	const picked = [];
	for (const e of els) {
		const t = e.tags ?? {};
		const name = String(t.name ?? '').trim();
		if (!name || GENERIC.test(name) || /\btest(ing)?\b/i.test(name)) continue;
		const lon = e.lon ?? e.center?.lon;
		const lat = e.lat ?? e.center?.lat;
		if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
		let kind = null;
		if (t.amenity === 'police') {
			if (/traffic|vahatuk|वाहतूक/i.test(name)) kind = 'traffic';
			else if (/police\s*(station|thane)|पोलीस ठाणे/i.test(name)) kind = 'police';
		} else if (t.amenity === 'fire_station') kind = 'fire';
		else if (t.amenity === 'hospital' && /hospital|medical college|rugnalaya|रुग्णालय/i.test(name) && (e.type !== 'node' || PUBLIC_HOSPITAL.test(name))) kind = 'hospital';
		if (!kind) continue;
		const en = titled(name);
		picked.push({ id: `osm_${e.type[0]}${e.id}`, kind, tier: 3, lon: round(lon), lat: round(lat), en, mr: t['name:mr'] || en, hi: t['name:hi'] || en, src: 'network-osm' });
	}
	// deterministic: by kind, then name, then id
	picked.sort((a, b) => a.kind.localeCompare(b.kind) || a.en.localeCompare(b.en) || a.id.localeCompare(b.id));
	for (const r of picked) add(r);
}

const ids = new Set();
for (const r of rows) {
	if (ids.has(r.id)) {
		console.error(`gen_deck_places: duplicate id ${r.id}`);
		process.exit(2);
	}
	ids.add(r.id);
}

const counts = rows.reduce((m, r) => ((m[r.kind] = (m[r.kind] ?? 0) + 1), m), {});
const body = `/**
 * GENERATED by scripts/gen_deck_places.mjs from cities/${CITY}/landmarks.json, gazetteer.json, network.json, the
 * OpenStreetMap stations and named-places extracts (OpenStreetMap contributors, ODbL).
 * Do not edit: change the City Pack and run \`node scripts/gen_deck_places.mjs\` (tests/map-live.unit.mjs fails while
 * this file and the pack disagree). ${rows.length} places: ${Object.entries(counts)
	.sort()
	.map(([k, n]) => `${k} ${n}`)
	.join(', ')}.
 * Read it through $lib/city/places, never directly.
 */

export const PLACE_MARK_ROWS = ${JSON.stringify(rows, null, '\t')} as const;
`;

if (argv.includes('--stdout')) process.stdout.write(body);
else if (argv.includes('--check')) {
	let cur = '';
	try {
		cur = readFileSync(OUT, 'utf8');
	} catch {
		/* missing */
	}
	if (cur !== body) {
		console.error('gen_deck_places: places.generated.ts is stale — run node scripts/gen_deck_places.mjs');
		process.exit(1);
	}
	console.log('gen_deck_places: up to date');
} else {
	writeFileSync(OUT, body);
	console.log(`gen_deck_places: wrote ${path.relative(DECK, OUT)} (${rows.length} places)`);
}
