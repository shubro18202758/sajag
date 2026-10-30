<script lang="ts">
	/**
	 * /design/decisions — the UI-S5A harness (plan R18, X16): a dev-only page,
	 * not linked anywhere, that seeds the ops store with FICTIONAL decision
	 * data (masked marks only, the fictional "Sandbox Officer", made-up
	 * cameras on real road names) and shows every decision surface offline:
	 *
	 *   - the /ops Decisions column (DecisionQueue) over the fixture units;
	 *   - each kind's ProposalCard;
	 *   - a right dock with the Inbox (list and detail), a Movement stand-in
	 *     holding the escort proposal (its home on /), and an inspector
	 *     stand-in with the Pursuit section (a stale last read, a likely
	 *     passed choke);
	 *   - the LiveStrip feed (liveStripFeed) through the navbar's strip.
	 *
	 * Nothing is sent: the ops store is never started (no poller; the
	 * Decisions column reads the rejected list once, a GET, for its tab
	 * count), and a decision clicked here reaches the client's writer
	 * only with an officer named, against whatever backend serves the page —
	 * so the harness keeps the officer empty unless `?officer=1`.
	 *
	 *   ?open=stolen|pursuit|echallan|escort|corridor   the Inbox detail of that unit
	 *                                                   (escort: the Movement stand-in)
	 *   ?section=pursuit                                the inspector stand-in with the Pursuit section
	 *   ?against=1                                      the read drove against a one-way (the flag)
	 *   ?officer=1                                      name the fictional officer
	 *
	 * UI-S7B deletes it.
	 */
	import { onMount, untrack } from 'svelte';
	import { page } from '$app/stores';
	import { ops } from '$lib/ops/store.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { provideUiLang, Tabs, Tag, Callout } from '$lib/ui';
	import { eventKindIcon, ACTION_ICON } from '$lib/design/icons';
	import Inbox from '$lib/decisions/Inbox.svelte';
	import ProposalCard from '$lib/decisions/ProposalCard.svelte';
	import PursuitPlan from '$lib/decisions/sections/PursuitPlan.svelte';
	import DecisionQueue from '$lib/ops/components/DecisionQueue.svelte';
	import { decisionUnits } from '$lib/decisions/units';
	import { liveStripFeed } from '$lib/decisions/live';
	import type {
		CorridorEvent,
		DispatchRecord,
		EnforcementRecommendation,
		EscortLane,
		InterceptionPlan,
		JunctionRef,
		SegmentRef,
		VehicleWatchRecord,
	} from '$lib/ops/types';

	provideUiLang(() => commandBar.lang);

	// ── the fixture (fictional; relative to the page's clock) ───────────────

	const NOW = Date.now();
	const iso = (msAgo: number) => new Date(NOW - msAgo).toISOString();
	const MIN = 60_000;

	const V_STOLEN = 'd5a1c0de-0000-4000-8000-0000000000a1';
	const V_PURSUED = 'd5a1c0de-0000-4000-8000-0000000000a2';
	const V_BLOCKED = 'd5a1c0de-0000-4000-8000-0000000000a3';
	const V_WARRANT = 'd5a1c0de-0000-4000-8000-0000000000a4';
	const V_STOLEN_PENAL = 'd5a1c0de-0000-4000-8000-0000000000a5';
	const P_EVENT = 'd5a1c0de-0000-4000-8000-0000000000e1';
	const MV_EVENT = 'd5a1c0de-0000-4000-8000-0000000000e2';
	const MOVEMENT = 'mv-harness-z';
	const rid = (n: number) => `d5a1c0de-0000-4000-8000-0000000001${String(n).padStart(2, '0')}`;
	const DSP = 'd5a1c0de-0000-4000-8000-0000000000d1';

	const SEGMENTS: SegmentRef[] = [
		{ segmentId: 1049, roadName: 'Dr Ambedkar Road (Parel flyover)', roadClass: 'secondary', coordinates: [[72.8574, 19.0028], [72.8607, 19.0021], [72.8634, 19.0043]] },
		{ segmentId: 1052, roadName: 'Senapati Bapat Marg', roadClass: 'secondary', coordinates: [[72.8634, 19.0043], [72.8653, 19.0084]] },
		{ segmentId: 1013, roadName: 'P D Mello Road', roadClass: 'secondary', coordinates: [[72.8443, 19.0089], [72.8573, 19.0094]] },
	];
	const JUNCTIONS: JunctionRef[] = [
		{ junctionId: 11, name: 'Hindmata', nameMr: null, lon: 72.8634, lat: 19.0043, junctionType: 'signal', signalControl: true },
		{ junctionId: 12, name: 'Dadar TT Circle', nameMr: null, lon: 72.8653, lat: 19.0084, junctionType: 'signal', signalControl: true },
		{ junctionId: 13, name: 'King’s Circle', nameMr: null, lon: 72.8574, lat: 19.0028, junctionType: 'roundabout', signalControl: false },
	];

	const sight = (lon: number, lat: number, msAgo: number, speed: number, heading: number) => ({ t: iso(msAgo), lon, lat, speedKmh: speed, heading, source: 'emulated_anpr' });
	const WATCH: VehicleWatchRecord[] = [
		{ vehicleId: V_STOLEN, plate: 'MH01XX•••7', earmarkState: 'flagged', earmarkReason: 'Stolen vehicle, FIR 4417/2026, Azad Maidan PS', lawfulBasis: 'stolen_vehicle_fir', retentionUntil: iso(-29 * 86_400_000), lastSighting: sight(72.8608, 19.0022, 100 * MIN, 95, 52) },
		{ vehicleId: V_PURSUED, plate: 'MH47EM•••1', earmarkState: 'flagged', earmarkReason: 'Stolen vehicle, FIR 4401/2026, Azad Maidan PS', lawfulBasis: 'stolen_vehicle_fir', retentionUntil: iso(-30 * 86_400_000), lastSighting: sight(72.8626, 19.0035, 12 * MIN, 95, 45) },
		{ vehicleId: V_BLOCKED, plate: 'MH05CD•••8', earmarkState: 'flagged', earmarkReason: 'Stolen vehicle, FIR 81/2026, Dadar PS', lawfulBasis: 'stolen_vehicle_fir', retentionUntil: iso(-20 * 86_400_000), lastSighting: sight(72.96, 19.1332, 25 * MIN, 64, 180) },
		{ vehicleId: V_WARRANT, plate: 'MH01KL•••7', earmarkState: 'watch', earmarkReason: 'Court warrant watch, case 12/2026', lawfulBasis: 'court_warrant', retentionUntil: iso(-12 * 86_400_000), lastSighting: null },
		{ vehicleId: V_STOLEN_PENAL, plate: 'MH07GH•••2', earmarkState: 'flagged', earmarkReason: 'Stolen vehicle, FIR 90/2026, Kurla PS', lawfulBasis: 'stolen_vehicle_fir', retentionUntil: iso(-25 * 86_400_000), lastSighting: null },
	];

	const rec = (
		id: string,
		vehicleId: string,
		plate: string,
		rule: string,
		text: string,
		msAgo: number,
		ev: Record<string, unknown>,
		status: 'pending' | 'approved' = 'pending',
	): EnforcementRecommendation => ({
		recommendationId: id,
		sightingId: `${id}-s`,
		vehicleId,
		plate,
		ruleId: rule,
		recommendation: text,
		evidence: { source: 'emulated_anpr', ...ev },
		status,
		decidedBy: status === 'approved' ? 'Sandbox Officer' : null,
		decidedAt: status === 'approved' ? iso(msAgo - 60_000) : null,
		auditTail: [],
		createdAt: iso(msAgo),
		pursuit: null,
	});

	const PENDING: EnforcementRecommendation[] = [
		rec(rid(1), V_STOLEN, 'MH01XX•••7', 'R_STOLEN_SIGHTING', 'Stolen vehicle MH01XX•••7 sighted at EM-CAM-02 (FIR 4417/2026)', 112 * MIN, { camera_id: 'EM-CAM-02', road_name: 'Marine Drive (Netaji Subhash Chandra Bose Road)', speed_kmh: 110, fir_ref: '4417/2026' }),
		rec(rid(2), V_STOLEN, 'MH01XX•••7', 'R_STOLEN_SIGHTING', 'Stolen vehicle MH01XX•••7 sighted at EM-J05 (FIR 4417/2026)', 106 * MIN, { camera_id: 'EM-J05', road_name: 'Annie Besant Road', speed_kmh: 102, fir_ref: '4417/2026' }),
		rec(rid(3), V_STOLEN, 'MH01XX•••7', 'R_STOLEN_SIGHTING', 'Stolen vehicle MH01XX•••7 sighted at EM-CAM-03 (FIR 4417/2026)', 100 * MIN, { camera_id: 'EM-CAM-03', road_name: 'Dr Ambedkar Road (Parel flyover)', speed_kmh: 95, fir_ref: '4417/2026' }),
		rec(rid(4), V_STOLEN_PENAL, 'MH07GH•••2', 'R_SPD_SEGMENT', 'MH07GH•••2 read at 71 km/h in a 40 km/h segment', 55 * MIN, { camera_id: 'EM-CAM-01', road_name: 'P D Mello Road', speed_kmh: 71, limit_kmh: 40, t: iso(56 * MIN) }),
		rec(rid(5), V_WARRANT, 'MH01KL•••7', 'R_SPD_SEGMENT', 'MH01KL•••7 read at 78 km/h in a 40 km/h segment', 40 * MIN, { camera_id: 'EM-CAM-04', road_name: 'Western Express Highway', speed_kmh: 78, limit_kmh: 40, t: iso(41 * MIN) }),
	];
	const APPROVED: EnforcementRecommendation[] = [
		{ ...rec(rid(6), V_PURSUED, 'MH47EM•••1', 'R_STOLEN_SIGHTING', 'Stolen vehicle MH47EM•••1 sighted at EM-CAM-03 (FIR 4401/2026)', 6 * MIN, { camera_id: 'EM-CAM-03', road_name: 'Dr Ambedkar Road (Parel flyover)' }, 'approved'), pursuit: { eventId: P_EVENT, status: 'active' } },
		rec(rid(7), V_STOLEN_PENAL, 'MH07GH•••2', 'R_SPD_SEGMENT', 'MH07GH•••2 read at 68 km/h in a 40 km/h segment', 5 * 86_400_000, { camera_id: 'EM-CAM-01', road_name: 'Annie Besant Road' }, 'approved'),
	];

	const phase = (msAgo: number) => [{ label: 'pursuit', startTime: iso(msAgo), endTime: iso(msAgo - 45 * MIN), closurePolicy: null, state: 'active' as const }];
	const EVENTS: CorridorEvent[] = [
		{
			eventId: P_EVENT,
			name: 'Pursuit of MH47EM•••1',
			eventKind: 'vehicle_pursuit',
			protectionClass: 'none',
			crowdClass: 'LOW',
			state: 'active',
			status: 'active',
			routeSegmentIds: [1049],
			phases: phase(3 * MIN),
			currentPhase: 'pursuit',
			band: null,
			windowStart: iso(3 * MIN),
			windowEnd: iso(-42 * MIN),
			description: `Opened by Sandbox Officer from the watchlist console (recommendation ${rid(6)}).`,
			source: 'live-events-api',
			metadata: { vehicleId: V_PURSUED, recommendationId: rid(6), source: null, mode: null, runId: null, useCaseId: null, isReplay: null },
			emulated: false,
		},
		{
			eventId: MV_EVENT,
			name: 'Z protected movement · P D Mello Road to the airport',
			eventKind: 'protected_movement',
			protectionClass: 'Z',
			crowdClass: 'MODERATE',
			state: 'active',
			status: 'active',
			routeSegmentIds: [1013, 1049, 1052],
			phases: phase(8 * MIN),
			currentPhase: 'transit',
			band: 'GREEN',
			windowStart: iso(8 * MIN),
			windowEnd: iso(-11 * MIN),
			description: null,
			source: 'live-events-api',
			movementId: MOVEMENT,
			metadata: { vehicleId: null, recommendationId: null, source: 'event-emulator', mode: 'use_case', runId: null, useCaseId: null, isReplay: null },
			emulated: true,
		},
	];

	const ESCORTS: EscortLane[] = [
		{
			movementId: MOVEMENT,
			eventId: MV_EVENT,
			status: 'escorting',
			alive: true,
			officer: null,
			gpsMode: 'emulated',
			trafficSimulated: true,
			timeoutSec: 90,
			outcomes: [],
			proposal: {
				movementId: MOVEMENT,
				eventId: MV_EVENT,
				approvalId: 'apr-harness-1',
				action: 'hold_position',
				kind: 'hold',
				summary: 'Hold the convoy short of Hindmata until Station Road clears',
				reason: null,
				trigger: 'incident_detected',
				tier: 'decider',
				confidence: 0.81,
				createdAt: NOW - 43_000,
				expiresAt: NOW + 47_000,
				timeoutSec: 90,
				segmentIds: [1052],
				peakCongestion: 0.86,
				simulated: true,
				proposed: {
					routeSource: null,
					segmentIds: [],
					tailSegmentIds: [],
					roadNames: [],
					viaSegmentIds: [],
					viaRoadNames: [],
					remainingM: null,
					newRemainingM: null,
					avoids: [],
					longDetour: false,
					closureType: null,
					closuresNew: [],
					closuresLifted: [],
					holdSegmentIds: [1052],
					maxHoldSec: 180,
					replan: false,
				},
			},
		},
	];

	const DISPATCHES: DispatchRecord[] = [
		{
			dispatchId: DSP,
			eventId: MV_EVENT,
			agency: 'ambulance',
			agencyLabel: '108 Ambulance',
			unitId: '108-EM-14',
			waypointJunction: 11,
			status: 'requested',
			requestedBy: '108-driver',
			decidedBy: null,
			decisionNote: null,
			approvedAt: null,
			createdAt: iso(4 * MIN),
			updatedAt: iso(4 * MIN),
			audit: [],
		},
	];

	const PLAN: InterceptionPlan = {
		eventId: P_EVENT,
		vehicleId: V_PURSUED,
		latestSighting: { sightingId: 's-harness-1', plate: 'MH47EM•••1', t: iso(12 * MIN), position: [72.8626, 19.0035], speedKmh: 95, heading: 45, source: 'emulated_anpr', cameraId: 'EM-CAM-03' },
		seedSegmentId: 1049,
		maxCostSec: 600,
		chokes: [
			{ rank: 1, junctionId: 11, junctionType: 'signal', signalControl: true, position: [72.8634, 19.0043], graphCostSec: 70, chokeWeight: 1, score: 0.82, name: 'Hindmata', downstream: true, likelyPassed: false },
			{ rank: 2, junctionId: 12, junctionType: 'signal', signalControl: true, position: [72.8653, 19.0084], graphCostSec: 160, chokeWeight: 1, score: 0.64, name: 'Dadar TT Circle', downstream: true, likelyPassed: false },
			{ rank: 3, junctionId: 13, junctionType: 'roundabout', signalControl: false, position: [72.8574, 19.0028], graphCostSec: 40, chokeWeight: 0.6, score: 0.31, name: 'King’s Circle', downstream: false, likelyPassed: true },
		],
		note: null,
		sightingAgeSec: 720,
		stale: true,
		staleAfterSec: 600,
		direction: { basis: 'heading', towardsJunctionIds: [11, 12], segmentBearingDeg: 48, positionAlongSegment: 0.7, seedSegmentOneway: false, againstOneway: false, onwardSegmentIds: [1052] },
	};

	// ── seed and restore ───────────────────────────────────────────────────

	const params = $derived($page.url.searchParams);
	let rightTab = $state<'inbox' | 'movement' | 'inspector'>('inbox');
	let inboxOpen = $state<string | null>(null);
	let ready = $state(false);

	const KEY_OF: Record<string, string> = {
		stolen: `stolen-sighting:${V_STOLEN}`,
		pursuit: `pursuit:${V_BLOCKED}`,
		echallan: `echallan:${rid(4)}`,
		corridor: `corridor-request:${DSP}`,
	};

	onMount(() => {
		const saved = {
			recommendations: ops.recommendations,
			approvedRecommendations: ops.approvedRecommendations,
			watchlist: ops.watchlist,
			events: ops.events,
			escorts: ops.escorts,
			dispatches: ops.dispatches,
			segmentLines: ops.segmentLines,
			junctions: ops.junctions,
			interception: ops.interception,
			trafficFeed: ops.trafficFeed,
			officer: ops.dutyOfficer,
		};
		// name the officer FIRST: a change of officer presence republishes the store's board and plan
		if (params.get('officer') === '1') ops.setDutyOfficer('Sandbox Officer');
		ops.recommendations = PENDING;
		ops.approvedRecommendations = APPROVED;
		ops.watchlist = WATCH;
		ops.escorts = ESCORTS;
		ops.dispatches = DISPATCHES;
		ops.segmentLines = SEGMENTS;
		ops.junctions = JUNCTIONS;
		ops.trafficFeed = { label: 'simulated', real: 0, synthetic: 49, segments: 49, dataAgeSec: 30, checkedAt: NOW };
		seedBoard();
		const open = params.get('open');
		if (open === 'escort') rightTab = 'movement';
		else if (open && KEY_OF[open]) inboxOpen = KEY_OF[open];
		if (params.get('section') === 'pursuit') rightTab = 'inspector';
		ready = true;
		return () => {
			ops.recommendations = saved.recommendations;
			ops.approvedRecommendations = saved.approvedRecommendations;
			ops.watchlist = saved.watchlist;
			ops.events = saved.events;
			ops.escorts = saved.escorts;
			ops.dispatches = saved.dispatches;
			ops.segmentLines = saved.segmentLines;
			ops.junctions = saved.junctions;
			ops.interception = saved.interception;
			ops.trafficFeed = saved.trafficFeed;
			ops.setDutyOfficer(saved.officer);
			commandBar.live = null;
			commandBar.officer = null;
		};
	});

	/** The board and the plan (the store republishes both when the officer's presence changes). */
	function seedBoard() {
		ops.events = EVENTS;
		ops.interception = params.get('against') === '1' && PLAN.direction ? { ...PLAN, direction: { ...PLAN.direction, againstOneway: true } } : PLAN;
	}

	// naming or clearing the officer here republishes the store's (empty) board: seed it again
	let lastOfficerOn: boolean | null = null;
	$effect(() => {
		const on = ops.officerOn;
		if (!ready) return;
		if (lastOfficerOn !== null && lastOfficerOn !== on) untrack(() => seedBoard());
		lastOfficerOn = on;
	});

	// the navbar: the officer control and the LiveStrip, as a rebuilt page supplies them
	$effect(() => {
		if (!ready) return;
		commandBar.officer = { value: ops.dutyOfficer, fromSession: ops.dutyOfficerFromSession, set: (v: string) => ops.setDutyOfficer(v) };
		commandBar.live = liveStripFeed({ route: '/' });
		commandBar.inboxCount = units.length;
		commandBar.inboxIntent = units.length ? 'warning' : 'none';
	});

	const units = $derived(ready ? decisionUnits() : []);
	const escortUnit = $derived(units.find((u) => u.kind === 'escort-proposal') ?? null);
	const gallery = $derived(units.filter((u) => u.kind === 'pursuit' || u.kind === 'echallan' || u.kind === 'corridor-request'));
	const tabs = $derived([
		{ id: 'inbox' as const, label: 'Inbox', count: units.length, countIntent: 'warning' as const, icon: ACTION_ICON.inbox },
		{ id: 'movement' as const, label: 'Movement', icon: eventKindIcon('protected_movement') },
		{ id: 'inspector' as const, label: 'Inspector', icon: 'properties' as const },
	]);
</script>

<svelte:head><title>Decisions harness · Sajag</title></svelte:head>

{#snippet convoyStandIn()}
	<div class="convoy-stub"><Tag icon={eventKindIcon('protected_movement')}>Movement card (UI-S6A) holds the escort proposal</Tag></div>
{/snippet}

<div class="harness" data-testid="decisions-harness">
	<section class="col queue">
		<header class="col-head"><h2>Decisions</h2><span class="sub">/ops column · fixture data</span></header>
		<div class="scroll">
			{#if ready}<DecisionQueue top={convoyStandIn} />{/if}
		</div>
	</section>

	<section class="col gallery">
		<header class="col-head"><h2>Proposal cards</h2><span class="sub">one anatomy, every kind</span></header>
		<div class="scroll">
			<Callout icon="info-sign">Fictional fixture data, masked marks only. The ops store is not started (no poller); only the Decisions column reads the rejected list once.</Callout>
			<div class="cards">
				{#each gallery as u (`${u.kind}:${u.id}`)}
					<div class="card-frame"><ProposalCard unit={u} sticky={false} /></div>
				{/each}
			</div>
		</div>
	</section>

	<aside class="col dock">
		<div class="dock-tabs"><Tabs items={tabs} bind:value={rightTab} height={39} label="Right dock" /></div>
		<div class="scroll" data-right-panel={rightTab}>
			{#if !ready}
				<span></span>
			{:else if rightTab === 'inbox'}
				<Inbox route="/" bind:open={inboxOpen} />
			{:else if rightTab === 'movement'}
				<div class="movement">
					<div class="mv-head">
						<div>
							<div class="mv-title">Z protected movement · P D Mello Road to the airport</div>
							<div class="mv-sub">Protected movement · class Z · escorting</div>
						</div>
					</div>
					{#if escortUnit}<ProposalCard unit={escortUnit} />{/if}
				</div>
			{:else}
				<div class="inspector">
					<div class="insp-head">
						<div class="insp-title">MH47EM•••1</div>
						<div class="insp-sub">Vehicle · car · watchlist (stolen, FIR)</div>
					</div>
					<PursuitPlan vehicleId={V_PURSUED} />
				</div>
			{/if}
		</div>
	</aside>
</div>

<style>
	.harness {
		display: grid;
		grid-template-columns: minmax(400px, 432px) minmax(0, 1fr) var(--v-ws-right);
		height: 100%;
		min-height: 0;
		background: var(--v-canvas);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	@media (max-width: 1679px) {
		.harness {
			grid-template-columns: minmax(380px, 432px) minmax(0, 1fr) var(--v-ws-right-md);
		}
	}

	@media (max-width: 1439px) {
		.harness {
			grid-template-columns: minmax(360px, 400px) minmax(0, 1fr) var(--v-ws-right-sm);
		}
	}

	.col {
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		background: var(--v-surface-1);
	}

	.queue {
		border-right: 1px solid var(--v-line-2);
	}

	.dock {
		border-left: 1px solid var(--v-line-2);
	}

	.gallery {
		background: var(--v-canvas);
	}

	.col-head {
		display: flex;
		align-items: center;
		gap: 8px;
		height: 40px;
		padding: 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		flex: 0 0 auto;
		background: var(--v-surface-1);
	}

	.col-head h2 {
		margin: 0;
		font-size: var(--v-text-base);
		font-weight: 600;
	}

	.col-head .sub {
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.scroll {
		flex: 1 1 auto;
		min-height: 0;
		overflow: auto;
	}

	.gallery .scroll {
		padding: 16px;
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
		gap: 16px;
		margin-top: 16px;
		align-items: start;
	}

	.card-frame {
		border-radius: var(--v-radius-panel);
		overflow: hidden;
		box-shadow: inset 0 0 0 1px var(--v-line-2);
		background: var(--v-surface-1);
	}

	.dock-tabs {
		padding: 0 12px;
		border-bottom: 1px solid var(--v-line-2);
		flex: 0 0 auto;
	}

	.convoy-stub {
		padding: 8px 12px;
	}

	.movement,
	.inspector {
		display: flex;
		flex-direction: column;
	}

	.mv-head,
	.insp-head {
		display: flex;
		gap: 12px;
		padding: 12px 16px;
		border-bottom: 1px solid var(--v-line-1);
	}

	.mv-title,
	.insp-title {
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: 20px;
	}

	.mv-sub,
	.insp-sub {
		margin-top: 4px;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}
</style>
