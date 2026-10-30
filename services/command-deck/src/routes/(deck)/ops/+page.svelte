<script lang="ts">
	/**
	 * /ops — the situation wall (SPEC §6.3; ownership UI-S5B).
	 *
	 *   header 44        "Situation · Mumbai · whole city", range presets,
	 *                    "As of hh:mm:ss IST", Share (the view header's:
	 *                    `data-share`), Refresh
	 *   metric strip 76  eight figures, exactly four commander counters
	 *                    (`data-prim="data-tile"` + `data-counter`)
	 *   .wall-grid       minmax(432px,3fr) | minmax(440px,4fr) | minmax(380px,3fr),
	 *                    each `.col` scrolling inside itself:
	 *     col 1  Decisions (DecisionQueue, with its `top` slot left empty for
	 *            the ConvoyCard, UI-S6A)
	 *     col 2  the City map tile (chrome v2, hud wall) and Corridor operations
	 *     col 3  City band · City signal plans · Active movement adaptation ·
	 *            Dispatch · Watchlist and retention · Feeds and services ·
	 *            Lab and system (collapsed)
	 *   .audit-band      220 px (172 below 1000 px tall): the audit (AuditStream)
	 *
	 * The navbar carries what is page-owned (plan R10/X12): the duty-officer
	 * input, the Data button (the decision model's posture and the wall's
	 * feeds), the Exercise-data tag, the band tag and its age, the Inbox count
	 * (decision units), and the search, which opens the canvas's omnibar (the
	 * page's only one, plan X25). There is no Share in the navbar.
	 *
	 * Selecting any row selects the object everywhere and opens the
	 * ObjectInspector as a 400 px drawer on the right: docked beside the
	 * columns on a wall ≥ 1680 px wide (the wall's selected live event shows
	 * there from load, as the board's selected row), sliding over the right
	 * column on a narrower screen (only when the operator picks a row). Its ✕
	 * or Esc closes it.
	 *
	 * Deep links: /ops#evt=<id> selects the event once the board carries it;
	 * #rec= and #dsp= scroll their card into view and mark it for 3 s (the
	 * decision stays the officer's) — retried until the first polls rendered
	 * it (20 s at most). Every id is validated (safePathId).
	 *
	 * Operator gate on and nobody signed in: the wall is not mounted (no
	 * operator poller fires, no 403 per panel); one sign-in card stands in.
	 */
	import { onDestroy, onMount, tick } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { safePathId } from '$lib/ops/endpoints';
	import { godsEye } from '$lib/gods-eye/store.svelte';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { fusionFeed } from '$lib/gods-eye/hud/feed.svelte';
	import { buildShareUrl } from '$lib/gods-eye/share-link';
	import { GODS_EYE_LAYER_IDS } from '$lib/gods-eye/layers';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { toasts } from '$lib/shell/toast.svelte';
	import OperatorSignIn from '$lib/shell/OperatorSignIn.svelte';
	import { registerProviders } from '$lib/workspace/providers';
	import { selectors } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { Input, Section, provideUiLang } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.wall';
	import '$lib/i18n/packs.corridor';
	import { tOps } from '$lib/i18n/strings.ops';
	import DecisionQueue from '$lib/ops/components/DecisionQueue.svelte';
	import { liveStripFeed } from '$lib/decisions/live';
	import { flowProvenance } from '$lib/corridor/events';
	import EventBoard from '$lib/ops/components/EventBoard.svelte';
	import SituationBandPanel from '$lib/ops/components/SituationBandPanel.svelte';
	import SignalGateCard from '$lib/ops/components/SignalGateCard.svelte';
	import AMAModuleCard from '$lib/ops/components/AMAModuleCard.svelte';
	import DispatchTiles from '$lib/ops/components/DispatchTiles.svelte';
	import WatchlistConsole from '$lib/ops/components/WatchlistConsole.svelte';
	import AuditStream from '$lib/ops/components/AuditStream.svelte';
	import WallHeader from '$lib/decisions/wall/WallHeader.svelte';
	import MetricStrip from '$lib/decisions/wall/MetricStrip.svelte';
	import MapTile from '$lib/decisions/wall/MapTile.svelte';
	import FeedsSection from '$lib/decisions/wall/FeedsSection.svelte';
	import LabSection from '$lib/decisions/wall/LabSection.svelte';
	import InspectorDrawer from '$lib/decisions/wall/InspectorDrawer.svelte';
	import { wallData } from '$lib/decisions/wall/wall-data.svelte';
	import { hourlyBins, metricCells, sourceMix } from '$lib/decisions/wall/metrics';
	import { dataFeeds, feedRows, worstStatus } from '$lib/decisions/wall/feeds';
	import { DEFAULT_RANGE, asRange, rangeWindow, type WallRange } from '$lib/decisions/wall/range';
	import { WALL_VIEW } from '$lib/decisions/wall/share';
	import { countable, historyCount } from '$lib/decisions/wall/provenance';
	import { ensurePursuitSection } from '$lib/decisions/wall/pursuit-bridge';
	import { ensureUnitsSource } from '$lib/decisions/wall/units-bridge';
	import '$lib/decisions/wall/wall.css';

	provideUiLang(() => ops.lang);
	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	/** The operator gate's state is known (or the read gave up): mount the wall, or the sign-in. */
	let sessionWaitOver = $state(false);
	const sessionKnown = $derived(ops.sessionGate !== null || sessionWaitOver);

	// ── the viewport (the drawer, the sparklines, the folded navbar officer) ─
	let vw = $state(1920);
	/** ≥ 1680: the drawer docks beside the columns (nothing is covered). */
	const wideWall = $derived(vw >= 1680);
	/** ≥ 1600: the metric strip's sparklines. */
	const sparkWide = $derived(vw >= 1600);
	/** < 1440: the navbar folds the officer into an avatar; the Decisions column shows the field (SPEC §3.7). */
	const officerInColumn = $derived(vw < 1440);

	// ── clocks ──────────────────────────────────────────────────────────────
	let now = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(id);
	});

	// ── the range (per viewer: remembered in this browser only) ─────────────
	const RANGE_KEY = 'sajag.ops.range';
	let range = $state<WallRange>(DEFAULT_RANGE);
	const window_ = $derived(rangeWindow(range, Math.floor(now / 30_000) * 30_000));

	function setRange(r: WallRange) {
		range = r;
		try {
			localStorage.setItem(RANGE_KEY, r);
		} catch {
			// storage unavailable (private mode): the choice holds for this visit
		}
	}

	// ── the Lab section (collapsed on every load, plan X23) ─────────────────
	let labOpen = $state(false);

	// ── the inspector drawer ────────────────────────────────────────────────
	/** The wall's selected event the operator closed the drawer on (it stays closed for it). */
	let dismissedEvent = $state<string | null>(null);
	/** The live event the board has selected (fixtures are not city objects). */
	const wallEventUrn = $derived.by(() => {
		const ev = ops.selectedEvent;
		return ev && ev.source !== 'offline-fixture' ? `event:${ev.eventId}` : null;
	});
	const drawerUrn = $derived(
		selection.current ?? (wideWall && wallEventUrn && dismissedEvent !== ops.selectedEventId ? wallEventUrn : null),
	);

	// a new board selection may show again; clearing the selection closes the drawer on the wall's event
	let lastSelection: string | null = null;
	$effect(() => {
		const cur = selection.current;
		if (lastSelection && !cur) dismissedEvent = ops.selectedEventId;
		lastSelection = cur;
	});
	let lastEvent: string | null = null;
	$effect(() => {
		const id = ops.selectedEventId;
		if (lastEvent !== null && id !== lastEvent && dismissedEvent !== id) dismissedEvent = null;
		lastEvent = id;
	});

	function closeDrawer() {
		dismissedEvent = ops.selectedEventId;
		if (selection.current) selection.clear();
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key !== 'Escape' || e.defaultPrevented || !drawerUrn) return;
		const tgt = e.target as HTMLElement | null;
		if (tgt && (tgt.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(tgt.tagName))) return;
		if (workspace.omnibar.open || document.querySelector('[data-ui="popover"], [data-ui-overlay="modal"]')) return;
		closeDrawer();
	}

	// ── deep links: #evt= / #rec= / #dsp= ───────────────────────────────────
	let deepTimer: ReturnType<typeof setTimeout> | null = null;
	let deepToken = 0;

	/** The deep link in a hash, validated; null when the hash carries none. */
	function parseDeepLink(hash: string): { kind: 'evt' | 'rec' | 'dsp'; id: string } | null {
		const params = new URLSearchParams(hash.replace(/^#/, ''));
		for (const kind of ['evt', 'rec', 'dsp'] as const) {
			const id = safePathId(params.get(kind));
			if (id) return { kind, id };
		}
		return null;
	}

	/** The card a rec / dsp link points at, once it is rendered. */
	function cardFor(kind: 'rec' | 'dsp', id: string): HTMLElement | null {
		const q = (sel: string) => document.querySelector<HTMLElement>(sel);
		const esc = CSS.escape(id);
		if (kind === 'rec') {
			return q(`[data-testid="queue-card"][data-kind="echallan"][data-id="${esc}"]`) ?? q(`[data-testid="queue-card"][data-rec-ids~="${esc}"]`);
		}
		return q(`[data-testid="queue-card"][data-kind="corridor-request"][data-id="${esc}"]`) ?? q(`[data-testid="dispatch-tile"][data-dispatch-id="${esc}"]`);
	}

	/** Bring the card into view and mark it for 3 s (its decision stays the officer's). */
	function highlight(el: HTMLElement) {
		const target = (el.firstElementChild as HTMLElement | null) && el.matches('.card-wrap, [style*="contents"]') ? (el.firstElementChild as HTMLElement) : el;
		target.scrollIntoView({ block: 'center', behavior: 'smooth' });
		target.classList.add('deep-link-hit');
		setTimeout(() => target.classList.remove('deep-link-hit'), 3000);
	}

	/** Resolve the hash's deep link; retried until the first polls rendered its target (≤ 20 s). */
	function followDeepLink(started = Date.now(), token = ++deepToken) {
		if (deepTimer) clearTimeout(deepTimer);
		deepTimer = null;
		if (token !== deepToken) return;
		const link = parseDeepLink(location.hash);
		if (!link) return;
		let done = false;
		if (link.kind === 'evt') {
			if (ops.events.some((e) => e.eventId === link.id)) {
				if (ops.selectedEventId !== link.id) ops.selectEvent(link.id);
				selection.select(`event:${link.id}`, { source: 'share' });
				done = true;
			}
		} else {
			const el = cardFor(link.kind, link.id);
			if (el) {
				highlight(el);
				done = true;
			}
		}
		if (!done && Date.now() - started < 20_000) deepTimer = setTimeout(() => followDeepLink(started, token), 500);
	}

	const onHashChange = () => followDeepLink();

	// ── share and refresh ───────────────────────────────────────────────────
	async function share() {
		const url = buildShareUrl(WALL_VIEW, GODS_EYE_LAYER_IDS);
		try {
			await navigator.clipboard.writeText(url);
			toasts.push({ kind: 'act', title: L('wall_share_done'), body: L('wall_share_body') });
		} catch {
			toasts.push({ kind: 'error', title: L('wall_share_failed'), body: url });
		}
	}

	let refreshing = $state(false);
	async function refresh() {
		if (refreshing) return;
		refreshing = true;
		wallData.refresh();
		void cityRegistry.refresh();
		await Promise.allSettled([
			ops.pollBoard(true),
			ops.pollRecommendations(),
			ops.pollDispatches(),
			ops.pollCityBand(),
			ops.pollSignalPlans(),
			ops.pollWatchlist(),
			ops.pollRetention(),
			ops.pollBrain(),
			ops.pollTrafficFeed(),
			ops.pollAudit(true),
		]);
		refreshing = false;
	}

	// ── lifecycle ───────────────────────────────────────────────────────────
	onMount(() => {
		try {
			range = asRange(localStorage.getItem(RANGE_KEY));
		} catch {
			// storage unavailable: the default range
		}
		registerProviders();
		// wave-C bridges: each stands in only until UI-S5A's registration exists, under the same id
		ensurePursuitSection();
		ensureUnitsSource(() => ({
			recommendations: ops.recommendations,
			escorts: ops.escortProposals,
			dispatches: ops.dispatches,
			plate: (raw) => ops.plate(raw),
		}));
		godsEye.followSelection = true; // wall mode: selecting an event flies the camera to it
		ops.start();
		wallData.start();
		fusionFeed.start();
		const wait = setTimeout(() => (sessionWaitOver = true), 2500);
		window.addEventListener('hashchange', onHashChange);
		void tick().then(() => followDeepLink());
		return () => clearTimeout(wait);
	});

	onDestroy(() => {
		godsEye.followSelection = false;
		godsEye.subjectLockId = null;
		if (typeof window !== 'undefined') window.removeEventListener('hashchange', onHashChange);
		if (deepTimer) clearTimeout(deepTimer);
		deepToken++;
		fusionFeed.stop();
		wallData.stop();
		ops.stop();
	});

	// ── what the wall shows ─────────────────────────────────────────────────
	const units = $derived(selectors.decisionUnits());
	/** The active protected movement (the ConvoyCard slot and the LiveStrip follow it). */
	const movementLive = $derived(
		ops.events.some((e) => e.source !== 'offline-fixture' && e.eventKind === 'protected_movement' && e.state === 'active'),
	);
	const liveEvents = $derived(ops.events.filter((e) => e.source !== 'offline-fixture'));
	const TERMINAL = new Set(['completed', 'cancelled', 'deferred']);

	const reads = $derived.by(() => {
		void fusionFeed.rows;
		return selectors.watchReads(now - 24 * 3_600_000, now);
	});

	/** The flow's provenance, the metric strip's derivation (audit C S2): the
	 * traffic feed's label wins; before it answers, the corridor summary's
	 * provenance stands in ('emulated' reads as 'simulated'). The map tile's
	 * legend takes its "Simulated flow" item from the same label — a partly
	 * simulated ('mixed') feed is still a simulated flow. */
	const flowLabel = $derived(flowProvenance(ops.trafficFeed?.label, wallData.summary?.provenance ?? null));

	/** The units the unit feed reports on a dispatch (their positions are what the counters vouch for). */
	const dispatchedUnits = $derived.by(() => {
		void cityRegistry.version;
		return cityRegistry
			.byKind('unit')
			.filter((u) => typeof u.props.dispatch_id === 'string' || typeof u.props.assigned_event_id === 'string')
			.map((u) => ({ emulated: u.props.emulated === true || u.source === 'emulated', ambulance: u.props.agency === 'ambulance' }));
	});

	const cells = $derived.by(() => {
		const summary = wallData.summary;
		const label = flowLabel;
		const pending = [
			...ops.recommendations.filter((r) => r.status === 'pending').map((r) => Date.parse(r.createdAt ?? '')),
			...ops.dispatches.filter((d) => d.status === 'requested').map((d) => Date.parse(d.createdAt ?? '')),
		].filter(Number.isFinite);
		const deadlines = units.map((u) => u.deadline).filter((d): d is number => d != null && d > now);
		// the soonest decision by its own unit, so the metric names its real kind (never matched back by deadline)
		const soonest = units.filter((u) => u.deadline != null && u.deadline > now).reduce<(typeof units)[number] | null>((m, u) => (m == null || (u.deadline as number) < (m.deadline as number) ? u : m), null);
		const readVehicles = new Set(reads.flatMap((r) => r.urns.filter((u) => u.startsWith('vehicle:'))));
		return metricCells({
			lang,
			now,
			active: ops.counters.activeEvents,
			// test and rehearsal events are kept out of the counts (SPEC §9.2)
			open: countable(liveEvents.filter((e) => e.state !== 'completed' && e.state !== 'cancelled')).length,
			// the same rule as `open`: test and rehearsal rows are not history the wall counts (F-13)
			history: wallData.historyUpdated ? historyCount(wallData.history) : null,
			units: units.length,
			soonestDeadline: deadlines.length ? Math.min(...deadlines) : null,
			soonestKind: soonest?.kind ?? null,
			oldestWaiting: pending.length ? Math.min(...pending) : null,
			dispatched: ops.counters.unitsDispatched,
			dispatchesClosed: ops.dispatches.filter((d) => TERMINAL.has(d.status)).length,
			ambulance: ops.counters.ambulanceWindows,
			ambulanceClosed: ops.dispatches.filter((d) => d.agency === 'ambulance' && TERMINAL.has(d.status)).length,
			speedKmh: summary?.avgSpeedKmh ?? null,
			speedSource: label === 'simulated' || label === 'mixed' || label === 'live' || label === 'none' ? label : null,
			speedSamples: wallData.speedSamples,
			roads: summary?.totalSegments ?? null,
			congested: summary?.congestedSegments ?? null,
			critical: summary?.criticalSegments ?? null,
			reads24: reads.length,
			readVehicles: readVehicles.size,
			lastRead: reads.length ? Math.max(...reads.map((r) => r.t)) : null,
			readBins: hourlyBins(reads.map((r) => r.t), now),
			anomalies: selectors.count('anomaly'),
			// COPY-1: the units' and the reads' provenance, read off the feeds that carry it
			unitsSource: sourceMix(dispatchedUnits.map((u) => u.emulated)),
			ambulanceSource: sourceMix(dispatchedUnits.filter((u) => u.ambulance).map((u) => u.emulated)),
			readsSource: sourceMix(reads.map((r) => r.source === 'emulated')),
		});
	});

	const feeds = $derived.by(() => {
		void cityRegistry.version;
		const cams = cityRegistry.byKind('camera');
		const ents = cityRegistry.entities();
		const emulated = ents.length ? ents.filter((e) => e.source === 'emulated').length / ents.length : 0;
		const camFeed = cityRegistry.feed('camera');
		return feedRows(
			{
				now,
				registry: { status: cityRegistry.status, note: cityRegistry.note, size: cityRegistry.size, updatedAt: cityRegistry.updatedAt, emulatedShare: emulated },
				cityFeed: { status: fusionFeed.status, note: fusionFeed.note, rows: fusionFeed.rows.length, updatedAt: fusionFeed.updatedAt },
				traffic: {
					label: ops.trafficFeed?.label ?? null,
					note: ops.trafficFeedNote,
					segments: ops.trafficFeed?.segments ?? wallData.summary?.totalSegments ?? null,
					dataAgeSec: ops.trafficFeed?.dataAgeSec ?? null,
				},
				cameras: {
					feed: camFeed ? { status: camFeed.status, count: camFeed.count, ageSec: camFeed.ageSec } : null,
					source: cams.length && cams.every((c) => c.source === 'emulated') ? 'emulated' : cams.length ? 'live' : null,
				},
				board: { status: ops.boardStatus, updated: ops.boardUpdated, open: liveEvents.length },
				model: { brain: ops.brain, tier: ops.brain?.degradationTier ?? null },
				emulator: { online: ops.emulator.online, lastChecked: ops.emulator.lastChecked, tapes: ops.emulatorLibrary.length },
			},
			lang,
		);
	});

	/** The newest answer behind the wall ("As of"), never the wall clock. */
	const asOf = $derived(
		Math.max(ops.boardUpdated, ops.recommendationsUpdated, ops.dispatchesUpdated, ops.cityBandUpdated, ops.signalPlansUpdated, ops.watchlistUpdated) || null,
	);

	// ── the navbar (plan R10/X12) ───────────────────────────────────────────
	$effect(() => {
		commandBar.lang = ops.lang;
		commandBar.onLangChange = (l: string) => (ops.lang = l);
		commandBar.onShare = null;
		commandBar.live = liveStripFeed({ route: '/ops' });
		commandBar.onSearch = (q?: string) => workspace.openOmnibar(q);
		commandBar.onInbox = () => {
			const el = document.querySelector<HTMLElement>('[data-wall="decisions"]');
			el?.scrollIntoView({ block: 'start', behavior: 'smooth' });
			el?.querySelector<HTMLElement>('[data-testid="queue-card"] [data-row-toggle], [data-testid="queue-card"] button')?.focus();
		};
	});

	$effect(() => {
		commandBar.officer = {
			value: ops.dutyOfficer,
			fromSession: ops.dutyOfficerFromSession,
			set: (v: string) => ops.setDutyOfficer(v),
		};
	});

	$effect(() => {
		const b = ops.brain;
		const latch = b?.decider.latch ?? null;
		commandBar.dataStatus = {
			decider: b ? (b.reachable ? b.decider.state : 'unreachable') : 'unknown',
			tier: b?.degradationTier ?? '',
			p95: b?.decider.p95Ms != null ? b.decider.p95Ms / 1000 : null,
			novelty: latch === 'armed' || latch === 'tripped',
			feeds: dataFeeds(feeds, lang),
			worst: worstStatus(feeds),
		};
	});

	$effect(() => {
		const f = ops.trafficFeed;
		commandBar.exercise =
			f && (f.label === 'simulated' || f.label === 'mixed')
				? {
						label: f.label,
						text:
							f.label === 'simulated'
								? L('wall_exercise_simulated', f.segments)
								: L('wall_exercise_mixed', Math.round((100 * f.synthetic) / Math.max(1, f.real + f.synthetic))),
					}
				: null;
	});

	/** The navbar's band: the city band (never a guessed Green; Unknown while its engine poll fails). */
	$effect(() => {
		const city = ops.cityBand;
		const band = city ? (city.stale ? null : city.band) : ops.bandSourceKind === 'city-band' ? ops.band : null;
		commandBar.band = band;
		commandBar.bandSource = city
			? city.stale
				? ops.bandSource
				: city.simulatedFeed
					? L('wall_band_source_city_sim')
					: L('wall_band_source_city')
			: band
				? ops.bandSource
				: null;
	});

	$effect(() => {
		const at = ops.cityBand?.evaluatedAt ?? (ops.cityBandUpdated || null);
		commandBar.bandAgeSec = at && commandBar.band ? Math.max(0, (Date.now() - at) / 1000) : null;
	});

	$effect(() => {
		const n = units.length;
		commandBar.inboxCount = n;
		commandBar.inboxIntent = n > 0 ? 'warning' : 'none';
	});
</script>

<svelte:head>
	<title>{L('wall_title')} · Sajag</title>
</svelte:head>

<svelte:window bind:innerWidth={vw} onkeydown={onKeydown} />

{#if ops.signInRequired}
	<!-- Gate on, nobody signed in: one card, no wall, no pollers. -->
	<div class="signin-wall" data-testid="ops-signin-required">
		<div class="signin-card">
			<h2>{tOps(lang, 'opsSigninTitle')}</h2>
			<p>{tOps(lang, 'opsSigninBody')}</p>
			<OperatorSignIn {lang} inline />
		</div>
	</div>
{:else if !sessionKnown}
	<div class="wall pending" aria-busy="true"></div>
{:else}
	<div class="wall" data-template="situation-wall">
		{#if ops.sessionLapsed}
			<p class="lapsed" data-testid="ops-session-lapsed">{tOps(lang, 'opsSessionLapsed')}</p>
		{/if}
		<WallHeader {lang} {range} onrange={setRange} {asOf} onshare={() => void share()} onrefresh={() => void refresh()} {refreshing} />
		<MetricStrip {cells} wide={sparkWide} />

		<div class="wall-main">
			<div class="wall-grid" class:with-drawer={!!drawerUrn && wideWall}>
				<!-- col 1 — the decisions -->
				<div class="col col-decisions">
					<Section title={L('wall_decisions')} icon="inbox" level={2} sub={units.length ? String(units.length) : null} data-prim="panel" data-wall="decisions">
						{#if officerInColumn}
							<div class="officer-row">
								<span class="o-label">{t(lang, 'shell_officer')}</span>
								<Input
									small
									fill
									class="officer-input"
									value={ops.dutyOfficer}
									readonly={ops.dutyOfficerFromSession}
									placeholder={t(lang, 'shell_officer_roster')}
									aria-label={t(lang, 'shell_officer')}
									title={t(lang, 'shell_officer_helper')}
									autocomplete="off"
									spellcheck="false"
									maxlength={64}
									oninput={(e: Event) => ops.setDutyOfficer((e.currentTarget as HTMLInputElement).value)}
								/>
							</div>
						{/if}
						<DecisionQueue>
							{#snippet top()}
								{#if movementLive}
									{#await import('$lib/corridor/ConvoyCard.svelte') then card}
										{@const ConvoyCard = card.default}
										<ConvoyCard variant="wall" {lang} {now} />
									{/await}
								{/if}
							{/snippet}
						</DecisionQueue>
					</Section>
				</div>

				<!-- col 2 — the city and its corridor operations -->
				<div class="col col-map">
					<MapTile {lang} simulatedFlow={flowLabel === 'simulated' || flowLabel === 'mixed'} focusUrn={drawerUrn} />
					<EventBoard window={window_} />
				</div>

				<!-- col 3 — band, signals, adaptation, dispatch, watchlist, feeds, lab -->
				<div class="col col-status">
					<SituationBandPanel window={window_} />
					<SignalGateCard />
					<AMAModuleCard />
					<DispatchTiles />
					<WatchlistConsole />
					<FeedsSection rows={feeds} {lang} />
					<LabSection {lang} bind:open={labOpen} />
				</div>

				{#if drawerUrn && wideWall}
					<InspectorDrawer urn={drawerUrn} docked {lang} onclose={closeDrawer} />
				{/if}
			</div>
			{#if drawerUrn && !wideWall}
				<InspectorDrawer urn={drawerUrn} docked={false} {lang} onclose={closeDrawer} />
			{/if}
		</div>

		<!-- the audit band (its own scroll strip) -->
		<div class="audit-band">
			<AuditStream />
		</div>
	</div>
{/if}

<style>
	.wall {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-width: 0;
		min-height: 0;
		height: 100%;
		overflow: hidden;
		background: var(--v-canvas);
	}

	.wall-main {
		position: relative;
		display: flex;
		flex: 1 1 auto;
		min-width: 0;
		min-height: 0;
	}

	.wall-grid {
		display: grid;
		flex: 1 1 auto;
		grid-template-columns: minmax(432px, 3fr) minmax(440px, 4fr) minmax(380px, 3fr);
		grid-template-rows: minmax(0, 1fr);
		min-width: 0;
		min-height: 0;
	}

	.wall-grid.with-drawer {
		grid-template-columns: minmax(432px, 3fr) minmax(440px, 4fr) minmax(380px, 3fr) 400px;
	}

	.col {
		display: flex;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
		overflow-x: hidden;
		overflow-y: auto;
		overscroll-behavior: contain;
		background: var(--v-surface-1);
		scrollbar-width: thin;
	}

	.col + .col {
		border-left: 1px solid var(--v-line-2);
	}

	/* panels keep their natural height: the column scrolls instead of squashing them */
	.col > :global(*) {
		flex: 0 0 auto;
	}

	.officer-row {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 16px;
		border-bottom: 1px solid var(--v-line-1);
	}

	.o-label {
		flex: 0 0 auto;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.officer-row :global(.officer-input) {
		flex: 1 1 auto;
		min-width: 0;
	}

	.audit-band {
		display: flex;
		flex: 0 0 220px;
		flex-direction: column;
		min-width: 0;
		height: 220px;
		overflow: hidden;
		border-top: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
	}

	@media (max-height: 999px) {
		.audit-band {
			flex-basis: 172px;
			height: 172px;
		}
	}

	/* a phone: the wall's three columns stack in one scroll (decisions, the map tile, the record), then the audit band */
	@media (max-width: 720px) {
		.wall {
			overflow-x: hidden;
			overflow-y: auto;
		}

		.wall-main {
			flex: none;
		}

		.wall-grid,
		.wall-grid.with-drawer {
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: none;
			grid-auto-rows: auto;
		}

		.col {
			overflow: visible;
		}

		.col + .col {
			border-left: 0;
			border-top: 1px solid var(--v-line-2);
		}

		.audit-band {
			flex: none;
		}
	}

	/* the audit probe's answer gets room: the band grows while it is open */
	.audit-band:has(:global([data-probe-open])) {
		flex-basis: clamp(300px, 38vh, 420px);
		height: clamp(300px, 38vh, 420px);
	}

	.audit-band > :global(*) {
		flex: 1 1 auto;
		min-height: 0;
	}

	.lapsed {
		margin: 0;
		padding: 6px 16px;
		background: var(--v-warning-veil);
		color: var(--v-ink-1);
		font-size: var(--v-text-xs);
		border-bottom: 1px solid var(--v-line-2);
	}

	/* a deep link's target: outlined for 3 s, then back to the wall's rhythm */
	.wall :global(.deep-link-hit) {
		outline: 2px solid var(--v-primary-text);
		outline-offset: -2px;
	}

	/* audit C item 12, fix round 2 (audit E item 3): the credits are ONE
	   compact line in the tile's own bottom-right corner — the logos, the
	   first attribution and Cesium's "Data attribution" lightbox link (the
	   full list opens in the lightbox) — never a max-height clamp that cut a
	   line mid-height and pushed the link out of view, and clear of the
	   readout and the scale bar at the left */
	.wall :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom) {
		max-width: min(40%, 250px); /* clear of the scale bar at every console size (audit E R2) */
	}

	.wall :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom .cesium-widget-credits) {
		display: flex;
		flex-wrap: nowrap;
		align-items: center;
		min-width: 0;
	}

	.wall :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom .cesium-credit-logoContainer) {
		flex: 0 0 auto;
	}

	.wall :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom .cesium-credit-logoContainer img) {
		height: 14px;
	}

	.wall :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom .cesium-credit-expand-link) {
		flex: 0 0 auto;
		white-space: nowrap;
	}

	.wall :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom .cesium-credit-textContainer) {
		flex: 0 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* ── operator gate: sign-in required (no wall mounted) ─────────────── */
	.signin-wall {
		display: grid;
		place-items: center;
		height: 100%;
		padding: 16px;
	}

	.signin-card {
		display: flex;
		flex-direction: column;
		gap: 12px;
		width: min(440px, 100%);
		padding: 20px;
		background: var(--v-surface-1);
		border-radius: var(--v-radius-panel);
		box-shadow: var(--v-elev-1);
	}

	.signin-card h2 {
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
		color: var(--v-ink-1);
	}

	.signin-card p {
		margin: 0;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}
</style>
