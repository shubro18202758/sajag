/**
 * Record the OSINT and DSS contract fixtures from the int3cl SANDBOX oracle
 * (UI-S7B; contracts C-C + C-U). GET only — never generate in a test.
 *
 *   node tests/contract/record-osint.mjs [base]   # default http://127.0.0.1:8162
 *
 * The base is guarded before any request (osint-hygiene.mjs
 * recordBaseRefusal): host exactly 127.0.0.1; the live ports (:5273 :8091
 * :8092 :8090 …) and int3c (:8161) always refused; any port but :8162 only
 * with RECORD_OSINT_ALLOW_PORT=<that port>.
 *
 * int3cl is seeded ONLY from OS-2's synthetic capture (plan R13: fictional
 * `*.example` publishers plus the public-domain SACHET sample), so these
 * recordings carry no real third-party OSINT content. NEVER record from
 * int3c (it holds the real PoC captures for parity runs).
 *
 * The recorder checks every payload by the SAME rules the replay re-asserts
 * (tests/contract/osint-hygiene.mjs): a publisher-like string at any depth,
 * dotted or not, or a URL / source-link host that is not `*.example` or
 * `sachet.ndma.gov.in`; a person key by substring at any depth; a raw
 * registration mark left after masking — any one discards the recording,
 * which is never edited by hand (plan R13). The C-U is also checked for its
 * shape (dssShapeProblems).
 *
 * Writes (into tests/contract/fixtures/, gitignored scratch except when the
 * files are committed deliberately):
 *   osint_event.entity.json   one osint_event CityEntity (the raw row)
 *   place.entity.json         one place CityEntity (the raw row)
 *   osint.feeditem.json       one osint FeedItem (the raw row)
 *   dss.decisionsupport.json  one C-U DecisionSupport (GET of an existing one)
 * and registers them in manifest.json (origin 'osint-sandbox', the recording
 * base and date).
 */

import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ALLOWED_HOST, dssShapeProblems, osintHygiene, recordBaseRefusal } from './osint-hygiene.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.join(HERE, 'fixtures');
const BASE = (process.argv[2] ?? 'http://127.0.0.1:8162').replace(/\/$/, '');
{
	const refused = recordBaseRefusal(BASE, process.env.RECORD_OSINT_ALLOW_PORT ?? null);
	if (refused) {
		console.error(`FAIL record-osint: ${BASE} — ${refused}. Nothing was requested.`);
		process.exit(2);
	}
}

const get = async (route) => {
	const res = await fetch(`${BASE}${route}`, { signal: AbortSignal.timeout(20000) });
	if (!res.ok) throw new Error(`${res.status} ${route}`);
	return res.json();
};

/** The C6 mask over free text (city/common.py): MH47EM9001 → MH47EM•••1. */
const maskMarks = (s) => String(s).replace(/\b([A-Z]{2}[ -]?\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?)(\d{4})\b/g, (_m, head, d) => `${head}•••${d.slice(-1)}`);

function assertRecordable(name, payload, { dss = false } = {}) {
	const h = osintHygiene(payload);
	const problems = [
		...h.badPublishers.map((p) => `${name}: non-synthetic publisher '${p}'`),
		...h.badHosts.map((x) => `${name}: non-synthetic host '${x}'`),
		...h.personKeys.map((k) => `${name}: person key '${k}'`),
		...h.plates.map((m) => `${name}: raw registration mark left after masking (${m})`),
		...(dss ? dssShapeProblems(payload).map((p) => `${name}: C-U shape — ${p}`) : []),
	];
	if (problems.length) throw new Error(`recording DISCARDED (never edited by hand):\n  ${problems.join('\n  ')}`);
	return { pubs: h.publishers };
}

/** Deep-mask every string value (C6) — the OSINT rows carry no marks, this is the guard. */
function masked(payload) {
	const out = JSON.parse(JSON.stringify(payload));
	const maskStrings = (node) => {
		if (Array.isArray(node)) {
			node.forEach(maskStrings);
			return node;
		}
		if (node && typeof node === 'object') {
			for (const [k, x] of Object.entries(node)) node[k] = typeof x === 'string' ? maskMarks(x) : maskStrings(x);
			return node;
		}
		return node;
	};
	return maskStrings(out);
}

const manifestPath = path.join(FIXTURES, 'manifest.json');
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
manifest.fixtures = manifest.fixtures ?? {};

async function record(file, route, pick) {
	const body = await get(route);
	const chosen = pick(body);
	if (!chosen) throw new Error(`${route}: nothing to record (the sandbox has no such row)`);
	const clean = masked(chosen);
	const { pubs } = assertRecordable(file, clean);
	writeFileSync(path.join(FIXTURES, file), `${JSON.stringify(clean, null, '\t')}\n`);
	manifest.fixtures[`osint:${file}`] = { file, status: 200, origin: 'osint-sandbox', route, recorded_from: BASE, recorded_at: new Date().toISOString(), publishers: pubs };
	console.log(`rec  ${route} → ${file} (publishers: ${pubs.join(', ') || 'none in payload'})`);
}

await record('osint_event.entity.json', '/api/v1/city/entities?kinds=osint_event', (b) =>
	// prefer a row whose props.dss carries an id (the C-U is then recorded from
	// the SAME subject, GET only); the synthetic-publisher assertion below
	// still discards any row whose provenance is not synthetic
	(b.entities ?? []).find(
		(e) => e.kind === 'osint_event' && typeof e.props?.dss?.dss_id === 'string' && (e.props?.provenance?.publishers ?? []).every((p) => ALLOWED_HOST.test(p)),
	) ?? (b.entities ?? []).find((e) => e.kind === 'osint_event' && (e.props?.provenance?.publishers ?? []).every((p) => ALLOWED_HOST.test(p))),
);
await record('place.entity.json', '/api/v1/city/entities?kinds=place', (b) => (b.entities ?? []).find((e) => e.kind === 'place'));

// one osint FeedItem: a "Situation surfaced" row whose subject is the recorded osint_event
const feedBody = await get('/api/v1/city/feed?limit=400');
const items = Array.isArray(feedBody?.items) ? feedBody.items : [];
const entity = JSON.parse(readFileSync(path.join(FIXTURES, 'osint_event.entity.json'), 'utf8'));
const row =
	items.find((i) => i.kind === 'osint' && (i.urns ?? []).includes(entity.urn)) ??
	items.find((i) => i.kind === 'osint');
if (!row) throw new Error('/city/feed: no osint row naming the recorded event');
{
	const clean = masked(row);
	const { pubs } = assertRecordable('osint.feeditem.json', clean);
	writeFileSync(path.join(FIXTURES, 'osint.feeditem.json'), `${JSON.stringify(clean, null, '\t')}\n`);
	manifest.fixtures['osint:osint.feeditem.json'] = { file: 'osint.feeditem.json', status: 200, origin: 'osint-sandbox', route: '/api/v1/city/feed?limit=400', recorded_from: BASE, recorded_at: new Date().toISOString(), publishers: pubs };
	console.log(`rec  /api/v1/city/feed → osint.feeditem.json (${row.id})`);
}

// one C-U DecisionSupport: the entity's own dss id, GET only (never generate)
const dssId = entity.props?.dss?.dss_id ?? entity.props?.dss?.dssId ?? null;
if (!dssId) throw new Error('the recorded osint_event carries no props.dss id — cannot record a C-U without generating one');
{
	const dss = await get(`/api/v1/decision-support/${dssId}`);
	const clean = masked(dss);
	assertRecordable('dss.decisionsupport.json', clean, { dss: true });
	writeFileSync(path.join(FIXTURES, 'dss.decisionsupport.json'), `${JSON.stringify(clean, null, '\t')}\n`);
	manifest.fixtures['osint:dss.decisionsupport.json'] = { file: 'dss.decisionsupport.json', status: 200, origin: 'osint-sandbox', route: `/api/v1/decision-support/${dssId}`, recorded_from: BASE, recorded_at: new Date().toISOString(), note: 'GET of an existing proposal — never generated in a test' };
	console.log(`rec  /api/v1/decision-support/${dssId} → dss.decisionsupport.json (state ${dss.state})`);
}

writeFileSync(manifestPath, `${JSON.stringify(manifest, null, '\t')}\n`);
console.log('ok   contract fixtures recorded from the int3cl sandbox (synthetic publishers verified, marks masked)');
