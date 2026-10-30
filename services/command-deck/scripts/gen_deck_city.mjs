#!/usr/bin/env node
/**
 * Deck city module generator: the City Pack (cities/<id>/city.json + landmarks.json, repo root) becomes
 * src/lib/city/city.generated.ts, the one place the console reads its city from: names (EN/MR/HI), the
 * centre, the boxes, the default map cameras, the plate rule, emergency numbers, agencies and landmarks.
 *
 *   node scripts/gen_deck_city.mjs                  write the module for the default city (mumbai)
 *   node scripts/gen_deck_city.mjs --city <id>      another pack under cities/
 *   node scripts/gen_deck_city.mjs --check          exit 1 when the committed module differs from the pack
 *   node scripts/gen_deck_city.mjs --stdout         print the module instead of writing it
 *
 * The output is deterministic (no timestamps), so --check compares bytes. Nothing here is hand-tuned per run:
 * the only per-city choices are DECK_VIEWS below, and they name landmarks by their canonical ids, so a pack
 * that renames or drops a landmark fails the build instead of drifting.
 */

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const REPO = path.resolve(DECK, '..', '..');
const OUT = path.join(DECK, 'src', 'lib', 'city', 'city.generated.ts');

const argv = process.argv.slice(2);
const arg = (name, dflt) => {
	const i = argv.indexOf(name);
	return i >= 0 && argv[i + 1] ? argv[i + 1] : dflt;
};
const CITY = arg('--city', 'mumbai');
const CHECK = argv.includes('--check');
const STDOUT = argv.includes('--stdout');

/**
 * How the console frames each city. Cameras name landmarks (ids from landmarks.json); the numbers are view
 * geometry only (metres, degrees), never city facts.
 *   home3d   the photoreal 3D home: an oblique look from `from` toward `toward`, the camera's target the
 *            point `at` (0..1) of the way between them, `range` metres from it at `pitchDeg`.
 *   home2d   the flat-map home: the city centre, `range` metres at `pitchDeg`, north up.
 *   core     the central district the base-map pictures frame: `lonHalf`/`latHalf` degrees around the
 *            3D home's target.
 *   plateSampleCodes  RTO numbers the console's samples and fixtures use (plausible codes only; the
 *            console never infers an office from a code).
 *   placeAcronyms  initialisms the city's road and place names are written with (signage spelling): the
 *            console's sentence-casing keeps them in capitals ("EM Bypass", never "Em Bypass"). The module
 *            adds every all-caps word of the pack's own landmark and agency names to them.
 */
const DECK_VIEWS = {
	mumbai: {
		// the photoreal home: from off Haji Ali looking north along the Worli seaface (its towers on the right) to the
		// Bandra–Worli Sea Link and Bandra beyond; the flat home: Dadar / Matunga (the pack's centre) with the island city and the near
		// suburbs in view (the city is tall and narrow: Colaba to Andheri is ~25 km)
		home3d: { from: 'haji_ali', toward: 'sea_link', at: 0.45, range: 5200, pitchDeg: -30 },
		home2d: { range: 24000, pitchDeg: -60 },
		core: { lonHalf: 0.04, latHalf: 0.04 },
		plateSampleCodes: ['01', '02', '03', '47'],
		// WEH, EEH, SV Road, LBS Marg, JVLR, SCLR, BKC, CSMT, LTT, NM Joshi Marg, SVP Road, VP Road, JSS Road, DN Road,
		// MG Road, P D'Mello Road (PD), KEM, JJ, GSB, TT, BMC, BEST, MMRDA, MSRDC, MSDMA, MTP, MH
		placeAcronyms: ['BEST', 'BKC', 'BMC', 'CSMT', 'DN', 'EEH', 'GSB', 'JJ', 'JSS', 'JVLR', 'KEM', 'LBS', 'LTT', 'LTMGH', 'MG', 'MH', 'MMRDA', 'MSDMA', 'MSRDC', 'MTP', 'NM', 'SCLR', 'SV', 'SVP', 'TT', 'VIP', 'VP', 'WEH'],
		// named obliques the omnibar and the 3D map fly to ("fly to Sea Link"): each looks from one landmark toward another
		views: [
			{ id: 'sea_link', from: 'worli_naka', toward: 'sea_link', at: 0.6, range: 3000, pitchDeg: -34 },
			{ id: 'marine_drive', from: 'girgaon_chowpatty', toward: 'churchgate', at: 0.45, range: 3200, pitchDeg: -32 },
			{ id: 'bkc', from: 'kalanagar', toward: 'bkc', at: 0.7, range: 2600, pitchDeg: -38 },
			{ id: 'dadar', from: 'hindmata', toward: 'dadar_tt', at: 0.6, range: 2400, pitchDeg: -40 },
			{ id: 'andheri', from: 'milan_subway', toward: 'andheri_subway', at: 0.75, range: 2800, pitchDeg: -38 },
			{ id: 'kings_circle', from: 'dadar_tt', toward: 'kings_circle', at: 0.7, range: 2200, pitchDeg: -40 },
			{ id: 'csmt', from: 'wankhede', toward: 'csmt', at: 0.6, range: 2400, pitchDeg: -36 },
			{ id: 'girgaon_chowpatty', from: 'lalbaug', toward: 'girgaon_chowpatty', at: 0.8, range: 2600, pitchDeg: -36 },
		],
	},
	kolkata: {
		home3d: { from: 'esplanade', toward: 'howrah_bridge', at: 0.6, range: 2800, pitchDeg: -38 },
		home2d: { range: 17000, pitchDeg: -60 },
		core: { lonHalf: 0.045, latHalf: 0.03 },
		plateSampleCodes: ['01', '02', '03', '04', '05', '06', '07', '08', '11', '12'],
		// EM Bypass, AJC Bose Road, APC Road, JL Nehru Road, SN Banerjee Road, CR Avenue, MG Road, DH Road,
		// GT Road, SP Mukherjee Road, BB Ganguly Street, BT Road, BBD Bag, VIP Road, KMC, WBSDMA, WBTC, NKDA, KMDA
		placeAcronyms: ['AJC', 'APC', 'BB', 'BBD', 'BT', 'CR', 'DH', 'EM', 'GT', 'JL', 'KMC', 'KMDA', 'MG', 'NKDA', 'SN', 'SP', 'VIP', 'WB', 'WBSDMA', 'WBTC'],
	},
};

function fail(msg) {
	console.error(`gen_deck_city: ${msg}`);
	process.exit(2);
}

function readJson(file) {
	try {
		return JSON.parse(readFileSync(file, 'utf8'));
	} catch (e) {
		fail(`cannot read ${path.relative(REPO, file)}: ${e.message}`);
	}
}

const round = (x, d = 6) => Number(x.toFixed(d));

/** Initial bearing a → b in degrees (−180..180], small-distance spherical formula. */
function bearingDeg(a, b) {
	const φ1 = (a.lat * Math.PI) / 180;
	const φ2 = (b.lat * Math.PI) / 180;
	const Δλ = ((b.lon - a.lon) * Math.PI) / 180;
	const y = Math.sin(Δλ) * Math.cos(φ2);
	const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
	return (Math.atan2(y, x) * 180) / Math.PI;
}

function names(o, where) {
	for (const k of ['en', 'mr', 'hi']) if (typeof o?.[k] !== 'string' || !o[k]) fail(`${where}: missing ${k} name`);
	return { en: o.en, mr: o.mr, hi: o.hi };
}

function build(cityId) {
	const dir = path.join(REPO, 'cities', cityId);
	const city = readJson(path.join(dir, 'city.json'));
	const lm = readJson(path.join(dir, 'landmarks.json'));
	const views = DECK_VIEWS[cityId];
	if (!views) fail(`no DECK_VIEWS entry for city '${cityId}'`);
	if (city.id !== cityId) fail(`city.json id '${city.id}' is not '${cityId}'`);

	const { south, west, north, east } = city.bbox ?? {};
	if (![south, west, north, east].every(Number.isFinite) || !(south < north && west < east)) fail('city.json bbox is not a box');
	const centre = { lat: city.centre?.lat, lon: city.centre?.lon };
	if (!(centre.lat >= south && centre.lat <= north && centre.lon >= west && centre.lon <= east)) fail('city.json centre lies outside its bbox');

	const landmarks = (lm.landmarks ?? []).map((l) => {
		if (!/^[a-z0-9_]+$/.test(l.id ?? '')) fail(`landmark id '${l.id}' is not a snake_case id`);
		if (!(l.lat >= south && l.lat <= north && l.lon >= west && l.lon <= east)) fail(`landmark '${l.id}' lies outside the city bbox`);
		return { id: l.id, kind: l.kind, lat: l.lat, lon: l.lon, ...names(l, `landmark ${l.id}`) };
	});
	const byId = new Map(landmarks.map((l) => [l.id, l]));
	if (byId.size !== landmarks.length) fail('duplicate landmark ids');
	const need = (id) => byId.get(id) ?? fail(`DECK_VIEWS names landmark '${id}', which landmarks.json does not hold`);

	const from = need(views.home3d.from);
	const toward = need(views.home3d.toward);
	const t = views.home3d.at;
	const target3d = { lon: round(from.lon + (toward.lon - from.lon) * t), lat: round(from.lat + (toward.lat - from.lat) * t) };
	const home3d = {
		lon: target3d.lon,
		lat: target3d.lat,
		range: views.home3d.range,
		headingDeg: round(bearingDeg(from, toward), 1),
		pitchDeg: views.home3d.pitchDeg,
		from: from.id,
		toward: toward.id,
	};
	const oblique = (v, where) => {
		const a = need(v.from);
		const b = need(v.toward);
		const k = v.at;
		return {
			lon: round(a.lon + (b.lon - a.lon) * k),
			lat: round(a.lat + (b.lat - a.lat) * k),
			range: v.range,
			headingDeg: round(bearingDeg(a, b), 1),
			pitchDeg: v.pitchDeg,
			from: a.id,
			toward: b.id,
			...(where ? { id: where } : {}),
		};
	};
	const views3d = (views.views ?? []).map((v) => {
		need(v.id);
		return oblique(v, v.id);
	});
	const home2d = { lon: centre.lon, lat: centre.lat, range: views.home2d.range, headingDeg: 0, pitchDeg: views.home2d.pitchDeg };
	const core = {
		minLon: round(target3d.lon - views.core.lonHalf),
		minLat: round(target3d.lat - views.core.latHalf),
		maxLon: round(target3d.lon + views.core.lonHalf),
		maxLat: round(target3d.lat + views.core.latHalf),
	};

	const p = city.plates ?? {};
	if (!p.state_code || !p.regex) fail('city.json plates needs state_code and regex');
	let plateRe;
	try {
		plateRe = new RegExp(p.regex);
	} catch (e) {
		fail(`city.json plates.regex does not compile: ${e.message}`);
	}
	const example = `${p.state_code} ${views.plateSampleCodes[1] ?? views.plateSampleCodes[0]} AB 1234`;
	for (const code of views.plateSampleCodes) {
		const sample = `${p.state_code} ${code} AB 1234`;
		if (!plateRe.test(sample)) fail(`sample plate '${sample}' fails the pack's plate regex`);
	}

	const agencies = (city.agencies ?? []).map((a) => ({ id: a.id, kind: a.kind, ...names(a, `agency ${a.id}`) }));

	// every all-caps word (2+ letters) of the pack's own EN names, plus the configured road initialisms
	const acronyms = new Set(views.placeAcronyms ?? []);
	for (const n of [...landmarks.map((l) => l.en), ...agencies.map((a) => a.en)]) {
		for (const w of n.split(/[^A-Za-z]+/)) if (w.length >= 2 && /^[A-Z]+$/.test(w)) acronyms.add(w);
	}

	return {
		id: city.id,
		name: names(city.name, 'city name'),
		region: names(city.region, 'region'),
		state: { code: city.state.code, ...names(city.state, 'state') },
		timezone: city.timezone,
		languages: { ui: [...city.languages.ui], defaultPublic: city.languages.default_public, defaultConsole: city.languages.default_console },
		centre: { lon: centre.lon, lat: centre.lat, label: city.centre.label },
		bbox: { minLon: west, minLat: south, maxLon: east, maxLat: north },
		coreBbox: core,
		cameras: { home2d, home3d },
		views: views3d,
		plates: {
			stateCode: p.state_code,
			format: p.format,
			regex: p.regex,
			sampleCodes: [...views.plateSampleCodes],
			example,
			note: p.note ?? '',
		},
		emergency: { ...city.emergency },
		agencies,
		acronyms: [...acronyms].sort(),
		river: city.hydrology?.river ? names(city.hydrology.river, 'river') : null,
		population: city.population ?? null,
		attribution: city.attribution ?? '',
		landmarks,
	};
}

function render(pack) {
	const json = JSON.stringify(pack, null, '\t');
	return `/**
 * GENERATED by scripts/gen_deck_city.mjs from cities/${pack.id}/city.json and cities/${pack.id}/landmarks.json.
 * Do not edit: change the City Pack and run \`node scripts/gen_deck_city.mjs\` (tests/city.unit.mjs fails while
 * this file and the pack disagree). Read it through $lib/city, never directly.
 */

export const CITY_PACK = ${json} as const;
`;
}

const text = render(build(CITY));
if (STDOUT) {
	process.stdout.write(text);
} else if (CHECK) {
	let have = '';
	try {
		have = readFileSync(OUT, 'utf8');
	} catch {
		/* missing counts as stale */
	}
	if (have !== text) {
		console.error(`gen_deck_city: ${path.relative(DECK, OUT)} is stale — run node scripts/gen_deck_city.mjs`);
		process.exit(1);
	}
	console.log(`gen_deck_city: ${path.relative(DECK, OUT)} matches cities/${CITY}`);
} else {
	mkdirSync(path.dirname(OUT), { recursive: true });
	writeFileSync(OUT, text);
	console.log(`gen_deck_city: wrote ${path.relative(DECK, OUT)} from cities/${CITY}`);
}
