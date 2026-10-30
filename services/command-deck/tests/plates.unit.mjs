/**
 * Plate rail unit test (FIX-B-DECK; SPEC §9.3 "no raw mark in DOM text
 * without a named officer", §3.4 "officer notes and streamed answers are
 * never altered" but for a mark).
 *
 *   node tests/plates.unit.mjs                    the deck's src/lib/gods-eye/plates.ts
 *   node tests/plates.unit.mjs --plates <file>    another copy of it (e.g. the pre-change file) against the same tables
 *
 * esbuild bundles the REAL plates.ts with the REAL workspace/mask.ts (`$lib`
 * aliased to src/lib) in memory — nothing is written to disk — and asserts,
 * hermetically:
 *
 *   1. marks typed in lower or mixed case, with dots, slashes, underscores,
 *      dashes or spaces, glued, or with a series that spells a month, are
 *      masked when no officer is named (maskPlatesInText, displayText,
 *      displayPlate, maskPlate) and shown as sent with one;
 *   2. dates ("24 Oct 2026", "on 12 oct 2026"), times, years, FIR numbers,
 *      UUIDs and an already-masked mark come back byte for byte;
 *   3. parity with workspace/mask.ts (maskMarks, hasRawMark) on the shared
 *      case table: the two masks are one rule;
 *   4. an upper-case mark masks exactly as before: every row of the upper
 *      table (and every one of the 39 state codes) gives the pre-change
 *      pattern's output (the oracle's city/common.py pattern, copied here
 *      as the reference);
 *   5. displayDetail masks every string (and key) of an evidence payload on
 *      its own — a mark right after a JSON escape too — never mutates the
 *      input, leaves other values alone, cuts a cycle instead of handing the
 *      payload back raw, and returns the payload untouched for an officer;
 *   6. plates.ts reuses the workspace rule (imports mask.ts, no pattern of
 *      its own), so the two cannot drift.
 *
 * Run against the pre-change plates.ts (a scratch copy), groups 1, 2, 3 and
 * 5 fail — that file matched upper case with one space or dash only, took
 * any two letters for a state code (an upper-case UUID's "DD12-3456" was
 * masked) and masked serialised JSON — while group 4 passes (upper case is
 * unchanged) and so does the plate-field row of group 1 (maskPlate's
 * fallback already hid a plate field it could not parse).
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const SRC_PLATES = path.join(DECK, 'src', 'lib', 'gods-eye', 'plates.ts');
const argi = process.argv.indexOf('--plates');
const PLATES = argi > 0 && process.argv[argi + 1] ? path.resolve(process.argv[argi + 1]) : SRC_PLATES;

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const show = (rows, max = 6) => rows.slice(0, max).join(' | ') + (rows.length > max ? ` | … ${rows.length - max} more` : '');

// ─── bundle the real modules (in memory) ────────────────────────────────────

const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');
const ENTRY = `
export * as plates from ${JSON.stringify(PLATES)};
export * as mask from './src/lib/workspace/mask';
`;
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'plates-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	write: false,
	logLevel: 'silent',
});
ok('bundle builds (esbuild, $lib aliased, in memory)', built.errors.length === 0 && built.outputFiles.length === 1, `${path.relative(DECK, PLATES)} + src/lib/workspace/mask.ts`);
const { plates: P, mask: MK } = await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString('base64')}`);

const OFF = false;
const ON = true;

// ─── 1. marks in any case and spelling: masked without an officer ───────────
// [as typed or sent, as an officer-less console shows it]

const MARKS = [
	// lower and mixed case
	['mh47em9001', 'mh47em•••1'],
	['Mh47Em9001', 'Mh47Em•••1'],
	['mh 47 em 9001', 'mh 47 em •••1'],
	['Mh 47 Em 9001', 'Mh 47 Em •••1'],
	['mh-01-xx-0007', 'mh-01-xx-•••7'],
	['tg09ab1234', 'tg09ab•••4'],
	['Dl3CAB1234', 'Dl3CAB•••4'],
	// dotted
	['MH.47.EM.9001', 'MH.47.EM.•••1'],
	['mh.47.em.9001', 'mh.47.em.•••1'],
	// slashed
	['MH/47/EM/9001', 'MH/47/EM/•••1'],
	['mh/12/ab/1234', 'mh/12/ab/•••4'],
	// underscored
	['MH_47_EM_9001', 'MH_47_EM_•••1'],
	['ka_05_mm_1234', 'ka_05_mm_•••4'],
	// mixed separators, up to three between parts
	['mh 01-xx/0007', 'mh 01-xx/•••7'],
	['MH - 47 - EM - 9001', 'MH - 47 - EM - •••1'],
	['mH01.xX 0007', 'mH01.xX •••7'],
	// glued (no separator anywhere), any case; no series
	['mh12ab1234', 'mh12ab•••4'],
	['up14ab2211', 'up14ab•••1'],
	['mh1a1234', 'mh1a•••4'],
	['mh 1 2345', 'mh 1 •••5'],
	// a series that spells a month: glued in any case, or upper case with an upper-case state code, is a mark
	['dl8sep1234', 'dl8sep•••4'],
	['ka05may1234', 'ka05may•••4'],
	['MH.01.MAY.1234', 'MH.01.MAY.•••4'],
	['MH.12.JAN.4321', 'MH.12.JAN.•••1'],
	['mh01oct1234', 'mh01oct•••4'],
	// inside running text (titles, notes, answers)
	['PURSUIT — stolen mh47em9001 (FIR 4401/2026)', 'PURSUIT — stolen mh47em•••1 (FIR 4401/2026)'],
	['Stolen-vehicle sighting of MH.47.EM.9001 at EM-CAM-03', 'Stolen-vehicle sighting of MH.47.EM.•••1 at EM-CAM-03'],
	['mh01xx0007 was read on 24 Oct 2026 at 10 am', 'mh01xx•••7 was read on 24 Oct 2026 at 10 am'],
	['Checked MH_01_XX_0007 on 12 oct 2026, CCTV clear', 'Checked MH_01_XX_•••7 on 12 oct 2026, CCTV clear'],
	['two: mh47em9001 · MH/01/XX/0007.', 'two: mh47em•••1 · MH/01/XX/•••7.'],
	['line one\nwb06em9001', 'line one\nwb06em•••1'],
];

const markBad = MARKS.filter(([x, want]) => P.maskPlatesInText(x) !== want).map(([x, want]) => `${JSON.stringify(x)} → ${JSON.stringify(P.maskPlatesInText(x))} want ${JSON.stringify(want)}`);
ok('maskPlatesInText: lower-case, dotted, slashed, underscored, glued and month-series marks are masked (the 4-digit number but its last digit)', markBad.length === 0, show(markBad) || `${MARKS.length} spellings`);

const textOffBad = MARKS.filter(([x, want]) => P.displayText(x, OFF) !== want || MK.hasRawMark(P.displayText(x, OFF))).map(([x]) => `${x} → ${P.displayText(x, OFF)}`);
ok('displayText, no officer named: every spelling masked, no raw mark left (hasRawMark)', textOffBad.length === 0, show(textOffBad) || `${MARKS.length} rows`);

const textOnBad = MARKS.filter(([x]) => P.displayText(x, ON) !== x).map(([x]) => x);
ok('displayText, a named duty officer: every row shown as sent', textOnBad.length === 0, show(textOnBad) || `${MARKS.length} rows raw`);

// a plate field (props.plate, a sighting's plate) as typed or read
const PLATE_FIELDS = [
	['mh47em9001', 'mh47em•••1'],
	['MH.47.EM.9001', 'MH.47.EM.•••1'],
	['MH/47/EM/9001', 'MH/47/EM/•••1'],
	['MH_47_EM_9001', 'MH_47_EM_•••1'],
	['dl8sep1234', 'dl8sep•••4'],
];
const plateBad = PLATE_FIELDS.filter(([x, want]) => P.maskPlate(x) !== want || P.displayPlate(x, OFF) !== want || P.displayPlate(x, ON) !== x).map(
	([x, want]) => `${x} → ${P.maskPlate(x)} / ${P.displayPlate(x, OFF)} want ${want}`,
);
ok('maskPlate / displayPlate: a plate in any case or spelling is masked without an officer, raw with one', plateBad.length === 0, show(plateBad) || PLATE_FIELDS.map(([x]) => P.displayPlate(x, OFF)).join(' · '));

// ─── 2. not marks: byte for byte ───────────────────────────────────────────

const NOT_MARKS = [
	// dates (a month in mixed or lower case is a date, whatever the case of the word before it)
	'24 Oct 2026',
	'on 12 oct 2026',
	'As of 24 Oct 2026, the vehicle was last read at EM-CAM-03.',
	'as of 24 Oct 2026',
	'As 24 Oct 2026',
	'AS 24 Oct 2026 · as 1 jan 2027 · up 12 Dec 2026',
	'Retention ends on 22 Nov 2026.',
	'Closed 23 or 24 Oct 2026, held up 12 Oct 2026',
	'From 23-Oct-2026 to UP-24-Oct-2026, then 12/10/2026',
	'mh 01 may 1234 reads as a date: a lower-case state code with a month',
	'2026-10-24',
	// times
	'Plan review at 10 am 2026',
	'10:45 IST',
	'23:59:59 IST on 24 Oct 2026',
	'2026-10-24T10:45:00Z',
	'Filed at 01 38 2026',
	// years
	'Diversion via NH 48 since 2024',
	'in 2026',
	'1999–2026',
	// FIR numbers
	'FIR 4401/2026, Hare Street PS',
	'FIR No. 112/2026',
	'FIR 9/2026 · e-challan 2026/0042',
	// UUIDs (a URN's id): even a hex group shaped like a mark, in any case
	'vehicle:0f4c5a2e-ab12-3456-8333-944455556666',
	'vehicle:0f4c5a2e-dd12-3456-8333-944455556666',
	'VEHICLE:0F4C5A2E-DD12-3456-8333-944455556666',
	'event:44444444-5555-4666-8777-888888888888',
	// already masked, ids, junctions, two letters that are no state code
	'MH47EM•••1 at EM-CAM-03, J15, 4401/2026',
	'mh47em•••1',
	'',
];
const notBad = NOT_MARKS.filter((x) => P.maskPlatesInText(x) !== x || P.displayText(x, OFF) !== x).map((x) => `${JSON.stringify(x)} → ${JSON.stringify(P.maskPlatesInText(x))}`);
ok('dates, times, years, FIR numbers, UUIDs and masked marks come back byte for byte', notBad.length === 0, show(notBad) || `${NOT_MARKS.length} phrases unchanged`);
ok('null and undefined: the empty string (maskPlatesInText, displayText), null (maskPlate, displayPlate)', P.maskPlatesInText(null) === '' && P.maskPlatesInText(undefined) === '' && P.displayText(null, OFF) === '' && P.maskPlate(null) === null && P.displayPlate(undefined, OFF) === null);

// ─── 4. upper case masks exactly as before ─────────────────────────────────
// The pre-change pattern (and the oracle's city/common.py _PLATE_IN_TEXT_RE), copied as the reference.

const OLD_RE = /\b([A-Z]{2}[ -]?\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?)(\d{4})\b/g;
const oldMask = (s) => (s ? s.replace(OLD_RE, (_m, head, num) => `${head}•••${num.slice(-1)}`) : '');
const oldMaskPlate = (p) => {
	if (!p) return null;
	const m = oldMask(p);
	if (m !== p) return m;
	return p.length >= 6 ? `${p.slice(0, -4)}•••${p.slice(-1)}` : `•••${p.slice(-1)}`;
};
const UPPER = [
	'MH47EM9001',
	'MH 47 EM 9001',
	'MH-01-AB-1234',
	'MH01XX0007',
	'MH1A1234',
	'TN 9 1234',
	'PURSUIT — stolen MH47EM9001 (FIR 4401/2026)',
	'Stolen MH01XX0007 reported — FIR 9/2026, Hare Street PS; Sandbox',
	'MH12AB1234 · DL3CAB1234 · KA05MAY1234 · UP 14 AB 2211',
	'MH 01 MAY 1234',
	'DL 8 SEP 1234',
	'MH-01-OCT-1234',
	'AS 24 OCT 2026',
	'e-challan proposed for MH47EM9001 at 72 km/h on Sector V - New Town link (limit 50)',
	'MH47EM•••1 and MH01XX0007',
];
for (const code of MK.STATE_CODES) UPPER.push(`${code}01AB1234`, `${code} 01 AB 1234`, `${code}-1-1234`, `seen ${code}12C4321 at J15`);
const upperBad = UPPER.filter((x) => P.maskPlatesInText(x) !== oldMask(x) || P.displayText(x, OFF) !== oldMask(x) || P.displayText(x, ON) !== x).map((x) => `${x} → ${P.maskPlatesInText(x)} was ${oldMask(x)}`);
ok('upper-case marks mask exactly as before (the pre-change pattern; all 39 state codes, spaced, dashed and glued)', upperBad.length === 0, show(upperBad) || `${UPPER.length} rows identical, e.g. ${P.maskPlatesInText(UPPER[6])}`);
const UPPER_PLATES = ['MH47EM9001', 'MH01XX0007', 'DL3CAB1234', 'MH 01 AB 1234', 'ZZ12AB1234', 'TEST', 'X1', 'MH47EM•••1'];
const upperPlateBad = UPPER_PLATES.filter((x) => P.maskPlate(x) !== oldMaskPlate(x) || P.displayPlate(x, OFF) !== oldMaskPlate(x) || P.displayPlate(x, ON) !== x).map((x) => `${x} → ${P.maskPlate(x)} was ${oldMaskPlate(x)}`);
ok('maskPlate on an upper-case plate field (and the short-plate fallback) unchanged', upperPlateBad.length === 0, show(upperPlateBad) || UPPER_PLATES.map((x) => P.maskPlate(x)).join(' · '));
ok(
	'the 39 state and union-territory codes, in any case, start a mark; two letters that are no state code never do',
	MK.STATE_CODES.length === 39 &&
		MK.STATE_CODES.every((c) => P.maskPlatesInText(`${c.toLowerCase()}01ab1234`) === `${c.toLowerCase()}01ab•••4` && P.maskPlatesInText(`${c}.01.AB.1234`) === `${c}.01.AB.•••4`) &&
		['zz01ab1234', 'XX.01.AB.1234'].every((x) => P.maskPlatesInText(x) === x),
	`${MK.STATE_CODES.length} codes`,
);

// ─── 3. parity with workspace/mask.ts on the shared table ──────────────────

const SHARED = [...MARKS.map(([x]) => x), ...NOT_MARKS, ...UPPER, ...PLATE_FIELDS.map(([x]) => x)];
const parityBad = SHARED.filter((x) => P.maskPlatesInText(x) !== MK.maskMarks(x) || P.displayText(x, OFF) !== MK.maskMarks(x)).map((x) => `${JSON.stringify(x)}: plates ${JSON.stringify(P.maskPlatesInText(x))} · mask.ts ${JSON.stringify(MK.maskMarks(x))}`);
ok('parity: plates.ts and workspace/mask.ts mask the shared table identically', parityBad.length === 0, show(parityBad) || `${SHARED.length} rows`);
const rawLeft = SHARED.filter((x) => MK.hasRawMark(P.displayText(x, OFF))).map((x) => `${x} → ${P.displayText(x, OFF)}`);
const flagBad = [...MARKS.map(([x]) => x)].filter((x) => !MK.hasRawMark(x)).concat(NOT_MARKS.filter((x) => MK.hasRawMark(x)));
ok('parity: hasRawMark flags every mark row and no other; nothing displayText returns without an officer still holds one', rawLeft.length === 0 && flagBad.length === 0, show(rawLeft.concat(flagBad)) || `${SHARED.length} rows clean`);

// ─── 5. displayDetail: evidence payloads ───────────────────────────────────

const RAW_DETAIL = {
	id: 'vehicle:0f4c5a2e-dd12-3456-8333-944455556666',
	text: 'Stolen mh47em9001 read at EM-CAM-03',
	when: '24 Oct 2026',
	speed_kmh: 72,
	confirmed: true,
	none: null,
	nested: { list: ['MH.47.EM.9001', 42, false, 'MH47EM9001'], note: 'line one\nwb01xx0007', tab: 'a\tn01ab1234 is no mark' },
	mh01xx0007: 'a mark used as a key',
};
const BEFORE = JSON.stringify(RAW_DETAIL);
const masked = P.displayDetail(RAW_DETAIL, OFF);
const maskedJson = JSON.stringify(masked);
ok(
	'displayDetail, no officer: every string masked on its own (keys too; a mark right after a "\\n" escape; nested arrays)',
	masked.text === 'Stolen mh47em•••1 read at EM-CAM-03' &&
		masked.nested.list[0] === 'MH.47.EM.•••1' &&
		masked.nested.list[3] === 'MH47EM•••1' &&
		masked.nested.note === 'line one\nwb01xx•••7' &&
		Object.keys(masked).includes('mh01xx•••7') &&
		!Object.keys(masked).includes('mh01xx0007') &&
		!MK.hasRawMark(maskedJson.replace(/\\[nt]/g, ' ')),
	maskedJson.slice(0, 160),
);
ok(
	'displayDetail: ids, dates, numbers, booleans, null and a text after a "\\t" escape unchanged; the input never mutated',
	masked.id === RAW_DETAIL.id &&
		masked.when === '24 Oct 2026' &&
		masked.speed_kmh === 72 &&
		masked.confirmed === true &&
		masked.none === null &&
		masked.nested.list[1] === 42 &&
		masked.nested.list[2] === false &&
		masked.nested.tab === 'a\tn01ab1234 is no mark' &&
		JSON.stringify(RAW_DETAIL) === BEFORE &&
		masked !== RAW_DETAIL,
);
ok('displayDetail, a named duty officer: the payload itself, untouched', P.displayDetail(RAW_DETAIL, ON) === RAW_DETAIL && JSON.stringify(RAW_DETAIL) === BEFORE);
ok(
	'displayDetail: a string payload masked; a number, null and undefined as they are',
	P.displayDetail('mh47em9001 on 24 Oct 2026', OFF) === 'mh47em•••1 on 24 Oct 2026' && P.displayDetail(7, OFF) === 7 && P.displayDetail(null, OFF) === null && P.displayDetail(undefined, OFF) === undefined,
);
const cyc = { text: 'mh47em9001', inner: { plate: 'MH.47.EM.9001' } };
cyc.self = cyc;
let cycOut;
let cycErr = null;
try {
	cycOut = P.displayDetail(cyc, OFF);
} catch (e) {
	cycErr = e;
}
ok(
	'displayDetail: a payload JSON cannot read (a cycle) is still masked, the cycle cut — never handed back raw',
	!cycErr && cycOut !== cyc && cycOut?.text === 'mh47em•••1' && cycOut?.inner?.plate === 'MH.47.EM.•••1' && cycOut?.self === '[circular]',
	cycErr ? String(cycErr) : cycOut === cyc ? 'the raw payload came back' : JSON.stringify(cycOut),
);
const dated = P.displayDetail({ at: new Date('2026-10-24T10:45:00Z'), plate: 'mh47em9001' }, OFF);
ok('displayDetail: read as JSON first (what the evidence modal prints): a Date becomes its ISO string', dated.at === '2026-10-24T10:45:00.000Z' && dated.plate === 'mh47em•••1', JSON.stringify(dated));

// ─── 6. one rule: plates.ts reuses workspace/mask.ts ───────────────────────

if (PLATES === SRC_PLATES) {
	const src = readFileSync(SRC_PLATES, 'utf8');
	const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
	ok(
		'plates.ts imports the workspace rule (maskMarks from $lib/workspace/mask) and keeps no mark pattern of its own',
		/import\s*\{[^}]*\bmaskMarks\b[^}]*\}\s*from\s*'\$lib\/workspace\/mask'/.test(code) && !/\\d\{4\}/.test(code) && !/new RegExp|\/\\b/.test(code),
		'one rule for the deck',
	);
	ok(
		'exports unchanged in name: maskPlatesInText, maskPlate, displayPlate, displayText, displayDetail',
		['maskPlatesInText', 'maskPlate', 'displayPlate', 'displayText', 'displayDetail'].every((k) => typeof P[k] === 'function') && Object.keys(P).sort().join() === 'displayDetail,displayPlate,displayText,maskPlate,maskPlatesInText',
		Object.keys(P).sort().join(', '),
	);
} else {
	console.log(`note the source checks (group 6) run on the deck's plates.ts only; this run read ${PLATES}`);
}

if (failures) {
	console.error(`\n${failures} check(s) failed`);
	process.exit(1);
}
console.log('\nok   plates — any case and spelling masked, dates and ids untouched, parity with workspace/mask.ts, upper case unchanged, evidence payloads');
