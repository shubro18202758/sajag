/**
 * Map v2 fix-ups unit test (FIX-D-MAP; SPEC §7 linked views, §9 honest
 * labels) — a selection anywhere highlights the entity on the v2 map, and
 * the replay banner names an emulated run as Emulated without ever
 * claiming emulation for a run it cannot show.
 *
 *   node tests/map-v2-fixes.unit.mjs
 *                                                           the deck's own files
 *   node tests/map-v2-fixes.unit.mjs --canvas <file> --banner <file> --pack <file>
 *                                                           scratch copies (e.g. the
 *                                                           pre-change files)
 *
 * Zero-browser (the house style): packs.map.ts is bundled with esbuild and
 * read through the REAL t() (the canvas-bus pattern), and the two Svelte
 * files are read as source. Asserts:
 *
 *   1. PACK     the replay provenance key map_replay_emulated exists in EN,
 *               HI and MR ('Emulated' / 'इम्यूलेटेड' / 'एम्युलेटेड') through
 *               t(), and map_replay_banner still names the run.
 *   2. BANNER   ReplayBanner takes `emulated` (default false) and renders
 *               the provenance word INSIDE [data-testid=replay-pill] only
 *               when it is true — a replay without provenance claims
 *               nothing.
 *   3. STATE    the canvas derives `replayEmulated` from the replay state
 *               (tapeIsEmulated(replay.tape)) and passes it to the banner;
 *               tapeIsEmulated checks the emulator's EM series on every
 *               plate and rejects a tape with any live mark.
 *   4. SELECT   applySelectionHighlight draws the canvas's own v2 selection
 *               marker (map2:sel) when no layer primitive matches the
 *               selection, counts it in selectedHighlights (the snapshot's
 *               selection.highlighted), draws it selected (the neutral
 *               marker + selection ring) and drops it when a layer draws
 *               the selection or the selection clears.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

function argOf(flag, fallback) {
	const i = process.argv.indexOf(flag);
	return i > 0 && process.argv[i + 1] ? path.resolve(process.argv[i + 1]) : fallback;
}

const CANVAS = argOf('--canvas', path.join(DECK, 'src/lib/gods-eye/GodsEyeCanvas.svelte'));
const BANNER = argOf('--banner', path.join(DECK, 'src/lib/gods-eye/hud/map/ReplayBanner.svelte'));
const PACK = argOf('--pack', path.join(DECK, 'src/lib/i18n/packs.map.ts'));

// ─── 1. the pack, through the real t() ─────────────────────────────────────

const OUT = path.join(HERE, 'artifacts', 'map-v2-fixes-bundle.mjs');
{
	const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');
	// t() resolves from BESIDE the pack under test, so a scratch pack (the
	// pre-change proof) registers into the same strings module the test reads.
	const strings = path.join(path.dirname(PACK), 'strings.ts');
	const rel = (f) => `./${path.relative(DECK, f).split(path.sep).join('/')}`;
	await esbuild.build({
		stdin: {
			contents: `import '${rel(PACK)}';\nexport { t } from '${rel(strings)}';\n`,
			resolveDir: DECK,
			loader: 'ts',
			sourcefile: 'map-v2-fixes-entry.ts',
		},
		absWorkingDir: DECK,
		alias: { $lib: './src/lib' },
		bundle: true,
		format: 'esm',
		platform: 'node',
		outfile: OUT,
		logLevel: 'silent',
	});
}
const { t } = await import(new URL(`file://${OUT}`).href);

const WORDS = { en: 'Emulated', hi: 'इम्यूलेटेड', mr: 'एम्युलेटेड' };
for (const [lang, word] of Object.entries(WORDS)) {
	ok(`replay pack: map_replay_emulated says Emulated (${lang})`, t(lang, 'map_replay_emulated') === word, `'${t(lang, 'map_replay_emulated')}'`);
}
ok('replay pack: map_replay_banner still names the run', /run 20/.test(t('en', 'map_replay_banner', 20)), `'${t('en', 'map_replay_banner', 20)}'`);

// ─── 2. the banner: the word rides the replay pill, gated on the state ─────

const bannerSrc = readFileSync(BANNER, 'utf8');
ok('replay banner: an emulated prop (default false)', /emulated\?:\s*boolean/.test(bannerSrc) && /emulated = false/.test(bannerSrc));
ok(
	'replay banner: the provenance word renders inside the replay pill, gated on emulated',
	/data-testid="replay-pill"/.test(bannerSrc) && /\{#if emulated\}[\s\S]*?map_replay_emulated[\s\S]*?\{\/if\}/.test(bannerSrc),
);
ok('replay banner: the pill renders the banner text before the word', /map_replay_banner/.test(bannerSrc));

// ─── 3. the canvas: provenance read from the replay state ──────────────────

const canvasSrc = readFileSync(CANVAS, 'utf8');
ok('replay canvas: the banner receives the tape provenance', /<ReplayBanner[^>]*emulated=\{replayEmulated\}/.test(canvasSrc));
ok('replay canvas: replayEmulated derives from the replay state (the tape)', /tapeIsEmulated\(replay\.tape\)/.test(canvasSrc));
ok(
	'replay canvas: the EM series check rejects a tape with any live mark',
	/slice\(4,\s*6\)[\s\S]{0,40}EM/.test(canvasSrc) && /every\(\(p\)\s*=>/.test(canvasSrc),
);
ok('replay canvas: a tape with no reads keeps the ledger provenance', /!\s*plates\.length[\s\S]{0,60}return true/.test(canvasSrc));

// ─── 4. the canvas: a selection no layer draws is still emphasised ─────────

ok(
	'selection canvas: applySelectionHighlight draws the v2 marker only when no primitive matches',
	/applySelectionMarker\(urn,\s*chrome === 'v2' && matches\.length === 0\)/.test(canvasSrc),
);
ok(
	'selection canvas: the canvas marker counts in the snapshot (selectedHighlights push)',
	/if \(selMarker\) selectedHighlights\.push\(\{ entity: selMarker, restore: \(\) => \{\} \}\);/.test(canvasSrc) &&
		/highlighted: selectedHighlights\.length/.test(canvasSrc),
);
ok(
	'selection canvas: the canvas marker wears the selection ring (selected state, neutral marker)',
	/markerBillboard\(C,\s*meta,\s*\{\s*selected:\s*true\s*\}\)/.test(canvasSrc) && /shape: 'disc',\s*cluster: false/.test(canvasSrc),
);
ok(
	'selection canvas: the marker is dropped when a layer draws the selection or it clears',
	/function dropSelectionMarker\(\)/.test(canvasSrc) && /dropSelectionMarker\(\);[\s\S]{0,20}return null;/.test(canvasSrc),
);
ok(
	'selection canvas: the marker id sits under the canvas decor prefix (map2:sel)',
	/const V2_SEL = `\$\{V2_PREFIX\}sel`;/.test(canvasSrc) && /id: V2_SEL,/.test(canvasSrc),
);

if (failures) {
	console.error(`\n${failures} failure(s)`);
	process.exit(1);
}
console.log('\nall green');
