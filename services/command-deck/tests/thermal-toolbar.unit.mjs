/**
 * Thermal-toolbar unit test (FIX-C-THERMAL; FIX-E-LOOKUP audit A survivors
 * TH-T3/T3b/T5/T6/T8; SPEC §16.5 confirmed the other way 2026-10-25, §9.1
 * honest copy) — the thermal-STYLE view lives one click away on the MAIN
 * map toolbar, next to Layers and Legend, and never reads as a thermal
 * sensor, an infrared camera or a FLIR device.
 *
 *   node tests/thermal-toolbar.unit.mjs                     the deck's own files
 *   node tests/thermal-toolbar.unit.mjs --toolbar <file> --pack <file>
 *                                        [--workspace <file>] [--agent <file>]
 *                                                           scratch copies (e.g.
 *                                                           the pre-change files)
 *
 * Static, zero-browser (the house copy-lint style): packs.map.ts,
 * packs.workspace.ts and packs.agent.ts are read from the TypeScript AST —
 * the objects passed to registerPack('en'|'hi'|'mr', …), string literals
 * and arrow templates resolved — and MapToolbar.svelte is read as source.
 * Asserts:
 *
 *   1. STRINGS  the thermal keys exist in EN, HI and MR: the button label
 *               and menu head (map_tool_thermal), the honest tooltip
 *               (map_tool_thermal_tip), the menu note (map_flir_note) and
 *               the on-map label while a thermal mode is on
 *               (map_thermal_on); the sensor menu items and the short
 *               palette names survive (map_flir_* / map_pal_*).
 *   2. HONESTY  every thermal string keeps the "visual filter" idea in
 *               each language (its own wording: the HI/MR on-map label and
 *               tooltip no longer REPEAT the view word — "दृश्य … (दृश्य
 *               फ़िल्टर)" is out); no thermal string claims a sensor or
 *               data once the negated phrases are removed; and NONE of them
 *               — map pack, workspace sensor detail, the agent proposal
 *               verb and the ⌘K palette label — so much as says "infrared",
 *               "IR camera", "thermal camera/imaging", a bare IR, "FLIR" or
 *               night vision, in EN or in HI/MR (audit E round 2, item 7).
 *   3. MARKUP   the toolbar has the direct thermal button
 *               ([data-map-tool="thermal"], exactly one, NOT inside an
 *               if) with the honest tooltip, PRESSED while a mode is on
 *               (pressed={sensor !== 'raw'}), its Popover anchored UNDER it
 *               like the shape menu (placement="bottom-start"), the Menu
 *               wired to pickSensor and pickSensor reaching onsensor with
 *               no dead branch, ONE Layers button and ONE Legend button in
 *               the SAME group as the thermal view (audit E round 2, item 1:
 *               round 1 rendered Layers and Legend twice), and the honest
 *               on-map label gated on sensor !== 'raw'.
 *   4. RENDER   the toolbar RENDERS (svelte/server via the esbuild .svelte
 *               loader): exactly one thermal button, aria-pressed per
 *               sensor, one Layers and one Legend button, in the group's
 *               order (audit E round 2, item 6 — kills TH-1).
 *   5. COMMANDS the omnibar's sensor command copy is honest in every
 *               language: "Thermal-style view: <palette>" (the palette in
 *               words, never the raw flir-* id) and "Change the
 *               thermal-style view"; the palette placeholder shows the
 *               thermal-style-view example, never "sensor flir-iron".
 *   6. CONTRACT the sensor prop and onsensor callback keep their union type.
 *
 *   7. CHROME V3 the V3 map (/map, V3-P4) keeps the same rules on its own tools: ONE direct thermal
 *               button in MapTools with the honest tooltip, pressed while a palette is on, never inside
 *               an if, beside 3D and measure; the page drives the canvas sensor (no CSS filter of its
 *               own) and its on-map label says "a visual filter, no thermal sensor" in EN, HI and MR.
 *               (--v3tools / --v3page / --v3pack point at scratch copies.)
 *
 * Against the pre-change files group 1 fails (map_pal_* missing), group 2
 * fails (the HI/MR on-map label repeats दृश्य; the workspace command
 * says "Sensor: ‹x›"; the placeholder says "sensor flir-iron"), group 3
 * fails (the thermal button sits in the Follow/Live group, the pressed
 * state and pickSensor→onsensor are unpinned) and group 4 fails. Exits 0
 * with `ok <name>` lines, 1 on any failure.
 */

import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const SRC_TOOLBAR = path.join(DECK, 'src/lib/gods-eye/hud/map/MapToolbar.svelte');
const SRC_PACK = path.join(DECK, 'src/lib/i18n/packs.map.ts');
const SRC_WORKSPACE = path.join(DECK, 'src/lib/i18n/packs.workspace.ts');
const SRC_AGENT = path.join(DECK, 'src/lib/i18n/packs.agent.ts');
const opt = (name, dflt) => {
	const i = process.argv.indexOf(name);
	return i > 0 && process.argv[i + 1] ? path.resolve(process.argv[i + 1]) : dflt;
};
const TOOLBAR = opt('--toolbar', SRC_TOOLBAR);
const PACK = opt('--pack', SRC_PACK);
const WORKSPACE = opt('--workspace', SRC_WORKSPACE);
const AGENT = opt('--agent', SRC_AGENT);

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

// ── the pack: EN/HI/MR entries from the AST (nothing is executed) ──────────

const ts = createRequire(path.join(DECK, 'package.json'))('typescript');

function unwrap(node) {
	let n = node;
	while (n && (ts.isAsExpression(n) || ts.isSatisfiesExpression?.(n) || ts.isParenthesizedExpression(n) || ts.isTypeAssertionExpression?.(n))) n = n.expression;
	return n;
}

/** A string-ish initializer's text, interpolations as ‹x›; null when not static. */
function textOf(node) {
	const n = unwrap(node);
	if (!n) return null;
	if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) return n.text;
	if (ts.isTemplateExpression(n)) return n.head.text + n.templateSpans.map((s) => '‹x›' + s.literal.text).join('');
	if (ts.isArrowFunction(n) || ts.isFunctionExpression(n)) {
		if (n.body && !ts.isBlock(n.body)) return textOf(n.body);
		if (n.body && ts.isBlock(n.body)) {
			const ret = n.body.statements.filter(ts.isReturnStatement);
			if (ret.length === 1 && ret[0].expression) return textOf(ret[0].expression);
		}
	}
	return null;
}

/** registerPack('en'|'hi'|'mr', …) → { key: text } for one pack file. */
function packsOf(file) {
	const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
	const decls = new Map();
	const calls = [];
	(function visit(node) {
		if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) decls.set(node.name.text, node.initializer);
		if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'registerPack') {
			const [code, pack] = node.arguments;
			if (code && ts.isStringLiteral(code) && ['en', 'hi', 'mr'].includes(code.text) && pack) calls.push([code.text, pack]);
		}
		ts.forEachChild(node, visit);
	})(sf);
	const out = { en: {}, hi: {}, mr: {} };
	for (const [code, arg] of calls) {
		const a = unwrap(arg);
		const obj = ts.isObjectLiteralExpression(a) ? a : ts.isIdentifier(a) && decls.has(a.text) ? unwrap(decls.get(a.text)) : null;
		if (!obj || !ts.isObjectLiteralExpression(obj)) continue;
		for (const p of obj.properties) {
			if (!ts.isPropertyAssignment(p)) continue;
			const name = p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) ? p.name.text : null;
			const text = textOf(p.initializer);
			if (name !== null && typeof text === 'string') out[code][name] = text;
		}
	}
	// HI and MR live ONLY in the per-language modules (FIX-E-PERF2): read `export const hi|mr = {…}` there
	for (const code of ['hi', 'mr']) {
		const chunk = file.replace(/\.ts$/, `.${code}.ts`);
		if (!existsSync(chunk)) continue;
		const cf = ts.createSourceFile(chunk, readFileSync(chunk, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
		for (const st of cf.statements) {
			if (!ts.isVariableStatement(st)) continue;
			for (const d of st.declarationList.declarations) {
				const obj = unwrap(d.initializer);
				if (!ts.isIdentifier(d.name) || d.name.text !== code || !obj || !ts.isObjectLiteralExpression(obj)) continue;
				for (const p of obj.properties) {
					if (!ts.isPropertyAssignment(p)) continue;
					const name = p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) ? p.name.text : null;
					const text = textOf(p.initializer);
					if (name !== null && typeof text === 'string') out[code][name] = text;
				}
			}
		}
	}
	return out;
}

const PACKS = packsOf(PACK);
const WORKSPACE_PACKS = packsOf(WORKSPACE);
const AGENT_PACKS = packsOf(AGENT);

// ── group 1: the strings exist in every language ──────────────────────────

const LANGS = ['en', 'hi', 'mr'];
const NEW_KEYS = ['map_tool_thermal', 'map_tool_thermal_tip', 'map_flir_note', 'map_thermal_on'];
const MENU_KEYS = ['map_flir_off', 'map_flir_whot', 'map_flir_bhot', 'map_flir_iron'];
const PAL_KEYS = ['map_pal_raw', 'map_pal_whot', 'map_pal_bhot', 'map_pal_iron'];

for (const lang of LANGS) {
	const missing = NEW_KEYS.filter((k) => !(k in PACKS[lang]));
	ok(`strings: ${lang} carries the thermal keys`, missing.length === 0, missing.length ? `missing ${missing.join(', ')}` : NEW_KEYS.join(', '));
}
ok(
	'strings: the sensor menu items and the short palette names survive in every language',
	LANGS.every((l) => [...MENU_KEYS, ...PAL_KEYS].every((k) => k in PACKS[l])),
	[...MENU_KEYS, ...PAL_KEYS].join(', '),
);
ok(
	'strings: the EN palette names are the four palettes in words (never the flir-* ids)',
	PACKS.en.map_pal_raw === 'normal colours' && PACKS.en.map_pal_whot === 'white hot' && PACKS.en.map_pal_bhot === 'black hot' && PACKS.en.map_pal_iron === 'ironbow',
	PAL_KEYS.map((k) => PACKS.en[k] ?? '‹missing›').join(', '),
);
ok(
	'strings: the EN tooltip is pinned honest',
	PACKS.en.map_tool_thermal_tip === 'Thermal-style view — a visual filter, no thermal sensor',
	JSON.stringify(PACKS.en.map_tool_thermal_tip ?? '‹missing›'),
);
ok('strings: the EN menu note is pinned honest', PACKS.en.map_flir_note === 'Visual filter, no thermal sensor', JSON.stringify(PACKS.en.map_flir_note ?? '‹missing›'));
ok('strings: the EN on-map label is pinned honest', PACKS.en.map_thermal_on === 'Thermal-style view (visual filter)', JSON.stringify(PACKS.en.map_thermal_on ?? '‹missing›'));

// ── group 2: honest in every language ─────────────────────────────────────

/** The "visual filter" idea, per language — either wording (the deck's own or the transliteration). */
const VISUAL_FILTER = {
	en: ['visual filter'],
	hi: ['दृश्य फ़िल्टर', 'विज़ुअल फ़िल्टर'],
	mr: ['व्हिज्युअल फिल्टर', 'दृश्य फिल्टर'],
};
/** The view word per language (FIX-E-LOOKUP: never repeated inside one string). */
const VIEW_WORD = { en: null, hi: 'दृश्य', mr: 'दृश्य' };
/** A negated sensor/data claim, per language — the only way those words may appear. */
const NEGATED = {
	en: ['no thermal sensor', 'no thermal data'],
	hi: ['कोई थर्मल सेंसर नहीं', 'कोई थर्मल डेटा नहीं'],
	mr: ['कोणताही थर्मल सेन्सर नाही', 'थर्मल सेन्सर नाही', 'कोणतीही थर्मल माहिती नाही', 'थर्मल माहिती नाही']
};
/** The bare words that would claim a sensor or thermal data, per language. */
const SENSOR_WORDS = { en: ['sensor', 'thermal data'], hi: ['सेंसर', 'थर्मल डेटा'], mr: ['सेन्सर', 'थर्मल माहिती', 'थर्मल डेटा'] };
/**
 * An infrared/IR-camera/FLIR/thermal-camera claim, per language — audit E
 * round 2 (item 7) widened the lexicon: any thermal-camera or thermal-imaging
 * wording, the native infrared words (अवरक्त), the IR
 * transliterations (आईआर), both कॅमेरा/कॅमेऱ्या spellings, night vision and heat
 * sensors. Bare "IR" is checked with a word boundary (it must never match
 * inside "visual filter").
 */
const IR_WORDS = {
	en: ['infrared', 'ir camera', 'flir', 'thermal camera', 'thermal imaging', 'heat sensor', 'night vision'],
	hi: ['इन्फ्रारेड', 'इंफ्रारेड', 'फ्लिर', 'अवरक्त', 'आईआर', 'थर्मल कैमरा', 'थर्मल इमेजिंग'],
	mr: ['इन्फ्रारेड', 'इंफ्रारेड', 'फ्लिर', 'अवरक्त', 'आयआर', 'थर्मल कॅमेरा', 'थर्मल कॅमेऱ्या', 'थर्मल इमेजिंग', 'नाइट व्हिजन', 'नाईट व्हिजन'],
};
/** Bare "IR" as its own word (EN) — never a substring. */
const BARE_IR = { en: /\bIR\b/i, hi: null, mr: null };

/** The thermal-named keys OUTSIDE the map pack the same sweep must hold
 *  (audit E round 2, item 2): the sensor command's detail line, the agent
 *  proposal chip's verb, and the ⌘K palette's sensor label. */
const EXTRA_THERMAL = (lang) => [
	['ws_cmd_sensor_detail', WORKSPACE_PACKS[lang]],
	['agent_verb_canvas_set_sensor', AGENT_PACKS[lang]],
	['pal_sensor', AGENT_PACKS[lang]],
];

for (const lang of LANGS) {
	for (const key of ['map_tool_thermal_tip', 'map_flir_note', 'map_thermal_on']) {
		const v = PACKS[lang][key] ?? '';
		ok(
			`honesty: ${lang}.${key} carries the visual-filter idea`,
			VISUAL_FILTER[lang].some((w) => v.toLowerCase().includes(w)),
			JSON.stringify(v || '‹missing›'),
		);
	}
	const family = [
		...[...NEW_KEYS, ...MENU_KEYS, 'map_tool_thermal'].map((k) => [`map.${k}`, PACKS[lang][k] ?? '']),
		...EXTRA_THERMAL(lang).map(([k, pack]) => [k, (pack ?? {})[k] ?? '']),
	];
	const residue = family.map(([key, s]) => {
		let out = s;
		for (const neg of NEGATED[lang]) out = out.split(neg).join('');
		return [key, out];
	});
	const claims = [];
	for (const [key, res] of residue) {
		for (const word of [...SENSOR_WORDS[lang], ...IR_WORDS[lang]]) {
			if (res.toLowerCase().includes(word)) claims.push(`"${key}" still says "${word}"`);
		}
		const bare = BARE_IR[lang];
		if (bare && bare.test(res)) claims.push(`"${key}" still says a bare IR`);
	}
	// the view word is never repeated inside one string ("दृश्य … (दृश्य फ़िल्टर)" is out)
	const view = VIEW_WORD[lang];
	if (view) {
		for (const [key, s] of family) {
			const n = s.split(view).length - 1;
			if (n > 1) claims.push(`"${key}" repeats the view word ${n}×`);
		}
	}
	ok(
		`honesty: no ${lang} thermal string — map pack, the sensor command detail, the agent verb and the palette label — claims a sensor, infrared, a thermal camera or FLIR, and the view word is never repeated`,
		claims.length === 0,
		claims.join(' | ') || 'sensor/data negated only, no infrared, no repeat',
	);
}

// ── group 2b: the command and placeholder copy is honest too ──────────────

const THERMAL_VIEW = { en: 'thermal-style view', hi: 'थर्मल-शैली दृश्य', mr: 'थर्मल-शैलीचे दृश्य' };
for (const lang of LANGS) {
	const cmd = WORKSPACE_PACKS[lang].ws_cmd_sensor ?? '';
	const cmdBad = !cmd.toLowerCase().includes(THERMAL_VIEW[lang]) || [...SENSOR_WORDS[lang], ...IR_WORDS[lang]].some((w) => cmd.toLowerCase().includes(w));
	ok(`commands: ${lang}.ws_cmd_sensor reads "Thermal-style view: <palette>", never a sensor claim`, !cmdBad, JSON.stringify(cmd || '‹missing›'));
	const tpl = WORKSPACE_PACKS[lang].ws_cmd_tpl_sensor ?? '';
	ok(`commands: ${lang}.ws_cmd_tpl_sensor says "Change the thermal-style view"`, tpl.toLowerCase().includes(THERMAL_VIEW[lang]) && !tpl.includes('सेंसर') && !tpl.toLowerCase().includes('sensor'), JSON.stringify(tpl || '‹missing›'));
	const reason = WORKSPACE_PACKS[lang].ws_reason_no_sensor ?? '';
	ok(`commands: ${lang}.ws_reason_no_sensor refuses honestly, without claiming sensors exist`, reason.length > 0 && ![...SENSOR_WORDS[lang]].some((w) => reason.toLowerCase().includes(w)) && reason.toLowerCase().includes(THERMAL_VIEW[lang]), JSON.stringify(reason || '‹missing›'));
	const pal = AGENT_PACKS[lang].pal_placeholder ?? '';
	const palBad = /flir/i.test(pal) || ['sensor', ...SENSOR_WORDS[lang].filter((w) => w !== 'thermal data'), ...IR_WORDS[lang]].some((w) => pal.toLowerCase().includes(w)) || !pal.toLowerCase().includes(THERMAL_VIEW[lang]);
	ok(`commands: ${lang}.pal_placeholder shows the thermal-style-view example, never "sensor flir-iron"`, !palBad, JSON.stringify(pal || '‹missing›'));
}

// ── group 3: the markup — the button, its anchoring, the label, no More ────

const toolbar = readFileSync(TOOLBAR, 'utf8');
const count = (hay, needle) => hay.split(needle).length - 1;
const at = (hay, needle) => hay.indexOf(needle);

ok('markup: the direct thermal button exists exactly once', count(toolbar, 'data-map-tool="thermal"') === 1, `${count(toolbar, 'data-map-tool="thermal"')} × data-map-tool="thermal"`);
ok('markup: the thermal button carries the honest tooltip', /data-map-tool="thermal"[\s\S]{0,400}?map_tool_thermal_tip/.test(toolbar) || /map_tool_thermal_tip[\s\S]{0,400}?data-map-tool="thermal"/.test(toolbar));
// FIX-E-LOOKUP (TH-T5): pressed while a mode is on — the behavioural state pin.
ok(
	'markup: the thermal button is PRESSED while a thermal mode is on',
	/pressed=\{sensor !== 'raw'\}/.test(toolbar),
	toolbar.includes('pressed={sensor !== \'raw\'}') ? 'pressed={sensor !== \'raw\'}' : 'no pressed binding on the sensor state',
);
// audit E round 2 (TH-2): the Menu WIRES pickSensor — an exact pin, the
// auditor's blessed minimum (SSR strips handlers, so a render cannot see it).
ok('markup: the sensor Menu wires onselect={pickSensor}', toolbar.includes('onselect={pickSensor}'), count(toolbar, 'onselect={pickSensor}') + ' × onselect={pickSensor}');
// audit E round 2 (TH-3): the pickSensor → onsensor call is LIVE — its
// condition carries no dead branch ("&& false" made round 1's body pin pass).
{
	const start = toolbar.indexOf('function pickSensor');
	const end = toolbar.indexOf('</script>', start);
	const body = start >= 0 && end > start ? toolbar.slice(start, end).replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/\/\/.*$/gm, ' ') : '';
	const live = /if\s*\(([^()]*)\)\s*onsensor\(item\.id\)/.exec(body || '');
	ok(
		'markup: pickSensor closes the menu and calls onsensor with the picked mode — no dead branch',
		!!live && !/&&\s*false|\|\|\s*true/.test(live[1]),
		live ? `condition: ${live[1].trim()}` : body ? body.replace(/\s+/g, ' ').slice(0, 140) : 'pickSensor not found',
	);
}
ok(
	'markup: the sensor menu is anchored UNDER the button like the shape menu',
	/placement="bottom-start"[\s\S]{0,600}?data-map-tool="thermal"[\s\S]{0,900}?Menu items=\{sensorItems\}/.test(toolbar),
);
// FIX-E-LOOKUP audit E round 2 (item 1): ONE Layers + Legend pair — the
// round-1 diff left the original group standing beside its copy, so every map
// page showed both twice (in the engineer's own screenshot). The source must
// hold exactly one layers button and one legend button, and ONE group that
// contains layers, legend AND thermal together (kills TH-7).
{
	ok('markup: exactly ONE Layers button and ONE Legend button', count(toolbar, 'icon="layers"') === 1 && count(toolbar, 'icon="list"') === 1, `${count(toolbar, 'icon="layers"')} × icon="layers", ${count(toolbar, 'icon="list"')} × icon="list"`);
	// balanced <div class="group"> scan
	const groups = [];
	let at = toolbar.indexOf('<div class="group">');
	while (at >= 0) {
		let depth = 0;
		let j = at;
		for (; j < toolbar.length; j++) {
			if (toolbar.startsWith('<div', j)) depth++;
			else if (toolbar.startsWith('</div>', j)) {
				depth--;
				if (!depth) break;
			}
		}
		groups.push(toolbar.slice(at, j));
		at = toolbar.indexOf('<div class="group">', j);
	}
	const mixed = groups.find((g) => g.includes('map_tool_layers') && g.includes('map_tool_legend') && g.includes('data-map-tool="thermal"'));
	ok(
		'markup: Layers, Legend and the thermal-style view sit in the SAME button group',
		!!mixed,
		`${groups.length} group(s); ${groups.map((g) => (g.includes('data-map-tool="thermal"') ? 'thermal' : g.includes('map_tool_layers') ? 'layers+legend' : 'tools')).join(' | ')}`,
	);
}

// FIX-E-LOOKUP audit E round 2 (item 6): the toolbar RENDERED — svelte/server
// through the esbuild .svelte loader, no browser, no new dependency. A mutant
// that unrenders the button (TH-1) or splits the group fails on its own HTML.
{
	const require = createRequire(path.join(DECK, 'package.json'));
	const { compile: compileSvelte } = require('svelte/compiler');
	const esbuild = require('esbuild');
	const loader = {
		name: 'svelte-server',
		setup(build) {
			build.onLoad({ filter: /\.svelte$/ }, async (args) => {
				try {
					const out = compileSvelte(readFileSync(args.path, 'utf8'), { filename: args.path, generate: 'server', runes: true });
					return { contents: out.js.code, loader: 'js', resolveDir: path.dirname(args.path) };
				} catch (e) {
					return { errors: [{ text: `${args.path}: ${e && e.message ? e.message : e}` }] };
				}
			});
		},
	};
	const built = await esbuild.build({
		stdin: {
			contents: `import MapToolbar from '${TOOLBAR}';\nimport { render } from 'svelte/server';\nexport { MapToolbar, render };\n`,
			resolveDir: DECK,
			loader: 'ts',
			sourcefile: 'thermal-toolbar-render-entry.ts',
		},
		absWorkingDir: DECK,
		alias: { $lib: path.join(DECK, 'src/lib') },
		nodePaths: [path.join(DECK, 'node_modules')],
		plugins: [loader],
		bundle: true,
		format: 'esm',
		platform: 'node',
		write: false,
		logLevel: 'silent',
	});
	const mod = await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString('base64')}`);
	const props = (sensor) => ({
		props: {
			lang: 'en',
			tool: 'select',
			shapeMode: 'select',
			canSearchAround: true,
			layersOpen: false,
			legendOpen: false,
			follow: { pressed: false, disabled: false, title: 'Follow' },
			mode: { kind: 'live', runId: null },
			showExit: false,
			touring: false,
			sensor,
			ontool() {}, onclearshape() {}, onsearcharound() {}, onlayers() {}, onlegend() {},
			onfollow() {}, onmode() {}, onexit() {}, ontour() {}, onsensor() {},
		},
	});
	const htmlRaw = mod.render(mod.MapToolbar, props('raw')).html;
	const htmlIron = mod.render(mod.MapToolbar, props('flir-iron')).html;
	const thermal = (h) => (h.match(/data-map-tool="thermal"/g) || []).length;
	ok(
		'render: the thermal-style view button renders exactly once, PRESSED only while a mode is on (TH-1, TH-8)',
		thermal(htmlRaw) === 1 && thermal(htmlIron) === 1 && htmlRaw.includes('aria-pressed="false"') && /data-map-tool="thermal"[^>]*aria-pressed="true"|aria-pressed="true"[^>]*data-map-tool="thermal"/.test(htmlIron),
		`raw ${thermal(htmlRaw)}× unpressed, iron ${thermal(htmlIron)}× pressed`,
	);
	ok(
		'render: exactly ONE Layers and ONE Legend button on the rendered toolbar (audit E item 1)',
		(htmlRaw.match(/aria-label="Layers"/g) || []).length === 1 && (htmlRaw.match(/aria-label="Legend"/g) || []).length === 1,
		`${(htmlRaw.match(/aria-label="Layers"/g) || []).length} layers, ${(htmlRaw.match(/aria-label="Legend"/g) || []).length} legend`,
	);
	// and the rendered order is the group's: legend before thermal, thermal before the follow lock
	const at = (h, s) => h.indexOf(s);
	ok(
		'render: the toolbar reads Layers · Legend · Thermal-style view · Follow',
		at(htmlRaw, 'aria-label="Legend"') < at(htmlRaw, 'data-map-tool="thermal"') && at(htmlRaw, 'data-map-tool="thermal"') < at(htmlRaw, 'chip lock'),
		`legend@${at(htmlRaw, 'aria-label="Legend"')} < thermal@${at(htmlRaw, 'data-map-tool="thermal"')} < follow@${at(htmlRaw, 'chip lock')}`,
	);
}

ok(
	'markup: the honest on-map label shows while a thermal mode is on',
	/sensor !== 'raw'/.test(toolbar) && /map_thermal_on/.test(toolbar) && /\{#if sensor !== 'raw'\}[\s\S]{0,200}?map_thermal_on/.test(toolbar),
);
const moreGone = !toolbar.includes('icon="more"') && !toolbar.includes('map_tool_more') && !toolbar.includes('map_presentation');
ok('markup: More → Presentation no longer holds the thermal entries', moreGone, moreGone ? 'no More button, no presentation key' : 'icon="more" / map_tool_more / map_presentation still present');
ok(
	'markup: the menu items are still the four sensor choices',
	['map_flir_off', 'map_flir_whot', 'map_flir_bhot', 'map_flir_iron'].every((k) => toolbar.includes(k)),
);
ok(
	'contract: the sensor prop and onsensor keep the union type',
	toolbar.includes("sensor: 'raw' | 'flir-whot' | 'flir-bhot' | 'flir-iron'") && toolbar.includes("onsensor: (mode: 'raw' | 'flir-whot' | 'flir-bhot' | 'flir-iron') => void"),
);

// ── group 7: chrome v3 — the V3 map's own tools (V3-P4; V3-SPEC §5.6, user decision: on the MAIN toolbar) ──
// The /map page draws its own tool column (MapTools) around the canvas mounted with chrome="v3"; the thermal-style view
// keeps the same rules there: ONE direct button, the honest tooltip, pressed while a palette is on, wired to the
// canvas's own sensor (mapChrome.act), and the on-map label honest in every language.

const V3_TOOLS = opt('--v3tools', path.join(DECK, 'src/lib/v3/map/MapTools.svelte'));
const V3_PAGE = opt('--v3page', path.join(DECK, 'src/lib/v3/map/MapPage.svelte'));
const V3_PACK = opt('--v3pack', path.join(DECK, 'src/lib/v3/map/packs.map3.ts'));
if (existsSync(V3_TOOLS) && existsSync(V3_PAGE)) {
	const v3t = readFileSync(V3_TOOLS, 'utf8');
	const v3p = readFileSync(V3_PAGE, 'utf8');
	const btn = (v3t.match(/<button[^>]*?data-map-tool="thermal"[\s\S]*?>/) ?? [''])[0] + (v3t.match(/<button(?:(?!<\/button>)[\s\S])*?data-map-tool="thermal"/) ?? [''])[0];
	ok('v3: the V3 map tools have the direct thermal button exactly once', count(v3t, 'data-map-tool="thermal"') === 1);
	ok('v3: … with the honest tooltip (map_tool_thermal_tip), never the bare label', /title=\{t\(lang, 'map_tool_thermal_tip'\)\}/.test(btn), btn.slice(0, 160));
	ok('v3: … pressed exactly while a thermal palette is on', /aria-pressed=\{thermalOn\}/.test(btn) && /const thermalOn = \$derived\(sensor !== 'raw'\)/.test(v3t));
	const beforeBtn = v3t.slice(0, v3t.indexOf('data-map-tool="thermal"'));
	ok('v3: … not inside an {#if} (always on the main tools)', (beforeBtn.match(/\{#if/g) ?? []).length === (beforeBtn.match(/\{\/if\}/g) ?? []).length);
	ok('v3: … in the same column as the 3D city and measure', v3t.indexOf('data-map-tool="3d"') < v3t.indexOf('data-map-tool="thermal"') && v3t.indexOf('data-map-tool="thermal"') < v3t.indexOf('data-map-tool="measure"'));
	ok('v3: the page drives the canvas sensor (mapChrome.act sensor), never a CSS filter of its own', /mapChrome\.act\('sensor', next\)/.test(v3p) && !/filter:\s*(grayscale|sepia|hue-rotate)/.test(v3p));
	ok('v3: the on-map label rides only while a palette is on', /\{#if sensor !== 'raw'\}[\s\S]{0,200}v3m_thermal_on/.test(v3p));
	const v3packs = { en: '', hi: '', mr: '' };
	for (const code of ['en', 'hi', 'mr']) {
		const f = code === 'en' ? V3_PACK : V3_PACK.replace(/\.ts$/, `.${code}.ts`);
		const m = existsSync(f) ? /v3m_thermal_on:\s*'([^']*)'/.exec(readFileSync(f, 'utf8')) : null;
		v3packs[code] = m ? m[1] : '';
	}
	ok('v3: the on-map label says a visual filter, no thermal sensor — EN, HI, MR', v3packs.en === 'Thermal-style view: a visual filter, no thermal sensor' && /फ़िल्टर/.test(v3packs.hi) && /सेंसर नहीं/.test(v3packs.hi) && /फिल्टर/.test(v3packs.mr) && /सेन्सर नाही/.test(v3packs.mr), JSON.stringify(v3packs));
	ok('v3: no V3 thermal string claims a sensor', !/infra-?red|\bFLIR\b|thermal (camera|imaging)|night vision/i.test(Object.values(v3packs).join(' ')));
} else {
	ok('v3: the V3 map tools exist (src/lib/v3/map/MapTools.svelte, MapPage.svelte)', false);
}

// ── result ────────────────────────────────────────────────────────────────

if (failures) {
	console.error(`thermal-toolbar: ${failures} FAILURE(S) — toolbar ${path.relative(DECK, TOOLBAR)}, pack ${path.relative(DECK, PACK)}`);
	process.exit(1);
}
console.log(`ok   thermal-toolbar — honest thermal-style view next to Layers/Legend (${path.relative(DECK, TOOLBAR)}, ${path.relative(DECK, PACK)})`);
process.exit(0);
