<script lang="ts">
	/**
	 * /plan — Plan a movement (V3-SPEC §6.6; colleague review: "the convoy/corridor planner on its own page, a
	 * 'Where to?' flow"). A calm sheet beside the real map, one step at a time, one primary action per step:
	 *
	 *   1 Where to   From / To with a place search (the planner's own places), the protection class as ride-type
	 *                cards (each with its lane floor and advance closure, from the protocol table), the departure
	 *                (in 30 min — the planner's default — in an hour, or at an IST time), an optional test or
	 *                rehearsal label → Find routes
	 *   2 Routes     the plan's candidates, best first, each with only the figures the plan reports; the plan's
	 *                state in words (ready, needs a waiver, held, no route); the traffic's provenance (simulated
	 *                says so); choosing a card previews it on the map — the escort runs the RECOMMENDED route
	 *   3 Launch     the lane-floor waiver (conditional plans), "Who is launching?" (a NAMED officer), Start
	 *                escort — locked with the reason until both are given; a refusal shows the brain's own words
	 *   4 Live       escort running (or adopted from the board), its open proposal → Decide, Follow on the map,
	 *                Open the operation, Stop (officer); ended → Clear (officer) and its outcome
	 *
	 * The planner is the corridor's, imported unchanged: the plan document and its launch gate
	 * (corridor/plan.ts), the ONE escort lifecycle the Analyst workspace's Plan tab also drives
	 * (corridor/escort-state.svelte.ts: createMovement + planMovement, launchEscort, stopEscort, clearMovement —
	 * "one POST per click: the store guards its own calls"), the ops store (the officer, plate masking, escort
	 * lanes and proposals, the road geometry). This page adds its own in-flight guard on top, so a double click
	 * sends ONE request. Every free text the brain wrote goes through ops.text (masked without a named officer).
	 */
	import { onDestroy, onMount } from 'svelte';
	import type { Component } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import OperatorSignIn from '$lib/shell/OperatorSignIn.svelte';
	import { registerProviders } from '$lib/workspace/providers';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { decisionUnits, type Unit } from '$lib/decisions/units';
	import { PLAN_POIS as POIS_EN, escortLifecycle } from '$lib/corridor/escort-state.svelte';
	import { landmarkName } from '$lib/city';
	import { cityName } from '$lib/city';
	import { addsText, candidateAdds, launchGate, planViolations, routeCandidates } from '$lib/corridor/plan';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.wall';
	import { provideUiLang } from '$lib/ui/lang';
	import { fmtTime, istTimeToMs, parseIstTime } from '$lib/ui/format/format';
	import '$lib/v3/packs.v3';
	import Glyph from '../Glyph.svelte';
	import MapThumb from '../map/MapThumb.svelte';
	import { v3Bar } from '../shell/v3-bar.svelte';
	import { V3_NAV } from '../shell/nav';
	import { decisionVM, roadLines } from '../home/view';
	import {
		PROTECTION_CLASSES,
		STEPS,
		departureMs,
		eventHref,
		failKind,
		failLeadKey,
		isLaterIstDay,
		planEventId,
		planOverlay,
		previewRouteId,
		proposalHref,
		routeLine,
		stateKey,
		stateTone,
		stepOf,
		trafficTagKey,
		waiverLines,
		type ClassId,
		type DepartureChoice,
	} from './model';
	import './packs.plan';
	import PlaceField from './PlaceField.svelte';
	import PlanOfficer from './PlanOfficer.svelte';
	import RouteCard from './RouteCard.svelte';
	import VehicleShot from '../media/VehicleShot.svelte';
	import Cover from '../media/Cover.svelte';
	import { convoyShot, keyArt } from '../media/art';
	import { photoForText, photoNear } from '../media/photos';
	import '../media/packs.media';

	provideUiLang(() => ops.lang);
	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	/** The planner's places in the page's language (landmarks.json spellings); `alt` keeps the English name searchable. */
	const PLAN_POIS = $derived(POIS_EN.map((p) => ({ ...p, name: landmarkName(p.id, lang), alt: p.name })));
	// V3-P7: the destination as a place — a credited reference photo when one is on file (never the place now)
	const planHour = Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Asia/Kolkata' }).format(Date.now()));

	const lc = escortLifecycle;

	// ── the clock (countdowns, "leaves at") ────────────────────────────────
	let now = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(id);
	});

	// ── step 1: the trip ───────────────────────────────────────────────────
	let originIdx = $state(lc.originIdx);
	let destIdx = $state(lc.destIdx);
	let vvipClass = $state<ClassId>(lc.vvipClass);
	let when = $state<DepartureChoice>('in30');
	let atText = $state('');
	let atValue = $state<string | null>(null);
	let atBad = $state(false);
	let labelOpen = $state(false);
	let label = $state('');

	/** The officer is changing the trip of a plan that is already in. */
	let editing = $state(false);
	/** The officer chose "Continue to launch". */
	let confirming = $state(false);
	/** The candidate previewed on the map (null: the recommended one). */
	let picked = $state<string | null>(null);
	/** Which action the lifecycle's last error belongs to (its failure shows only in that step). */
	let lastAction = $state<'plan' | 'launch' | 'stop' | null>(null);

	// this page's own in-flight guards (on top of the lifecycle's): one request per press
	let planInFlight = false;
	let launchInFlight = false;

	const depMs = $derived(departureMs(when, atValue, now, (hhmm, anchor) => istTimeToMs(hhmm, anchor)));
	const leaves = $derived(
		Number.isFinite(depMs) ? (isLaterIstDay(depMs, now) ? L('v3p_leaves_tomorrow', fmtTime(depMs)) : L('v3p_leaves', fmtTime(depMs))) : null,
	);
	const findLock = $derived(
		lc.escortRunning ? L('v3p_find_locked_running') : originIdx === destIdx ? L('v3p_find_locked_same') : !Number.isFinite(depMs) ? L('v3p_find_locked_time') : null,
	);

	function commitAt() {
		const v = atText.trim();
		const norm = v ? parseIstTime(v) : null;
		atBad = !!v && !norm;
		atValue = norm;
		if (norm) atText = norm;
	}

	function swap() {
		const a = originIdx;
		originIdx = destIdx;
		destIdx = a;
	}

	async function findRoutes() {
		if (planInFlight || findLock || lc.phase === 'planning') return;
		planInFlight = true;
		editing = false;
		confirming = false;
		picked = null;
		lastAction = 'plan';
		try {
			await escortLifecycle.plan({ originIdx, destIdx, vvipClass, departureIso: new Date(depMs).toISOString(), label });
		} finally {
			planInFlight = false;
		}
	}

	// ── the plan (the corridor's own state machine) ────────────────────────
	const doc = $derived(lc.doc);
	const candidates = $derived(routeCandidates(doc));
	let waiverAccepted = $state(false);
	let waiverFor = $state<string | null>(null);
	$effect(() => {
		// a new plan document resets its waiver (CONDITIONAL capability 15)
		const id = lc.doc?.movement_id ?? null;
		if (waiverFor !== id) {
			waiverFor = id;
			waiverAccepted = false;
		}
	});
	const gate = $derived(
		launchGate(doc, { waiverAccepted, officerNamed: ops.officerOn }, {
			waiverNeeded: L('v3p_lock_waiver'),
			holdLocked: L('v3p_lock_hold'),
			officerNeeded: L('v3p_lock_officer'),
			noPlan: L('v3p_lock_none'),
		}),
	);
	const step = $derived(stepOf({ phase: lc.phase, hasDoc: !!doc, offered: gate.escortOffered, confirming, editing }));
	const stepIdx = $derived(STEPS.indexOf(step));
	const recommendedId = $derived(lc.recommendedId);
	// launch and live show the route that runs; Routes previews the officer's pick
	const previewId = $derived(previewRouteId(candidates, step === 'routes' ? picked : null, recommendedId));
	const waiver = $derived(waiverLines(planViolations(doc), (id) => ops.roadName(id), (id) => L('v3p_seg', id)));
	const tripFrom = $derived(PLAN_POIS[step === 'where' ? originIdx : lc.originIdx] ?? null);
	const tripTo = $derived(PLAN_POIS[step === 'where' ? destIdx : lc.destIdx] ?? null);
	const tripClass = $derived(step === 'where' ? vvipClass : lc.vvipClass);
	const tripLeaves = $derived(lc.plannedDepartureMs != null ? fmtTime(lc.plannedDepartureMs) : null);
	const trafficKey = $derived(trafficTagKey(ops.trafficFeed?.label ?? null));
	const holdAt = $derived(fmtTime(lc.plannedDepartureMs ?? now + 15 * 60_000));

	function addsFor(i: number): string | null {
		if (i === 0) return null;
		const roads = candidateAdds(candidates[i], candidates[0]);
		return roads.length ? L('v3p_adds', addsText(roads)) : L('v3p_adds_none');
	}

	// ── step 3: launch ─────────────────────────────────────────────────────
	async function launch() {
		if (launchInFlight || gate.launchLocked || lc.phase === 'starting' || lc.escortRunning) return;
		launchInFlight = true;
		lastAction = 'launch';
		try {
			await escortLifecycle.launch();
		} finally {
			launchInFlight = false;
		}
	}

	/** A failure, worded: the lead says who answered (or that nothing did); the text is the server's, verbatim. */
	const planFail = $derived.by(() => {
		if (lastAction !== 'plan' || step !== 'where' || !lc.error) return null;
		const k = failKind(lc.error) ?? 'refused';
		return { kind: k, lead: L(failLeadKey(k, 'plan')), text: ops.text(lc.error) };
	});
	const launchFail = $derived.by(() => {
		if (lastAction !== 'launch' || step !== 'launch') return null;
		const raw = lc.launchRefusal;
		if (!raw) return lc.error ? { kind: 'note' as const, lead: null, text: ops.text(lc.error) } : null;
		const k = failKind(raw) ?? 'refused';
		return { kind: k, lead: L(failLeadKey(k, 'launch')), text: ops.text(raw) };
	});

	// a failure is the step's news: it scrolls into view where it appears (the sheet may be scrolled to its footer)
	let failBox = $state<HTMLElement | null>(null);
	$effect(() => {
		if ((planFail || launchFail) && failBox) failBox.scrollIntoView({ block: 'nearest', behavior: 'instant' as ScrollBehavior });
	});

	// ── step 4: live ───────────────────────────────────────────────────────
	const lane = $derived(lc.movementId ? (ops.escorts.find((l) => l.movementId === lc.movementId) ?? null) : null);
	const adopted = $derived(step === 'live' && !doc);
	const liveEvent = $derived(lc.movementId ? (ops.events.find((e) => e.movementId === lc.movementId) ?? null) : null);
	const eventId = $derived(planEventId(doc, ops.events, lc.movementId) ?? lane?.eventId ?? null);
	const proposal = $derived(lc.escortRunning ? ops.escortProposalFor(lc.movementId, lc.followedDoc) : null);
	const proposalLeft = $derived(proposal?.expiresAt != null ? Math.max(0, Math.round((proposal.expiresAt - now) / 1000)) : null);
	const ended = $derived(lc.phase === 'ended');
	const endKey = $derived(
		lc.endedStatus === 'completed' ? 'v3p_end_completed' : lc.endedStatus === 'stopped' ? 'v3p_end_stopped' : lc.endedStatus === 'failed' ? 'v3p_end_failed' : 'v3p_end_unknown',
	);
	const mapHref = V3_NAV.find((n) => n.id === 'map')?.href ?? '/gods-eye';
	const stopFail = $derived(lastAction === 'stop' && step === 'live' && lc.error ? ops.text(lc.error) : null);

	async function stop() {
		lastAction = 'stop';
		await lc.stop();
	}

	function startOver() {
		escortLifecycle.reset();
		editing = false;
		confirming = false;
		picked = null;
		lastAction = null;
	}

	// the lifecycle closes when the brain reports the escort ended, and adopts one this console did not launch
	$effect(() => {
		void lc.phase;
		lc.sync();
	});

	// ── the map ────────────────────────────────────────────────────────────
	const overlay = $derived.by(() => {
		if (adopted && liveEvent?.routeSegmentIds?.length) {
			const lines = routeLine({ route_id: 'live', segment_ids: liveEvent.routeSegmentIds }, ops.segmentLines);
			return { lines: lines.map((coords) => ({ coords, style: 'route' as const })), points: [] };
		}
		return planOverlay({
			from: tripFrom,
			to: tripTo,
			candidates: step === 'where' ? [] : candidates,
			previewId,
			segments: ops.segmentLines,
		});
	});
	const roads = $derived(roadLines());
	const mapAlt = $derived(
		step !== 'where' && candidates.length
			? L('v3p_map_alt_routes', candidates.length, tripFrom?.name ?? '—', tripTo?.name ?? '—')
			: L('v3p_map_alt', tripFrom?.name ?? '—', tripTo?.name ?? '—'),
	);

	// ── the decisions (the rail's badge and the bell, as on every V3 page) ─
	const units = $derived.by((): Unit[] => {
		void cityRegistry.version;
		return decisionUnits(ops);
	});

	// ── the shell (the v2 contract + the V3 bar) ───────────────────────────
	let Omnibar = $state<Component | null>(null);
	let sessionWaitOver = $state(false);
	onMount(() => {
		registerProviders();
		ops.start();
		cityRegistry.start();
		const wait = setTimeout(() => (sessionWaitOver = true), 2500);
		void import('$lib/workspace/components/omnibar/Omnibar.svelte').then((m) => (Omnibar = m.default as unknown as Component));
		return () => clearTimeout(wait);
	});
	onDestroy(() => {
		// a plan that never launched does not outlive the page; a running escort stays followed
		if (!escortLifecycle.escortRunning) escortLifecycle.reset();
		cityRegistry.stop();
		ops.stop();
		if (typeof window !== 'undefined') delete (window as unknown as Record<string, unknown>).__V3_PLAN__;
	});

	$effect(() => {
		commandBar.lang = ops.lang;
		commandBar.onLangChange = (l: string) => (ops.lang = l);
		commandBar.onShare = null;
		commandBar.onSearch = (q?: string) => workspace.openOmnibar(q);
		commandBar.onInbox = null;
	});
	$effect(() => {
		commandBar.officer = { value: ops.dutyOfficer, fromSession: ops.dutyOfficerFromSession, set: (v: string) => ops.setDutyOfficer(v) };
	});
	$effect(() => {
		const f = ops.trafficFeed;
		commandBar.exercise =
			f && (f.label === 'simulated' || f.label === 'mixed')
				? {
						label: f.label,
						text: f.label === 'simulated' ? L('wall_exercise_simulated', f.segments) : L('wall_exercise_mixed', Math.round((100 * f.synthetic) / Math.max(1, f.real + f.synthetic))),
					}
				: null;
	});
	$effect(() => {
		commandBar.inboxCount = units.length;
		commandBar.inboxIntent = units.length ? 'warning' : 'none';
	});
	$effect(() => {
		v3Bar.title = L('v3p_title');
		v3Bar.sub = `${cityName(lang)} · ${fmtTime(now)} IST`;
		v3Bar.active = 'plan';
	});
	const mountedAt = Date.now();
	const firstRound = $derived(
		(ops.boardUpdated > 0 && ops.recommendationsUpdated > 0 && ops.dispatchesUpdated > 0 && ops.escortsDeployed !== null && cityRegistry.status !== 'idle') ||
			now - mountedAt > 10_000,
	);
	$effect(() => {
		v3Bar.decisions = firstRound
			? units.map((u) => {
					const vm = decisionVM(u, lang, now);
					return { key: vm.key, title: vm.maskedTitle, href: vm.href, emulated: vm.emulated };
				})
			: null;
	});

	// ── the test hook (the smoke reads the page's own state) ───────────────
	$effect(() => {
		if (typeof window === 'undefined') return;
		(window as unknown as Record<string, unknown>).__V3_PLAN__ = {
			step,
			phase: lc.phase,
			movementId: lc.movementId,
			candidates: candidates.map((c) => c.route_id),
			recommended: recommendedId,
			preview: previewId,
			launchLocked: gate.launchLocked,
			lockReason: gate.launchLockReason,
			officerOn: ops.officerOn,
			error: lc.error,
			refusal: lc.launchRefusal,
		};
	});

	const STEP_KEY: Record<string, string> = { where: 'v3p_step_where', routes: 'v3p_step_routes', launch: 'v3p_step_launch', live: 'v3p_step_live' };
</script>

<svelte:head>
	<title>{L('v3_nav_plan')} · Sajag</title>
</svelte:head>

{#if ops.signInRequired}
	<div class="signin" data-testid="cockpit-signin-required">
		<div class="signin-card">
			<h2>{tOps(lang, 'opsSigninTitle')}</h2>
			<p>{tOps(lang, 'cockpitSigninBody')}</p>
			<OperatorSignIn lang={ops.lang} inline />
		</div>
	</div>
{:else}
	<div class="plan" data-v3="plan" data-step={step} data-ready={sessionWaitOver || ops.boardUpdated > 0 ? 'true' : 'false'}>
		<section class="sheet" aria-labelledby="v3p-heading">
			<ol class="steps" aria-label={L('v3p_steps')}>
				{#each STEPS as s, i (s)}
					<li class={['st', i < stepIdx && 'done', i === stepIdx && 'now']} aria-current={i === stepIdx ? 'step' : undefined} data-step={s}>
						<span class="st-n" aria-hidden="true">{#if i < stepIdx}<Glyph name="check" size={14} />{:else}{i + 1}{/if}</span>
						<span class="st-l">{L(STEP_KEY[s])}</span>
					</li>
				{/each}
			</ol>

			<div class="body">
				{#if step === 'where'}
					<!-- ── 1. where to ── -->
					<h2 class="h" id="v3p-heading">{L('v3p_where_heading')}</h2>
					<p class="lead">{L('v3p_where_lead')}</p>

					<div class="pair">
						<PlaceField id="v3p-from" testid="v3-plan-from" mark="from" label={L('v3p_from')} placeholder={L('v3p_from_ph')} bind:value={originIdx} places={PLAN_POIS} {lang} disabled={lc.phase === 'planning'} />
						<PlaceField id="v3p-to" testid="v3-plan-to" mark="to" label={L('v3p_to')} placeholder={L('v3p_to_ph')} bind:value={destIdx} places={PLAN_POIS} {lang} disabled={lc.phase === 'planning'} />
						<button type="button" class="swap" aria-label={L('v3p_swap')} title={L('v3p_swap')} data-testid="v3-plan-swap" onclick={swap} disabled={lc.phase === 'planning'}>
							<Glyph name="shuffle" size={18} />
						</button>
					</div>
					{#if originIdx === destIdx}<p class="warn-line" role="status">{L('v3p_same')}</p>{/if}
					{#if destIdx != null && PLAN_POIS[destIdx]}
						{@const poi = PLAN_POIS[destIdx]}
						{@const destPhoto = photoNear(poi.coord[0], poi.coord[1], 900, planHour) ?? photoForText(poi.alt, planHour)}
						{#if destPhoto}
							<div class="dest" data-testid="v3-plan-dest-photo" data-photo={destPhoto.slug}>
								<Cover art={keyArt('advisory')} photo={destPhoto} alt="" {lang} compact sizes="480px" />
								<span class="dest-name">{poi.name}{#if destPhoto.title !== poi.name && destPhoto.title !== poi.alt}<small>{destPhoto.title}</small>{/if}</span>
							</div>
						{/if}
					{/if}

					<fieldset class="group">
						<legend class="gh">{L('v3p_class_heading')}</legend>
						<div class="classes" role="radiogroup" aria-label={L('v3p_class_heading')}>
							{#each PROTECTION_CLASSES as c (c.id)}
								<button
									type="button"
									role="radio"
									class={['cls', vvipClass === c.id && 'is-selected']}
									aria-checked={vvipClass === c.id}
									data-testid="v3-plan-class"
									data-class={c.id}
									onclick={() => (vvipClass = c.id)}
								>
									<VehicleShot cls={convoyShot(c.id)} {lang} width={150} class="cls-shot" />
									<span class="cls-id">{c.id}</span>
									<span class="cls-m">{L('v3p_class_lanes', c.minLanes)}</span>
									<span class="cls-m">{c.advanceClosureSec != null ? L('v3p_class_closure', Math.round(c.advanceClosureSec / 60)) : L('v3p_class_closure_none')}</span>
								</button>
							{/each}
						</div>
						<p class="fine">{L('v3p_class_note')}</p>
					</fieldset>

					<fieldset class="group">
						<legend class="gh">{L('v3p_when_heading')}</legend>
						<div class="chips" role="radiogroup" aria-label={L('v3p_when_heading')}>
							{#each [['in30', 'v3p_when_in30'], ['in60', 'v3p_when_in60'], ['at', 'v3p_when_at']] as [id, key] (id)}
								<button
									type="button"
									role="radio"
									class={['chip', when === id && 'is-selected']}
									aria-checked={when === id}
									data-testid="v3-plan-when"
									data-when={id}
									onclick={() => (when = id as DepartureChoice)}>{L(key)}</button
								>
							{/each}
						</div>
						{#if when === 'at'}
							<label class="at">
								<span class="at-l">{L('v3p_when_at_label')}</span>
								<span class="at-f">
									<input
										class="at-i"
										data-testid="v3-plan-time"
										inputmode="numeric"
										placeholder="hh:mm"
										maxlength="5"
										aria-invalid={atBad}
										bind:value={atText}
										onblur={commitAt}
										onkeydown={(e) => {
											if (e.key === 'Enter') {
												e.preventDefault();
												commitAt();
											}
										}}
									/>
									<span class="ist">IST</span>
								</span>
							</label>
							{#if atBad}<p class="warn-line" role="status">{L('v3p_when_at_bad')}</p>{/if}
						{/if}
						{#if leaves}<p class="leaves" data-testid="v3-plan-leaves"><Glyph name="clock" size={15} />{leaves}</p>{/if}
					</fieldset>

					{#if labelOpen}
						<label class="lab">
							<span class="gh">{L('v3p_label')}</span>
							<input class="lab-i" data-testid="v3-plan-label" maxlength="120" placeholder={L('v3p_label_ph')} bind:value={label} autocomplete="off" />
							<span class="fine">{L('v3p_label_hint')}</span>
						</label>
					{:else}
						<button type="button" class="linkish" onclick={() => (labelOpen = true)}><Glyph name="plus" size={16} />{L('v3p_label_toggle')}</button>
					{/if}

					{#if planFail}
						<div class="fail" role="alert" data-testid="v3-plan-failure" data-kind={planFail.kind} bind:this={failBox}>
							<p class="fail-h">{L('v3p_fail_plan_heading')}</p>
							<p class="fail-lead">{planFail.lead}</p>
							{#if planFail.kind !== 'no-answer'}<blockquote class="verbatim" data-testid="v3-plan-failure-text">{planFail.text}</blockquote>{/if}
							{#if planFail.kind === 'no-answer'}<p class="fail-tech" data-testid="v3-plan-failure-text">{planFail.text}</p>{/if}
						</div>
					{/if}
				{:else if step === 'routes'}
					<!-- ── 2. routes ── -->
					<div class="trip" data-testid="v3-plan-trip">
						<div class="trip-line">
							<span class="tdot" aria-hidden="true"></span><b>{tripFrom?.name}</b>
							<Glyph name="up" size={14} class="arrow" />
							<span class="tsq" aria-hidden="true"></span><b>{tripTo?.name}</b>
						</div>
						<div class="trip-meta">
							<span>{L('v3p_trip_class', tripClass)}</span>
							{#if tripLeaves}<span>{L('v3p_leaves', tripLeaves)}</span>{/if}
							<button type="button" class="linkish sm" data-testid="v3-plan-edit" onclick={() => (editing = true)}>{L('v3p_edit')}</button>
						</div>
					</div>

					<div class="tags">
						<span class={['tag', `tone-${stateTone(gate.state)}`]} data-testid="v3-plan-status" data-state={gate.state}>{L(stateKey(gate.state))}</span>
						{#if trafficKey && candidates.length}
							<span class="tag dashed" data-testid="v3-plan-sim" data-label={ops.trafficFeed?.label ?? 'unknown'} title={L('v3p_sim_tip')}>
								<Glyph name="flask" size={14} />{L(trafficKey)}
							</span>
						{/if}
					</div>

					{#if gate.state === 'no_route' || !candidates.length}
						<div class="empty" data-testid="v3-plan-no-route">
							<h2 class="h" id="v3p-heading">{L('v3p_no_route_heading')}</h2>
							<p class="lead">{L('v3p_no_route_body')}</p>
							{#if doc?.overall_reasoning}<blockquote class="verbatim">{ops.text(doc.overall_reasoning)}</blockquote>{/if}
							<p class="lead">{L('v3p_no_route_next')}</p>
						</div>
					{:else}
						<h2 class="h" id="v3p-heading">{L('v3p_routes_found', candidates.length)}</h2>
						<p class="lead">{L('v3p_routes_lead')}</p>

						{#if gate.held}
							<div class="note hold" data-testid="v3-plan-hold" role="status">
								<Glyph name="clock" size={18} />
								<span><b>{L('v3p_hold_heading')}</b>{L('v3p_hold_body', holdAt)}</span>
							</div>
						{/if}

						<div class="routes" role="radiogroup" aria-label={L('v3p_routes_found', candidates.length)}>
							{#each candidates as route, i (route.route_id)}
								<RouteCard
									{route}
									rank={i}
									recommended={route.route_id === recommendedId}
									pickedBy={lc.recommendedBy}
									confidence={doc?.decider_pick?.confidence ?? null}
									adds={addsFor(i)}
									reason={route.reason ? ops.text(route.reason) : null}
									checked={route.route_id === previewId}
									{lang}
									shot={convoyShot(lc.vvipClass)}
									onpick={() => (picked = route.route_id)}
								/>
							{/each}
						</div>

						{#if doc?.overall_reasoning}
							<details class="more">
								<summary>{L('v3p_notes')}</summary>
								<p class="notes" data-testid="v3-plan-notes">{ops.text(doc.overall_reasoning)}</p>
							</details>
						{/if}
						{#if doc?.rejected_routes?.length}
							<details class="more">
								<summary>{L('v3p_rejected', doc.rejected_routes.length)}</summary>
								<ul class="rej">
									{#each doc.rejected_routes as r (r.route_id)}<li>{ops.text(r.reason ?? r.route_id)}</li>{/each}
								</ul>
							</details>
						{/if}
					{/if}
				{:else if step === 'launch'}
					<!-- ── 3. launch ── -->
					<h2 class="h" id="v3p-heading">{L('v3p_launch_heading')}</h2>
					<p class="lead">{L('v3p_launch_lead', tripClass, tripTo?.name ?? '—')}</p>
					{#if launchFail}
						<div class="fail" role="alert" data-testid="v3-plan-refusal" data-kind={launchFail.kind} bind:this={failBox}>
							<p class="fail-h">{L('v3p_fail_launch_heading')}</p>
							{#if launchFail.lead}<p class="fail-lead">{launchFail.lead}</p>{/if}
							{#if launchFail.kind === 'no-answer'}
								<p class="fail-tech" data-testid="v3-plan-refusal-text">{launchFail.text}</p>
							{:else}
								<blockquote class="verbatim" data-testid="v3-plan-refusal-text">{launchFail.text}</blockquote>
							{/if}
							<p class="fine">{L('v3p_fail_once')}</p>
						</div>
					{/if}

					{#each candidates.filter((c) => c.route_id === recommendedId) as route (route.route_id)}
						<div class="mini">
							<RouteCard
								{route}
								rank={candidates.indexOf(route)}
								recommended
								pickedBy={lc.recommendedBy}
								confidence={doc?.decider_pick?.confidence ?? null}
								adds={null}
								reason={null}
								checked
								{lang}
								shot={convoyShot(lc.vvipClass)}
								onpick={() => {}}
							/>
						</div>
					{/each}

					{#if gate.state === 'conditional'}
						<section class="waiver" data-testid="v3-plan-waiver-box">
							<h3 class="gh">{L('v3p_waiver_heading')}</h3>
							<p class="fine">{L('v3p_waiver_lead')}</p>
							<ul class="viol">
								{#each waiver.slice(0, 6) as line, vi (vi)}
									<li>{ops.text(line)}</li>
								{/each}
							</ul>
							<label class="check">
								<input type="checkbox" data-testid="v3-plan-waiver" bind:checked={waiverAccepted} disabled={lc.phase === 'starting'} />
								<span>{L('v3p_waiver')}</span>
							</label>
							{#if waiverAccepted && ops.officerOn}<p class="stamp" data-testid="v3-plan-waiver-by">{L('v3p_waiver_by', ops.dutyOfficer.trim())}</p>{/if}
						</section>
					{/if}

					<PlanOfficer {lang} />
					{#if lc.note}<p class="fine" data-testid="v3-plan-note">{lc.note}</p>{/if}
				{:else}
					<!-- ── 4. live ── -->
					<div class="live-head">
						<span class={['live-dot', ended && 'off']} aria-hidden="true"></span>
						<h2 class="h" id="v3p-heading">{ended ? L('v3p_ended_heading') : L('v3p_live_heading')}</h2>
					</div>
					{#if ended}
						<p class="lead" data-testid="v3-plan-ended" data-status={lc.endedStatus ?? ''}>{L(endKey)}</p>
					{:else if adopted}
						<p class="lead">{L('v3p_live_adopted')}</p>
					{:else}
						<p class="lead">{L('v3p_live_lead', lc.vvipClass, PLAN_POIS[lc.destIdx]?.name ?? '—')}</p>
					{/if}
					<div class="tags">
						{#if lc.startedAt && !adopted}<span class="tag tone-neutral">{L('v3p_live_since', fmtTime(lc.startedAt))}</span>{/if}
						{#if lane?.gpsMode === 'emulated'}<span class="tag dashed" data-testid="v3-plan-emulated" title={L('v3p_gps_tip')}><Glyph name="flask" size={14} />{L('v3p_gps_emulated')}</span>{/if}
						{#if lane?.trafficSimulated}<span class="tag dashed" data-testid="v3-plan-sim" data-label="simulated" title={L('v3p_sim_tip')}><Glyph name="flask" size={14} />{L('v3p_sim')}</span>{/if}
					</div>

					{#if proposal}
						<a class="proposal" href={proposalHref(proposal.approvalId)} data-testid="v3-plan-proposal" data-approval-id={proposal.approvalId}>
							<span class="pr-top">
								<span class="pr-k"><span class="pr-dot" aria-hidden="true"></span>{L('v3p_proposal')}</span>
								{#if proposalLeft != null}
									<span class="pr-left" role="timer">{proposalLeft > 0 ? `${Math.floor(proposalLeft / 60)}:${String(proposalLeft % 60).padStart(2, '0')}` : tOps(lang, 'escExpiring')}</span>
								{/if}
							</span>
							<span class="pr-t">{ops.text(ops.escortProposalText(proposal))}</span>
							<span class="pr-go">{L('v3p_proposal_open')}<Glyph name="up" size={14} class="go-arrow" /></span>
						</a>
					{/if}

					<div class="links">
						<a class="ghost" href={mapHref} data-testid="v3-plan-follow"><Glyph name="map" size={18} />{L('v3p_follow')}</a>
						{#if eventId}<a class="ghost" href={eventHref(eventId)} data-testid="v3-plan-operation"><Glyph name="convoy" size={18} />{L('v3p_open_event')}</a>{/if}
					</div>

					{#if stopFail}<blockquote class="verbatim" role="alert" data-testid="v3-plan-stop-failure">{stopFail}</blockquote>{/if}
					{#if lc.clearOutcome}
						<div class={['outcome', lc.clearOutcome.ok && 'ok']} data-testid="v3-plan-clear-outcome" data-ok={lc.clearOutcome.ok} data-to-status={lc.clearOutcome.toStatus ?? ''}>
							{#if lc.clearOutcome.ok}
								<Glyph name="checkc" size={18} />{L('v3p_cleared', lc.clearOutcome.toStatus ?? '—')}
							{:else}
								<span>{L('v3p_clear_failed')}</span>
								<blockquote class="verbatim">{ops.text(lc.clearOutcome.detail ?? '—')}</blockquote>
							{/if}
						</div>
					{/if}
					{#if !ended}<PlanOfficer {lang} context="live" />{/if}
				{/if}
			</div>

			<!-- the step's one primary action (and its reason when it is locked) -->
			<footer class="foot">
				{#if step === 'where'}
					<button type="button" class="primary" data-testid="v3-plan-find" disabled={!!findLock || lc.phase === 'planning'} aria-describedby="v3p-find-why" onclick={() => void findRoutes()}>
						{lc.phase === 'planning' ? L('v3p_finding') : L('v3p_find')}
						{#if lc.phase !== 'planning'}<Glyph name="route" size={20} />{/if}
					</button>
					<p class="why" id="v3p-find-why">{findLock ?? L('v3p_find_note')}</p>
				{:else if step === 'routes'}
					{#if gate.escortOffered}
						<button type="button" class="primary" data-testid="v3-plan-continue" onclick={() => (confirming = true)}>{L('v3p_continue')}</button>
					{:else}
						<button type="button" class="primary" data-testid="v3-plan-replan" onclick={() => (editing = true)}>{L('v3p_replan')}</button>
					{/if}
					{#if gate.launchLockReason && gate.state !== 'no_route'}<p class="why">{gate.launchLockReason}</p>{/if}
				{:else if step === 'launch'}
					<button
						type="button"
						class="primary go"
						data-testid="v3-plan-launch"
						aria-disabled={gate.launchLocked || lc.phase === 'starting'}
						aria-describedby="v3p-launch-why"
						onclick={() => void launch()}
					>
						{lc.phase === 'starting' ? L('v3p_launching') : L('v3p_launch')}
					</button>
					<p class="why" id="v3p-launch-why" data-testid="v3-plan-lock" data-locked={gate.launchLocked ? 'true' : 'false'}>
						{gate.launchLockReason ?? L('v3p_once')}
					</p>
					<button type="button" class="linkish sm" data-testid="v3-plan-back" disabled={lc.phase === 'starting'} onclick={() => (confirming = false)}>{L('v3p_back')}</button>
				{:else if !ended}
					<button
						type="button"
						class="danger"
						data-testid="v3-plan-stop"
						aria-disabled={!ops.officerOn || lc.phase === 'stopping'}
						onclick={() => {
							if (ops.officerOn && lc.phase === 'escorting') void stop();
						}}
					>
						{lc.phase === 'stopping' ? L('v3p_stopping') : L('v3p_stop')}
					</button>
					{#if !ops.officerOn}<p class="why">{L('v3p_lock_stop')}</p>{/if}
				{:else}
					{#if lc.movementId && !lc.clearOutcome?.ok}
						<button
							type="button"
							class="primary"
							data-testid="v3-plan-clear"
							aria-disabled={!ops.officerOn || lc.clearing}
							title={L('v3p_clear_hint')}
							onclick={() => {
								if (ops.officerOn && !lc.clearing) void lc.clear();
							}}
						>
							{lc.clearing ? L('v3p_clearing') : L('v3p_clear')}
						</button>
						<p class="why">{ops.officerOn ? L('v3p_clear_hint') : L('v3p_lock_stop')}</p>
					{/if}
					<button type="button" class="linkish sm" data-testid="v3-plan-new" onclick={startOver}>{L('v3p_new')}</button>
				{/if}
			</footer>
		</section>

		<div class="mapcol">
			<MapThumb class="pmap" {overlay} {roads} alt={mapAlt} eager labels credit markerR={15} maxTiles={42} zoom={13} />
			{#if step !== 'where' && candidates.length && !adopted}
				<div class="key" data-testid="v3-plan-key">
					<span class="k-row"><span class="sw sw-route" aria-hidden="true"></span>{previewId === recommendedId ? L('v3p_map_key_runs') : L('v3p_compare')}</span>
					{#if candidates.length > 1}<span class="k-row"><span class="sw sw-dash" aria-hidden="true"></span>{L('v3p_map_key_other')}</span>{/if}
					{#if trafficKey}<span class="k-row dim"><Glyph name="flask" size={14} />{L(trafficKey)}</span>{/if}
				</div>
			{/if}
		</div>
	</div>
{/if}

{#if Omnibar}<Omnibar />{/if}

<style>
	.plan {
		display: grid;
		grid-template-columns: 540px minmax(0, 1fr);
		gap: 24px;
		height: 100%;
		min-height: 0;
		padding: 24px var(--v3-gut) 24px 24px;
		box-sizing: border-box;
	}

	/* ── the sheet ─────────────────────────────────────────────────────────── */
	.sheet {
		display: flex;
		flex-direction: column;
		min-height: 0;
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
		box-shadow:
			0 0 0 1px var(--v3-line-1),
			var(--v3-elev-1);
		overflow: hidden;
	}

	.steps {
		display: flex;
		gap: 6px;
		margin: 0;
		padding: 18px 24px 14px;
		list-style: none;
		border-bottom: 1px solid var(--v3-line-1);
	}

	.st {
		display: flex;
		align-items: center;
		gap: 8px;
		flex: 1;
		min-width: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		font-weight: 600;
	}

	.st-n {
		display: grid;
		place-items: center;
		flex: none;
		width: 24px;
		height: 24px;
		border-radius: 50%;
		box-shadow: inset 0 0 0 1.5px var(--v3-line-3);
		font-size: var(--v3-text-micro);
		font-variant-numeric: tabular-nums;
	}

	.st-l {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.st.now {
		color: var(--v3-t1);
	}

	.st.now .st-n {
		background: var(--v3-primary-bg);
		box-shadow: none;
		color: var(--v3-primary-ink);
	}

	.st.done {
		color: var(--v3-t2);
	}

	.st.done .st-n {
		background: var(--v3-route-veil);
		box-shadow: none;
		color: var(--v3-route-text);
	}

	.body {
		display: flex;
		flex-direction: column;
		gap: 18px;
		flex: 1;
		min-height: 0;
		padding: 22px 24px 24px;
		overflow: auto;
		scrollbar-width: thin;
		scrollbar-color: var(--v3-s4) transparent;
	}

	.h {
		margin: 0;
		font-size: var(--v3-text-title);
		line-height: var(--v3-lh-title);
		font-weight: 680;
	}

	.lead {
		margin: -8px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
	}

	.fine {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.warn-line {
		margin: -8px 0 0;
		color: var(--v3-decide-text);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	/* the From / To pair: one card, a line joining the dot and the square */
	.pair {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding-right: 52px;
	}

	.pair::before {
		content: '';
		position: absolute;
		left: 23px;
		top: 38px;
		bottom: 38px;
		width: 2px;
		background: var(--v3-line-3);
	}

	.swap {
		position: absolute;
		right: 0;
		top: 50%;
		display: grid;
		place-items: center;
		width: 40px;
		height: 40px;
		margin-top: -20px;
		border: 1px solid var(--v3-line-2);
		border-radius: 50%;
		background: var(--v3-s2);
		color: var(--v3-t2);
		cursor: pointer;
	}

	.swap:hover:not(:disabled) {
		color: var(--v3-t1);
		border-color: var(--v3-line-3);
	}

	.group {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0;
		padding: 0;
		border: 0;
		min-width: 0;
	}

	.gh {
		margin: 0;
		padding: 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
		font-weight: 650;
	}

	/* the classes, like ride types: four cards in a row */
	.classes {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 8px;
	}

	.cls {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 2px;
		min-width: 0;
		padding: 12px 12px 12px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		text-align: left;
		cursor: pointer;
		transition: border-color var(--v3-dur-1) var(--v3-ease);
	}

	.cls:hover {
		border-color: var(--v3-line-3);
	}

	.cls.is-selected {
		border-color: var(--v3-route);
		background: var(--v3-route-veil);
		box-shadow: inset 0 0 0 1px var(--v3-route);
	}

	.cls :global(.cls-shot) {
		width: 100%;
		height: auto;
		margin: -4px 0 2px;
	}

	.dest {
		position: relative;
		flex: none;
		height: 150px;
		overflow: hidden;
		border-radius: var(--v3-radius-l);
	}

	@media (max-width: 1500px), (max-height: 820px) {
		.dest {
			height: 88px;
		}
	}

	.dest :global(.cover) {
		width: 100%;
		height: 100%;
	}

	.dest-name {
		position: absolute;
		top: 10px;
		left: 12px;
		z-index: 2;
		display: flex;
		flex-direction: column;
		padding: 4px 10px;
		border-radius: var(--v3-radius-s);
		background: var(--v3-photo-scrim);
		color: var(--v3-photo-ink);
		font-size: var(--v3-text-meta);
		font-weight: 650;
	}

	.dest-name small {
		font-size: var(--v3-text-micro);
		font-weight: 500;
		opacity: 0.86;
	}

	.cls-id {
		margin-bottom: 4px;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 700;
	}

	.cls-m {
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.chip {
		height: 38px;
		padding: 0 16px;
		border: 1px solid var(--v3-line-2);
		border-radius: 19px;
		background: transparent;
		color: var(--v3-t2);
		font: inherit;
		font-size: 14px;
		font-weight: 620;
		cursor: pointer;
	}

	.chip:hover {
		color: var(--v3-t1);
		border-color: var(--v3-line-3);
	}

	.chip.is-selected {
		border-color: var(--v3-t1);
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.at {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.at-l {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.at-f {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 40px;
		padding: 0 12px;
		border: 1px solid var(--v3-line-3);
		border-radius: var(--v3-radius-s);
		background: var(--v3-s2);
	}

	.at-i {
		width: 64px;
		border: 0;
		background: transparent;
		color: var(--v3-t1);
		font: inherit;
		font-size: var(--v3-text-sub);
		font-variant-numeric: tabular-nums;
		outline: 0;
	}

	.at-i[aria-invalid='true'] {
		color: var(--v3-decide-text);
	}

	.ist {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 650;
	}

	.leaves {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-meta);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}

	.lab {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.lab-i {
		height: 42px;
		padding: 0 14px;
		border: 1px solid var(--v3-line-3);
		border-radius: var(--v3-radius-s);
		background: var(--v3-s2);
		color: var(--v3-t1);
		font: inherit;
		font-size: var(--v3-text-body);
	}

	.linkish {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		align-self: flex-start;
		padding: 6px 0;
		border: 0;
		background: none;
		color: var(--v3-brand-text);
		font: inherit;
		font-size: 14px;
		font-weight: 650;
		cursor: pointer;
	}

	.linkish.sm {
		padding: 2px 0;
		font-size: var(--v3-text-meta);
	}

	.linkish:disabled {
		color: var(--v3-t3);
		cursor: default;
	}

	/* ── failures: a neutral panel, the server's own words quoted (never red: red is a vehicle alert) ── */
	.fail {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 14px 16px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		box-shadow: inset 3px 0 0 var(--v3-line-3);
	}

	.fail-h {
		margin: 0;
		font-size: var(--v3-text-body);
		font-weight: 650;
	}

	.fail-lead {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.verbatim {
		margin: 0;
		padding: 8px 12px;
		border-left: 2px solid var(--v3-line-3);
		color: var(--v3-t1);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		overflow-wrap: anywhere;
		white-space: pre-wrap;
	}

	.fail-tech {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		overflow-wrap: anywhere;
	}

	/* ── routes ────────────────────────────────────────────────────────────── */
	.trip {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 14px 16px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.trip-line {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 8px;
		font-size: var(--v3-text-body);
	}

	.trip-line :global(.arrow) {
		transform: rotate(90deg);
		color: var(--v3-t3);
	}

	.tdot,
	.tsq {
		width: 10px;
		height: 10px;
		border: 2.5px solid var(--v3-brand-text);
		border-radius: 50%;
	}

	.tsq {
		border-color: var(--v3-route);
		border-radius: 2px;
		background: var(--v3-route);
	}

	.trip-meta {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 14px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.trip-meta .linkish {
		margin-left: auto;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.tag {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 28px;
		padding: 0 12px;
		border-radius: 14px;
		font-size: var(--v3-text-meta);
		font-weight: 650;
		white-space: nowrap;
	}

	.tone-ok {
		background: var(--v3-ok-veil);
		color: var(--v3-ok-text);
	}

	.tone-decide {
		background: var(--v3-decide-veil);
		color: var(--v3-decide-text);
	}

	.tone-neutral {
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.tag.dashed {
		border: 1px dashed var(--v3-dashed);
		color: var(--v3-t2);
	}

	.routes {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.note {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		padding: 12px 14px;
		border-radius: var(--v3-radius-m);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.note b {
		display: block;
		font-size: var(--v3-text-body);
	}

	.note.hold {
		background: var(--v3-decide-veil);
		color: var(--v3-decide-text);
	}

	.empty {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.more summary {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 650;
		cursor: pointer;
	}

	.notes,
	.rej {
		margin: 8px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.rej {
		padding-left: 18px;
	}

	/* ── launch ────────────────────────────────────────────────────────────── */
	.mini :global(.card) {
		cursor: default;
	}

	.waiver {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 14px 16px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-decide-veil);
		box-shadow: inset 3px 0 0 var(--v3-decide);
	}

	.viol {
		margin: 0;
		padding-left: 18px;
		color: var(--v3-t1);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.check {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
		cursor: pointer;
	}

	.check input {
		flex: none;
		width: 20px;
		height: 20px;
		margin: 1px 0 0;
		accent-color: var(--v3-decide);
	}

	.stamp {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	/* ── live ──────────────────────────────────────────────────────────────── */
	.live-head {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.live-dot {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: var(--v3-route);
		box-shadow: 0 0 0 6px var(--v3-route-veil);
		animation: pulse 2.4s var(--v3-ease) infinite;
	}

	.live-dot.off {
		background: var(--v3-t3);
		box-shadow: none;
		animation: none;
	}

	@keyframes pulse {
		50% {
			box-shadow: 0 0 0 10px var(--v3-scrim-none);
		}
	}

	.proposal {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 14px 16px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-decide-veil);
		box-shadow: inset 0 0 0 1px var(--v3-decide-line);
		color: var(--v3-t1);
		text-decoration: none;
	}

	.pr-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
	}

	.pr-k {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		color: var(--v3-decide-text);
		font-size: var(--v3-text-meta);
		font-weight: 650;
	}

	.pr-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--v3-decide);
	}

	.pr-left {
		color: var(--v3-decide-text);
		font-size: var(--v3-text-sub);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.pr-t {
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
	}

	.pr-go {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--v3-decide-text);
		font-size: var(--v3-text-meta);
		font-weight: 650;
	}

	.pr-go :global(.go-arrow) {
		transform: rotate(90deg);
	}

	.links {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}

	.ghost {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: var(--v3-ctl-lg);
		padding: 0 16px;
		border: 1px solid var(--v3-line-2);
		border-radius: 22px;
		color: var(--v3-t1);
		font-size: 14px;
		font-weight: 650;
		text-decoration: none;
	}

	.ghost:hover {
		border-color: var(--v3-line-3);
		background: var(--v3-s2);
	}

	.outcome {
		display: flex;
		flex-direction: column;
		gap: 6px;
		color: var(--v3-t1);
		font-size: var(--v3-text-meta);
	}

	.outcome.ok {
		flex-direction: row;
		align-items: center;
		gap: 8px;
		color: var(--v3-ok-text);
	}

	/* ── the footer: the step's one primary action ─────────────────────────── */
	.foot {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 16px 24px 20px;
		border-top: 1px solid var(--v3-line-1);
		background: var(--v3-s1);
	}

	.primary,
	.danger {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		height: var(--v3-ctl-xl);
		padding: 0 24px;
		border: 0;
		border-radius: 28px;
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		font: inherit;
		font-size: var(--v3-text-sub);
		font-weight: 680;
		white-space: nowrap;
		cursor: pointer;
		transition: background var(--v3-dur-1) var(--v3-ease);
	}

	.primary:hover:not(:disabled):not([aria-disabled='true']) {
		background: var(--v3-primary-hover);
	}

	.primary:disabled,
	.primary[aria-disabled='true'],
	.danger[aria-disabled='true'] {
		background: var(--v3-s3);
		color: var(--v3-t3);
		cursor: not-allowed;
	}

	.danger {
		background: transparent;
		box-shadow: inset 0 0 0 1.5px var(--v3-t2);
		color: var(--v3-t1);
	}

	.why {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		text-align: center;
	}

	.foot .linkish {
		align-self: center;
	}

	/* ── the map ───────────────────────────────────────────────────────────── */
	.mapcol {
		position: relative;
		min-width: 0;
		min-height: 0;
		border-radius: var(--v3-radius-xl);
		overflow: hidden;
		box-shadow: 0 0 0 1px var(--v3-line-1);
	}

	.mapcol :global(.pmap) {
		position: absolute;
		inset: 0;
	}

	/* the map key floats on the map's tag ground (--v3-glass: its inks hold ≥ 4.5:1 over the darkest and lightest graded
	   map, tests/v3-tokens.unit.mjs); the Map page keeps its own translucent glass tokens */
	.key {
		position: absolute;
		left: 16px;
		bottom: 16px;
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 12px 14px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: var(--v3-glass);
		color: var(--v3-t1);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		font-weight: 600;
	}

	.k-row {
		display: inline-flex;
		align-items: center;
		gap: 10px;
	}

	.k-row.dim {
		color: var(--v3-t2);
	}

	.sw {
		width: 26px;
		height: 0;
		border-top: 5px solid var(--v3-route);
		border-radius: 3px;
	}

	.sw-dash {
		border-top: 3px dashed var(--v3-t2);
	}

	.signin {
		display: grid;
		place-items: center;
		height: 100%;
	}

	.signin-card {
		max-width: 420px;
		padding: 28px;
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}

	.swap:focus-visible,
	.cls:focus-visible,
	.chip:focus-visible,
	.linkish:focus-visible,
	.primary:focus-visible,
	.danger:focus-visible,
	.ghost:focus-visible,
	.proposal:focus-visible,
	.at-i:focus-visible,
	.lab-i:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	:global(:lang(hi)) .h,
	:global(:lang(mr)) .h {
		line-height: 1.4;
	}

	@media (max-width: 1500px) {
		.plan {
			grid-template-columns: 460px minmax(0, 1fr);
			gap: 18px;
			padding: 18px var(--v3-gut) 18px 18px;
		}

		.steps {
			padding: 14px 20px 12px;
		}

		.body {
			gap: 14px;
			padding: 18px 20px 20px;
		}

		.foot {
			padding: 12px 20px 16px;
		}

		.cls {
			padding: 10px;
		}

		.primary,
		.danger {
			height: 50px;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.live-dot {
			animation: none;
		}
	}

	/* a phone: the sheet over a short map, one column, in the page's own scroll */
	@media (max-width: 720px) {
		.plan {
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: auto 220px;
			height: auto;
			gap: 12px;
			padding: 12px var(--v3-gut) 16px;
		}

		.sheet {
			overflow: visible;
		}

		.classes {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.steps {
			padding: 14px 16px 10px;
			overflow-x: auto;
			scrollbar-width: none;
		}

		.mapcol {
			min-height: 220px;
		}
	}
</style>
