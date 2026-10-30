/**
 * Derive tests/fixtures/workspace/captured.json from the redesign prototype's
 * masked capture (data/live-data.js, `window.SAJAG_DATA`).
 *
 *   node tests/fixtures/workspace/derive.mjs <redesign/prototype dir>
 *
 * Not run by any gate: the committed captured.json is the fixture
 * (tests/workspace.unit.mjs reads only that file). This script documents how
 * it was made and re-makes it byte for byte from the same capture.
 *
 * Reduction (what the selector tests read, ≤ 150 KB):
 *   - the watchlisted vehicle MH47EM•••1 and every object linked to it: its
 *     snapshot row, its dossier (the 50 related rows) and the one other
 *     dossier that links a further read to it (51 linked objects in all);
 *   - the city feed rows of the six hours before the capture (`feedIn`,
 *     `watchReads`), props cut to a short whitelist.
 *
 * Ethics rules applied in code (never by a list of names in this file):
 *   - registration marks stay masked: `plate_masked` and the masked labels;
 *     the `plate` field is dropped everywhere, so no raw-mark field survives;
 *   - every human actor value (actor_kind "human") and every officer field
 *     (decided_by, requested_by, opened_by, earmarked_by, officer) becomes the
 *     fictional "Sandbox Officer"; the same strings are replaced inside every
 *     text (names are collected from the capture at run time and asserted
 *     absent afterwards); system and machine actors keep their names;
 *   - officer notes and claimed officers are dropped.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PROTO = process.argv[2];
if (!PROTO) {
	console.error('usage: node derive.mjs <redesign/prototype dir>');
	process.exit(2);
}

// The capture is one JSON object assigned to window.SAJAG_DATA: parse it as JSON, never execute it.
const raw = readFileSync(path.join(PROTO, 'data/live-data.js'), 'utf8');
const start = raw.indexOf('=', raw.indexOf('window.SAJAG_DATA'));
const end = raw.lastIndexOf('}');
if (start < 0 || end < start) throw new Error('unexpected capture framing (window.SAJAG_DATA = {…};)');
const D = JSON.parse(raw.slice(start + 1, end + 1));
const VEHICLE = 'vehicle:1b94e9d2-7e11-4174-a735-7dd3be3189cf';
const AS_OF = D.snapshot.as_of;
const SANDBOX_OFFICER = 'Sandbox Officer';
const NOW = Date.parse(AS_OF);

// ── 1. the human values to replace, collected from the capture ────────────
const OFFICER_KEYS = new Set(['decided_by', 'requested_by', 'opened_by', 'earmarked_by', 'officer']);
const DROP_KEYS = new Set(['plate', 'note', 'claimed_officer', 'withheld_reason_note']);
const human = new Set();
const collect = (v) => {
	if (typeof v !== 'string' || !v.trim()) return;
	human.add(v);
	const bare = v.replace(/\s*\([^)]*\)\s*$/, '').trim();
	if (bare && bare !== v) human.add(bare);
};
(function walk(o) {
	if (Array.isArray(o)) return o.forEach(walk);
	if (!o || typeof o !== 'object') return;
	if (o.actor_kind === 'human') collect(o.actor);
	for (const [k, v] of Object.entries(o)) {
		if (OFFICER_KEYS.has(k)) collect(v);
		walk(v);
	}
})(D);
const NAMES = [...human].sort((a, b) => b.length - a.length);

function scrubText(s) {
	let out = s;
	for (const n of NAMES) out = out.split(n).join(SANDBOX_OFFICER);
	return out;
}

/** A deep copy: dropped keys removed, officer fields and human names replaced. */
function scrub(o) {
	if (Array.isArray(o)) return o.map(scrub);
	if (typeof o === 'string') return scrubText(o);
	if (!o || typeof o !== 'object') return o;
	const out = {};
	for (const [k, v] of Object.entries(o)) {
		if (DROP_KEYS.has(k)) continue;
		if (OFFICER_KEYS.has(k)) out[k] = typeof v === 'string' && v.trim() ? SANDBOX_OFFICER : v;
		else out[k] = scrub(v);
	}
	if (out.actor_kind === 'human' && typeof out.actor === 'string') out.actor = SANDBOX_OFFICER;
	return out;
}

// one feed row: the C-C wire shape, props cut to a whitelist; `withText` false keeps only what the
// selectors read (time, kind, urns, actor kind, source) for rows that do not concern the vehicle
const FEED_PROPS = ['camera_id', 'speed_kmh', 'hit', 'plate_masked', 'rule_id', 'status', 'tier', 'confidence', 'event_kind'];
function feedRow(i, withText = true) {
	const props = withText ? Object.fromEntries(Object.entries(i.props ?? {}).filter(([k]) => FEED_PROPS.includes(k))) : {};
	return { id: i.id, t: i.t, kind: i.kind, urns: i.urns ?? [], actor: i.actor ?? null, actor_kind: i.actor_kind, text: withText ? (i.text ?? '') : '', source: i.source, severity: i.severity, props };
}

// ── 2. the vehicle's neighbourhood ───────────────────────────────────────
const ENTITY_KEEP = ['urn', 'kind', 'id', 'label', 'lon', 'lat', 'state', 'source', 't', 'links', 'props'];
/** The props each kind's adapter and the inspector read; everything else is dropped. */
const PROPS_KEEP = {
	vehicle: ['plate_masked', 'vehicle_class', 'earmark_state', 'lawful_basis', 'earmark_reason', 'retention_until', 'last_sighting_id', 'last_camera_id', 'last_speed_kmh', 'last_heading', 'matched_plate_hit'],
	sighting: ['plate_masked', 'camera_id', 'vehicle_id', 'speed_kmh', 'heading', 'vehicle_class', 'matched_plate_hit', 'run_id', 'read_source'],
	camera: ['camera_kind', 'camera_source', 'registered', 'junction_id', 'segment_id', 'heading_deg', 'reads_15m', 'hits_15m', 'last_read_t'],
	recommendation: ['rule_id', 'status', 'recommendation', 'decided_by', 'decided_at', 'created_at', 'vehicle_id', 'sighting_id', 'camera_id', 'plate_masked', 'evidence', 'vehicle_reported_stolen', 'withheld_text'],
	event: ['event_kind', 'title', 'status', 'protection_class', 'crowd_class', 'route_spines', 'actual_start', 'actual_end', 'planned_start', 'planned_end', 'metadata'],
};
const EVIDENCE_KEEP = ['speed_kmh', 'speed_limit_kmh', 'excess_kmh', 'road_name', 'segment_id', 'camera_id', 'fir_ref'];
const pick = (o, keys) => Object.fromEntries(keys.filter((k) => k in o).map((k) => [k, o[k]]));

const vDossier = D.dossiers[VEHICLE];
const relatedUrns = new Set(vDossier.related.map((r) => r.entity.urn));
// the other dossiers whose related rows link a further object to the vehicle
const extraDossiers = Object.entries(D.dossiers)
	.filter(([urn, d]) => urn !== VEHICLE && d && d.related.some((r) => !relatedUrns.has(r.entity.urn) && r.entity.urn !== VEHICLE && (r.entity.links ?? []).includes(VEHICLE)))
	.map(([, d]) => d);

const inScope = new Set([VEHICLE, ...relatedUrns]);
for (const d of extraDossiers) for (const r of d.related) if ((r.entity.links ?? []).includes(VEHICLE)) inScope.add(r.entity.urn);

function entity(e) {
	const o = pick(e, ENTITY_KEEP);
	o.links = (o.links ?? []).filter((l) => inScope.has(l));
	const keep = PROPS_KEEP[o.kind];
	if (keep) o.props = pick(o.props ?? {}, keep);
	if (o.props?.evidence) o.props.evidence = pick(o.props.evidence, EVIDENCE_KEEP);
	return scrub(o);
}

const snapshotEntities = D.snapshot.entities.filter((e) => inScope.has(e.urn)).map(entity);
// ── 3. the feed rows of the six hours before the capture ─────────────────
const SIX_H = 6 * 3600e3;
const feed = D.feed.items
	.filter((i) => {
		const t = Date.parse(i.t);
		return Number.isFinite(t) && t <= NOW && t >= NOW - SIX_H;
	})
	.map((i) => scrub(feedRow(i, (i.urns ?? []).some((u) => inScope.has(u)))));
const feedIds = new Set(feed.filter((r) => r.text).map((r) => r.id));

// a dossier's audit row that the feed above carries in full is written as its id (the test rehydrates it)
const dossiers = [vDossier, ...extraDossiers].map((d) => ({
	entity: entity(d.entity),
	related: d.related.filter((r) => inScope.has(r.entity.urn)).map((r) => ({ relation: r.relation, entity: entity(r.entity) })),
	audit: d === vDossier ? d.audit.map((a) => (feedIds.has(a.id) ? a.id : scrub(feedRow(a)))) : [],
}));

// ── 4. write: compact JSON, one record per line ──────────────────────────
const meta = {
	what: 'The selector fixture of tests/workspace.unit.mjs: the watchlisted vehicle MH47EM•••1, every object linked to it, and the city feed of the six hours before the capture.',
	derived_from: 'redesign prototype data/live-data.js (window.SAJAG_DATA): GETs of an emulated scenario, registration marks masked at capture',
	captured_at: AS_OF,
	names: 'every human actor and officer value is the fictional Sandbox Officer; system and machine actors keep their names',
	marks: 'masked only (plate_masked); no raw-mark field',
	feed_text: 'kept for rows about the vehicle and its linked objects; other rows keep time, kind, urns, actor kind and source',
	audit_refs: "a dossier audit entry that is a string is the id of the feed row carrying it in full",
	made_by: 'tests/fixtures/workspace/derive.mjs',
};
const J = (v) => JSON.stringify(v);
const list = (rows, pad) => `[\n${rows.map((r) => `${pad}${J(r)}`).join(',\n')}\n${pad.slice(1)}]`;
const text =
	`{\n\t"_meta": ${J(meta)},\n\t"as_of": ${J(AS_OF)},\n\t"vehicle": ${J(VEHICLE)},\n` +
	`\t"snapshot": {"as_of": ${J(AS_OF)}, "feeds": {}, "entities": ${list(snapshotEntities, '\t\t')}},\n` +
	`\t"dossiers": [\n${dossiers
		.map((d) => `\t\t{"entity": ${J(d.entity)},\n\t\t"related": ${list(d.related, '\t\t\t')},\n\t\t"audit": ${list(d.audit, '\t\t\t')}}`)
		.join(',\n')}\n\t],\n` +
	`\t"feed": {"items": ${list(feed, '\t\t')}}\n}\n`;
JSON.parse(text);
for (const n of NAMES) {
	if (n !== SANDBOX_OFFICER && text.includes(n)) throw new Error(`a collected human value survived (length ${n.length})`);
}
if (/"plate"\s*:/.test(text)) throw new Error('a raw-mark field survived');
const file = path.join(HERE, 'captured.json');
writeFileSync(file, text);
console.log(`captured.json: ${(Buffer.byteLength(text) / 1024).toFixed(1)} KB · ${snapshotEntities.length} snapshot entities · ${dossiers.length} dossiers (${dossiers.map((d) => d.related.length).join('+')} related) · ${feed.length} feed rows · ${NAMES.length} human values replaced`);
