/**
 * The OSINT / DSS fixture hygiene rules (UI-S7B; plan R13; ethics rules 3, 5
 * and 9), shared by the replay (tests/contract/run.mjs §16) and the recorder
 * (tests/contract/record-osint.mjs) so a fixture is checked by ONE rule set
 * when it is written and every time it is replayed. Pure: no I/O.
 *
 *   publishers  every string under a publisher-like key at ANY depth —
 *               `publisher`, `publishers`, `publisher_name`, `provenance.
 *               publishers`, `props.provenance.publishers`, … (any key whose
 *               name contains "publisher"), dotted or not — must be a
 *               `*.example` host or `sachet.ndma.gov.in`. A bare outlet NAME
 *               ("Times of India") is not a host and fails.
 *   hosts       every URL host in any string (with a scheme, or scheme-less
 *               `www.x.com/…` / `x.co.in`), and every string under a source-
 *               link key (`url`, `link`, `href`, `host`, `domain`, `site`,
 *               `source_url`, `source_link`, …), must be one of those hosts.
 *   persons     no key containing a person term at any depth — the
 *               osint_common FORBIDDEN_KEY_RE, matched as a SUBSTRING (so
 *               `author_name`, `reporter_name`, `poster_handle` fail), plus
 *               a person `name` (`full_name`, `person_name`, `first_name`,
 *               `last_name`, `display_name`, `real_name`). Exempt exactly as
 *               osint_common.ethics: `surface_forms` (a list), `surfaced` (a
 *               count), `touches_persons` (a bool), and a whole opaque id
 *               (40-hex sha1 or canonical lower-case uuid) as a key.
 *   plates      no RAW registration mark in any string: 39 state/UT codes,
 *               any case, separators space . - / _ (uuids and sha1 ids held
 *               out first). A masked mark (MH47EM•••1) is fine.
 */

export const ALLOWED_HOST = /^(?:[a-z0-9-]+\.)*[a-z0-9-]+\.example$|^sachet\.ndma\.gov\.in$/i;

/** osint_common.ethics FORBIDDEN_KEY_RE (frozen, X18), as a substring, case-insensitive. */
export const FORBIDDEN_KEY_RE =
	/author|person|handle|username|byline|reporter|poster|uploader|suspect|accused|victim|owner|driver_name|face|biometric|individual_/i;
/** A person's NAME under a generic key (the denylist covers `<term>_name`). */
const PERSON_NAME_KEY = /^(?:full|first|last|middle|display|real|given|family|sur)_?name$/i;
const EXEMPT_KEYS = { surface_forms: (v) => Array.isArray(v), surfaced: (v) => Number.isInteger(v), touches_persons: (v) => typeof v === 'boolean' };
const OPAQUE_ID = /^(?:[0-9a-f]{40}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;

const PUBLISHER_KEY = /publisher/i;
const LINK_KEY = /(?:^|_)(?:url|urls|uri|link|links|href|host|hosts|domain|domains|site|sites)$/i;

/** URL hosts in free text: with a scheme, or a scheme-less dotted name with a real-world TLD. */
const SCHEME_HOST = /\b[a-z][a-z0-9+.-]*:\/\/([a-z0-9.-]+)/gi;
const BARE_HOST = /(?<![@\w.-])((?:[a-z0-9-]+\.)+(?:com|in|org|net|co|news|info|io|gov|edu|tv|me|uk|us|biz|online|site|live|example))(?=[/:?#\s)\]'",;]|$)/gi;

const STATES =
	'AN|AP|AR|AS|BR|CG|CH|DD|DL|DN|GA|GJ|HP|HR|JH|JK|KA|KL|LA|LD|MH|ML|MN|MP|MZ|NL|OD|OR|PB|PY|RJ|SK|TG|TN|TR|TS|UK|UP|WB';
/** A raw Indian registration mark, any case, separators space . - / _ (validate_glm's rule, widened to any case). */
export const RAW_PLATE = new RegExp(`(?<![A-Za-z0-9])(?:${STATES})[ ._/-]?\\d{1,2}[ ._/-]?(?:[A-Za-z]{1,3}[ ._/-]?)?\\d{4}(?![A-Za-z0-9])`, 'i');
const ID_IN_TEXT = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\b[0-9a-f]{40}\b/gi;

/** Is `key` (with its value) a person key? */
export function isPersonKey(key, value) {
	if (key == null) return false;
	const k = String(key);
	if (OPAQUE_ID.test(k)) return false;
	if (Object.hasOwn(EXEMPT_KEYS, k)) return !EXEMPT_KEYS[k](value);
	return FORBIDDEN_KEY_RE.test(k) || PERSON_NAME_KEY.test(k);
}

/** Every URL host named in a string. */
export function hostsIn(text) {
	const out = new Set();
	for (const m of String(text).matchAll(SCHEME_HOST)) out.add(m[1].toLowerCase());
	for (const m of String(text).matchAll(BARE_HOST)) out.add(m[1].toLowerCase());
	return out;
}

/**
 * Check one payload. Returns {publishers, badPublishers, hosts, badHosts,
 * personKeys, plates} — `plates` quoted masked (head + •••).
 */
export function osintHygiene(payload) {
	const publishers = new Set();
	const hosts = new Set();
	const personKeys = new Set();
	const plates = new Set();
	const walk = (v, path, underPublisher, underLink) => {
		if (Array.isArray(v)) {
			v.forEach((x, i) => walk(x, `${path}[${i}]`, underPublisher, underLink));
			return;
		}
		if (v && typeof v === 'object') {
			for (const [k, x] of Object.entries(v)) {
				if (isPersonKey(k, x)) personKeys.add(`${path}.${k}`.replace(/^\./, ''));
				walk(x, `${path}.${k}`, underPublisher || PUBLISHER_KEY.test(k), underLink || LINK_KEY.test(k));
			}
			return;
		}
		if (typeof v !== 'string') return;
		if (underPublisher) publishers.add(v);
		for (const h of hostsIn(v)) hosts.add(h);
		if (underLink && v.trim()) {
			const t = v.trim();
			// a link value names a host whatever its form: the host part of `scheme://h/…`, `h/…` or `h`
			const h = (t.match(/^[a-z][a-z0-9+.-]*:\/\/([^/?#\s]+)/i)?.[1] ?? (/^[^\s/]+\.[^\s/]+(?:[/?#]|$)/.test(t) ? t.split(/[/?#]/)[0] : null))?.toLowerCase();
			if (h) hosts.add(h);
		}
		const scrubbed = v.replace(ID_IN_TEXT, ' ');
		const m = scrubbed.match(RAW_PLATE);
		if (m) plates.add(m[0].replace(/\d{3}(\d)$/, '•••$1')); // quoted masked: MH47EM9001 → MH47EM•••1
	};
	walk(payload, '', false, false);
	return {
		publishers: [...publishers],
		badPublishers: [...publishers].filter((p) => !ALLOWED_HOST.test(p)),
		hosts: [...hosts],
		badHosts: [...hosts].filter((h) => !ALLOWED_HOST.test(h)),
		personKeys: [...personKeys],
		plates: [...plates],
	};
}

/** The C-U DecisionSupport states (osint_common.types DssState). */
export const DSS_STATES = ['proposed', 'approved', 'rejected', 'deferred', 'superseded', 'expired'];

/**
 * The C-U shape a recorded DecisionSupport must hold (raw wire payload):
 * a known `state` equal to `human_gate.state`; a non-empty `coa_set` with
 * unique coa ids; `recommendation.ranked_coa_ids` non-empty and every id in
 * the coa set; `top_coa_id` a coa of the set and the first ranked id;
 * `best_blocked` (when set) a ranked id other than the pick (osint_common
 * types.py Recommendation / DecisionSupport validators); the honest
 * SIMULATED label (the outcomes are simulated). Returns a list of problems.
 */
export function dssShapeProblems(d) {
	const p = [];
	if (!d || typeof d !== 'object') return ['not an object'];
	if (!DSS_STATES.includes(d.state)) p.push(`state '${d.state}' not one of ${DSS_STATES.join('|')}`);
	if (d.human_gate?.state !== d.state) p.push(`human_gate.state '${d.human_gate?.state}' ≠ state '${d.state}'`);
	const coas = Array.isArray(d.coa_set) ? d.coa_set : [];
	if (!coas.length) p.push('coa_set empty');
	const ids = coas.map((c) => c?.coa_id);
	if (ids.some((x) => typeof x !== 'string' || !x)) p.push('a coa without a coa_id');
	if (new Set(ids).size !== ids.length) p.push('duplicate coa ids');
	const ranked = Array.isArray(d.recommendation?.ranked_coa_ids) ? d.recommendation.ranked_coa_ids : [];
	if (!ranked.length) p.push('recommendation.ranked_coa_ids empty');
	const stray = ranked.filter((r) => !ids.includes(r));
	if (stray.length) p.push(`ranked ids not in coa_set: ${stray.join(',')}`);
	const top = d.recommendation?.top_coa_id;
	if (!ids.includes(top)) p.push(`top_coa_id '${top}' names no coa of coa_set`);
	if (ranked.length && top !== ranked[0]) p.push(`ranked_coa_ids does not start with top_coa_id '${top}' (starts '${ranked[0]}')`);
	const bb = d.recommendation?.best_blocked?.coa_id;
	if (bb != null && (!ranked.includes(bb) || bb === top)) p.push(`best_blocked '${bb}' is not a ranked alternative to the pick`);
	if (!Array.isArray(d.labels) || !d.labels.includes('SIMULATED')) p.push('no SIMULATED label');
	if (typeof d.event_urn !== 'string' || !/^osint_event:/.test(d.event_urn)) p.push(`event_urn '${d.event_urn}' is not an osint_event urn`);
	return p;
}

/**
 * The recorder's target guard (record-osint.mjs; brief R13, audit E-S7B F10):
 * the C-C / C-U fixtures are recorded from the int3cl sandbox oracle ONLY.
 *   - the host must be exactly 127.0.0.1 (never localhost, never a remote);
 *   - the live stack's ports (deck 5273, oracle 8091, brain 8092, emulator
 *     8090, PostGIS 56434, Valkey 6380, NATS 4223, models 8083-8085) and int3c
 *     (oracle 8161, PostGIS 56561 — it holds the real PoC captures) are
 *     ALWAYS refused, whatever the override;
 *   - any port but 8162 is refused unless `allowPort` names that exact port
 *     (RECORD_OSINT_ALLOW_PORT, for another synthetic sandbox).
 * Returns null when the base is acceptable, else the reason.
 */
export const RECORD_REFUSED_PORTS = new Map([
	['5273', 'the live deck'],
	['8091', 'the live oracle'],
	['8092', 'the live brain'],
	['8090', 'the live emulator'],
	['56434', 'the live PostGIS'],
	['6380', 'the live Valkey'],
	['4223', 'the live NATS'],
	['8083', 'a live model host'],
	['8084', 'a live model host'],
	['8085', 'a live model host'],
	['8161', 'int3c (real PoC captures — never recorded)'],
	['56561', 'int3c PostGIS (real PoC captures — never recorded)'],
]);
export function recordBaseRefusal(base, allowPort = null) {
	let u;
	try {
		u = new URL(base);
	} catch {
		return `not a URL: ${base}`;
	}
	if (u.protocol !== 'http:') return `scheme ${u.protocol} refused (the sandbox oracle is plain http on 127.0.0.1)`;
	if (u.hostname !== '127.0.0.1') return `host ${u.hostname} refused — only 127.0.0.1 (the int3cl sandbox)`;
	const port = u.port || '80';
	if (RECORD_REFUSED_PORTS.has(port)) return `port ${port} refused — ${RECORD_REFUSED_PORTS.get(port)}`;
	if (port !== '8162' && String(allowPort ?? '') !== port) return `port ${port} refused — the int3cl oracle is :8162 (RECORD_OSINT_ALLOW_PORT=${port} to record from another synthetic sandbox)`;
	return null;
}
