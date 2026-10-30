/**
 * V3 imagery gate (V3-P7) — zero browser.
 *
 *   node tests/v3-media.unit.mjs
 *
 *   1. ARTWORK       static/artwork/{vehicles,events,scenes}: every event kind the deck can draw has its 16:9 key art,
 *                    every vehicle class its studio shot (and every protection class its convoy composition), the
 *                    five Home scenes exist; each SVG is labelled (role="img" + aria-label), holds no <image> (never
 *                    a photo or a camera frame), no <text> (no words in images), no script, no external reference, no
 *                    person word, no navy and no purple; each ≤ 40 KB and the set ≤ 1,024 KB (22 key arts, 16 vehicle
 *                    shots and compositions, 5 scenes; the old set's 900 KB held 19 + 14 + 5). The art is Mumbai's: the scenes and key art name their places.
 *   2. DETERMINISTIC re-running the generator (scripts/brand/build_artwork.py, in the repo) into a temp folder reproduces
 *                    static/artwork byte for byte; the registries match their manifests (scripts/brand/media_data.py).
 *   3. PHOTOS        every photo row has its author, licence, licence URL, source page and credit; both sizes exist in
 *                    static/photos; static/photos/NOTICE.md names each one with its licence; nothing in static/photos
 *                    is unlisted; the photos left out for a legible plate, a face or a political poster stay out; the photos
 *                    are of Mumbai.
 *   4. MARKS         every file in static/logos has a row and every row a file; NOTICE.md names each; the ownership
 *                    credit line is in the pack.
 *   5. HONESTY       a photo is drawn only by Cover.svelte (which always prints "Reference photo · not live" and the
 *                    credit); the public pages load imagery from their own origin only.
 *   6. PACKS         packs.media EN / HI / MR carry the same keys; every v3i_ key the code uses exists; HI holds no
 *                    Marathi and MR no Devanagari (the danda । ॥, U+0964/5, is shared punctuation and allowed); nothing left
 *                    in English.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const ART = path.join(DECK, 'static/artwork');
const PHOTOS_DIR = path.join(DECK, 'static/photos');
const LOGOS_DIR = path.join(DECK, 'static/logos');
const REPO = path.resolve(DECK, '../..');
const GENERATOR = path.join(REPO, 'scripts/brand/build_artwork.py');
const OUT = path.join(HERE, 'artifacts', 'v3-media-bundle.mjs');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

const walk = (dir, filter = () => true) => {
	const out = [];
	const go = (d) => {
		for (const f of readdirSync(d).sort()) {
			const p = path.join(d, f);
			if (statSync(p).isDirectory()) go(p);
			else if (filter(p)) out.push(p);
		}
	};
	if (existsSync(dir)) go(dir);
	return out;
};

mkdirSync(path.dirname(OUT), { recursive: true });
const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');
const built = await esbuild.build({
	stdin: {
		contents: [
			`export * as art from './src/lib/v3/media/art';`,
			`export * as photos from './src/lib/v3/media/photos';`,
			`export * as logos from './src/lib/v3/media/logos';`,
			`export * as packs from './src/lib/v3/media/packs.media';`,
			`export { hi } from './src/lib/v3/media/packs.media.hi';`,
			`export { mr } from './src/lib/v3/media/packs.media.mr';`,
			`export { EVENT_ART } from './src/lib/v3/home/model';`,
		].join('\n'),
		resolveDir: DECK,
		loader: 'ts',
		sourcefile: 'v3-media-entry.ts',
	},
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
	external: ['$app/*', 'svelte', 'svelte/*'],
	define: { 'import.meta.env.SSR': 'true' },
});
ok('bundle builds (media/art, photos, logos, packs.media)', built.errors.length === 0, built.errors.map((e) => e.text).join(' | '));
const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);

// ── colour helpers ───────────────────────────────────────────────────────────

function hsl(hex) {
	const h = hex.replace('#', '');
	const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h.slice(0, 6);
	const [r, g, b] = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255);
	const max = Math.max(r, g, b);
	const min = Math.min(r, g, b);
	const l = (max + min) / 2;
	const d = max - min;
	if (d === 0) return { h: 0, s: 0, l };
	const s = d / (1 - Math.abs(2 * l - 1));
	let hue = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
	hue *= 60;
	if (hue < 0) hue += 360;
	return { h: hue, s, l };
}
/** Navy (a dark, saturated blue) or purple: the neutral grounds never carry either. */
const navyOrPurple = (hex) => {
	const c = hsl(hex);
	return (c.h >= 250 && c.h <= 320 && c.s > 0.25 && c.l > 0.08) || (c.h >= 205 && c.h < 250 && c.s > 0.35 && c.l < 0.3);
};

// ── 1. artwork ───────────────────────────────────────────────────────────────

const svgs = walk(ART, (p) => p.endsWith('.svg'));
const rel = (p) => path.relative(ART, p);
{
	const groups = { events: M.art.KEY_ART_KINDS.length, vehicles: M.art.VEHICLE_SHOTS.length, scenes: 5 };
	for (const [g, n] of Object.entries(groups)) {
		const have = svgs.filter((f) => path.basename(path.dirname(f)) === g).length;
		ok(`artwork/${g}: ${n} files`, have === n, `${have}`);
	}
	const missingKind = [...M.art.KEY_ART_KINDS, ...M.EVENT_ART].filter((k) => !existsSync(path.join(ART, 'events', `${M.art.keyArtKind(k)}.svg`)));
	ok('every event kind the deck draws (Home tiles, corridor and OSINT kinds) has its key art', missingKind.length === 0, missingKind.join(', ') || `${M.EVENT_ART.size} kinds`);
	const deckClasses = ['ambulance', 'auto_rickshaw', 'bus', 'car', 'fire_tender', 'patrol', 'suv', 'tempo', 'truck', 'two_wheeler', 'motorcycle', 'scooter', 'lcv', 'hgv', 'jeep', 'taxi', 'toto', 'e-rickshaw', 'cab', 'unknown-class'];
	const missingCls = deckClasses.filter((c) => !existsSync(path.join(ART, 'vehicles', `${M.art.vehicleShotClass(c)}.svg`)));
	ok('every vehicle class (and alias) has its studio shot; an unknown class falls back to the car', missingCls.length === 0 && M.art.vehicleShotClass('unknown-class') === 'car', missingCls.join(', '));
	ok("Mumbai's fleet: the kaali-peeli taxi, the BEST double-decker and the auto have their shots", M.art.vehicleShotClass('taxi') === 'taxi' && M.art.vehicleShotClass('kaali-peeli') === 'taxi' && M.art.vehicleShotClass('double_decker') === 'bus' && M.art.vehicleShotClass('best') === 'bus' && M.art.vehicleShotClass('e-rickshaw') === 'toto' && M.art.vehicleShotClass('auto') === 'auto_rickshaw');
	ok("Mumbai's event kinds find their art (waterlogging at high tide, tree fall, Ganeshotsav, visarjan, locals stopped, jetty)", M.art.keyArtKind('waterlogging') === 'flooding' && M.art.keyArtKind('high_tide') === 'flooding' && M.art.keyArtKind('tree_fall') === 'cyclone' && M.art.keyArtKind('ganeshotsav') === 'mass_gathering' && M.art.keyArtKind('visarjan') === 'procession' && M.art.keyArtKind('local_train') === 'station_surge' && M.art.keyArtKind('jetty') === 'ghat_transit');
	const conv = ['Z+', 'Z', 'Y', 'X'].map((c) => M.art.convoyShot(c));
	ok('every protection class has its convoy composition', conv.every((c) => existsSync(path.join(ART, 'vehicles', `${c}.svg`))) && new Set(conv).size === 4, conv.join(', '));
	ok('every Home scene exists and the hour picks one', ['dawn', 'day', 'dusk', 'night', 'all-clear'].every((s) => existsSync(path.join(ART, 'scenes', `${s}.svg`))) && M.art.sceneFor(6) === 'dawn' && M.art.sceneFor(12) === 'day' && M.art.sceneFor(18) === 'dusk' && M.art.sceneFor(23) === 'night');
	const issues = [];
	for (const f of svgs) {
		const s = readFileSync(f, 'utf8');
		const r = rel(f);
		if (!/<svg\b[^>]*\brole="img"/.test(s) || !/<svg\b[^>]*\baria-label="[^"]{8,}"/.test(s)) issues.push(`${r}: no role/label`);
		if (/<image\b/i.test(s)) issues.push(`${r}: <image>`);
		if (/<text\b/i.test(s)) issues.push(`${r}: <text>`);
		if (/<script\b|\bon\w+=|javascript:/i.test(s)) issues.push(`${r}: script`);
		if (/(href|src)="(https?:|\/\/)/i.test(s) || /url\((?!#)/.test(s)) issues.push(`${r}: external ref`);
		if (/\b(person|people|face|faces|human|man|woman|men|women)\b/i.test(s)) issues.push(`${r}: person word`);
		for (const m of s.matchAll(/#[0-9a-fA-F]{6}\b/g)) if (navyOrPurple(m[0])) issues.push(`${r}: navy/purple ${m[0]}`);
		if (statSync(f).size > 40_960) issues.push(`${r}: ${(statSync(f).size / 1024).toFixed(1)} KB > 40 KB`);
	}
	ok('every artwork SVG: labelled, no <image>/<text>/script/external ref, no person word, no navy or purple, ≤ 40 KB', issues.length === 0, issues.slice(0, 6).join(' | ') || `${svgs.length} files`);
	const total = svgs.reduce((n, f) => n + statSync(f).size, 0);
	ok('the artwork set ≤ 1,024 KB', total <= 1024 * 1024, `${(total / 1024).toFixed(1)} KB`);
	const labels = svgs.map((f) => /aria-label="([^"]*)"/.exec(readFileSync(f, 'utf8'))?.[1] ?? '').join(' ');
	ok('no old-city name in any artwork', !/ahmedabad|amdavad|gujarat|sabarmati|motera|kankaria|gandhinagar|kolkata|calcutta|howrah|hooghly|vidyasagar|victoria memorial|durga|bengal/i.test(labels));
	const scenes = ['dawn', 'day', 'dusk', 'night'].map((n) => readFileSync(path.join(ART, 'scenes', `${n}.svg`), 'utf8'));
	ok('the Home scenes are Mumbai (the Bandra–Worli Sea Link)', scenes.every((x) => /Mumbai/.test(x) && /Sea Link/.test(x)));
}

// ── 2. deterministic ─────────────────────────────────────────────────────────

if (existsSync(GENERATOR)) {
	const tmp = mkdtempSync(path.join(os.tmpdir(), 'v3-art-'));
	try {
		execFileSync('python3', ['-I', GENERATOR, tmp], { stdio: 'pipe' });
		const fresh = walk(tmp);
		const differ = fresh.filter((f) => {
			const twin = path.join(ART, path.relative(tmp, f));
			return !existsSync(twin) || readFileSync(twin, 'utf8') !== readFileSync(f, 'utf8');
		});
		ok('the generator reproduces static/artwork byte for byte', fresh.length === svgs.length && differ.length === 0, differ.slice(0, 4).map((f) => path.relative(tmp, f)).join(', ') || `${fresh.length} files`);
	} catch (e) {
		ok('the generator runs', false, String(e.message).slice(0, 200));
	} finally {
		rmSync(tmp, { recursive: true, force: true });
	}
} else {
	ok('the artwork generator is in the repo', false, GENERATOR);
}

// ── 3. photos ────────────────────────────────────────────────────────────────

{
	const rows = M.photos.PHOTOS;
	const notice = existsSync(path.join(PHOTOS_DIR, 'NOTICE.md')) ? readFileSync(path.join(PHOTOS_DIR, 'NOTICE.md'), 'utf8') : '';
	const bad = [];
	for (const p of rows) {
		for (const k of ['author', 'license', 'licenseUrl', 'source', 'credit', 'title', 'place']) if (!p[k] || !String(p[k]).trim()) bad.push(`${p.slug}: no ${k}`);
		if (!/^https:\/\/creativecommons\.org\/|^https:\/\/commons\.wikimedia\.org\//.test(p.licenseUrl)) bad.push(`${p.slug}: licence URL`);
		if (!p.credit.includes(p.license)) bad.push(`${p.slug}: credit without licence`);
		for (const w of [640, 1600]) if (!existsSync(path.join(PHOTOS_DIR, `${p.slug}-${w}.webp`))) bad.push(`${p.slug}-${w}.webp missing`);
		if (!notice.includes(`**${p.slug}**`) || !notice.includes(p.license)) bad.push(`${p.slug}: not in NOTICE`);
	}
	ok(`every photo (${rows.length}) has author, licence, licence URL, source and credit; both sizes exist; NOTICE names it`, rows.length >= 15 && bad.length === 0, bad.slice(0, 6).join(' | '));
	const listed = new Set(rows.flatMap((p) => [`${p.slug}-640.webp`, `${p.slug}-1600.webp`]));
	const stray = readdirSync(PHOTOS_DIR).filter((f) => f !== 'NOTICE.md' && !listed.has(f));
	ok('nothing in static/photos is unlisted', stray.length === 0, stray.join(', '));
	// curated out when the set was chosen (scripts/brand/photos/rejected.json): readable plates, people as the subject, a political hoarding
	const rejected = JSON.parse(readFileSync(path.join(REPO, 'scripts/brand/photos/rejected.json'), 'utf8'));
	const norm = (x) => decodeURIComponent(String(x)).replace(/_/g, ' ').toLowerCase();
	const back = rows.filter((p) => rejected.some((r) => norm(p.source).includes(norm(r.file))));
	ok(`the photos rejected for a legible plate, a face, people as the subject or a political poster stay out (${rejected.length})`, rejected.length >= 10 && back.length === 0, back.map((p) => p.slug).join(', '));
	ok('every photo is of Mumbai (no old-city place)', rows.every((p) => p.lat > 18.89 && p.lat < 19.28 && p.lon > 72.77 && p.lon < 72.99) && !rows.some((p) => /ahmedabad|sabarmati|gujarat|kolkata|howrah|hooghly/i.test(`${p.title} ${p.slug}`)));
	const bridgeNoon = M.photos.photoNear(72.817, 19.038, 900, 12);
	const bridgeNight = M.photos.photoNear(72.817, 19.038, 900, 22);
	ok('a Sea Link point finds the bridge by day at noon and lit at night; a far point finds none', bridgeNoon?.slug === 'sea-link-day' && bridgeNight?.slug === 'sea-link-night' && M.photos.photoNear(73.4, 19.9, 900, 12) === null, `${bridgeNoon?.slug} / ${bridgeNight?.slug}`);
	ok('a generic subject (taxi, double-decker, local train, visarjan) is never matched by distance', rows.filter((p) => ['taxi', 'bus', 'local_train', 'visarjan', 'metro', 'waterlogging', 'high_tide'].includes(p.place)).every((p) => p.near === false));
	ok('place names find their photos (EN, मराठी, हिंदी)', M.photos.photoForText('Diversion at Marine Drive')?.place === 'marine_drive' && M.photos.photoForText('वांद्रे–वरळी सागरी सेतू')?.place === 'sea_link' && M.photos.photoForText('Wankhede egress')?.place === 'wankhede' && M.photos.photoForText('गेटवे ऑफ इंडिया के पास')?.place === 'gateway');
	const bytes = readdirSync(PHOTOS_DIR).reduce((n, f) => n + statSync(path.join(PHOTOS_DIR, f)).size, 0);
	ok('static/photos ≤ 6 MB', bytes <= 6 * 1024 * 1024, `${(bytes / 1048576).toFixed(2)} MB`);
}

// ── 4. marks ─────────────────────────────────────────────────────────────────

{
	const rows = M.logos.MARKS;
	const files = readdirSync(LOGOS_DIR).filter((f) => f !== 'NOTICE.md');
	const notice = existsSync(path.join(LOGOS_DIR, 'NOTICE.md')) ? readFileSync(path.join(LOGOS_DIR, 'NOTICE.md'), 'utf8') : '';
	const noRow = files.filter((f) => !rows.some((m) => m.src === `/logos/${f}`));
	const noFile = rows.filter((m) => !existsSync(path.join(DECK, 'static', m.src)));
	const noNotice = rows.filter((m) => !notice.includes(`**${m.key.replace(/_/g, '-')}**`));
	ok(`every mark file has a row and every row a file (${rows.length})`, rows.length > 0 && noRow.length === 0 && noFile.length === 0, [...noRow, ...noFile.map((m) => m.key)].join(', '));
	ok('NOTICE.md names every mark and carries the ownership line', noNotice.length === 0 && /belong to their owners/.test(notice) && /not affiliated with or endorsed by/.test(notice), noNotice.map((m) => m.key).join(', '));
	ok('the roles the deck speaks of find their marks (police, traffic, municipal, disaster, Sachet, IMD)', ['police', 'traffic', 'municipal', 'disaster', 'metro', 'bus', 'rail'].every((r) => M.logos.markFor(r)) && M.logos.sourceMark('sachet.ndma.gov.in')?.key === 'ndma_sachet' && M.logos.sourceMark('mausam.imd.gov.in')?.key === 'imd' && M.logos.sourceMark('Brihanmumbai Municipal Corporation')?.key === 'bmc');
	const cityIds = JSON.parse(readFileSync(path.join(REPO, 'cities/mumbai/city.json'), 'utf8')).agencies.map((a) => a.id);
	const agencyMarks = rows.filter((m) => !['openstreetmap', 'open_meteo', 'copernicus', 'cesium', 'ndma_sachet'].includes(m.key));
	ok("the marks are keyed by city.json's agency ids", agencyMarks.length >= 8 && agencyMarks.every((m) => cityIds.includes(m.key) && M.logos.markFor(m.key)?.key === m.key), agencyMarks.filter((m) => !cityIds.includes(m.key)).map((m) => m.key).join(', '));
	ok('fire, ERSS 112, the ambulance (108) service and volunteers keep the generic badge (no mark on file)', ['fire', '112', '108', 'volunteers'].every((r) => M.logos.markFor(r) === null));
	ok('no old-city mark is left', !rows.some((m) => /gujarat|ahmedabad|amdavad|gsdma|amts|janmarg|gmrc|kolkata|west bengal|howrah|bidhannagar|wbtc|nkda/i.test(`${m.key} ${m.name}`)));
	ok('the ownership credit line is in the pack', /belong to their owners\. Sajag is a prototype and is not affiliated with or endorsed by them\./.test(M.packs.MEDIA_PACKS.en.v3i_marks_credit));
}

// ── 5. honesty ───────────────────────────────────────────────────────────────

{
	const code = walk(path.join(DECK, 'src'), (p) => /\.(svelte|ts)$/.test(p));
	const drawsPhoto = code.filter((f) => !/media\/(photos|photos\.data|Cover)\.(ts|svelte)$/.test(f) && /photoSrc(set)?\(|\/photos\/[a-z0-9-]+-(640|1600)\.webp/.test(readFileSync(f, 'utf8')));
	ok('a photo is drawn only by Cover.svelte', drawsPhoto.length === 0, drawsPhoto.map((f) => path.relative(DECK, f)).join(', '));
	const cover = readFileSync(path.join(DECK, 'src/lib/v3/media/Cover.svelte'), 'utf8');
	const photoBranch = cover.slice(cover.indexOf('{#if photo}'), cover.indexOf('{:else}'));
	ok('Cover prints "Reference photo · not live" and the credit on every photo', /v3i_ref_photo/.test(photoBranch) && /photo\.credit/.test(photoBranch) && !/\{#if[^}]*compact[^}]*\}[\s\S]*v3i_ref_photo/.test(photoBranch));
	const pub = [...walk(path.join(DECK, 'src/routes/(public)'), (p) => /\.svelte$/.test(p)), ...walk(path.join(DECK, 'src/lib/citizen'), (p) => /\.svelte$/.test(p)), ...walk(path.join(DECK, 'src/lib/v3/public'), (p) => /\.svelte$/.test(p))];
	const offsite = pub.filter((f) => /<img[^>]+src="(https?:)?\/\//.test(readFileSync(f, 'utf8')));
	ok('public pages load imagery from their own origin only', offsite.length === 0, offsite.map((f) => path.relative(DECK, f)).join(', '));
}

// ── 6. packs ─────────────────────────────────────────────────────────────────

{
	const en = Object.keys(M.packs.MEDIA_PACKS.en);
	const hi = Object.keys(M.hi);
	const mr = Object.keys(M.mr);
	const same = (a, b) => a.length === b.length && a.every((k) => b.includes(k));
	ok('packs.media: EN / HI / MR carry the same keys', same(en, hi) && same(en, mr), `${en.length} keys`);
	ok('packs.media: every key starts with v3i_', en.every((k) => k.startsWith('v3i_')));
	const code = walk(path.join(DECK, 'src'), (p) => /\.(svelte|ts)$/.test(p) && !/packs\.media/.test(p));
	const used = new Set();
	const prefixes = new Set();
	for (const f of code) {
		const s = readFileSync(f, 'utf8');
		for (const m of s.matchAll(/['"`](v3i_[a-z0-9_-]+)['"`]/g)) used.add(m[1]);
		for (const m of s.matchAll(/`(v3i_[a-z0-9_]+)\$\{/g)) prefixes.add(m[1]);
	}
	const missing = [...used].filter((k) => !en.includes(k));
	ok('every literal v3i_ key the code uses exists in the pack', missing.length === 0, missing.join(', ') || `${used.size} used`);
	const dyn = { v3i_scene_: ['dawn', 'day', 'dusk', 'night', 'all-clear'], v3i_cls_: M.art.VEHICLE_SHOTS, v3i_agency_: ['police', 'traffic', 'ems', 'municipal', 'disaster', 'ndma', 'imd', 'metro', 'wbtc', 'osm', 'citizens'] };
	const dynMissing = Object.entries(dyn).flatMap(([p, list]) => list.map((x) => `${p}${x}`).filter((k) => !en.includes(k)));
	ok('every dynamic v3i_ key (scenes, vehicle classes, agencies) exists', dynMissing.length === 0 && [...prefixes].every((p) => p in dyn), dynMissing.join(', ') || [...prefixes].join(', '));
	const text = (v) => (typeof v === 'function' ? v('‹x›', '‹y›') : v);
	const untranslated = (pack) => en.filter((k) => text(M.packs.MEDIA_PACKS.en[k]) === text(pack[k]) && /[a-z]{4}/.test(text(M.packs.MEDIA_PACKS.en[k])));
	const u = [...untranslated(M.hi), ...untranslated(M.mr)];
	ok('HI and MR are translated (no EN sentence left in place)', u.length === 0, u.slice(0, 6).join(', '));
	const leakHi = Object.values(M.hi).map(text).filter((s) => /[\u0980-\u09FF]/.test(String(s)));
	// the danda । and double danda ॥ (U+0964/5) are shared punctuation: Marathi ends its sentences with them
	const leakMr = Object.values(M.mr).map(text).filter((s) => /[\u0980-\u09FF\u0966-\u096F]/.test(String(s)));
	const gujarati = [...Object.values(M.hi), ...Object.values(M.mr)].map(text).filter((s) => /[\u0A80-\u0AFF]/.test(String(s)));
	ok('no Bengali script left in the HI or MR pack, MR keeps Latin digits, no Gujarati anywhere', leakHi.length === 0 && leakMr.length === 0 && gujarati.length === 0, [...leakHi, ...leakMr, ...gujarati].slice(0, 3).join(' | '));
	ok('MR is Marathi', Object.values(M.mr).map(text).filter((s) => /[\u0900-\u097F]/.test(String(s))).length >= en.length - 2);
}

console.log(failures ? `\n${failures} FAILED` : '\nv3-media: ALL OK');
process.exit(failures ? 1 : 0);
