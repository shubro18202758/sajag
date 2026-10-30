/**
 * V3 token gate (V3-P01; V3-SPEC §4.2, §4.3, §7.7, §7.8) — zero browser.
 *
 *   node tests/v3-tokens.unit.mjs
 *
 *   1. PARITY     src/lib/v3/tokens.css ↔ src/lib/v3/tokens.ts: the night block (:root) holds exactly the
 *                 shared keys + the night colours, the day block ([data-theme='daylight']) exactly the
 *                 colour keys (so both themes resolve the SAME key list), the < 1500 px block exactly
 *                 V3_COMPACT — every value equal, every key `--v3-*`.
 *   2. CONTRAST   every V3 text ink ≥ 4.5:1 on EVERY V3 surface (bg, s1…s4) in BOTH themes; each role's
 *                 ink on its own veil composited over surface 1; the primary, brand and decision fills
 *                 with their inks. The table is printed.
 *   3. SPEC       the frozen roles keep their §4.2 values (decision #FF9F43, alert #FF5C61, ok #3CCB7F,
 *                 AI #5B91F5, route #2DD4BF, brand #276EF1, filled blue #276EF1, neutral black / grey grounds); the type scale and the
 *                 shell sizes are §4.3 / §3.1's; the operator type floor is 12 px.
 *   4. PACKS      packs.v3 EN / HI / MR carry the same keys; every `v3_*` key the V3 code uses exists; the EN
 *                 copy keeps the copy rules (≤ one " · ", titles ≤ 32 characters, no ALL-CAPS word outside
 *                 the acronym list); HI / MR are really translated (no EN string left in place).
 *   5. HEX        no hex colour literal in V3 code outside tokens.css / tokens.ts.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const V3 = path.join(DECK, 'src/lib/v3');
const OUT = path.join(HERE, 'artifacts', 'v3-tokens-bundle.mjs');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

mkdirSync(path.dirname(OUT), { recursive: true });
const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');
const built = await esbuild.build({
	stdin: {
		contents: `export * as tokens from './src/lib/v3/tokens';\nexport * as packs from './src/lib/v3/packs.v3';\nexport { hi } from './src/lib/v3/packs.v3.hi';\nexport { mr } from './src/lib/v3/packs.v3.mr';\nexport * as icons from './src/lib/v3/icons';`,
		resolveDir: DECK,
		loader: 'ts',
		sourcefile: 'v3-tokens-entry.ts',
	},
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
	define: { 'import.meta.env.SSR': 'true' },
});
ok('bundle builds (tokens.ts, packs.v3, icons)', built.errors.length === 0);
const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const T = M.tokens;

// ── 1. parity ────────────────────────────────────────────────────────────────

const css = readFileSync(path.join(V3, 'tokens.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
function block(re) {
	const m = re.exec(css);
	if (!m) return null;
	let depth = 0;
	let i = m.index + m[0].length - 1;
	const start = i + 1;
	for (; i < css.length; i++) {
		if (css[i] === '{') depth++;
		else if (css[i] === '}' && --depth === 0) break;
	}
	const body = css.slice(start, i);
	const out = {};
	for (const d of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[d[1]] = d[2].trim().replace(/\s+/g, ' ');
	return out;
}
const night = block(/(^|\n):root\s*\{/);
const compact = block(/@media \(max-width: 1500px\)\s*\{\s*:root\s*\{/);
const day = block(/:root\[data-theme='daylight'\]\s*\{/);
const norm = (v) => String(v).replace(/\s+/g, ' ').trim();
const diff = (a, b) => {
	const keys = new Set([...Object.keys(a ?? {}), ...Object.keys(b ?? {})]);
	return [...keys].filter((k) => norm(a?.[k]) !== norm(b?.[k]));
};
ok('tokens.css has the night, compact and day blocks', !!night && !!compact && !!day);
const nightTs = { ...T.V3_SHARED, ...T.V3_COLOURS.night };
ok('night block = V3_SHARED + V3_COLOURS.night (keys and values)', diff(night, nightTs).length === 0, diff(night, nightTs).slice(0, 6).join(', ') || `${Object.keys(night).length} keys`);
ok('day block = V3_COLOURS.day (keys and values)', diff(day, T.V3_COLOURS.day).length === 0, diff(day, T.V3_COLOURS.day).slice(0, 6).join(', ') || `${Object.keys(day).length} keys`);
ok('the < 1500 px block = V3_COMPACT', diff(compact, T.V3_COMPACT).length === 0, diff(compact, T.V3_COMPACT).join(', ') || `${Object.keys(compact).length} keys`);
ok('both themes resolve the same key list', JSON.stringify(Object.keys(T.v3Tokens('night')).sort()) === JSON.stringify(Object.keys(T.v3Tokens('day')).sort()));
ok('every key is --v3-* (no existing --v-* key is redefined here)', [...Object.keys(night), ...Object.keys(day), ...Object.keys(compact)].every((k) => k.startsWith('--v3-')));

// ── 2. contrast ──────────────────────────────────────────────────────────────

function rgba(v) {
	const s = String(v).trim();
	let m = /^#([0-9a-f]{6})$/i.exec(s);
	if (m) return [parseInt(m[1].slice(0, 2), 16), parseInt(m[1].slice(2, 4), 16), parseInt(m[1].slice(4, 6), 16), 1];
	m = /^rgba?\(([^)]+)\)$/i.exec(s);
	if (m) {
		const p = m[1].split(',').map((x) => Number(x.trim()));
		return [p[0], p[1], p[2], p[3] ?? 1];
	}
	throw new Error(`not a colour: ${v}`);
}
const over = (fg, bg) => [0, 1, 2].map((i) => fg[i] * fg[3] + bg[i] * (1 - fg[3]));
const lum = (c) => {
	const [r, g, b] = c.map((x) => {
		const v = x / 255;
		return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
	});
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => {
	const [x, y] = [lum(a), lum(b)];
	return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
};
for (const theme of ['night', 'day']) {
	const k = T.v3Tokens(theme);
	const rows = [];
	let worst = Infinity;
	for (const ink of T.TEXT_INKS)
		for (const surf of T.SURFACES) {
			const r = ratio(rgba(k[ink]).slice(0, 3), rgba(k[surf]).slice(0, 3));
			worst = Math.min(worst, r);
			if (r < 4.5) rows.push(`${ink} on ${surf} ${r.toFixed(2)}`);
		}
	ok(`${theme}: every text ink ≥ 4.5:1 on every surface (${T.TEXT_INKS.length} inks × ${T.SURFACES.length} surfaces)`, rows.length === 0, rows.join(' | ') || `worst ${worst.toFixed(2)}:1`);
	const veil = [];
	for (const [ink, v] of T.VEIL_PAIRS) {
		const bg = over(rgba(k[v]), rgba(k['--v3-s1']).slice(0, 3));
		const r = ratio(rgba(k[ink]).slice(0, 3), bg);
		if (r < 4.5) veil.push(`${ink} on ${v} ${r.toFixed(2)}`);
	}
	ok(`${theme}: each role's ink on its own veil (over surface 1) ≥ 4.5:1`, veil.length === 0, veil.join(' | ') || `${T.VEIL_PAIRS.length} tags`);
	const fill = [];
	for (const [ink, f] of T.FILL_PAIRS) {
		const r = ratio(rgba(k[ink]).slice(0, 3), rgba(k[f]).slice(0, 3));
		if (r < 4.5) fill.push(`${ink} on ${f} ${r.toFixed(2)}`);
	}
	ok(`${theme}: the primary, brand and decision fills with their inks ≥ 4.5:1`, fill.length === 0, fill.join(' | ') || `${T.FILL_PAIRS.length} fills`);
	// the tags that sit on a map thumb: the ink over the glass ground over the darkest/lightest map
	if (theme === 'night') {
		const glass = (mapPx) => over(rgba(k['--v3-glass']), mapPx);
		const bad = [];
		for (const mapPx of [
			[13, 19, 32],
			[70, 83, 110],
		])
			for (const ink of ['--v3-t1', '--v3-t2'])
				if (ratio(rgba(k[ink]).slice(0, 3), glass(mapPx)) < 4.5) bad.push(`${ink} over glass on map ${mapPx}`);
		ok('night: tag ink over the glass ground stays ≥ 4.5:1 on the darkest and lightest graded map', bad.length === 0, bad.join(' | ') || 'both');
		// the floating-panel glass (Decide's sheet, Home's inset): every text ink over it, even with no blur, over a black and a white pixel
		const panel = (px) => over(rgba(k['--v3-glass-bg']), px);
		const badPanel = [];
		for (const px of [[0, 0, 0], [255, 255, 255]]) for (const ink of ['--v3-t1', '--v3-t2', '--v3-t3']) if (ratio(rgba(k[ink]).slice(0, 3), panel(px)) < 4.5) badPanel.push(`${ink} over panel glass on ${px}`);
		ok('night: every text ink over the panel glass ≥ 4.5:1 on a black and a white pixel', badPanel.length === 0, badPanel.join(' | ') || 'all');
		// one material: the panel glass is the map's glass (glass.ts GLASS), never a fork
		const gsrc = readFileSync(path.join(V3, 'map/glass.ts'), 'utf8');
		const gv = (name) => new RegExp(`${name}: '([^']+)'`).exec(gsrc)?.[1];
		ok('the panel glass tokens equal the map glass (bg, solid, border, blur)', gv('bg') === k['--v3-glass-bg'] && gv('solid') === k['--v3-glass-solid'] && gv('border') === k['--v3-glass-border'] && gv('blur') === k['--v3-glass-blur'], JSON.stringify([gv('bg'), gv('solid'), gv('border'), gv('blur')]));
	}
}

// ── 3. spec values ───────────────────────────────────────────────────────────

{
	const n = T.V3_COLOURS.night;
	const want = { '--v3-decide': '#FF9F43', '--v3-alert': '#FF5C61', '--v3-ok': '#3CCB7F', '--v3-ai': '#5B91F5', '--v3-route': '#2DD4BF', '--v3-brand': '#276EF1', '--v3-brand-strong': '#276EF1', '--v3-bg': '#000000', '--v3-s1': '#111111', '--v3-s2': '#1A1A1A', '--v3-s3': '#242424', '--v3-s4': '#2E2E2E', '--v3-t1': '#FFFFFF', '--v3-t2': '#CBCBCB' };
	const bad = Object.entries(want).filter(([k, v]) => n[k] !== v);
	ok('night: the frozen §4.2 roles and grounds', bad.length === 0, bad.map(([k]) => k).join(', ') || 'as specified (neutral grounds, t3 #A6A6A6)');
	const S = T.V3_SHARED;
	ok('type scale §4.3 (≥ 1500 px): display 40/48, title 28/36, heading 20/28, sub 17/24, body 15/22, meta 13/18, micro 12/16', S['--v3-text-display'] === '40px' && S['--v3-lh-display'] === '48px' && S['--v3-text-title'] === '28px' && S['--v3-text-heading'] === '20px' && S['--v3-text-sub'] === '17px' && S['--v3-text-body'] === '15px' && S['--v3-text-meta'] === '13px' && S['--v3-text-micro'] === '12px');
	ok('< 1500 px: display 32/40, title 24/32, rail 76, top bar 60', T.V3_COMPACT['--v3-text-display'] === '32px' && T.V3_COMPACT['--v3-lh-display'] === '40px' && T.V3_COMPACT['--v3-text-title'] === '24px' && T.V3_COMPACT['--v3-rail'] === '76px' && T.V3_COMPACT['--v3-top'] === '60px');
	ok('shell §3.1: rail 88, top bar 68; controls 44 / 56; radii 8/12/16/22; motion 120/200/320 ms', S['--v3-rail'] === '88px' && S['--v3-top'] === '68px' && S['--v3-ctl-lg'] === '44px' && S['--v3-ctl-xl'] === '56px' && [S['--v3-radius-s'], S['--v3-radius-m'], S['--v3-radius-l'], S['--v3-radius-xl']].join() === '8px,12px,16px,22px' && [S['--v3-dur-1'], S['--v3-dur-2'], S['--v3-dur-3']].join() === '120ms,200ms,320ms');
	const sizes = Object.entries({ ...S, ...T.V3_COMPACT }).filter(([k]) => k.startsWith('--v3-text-')).map(([, v]) => parseFloat(v));
	ok('operator type floor: every V3 text size ≥ 12 px', sizes.every((x) => x >= 12), sizes.join(' '));
	ok('the glyph set has the §4.4 count (68)', M.icons.GLYPH_COUNT === 68, `${M.icons.GLYPH_COUNT}`);
}

// ── 4. packs ─────────────────────────────────────────────────────────────────

{
	const en = Object.keys(M.packs.V3_PACKS.en);
	const hi = Object.keys(M.hi);
	const mr = Object.keys(M.mr);
	const same = (a, b) => a.length === b.length && a.every((k) => b.includes(k));
	ok('packs.v3: EN / HI / MR carry the same keys', same(en, hi) && same(en, mr), `${en.length} keys`);
	ok('packs.v3: every key starts with v3_', en.every((k) => k.startsWith('v3_')));
	// every v3_ key the code uses exists
	const files = [];
	const walk = (d) => {
		for (const f of readdirSync(d)) {
			const p = path.join(d, f);
			if (statSync(p).isDirectory()) walk(p);
			else if (/\.(svelte|ts)$/.test(f) && !/packs\.v3/.test(f)) files.push(p);
		}
	};
	walk(V3);
	walk(path.join(DECK, 'src/routes/(v3)'));
	const used = new Set();
	for (const f of files) for (const m of readFileSync(f, 'utf8').matchAll(/['"`](v3_[a-z0-9_]+)['"`]/g)) used.add(m[1]);
	const dyn = ['v3_band_green', 'v3_band_amber', 'v3_band_red', 'v3_band_black', 'v3_prov_emulated', 'v3_prov_simulated', 'v3_prov_test', 'v3_onb_1', 'v3_onb_2', 'v3_onb_3'];
	const missing = [...used, ...dyn].filter((k) => !en.includes(k));
	ok('every v3_ key the V3 code uses exists in the pack', missing.length === 0, missing.join(', ') || `${used.size} used`);
	// copy rules on EN (the deck's copy-lint rules, applied to the V3 pack)
	const ACR = new Set('FIR ANPR IST VVIP AI ID OSM ETA OSINT ICCC IMD DSS SMS GPS API PIN CCTV SG CG SP V3'.split(' '));
	const text = (v) => (typeof v === 'function' ? v('‹x›', '‹y›', '‹z›') : v);
	const bad = [];
	for (const [k, v] of Object.entries(M.packs.V3_PACKS.en)) {
		const s = String(text(v));
		if ((s.match(/ · /g) ?? []).length > 1) bad.push(`${k}: separator`);
		if (/(title|heading)$/.test(k) && s.length > 32) bad.push(`${k}: title > 32`);
		for (const w of s.split(/[^A-Za-z0-9•]+/)) if (w.length > 1 && /^[A-Z]+$/.test(w) && !ACR.has(w)) bad.push(`${k}: ALL-CAPS ${w}`);
	}
	ok('EN copy rules: ≤ one " · ", titles ≤ 32, no ALL-CAPS word outside the acronyms', bad.length === 0, bad.slice(0, 6).join(' | '));
	const untranslated = (pack) => en.filter((k) => {
		const a = String(text(M.packs.V3_PACKS.en[k]));
		const b = String(text(pack[k]));
		return a === b && /[a-z]{4}/.test(a) && !/^©|^\d|km\/h/.test(a);
	});
	const uh = untranslated(M.hi);
	const ug = untranslated(M.mr);
	ok('HI and MR are translated (no EN sentence left in place)', uh.length === 0 && ug.length === 0, [...uh, ...ug].slice(0, 6).join(', '));
	const leakHi = Object.values(M.hi).map(text).filter((s) => /[ঀ-৿]/.test(String(s)));
	const leakMr = Object.values(M.mr).map(text).filter((s) => /[ঀ-৿०-९]/.test(String(s)));
	ok('no Bengali script left in the HI or MR pack, and MR keeps Latin digits (Marathi is Devanagari)', leakHi.length === 0 && leakMr.length === 0);
}

// ── 5. hex literals only in the token files ─────────────────────────────────

{
	const hits = [];
	const walk = (d) => {
		for (const f of readdirSync(d)) {
			const p = path.join(d, f);
			if (statSync(p).isDirectory()) walk(p);
			else if (/\.(svelte|ts|css)$/.test(f) && !/^tokens\.(ts|css)$/.test(f)) {
				readFileSync(p, 'utf8')
					.split('\n')
					.forEach((line, i) => {
						if (/#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b(?![\w-])/.test(line.replace(/href="#[\w-]+"|#v3-[\w-]+|#evt=|#unit=|#items=/g, ''))) hits.push(`${path.relative(DECK, p)}:${i + 1}`);
					});
			}
		}
	};
	walk(V3);
	walk(path.join(DECK, 'src/routes/(v3)'));
	ok('no hex colour literal in V3 code outside tokens.css / tokens.ts', hits.length === 0, hits.slice(0, 6).join(' | '));
	// Neutral grounds, colour only for meaning: no yellow anywhere (no token, no V3 colour, no brand file). Yellow is
	// hue 40–70° with real saturation; the decision orange (≈ 30°) sits clear of it.
	const walkSrc = (d = path.join(DECK, 'src'), out = []) => {
		for (const f of readdirSync(d)) {
			const p = path.join(d, f);
			if (statSync(p).isDirectory()) walkSrc(p, out);
			else if (/\.(svelte|ts|css)$/.test(f)) out.push(p);
		}
		return out;
	};
	const taxiUsers = walkSrc().filter((f) => /--v3-land-taxi/.test(readFileSync(f, 'utf8')));
	ok('no Kolkata-taxi token (--v3-land-taxi) anywhere: the brand is neutral', taxiUsers.length === 0 && !Object.keys(T.V3_SHARED).some((k) => /taxi/.test(k)), taxiUsers.join(', '));
	const yellowish = (hex) => {
		const n = parseInt(hex.slice(1, 7), 16);
		const r = ((n >> 16) & 255) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
		const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
		if (d < 0.15) return false;
		let h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
		h = (h * 60 + 360) % 360;
		return h >= 40 && h <= 70;
	};
	const css = readFileSync(path.join(V3, 'tokens.css'), 'utf8');
	const yellowTokens = [...css.matchAll(/#[0-9a-fA-F]{6}\b/g)].map((m) => m[0]).filter(yellowish);
	const brandDir = path.join(DECK, 'static/brand');
	const yellowBrand = readdirSync(brandDir).filter((f) => f.endsWith('.svg')).filter((f) => [...readFileSync(path.join(brandDir, f), 'utf8').matchAll(/#[0-9a-fA-F]{6}\b/g)].some((m) => yellowish(m[0])));
	ok('no yellow in the V3 tokens or the brand files', yellowTokens.length === 0 && yellowBrand.length === 0, [...yellowTokens, ...yellowBrand].join(', '));
}

console.log(failures ? `\n${failures} FAILED` : '\nv3-tokens: ALL OK');
process.exit(failures ? 1 : 0);
