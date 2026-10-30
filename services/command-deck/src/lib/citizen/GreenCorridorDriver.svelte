<script lang="ts">
	/**
	 * GreenCorridorDriver — "The Window" (Daylight, Marathi-first).
	 *
	 * The 108 driver flow on the REAL dispatch lifecycle (units/router.py):
	 *
	 *   request   POST /api/v1/events/{event}/dispatch — agency ambulance,
	 *             the driver's own 108 unit, the stretch's signalised
	 *             junction as waypoint, requested_by '108-driver'. The
	 *             event is the live public event that owns the stretch.
	 *   approval  a named duty officer approves or defers it on /ops
	 *             (DispatchTiles). The driver CANNOT approve: the page polls
	 *             its own request (GET /api/public/dispatches/{id}, one poll
	 *             in flight, statuses never regress) and says "awaiting duty
	 *             officer" until the officer decides.
	 *   window    doctrine: the corridor opens 60–180 s before the
	 *             ambulance reaches the junction (the event's advance
	 *             closure, clamped; its provenance — closure plan, live
	 *             adaptation or doctrine baseline — is shown). The bound
	 *             unit is the oracle's EMULATED projection, whose journey
	 *             starts at approved_at; its projected arrival times the
	 *             window (holds.windowTiming): "approved — opens in N s",
	 *             then "open — closes in N s" as it reaches the junction.
	 *             Without a projection the window runs from approved_at.
	 *             Server clock, skew corrected from as_of.
	 *
	 * Only REAL corridors are requestable: an event the emulator opened
	 * (SIMULATED FEED · EMULATED) is never offered as a live corridor — the
	 * page says how many it withheld — so a driver never files a 108 request
	 * against a demonstration run.
	 *
	 * A request in flight survives the public feed dropping out or the
	 * event leaving it (the request's event is snapshotted). The SCRIPTED
	 * FALLBACK (labelled, nothing sent, demo-scale numbers, no duty officer
	 * in the loop) appears only when no live public event exists, and once
	 * started it runs to its end even if a live event appears. Stretches
	 * carry their signage road names.
	 */
	import { onMount } from 'svelte';
	import { kindLabel, localizeNumber, t } from '$lib/i18n/strings';
	import { citizenT } from '$lib/i18n/strings.citizen';
	import { requestDispatch } from '$lib/ops/client';
	import '$lib/v3/public/packs.pub3';
	import Glyph from '$lib/v3/Glyph.svelte';
	import PublicTag from '$lib/v3/public/PublicTag.svelte';
	import LightCorridorMap from './LightCorridorMap.svelte';
	import { clockAt, clockAtMs, doctrineWindowSec, windowState, windowTiming, type Stretch } from './holds';
	import { PUBLIC_DISPATCH_API, publicFeed } from './public-feed.svelte';
	import { fixturePublicEvents, type PublicCorridorEvent } from './public-model';
	import VehicleShot from '$lib/v3/media/VehicleShot.svelte';
	import AgencyMark from '$lib/v3/media/AgencyMark.svelte';
	import { markFor } from '$lib/v3/media/logos';
	import '$lib/v3/media/packs.media';

	type Phase =
		| 'idle'
		| 'evaluating'
		| 'requested'
		| 'approved'
		| 'proposal'
		| 'open'
		| 'done'
		| 'deferred'
		| 'cancelled';
	type Urgency = 'cardiac' | 'trauma' | 'stroke' | 'other';

	interface TrackedUnit {
		status: string | null;
		etaSec: number | null;
		arrived: boolean;
		position: { lon: number; lat: number } | null;
	}

	let { lang, onBack }: { lang: string; onBack?: () => void } = $props();

	const UNIT_RE = /^108-[A-Za-z0-9]{1,8}$/;
	const POLL_MS = 3000;
	/** Backend lifecycle order (units/router.py); terminal states share the top rank. */
	const STATUS_RANK: Record<string, number> = {
		requested: 0,
		approved: 1,
		en_route: 2,
		on_scene: 3,
		completed: 4,
		deferred: 4,
		cancelled: 4,
	};

	let phase = $state<Phase>('idle');
	/** "<eventId>|<segmentId>" — the stretch AND the event that owns it. */
	let choice = $state('');
	let unitNo = $state('');
	let urgency = $state<Urgency>('cardiac');
	let requestError = $state<string | null>(null);
	/**
	 * F-08: when THIS driver filed the request (local clock), or null. The
	 * clock counts from it — never from the page load — and says that the
	 * golden hour itself began earlier, at the incident Sajag cannot see.
	 */
	let requestedAtMs = $state<number | null>(null);
	let nowMs = $state(Date.now());
	const goldenElapsed = $derived(requestedAtMs == null ? null : Math.max(0, Math.floor((nowMs - requestedAtMs) / 1000)));

	// Live request state (the dispatch the officer decides on).
	let dispatchId = $state<string | null>(null);
	let dispatchEventId = $state<string | null>(null);
	/** The event + stretch the request was filed under (outlives the feed). */
	let requestSnapshot = $state<PublicCorridorEvent | null>(null);
	let requestStretch = $state<Stretch | null>(null);
	let dispatchStatus = $state<string | null>(null);
	let approvedAtMs = $state<number | null>(null);
	/** Projected arrival at the junction, server clock (eta_at + eta_sec). */
	let arrivalAtMs = $state<number | null>(null);
	let skewMs = $state(0);
	let pollFailing = $state(false);
	let unit = $state<TrackedUnit | null>(null);

	// Scripted-fallback state (demo-scale numbers, labelled).
	let scriptRunning = $state(false);
	let reachInSec = $state(0);
	let scriptedWindowSec = $state(0);
	let scriptedOpenedAt = $state(0);
	let scriptedUnit = $state<'none' | 'en_route' | 'on_scene'>('none');

	let pollTimer: ReturnType<typeof setInterval> | null = null;
	/** The dispatch whose status poll is in flight (one at a time). */
	let pollingId: string | null = null;
	let scriptTimers: ReturnType<typeof setTimeout>[] = [];

	/** Live public events with a spine (the request can only name one of these). */
	const liveEvents = $derived<PublicCorridorEvent[]>(
		publicFeed.status === 'live' || publicFeed.status === 'stale'
			? publicFeed.events.filter((e) => e.source === 'live' && e.stretches.length > 0)
			: [],
	);
	/** Emulated corridor events withheld from the picker (said, not hidden silently). */
	const emulatedWithheld = $derived(
		publicFeed.status === 'live' || publicFeed.status === 'stale'
			? publicFeed.events.filter((e) => e.source === 'emulated').length
			: 0,
	);
	const connecting = $derived(publicFeed.status === 'connecting');
	/**
	 * Scripted fallback ONLY when no live event exists and no live request
	 * is open — and once a scripted run starts it is latched to its end.
	 */
	const scripted = $derived(scriptRunning || (!connecting && liveEvents.length === 0 && dispatchId === null));
	const pickable = $derived<PublicCorridorEvent[]>(scripted ? fixturePublicEvents().slice(0, 1) : liveEvents);

	const chosen = $derived.by(() => {
		const [eid, sid] = choice.split('|');
		const ev = pickable.find((e) => e.eventId === eid);
		const stretch = ev?.stretches.find((s) => String(s.segmentId) === sid);
		return ev && stretch ? { ev, stretch } : null;
	});
	/** The event a live request was filed under: fresh from the feed, else its snapshot. */
	const requestEvent = $derived<PublicCorridorEvent | null>(
		dispatchEventId
			? (liveEvents.find((e) => e.eventId === dispatchEventId) ?? requestSnapshot)
			: (chosen?.ev ?? null),
	);
	const shownStretch = $derived<Stretch | null>(dispatchEventId ? requestStretch : (chosen?.stretch ?? null));

	/** The event's advance closure before the doctrine clamp, with its provenance. */
	const windowBasis = $derived.by(() => {
		if (scripted) return null;
		const adv = requestEvent?.hold.advanceClosureSec ?? null;
		return adv == null || !(adv > 0) ? null : { raw: Math.round(adv), source: requestEvent?.hold.source ?? null };
	});
	/** Window length: the event's advance closure inside the 60–180 s doctrine. */
	const windowSec = $derived(scripted ? scriptedWindowSec : doctrineWindowSec(windowBasis?.raw));
	const serverNow = $derived(nowMs + skewMs);
	const liveWindow = $derived(scripted ? null : windowTiming(approvedAtMs, arrivalAtMs, windowSec));

	/** Seconds left in an open window (scripted: from its scripted opening). */
	const countdown = $derived.by(() => {
		if (phase !== 'open' || windowSec == null) return null;
		if (scripted) {
			if (!scriptedOpenedAt) return null;
			return Math.max(0, windowSec - Math.floor((nowMs - scriptedOpenedAt) / 1000));
		}
		return liveWindow ? Math.max(0, Math.ceil((liveWindow.closesAt - serverNow) / 1000)) : null;
	});
	/** Seconds until an approved window opens (live, arrival-timed only). */
	const opensIn = $derived(
		phase === 'approved' && liveWindow ? Math.max(0, Math.ceil((liveWindow.opensAt - serverNow) / 1000)) : null,
	);

	// Scripted: the window closes when its countdown runs out.
	$effect(() => {
		if (scripted && countdown === 0 && phase === 'open') {
			phase = 'done';
			scriptRunning = false;
		}
	});

	// Live: an approved request's phase follows its window on the server clock.
	$effect(() => {
		if (scripted || (phase !== 'approved' && phase !== 'open')) return;
		if (!liveWindow) {
			// Approved, but no window length is published: open, untimed.
			if (phase !== 'open') phase = 'open';
			return;
		}
		const state = windowState(liveWindow, serverNow);
		if (state === 'closed') {
			phase = 'done';
			stopPolling();
		} else {
			const next: Phase = state === 'open' ? 'open' : 'approved';
			if (phase !== next) phase = next;
		}
	});

	const URGENCIES: Array<{ key: Urgency; labelKey: string }> = [
		{ key: 'cardiac', labelKey: 'urgCardiac' },
		{ key: 'trauma', labelKey: 'urgTrauma' },
		{ key: 'stroke', labelKey: 'urgStroke' },
		{ key: 'other', labelKey: 'urgOther' },
	];

	const rail = $derived<Array<{ key: Phase; labelKey: string }>>(
		scripted
			? [
					{ key: 'idle', labelKey: 'phase_idle' },
					{ key: 'evaluating', labelKey: 'phase_evaluating' },
					{ key: 'proposal', labelKey: 'phase_proposal' },
					{ key: 'open', labelKey: 'phase_open' },
				]
			: [
					{ key: 'idle', labelKey: 'phase_idle' },
					{ key: 'requested', labelKey: 'phase_requested' },
					{ key: 'approved', labelKey: 'phase_approved' },
					{ key: 'open', labelKey: 'phase_open' },
				],
	);
	const railActive = $derived<Phase>(
		phase === 'done' ? 'open' : phase === 'evaluating' && !scripted ? 'requested' : phase,
	);

	onMount(() => {
		const golden = setInterval(() => {
			nowMs = Date.now();
		}, 1000);
		return () => {
			clearInterval(golden);
			stopPolling();
			for (const tm of scriptTimers) clearTimeout(tm);
		};
	});

	function goldenClock(): string {
		if (goldenElapsed == null) return '—:—';
		const mm = String(Math.floor(goldenElapsed / 60)).padStart(2, '0');
		const ss = String(goldenElapsed % 60).padStart(2, '0');
		return localizeNumber(`${mm}:${ss}`, lang);
	}

	/** A stretch by its signage name and its place on the route (F-24: never a raw segment id). */
	function stretchLabel(roadName: string | null, index: number): string {
		const n = localizeNumber(index + 1, lang);
		return roadName ? citizenT(lang, 'driver_stretch_option', roadName, n) : citizenT(lang, 'driver_stretch_unnamed', n);
	}

	/** Where the window length came from, clamping and timing included. */
	function windowSourceText(): string {
		const basis = windowBasis;
		if (!basis || windowSec == null) return citizenT(lang, 'driver_window_unpublished');
		const key =
			basis.source === 'adaptive_params'
				? 'driver_window_from_adaptive'
				: basis.source === 'adaptive_baseline'
					? 'driver_window_from_baseline'
					: 'driver_window_from_policy';
		let text = citizenT(lang, key, localizeNumber(windowSec, lang));
		if (basis.raw !== windowSec) text += ` ${citizenT(lang, 'driver_window_clamped', localizeNumber(basis.raw, lang))}`;
		if (liveWindow) {
			text += ` · ${citizenT(lang, liveWindow.anchor === 'eta' ? 'driver_window_anchor_eta' : 'driver_window_anchor_approval')}`;
		}
		return text;
	}

	function stopPolling() {
		if (pollTimer) clearInterval(pollTimer);
		pollTimer = null;
	}

	function resetLive() {
		stopPolling();
		pollingId = null;
		dispatchId = null;
		dispatchEventId = null;
		requestSnapshot = null;
		requestStretch = null;
		dispatchStatus = null;
		approvedAtMs = null;
		arrivalAtMs = null;
		unit = null;
		pollFailing = false;
	}

	/**
	 * Map the officer's decision onto the driver's phase. Answers can land
	 * out of order (3 s poll, 8 s timeout): a status BEHIND the one already
	 * shown, or anything after a terminal state, is ignored.
	 */
	function applyStatus(status: string) {
		const rank = STATUS_RANK[status];
		if (rank === undefined) return;
		const current = dispatchStatus ? STATUS_RANK[dispatchStatus] : undefined;
		if (current !== undefined && (rank < current || (current === 4 && status !== dispatchStatus))) return;
		// The ticker refreshes once a second; window timing must not start
		// up to a second stale when the officer's approval lands.
		nowMs = Date.now();
		dispatchStatus = status;
		if (status === 'requested') phase = 'requested';
		else if (status === 'deferred') phase = 'deferred';
		else if (status === 'cancelled') phase = 'cancelled';
		else if (status === 'completed') phase = 'done';
		else if (phase === 'requested' || phase === 'evaluating') phase = 'approved'; // the window effect times it
		if (rank === 4) stopPolling();
	}

	async function pollDispatch() {
		const id = dispatchId;
		const eventId = dispatchEventId;
		if (!id || !eventId || pollingId === id) return;
		pollingId = id;
		try {
			const res = await fetch(`${PUBLIC_DISPATCH_API}/${id}?event=${eventId}`, {
				headers: { accept: 'application/json' },
				signal: AbortSignal.timeout(8000),
			});
			if (id !== dispatchId) return; // a newer request (or a reset) superseded this poll
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const body = (await res.json()) as {
				as_of?: string;
				dispatch?: { status?: string; approved_at?: string | null };
				unit?: {
					status?: string | null;
					eta_sec?: number | null;
					eta_at?: string | null;
					arrived?: boolean;
					position?: [number, number] | null;
				} | null;
			};
			if (id !== dispatchId) return;
			const asOf = body.as_of ? Date.parse(body.as_of) : Number.NaN;
			if (Number.isFinite(asOf)) skewMs = asOf - Date.now();
			// Approval is a fact once seen: a later answer never clears it.
			const approved = body.dispatch?.approved_at ? Date.parse(body.dispatch.approved_at) : Number.NaN;
			if (Number.isFinite(approved)) approvedAtMs = approved;
			const u = body.unit;
			if (u) {
				unit = {
					status: u.status ?? null,
					etaSec: typeof u.eta_sec === 'number' ? Math.round(u.eta_sec) : null,
					arrived: u.arrived === true,
					position: u.position ? { lon: u.position[0], lat: u.position[1] } : null,
				};
				const etaAt = u.eta_at ? Date.parse(u.eta_at) : Number.NaN;
				if (typeof u.eta_sec === 'number' && Number.isFinite(etaAt)) arrivalAtMs = etaAt + u.eta_sec * 1000;
			}
			pollFailing = false;
			applyStatus(body.dispatch?.status ?? 'requested');
		} catch {
			if (id === dispatchId) pollFailing = true;
		} finally {
			if (pollingId === id) pollingId = null;
		}
	}

	async function request() {
		const c = chosen;
		if (!c) {
			// The button stays enabled-looking; the reason is inline (SPEC §6.6).
			requestError = t(lang, 'asst_driver_choose_stretch');
			return;
		}
		requestError = null;
		if (scripted) {
			requestedAtMs = Date.now();
			nowMs = requestedAtMs;
			runScripted(c.stretch.segmentId);
			return;
		}
		if (!UNIT_RE.test(unitNo.trim())) {
			requestError = citizenT(lang, 'driver_unit_invalid');
			return;
		}
		resetLive();
		phase = 'evaluating';
		requestedAtMs = Date.now();
		nowMs = requestedAtMs;
		try {
			const rec = await requestDispatch(c.ev.eventId, {
				agency: 'ambulance',
				unitId: unitNo.trim(),
				waypointJunction: c.stretch.junctionId ?? undefined,
				requestedBy: '108-driver',
				note: `green corridor · ${urgency} · ${c.stretch.roadName ?? `segment ${c.stretch.segmentId}`}`,
			});
			if (!rec) throw new Error('no dispatch id returned');
			dispatchId = rec.dispatchId;
			dispatchEventId = c.ev.eventId;
			requestSnapshot = c.ev;
			requestStretch = c.stretch;
			applyStatus(rec.status);
			pollTimer = setInterval(() => void pollDispatch(), POLL_MS);
			void pollDispatch();
		} catch (err) {
			phase = 'idle';
			requestedAtMs = null; // nothing was filed: the clock has nothing to count from
			requestError = citizenT(lang, 'driver_request_failed', err instanceof Error ? err.message : String(err));
		}
	}

	/** The labelled scripted fallback: nothing is sent; numbers are demo-scale. */
	function runScripted(segmentId: number) {
		for (const tm of scriptTimers) clearTimeout(tm);
		scriptTimers = [];
		scriptRunning = true;
		phase = 'evaluating';
		scriptedUnit = 'none';
		scriptTimers.push(
			setTimeout(() => {
				reachInSec = 120 + (segmentId % 3) * 30;
				scriptedWindowSec = urgency === 'cardiac' ? 90 : urgency === 'stroke' ? 75 : 60;
				phase = 'proposal';
			}, 1400),
			setTimeout(() => {
				scriptedOpenedAt = Date.now();
				scriptedUnit = 'en_route';
				phase = 'open';
			}, 4400),
			setTimeout(() => (scriptedUnit = 'on_scene'), 13_400),
		);
	}

	function again() {
		for (const tm of scriptTimers) clearTimeout(tm);
		scriptTimers = [];
		scriptRunning = false;
		resetLive();
		requestedAtMs = null;
		phase = 'idle';
	}

	function statusWord(status: string | null): string {
		return status ? citizenT(lang, `dispatch_status_${status}`) : '—';
	}
</script>

{#snippet liveCorridor()}
	<div class="corridor-block">
		<h3>{citizenT(lang, 'corridor_map')} · {citizenT(lang, 'corridor_granted_stretch')}</h3>
		<div class="map-wrap">
			<LightCorridorMap
				{lang}
				compact
				highlightSegmentId={shownStretch?.segmentId ?? null}
				routes={requestEvent?.stretches.map((s) => ({ segmentId: s.segmentId, live: !scripted })) ?? []}
				unit={scripted ? null : (unit?.position ?? null)}
			/>
		</div>
		{#if scripted}
			<p class="unit" data-unit-status={scriptedUnit}>
				<PublicTag tone="dashed" glyph="flask" label={citizenT(lang, 'comms_dispatch_demo')} />
				<span>{scriptedUnit === 'on_scene' ? citizenT(lang, 'unit_on_scene') : citizenT(lang, 'unit_en_route')}</span>
			</p>
			<p class="unit-note">{citizenT(lang, 'units_note_fallback')}</p>
		{:else}
			<p class="unit" data-unit-status={dispatchStatus ?? 'none'}>
				<PublicTag tone="dashed" glyph="flask" label={citizenT(lang, 'driver_unit_emulated')} />
				<span class="fig">{unitNo.trim()}</span>
				<span>· {statusWord(dispatchStatus)}</span>
				{#if unit?.arrived}
					<span>· {citizenT(lang, 'driver_unit_arrived')}</span>
				{:else if unit?.etaSec != null}
					<span class="fig">· {citizenT(lang, 'driver_unit_eta', localizeNumber(unit.etaSec, lang))}</span>
				{:else}
					<span>· {citizenT(lang, 'driver_unit_no_position')}</span>
				{/if}
			</p>
		{/if}
	</div>
{/snippet}

<div class="driver" data-screen="driver" data-phase={phase} data-mode={connecting && dispatchId === null && !scriptRunning ? 'connecting' : scripted ? 'scripted' : 'live'}>
	<!-- Time since THIS request (F-08): always on screen, tabular; it starts when the
	     request is sent, never at page load, and never claims to be the golden hour itself. -->
	<div class="golden" data-testid="golden-hour" data-started={goldenElapsed == null ? '0' : '1'}>
		<span class="golden-label">{citizenT(lang, 'golden_hour')}</span>
		<span class="golden-clock fig" data-golden-seconds={goldenElapsed ?? undefined}>{goldenClock()}</span>
		<span class="golden-elapsed">{citizenT(lang, goldenElapsed == null ? 'golden_not_started' : 'golden_elapsed')}</span>
	</div>

	<header class="head">
		<span class="head-pic" aria-hidden="true"><VehicleShot cls="ambulance" {lang} width={200} decorative />{#if markFor('108')}<span class="head-mark"><AgencyMark role="108" {lang} size={24} decorative /></span>{/if}</span>
		{#if onBack}
			<button class="back" onclick={onBack}>← {t(lang, 'driverBack')}</button>
		{/if}
		<h1>{t(lang, 'driverTitle')}</h1>
		<!-- F-09: the officer's queue is the live flow's; the scripted fallback sends nothing (its note says so) -->
		{#if !scripted}<p data-testid="driver-sub">{t(lang, 'driverSub')}</p>{/if}
	</header>

	<!-- Fixed verb rail: four large steps. The current one is ringed AND bold; a step behind is ticked — never colour alone. -->
	<ol class="rail" data-testid="phase-rail">
		{#each rail as r, i (r.key)}
			{@const behind = railActive !== 'idle' && rail.findIndex((x) => x.key === railActive) > i}
			<li class="step" class:is-selected={railActive === r.key} class:done={behind} aria-current={railActive === r.key ? 'step' : undefined}>
				<span class="dot" aria-hidden="true">{#if behind}<Glyph name="check" size={22} />{:else}<span class="num fig">{localizeNumber(i + 1, lang)}</span>{/if}</span>
				<span class="word">{citizenT(lang, r.labelKey)}</span>
			</li>
		{/each}
	</ol>

	{#if connecting && dispatchId === null && !scriptRunning}
		<!-- no mode claim until the feed has answered -->
	{:else if scripted}
		<p class="mode-note scripted-note" data-testid="scripted-note">
			<PublicTag tone="dashed" glyph="flask" label={citizenT(lang, 'scripted_badge')} />
			<span class="note-text">{citizenT(lang, 'scripted_note')}</span>
		</p>
	{:else}
		<p class="mode-note live-note">
			<PublicTag tone="live" glyph="check" label={t(lang, 'opsSourceLive')} />
			<span class="note-text">{citizenT(lang, 'driver_live_note')}</span>
		</p>
	{/if}

	{#if connecting && dispatchId === null && !scriptRunning}
		<div class="empty" data-prim="empty-state">
			<img class="empty-scene" src="/artwork/scenes/day.svg" alt={t(lang, 'v3i_scene_day')} width="960" height="320" decoding="async" />
			<p class="empty-t">{citizenT(lang, 'citizen_feed_connecting')}</p>
		</div>
	{:else if phase === 'evaluating'}
		<section class="state-card evaluating" data-testid="evaluating">
			<div class="pulse" aria-hidden="true"></div>
			<p>{t(lang, 'evaluating')}</p>
		</section>
	{:else if phase === 'requested'}
		<!-- Live: the officer decides on /ops; the driver can only wait. -->
		<section class="state-card awaiting" data-testid="awaiting-officer">
			<div class="pulse" aria-hidden="true"></div>
			<div>
				<h2>{citizenT(lang, 'driver_awaiting_title')}</h2>
				<p>{citizenT(lang, 'driver_awaiting_body')}</p>
				{#if dispatchId}
					<p class="ref fig">{citizenT(lang, 'driver_request_ref', dispatchId.slice(0, 8))} · {unitNo.trim()}</p>
				{/if}
				{#if pollFailing}
					<p class="poll-note">{citizenT(lang, 'driver_status_retry')}</p>
				{/if}
			</div>
		</section>
	{:else if phase === 'proposal'}
		<!-- Scripted fallback only: demo-scale numbers, approval is scripted (the note above says so). -->
		<section class="state-card proposal" data-testid="proposal">
			<h2>{t(lang, 'proposalTitle')}</h2>
			<p class="reach">
				{t(lang, 'convoyReachesIn')}
				<strong class="fig">{localizeNumber(reachInSec, lang)} s</strong>
				<span class="fig">({clockAt(reachInSec, lang)})</span>
			</p>
			<p class="cross">
				{t(lang, 'crossBefore')} <strong class="fig">{clockAt(reachInSec + scriptedWindowSec, lang)}</strong>
			</p>
			<p class="doctrine">{citizenT(lang, 'doctrine_note')}</p>
			<p class="scripted-approval">{citizenT(lang, 'driver_scripted_approval')}</p>
		</section>
	{:else if phase === 'approved' || phase === 'open'}
		<!--
			One branch for both live states, so the corridor map is NOT
			remounted at the moment the window opens: approved = primed (opens
			one window-length before the unit's projected arrival), open =
			counting down to that arrival. The scripted run uses 'open' only.
		-->
		<section
			class={['state-card', phase === 'open' ? 'window-open' : 'primed']}
			data-testid={phase === 'open' ? 'window-open' : 'window-primed'}
		>
			{#if phase === 'open'}
				<h2 class="open-title">{t(lang, 'windowOpen')}</h2>
				{#if countdown != null}
					<p class="countdown fig" data-countdown={countdown}>
						<span class="cd-l">{t(lang, 'windowClosesIn')}</span>
						<span class="cd-n">{localizeNumber(countdown, lang)} s</span>
					</p>
				{/if}
			{:else}
				<h2 class="primed-title">{citizenT(lang, 'driver_primed_title')}</h2>
				{#if opensIn != null && liveWindow}
					<p class="countdown fig" data-opens-in={opensIn}>
						{citizenT(lang, 'driver_primed_countdown', localizeNumber(opensIn, lang))}
					</p>
					<p class="primed-when">{citizenT(lang, 'driver_primed_when', clockAtMs(liveWindow.opensAt - skewMs, lang))}</p>
				{/if}
			{/if}
			{#if !scripted}
				<p class="window-source" data-window-source={windowBasis?.source ?? 'none'} data-window-anchor={liveWindow?.anchor ?? 'none'}>
					{windowSourceText()}
				</p>
				{#if pollFailing}
					<p class="poll-note">{citizenT(lang, 'driver_status_retry')}</p>
				{/if}
			{/if}
			{@render liveCorridor()}
		</section>
	{:else}
		{#if phase === 'deferred' || phase === 'cancelled'}
			<p class="rail-note" data-phase-note={phase}>
				{phase === 'deferred' ? citizenT(lang, 'driver_deferred_body') : citizenT(lang, 'driver_cancelled_body')}
			</p>
		{:else if phase === 'done'}
			<p class="rail-note done-note" data-phase-note="done">{citizenT(lang, 'driver_window_closed')}</p>
		{/if}
		{#if pickable.length === 0}
			<div class="empty" data-prim="empty-state">
				<img class="empty-scene" src="/artwork/scenes/day.svg" alt={t(lang, 'v3i_scene_day')} width="960" height="320" decoding="async" />
				<p class="empty-t">{t(lang, 'noMovement')}</p>
				<p class="empty-h">{t(lang, 'noMovementSub')}</p>
			</div>
		{:else}
			<section class="request-card">
				<label class="field stretch-pick">
					<span class="lbl">{t(lang, 'atStretch')}</span>
					<select bind:value={choice} data-testid="stretch-select">
						<option value="">—</option>
						{#each pickable as ev (ev.eventId)}
							<optgroup label={citizenT(lang, 'driver_event_label', kindLabel(lang, ev.eventKind))}>
								{#each ev.stretches as st (st.segmentId)}
									<option value={`${ev.eventId}|${st.segmentId}`}>{stretchLabel(st.roadName, ev.stretches.indexOf(st))}</option>
								{/each}
							</optgroup>
						{/each}
					</select>
				</label>
				{#if !scripted}
					<label class="field unit-pick">
						<span class="lbl">{citizenT(lang, 'driver_unit_label')}</span>
						<input
							type="text"
							bind:value={unitNo}
							placeholder="108-14"
							autocomplete="off"
							spellcheck="false"
							aria-label={citizenT(lang, 'driver_unit_hint')}
							data-testid="unit-input"
						/>
					</label>
				{/if}
				<fieldset class="urgency">
					<legend>{t(lang, 'urgency')}</legend>
					<div class="chips">
						{#each URGENCIES as u (u.key)}
							<button type="button" class="urg" class:is-selected={urgency === u.key} aria-pressed={urgency === u.key} onclick={() => (urgency = u.key)}>
								{#if urgency === u.key}<Glyph name="check" size={18} />{/if}{t(lang, u.labelKey)}
							</button>
						{/each}
					</div>
				</fieldset>
				<div class="request-row">
					<button
						type="button"
						class="big"
						data-testid="request-btn"
						onclick={() => void request()}
						disabled={!scripted && !UNIT_RE.test(unitNo.trim())}
					>
						{t(lang, 'requestBtn')}
					</button>
					{#if !chosen}
						<!-- the inline reason: the control reads enabled, the missing pick is said -->
						<p class="request-hint">{t(lang, 'asst_driver_choose_stretch')}</p>
					{/if}
				</div>
				{#if requestError}
					<p class="request-error" data-testid="request-error">{requestError}</p>
				{/if}
				{#if phase === 'done' && scripted}
					<div class="after-action" data-testid="after-action">
						<!-- COPY-4: a scripted run measures nothing — no "minutes returned" figure -->
						<p>{citizenT(lang, 'after_action')}</p>
					</div>
				{/if}
			</section>
		{/if}
	{/if}

	{#if (phase === 'deferred' || phase === 'cancelled' || (phase === 'done' && !scripted)) && pickable.length === 0}
		<!-- Only when no request card is on screen (it carries the one request button). -->
		<button type="button" class="again" onclick={again}>{citizenT(lang, 'driver_new_request')}</button>
	{/if}

	{#if emulatedWithheld > 0 && dispatchId === null}
		<p class="emulated-withheld" data-testid="driver-emulated-withheld" data-count={emulatedWithheld}>
			<PublicTag tone="dashed" glyph="flask" label={citizenT(lang, 'citizen_emulated_badge')} />
			<span class="note-text">{citizenT(lang, 'driver_emulated_hidden', localizeNumber(emulatedWithheld, lang))}</span>
		</p>
	{/if}

	<div class="control-room">
		<h3>{citizenT(lang, 'control_room')}</h3>
		<p class="fig">{citizenT(lang, 'control_room_line')}</p>
	</div>

	<p class="baseline">{t(lang, 'baselineNote')}</p>
	{#if scripted}
		<p class="demo">{t(lang, 'demoNote')}</p>
	{/if}
</div>

<style>
	.driver {
		box-sizing: border-box;
		display: flex;
		flex-direction: column;
		gap: 16px;
		width: 100%;
		max-width: 592px;
		margin: 0 auto;
		padding: 20px 16px 40px;
		color: var(--v3-t1);
		font-size: 18px;
		line-height: 26px;
	}

	.fig {
		font-variant-numeric: tabular-nums;
	}

	/* ── the hero: time since THIS request ─────────────────────────────── */
	.golden {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
		padding: 22px 20px 20px;
		border-radius: var(--v3-radius-xl);
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		text-align: center;
		box-shadow: var(--v3-elev-2);
	}

	.golden-label {
		font-size: 17px;
		font-weight: 650;
		line-height: 24px;
	}

	.golden-clock {
		font-size: 68px;
		font-weight: 680;
		line-height: 76px;
	}

	.golden-elapsed {
		max-width: 30rem;
		font-size: var(--v3-text-meta);
		line-height: 20px;
		opacity: 0.88;
	}

	.head h1 {
		margin: 4px 4px 0;
		font-size: 30px;
		font-weight: 680;
		line-height: 38px;
	}

	.head p {
		margin: 4px 4px 0;
		color: var(--v3-t2);
		font-size: 17px;
		line-height: 24px;
	}

	.back {
		min-height: 44px;
		padding: 0 8px;
		border: 0;
		background: transparent;
		color: var(--v3-brand-text);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	/* ── the phase rail: four large steps ──────────────────────────────── */
	.rail {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 6px;
		margin: 4px 0 0;
		padding: 0;
		list-style: none;
	}

	.step {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		padding: 0 2px;
		color: var(--v3-t2);
		text-align: center;
	}

	/* the connecting rule */
	.step + .step::before {
		content: '';
		position: absolute;
		top: 21px;
		right: 50%;
		width: 100%;
		height: 3px;
		background: var(--v3-line-2);
	}

	.step.done + .step::before,
	.step.is-selected::before {
		background: var(--v3-brand-strong);
	}

	.dot {
		position: relative;
		z-index: 1;
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		border-radius: 50%;
		background: var(--v3-s1);
		box-shadow: inset 0 0 0 2px var(--v3-line-3);
		color: var(--v3-t2);
		font-size: 18px;
		font-weight: 650;
	}

	.step.done .dot {
		background: var(--v3-brand-strong);
		box-shadow: none;
		color: var(--v3-on-brand);
	}

	/* the current step: a ring AND bold words (the global .is-selected veil is for data rows) */
	.step.is-selected {
		background: transparent !important;
		box-shadow: none !important;
		color: var(--v3-t1);
	}

	.step.is-selected .dot {
		box-shadow:
			inset 0 0 0 3px var(--v3-brand-strong),
			0 0 0 4px var(--v3-brand-veil);
		color: var(--v3-t1);
	}

	.word {
		font-size: 15px;
		font-weight: 600;
		line-height: 20px;
		overflow-wrap: anywhere;
	}

	.step.is-selected .word {
		font-weight: 700;
	}

	/* ── notes ─────────────────────────────────────────────────────────── */
	.mode-note,
	.emulated-withheld {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 10px;
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 20px;
	}

	.note-text {
		flex: 1 1 14rem;
		min-width: 0;
	}

	.rail-note {
		margin: 0;
		padding: 14px 16px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
		font-size: 17px;
		line-height: 24px;
	}

	.done-note {
		border-color: var(--v3-ok);
		background: var(--v3-ok-veil);
	}

	/* ── state cards ───────────────────────────────────────────────────── */
	.state-card {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 20px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
		box-shadow: var(--v3-elev-1);
	}

	.state-card h2 {
		margin: 0;
		font-size: 24px;
		font-weight: 680;
		line-height: 32px;
	}

	.state-card p {
		margin: 0;
	}

	.evaluating,
	.awaiting {
		flex-direction: row;
		align-items: center;
		gap: 16px;
	}

	.awaiting p {
		margin-top: 4px;
		color: var(--v3-t2);
		font-size: 16px;
		line-height: 24px;
	}

	.pulse {
		flex: none;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: var(--v3-brand-strong);
		box-shadow: 0 0 0 0 var(--v3-brand-veil);
		animation: pulse 1.6s var(--v3-ease) infinite;
	}

	@keyframes pulse {
		70% {
			box-shadow: 0 0 0 16px transparent;
		}
		100% {
			box-shadow: 0 0 0 0 transparent;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.pulse {
			animation: none;
			box-shadow: 0 0 0 6px var(--v3-brand-veil);
		}
	}

	.ref,
	.poll-note,
	.doctrine,
	.scripted-approval,
	.unit-note,
	.window-source,
	.primed-when {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 20px;
	}

	.reach,
	.cross {
		font-size: 18px;
	}

	/* the open window is the 108 green corridor: the clear green, with words */
	.window-open {
		border-color: var(--v3-ok);
		background: var(--v3-ok-veil);
	}

	.open-title,
	.primed-title {
		font-size: 26px;
	}

	.window-open .open-title {
		color: var(--v3-ok-text);
	}

	/* the label small, the number the biggest thing on the page */
	.countdown {
		display: flex;
		flex-direction: column;
		margin: 0;
		font-size: 22px;
		font-weight: 650;
		line-height: 30px;
	}

	.cd-l {
		color: var(--v3-t2);
		font-size: 18px;
		line-height: 26px;
	}

	.cd-n {
		font-size: 64px;
		font-weight: 700;
		line-height: 72px;
	}

	.corridor-block {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-top: 6px;
	}

	.corridor-block h3 {
		margin: 0;
		font-size: 17px;
		font-weight: 650;
	}

	.map-wrap {
		overflow: hidden;
		border-radius: var(--v3-radius-l);
	}

	.map-wrap :global(.light-map) {
		border-radius: var(--v3-radius-l);
	}

	.unit {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px 10px;
		margin: 0;
		font-size: 16px;
	}

	/* ── the request card ──────────────────────────────────────────────── */
	.request-card {
		display: flex;
		flex-direction: column;
		gap: 18px;
		padding: 20px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
		box-shadow: var(--v3-elev-1);
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}

	.lbl,
	legend {
		padding: 0;
		font-size: 17px;
		font-weight: 650;
		line-height: 24px;
	}

	.field select,
	.field input {
		box-sizing: border-box;
		width: 100%;
		min-width: 0;
		height: 56px;
		padding: 0 14px;
		border: 1px solid var(--v3-line-3);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		font-size: 18px;
	}

	.field select:focus-visible,
	.field input:focus-visible,
	.urg:focus-visible,
	.big:focus-visible,
	.again:focus-visible,
	.back:focus-visible {
		outline: 2px solid var(--v3-brand-strong);
		outline-offset: 2px;
	}

	.urgency {
		min-width: 0;
		margin: 0;
		padding: 0;
		border: 0;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 8px;
	}

	.urg {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		min-height: 48px;
		padding: 0 18px;
		border: 1px solid var(--v3-line-3);
		border-radius: 24px;
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		font-size: 17px;
		font-weight: 600;
		cursor: pointer;
	}

	/* the chosen urgency: ticked and filled ink — words and a mark, never colour alone */
	.urg.is-selected {
		border-color: var(--v3-primary-bg);
		background: var(--v3-primary-bg) !important;
		box-shadow: none !important;
		color: var(--v3-primary-ink);
	}

	.request-row {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.big {
		min-height: 60px;
		padding: 0 24px;
		border: 0;
		border-radius: var(--v3-radius-l);
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		font: inherit;
		font-size: 20px;
		font-weight: 680;
		cursor: pointer;
		transition: background var(--v3-dur-1) var(--v3-ease);
	}

	.big:hover:not(:disabled) {
		background: var(--v3-primary-hover);
	}

	.big:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.request-hint {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 20px;
	}

	.request-error {
		margin: 0;
		padding: 12px 14px;
		border: 1px solid var(--v3-line-3);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		font-size: 16px;
		line-height: 24px;
	}

	.after-action p {
		margin: 0;
		color: var(--v3-t2);
		font-size: 16px;
		line-height: 24px;
	}

	.again {
		align-self: flex-start;
		min-height: 48px;
		padding: 0 18px;
		border: 1px solid var(--v3-line-3);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	/* ── empty and footer ──────────────────────────────────────────────── */
	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		padding: 20px 16px 4px;
		text-align: center;
	}

	.empty-scene {
		display: block;
		width: 100%;
		height: 150px;
		margin-bottom: 8px;
		object-fit: cover;
		border-radius: var(--v3-radius-l);
	}

	/* V3-P7: the 108 ambulance's studio shot heads the driver page, its service's mark beside it */
	.head-pic {
		position: relative;
		display: block;
		width: 200px;
		margin: 0 auto 4px;
	}

	.head-pic :global(.shot) {
		width: 200px;
		height: auto;
	}

	.head-mark {
		position: absolute;
		right: -8px;
		bottom: 8px;
	}

	.empty-t {
		margin: 0;
		font-size: 20px;
		font-weight: 650;
		line-height: 28px;
	}

	.empty-h {
		margin: 0;
		color: var(--v3-t2);
		font-size: 16px;
		line-height: 24px;
	}

	.control-room h3 {
		margin: 0;
		font-size: 17px;
		font-weight: 650;
	}

	.control-room p,
	.baseline,
	.demo {
		margin: 2px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 20px;
	}

	@media (max-width: 420px) {
		.golden-clock {
			font-size: 60px;
			line-height: 68px;
		}

		.word {
			font-size: 14px;
		}

		.cd-n {
			font-size: 56px;
			line-height: 64px;
		}
	}
</style>
