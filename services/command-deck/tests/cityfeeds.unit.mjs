/**
 * City feeds ($lib/cityfeeds) — the pure rules, the packs and the wiring, on the service's own answers recorded
 * offline on 28 Oct 2026 (tests/fixtures/cityfeeds/, exported from services/cityfeeds in offline mode).
 *
 *   chips     Air · Heat · Cyclone · River · Quake in order; value, band word, tone and honest label from the
 *             summary only; a missing feed says "Unavailable", never zero
 *   tones     the band → tone → EXISTING band-ladder token map (no new colour token); a worse air band draws larger
 *   layers    the Layers-sheet lines of the air and cyclone layers ("No active cyclone")
 *   sheet     the figures come only from the service's numbers; the sources are links
 *   citizen   "Air today": the sentence and the advice per band, in मराठी with the danda
 *   packs     EN / HI / MR complete; every MR sentence ends with a full stop (Marathi does not use the danda)
 *   wiring    the deck proxy rule, the AI gate's public reads (summary, air) and the dev proxy for /api/cityfeeds
 */
import { mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const ARTIFACTS = path.join(HERE, 'artifacts');
mkdirSync(ARTIFACTS, { recursive: true });
const esbuild = await import(pathToFileURL(path.join(DECK, 'node_modules/esbuild/lib/main.js')).href);

const entry = [
	`export * as MD from ${JSON.stringify(path.join(DECK, 'src/lib/cityfeeds/model.ts'))};`,
	`export * as CL from ${JSON.stringify(path.join(DECK, 'src/lib/cityfeeds/client.ts'))};`,
	`export * as PK from ${JSON.stringify(path.join(DECK, 'src/lib/cityfeeds/packs.feeds.ts'))};`,
	`export { hi } from ${JSON.stringify(path.join(DECK, 'src/lib/cityfeeds/packs.feeds.hi.ts'))};`,
	`export { mr } from ${JSON.stringify(path.join(DECK, 'src/lib/cityfeeds/packs.feeds.mr.ts'))};`,
	`export * as STR from ${JSON.stringify(path.join(DECK, 'src/lib/i18n/strings.ts'))};`,
	`export * as GATE from ${JSON.stringify(path.join(DECK, 'src/lib/ai/gate.server.ts'))};`,
	`export * as TOK from ${JSON.stringify(path.join(DECK, 'src/lib/design/tokens.ts'))};`,
].join('\n');
const outfile = path.join(ARTIFACTS, 'cityfeeds-unit-bundle.mjs');
await esbuild.build({
	stdin: { contents: entry, resolveDir: DECK, loader: 'ts', sourcefile: 'cityfeeds-unit.entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	platform: 'node',
	format: 'esm',
	outfile,
	logLevel: 'error',
	define: { 'import.meta.env.SSR': 'true' },
});
const M = await import(`${pathToFileURL(outfile).href}?t=${Date.now()}`);

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const fx = (n) => JSON.parse(readFileSync(path.join(HERE, 'fixtures', 'cityfeeds', `${n}.json`), 'utf8'));
const SUM = fx('summary');
const L = (k, ...a) => M.STR.t('en', k, ...a);
const LB = (k, ...a) => M.STR.t('mr', k, ...a);

// ── chips ──
{
	const row = M.MD.chipRow(SUM, L);
	ok('chips: Air · Heat · Cyclone · River · Quake, in that order (the tide stays on Rain · Tide)', row.map((c) => c.id).join() === 'air,heat,cyclone,river,quake');
	const air = row[0];
	ok('chips: air shows the indicative AQI, its band in words and the Modelled label', air.value === 'AQI 62' && air.band === 'Satisfactory' && air.label === 'MODELLED' && air.tone === 'good', JSON.stringify(air));
	const cyc = row[2];
	ok('chips: the cyclone chip names the storm, its distance and the GDACS alert in words', cyc.value === 'ARNAB-26, 972 km away' && cyc.band === 'Red alert' && cyc.tone === 'poor' && cyc.label === 'LIVE', JSON.stringify(cyc));
	ok('chips: river and quake from CWC and USGS, live', row[3].value === 'All below warning' && row[3].band === 'Normal' && row[4].value === 'None in 30 days' && row[4].band === 'Quiet' && row[3].label === 'LIVE');
	ok('chips: heat shows the heat index with its band word', /°C$/.test(row[1].value) && row[1].band === 'Comfortable');
	const none = M.MD.chipRow(null, L);
	ok('chips: no summary → every chip says Unavailable (never a zero)', none.every((c) => c.value === 'Unavailable' && !c.available && c.label === 'UNAVAILABLE'));
	const down = M.MD.chipVM('air', { ...SUM.chips.air, label: 'UNAVAILABLE', value: null }, L);
	ok('chips: an unavailable feed is not drawn as a value', !down.available && down.value === 'Unavailable');
	const noCyc = M.MD.chipVM('cyclone', { ...SUM.chips.cyclone, value: null, band: 'none' }, L);
	ok('chips: no active cyclone says so', noCyc.value === 'No active cyclone' && noCyc.available);
	const mr = M.MD.chipRow(SUM, LB);
	ok('chips: मराठी band words', mr[0].band === 'समाधानकारक' && mr[2].band === 'रेड अलर्ट' && mr[3].value === 'सर्व इशारा पातळीखाली');
}

// ── tones → existing tokens ──
{
	const tokens = new Set(Object.keys(M.TOK.TOKENS.command));
	const used = Object.values(M.MD.TONE_TOKEN).flatMap((t) => [t.fill, t.ring]).filter(Boolean);
	ok('tones: every tone paints with an EXISTING semantic token (no new colour)', used.every((t) => tokens.has(t)), used.join(' '));
	ok('tones: National AQI bands on the ladder (green · amber · red · black)', ['good', 'satisfactory', 'moderate', 'poor', 'very_poor', 'severe'].map((b) => M.MD.toneOf('air', b)).join() === 'good,good,fair,poor,poor,severe');
	ok('tones: a worse band draws a larger air marker (meaning never rides on colour alone)', M.MD.NAQI_ORDER.every((b, i, a) => i === 0 || M.MD.airRadius(b) > M.MD.airRadius(a[i - 1])));
	ok('tones: an unknown band is neutral', M.MD.toneOf('river', 'whatever') === 'neutral' && M.MD.toneOf('cyclone', null) === 'neutral');
}

// ── layer rows ──
{
	const K = (k, ...a) => `${k}${a.length ? `(${a.join(',')})` : ''}`;
	ok('layers: off rows say what they would show', M.MD.feedLayerSub('air', { visible: false, count: 0, error: null }, K) === 'cf_l_air_about' && M.MD.feedLayerSub('cyclone', { visible: false, count: 0, error: null }, K) === 'cf_l_cyc_about');
	ok('layers: the cyclone row says "No active cyclone" with none', M.MD.feedLayerSub('cyclone', { visible: true, count: 0, error: null }, L) === 'No active cyclone');
	ok('layers: the air row counts the sites and names the worst band', M.MD.feedLayerSub('air', { visible: true, count: 10, error: null, detail: { worst_band: 3 } }, L) === '10 sites, worst poor');
	ok('layers: other layers are not the city feeds’', M.MD.feedLayerSub('waterlog', { visible: true, count: 1, error: null }, K) === null);
	ok('layers: the row detail comes from the shared summary (worst air band, nearest cyclone distance)', JSON.stringify(M.MD.feedRowDetail('air', SUM)) === '{"worst_band":1}' && JSON.stringify(M.MD.feedRowDetail('cyclone', SUM)) === '{"distance_km":972}' && M.MD.feedRowDetail('flow', SUM) === undefined && M.MD.feedRowDetail('air', null) === undefined);
	ok('layers: worstBandIndex', M.MD.worstBandIndex(['good', 'moderate', null]) === 2 && M.MD.worstBandIndex([]) === -1);
}

// ── the sheet ──
{
	const air = M.MD.sheetFigures('air', fx('air'), L, 'en');
	ok('sheet: air figures from the service (worst site, 24-h PM means, the next 48 h, the grid note)', /Worst site: /.test(air[0]) && /PM2\.5 37\.4, PM10 37\.5/.test(air[1]) && air.some((x) => /Next 48 hours/.test(x)) && air.some((x) => /4 cell\(s\) cover the 10 sites/.test(x)), air.join(' | '));
	const cyc = M.MD.sheetFigures('cyclone', fx('cyclones'), L, 'en');
	ok('sheet: cyclone figures (distance, bearing, closest approach)', /ARNAB-26 is 972 km SW of Mumbai/.test(cyc[0]) && /no closer than 700 km/.test(cyc[1]), cyc.join(' | '));
	const riv = M.MD.sheetFigures('river', fx('river'), L, 'en');
	ok('sheet: river lines carry CWC levels and warning levels, and the DVC news count', riv.some((x) => /^Harinkhola: 5\.06 m \(warning 11\.8 m\)$/.test(x)) && riv.some((x) => /0 news mention/.test(x)), riv.join(' | '));
	const qk = M.MD.sheetFigures('quake', fx('quakes'), L, 'en');
	ok('sheet: quake figures', /^M4\.3, 45 km E of Tura, India, 407 km away$/.test(qk[0]), qk.join(' | '));
	ok('sheet: no answer → no figures (never a guess)', M.MD.sheetFigures('air', null, L, 'en').length === 0);
	ok('sheet: every chip has at least one source, every link https', Object.values(M.MD.CHIP_SOURCES).every((r) => r.length >= 1) && Object.values(M.MD.CHIP_SOURCES).flat().every((s) => !s.url || s.url.startsWith('https://')));
	const mr = M.MD.sheetFigures('air', fx('air'), LB, 'mr');
	ok('sheet: in मराठी the worst site carries its Marathi name', /রবীন্দ্রভারতী/.test(mr[0]), mr[0]);
}

// ── the citizen card ──
{
	const t = M.MD.airToday('satisfactory', 62, LB);
	ok('citizen: "Air today" in plain Marathi, ending with a full stop', t.head === 'आज मुंबईची हवा समाधानकारक आहे (AQI सुमारे 62).' && t.advice.endsWith('.'), JSON.stringify(t));
	ok('citizen: an advice line for every band, in all three languages', M.MD.NAQI_ORDER.every((b) => ['en', 'mr', 'hi'].every((l) => M.STR.t(l, `cf_pub_adv_${b}`) !== `cf_pub_adv_${b}`)));
	ok('citizen: no band → no sentence', M.MD.airToday(null, 62, L) === null && M.MD.airToday('nonsense', 62, L) === null);
}

// ── packs ──
{
	const en = M.PK.FEEDS_PACK_KEYS;
	ok('packs: HI and MR carry exactly the EN keys', en.length > 50 && en.every((k) => k in M.hi && k in M.mr) && Object.keys(M.mr).length === en.length && Object.keys(M.hi).length === en.length, `${en.length} keys`);
	const bnSentences = en.filter((k) => /^cf_(pub_adv|what|officer|down|sheet_down|tag_.*_tip|pub_lead|pub_down|pub_tag_tip)/.test(k)).map((k) => [k, String(M.mr[k])]);
	ok('packs: every MR sentence ends with a full stop (never the danda)', bnSentences.every(([, v]) => v.trim().endsWith('.') && !v.includes('।')), bnSentences.filter(([, v]) => !v.trim().endsWith('.') || v.includes('।')).map(([k]) => k).join(' '));
	ok('packs: proposals stay proposals and a named officer decides', /named officer decides/.test(L('cf_officer')) && /अधिकारी निर्णय घेतात/.test(LB('cf_officer')));
}

// ── wiring ──
{
	const hooks = readFileSync(path.join(DECK, 'src/hooks.server.ts'), 'utf8');
	ok('wiring: /api/cityfeeds is a pinned loopback rule on CITYFEEDS_PORT (default 8199), prefix stripped', /\{ prefix: '\/api\/cityfeeds', target: AI_TARGET\('CITYFEEDS_PORT', '8199'\), strip: true \}/.test(hooks));
	const vite = readFileSync(path.join(DECK, 'vite.config.ts'), 'utf8');
	ok('wiring: the dev deck proxies /api/cityfeeds when CITYFEEDS_PORT is named', /\['speech', 'forecast', 'vision', 'hydro', 'twin', 'cityfeeds'\]/.test(vite));
	const g = M.GATE.aiGateDecision;
	ok('wiring: the AI gate lets the citizen page read the summary and the air (GET, no force) and nothing else', g('GET', '/api/cityfeeds/feeds/summary') === 'allow' && g('GET', '/api/cityfeeds/feeds/air') === 'allow' && g('GET', '/api/cityfeeds/feeds/air', '?force=1') === 'deny' && g('GET', '/api/cityfeeds/feeds/cyclones') === 'deny' && g('GET', '/api/cityfeeds/feeds/proposals') === 'deny' && g('POST', '/api/cityfeeds/feeds/air') === 'deny');
	ok('wiring: the client reads only the deck origin', M.CL.FEEDS_PATH === '/api/cityfeeds' && Object.values(M.CL.CHIP_ROUTE).every((r) => r.startsWith('/feeds/')));
}

if (failures) {
	console.error(`\nFAIL cityfeeds.unit — ${failures} assertion(s) failed`);
	process.exit(1);
}
console.log('cityfeeds.unit: ALL OK');
