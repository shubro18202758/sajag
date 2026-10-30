/**
 * The corridor's shared escort lifecycle (SPEC §5.3 PlanPanel [S6] +
 * ConvoyCard [S6]) — ONE state for the movement this console launched (or
 * adopted), read by the Plan tab (Launch / Stop / Clear) and the Movement
 * tab's ConvoyCard (figures, hold, proposals), so the two never disagree
 * and never fan out into parallel polls. The status itself is the shared
 * follower's (template/escort.svelte.ts); the corridor summary stays
 * template/corridor.svelte.ts. Both keep their paths — every wave's
 * canvases and vitals import them.
 *
 *   plan(params)     createMovement + planMovement (the audited
 *                    pre-movement workflow); the plan document lands here
 *                    for both tabs, and the corridor event it registered
 *                    (C-I event_id) is loaded onto the board and flown to
 *   launch()         Launch escort — a named duty officer travels in the
 *                    request (C-J); offered only on a plan that may depart
 *   stop()           the officer's STOP (C-J, idempotent)
 *   clear()          post-clearance restoration (C-J /clear): how the
 *                    corridor event closed, shown in the Plan tab
 *   adopt()          an escort launched elsewhere (the API, another
 *                    console, a reload) is picked up once: the active
 *                    protected movement on the board is asked for its
 *                    escort status, and a running one is followed
 *
 * No client-side simulation: every step is a real call and every failure
 * renders honestly. One POST per click: the store guards its own calls.
 */
import { ApiError, createMovement, launchEscort, planMovement, stopEscort } from '$lib/api/client';
import type { MovementPlanDoc } from '$lib/api/client';
import { clearMovement } from '$lib/ops/client';
import { fetchEscortStatus } from '$lib/gods-eye/city-api';
import { ops } from '$lib/ops/store.svelte';
import { toasts } from '$lib/shell/toast.svelte';
import { focus } from '$lib/gods-eye/focus.svelte';
import { t } from '$lib/i18n/strings';
import { tOps } from '$lib/i18n/strings.ops';
import { displayText } from '$lib/gods-eye/plates';
import { escortFollower, type EscortTerminal } from '$lib/ops/components/template/escort.svelte';
import { landmark } from '$lib/city';
import type { EscortPhase } from '$lib/types';
import type { EscortStatus } from '$lib/gods-eye/city-api';

export type { EscortTerminal };

/**
 * The template's canonical POI list ([lon, lat] — API order): City Pack landmarks
 * (cities/<id>/landmarks.json through $lib/city — canonical ids, names and points),
 * each on or beside the city's road network. Indices are the planner's: the default
 * trip runs from Mantralaya (1) to the airport, Terminal 2 (12) — the protected-movement
 * corridor (Marine Drive, the Coastal Road or Worli seaface, the Sea Link, BKC, the
 * airport road); Raj Bhavan, KEM and Sion hospitals and Dadar TT are trip ends too.
 * scripts/poi_route_matrix.py POIS mirrors this list.
 */
const PLAN_POI_IDS = [
	'csmt',
	'mantralaya',
	'churchgate',
	'wankhede',
	'girgaon_chowpatty',
	'raj_bhavan',
	'haji_ali',
	'kem',
	'dadar_tt',
	'sion_hospital',
	'bkc',
	'kalanagar',
	'airport_t2',
	'weh_andheri',
] as const;

export const PLAN_POIS: ReadonlyArray<{ id: string; name: string; coord: [number, number] }> = PLAN_POI_IDS.flatMap((id) => {
	const l = landmark(id);
	return l ? [{ id, name: l.en, coord: [l.lon, l.lat] as [number, number] }] : [];
});

/** Movements already asked whether an escort runs for them (one adoption attempt each). */
const probed = new Set<string>();

class EscortLifecycle {
	phase = $state<EscortPhase>('idle');
	movementId = $state<string | null>(null);
	doc = $state.raw<MovementPlanDoc | null>(null);
	/** The departure the plan was asked for (epoch ms; the hold state's "re-plan after"). */
	plannedDepartureMs = $state<number | null>(null);
	/** The origin / destination indices the plan was asked for (the Movement tab's figures). */
	originIdx = $state(1);
	destIdx = $state(12);
	vvipClass = $state<'Z+' | 'Z' | 'Y' | 'X'>('Z');
	startedAt = $state<number | null>(null);
	/** The brain answered the officer's STOP with status 'stopped' (before the follower re-reads). */
	stopAnswered = $state(false);
	/** CLEAR in flight / its answer: how the corridor event closed (C-F to_status). */
	clearing = $state(false);
	clearOutcome = $state<{ ok: boolean; toStatus: string | null; detail: string | null } | null>(null);
	error = $state<string | null>(null);
	note = $state<string | null>(null);
	/** The launch refused: the brain's own reason (a 409), never a raw body. */
	launchRefusal = $state<string | null>(null);

	/** The plan's ranked candidates (primary first). */
	get candidates() {
		const doc = this.doc;
		return doc ? [doc.primary_route, ...(doc.alternate_routes ?? [])].filter((r): r is NonNullable<typeof r> => r != null) : [];
	}

	get recommendedId(): string | null {
		const pick = this.doc?.decider_pick ?? null;
		const candidates = this.candidates;
		if (pick?.applied && pick.route_id && candidates.some((c) => c.route_id === pick.route_id)) return pick.route_id;
		return candidates[0]?.route_id ?? null;
	}

	get recommendedBy(): 'decider' | 'tactical' {
		return this.doc?.decider_pick?.applied && this.doc?.decider_pick?.route_id ? 'decider' : 'tactical';
	}

	get plannedEtaSec(): number | null {
		const r = this.candidates.find((c) => c.route_id === this.recommendedId);
		return r?.estimated_time_sec && r.estimated_time_sec > 0 ? r.estimated_time_sec : null;
	}

	get plannedDistanceM(): number | null {
		const r = this.candidates.find((c) => c.route_id === this.recommendedId);
		return r?.distance_m ?? r?.total_distance_m ?? null;
	}

	get escortRunning(): boolean {
		return this.phase === 'escorting' || this.phase === 'stopping';
	}

	/** The brain's final word on this escort (follower), or the STOP answer while it re-reads. */
	get endedStatus(): EscortTerminal | null {
		return escortFollower.movementId === this.movementId
			? (escortFollower.terminal ?? (this.stopAnswered ? 'stopped' : null))
			: null;
	}

	/** The follower's own status document, for THIS movement (the proposal/hold fallback). */
	get followedDoc() {
		return this.movementId && escortFollower.movementId === this.movementId ? escortFollower.status : null;
	}

	/** The brain says the escort ended: the lifecycle closes (the badge and timer stop). */
	sync() {
		if (this.escortRunning && this.endedStatus) this.phase = 'ended';
		// adoption waits for the lanes question to settle (see adopt)
		if (!this.movementId && ops.escortsDeployed != null) this.adopt();
	}

	/** Plan a corridor (origin/destination indices, class, departure ISO, optional label). */
	async plan(params: { originIdx: number; destIdx: number; vvipClass: 'Z+' | 'Z' | 'Y' | 'X'; departureIso: string; label: string }) {
		if (this.phase === 'planning' || this.escortRunning) return;
		this.error = null;
		this.note = null;
		this.launchRefusal = null;
		this.clearOutcome = null;
		this.doc = null;
		this.stopAnswered = false;
		escortFollower.follow(null);
		this.phase = 'planning';
		this.originIdx = params.originIdx;
		this.destIdx = params.destIdx;
		this.vvipClass = params.vvipClass;
		this.plannedDepartureMs = Date.parse(params.departureIso) || null;
		const from = PLAN_POIS[params.originIdx];
		const to = PLAN_POIS[params.destIdx];
		const req = { origin: from.coord, destination: to.coord, vvipClass: params.vvipClass, plannedDeparture: params.departureIso };
		try {
			const { movementId: id } = await createMovement({ ...req, title: params.label.trim() || null });
			this.movementId = id;
			const planned = await planMovement(id, req);
			this.doc = planned;
			const ranked = this.candidates.length;
			// No candidates: the Plan tab says NO ROUTE with the overall
			// reasoning — once (not also as a red error line).
			this.phase = ranked ? 'planned' : 'idle';
			toasts.push({
				kind: 'act',
				title: `${t(ops.lang, 'tpl_candidates')} · ${planned.status ?? '—'}`,
				body: `${id} · ${ranked}`,
			});
			// The plan is a corridor event now (C-I): load it onto the board at
			// once and fly the canvas to it (the focus bus waits for geometry).
			if (planned.event_id) {
				const eventId = planned.event_id;
				void ops.pollBoard().then(() => {
					if (ops.events.some((e) => e.eventId === eventId) && ops.selectedEventId !== eventId) ops.selectEvent(eventId);
				});
				focus.request(eventId);
			}
		} catch (err) {
			this.phase = 'idle';
			// A 409 from /plan: an escort is running for this movement — the
			// brain will not re-plan under a live convoy.
			const status = (err as { status?: unknown } | null)?.status;
			const msg = err instanceof Error ? err.message : String(err);
			this.error = status === 409 || /^409\b/.test(msg) ? tOps(ops.lang, 'escortRunningStopFirst') : msg;
		}
	}

	/** Launch the escort (a plan that may depart; the officer is the store's). */
	async launch() {
		const movementId = this.movementId;
		if (!movementId || !this.escortOfferedNow || this.escortRunning || this.phase === 'starting') return;
		this.error = null;
		this.note = null;
		this.launchRefusal = null;
		if (!ops.officerOn) {
			this.error = t(ops.lang, 'tpl_officer_needed');
			return;
		}
		this.phase = 'starting';
		this.stopAnswered = false;
		try {
			const res = await launchEscort(movementId, { officer: ops.dutyOfficer, destination: PLAN_POIS[this.destIdx].coord });
			if (res.status === 'running' || res.task_id) {
				// Contract C-J: the escort runs as a background task; the
				// ConvoyCard follows GET /movements/{id}/escort.
				this.phase = 'escorting';
				this.startedAt = Date.now();
				escortFollower.follow(movementId);
				toasts.push({ kind: 'act', title: t(ops.lang, 'tpl_escort_live'), body: `${movementId} · ${ops.dutyOfficer}` });
			} else {
				// A brain without escort control ran its loop inline and it ended
				// at once (no GPS stream) — say so instead of a timer pretending.
				this.phase = 'planned';
				this.note = `${t(ops.lang, 'tpl_escort_legacy')}${res.final_status ? ` · final status ${res.final_status}` : ''}${
					res.total_iterations != null ? ` · ${res.total_iterations} iteration(s)` : ''
				}`;
			}
		} catch (err) {
			this.phase = 'planned';
			this.launchRefusal = escortRefusalText(err);
			this.error = this.launchRefusal;
		}
	}

	private get escortOfferedNow(): boolean {
		const doc = this.doc;
		const status = doc?.status;
		const held = status === 'hold' || doc?.hold === true;
		return !!movementOk(this.movementId) && !!doc && status !== 'no_route' && !held && this.candidates.length > 0;
	}

	/** The officer stops the escort (C-J POST /movements/{id}/stop, idempotent). */
	async stop() {
		const movementId = this.movementId;
		if (!movementId || this.phase !== 'escorting') return;
		this.error = null;
		if (!ops.officerOn) {
			this.error = t(ops.lang, 'tpl_officer_needed');
			return;
		}
		this.phase = 'stopping';
		try {
			const res = (await stopEscort(movementId, ops.dutyOfficer)) as { status?: string } | null;
			this.stopAnswered = res?.status === 'stopped';
			escortFollower.refresh();
			toasts.push({ kind: 'act', title: t(ops.lang, 'tpl_escort_stopped'), body: `${movementId} · ${ops.dutyOfficer}` });
			if (!this.stopAnswered) this.phase = 'escorting'; // the follower reports the brain's real state
		} catch (err) {
			this.phase = 'escorting';
			this.error = err instanceof Error ? err.message : String(err);
		}
	}

	/** CLEAR (C-J /clear {officer}): the corridor event closes 'completed' after a live run, 'cancelled' if it never went live. */
	async clear() {
		const movementId = this.movementId;
		if (!movementId || this.clearing || this.escortRunning) return;
		this.error = null;
		if (!ops.officerOn) {
			this.error = t(ops.lang, 'tpl_officer_needed');
			return;
		}
		this.clearing = true;
		this.clearOutcome = null;
		try {
			const res = await clearMovement(movementId, ops.dutyOfficer);
			this.clearOutcome = { ok: res.ok, toStatus: res.toStatus, detail: res.detail };
			if (res.ok) {
				void ops.pollBoard(true);
				toasts.push({
					kind: 'act',
					title: tOps(ops.lang, 'escortCleared'),
					body: `${movementId} · ${res.toStatus ?? '—'} · ${ops.dutyOfficer}`,
				});
			}
		} catch (err) {
			this.clearOutcome = { ok: false, toStatus: null, detail: err instanceof Error ? err.message : String(err) };
		} finally {
			this.clearing = false;
		}
	}

	/** Back to idle: the next plan starts clean (the follower is dropped). */
	reset() {
		this.phase = 'idle';
		this.movementId = null;
		this.doc = null;
		this.plannedDepartureMs = null;
		this.error = null;
		this.note = null;
		this.startedAt = null;
		this.stopAnswered = false;
		this.launchRefusal = null;
		this.clearOutcome = null;
		escortFollower.follow(null);
		this.adopt();
	}

	/**
	 * An escort this console did not launch: the active protected movement on
	 * the board is adopted when the stack reports its escort RUNNING. The
	 /escorts lanes answer first (one GET for every escort): a movement the
	 * lanes know as running is adopted from its lane, with no per-movement
	 * request at all. Only when the lanes do not answer (an older brain —
	 * escortsDeployed is not true) is the movement's own status document
	 * asked once (C-J GET /movements/{id}/escort).
	 */
	adopt() {
		if (this.phase !== 'idle' || this.movementId) return;
		// the lanes question comes first: until GET /api/convoy/escorts has
		// answered (deployed or not), whether this movement has an escort is
		// unknown — re-run when it settles instead of asking per movement
		if (ops.escortsDeployed == null) return;
		const ev = ops.events.find(
			(e) => e.source !== 'offline-fixture' && e.eventKind === 'protected_movement' && e.state === 'active' && !!e.movementId,
		);
		const mid = ev?.movementId;
		if (!mid || probed.has(mid)) return;
		probed.add(mid);
		const adopt = (startedAt: number | null | undefined) => {
			if (this.phase !== 'idle' || this.movementId) return;
			this.movementId = mid;
			this.startedAt = startedAt ?? Date.now();
			this.phase = 'escorting';
			this.note = tOps(ops.lang, 'escortAdopted');
			escortFollower.follow(mid);
		};
		if (ops.escortsDeployed === true) {
			// the lanes answer: they list every running escort — no per-movement request
			const lane = ops.escorts.find((l) => l.movementId === mid);
			if (lane && (lane.status === 'running' || lane.status === 'waiting_for_gps')) adopt(null);
			return;
		}
		void fetchEscortStatus(mid, AbortSignal.timeout(6000))
			.then((st) => {
				if (this.phase !== 'idle' || this.movementId) return;
				if (st.status !== 'running' && st.status !== 'waiting_for_gps') return;
				adopt(st.startedAt);
			})
			.catch(() => {
				// no escort route / no escort: the planner stays idle
			});
	}
}

const movementOk = (v: string | null): v is string => !!v;

/** Why the brain refused the escort: a 409 carries its reason as ApiError.detail —
 * shown as written (plate-masked unless an officer is named), never the raw body. */
export function escortRefusalText(err: unknown): string {
	if (err instanceof ApiError && err.status === 409 && typeof err.detail === 'string' && err.detail.trim()) {
		return displayText(err.detail, ops.officerOn);
	}
	return err instanceof Error ? err.message : String(err);
}

/**
 * The legacy referred actions of a running escort (an older brain): ONLY
 * when the escort reports no proposals — the lanes are not deployed AND
 * the followed document does not report authority (OW:1439 pins the list
 * absent beside a proposal; CC:1089 counts the rows otherwise).
 */
export function legacyApprovals(
	escortsDeployed: boolean | null,
	status: EscortStatus | null,
	live: boolean,
): EscortStatus['pendingApprovals'] {
	const reported = escortsDeployed === true || status?.proposalsReported === true;
	if (reported || !live || !status) return [];
	return status.pendingApprovals ?? [];
}

/**
 * The /escorts lanes know this movement's escort as RUNNING (audit C S2):
 * the answer exists (`ops.escortsDeployed === true`) and the movement's lane
 * reports 'running' or the GPS wait. This is the /ops wall's live read — the
 * wall never adopts the escort nor starts its per-movement poll (the shared
 * follower is the cockpit's), but a lane it knows as running is never shown
 * as a 'planned' shell.
 */
export function laneRunning(
	deployed: boolean | null,
	lanes: ReadonlyArray<{ movementId: string; status: string }>,
	movementId: string | null | undefined,
): boolean {
	if (deployed !== true || !movementId) return false;
	return lanes.some((l) => l.movementId === movementId && (l.status === 'running' || l.status === 'waiting_for_gps'));
}

/** THE corridor escort lifecycle (one per console). */
export const escortLifecycle = new EscortLifecycle();
