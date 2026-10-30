/**
 * The omnibar's officer-only full-mark lookup (FIX-C-PLATESEARCH; the S3
 * result block is FIX-E-LOOKUP): the client for
 * GET /api/v1/vehicles/lookup?plate=<mark> and the pure presenter that
 * turns its outcome into the omnibar's result block.
 *
 * The deck proxies /api/v1 to the oracle and hooks.server.ts attaches the
 * verified x-sajag-officer header server-side, so the client sets NO officer
 * header of its own (a client-set name would be a claim, not an identity):
 * without a signed-in duty officer the oracle answers 409 officer-required
 * and the block says so honestly — never a mark.
 *
 * Every completed lookup is written to the oracle's audit trail; the 200
 * body carries the row back (officer, time, masked mark, result class) and
 * the presenter renders the quiet "Lookup recorded · <officer> · <time>"
 * line from it. The reads it shows are only what C6 let leave the store
 * (active_earmark → the trail, evidence_only → the evidence reads, neither
 * → none, with the no-lawful-basis note through its TRANSLATED key — the
 * oracle's sentence, in the block's language; FIX-E-LOOKUP: never the raw
 * EN server copy). The reads it names carry an explicit date (a trail read
 * can be days old — a bare hh:mm would read as today's) and the first
 * three stand for the rest through "+N more reads"; the whole trail stays
 * in `readUrns` for the block's "Show trail" action, the vehicle in
 * `vehicleUrn` for "Open vehicle".
 *
 * lookupVehicle never throws: a timeout, a network drop or an oracle
 * without the route (the sandbox runs main's code) maps to an outcome the
 * presenter renders as an honest error state, never a crash. A 422 (not a
 * registration mark) renders through the translated invalid-mark key — the
 * server's detail used to echo the input and name a full mark, so the deck
 * never shows it.
 */
import { t } from '$lib/i18n/strings';
import { colStamp, fmtDay, fmtTime } from '$lib/ui/format/format';
import { HUMAN, human } from './vocabulary';

/** One lawful camera read (the /sightings row shape, defensively read). */
export interface LookupRead {
	sighting_id: string | null;
	camera_id: string | null;
	t: string | null;
}

/** The parsed 200 body of GET /api/v1/vehicles/lookup, defensively read. */
export interface LookupResult {
	found: boolean;
	/** The CANONICAL mark, full — this is an officer-only route. */
	mark: string | null;
	mark_masked: string | null;
	vehicle_id: string | null;
	vehicle_class: string | null;
	earmark: { state: string | null; reason: string | null; lawful_basis: string | null; retention_until: string | null } | null;
	open_recommendations: { recommendation_id: string | null; rule_id: string | null; status: string | null }[];
	open_pursuits: { event_id: string | null; status: string | null; recommendation_id: string | null }[];
	disclosure: string;
	reads: LookupRead[];
	/** The oracle's own sentence (the no-lawful-basis note), shown as sent. */
	note: string | null;
	audit: { officer: string | null; looked_up_at: string | null } | null;
}

/** What lookupVehicle resolves with — always; it never throws. */
export interface LookupOutcome {
	ok: boolean;
	httpStatus: number;
	result?: LookupResult;
	/** True when the oracle answered 409: no signed-in duty officer, nothing looked up. */
	officerRequired?: boolean;
	/** The server's sentence (the 409 reason, an error detail) when there is one. */
	detail?: string | null;
}

const str = (v: unknown): string | null => (typeof v === 'string' && v.length ? v : null);
const rec = (v: unknown): Record<string, unknown> | null =>
	v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);

/** The oracle's no-lawful-basis sentence (traffic_oracle/vehicles/__init__.py,
 *  NO_BASIS_NOTE) — the ONLY server note that maps to the translated key. Any
 *  other server note is shown as sent (audit E round 2, nice-to-have: round 1
 *  mapped ANY note to the no-basis sentence, so a different server sentence
 *  was shown translated as if it were this one). */
const ORACLE_NO_BASIS_NOTE =
	"No lawful basis to show this vehicle's camera reads — earmark it with a lawful basis to proceed";

function parseLookupResult(body: Record<string, unknown>): LookupResult {
	const earmark = rec(body.earmark);
	const audit = rec(body.audit);
	return {
		found: body.found === true,
		mark: str(body.mark),
		mark_masked: str(body.mark_masked),
		vehicle_id: str(body.vehicle_id),
		vehicle_class: str(body.vehicle_class),
		earmark: earmark
			? { state: str(earmark.state), reason: str(earmark.reason), lawful_basis: str(earmark.lawful_basis), retention_until: str(earmark.retention_until) }
			: null,
		open_recommendations: list(body.open_recommendations).map((r) => {
			const o = rec(r);
			return { recommendation_id: str(o?.recommendation_id), rule_id: str(o?.rule_id), status: str(o?.status) };
		}),
		open_pursuits: list(body.open_pursuits).map((r) => {
			const o = rec(r);
			return { event_id: str(o?.event_id), status: str(o?.status), recommendation_id: str(o?.recommendation_id) };
		}),
		disclosure: str(body.disclosure) ?? 'none',
		reads: list(body.reads).map((r) => {
			const o = rec(r);
			return { sighting_id: str(o?.sighting_id), camera_id: str(o?.camera_id), t: str(o?.t) };
		}),
		note: str(body.note),
		audit: audit ? { officer: str(audit.officer), looked_up_at: str(audit.looked_up_at) } : null,
	};
}

/**
 * GET /api/v1/vehicles/lookup?plate=<mark> — same-origin through the deck
 * proxy (ops/client.ts's decideEscortProposal house style: a relative fetch,
 * no client-set officer header, a bounded 8 s timeout, the body parsed
 * defensively, never a throw). `mark` should arrive normalised (search.ts's
 * normMark); it is encoded here regardless.
 */
export async function lookupVehicle(mark: string, signal?: AbortSignal): Promise<LookupOutcome> {
	try {
		const res = await fetch(`/api/v1/vehicles/lookup?plate=${encodeURIComponent(mark)}`, {
			signal: signal ?? AbortSignal.timeout(8000),
		});
		const text = await res.text().catch(() => '');
		let body: Record<string, unknown> = {};
		try {
			body = JSON.parse(text) as Record<string, unknown>;
		} catch {
			// non-JSON (a proxy's error page): the text is the detail
		}
		if (res.ok) return { ok: true, httpStatus: res.status, result: parseLookupResult(body) };
		const problem = rec(body.detail);
		const detail = str(body.detail) ?? (problem ? str(problem.reason) : null) ?? (text.slice(0, 200) || `HTTP ${res.status}`);
		return {
			ok: false,
			httpStatus: res.status,
			officerRequired: problem?.error === 'officer-required',
			detail,
		};
	} catch (err) {
		return { ok: false, httpStatus: 0, detail: err instanceof Error ? err.message : String(err) };
	}
}

/** The omnibar result block's lines (pure — the unit tests render through it). */
export interface LookupView {
	state: 'found' | 'none' | 'officer-required' | 'error';
	/** The unmasked canonical mark; null whenever a mark must not be shown (409, errors). */
	mark: string | null;
	/** Found: the watchlist line with the basis IN WORDS. Otherwise: the honest sentence. */
	heading: string;
	/** How many lawful reads C6 let leave the store; null when none leave. */
	reads: number | null;
	/** The first reads as "camera · 23 Oct 13:22" — always dated (FIX-E-LOOKUP). */
	readRows: string[];
	/** Reads beyond the first three: the block's "+N more reads" line. */
	moreReads: number | null;
	/** Every lawful read's sighting URN — the trail the "Show trail" action highlights. */
	readUrns: string[];
	/** The found vehicle's URN — the "Open vehicle" action's target. */
	vehicleUrn: string | null;
	/** The no-lawful-basis note through its translated key (the oracle's fixed sentence). */
	note: string | null;
	/** Found: how many recommendations and pursuits are open on the vehicle. */
	recommendations: number | null;
	pursuits: number | null;
	/** "Lookup recorded · <officer> · <time>", assembled from the response's audit object. */
	recorded: string | null;
	/** The failure sentence: the translated invalid-mark copy, or the server's detail. */
	detail: string | null;
}

const VIEW_EMPTY: Omit<LookupView, 'heading'> = {
	state: 'error',
	mark: null,
	reads: null,
	readRows: [],
	moreReads: null,
	readUrns: [],
	vehicleUrn: null,
	note: null,
	recommendations: null,
	pursuits: null,
	recorded: null,
	detail: null,
};

/** A lawful basis in words, in `lang`: the pack key (ws_basis_<code>), the
 *  vocabulary, else the code's words — never the raw enum (FIX-E-LOOKUP). */
export function basisWords(code: string | null, lang: string): string {
	if (!code) return '';
	const key = `ws_basis_${code}`;
	const named = t(lang, key);
	return named !== key ? named : HUMAN[code] ?? human(code);
}

/** A read's moment, ALWAYS dated ("23 Oct 13:22"): a trail read can be days
 *  old, and a bare hh:mm would read as today's. */
function datedRead(iso: string | null): string {
	const ms = iso == null ? NaN : Date.parse(iso);
	return Number.isFinite(ms) ? `${fmtDay(ms)} ${fmtTime(ms)}` : '—';
}

/** Assemble the result block's lines from an outcome (offer-independent, pure). */
export function lookupView(o: LookupOutcome, lang = 'en', now: number = Date.now()): LookupView {
	if (!o.ok || !o.result) {
		// the 409 says the oracle looked up nothing: the copy says so, and never a mark
		if (o.officerRequired) return { ...VIEW_EMPTY, state: 'officer-required', heading: t(lang, 'ws_lookup_officer_required') };
		// the 422 says the plate is not a mark: the translated copy, never the
		// server detail (it used to echo the input and name a full mark)
		if (o.httpStatus === 422) return { ...VIEW_EMPTY, heading: t(lang, 'ws_lookup_error'), detail: t(lang, 'ws_lookup_invalid_plate') };
		return { ...VIEW_EMPTY, heading: t(lang, 'ws_lookup_error'), detail: o.detail ?? null };
	}
	const r = o.result;
	const lawful = r.disclosure === 'active_earmark' || r.disclosure === 'evidence_only';
	const audit = r.audit;
	const urns = lawful ? r.reads.map((x) => (x.sighting_id ? `sighting:${x.sighting_id}` : '')).filter(Boolean) : [];
	return {
		state: r.found ? 'found' : 'none',
		mark: r.mark,
		heading: r.found
			? r.earmark
				? `${t(lang, 'ws_lookup_watchlist')}${r.earmark.lawful_basis ? ` · ${basisWords(r.earmark.lawful_basis, lang)}` : ''}`
				: t(lang, 'ws_lookup_unwatched')
			: t(lang, 'ws_lookup_none'),
		reads: r.found && lawful ? r.reads.length : null,
		readRows: r.found && lawful ? r.reads.slice(0, 3).map((x) => `${x.camera_id ?? '—'} · ${datedRead(x.t)}`) : [],
		moreReads: r.found && lawful && r.reads.length > 3 ? r.reads.length - 3 : null,
		readUrns: urns,
		vehicleUrn: r.found && r.vehicle_id ? `vehicle:${r.vehicle_id}` : null,
		note: r.note ? (r.note === ORACLE_NO_BASIS_NOTE ? t(lang, 'ws_lookup_nobasis') : r.note) : null,
		recommendations: r.found && r.open_recommendations.length ? r.open_recommendations.length : null,
		pursuits: r.found && r.open_pursuits.length ? r.open_pursuits.length : null,
		recorded: audit?.officer ? t(lang, 'ws_lookup_recorded', audit.officer, colStamp([audit.looked_up_at], now)[0]) : null,
		detail: null,
	};
}
