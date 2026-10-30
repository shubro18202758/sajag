/**
 * Decision units (SPEC §5.4, review B1; plan X9) — one decision unit, one
 * home, one honest card. A unit is what an officer decides ONCE:
 *
 *   stolen-sighting   one stolen vehicle (watchlist basis stolen_vehicle_fir)
 *                     with N pending R_STOLEN_SIGHTING rows is ONE unit:
 *                     authorise the newest sighting, or dismiss them all
 *                     under one reason. Its step 2 (open the pursuit) rides
 *                     inside the same unit, never a second one.
 *   pursuit           a flagged vehicle with a latest sighting and no open
 *                     pursuit (the store's pursuitCandidates) that is NOT a
 *                     stolen-sighting unit already; its refusal is inline.
 *   echallan          a pending penal recommendation.
 *   escort-proposal   an escort's one open proposal (time-boxed).
 *   corridor-request  a 108 ambulance dispatch in 'requested'.
 *
 * `UNIT_KINDS` is a table, one entry per kind: `collect(state)` builds that
 * kind's units from the ops store (or a fixture with the same shape),
 * `title`, `deadline`, `severity` and `dataHooks` (the `queue-card` data-*
 * attributes the /ops item carries). `decisionUnits()` returns every unit,
 * sorted by deadline (none last), then severity. A kind added later (the
 * DSS's `dss`, OS-DECK-B) registers its own entry here and is covered by
 * tests/decisions.unit.mjs, which iterates the table.
 *
 * Marks: `Unit.title` carries the MASKED registration mark (it reaches the
 * navbar count's tooltip, the LiveStrip, link cards and share paths); the
 * cards print the mark through `ops.plate` at render time (raw only for a
 * named duty officer, C6).
 */
import { ops } from '$lib/ops/store.svelte';
import { approvalSpent, isEmulatedActor } from '$lib/ops/client';
import { maskPlate, maskPlatesInText } from '$lib/ops/format';
import { t } from '$lib/i18n/strings';
import { tOps } from '$lib/i18n/strings.ops';
import '$lib/i18n/packs.decisions';
import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
import {
	isWaiting,
	parseDssSummary,
	parseSecondOrder,
	severityFor,
	type DssSummary,
	type SecondOrderFlag,
} from '$lib/dss/dss-data';
import type { VerificationState } from '$lib/ops/types';
import type {
	CorridorEvent,
	DispatchRecord,
	EnforcementRecommendation,
	EscortLane,
	EscortProposal,
	PursuitCandidate,
	VehicleWatchRecord,
} from '$lib/ops/types';

/** One decision unit (plan contract X9, frozen). */
export interface Unit {
	kind: string;
	id: string;
	subjectUrn: string;
	title: string;
	deadline: number | null;
	severity: 0 | 1 | 2 | 3;
	data: Record<string, unknown>;
}

/** What `collect` reads: the ops store (or a fixture of the same shape, tests). */
export type DecisionState = typeof ops;

/** One kind's entry in the table. */
export interface UnitKind {
	kind: string;
	/** Every unit of this kind in `state` (the live ops store by default). */
	collect(state?: DecisionState): Unit[];
	/** The imperative title as this console may print it (the mark through ops.plate). */
	title(u: Unit, lang?: string): string;
	deadline(u: Unit): number | null;
	severity(u: Unit): 0 | 1 | 2 | 3;
	/** The `queue-card` data-* attributes of the unit's /ops item (values as strings). */
	dataHooks(u: Unit): Record<string, string>;
	/** True for a time-boxed kind (a countdown, an expiry bar; never a modal). */
	timeBoxed: boolean;
}

export const STOLEN_RULE = 'R_STOLEN_SIGHTING';
/** The 108 golden hour (a corridor request's deadline). */
export const GOLDEN_HOUR_MS = 60 * 60 * 1000;

// ── data shapes (Unit.data per kind) ────────────────────────────────────

/** Step 2 of a stolen-vehicle unit: the pursuit opening, inside the same unit. */
export interface PursuitStep {
	/** ready = it can be offered (refusal null); blocked = it cannot (refusal named); open = a pursuit is already open. */
	state: 'ready' | 'blocked' | 'open';
	refusal: 'no-anchor' | 'no-approved-recommendation' | null;
	candidate: PursuitCandidate | null;
	/** The open pursuit event, when state is 'open'. */
	eventId: string | null;
}

export interface StolenData extends Record<string, unknown> {
	vehicleId: string;
	plate: string | null;
	/** Pending R_STOLEN_SIGHTING rows, newest first. */
	recs: EnforcementRecommendation[];
	newest: EnforcementRecommendation;
	/** The unspent approved R_STOLEN_SIGHTING (one approval authorises ONE pursuit, C6), or null. */
	approved: EnforcementRecommendation | null;
	fir: string | null;
	watch: VehicleWatchRecord | null;
	/** The oracle's refusal of the newest sighting's decision (verbatim, never retried). */
	refusal: { status: number; detail: string } | null;
	step: PursuitStep;
	emulated: boolean;
}

export interface PursuitData extends Record<string, unknown> {
	vehicleId: string;
	plate: string | null;
	candidate: PursuitCandidate;
	refusal: 'no-anchor' | 'no-approved-recommendation' | null;
	emulated: boolean;
}

export interface EchallanData extends Record<string, unknown> {
	rec: EnforcementRecommendation;
	plate: string | null;
	/** The vehicle is reported stolen (FIR): Reject only, never Approve (C-N). */
	stolen: VehicleWatchRecord | null;
	refusal: { status: number; detail: string } | null;
	emulated: boolean;
}

export interface EscortData extends Record<string, unknown> {
	proposal: EscortProposal;
	lane: EscortLane | null;
	event: CorridorEvent | null;
	emulated: boolean;
}

export interface CorridorData extends Record<string, unknown> {
	dispatch: DispatchRecord;
	event: CorridorEvent | null;
	emulated: boolean;
}

/** A decision-support unit's subject: the entity whose props.dss proposes a response (plan X22). */
export interface DssData extends Record<string, unknown> {
	dssId: string;
	/** The subject entity's URN (osint_event:<uuid> | event:<uuid>) — the unit's subjectUrn. */
	urn: string;
	subjectKind: 'osint_event' | 'event';
	label: string;
	/** The C-T DssSummary (no GET — plan R11/X13; the full C-U object loads when the card opens). */
	summary: DssSummary;
	verification: VerificationState | null;
	credibility: number | null;
	secondOrder: SecondOrderFlag[];
	eventClass: string | null;
	situationSummary: string | null;
	sajagEventKind: string | null;
	promotedEventId: string | null;
	/** The event entity's lifecycle state (osint subjects carry null). */
	eventState: string | null;
	emulated: boolean;
}

export const stolenOf = (u: Unit) => u.data as StolenData;
export const pursuitOf = (u: Unit) => u.data as PursuitData;
export const echallanOf = (u: Unit) => u.data as EchallanData;
export const escortOf = (u: Unit) => u.data as EscortData;
export const corridorOf = (u: Unit) => u.data as CorridorData;
export const dssOf = (u: Unit) => u.data as DssData;

// ── helpers ─────────────────────────────────────────────────────────────

const ms = (iso: string | null | undefined): number => {
	const v = iso ? Date.parse(iso) : NaN;
	return Number.isFinite(v) ? v : 0;
};

/** The recommendation's evidence came from the emulator. */
export function emulatedRec(rec: EnforcementRecommendation): boolean {
	const src = rec.evidence?.['source'];
	return typeof src === 'string' && src.toLowerCase().includes('emulat');
}

/**
 * The FIR reference of a stolen vehicle: the oracle's own evidence.fir_ref
 * (C-N), else extracted from the sighting text or the earmark reason the
 * way the oracle does (the word FIR on its own, a reference with a digit).
 */
export function firOf(recs: readonly EnforcementRecommendation[], watch: VehicleWatchRecord | null): string | null {
	for (const r of recs) {
		const ref = r.evidence?.fir_ref;
		if (typeof ref === 'string' && ref.trim()) return ref.trim();
	}
	for (const text of [...recs.map((r) => r.recommendation ?? ''), watch?.earmarkReason ?? '']) {
		const m = /\bFIR\b[\s:#.-]*(?:No\b\.?\s*)?([A-Za-z0-9][A-Za-z0-9/-]{0,31})/i.exec(text);
		const ref = m?.[1].replace(/[/-]+$/, '');
		if (ref && /\d/.test(ref)) return ref;
	}
	return null;
}

/** A vehicle's pursuit step (step 2 of its stolen-vehicle unit). */
export function pursuitStep(state: DecisionState, vehicleId: string): PursuitStep {
	const candidate = state.pursuitCandidates.find((p) => p.vehicle.vehicleId === vehicleId) ?? null;
	if (candidate) return { state: candidate.refusal ? 'blocked' : 'ready', refusal: candidate.refusal, candidate, eventId: null };
	const open = state.pursuitFor(vehicleId);
	if (open) return { state: 'open', refusal: null, candidate: null, eventId: open.eventId };
	// flagged without a latest sighting (or not flagged): nothing to anchor the pursuit on
	return { state: 'blocked', refusal: 'no-anchor', candidate: null, eventId: null };
}

const plateOr = (plate: string | null | undefined, fallback: string) => maskPlate(plate) ?? fallback.slice(0, 8);

/** The masked mark of a unit (titles that leave the card). */
function masked(plate: string | null | undefined, id: string): string {
	return plateOr(plate, id);
}

// ── the table ───────────────────────────────────────────────────────────

/**
 * The stolen-vehicle unit's imperative: authorise the newest sighting; once
 * authorised, its next step (open the pursuit) when it can be offered, else
 * dismiss the earlier sightings.
 */
export function stolenTitleKey(d: StolenData): string {
	if (!d.approved) return 'dec_title_stolen';
	return d.step.state === 'ready' ? 'dec_title_pursuit' : 'dec_title_stolen_after';
}

const stolenKind: UnitKind = {
	kind: 'stolen-sighting',
	timeBoxed: false,
	collect(state = ops) {
		const by = new Map<string, EnforcementRecommendation[]>();
		for (const r of state.recommendations) {
			if (r.status !== 'pending' || r.ruleId !== STOLEN_RULE) continue;
			const key = r.vehicleId ?? r.recommendationId;
			const list = by.get(key) ?? [];
			list.push(r);
			by.set(key, list);
		}
		const out: Unit[] = [];
		for (const [vehicleId, list] of by) {
			const recs = [...list].sort((a, b) => ms(b.createdAt) - ms(a.createdAt));
			const newest = recs[0];
			const watch = state.watchlist.find((w) => w.vehicleId === vehicleId) ?? null;
			const approved =
				state.approvedRecommendations.find((a) => a.vehicleId === vehicleId && a.ruleId === STOLEN_RULE && !approvalSpent(a)) ?? null;
			const refusal = state.recommendationRefusals[newest.recommendationId] ?? null;
			const plate = newest.plate ?? watch?.plate ?? null;
			const data: StolenData = {
				vehicleId,
				plate,
				recs,
				newest,
				approved,
				fir: firOf(recs, watch),
				watch,
				refusal: refusal ? { status: refusal.status, detail: refusal.detail } : null,
				step: pursuitStep(state, vehicleId),
				emulated: recs.some(emulatedRec),
			};
			const u: Unit = { kind: 'stolen-sighting', id: vehicleId, subjectUrn: `vehicle:${vehicleId}`, title: '', deadline: null, severity: 3, data };
			u.title = t('en', stolenTitleKey(data), masked(plate, vehicleId));
			out.push(u);
		}
		return out;
	},
	title(u, lang = ops.lang) {
		const d = stolenOf(u);
		return t(lang, stolenTitleKey(d), ops.plate(d.plate) ?? d.vehicleId.slice(0, 8));
	},
	deadline: () => null,
	severity: () => 3,
	dataHooks(u) {
		const d = stolenOf(u);
		return { kind: 'stolen-sighting', id: d.vehicleId, count: String(d.recs.length), 'rec-ids': d.recs.map((r) => r.recommendationId).join(' ') };
	},
};

const pursuitKind: UnitKind = {
	kind: 'pursuit',
	timeBoxed: false,
	collect(state = ops) {
		const stolen = new Set(
			state.recommendations.filter((r) => r.status === 'pending' && r.ruleId === STOLEN_RULE).map((r) => r.vehicleId ?? r.recommendationId),
		);
		return state.pursuitCandidates
			.filter((c) => !stolen.has(c.vehicle.vehicleId))
			.map((c) => {
				const data: PursuitData = {
					vehicleId: c.vehicle.vehicleId,
					plate: c.vehicle.plate,
					candidate: c,
					refusal: c.refusal,
					emulated: c.vehicle.lastSighting?.source === 'emulated_anpr',
				};
				return {
					kind: 'pursuit',
					id: c.vehicle.vehicleId,
					subjectUrn: `vehicle:${c.vehicle.vehicleId}`,
					title: t('en', 'dec_title_pursuit', masked(c.vehicle.plate, c.vehicle.vehicleId)),
					deadline: null,
					severity: 2,
					data,
				} satisfies Unit;
			});
	},
	title(u, lang = ops.lang) {
		const d = pursuitOf(u);
		return t(lang, 'dec_title_pursuit', ops.plate(d.plate) ?? d.vehicleId.slice(0, 8));
	},
	deadline: () => null,
	severity: () => 2,
	dataHooks(u) {
		return { kind: 'pursuit', id: pursuitOf(u).vehicleId, refusal: pursuitOf(u).refusal ?? '' };
	},
};

const echallanKind: UnitKind = {
	kind: 'echallan',
	timeBoxed: false,
	collect(state = ops) {
		return state.recommendations
			.filter((r) => r.status === 'pending' && r.ruleId !== STOLEN_RULE)
			.map((rec) => {
				const stolen = state.stolenVehicle(rec.vehicleId);
				const refusal = state.recommendationRefusals[rec.recommendationId] ?? null;
				const data: EchallanData = {
					rec,
					plate: rec.plate,
					stolen,
					refusal: refusal ? { status: refusal.status, detail: refusal.detail } : null,
					emulated: emulatedRec(rec),
				};
				return {
					kind: 'echallan',
					id: rec.recommendationId,
					subjectUrn: `recommendation:${rec.recommendationId}`,
					title: t('en', stolen ? 'dec_title_echallan_stolen' : 'dec_title_echallan', masked(rec.plate, rec.recommendationId)),
					deadline: null,
					severity: 1,
					data,
				} satisfies Unit;
			});
	},
	title(u, lang = ops.lang) {
		const d = echallanOf(u);
		return t(lang, d.stolen ? 'dec_title_echallan_stolen' : 'dec_title_echallan', ops.plate(d.plate) ?? u.id.slice(0, 8));
	},
	deadline: () => null,
	severity: () => 1,
	dataHooks(u) {
		const d = echallanOf(u);
		return { kind: 'echallan', id: u.id, stolen: d.stolen ? '1' : '', refused: d.refusal ? '1' : '' };
	},
};

/** An escort proposal's whole sentence as this console prints it (route, km, avoids, closures; or the hold and its bound). */
export function escortSentence(p: EscortProposal, state: DecisionState = ops): string {
	const s = state.escortProposalText(p);
	return s ? s.charAt(0).toUpperCase() + s.slice(1) : p.approvalId;
}

/**
 * An escort proposal's imperative title: the sentence's first clause ("Plan B
 * via AJC Bose Road", "Hold the convoy short of Chowringhee Road"); the rest of
 * the sentence is the card's Why, so nothing it says is lost.
 */
export function escortTitle(p: EscortProposal, state: DecisionState = ops): string {
	const s = escortSentence(p, state);
	const cuts = [s.indexOf(' · '), s.indexOf(' (congestion')].filter((i) => i > 0);
	return cuts.length ? s.slice(0, Math.min(...cuts)) : s;
}

const escortKind: UnitKind = {
	kind: 'escort-proposal',
	timeBoxed: true,
	collect(state = ops) {
		return state.escortProposals.map((p) => {
			const lane = state.escorts.find((l) => l.movementId === p.movementId) ?? null;
			const event = state.eventById(p.eventId);
			const data: EscortData = { proposal: p, lane, event, emulated: lane?.gpsMode === 'emulated' || !!event?.emulated };
			return {
				kind: 'escort-proposal',
				id: p.approvalId,
				subjectUrn: p.eventId ? `event:${p.eventId}` : `convoy:${p.movementId}`,
				title: maskPlatesInText(escortTitle(p, state)),
				deadline: p.expiresAt ?? null,
				severity: 3,
				data,
			} satisfies Unit;
		});
	},
	title(u) {
		return escortTitle(escortOf(u).proposal);
	},
	deadline: (u) => escortOf(u).proposal.expiresAt ?? null,
	severity: () => 3,
	dataHooks(u) {
		return { kind: 'escort-proposal', id: u.id, 'movement-id': escortOf(u).proposal.movementId };
	},
};

/** A dispatch the emulator produced: its event is emulated, or its requester is. */
function emulatedDispatch(state: DecisionState, d: DispatchRecord): boolean {
	return !!state.eventById(d.eventId)?.emulated || isEmulatedActor(d.requestedBy);
}

const corridorKind: UnitKind = {
	kind: 'corridor-request',
	timeBoxed: false,
	collect(state = ops) {
		return state.openDispatches
			.filter((d) => d.agency === 'ambulance' && d.status === 'requested')
			.map((d) => {
				const data: CorridorData = { dispatch: d, event: state.eventById(d.eventId), emulated: emulatedDispatch(state, d) };
				const created = ms(d.createdAt);
				return {
					kind: 'corridor-request',
					id: d.dispatchId,
					subjectUrn: `dispatch:${d.dispatchId}`,
					title: t('en', 'dec_title_corridor', d.unitId ?? d.dispatchId.slice(0, 8)),
					deadline: created ? created + GOLDEN_HOUR_MS : null,
					// a request filed from the 108 driver's own view first
					severity: d.requestedBy === '108-driver' ? 3 : 2,
					data,
				} satisfies Unit;
			});
	},
	title(u, lang = ops.lang) {
		const d = corridorOf(u).dispatch;
		return t(lang, 'dec_title_corridor', d.unitId ?? d.dispatchId.slice(0, 8));
	},
	deadline: (u) => {
		const created = ms(corridorOf(u).dispatch.createdAt);
		return created ? created + GOLDEN_HOUR_MS : null;
	},
	severity: (u) => (corridorOf(u).dispatch.requestedBy === '108-driver' ? 3 : 2),
	dataHooks(u) {
		return { kind: 'corridor-request', id: u.id };
	},
};

const expiresMsOf = (s: DssSummary): number | null => {
	const ms = Date.parse(s.expiresAt ?? '');
	return Number.isFinite(ms) ? ms : null;
};

/**
 * The decision-support unit (plan X22): ONE per DSS whose props.dss is
 * 'proposed' and unexpired, read from the city registry's `osint_event` AND
 * `event` entities (R11: no new GET — the summary rides the snapshot). The
 * same DSS on both surfaces is still ONE decision, so the collect dedupes by
 * dss id, keeping the osint_event subject (its promotion is what approving
 * can cause). An expired summary is never a unit; `deadline` is
 * `expires_at` (generated_at + horizon_min).
 */
const dssKind: UnitKind = {
	kind: 'dss',
	timeBoxed: false,
	collect(state = ops) {
		const now = Date.now();
		const seen = new Set<string>();
		const out: Unit[] = [];
		const events = state.events.map((e) => ({ eventId: e.eventId, eventKind: e.eventKind }));
		// osint_event first: its subject is the one approving can promote (C-U approve step 1)
		for (const kind of ['osint_event', 'event'] as const) {
			for (const e of cityRegistry.byKind(kind)) {
				const summary = parseDssSummary(e.props.dss);
				if (!summary || !isWaiting(summary, now) || seen.has(summary.dssId)) continue;
				seen.add(summary.dssId);
				const p = e.props;
				const str = (v: unknown) => (typeof v === 'string' && v.length ? v : null);
				const flags = parseSecondOrder(p.second_order);
				const verification = e.verificationState;
				const eventClass = str(p.event_class);
				const situationSummary = str(p.summary);
				const data: DssData = {
					dssId: summary.dssId,
					urn: e.urn,
					subjectKind: kind,
					label: e.label,
					summary,
					verification,
					credibility: e.credibility,
					secondOrder: flags,
					eventClass,
					situationSummary,
					sajagEventKind: str(p.sajag_event_kind),
					promotedEventId: str(p.promoted_event_id),
					eventState: kind === 'event' ? e.state : null,
					emulated: false,
				};
				const u: Unit = {
					kind: 'dss',
					id: summary.dssId,
					subjectUrn: e.urn,
					title: t('en', 'dss_title', e.label),
					deadline: expiresMsOf(summary),
					severity: severityFor(flags, verification, eventClass, situationSummary, events),
					data,
				};
				out.push(u);
			}
		}
		return out;
	},
	title(u, lang = ops.lang) {
		return t(lang, 'dss_title', dssOf(u).label);
	},
	deadline: (u) => expiresMsOf(dssOf(u).summary),
	severity(u) {
		const d = dssOf(u);
		return severityFor(
			d.secondOrder,
			d.verification,
			d.eventClass,
			d.situationSummary,
			ops.events.map((e) => ({ eventId: e.eventId, eventKind: e.eventKind })),
		);
	},
	dataHooks(u) {
		return { kind: 'dss', id: u.id, subject: dssOf(u).urn };
	},
};

/** The unit kinds, one entry per kind (plan X9). Order = the tie-break after deadline and severity. */
export const UNIT_KINDS: Record<string, UnitKind> = {
	'escort-proposal': escortKind,
	'corridor-request': corridorKind,
	'stolen-sighting': stolenKind,
	pursuit: pursuitKind,
	echallan: echallanKind,
	dss: dssKind,
};

const KIND_ORDER = () => Object.keys(UNIT_KINDS);

/** Deadline first (none last), then severity (high first), then the table order, then id. */
export function compareUnits(a: Unit, b: Unit): number {
	const order = KIND_ORDER();
	return (
		(a.deadline ?? Infinity) - (b.deadline ?? Infinity) ||
		b.severity - a.severity ||
		order.indexOf(a.kind) - order.indexOf(b.kind) ||
		(a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
	);
}

/** Every decision unit, sorted by deadline, then severity (SPEC §5.3 Inbox, §5.4). */
export function decisionUnits(state: DecisionState = ops): Unit[] {
	const out: Unit[] = [];
	for (const k of Object.values(UNIT_KINDS)) {
		try {
			out.push(...k.collect(state));
		} catch {
			// one kind's failure never blanks the others
		}
	}
	return out.sort(compareUnits);
}

/** The display title of a unit (the kind's own title; the unit's stored title as a fallback). */
export function unitTitle(u: Unit, lang?: string): string {
	try {
		return UNIT_KINDS[u.kind]?.title(u, lang) ?? u.title;
	} catch {
		return u.title;
	}
}

/** The unit's emulated flag (the view options' "hide emulated"). */
export function unitEmulated(u: Unit): boolean {
	return u.data.emulated === true;
}

/** "Reported stolen" chip text for an e-challan on a stolen vehicle (the old queue's wording, verbatim). */
export const stolenChip = (lang: string) => tOps(lang, 'queueStolenChip');
