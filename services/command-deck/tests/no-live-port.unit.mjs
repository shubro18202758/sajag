/**
 * No browser code path targets a live service port directly (audit F-CONN-01).
 *
 *   node tests/no-live-port.unit.mjs
 *
 * The deck reaches the oracle, the brain and the emulator ONLY through its
 * own origin's proxy prefixes (/api/v1, /api/convoy, /api/emulator — the vite
 * dev proxy and src/hooks.server.ts forward them to the ports the SERVER was
 * started with, a sandbox's for a dev deck). An absolute URL built in the
 * browser bypasses that: the old dev-only `http://localhost:8090` emulator
 * rung retried every proxy 404 against the LIVE emulator, and a body-less POST
 * (stop run N) is a CORS "simple request" that needs no preflight.
 *
 * Every client module under src/ (everything except server-only code:
 * src/lib/server/**, *.server.ts, +server.ts, hooks.server.ts) is parsed with
 * the TypeScript compiler — .svelte files: each <script> block, plus the
 * markup with its comments removed — and every string literal and template
 * literal (with its ${} holes) is checked. A literal fails when it:
 *   1. is an absolute URL (http/https/ws/wss, or protocol-relative //host)
 *      whose port is a live service port (8090 emulator, 8091 oracle,
 *      8092 brain, 5273 deck), on ANY host — a literal host or a `${…}` one;
 *   2. names a loopback host with a live port without a scheme
 *      (`localhost:8090`, `127.0.0.1:8091`, `[::1]:8092`, `0.0.0.0:5273`);
 *   3. is an absolute http(s)/ws(s) URL to a loopback host on any port (the
 *      browser has no business addressing a loopback service directly).
 * A self-check first proves the detector flags the shapes F-CONN-01 found
 * (the old EMULATOR_BASE constant, a `${location.hostname}:8090` template)
 * and passes the legitimate ones (proxy prefixes, same-origin ws://${host}
 * paths, copy that merely mentions a port).
 *
 * Exit 0 when no client literal matches; 1 with every offending file:line.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const SRC = path.join(DECK, 'src');
const ts = createRequire(path.join(DECK, 'package.json'))('typescript');

const LIVE_PORTS = ['8090', '8091', '8092', '5273'];
const PORT_ALT = LIVE_PORTS.join('|');
const LOOPBACK = String.raw`(?:localhost|[\w.-]+\.localhost|127(?:\.\d{1,3}){3}|0\.0\.0\.0|\[::1?\])`;
const RULES = [
	{ id: 'absolute-url-live-port', re: new RegExp(String.raw`(?:(?:https?|wss?):)?\/\/[^\s/'"\`]*:(?:${PORT_ALT})(?![0-9])`, 'i') },
	{ id: 'loopback-live-port', re: new RegExp(String.raw`${LOOPBACK}:(?:${PORT_ALT})(?![0-9])`, 'i') },
	{ id: 'absolute-url-loopback', re: new RegExp(String.raw`(?:https?|wss?):\/\/${LOOPBACK}(?::|\/|$)`, 'i') },
];

/** Rule ids the literal text breaks ([] = clean). */
function offences(text) {
	return RULES.filter((r) => r.re.test(text)).map((r) => r.id);
}

/** Every string / template literal in a TS/JS source, with its 1-based line (+ lineOffset). */
function literals(code, file, lineOffset = 0) {
	const sf = ts.createSourceFile(file, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
	const out = [];
	const visit = (node) => {
		if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
			out.push({ text: node.text, line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1 + lineOffset });
		} else if (ts.isTemplateExpression(node)) {
			// the whole template, holes included: `http://${location.hostname}:8090` must read as one URL
			out.push({ text: node.getText(sf).slice(1, -1), line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1 + lineOffset });
		}
		ts.forEachChild(node, visit);
	};
	visit(sf);
	return out;
}

/** A .svelte file: its script blocks as TS, the markup (comments removed) as text lines. */
function svelteLiterals(code, file) {
	const out = [];
	const scriptRe = /<script\b[^>]*>([\s\S]*?)<\/script>/g;
	let m;
	let markup = code;
	while ((m = scriptRe.exec(code))) {
		const body = m[1];
		const start = m.index + m[0].indexOf(body);
		const lineOffset = code.slice(0, start).split('\n').length - 1;
		out.push(...literals(body, file, lineOffset));
		markup = markup.replace(m[0], m[0].replace(/[^\n]/g, ' '));
	}
	markup = markup.replace(/<style\b[^>]*>[\s\S]*?<\/style>/g, (s) => s.replace(/[^\n]/g, ' '));
	markup = markup.replace(/<!--[\s\S]*?-->/g, (s) => s.replace(/[^\n]/g, ' '));
	markup.split('\n').forEach((text, i) => {
		if (text.trim()) out.push({ text, line: i + 1 });
	});
	return out;
}

const SERVER_ONLY = (rel) =>
	rel.startsWith('lib/server/') || /(^|\/)hooks\.server\.[jt]s$/.test(rel) || /\.server\.[jt]s$/.test(rel) || /(^|\/)\+server\.[jt]s$/.test(rel);

function* walk(dir) {
	for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
		const p = path.join(dir, e.name);
		if (e.isDirectory()) yield* walk(p);
		else if (/\.(ts|js|mjs|svelte)$/.test(e.name)) yield p;
	}
}

let failures = 0;
const ok = (name, pass, detail = '') => {
	console.log(`${pass ? 'ok  ' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`);
	if (!pass) failures++;
};

// ── self-check: the detector flags F-CONN-01's shapes and passes the legitimate ones ──
const MUST_FLAG = [
	["export const EMULATOR_BASE = 'http://localhost:8090';", 'the old emulator rung'],
	['const u = `http://${location.hostname}:8090/api/v1/emulator/runs/${id}/stop`;', 'a template host + live port'],
	["fetch('//127.0.0.1:8091/api/v1/events')", 'protocol-relative oracle'],
	['new WebSocket(`ws://localhost:8092/ws/convoy/${id}`)', 'a ws to the live brain'],
	["const base = 'localhost:5273';", 'scheme-less loopback + deck port'],
	["const x = 'http://127.0.0.1:8162/health';", 'any absolute loopback URL'],
];
const MUST_PASS = [
	["const EMULATOR_PROXY_PATH = '/api/emulator';", 'the proxy prefix'],
	['const u = `${protocol}//${host}${BRAIN_API}/ws/event/${id}`;', 'a same-origin ws URL'],
	["const copy = 'cause-tape injection on loopback :8090';", 'copy that names a port'],
	["const u = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';", 'an external https URL'],
];
for (const [code, what] of MUST_FLAG) {
	const hit = literals(code, 'selfcheck.ts').flatMap((l) => offences(l.text));
	ok(`self-check flags ${what}`, hit.length > 0, hit.join(',') || 'not flagged');
}
for (const [code, what] of MUST_PASS) {
	const hit = literals(code, 'selfcheck.ts').flatMap((l) => offences(l.text));
	ok(`self-check passes ${what}`, hit.length === 0, hit.join(',') || 'clean');
}
// a commented-out URL in markup is not code; a live one in markup is
ok('self-check: svelte markup is scanned, comments are not', svelteLiterals('<!-- http://localhost:8090 -->\n<a href="http://localhost:8091/x">x</a>', 'x.svelte').flatMap((l) => offences(l.text)).length > 0
	&& svelteLiterals('<!-- http://localhost:8090 -->\n<p>ok</p>', 'x.svelte').flatMap((l) => offences(l.text)).length === 0);

// ── the client tree ─────────────────────────────────────────────────────────
const hits = [];
let scanned = 0;
for (const file of walk(SRC)) {
	const rel = path.relative(SRC, file).split(path.sep).join('/');
	if (SERVER_ONLY(rel)) continue;
	scanned++;
	const code = fs.readFileSync(file, 'utf8');
	const lits = file.endsWith('.svelte') ? svelteLiterals(code, file) : literals(code, file);
	for (const l of lits) {
		const why = offences(l.text);
		if (why.length) hits.push(`src/${rel}:${l.line} [${why.join(',')}] ${l.text.trim().slice(0, 120)}`);
	}
}
ok(`client code builds no absolute URL to a live port (${LIVE_PORTS.join('/')}) or a loopback host — ${scanned} client modules`, hits.length === 0, hits.length ? `\n  ${hits.join('\n  ')}` : 'none');
ok('the scan saw the client tree (ops/client.ts, the emulator caller, is a client module)', scanned > 100 && fs.existsSync(path.join(SRC, 'lib/ops/client.ts')));

if (failures) {
	console.log(`no-live-port: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('no-live-port: all checks passed');
