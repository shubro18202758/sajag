/**
 * The workspace mark mask's upper-case superset pass (FIX-C; SPEC §9.3 "no
 * raw mark in DOM text", the oracle's city/common.py `_PLATE_UPPER_RE` —
 * one rule everywhere: the deck's maskMarks == the oracle's
 * mask_plates_in_text).
 *
 *   node tests/mask-superset.unit.mjs                 the deck's src/lib/workspace/mask.ts
 *   node tests/mask-superset.unit.mjs --mask <file>   another copy of it (e.g. the pre-change
 *                                                     file) against the same tables
 *
 * esbuild bundles the REAL workspace/mask.ts (`$lib` aliased to src/lib) in
 * memory — nothing is written to disk — and asserts, hermetically:
 *
 *   1. an UPPER-case mark shape masks whatever its first two letters
 *      ("XY12AB1234" → "XY12AB•••4", "XY 12 AB 1234 on the watchlist"), a
 *      space or a dash between the parts, as the oracle always masked it;
 *      "AS OF 24 OCT 2026" masks exactly as it always did (no date-shape
 *      refusal on this pass); lower case still needs a real state code
 *      ("xy12ab1234" stays raw);
 *   2. every existing case of workspace.unit.mjs §10c/§10d still holds for
 *      maskMarks and hasRawMark: the raw marks server props carry (an
 *      e-challan's proposal, an earmark reason, a privacy note, a pursuit's
 *      title) mask and are detected; dates, times, FIR numbers and uuids
 *      stay byte for byte and are never detected; every typed spelling
 *      still masks and its masked output is clean; the §10d row "AB12CD3456
 *      is no state code" moves to the superset table (it is exactly the
 *      pass's shape, and the oracle masks it);
 *   3. text without a mark returns the same string (the fast path accounts
 *      for the pass: a text holding only "XY12AB1234" is masked, a text
 *      with no shape either pass takes is returned as is);
 *   4. the state codes are unchanged (39, WB among them).
 *
 * Run against the pre-change mask.ts (a scratch copy), the superset rows of
 * group 1 fail (the pass is missing: they come back raw, and hasRawMark
 * misses them), and so does group 3's fast-path row (a text holding only
 * "XY12AB1234" was returned as is) — every §10c/§10d case and group 4 pass:
 * that file had no upper-case pass at all.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const SRC_MASK = path.join(DECK, 'src', 'lib', 'workspace', 'mask.ts');
const argi = process.argv.indexOf('--mask');
const MASK = argi > 0 && process.argv[argi + 1] ? path.resolve(process.argv[argi + 1]) : SRC_MASK;

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const show = (rows, max = 6) => rows.slice(0, max).join(' | ') + (rows.length > max ? ` | … ${rows.length - max} more` : '');

// ─── bundle the real module (in memory) ──────────────────────────────────────

const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');
const ENTRY = `export * as mask from ${JSON.stringify(MASK)};`;
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'mask-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	write: false,
	logLevel: 'silent',
});
ok('bundle builds (esbuild, $lib aliased, in memory)', built.errors.length === 0 && built.outputFiles.length === 1, `${path.relative(DECK, MASK)}`);
const { mask: MK } = await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString('base64')}`);

// ─── 1. the upper-case superset pass (the oracle's _PLATE_UPPER_RE) ─────────

const SUPERSET = [
	['XY12AB1234', 'XY12AB•••4'],
	['XY 12 AB 1234 on the watchlist', 'XY 12 AB •••4 on the watchlist'],
	['AS OF 24 OCT 2026', 'AS OF 24 OCT •••6'],  // all caps: masked as it always was
	['AB12CD3456 is no state code', 'AB12CD•••6 is no state code'],  // §10d's row: the pass's shape
	['XY-12-AB-1234 near J11', 'XY-12-AB-•••4 near J11'],  // a dash between the parts too
	['OF 24 OCT 2026 after AS', 'OF 24 OCT •••6 after AS'],  // the head the oracle's rule takes
];
const supersetBad = SUPERSET.filter(([x, want]) => MK.maskMarks(x) !== want || !MK.hasRawMark(x) || MK.hasRawMark(MK.maskMarks(x))).map(
	([x, want]) => `${JSON.stringify(x)} → ${JSON.stringify(MK.maskMarks(x))} want ${JSON.stringify(want)}`,
);
ok('the upper-case pass: any two upper-case letters, a space or a dash, mask (the head kept, the number but its last digit); hasRawMark detects the raw shape and passes the masked one', supersetBad.length === 0, show(supersetBad) || SUPERSET.map(([x]) => MK.maskMarks(x)).join(' · '));
ok('lower case still needs a real state code (the any-case rule alone never takes two letters)', MK.maskMarks('xy12ab1234') === 'xy12ab1234' && !MK.hasRawMark('xy12ab1234'), MK.maskMarks('xy12ab1234'));

// ─── 2. every existing §10c/§10d case still holds ───────────────────────────

// §10c: the raw marks server props carry inside free text (MH01XX0007)
const RM = 'MH01XX0007';
const RAW_IN_PROPS = [
	[`e-challan recommended: ${RM} read at 72 km/h in a 50 km/h segment`, `e-challan recommended: MH01XX•••7 read at 72 km/h in a 50 km/h segment`],
	[`Stolen ${RM} reported — FIR 9/2026, Hare Street PS; Sandbox`, `Stolen MH01XX•••7 reported — FIR 9/2026, Hare Street PS; Sandbox`],
	[`Reads of ${RM} are kept 30 days`, `Reads of MH01XX•••7 are kept 30 days`],
	[`PURSUIT — ${RM}`, `PURSUIT — MH01XX•••7`],
	[`PURSUIT — stolen ${RM} (FIR 9/2026, Hare Street PS)`, `PURSUIT — stolen MH01XX•••7 (FIR 9/2026, Hare Street PS)`],
];
const rawBad = RAW_IN_PROPS.filter(([x, want]) => MK.maskMarks(x) !== want || !MK.hasRawMark(x) || MK.hasRawMark(MK.maskMarks(x))).map(
	([x, want]) => `${JSON.stringify(x)} → ${JSON.stringify(MK.maskMarks(x))} want ${JSON.stringify(want)}`,
);
ok('§10c raw marks in props: maskMarks masks the mark alone (the FIR number and the rest as they were) and hasRawMark flags the raw text, never the masked one', rawBad.length === 0, show(rawBad) || `${RAW_IN_PROPS.length} texts, e.g. ${MK.maskMarks(RAW_IN_PROPS[3][0])}`);

// §10d: dates, times, years, FIR numbers, uuids — byte for byte, never detected
const NOT_MARKS = [
	'As of 24 Oct 2026, the vehicle was last read at EM-CAM-03.',
	'Retention ends on 22 Nov 2026.',
	'Checked on 12 Oct 2026, CCTV clear',
	'Waterlogging reported on 23 Oct 2026 near Thanthania',
	'Road closed till 30 Nov 2026',
	'Plan review at 10 am 2026',
	'Diversion via NH 48 since 2024',
	'FIR 4401/2026, Hare Street PS',
	'Filed at 01 38 2026',
	'Closed 23 or 24 Oct 2026, held up 12 Oct 2026',
	'AS 24 Oct 2026 · as 1 jan 2027 · up 12 Dec 2026',
	// the orchestrator's cases (a month in mixed or lower case is a date, whatever the state-code word's case)
	'As 24 Oct 2026',
	'as of 24 Oct 2026',
	'on 12 oct 2026',
	'AS 24 Oct 2026',
	'From 23-Oct-2026 to UP-24-Oct-2026, then 12/10/2026',
	'Opened by Sandbox Officer from the watchlist console (recommendation 3f2a…)',
	// uuids (a URN's id): even a hex group shaped like a mark, and a real mark beside one
	'event:3f2a1b12-3456-4abc-8def-0123456789ab',
	'dispatch:0b7e3c2a-dd12-3456-9a8b-5c6d7e8f9a0b',
];
const notBad = NOT_MARKS.filter((x) => MK.maskMarks(x) !== x || MK.hasRawMark(x)).map((x) => `${JSON.stringify(x)} → ${JSON.stringify(MK.maskMarks(x))}`);
ok('§10d: dates, times, years, FIR numbers and uuids come back byte for byte and are never a raw mark', notBad.length === 0, show(notBad) || `${NOT_MARKS.length} phrases unchanged`);
ok(
	'§10d: a real mark beside a held-out uuid masks, the uuid untouched',
	MK.maskMarks('DD 12 AB 3456 near dispatch:0b7e3c2a-dd12-3456-9a8b-5c6d7e8f9a0b') === 'DD 12 AB •••6 near dispatch:0b7e3c2a-dd12-3456-9a8b-5c6d7e8f9a0b',
	MK.maskMarks('DD 12 AB 3456 near dispatch:0b7e3c2a-dd12-3456-9a8b-5c6d7e8f9a0b'),
);

// §10d: every typed spelling still masks, and the masked output is clean
const TYPED = ['mh01xx0007', 'Mh01Xx0007', 'MH.01.XX.0007', 'mh 01 xx 0007', 'MH-01-XX-0007', 'mH01.xX 0007', 'MH01XX0007'];
const MORE_TYPED = ['MH/01/XX/0007', 'MH_01_XX_0007', 'mh 01-xx/0007'];
const typedBad = [...TYPED, ...MORE_TYPED].filter((x) => !MK.maskMarks(x).endsWith('•••7') || MK.hasRawMark(MK.maskMarks(x)) || !MK.hasRawMark(x)).map((x) => `${x} → ${MK.maskMarks(x)}`);
ok('§10d: all 10 typed spellings (dots, dashes, slashes, underscores, spaces, glued) still mask; hasRawMark flags each raw one and passes its masked output', typedBad.length === 0, show(typedBad) || `${TYPED.length + MORE_TYPED.length} spellings, e.g. ${MK.maskMarks('mH01.xX 0007')}`);

// §10d: an upper-case state code with an upper-case month series is a mark, spaced or not
const UPPER_MONTH = [
	['MH 01 MAY 1234', 'MH 01 MAY •••4'],
	['DL 8 SEP 1234', 'DL 8 SEP •••4'],
	['MH-01-OCT-1234', 'MH-01-OCT-•••4'],
	['MH.12.JAN.4321', 'MH.12.JAN.•••1'],
];
const monthBad = UPPER_MONTH.filter(([x, want]) => MK.maskMarks(x) !== want || !MK.hasRawMark(x) || MK.hasRawMark(MK.maskMarks(x))).map(([x, want]) => `${x} → ${MK.maskMarks(x)} want ${want}`);
ok('§10d: an upper-case state code with an upper-case series that spells a month is a mark, spaced or not', monthBad.length === 0, show(monthBad) || UPPER_MONTH.map(([x]) => MK.maskMarks(x)).join(' · '));
ok(
	'§10d: real state codes in any case still mask; a series glued to its number even when it spells a month',
	MK.maskMarks('MH12AB1234 · tg09ab1234 · Dl3CAB1234 · DL8SEP1234 · KA05MAY1234 · up 14 ab 2211') === 'MH12AB•••4 · tg09ab•••4 · Dl3CAB•••4 · DL8SEP•••4 · KA05MAY•••4 · up 14 ab •••1',
	MK.maskMarks('MH12AB1234 · tg09ab1234 · Dl3CAB1234 · DL8SEP1234 · KA05MAY1234 · up 14 ab 2211'),
);

// §10d: officer notes and streamed answers — a text with dates (and an already-masked mark) is never altered
const ANSWER = 'As of 24 Oct 2026 the vehicle MH47EM•••1 was last read at EM-CAM-03; retention ends on 22 Nov 2026.';
const ANSWER_RAW = 'mh01xx0007 was read on 24 Oct 2026 at 10 am';
ok(
	'§10d: a streamed answer with dates and a masked mark comes back byte for byte; a lower-case raw mark in one is still masked',
	MK.maskMarks(ANSWER) === ANSWER && !MK.hasRawMark(ANSWER) && MK.maskMarks(ANSWER_RAW) === 'mh01xx•••7 was read on 24 Oct 2026 at 10 am',
	`${JSON.stringify(MK.maskMarks(ANSWER))} · ${MK.maskMarks(ANSWER_RAW)}`,
);

// ─── 3. text without a mark: the same string ────────────────────────────────

const PLAIN = 'plain text, no mark';
const plain = MK.maskMarks(PLAIN);
ok('text with no shape either pass takes is returned as is (the same string); a text holding only "XY12AB1234" is masked', plain === PLAIN && MK.maskMarks('XY12AB1234') === 'XY12AB•••4' && MK.maskMarks('') === '' && MK.maskMarks(null) === '' && MK.maskMarks(undefined) === '', plain);

// ─── 4. the exports unchanged ───────────────────────────────────────────────

ok('STATE_CODES unchanged (39 codes, WB among them) and MARK_MASK still •••', Array.isArray(MK.STATE_CODES) && MK.STATE_CODES.length === 39 && MK.STATE_CODES.includes('WB') && MK.MARK_MASK === '•••', `${MK.STATE_CODES.length} codes`);

if (failures) {
	console.error(`\n${failures} check(s) failed`);
	process.exit(1);
}
console.log('\nok   mask superset — upper-case shapes masked, every §10c/§10d case intact, uuids held out, plain text untouched');
