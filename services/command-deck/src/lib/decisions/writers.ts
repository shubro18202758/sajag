/**
 * Writers (SPEC §5.4 "Writers", review B2; plan X9/X10) — what a decision
 * REALLY changes. The ProposalCard's "What changes" rows are generated from
 * this table and never claim more than the writer does; tests/
 * decisions.unit.mjs asserts each entry's rows against the client call its
 * `run()` makes (a fetch stub records every POST).
 *
 * Keyed `${kind}.${action}`. Each entry gives:
 *   changes(u)    rows Object | Now | After you decide (after null = "No change")
 *   unchanged(u)  what the writer leaves alone, said once under the table
 *   nextStep(u)   the next, separate decision, where the writer has one
 *   refusals      code → the inline sentence (a refusal never POSTs)
 *   run(u, actor, args)  the EXISTING writer in ops/client.ts, through the ops
 *                 store (its officer gate, busy guard, refusal record and
 *                 re-poll): decideEnforcementRecommendation,
 *                 openPursuitEvent, decideEscortProposal, decideDispatch,
 *                 requestDispatch. Every run is guarded so that a double
 *                 click sends ONE POST: a second call while the first is in
 *                 flight returns the same promise, and a call within
 *                 SETTLE_MS of a success is refused 'already-decided'.
 *
 * `ChangeRow.writes` (an addition to the frozen shape) lists the ids a
 * changed row's POSTs touch, so the unit test can hold the table to the
 * calls the writer makes.
 *
 * The AI or a rule proposes; a NAMED officer decides (ethics rule 6): every
 * run refuses 'officer-required' before any request when no officer is
 * named, and the store's own gate refuses again.
 */
import { ops } from '$lib/ops/store.svelte';
import { fmtStamp } from '$lib/ui/format/format';
import { t, kindLabel } from '$lib/i18n/strings';
import { tOps } from '$lib/i18n/strings.ops';
import '$lib/i18n/packs.decisions';
import { decideDecisionSupport, type DecisionSupport } from '$lib/ops/client';
import { dssState, recordDssRefusal, selectionOf } from '$lib/dss/dss-store.svelte';
import { actuatingOf, coaById, defaultCoaId, dispatchesOf, nextStepLine } from '$lib/dss/dss-data';
import {
	STOLEN_RULE,
	corridorOf,
	dssOf,
	echallanOf,
	escortOf,
	pursuitOf,
	stolenOf,
	type Unit,
} from './units';

/** One row of "What changes" (plan X9, frozen; `writes` added). */
export interface ChangeRow {
	object: string;
	now: string;
	/** null = "No change" (ink-2). */
	after: string | null;
	/** The ids this row's change POSTs to (recommendation, dispatch, approval or event ids). */
	writes?: readonly string[];
}

/** What a writer run came back with. */
export interface WriterResult {
	ok: boolean;
	/** A refusal code (a key of the entry's `refusals`) — nothing was sent, or the server refused. */
	refusal?: string;
	/** The server's own sentence, verbatim (a 409). */
	detail?: string;
	/** How many POSTs this run sent. */
	posts?: number;
}

/** One writer (plan X9, frozen). */
export interface WriterEntry {
	changes(u: Unit, opts?: unknown): ChangeRow[];
	unchanged(u: Unit): string[];
	/** `opts` carries what the card knows: the dss writer reads the chosen COA from it. */
	nextStep?(u: Unit, opts?: unknown): string;
	refusals: Record<string, string>;
	run(u: Unit, actor: string, args: Record<string, unknown>): Promise<unknown>;
}

/** The primary and secondary actions of each unit kind (the card's buttons), in `${kind}.${action}` keys. */
export const ACTIONS: Record<string, { primary: string | null; secondary: string | null }> = {
	'stolen-sighting': { primary: 'authorise', secondary: 'dismiss' },
	pursuit: { primary: 'open', secondary: null },
	echallan: { primary: 'approve', secondary: 'reject' },
	'escort-proposal': { primary: 'approve', secondary: 'reject' },
	'corridor-request': { primary: 'approve', secondary: 'defer' },
	// plan X22: Approve is the primary; Defer sits beside the card's COA list (the shell's
	// footer carries one secondary), Reject is the default secondary
	dss: { primary: 'approve', secondary: 'reject' },
};

/** A late second click of a double click arriving after the first POST settled is refused for this long. */
export const SETTLE_MS = 4000;

const L = (key: string, ...args: unknown[]) => t(ops.lang, key, ...args);

/** Shared refusal sentences (EN keys in packs.decisions.ts). */
const REFUSE = {
	officer: () => L('dec_refuse_officer'),
	reason: () => L('dec_refuse_reason'),
	decided: () => L('dec_refuse_decided'),
	stolen: () => L('dec_refuse_stolen'),
	refused: () => L('dec_refuse_refused'),
};

/**
 * A refusal table whose sentences are read in the console's language at the
 * moment they are printed (each value is a getter over an i18n key).
 */
function refs(keys: Record<string, string>): Record<string, string> {
	const out: Record<string, string> = {};
	for (const [code, key] of Object.entries(keys)) Object.defineProperty(out, code, { enumerable: true, get: () => L(key) });
	return out;
}

// ── the double-click guard ──────────────────────────────────────────────

const inflight = new Map<string, Promise<WriterResult>>();
const settled = new Map<string, number>();

/** Run `fn` once per `key` at a time; a repeat within SETTLE_MS of a success is refused. */
function guarded(key: string, fn: () => Promise<WriterResult>): Promise<WriterResult> {
	const running = inflight.get(key);
	if (running) return running;
	const at = settled.get(key);
	if (at != null && Date.now() - at < SETTLE_MS) return Promise.resolve({ ok: false, refusal: 'already-decided', posts: 0 });
	const p = (async () => {
		try {
			const res = await fn();
			if (res.ok) settled.set(key, Date.now());
			return res;
		} finally {
			inflight.delete(key);
		}
	})();
	inflight.set(key, p);
	return p;
}

/** True while a writer for this unit is in flight (the card's busy state). */
export function writerBusy(u: Unit): boolean {
	for (const k of inflight.keys()) if (k.endsWith(`:${u.kind}:${u.id}`)) return true;
	return false;
}

/** Forget every guard (tests only). */
export function resetWriterGuards(): void {
	inflight.clear();
	settled.clear();
}

/** The officer gate before any request (the store's own gate refuses again). */
function officerOk(actor: string): boolean {
	const who = (actor ?? '').trim();
	return who.length >= 2 && ops.officerOn && ops.dutyOfficer.trim() === who;
}

const note = (args: Record<string, unknown>) => (typeof args.note === 'string' ? args.note.trim().slice(0, 500) : '');

// ── row texts ───────────────────────────────────────────────────────────

const camOf = (r: { evidence: Record<string, unknown> | null }) => {
	const c = r.evidence?.['camera_id'];
	return typeof c === 'string' ? c : null;
};

/** "Newest sighting · EM-CAM-05 10:12" (the camera and the time through the formatter's stamp). */
function sightingLabel(r: { evidence: Record<string, unknown> | null; createdAt: string | null }): string {
	const cam = camOf(r);
	const when = r.createdAt ? fmtStamp(r.createdAt) : '';
	return L('dec_row_newest_sighting', [cam, when].filter(Boolean).join(' '));
}

const recIds = (u: Unit) => stolenOf(u).recs.map((r) => r.recommendationId);

// ── the decision-support writer's seams (plan X22) ──────────────────────

/** The agency of a dispatch action, as the row names it (the oracle's params.agency). */
function dssAgencyLabel(agency: string): string {
	const key = `dss_agency_${agency}`;
	const v = L(key);
	return v === key ? agency || '—' : v;
}

/** The chosen COA for a dss unit: args.coaId, then the officer's radio, then the engine's pick. */
function dssCoaFor(u: Unit, opts: unknown): { dss: DecisionSupport | null; coaId: string | null } {
	const o = (opts ?? {}) as { dss?: DecisionSupport; coaId?: string };
	const dss = o.dss ?? dssState.objects[u.id] ?? null;
	const coaId = o.coaId ?? selectionOf(u.id) ?? (dss ? defaultCoaId(dss) : null) ?? dssOf(u).summary.topCoaId ?? null;
	return { dss, coaId };
}

/** The chosen COA's verbs that carry no write of their own (the promotion or a dispatch row covers the rest). */
function otherVerbsOf(coa: Parameters<typeof actuatingOf>[0]): string[] {
	const out: string[] = [];
	for (const a of coa?.actions ?? []) {
		if (a.verb === 'dispatch' || a.verb === 'monitor') continue;
		if (!out.includes(a.verb)) out.push(a.verb);
	}
	return out;
}

/** Map the client's outcome to a WriterResult, keeping the oracle's 409 code and its own sentence. */
function dssResult(res: Awaited<ReturnType<typeof decideDecisionSupport>>, dssId: string) {
	if (res.ok) return { ok: true, posts: 1 };
	recordDssRefusal(dssId, res.refusal ?? 'refused', res.detail);
	return { ok: false, refusal: res.refusal ?? 'refused', detail: res.detail ?? undefined, posts: 1 };
}

// ── the table ───────────────────────────────────────────────────────────

export const WRITERS: Record<string, WriterEntry> = {
	/** Stolen · Authorise pursuit — approves the NEWEST sighting only (C6 pursuit gate's human approval). */
	'stolen-sighting.authorise': {
		changes(u) {
			const d = stolenOf(u);
			const earlier = d.recs.length - 1;
			const rows: ChangeRow[] = [
				{ object: sightingLabel(d.newest), now: L('dec_state_pending'), after: L('dec_after_approved'), writes: [d.newest.recommendationId] },
			];
			if (earlier > 0) rows.push({ object: L('dec_row_earlier_sightings', earlier), now: L('dec_state_pending'), after: null });
			rows.push({ object: L('dec_row_pursuit'), now: L('dec_state_not_open'), after: null });
			return rows;
		},
		unchanged: () => [L('dec_unchanged_earlier'), L('dec_unchanged_pursuit'), L('dec_unchanged_fine')],
		nextStep(u) {
			const road = stolenOf(u).step.candidate?.anchor?.roadName ?? null;
			return road ? L('dec_next_open_pursuit_on', road) : L('dec_next_open_pursuit');
		},
		refusals: refs({
			'officer-required': 'dec_refuse_officer',
			'already-decided': 'dec_refuse_decided',
			'already-authorised': 'dec_refuse_authorised',
			refused: 'dec_refuse_refused',
		}),
		run(u, actor) {
			return guarded(`stolen-sighting.authorise:${u.kind}:${u.id}`, async () => {
				const d = stolenOf(u);
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				if (d.approved) return { ok: false, refusal: 'already-authorised', posts: 0 };
				if (d.refusal) return { ok: false, refusal: 'refused', detail: d.refusal.detail, posts: 0 };
				const ok = await ops.decideRecommendation(d.newest.recommendationId, 'approve', tOps(ops.lang, 'queueStolenAuthoriseNote'));
				const refusal = ops.recommendationRefusals[d.newest.recommendationId];
				return ok ? { ok: true, posts: 1 } : { ok: false, refusal: refusal ? 'refused' : 'failed', detail: refusal?.detail, posts: 1 };
			});
		},
	},

	/** Stolen · Dismiss all — rejects EACH pending sighting under ONE reason, stopping at the first failure. */
	'stolen-sighting.dismiss': {
		changes(u) {
			const d = stolenOf(u);
			return [
				{ object: L('dec_row_pending_sightings', d.recs.length), now: L('dec_state_pending'), after: L('dec_after_rejected'), writes: recIds(u) },
				{ object: L('dec_row_watchlist'), now: L('dec_state_active'), after: null },
			];
		},
		unchanged: () => [L('dec_unchanged_watchlist'), L('dec_unchanged_retention')],
		refusals: refs({
			'officer-required': 'dec_refuse_officer',
			'reason-required': 'dec_refuse_reason',
			'already-decided': 'dec_refuse_decided',
		}),
		run(u, actor, args) {
			return guarded(`stolen-sighting.dismiss:${u.kind}:${u.id}`, async () => {
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				const reason = note(args);
				if (!reason) return { ok: false, refusal: 'reason-required', posts: 0 };
				let posts = 0;
				for (const r of stolenOf(u).recs) {
					posts++;
					if (!(await ops.decideRecommendation(r.recommendationId, 'reject', reason))) {
						const refusal = ops.recommendationRefusals[r.recommendationId];
						return { ok: false, refusal: refusal ? 'refused' : 'failed', detail: refusal?.detail, posts };
					}
				}
				return { ok: true, posts };
			});
		},
	},

	/**
	 * Pursuit · Open pursuit — a SEPARATE decision (step 2 of a stolen-vehicle
	 * unit, or a pursuit-opening unit): POST /api/v1/events (vehicle_pursuit)
	 * anchored on the latest sighting's road, citing the approved
	 * recommendation. Refused inline before any request when the anchor or the
	 * approval is missing.
	 */
	'pursuit.open': {
		changes(u) {
			const c = u.kind === 'stolen-sighting' ? stolenOf(u).step.candidate : pursuitOf(u).candidate;
			const road = c?.anchor?.roadName ?? (c?.anchor ? `#${c.anchor.segmentId}` : null);
			const vehicle = u.kind === 'stolen-sighting' ? stolenOf(u).vehicleId : pursuitOf(u).vehicleId;
			return [
				{ object: L('dec_row_pursuit_event'), now: L('dec_state_none'), after: road ? L('dec_after_opens_on', road) : L('dec_after_opens'), writes: [vehicle] },
				{ object: L('dec_row_interception'), now: L('dec_state_none'), after: L('dec_after_plan_starts') },
				{ object: L('dec_row_approved_rec'), now: L('dec_state_approved'), after: null },
			];
		},
		unchanged: () => [L('dec_unchanged_recs')],
		nextStep: () => L('dec_next_after_pursuit'),
		refusals: refs({
			'officer-required': 'dec_refuse_officer',
			'no-anchor': 'dec_refuse_no_anchor',
			'no-approved-recommendation': 'dec_refuse_no_approval',
			'already-open': 'dec_refuse_open',
			'already-decided': 'dec_refuse_decided',
		}),
		run(u, actor) {
			return guarded(`pursuit.open:${u.kind}:${u.id}`, async () => {
				const vehicleId = u.kind === 'stolen-sighting' ? stolenOf(u).vehicleId : pursuitOf(u).vehicleId;
				const c = ops.pursuitCandidates.find((p) => p.vehicle.vehicleId === vehicleId) ?? null;
				if (!c) return { ok: false, refusal: ops.pursuitFor(vehicleId) ? 'already-open' : 'no-anchor', posts: 0 };
				if (c.refusal) return { ok: false, refusal: c.refusal, posts: 0 };
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				const ok = await ops.openPursuitFor(vehicleId);
				return ok ? { ok: true, posts: 1 } : { ok: false, refusal: 'failed', detail: ops.pursuitNote?.text, posts: 1 };
			});
		},
	},

	/** E-challan · Approve — that recommendation only. Never on a vehicle reported stolen (C-N). */
	'echallan.approve': {
		changes(u) {
			const d = echallanOf(u);
			return [
				{ object: L('dec_row_echallan', ops.plate(d.plate) ?? u.id.slice(0, 8)), now: L('dec_state_pending'), after: L('dec_after_approved'), writes: [u.id] },
			];
		},
		unchanged: () => [L('dec_unchanged_other_recs')],
		refusals: refs({
			'officer-required': 'dec_refuse_officer',
			'vehicle-stolen': 'dec_refuse_stolen',
			refused: 'dec_refuse_refused',
			'already-decided': 'dec_refuse_decided',
		}),
		run(u, actor) {
			return guarded(`echallan.approve:${u.kind}:${u.id}`, async () => {
				const d = echallanOf(u);
				if (d.stolen) return { ok: false, refusal: 'vehicle-stolen', posts: 0 };
				if (d.refusal || ops.recommendationRefusals[u.id]) return { ok: false, refusal: 'refused', detail: (d.refusal ?? ops.recommendationRefusals[u.id])?.detail, posts: 0 };
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				const ok = await ops.decideRecommendation(u.id, 'approve');
				const refusal = ops.recommendationRefusals[u.id];
				return ok ? { ok: true, posts: 1 } : { ok: false, refusal: refusal ? 'refused' : 'failed', detail: refusal?.detail, posts: 1 };
			});
		},
	},

	/** E-challan · Reject — that recommendation only, with the officer's reason (the oracle note). */
	'echallan.reject': {
		changes(u) {
			const d = echallanOf(u);
			return [
				{ object: L('dec_row_echallan', ops.plate(d.plate) ?? u.id.slice(0, 8)), now: L('dec_state_pending'), after: L('dec_after_rejected'), writes: [u.id] },
			];
		},
		unchanged: () => [L('dec_unchanged_other_recs')],
		refusals: refs({
			'officer-required': 'dec_refuse_officer',
			'reason-required': 'dec_refuse_reason',
			'already-decided': 'dec_refuse_decided',
		}),
		run(u, actor, args) {
			return guarded(`echallan.reject:${u.kind}:${u.id}`, async () => {
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				const reason = note(args);
				if (!reason) return { ok: false, refusal: 'reason-required', posts: 0 };
				const ok = await ops.decideRecommendation(u.id, 'reject', reason);
				return ok ? { ok: true, posts: 1 } : { ok: false, refusal: 'failed', posts: 1 };
			});
		},
	},

	/**
	 * Escort · Approve — the brain applies the proposed hold or re-route IF it
	 * can still apply it (an approval can come back "not applied": the convoy
	 * passed the branch point). Time-boxed: unanswered, the current plan holds.
	 */
	'escort-proposal.approve': {
		changes(u) {
			const p = escortOf(u).proposal;
			const c = p.proposed;
			const holdRoads = (c?.holdSegmentIds.length ? c.holdSegmentIds : p.segmentIds).map((id) => ops.roadName(id) ?? `#${id}`);
			if (p.kind === 'hold') {
				const sec = Math.round(c?.maxHoldSec ?? 0);
				return [
					{ object: L('dec_row_convoy'), now: L('dec_state_moving'), after: L('dec_after_holds', holdRoads[0] ?? '—', sec || '—'), writes: [p.approvalId] },
					{ object: L('dec_row_route'), now: L('dec_state_current'), after: null },
					{ object: L('dec_row_signals_closures'), now: L('dec_state_current'), after: null },
				];
			}
			if (p.kind === 'plan_b' || p.kind === 'reroute') {
				const via = c?.viaRoadNames.length ? c.viaRoadNames.join(', ') : (c?.viaSegmentIds ?? []).map((id) => ops.roadName(id) ?? `#${id}`).join(', ');
				const closures = c && (c.closuresNew.length || c.closuresLifted.length) ? L('dec_after_closures', c.closuresNew.length, c.closuresLifted.length) : null;
				return [
					{ object: L('dec_row_route'), now: L('dec_state_current'), after: L('dec_after_route', tOps(ops.lang, `escKind_${p.kind}`), via || '—'), writes: [p.approvalId] },
					{ object: L('dec_row_closures'), now: L('dec_state_current'), after: closures },
					{ object: L('dec_row_signals'), now: L('dec_state_current'), after: null },
				];
			}
			return [
				{ object: L('dec_row_proposal'), now: L('dec_state_open'), after: L('dec_after_approved'), writes: [p.approvalId] },
				{ object: L('dec_row_convoy'), now: L('dec_state_current'), after: null },
			];
		},
		unchanged: () => [L('dec_unchanged_other_proposals')],
		nextStep: () => L('dec_next_escort'),
		refusals: refs({
			'officer-required': 'dec_refuse_officer',
			expired: 'dec_refuse_expired',
			'not-applied': 'dec_refuse_not_applied',
			'already-decided': 'dec_refuse_decided',
		}),
		run(u, actor) {
			return guarded(`escort-proposal.approve:${u.kind}:${u.id}`, async () => {
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				if (ops.escortAnswered(escortOf(u).proposal.approvalId)) return { ok: false, refusal: 'already-decided', posts: 0 };
				const res = await ops.decideEscortProposal(escortOf(u).proposal, 'approve');
				if (!res) return { ok: false, refusal: 'failed', posts: 0 };
				return res.ok ? { ok: true, posts: 1 } : { ok: false, refusal: res.status === 'expired' ? 'expired' : 'failed', detail: res.detail ?? undefined, posts: 1 };
			});
		},
	},

	/** Escort · Reject — the proposal closes; the current plan stays. */
	'escort-proposal.reject': {
		changes(u) {
			const p = escortOf(u).proposal;
			return [
				{ object: L('dec_row_proposal'), now: L('dec_state_open'), after: L('dec_after_rejected_plain'), writes: [p.approvalId] },
				{ object: L('dec_row_convoy'), now: L('dec_state_current_plan'), after: null },
			];
		},
		unchanged: () => [L('dec_unchanged_route_signals')],
		refusals: refs({
			'officer-required': 'dec_refuse_officer',
			expired: 'dec_refuse_expired',
			'already-decided': 'dec_refuse_decided',
		}),
		run(u, actor) {
			return guarded(`escort-proposal.reject:${u.kind}:${u.id}`, async () => {
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				if (ops.escortAnswered(escortOf(u).proposal.approvalId)) return { ok: false, refusal: 'already-decided', posts: 0 };
				const res = await ops.decideEscortProposal(escortOf(u).proposal, 'reject');
				if (!res) return { ok: false, refusal: 'failed', posts: 0 };
				return res.ok ? { ok: true, posts: 1 } : { ok: false, refusal: res.status === 'expired' ? 'expired' : 'failed', detail: res.detail ?? undefined, posts: 1 };
			});
		},
	},

	/** Corridor request (108) · Approve — that dispatch's status only. */
	'corridor-request.approve': {
		changes(u) {
			const d = corridorOf(u).dispatch;
			return [
				{ object: L('dec_row_dispatch', d.unitId ?? d.dispatchId.slice(0, 8)), now: L('dec_state_requested'), after: L('dec_after_approved'), writes: [u.id] },
			];
		},
		unchanged: () => [L('dec_unchanged_other_dispatches')],
		nextStep: () => L('dec_next_dispatch'),
		refusals: refs({ 'officer-required': 'dec_refuse_officer', 'already-decided': 'dec_refuse_decided' }),
		run(u, actor, args) {
			return guarded(`corridor-request.approve:${u.kind}:${u.id}`, async () => {
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				const ok = await ops.decideDispatchAction(u.id, 'approve', note(args));
				return ok ? { ok: true, posts: 1 } : { ok: false, refusal: 'failed', posts: 1 };
			});
		},
	},

	/** Corridor request (108) · Defer — that dispatch's status only, with the reason. */
	'corridor-request.defer': {
		changes(u) {
			const d = corridorOf(u).dispatch;
			return [
				{ object: L('dec_row_dispatch', d.unitId ?? d.dispatchId.slice(0, 8)), now: L('dec_state_requested'), after: L('dec_after_deferred'), writes: [u.id] },
			];
		},
		unchanged: () => [L('dec_unchanged_other_dispatches')],
		refusals: refs({
			'officer-required': 'dec_refuse_officer',
			'reason-required': 'dec_refuse_reason',
			'already-decided': 'dec_refuse_decided',
		}),
		run(u, actor, args) {
			return guarded(`corridor-request.defer:${u.kind}:${u.id}`, async () => {
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				const reason = note(args);
				if (!reason) return { ok: false, refusal: 'reason-required', posts: 0 };
				const ok = await ops.decideDispatchAction(u.id, 'defer', reason);
				return ok ? { ok: true, posts: 1 } : { ok: false, refusal: 'failed', posts: 1 };
			});
		},
	},

	/**
	 * Decision support (plan X22, C-U) — approving ONE course of action. The
	 * oracle does the writing server-side: it promotes an unpromoted OSINT
	 * report (C-T) when the chosen COA actuates, and files one dispatch
	 * REQUEST per dispatch action (each decided separately in Dispatch);
	 * this client sends the ONE decision POST. Defer sits beside the card's
	 * COA list (the shell's footer carries one secondary slot), with the same
	 * writer gate and the same note rule as Reject.
	 */
	'dss.approve': {
		changes(u, opts) {
			const d = dssOf(u);
			const { dss, coaId } = dssCoaFor(u, opts);
			const coa = coaById(dss, coaId);
			const rows: ChangeRow[] = [
				{
					object: L('dss_row_decision'),
					now: L('dss_state_proposed'),
					after: L('dss_after_approved', coa?.label ?? d.summary.topCoaLabel ?? '—'),
					writes: [u.id],
				},
			];
			if (d.subjectKind === 'osint_event' && !d.promotedEventId && actuatingOf(coa)) {
				rows.push({
					object: L('dss_row_report'),
					now: L('dss_now_report'),
					after: L('dss_after_promoted', kindLabel(ops.lang, d.sajagEventKind)),
					writes: [d.urn.slice('osint_event:'.length)],
				});
			}
			for (const a of dispatchesOf(coa)) {
				const agency = dssAgencyLabel(typeof a.params.agency === 'string' ? a.params.agency : '');
				const count = typeof a.params.count === 'number' && Number.isFinite(a.params.count) ? a.params.count : 1;
				rows.push({ object: L('dss_row_dispatch', agency, count), now: L('dss_now_none'), after: L('dss_after_requested'), writes: [] });
			}
			for (const verb of otherVerbsOf(coa)) {
				rows.push({ object: L(`dss_verb_${verb}`), now: L('dss_now_none'), after: null });
			}
			return rows;
		},
		unchanged: () => [L('dss_unchanged_coas'), L('dss_unchanged_units')],
		nextStep(u, opts) {
			const { dss, coaId } = dssCoaFor(u, opts);
			return nextStepLine(ops.lang, coaById(dss, coaId));
		},
		refusals: refs({
			'officer-required': 'dss_refuse_officer',
			'reason-required': 'dss_refuse_reason',
			'not-proposed': 'dss_refuse_not_proposed',
			'coa-vetoed': 'dss_refuse_coa_vetoed',
			'coa-infeasible': 'dss_refuse_coa_infeasible',
			'unknown-coa': 'dss_refuse_unknown_coa',
			'no-anchor': 'dss_refuse_no_anchor',
			refused: 'dss_refuse_refused',
			failed: 'dss_refuse_failed',
		}),
		run(u, actor, args) {
			return guarded(`dss.approve:${u.kind}:${u.id}`, async () => {
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				const { dss, coaId } = dssCoaFor(u, args);
				if (!coaId) return { ok: false, refusal: 'unknown-coa', posts: 0 };
				const coa = coaById(dss, coaId);
				if (coa?.vetoed) return { ok: false, refusal: 'coa-vetoed', posts: 0 };
				if (coa && !coa.feasible) return { ok: false, refusal: 'coa-infeasible', posts: 0 };
				const res = await decideDecisionSupport(u.id, { decision: 'approve', coaId, ...(note(args) ? { note: note(args) } : {}) }, actor);
				return dssResult(res, u.id);
			});
		},
	},

	/** Decision support · Reject — the DSS's state only, with the officer's reason (the oracle note). */
	'dss.reject': {
		changes(u, opts) {
			const reason = typeof (opts as { note?: unknown })?.note === 'string' ? (opts as { note: string }).note : '';
			return [
				{
					object: L('dss_row_decision'),
					now: L('dss_state_proposed'),
					after: reason ? L('dss_after_rejected_note', reason) : L('dss_after_rejected'),
					writes: [u.id],
				},
			];
		},
		unchanged: () => [L('dss_unchanged_subject'), L('dss_unchanged_units')],
		refusals: refs({
			'officer-required': 'dss_refuse_officer',
			'reason-required': 'dss_refuse_reason',
			'not-proposed': 'dss_refuse_not_proposed',
			refused: 'dss_refuse_refused',
			failed: 'dss_refuse_failed',
		}),
		run(u, actor, args) {
			return guarded(`dss.reject:${u.kind}:${u.id}`, async () => {
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				const reason = note(args);
				if (!reason) return { ok: false, refusal: 'reason-required', posts: 0 };
				const res = await decideDecisionSupport(u.id, { decision: 'reject', note: reason }, actor);
				return dssResult(res, u.id);
			});
		},
	},

	/** Decision support · Defer — the DSS's state only, with the officer's reason (the oracle note). */
	'dss.defer': {
		changes(u, opts) {
			const reason = typeof (opts as { note?: unknown })?.note === 'string' ? (opts as { note: string }).note : '';
			return [
				{
					object: L('dss_row_decision'),
					now: L('dss_state_proposed'),
					after: reason ? L('dss_after_deferred_note', reason) : L('dss_after_deferred'),
					writes: [u.id],
				},
			];
		},
		unchanged: () => [L('dss_unchanged_subject'), L('dss_unchanged_units')],
		refusals: refs({
			'officer-required': 'dss_refuse_officer',
			'reason-required': 'dss_refuse_reason',
			'not-proposed': 'dss_refuse_not_proposed',
			refused: 'dss_refuse_refused',
			failed: 'dss_refuse_failed',
		}),
		run(u, actor, args) {
			return guarded(`dss.defer:${u.kind}:${u.id}`, async () => {
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				const reason = note(args);
				if (!reason) return { ok: false, refusal: 'reason-required', posts: 0 };
				const res = await decideDecisionSupport(u.id, { decision: 'defer', note: reason }, actor);
				return dssResult(res, u.id);
			});
		},
	},

	/**
	 * Pursuit choke · Request unit — a dispatch REQUEST on the open pursuit
	 * event with the choke junction as the waypoint (a duty officer still
	 * approves it in Dispatch). `u` is the pursuit's unit (kind 'pursuit',
	 * id = the vehicle) or any unit; args {eventId, junctionId, agency, unitId}.
	 */
	'pursuit.request-unit': {
		changes(u, opts) {
			const o = (opts ?? {}) as { eventId?: string; junctionId?: number; junctionName?: string | null; agency?: string };
			return [
				{
					object: L('dec_row_dispatch_request'),
					now: L('dec_state_none'),
					after: L('dec_after_requested', o.agency ?? '—', o.junctionName ?? (o.junctionId != null ? `J${o.junctionId}` : '—')),
					writes: o.eventId ? [o.eventId] : [],
				},
			];
		},
		unchanged: () => [L('dec_unchanged_pursuit_plan')],
		nextStep: () => L('dec_next_request'),
		refusals: refs({
			'officer-required': 'dec_refuse_officer',
			'event-closed': 'dec_refuse_event_closed',
			'already-decided': 'dec_refuse_decided',
		}),
		run(u, actor, args) {
			const eventId = typeof args.eventId === 'string' ? args.eventId : '';
			const junctionId = typeof args.junctionId === 'number' && Number.isInteger(args.junctionId) ? args.junctionId : null;
			return guarded(`pursuit.request-unit:${u.kind}:${u.id}:${eventId}:${junctionId}`, async () => {
				if (!officerOk(actor)) return { ok: false, refusal: 'officer-required', posts: 0 };
				const ev = ops.eventById(eventId);
				if (!ev || ev.state === 'completed' || ev.state === 'cancelled') return { ok: false, refusal: 'event-closed', posts: 0 };
				const ok = await ops.requestDispatchUnit(eventId, {
					agency: typeof args.agency === 'string' ? args.agency : 'police',
					unitId: typeof args.unitId === 'string' ? args.unitId : '',
					waypointJunction: junctionId,
					...(typeof args.note === 'string' && args.note ? { note: args.note } : {}),
				});
				return ok ? { ok: true, posts: 1 } : { ok: false, refusal: 'failed', detail: ops.dispatchRequestNote?.text, posts: 1 };
			});
		},
	},
};

/** The writer of a unit's action (`${kind}.${action}`), or null. */
export function writerFor(kind: string, action: string | null): WriterEntry | null {
	return action ? (WRITERS[`${kind}.${action}`] ?? null) : null;
}

/** The R_STOLEN_SIGHTING rule id (re-exported for the cards). */
export { STOLEN_RULE };

/** Shared refusal sentences by code (cards print a refusal through this). */
export function refusalText(entry: WriterEntry | null, code: string | undefined): string {
	if (!code) return '';
	return entry?.refusals[code] ?? (code === 'officer-required' ? REFUSE.officer() : code === 'reason-required' ? REFUSE.reason() : code === 'already-decided' ? REFUSE.decided() : REFUSE.refused());
}
