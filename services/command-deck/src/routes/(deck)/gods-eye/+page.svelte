<script lang="ts">
	/**
	 * `/gods-eye` — CITY, MAP MODE (SPEC §6.2): the workspace frame in map
	 * mode — the full-bleed God's-eye canvas (chrome v2) below the navbar and
	 * the LiveStrip, the docks collapsed (the bottom dock to its 36 px
	 * header), the City vitals CARD floating at the top right (publishing
	 * `__GODS_EYE__.vitals`), and the left dock's Info tab with the full
	 * vitals when opened. `[`, `]`, `\` or the rail open the docks; `Esc`
	 * never navigates; "Exit map mode" (`.chip.exit`) restores the docks on
	 * this route. Idle orbit after 30 s is allowed when nothing is selected.
	 *
	 * Replay is allowed here (SPEC §7.3): live layers stand down as the
	 * canvas does today, the banner names the run, and the LiveStrip and the
	 * inbox stay live — a live interrupt shows in the strip with its Review.
	 * The omnibar is the canvas-mounted one (hud="full", plan X25).
	 *
	 * One Share, in the pane header (`data-share`). The canvas's own camera
	 * and layers hash carries the view.
	 *
	 * Operator gate on and nobody signed in: the canvas is not mounted — one
	 * sign-in panel stands in (no pollers behind it).
	 */
	import { onDestroy, onMount } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import OperatorSignIn from '$lib/shell/OperatorSignIn.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { godsEye } from '$lib/gods-eye/store.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { fusionFeed } from '$lib/gods-eye/hud/feed.svelte';
	import { replay } from '$lib/gods-eye/hud/replay.svelte';
	import GodsEyeCanvas from '$lib/gods-eye/GodsEyeCanvas.svelte';
	import CityVitals from '$lib/gods-eye/hud/CityVitals.svelte';
	import WorkspaceFrame from '$lib/workspace/components/WorkspaceFrame.svelte';
	import { registerProviders } from '$lib/workspace/providers';
	import { liveWorld, selectors } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { Button, provideUiLang } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.wall';
	import { parseUnitKey } from '$lib/decisions/homes';
	import { liveStripFeed, openPursuits } from '$lib/decisions/live';
	import { corridor } from '$lib/ops/components/template/corridor.svelte';
	import { dataFeeds, feedRows, worstStatus } from '$lib/decisions/wall/feeds';

	provideUiLang(() => ops.lang);
	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	/** The operator gate's state is known (or the read gave up): mount the map, or the sign-in. */
	let sessionWaitOver = $state(false);
	const sessionKnown = $derived(ops.sessionGate !== null || sessionWaitOver);

	// ── the canvas props (the workspace's state) ────────────────────────────
	const protectedSet = $derived(selectors.protectedUrns());
	const selectionItems = $derived(selection.items);
	/** Idle orbit after 30 s, allowed only while nothing is selected (the canvas enforces the selection rule). */
	const idleOrbit = $derived(true);

	/** "Exit map mode": restore the docks on THIS route (never navigate). */
	function exitMapMode() {
		workspace.docks = { left: true, right: true, bottom: 'compact' };
	}

	/** The map-mode dock collapse on ENTRY: docks closed; the bottom dock compact (replay reachable). */
	function collapseForMapMode() {
		workspace.docks = { left: false, right: false, bottom: 'compact' };
	}

	// ── map mode's collapsed docks (the page's default, SPEC §6.2) ──────────
	const units = $derived(selectors.decisionUnits());
	const movementLive = $derived(
		ops.events.some((e) => e.source !== 'offline-fixture' && e.eventKind === 'protected_movement' && e.state === 'active'),
	);
	const pursuitLive = $derived(openPursuits(ops).length > 0);

	/** The vitals CARD stands down while the Info tab shows the full vitals: one variant at a time (§12.1.2). */
	const leftTab = $derived(workspace.leftTab);
	const leftOpen = $derived(workspace.docks.left);
	/* the rail's Info tab is this route's ONLY left tab: the frame resolves an
	   empty tab id to it (so ` [` opens Info whatever way), and the card must
	   stand down for it the same — audit C S1's probe counted two city-vitals */
	const leftTabId = $derived(leftTab || 'info');
	const cardMounted = $derived(!(leftOpen && leftTabId === 'info'));

	onMount(() => {
		godsEye.followSelection = false; // map mode: a free camera; selections fly on request
		registerProviders();
		ops.start();
		fusionFeed.start();
		const wait = setTimeout(() => (sessionWaitOver = true), 2500);
		// the docks collapse on entry (map mode), wherever the operator came from;
		// the bottom dock keeps its compact timeline — the Live/Replay control and
		// the tape live there (replay is allowed in map mode, SPEC §7.3)
		workspace.docks = { left: false, right: false, bottom: 'compact' };
		openUnitFromHash();
		return () => clearTimeout(wait);
	});

	onDestroy(() => {
		godsEye.followSelection = false;
		godsEye.subjectLockId = null;
		if (replay.mode === 'replay') replay.exit();
		selection.clear();
		ops.stop();
		fusionFeed.stop();
	});

	// a selection opens the inspector (the right dock): the operator picked an
	// object; Esc clears it and the dock stays as they left it
	let lastSelection = $state<string | null | undefined>(undefined);
	$effect(() => {
		const sel = selection.current;
		const picked = lastSelection !== undefined && sel !== lastSelection && !!sel;
		lastSelection = sel;
		if (picked) {
			workspace.rightTab = 'inspector';
			workspace.setDock('right', true);
		}
	});

	/** Deep links: #inbox=<kind:id> / #movement=<kind:id> (the homes' hrefs) open their tab behind the map. */
	function openUnitFromHash() {
		if (typeof location === 'undefined') return;
		const params = new URLSearchParams(location.hash.replace(/^#/, ''));
		for (const key of ['inbox', 'movement'] as const) {
			const parsed = parseUnitKey(params.get(key));
			if (!parsed) continue;
			const unit = units.find((u) => u.kind === parsed.kind && u.id === parsed.id);
			if (!unit) continue;
			workspace.openDecisionHome(unit, '/gods-eye');
			return;
		}
		workspace.fromHash(location.hash);
	}

	// ── the command bar (plan R10/X12) ──────────────────────────────────────
	let now = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(id);
	});

	const feeds = $derived.by(() => {
		void cityRegistry.version;
		const summary = corridor.row;
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
					label: ops.trafficFeed?.label ?? (summary?.provenance === 'emulated' ? 'simulated' : (summary?.provenance ?? null)),
					note: ops.trafficFeedNote,
					segments: ops.trafficFeed?.segments ?? summary?.totalSegments ?? null,
					dataAgeSec: ops.trafficFeed?.dataAgeSec ?? null,
				},
				cameras: {
					feed: camFeed ? { status: camFeed.status, count: camFeed.count, ageSec: camFeed.ageSec } : null,
					source: cams.length && cams.every((c) => c.source === 'emulated') ? 'emulated' : cams.length ? 'live' : null,
				},
				board: { status: ops.boardStatus, updated: ops.boardUpdated, open: ops.events.filter((e) => e.source !== 'offline-fixture').length },
				model: { brain: ops.brain, tier: ops.brain?.degradationTier ?? null },
				emulator: { online: ops.emulator.online, lastChecked: ops.emulator.lastChecked, tapes: ops.emulatorLibrary.length },
			},
			lang,
		);
	});

	$effect(() => {
		commandBar.lang = ops.lang;
		commandBar.onLangChange = (l) => (ops.lang = l);
		commandBar.onShare = null; // Share lives in the pane header
		commandBar.onSearch = (q) => workspace.openOmnibar(q);
		commandBar.onInbox = () => {
			workspace.rightTab = 'inbox';
			workspace.setDock('right', true);
		};
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
			f && (f.label === 'simulated' || f.label === 'mixed') ? { label: f.label, text: L('wall_exercise_simulated', f.segments) } : null;
	});

	$effect(() => {
		const city = ops.cityBand;
		const band = city ? (city.stale ? null : city.band) : ops.bandSourceKind === 'city-band' ? ops.band : null;
		commandBar.band = band;
		commandBar.bandSource = band ? ops.bandSource : null;
	});

	$effect(() => {
		const at = ops.cityBand?.evaluatedAt ?? (ops.cityBandUpdated || null);
		commandBar.bandAgeSec = at && commandBar.band ? Math.max(0, (now - at) / 1000) : null;
	});

	$effect(() => {
		const n = units.length;
		commandBar.inboxCount = n;
		commandBar.inboxIntent = n > 0 ? 'warning' : 'none';
	});

	$effect(() => {
		// the strip (and its interrupts) stay live through a replay (SPEC §7.3)
		commandBar.live = liveStripFeed({ route: '/gods-eye' });
	});

	async function share() {
		const url = typeof location !== 'undefined' ? `${location.origin}${location.pathname}${location.hash}` : '';
		try {
			await navigator.clipboard.writeText(url);
		} catch {
			// clipboard refused: nothing else changes
		}
	}
</script>

<svelte:head>
	<title>{t(lang, 'cc_title')} · Sajag</title>
	<meta name="robots" content="noindex" />
</svelte:head>

{#if ops.signInRequired}
	<!-- Gate on, nobody signed in: one sign-in panel, no canvas, no pollers. -->
	<div class="signin-wall" data-testid="cc-signin-required">
		<div class="signin-card">
			<h2>{t(lang, 'cc_signin_title')}</h2>
			<p>{t(lang, 'cc_signin_body')}</p>
			<OperatorSignIn lang={ops.lang} inline />
			<p class="gate-note">{t(lang, 'cc_signin_hash_note')}</p>
		</div>
	</div>
{:else if !sessionKnown}
	<div class="page" data-template="city-command" data-pending="session" aria-busy="true"></div>
{:else}
	<div class="page" data-template="city-command" class:replaying={replay.mode === 'replay'}>
		<WorkspaceFrame route="/gods-eye" mode="map" live={{ movement: movementLive, pursuit: pursuitLive }}>
			{#snippet headerRight()}
				<Button minimal small icon="share" class="share" data-share tooltip={L('shell_share')} aria-label={L('shell_share')} onclick={() => void share()} />
			{/snippet}
			{#snippet map()}
				<GodsEyeCanvas
					hud="full"
					chrome="v2"
					onexit={exitMapMode}
					protected={protectedSet}
					selectionItems={selectionItems}
					{idleOrbit}
				/>
			{/snippet}
			{#snippet overlay()}
				{#if cardMounted}
					<CityVitals variant="card" />
				{/if}
			{/snippet}
		</WorkspaceFrame>
	</div>
{/if}

<style>
	.page {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		min-width: 0;
		overflow: hidden;
		background: var(--v-canvas);
		color: var(--v-ink-1);
	}

	.page :global(.ws) {
		flex: 1 1 auto;
		min-height: 0;
	}

	/* map mode: the bottom dock never grows past its normal sizes — 'full' keeps
	   its 278 px (the audit tab opens inside it, scrolling), so a tab an audit
	   check opens can never swallow the full-bleed map (SPEC §6.2) */
	.page :global(.ws.map-mode .bottom[data-size='full']) {
		height: 278px;
		flex: 0 0 278px;
	}

	/* map mode: the bottom dock COLLAPSES TO ITS 36 PX HEADER (SPEC §6.2, audit
	   C S2): the frame's map-mode rule sizes the dock by its content, so the
	   compact dock is pinned to the header's own 36 px — the Live/Replay control
	   rides that row (the analysis dock overlays its controls into the header
	   row) and a tab's body spills past the collapsed section, clipped by the
	   page. A LIVE replay needs its bar: while one runs the dock takes its
	   content's height again. */
	.page :global(.ws.map-mode .bottom[data-size='compact']) {
		height: 36px;
		flex: 0 0 36px;
	}

	.page :global(.ws.map-mode:has([data-testid='fusion-rail'][data-mode='replay']) .bottom[data-size='compact']) {
		height: auto;
		flex: 0 0 auto;
	}

	/* audit E item 3 (round 2): the credits are ONE compact line here too, as
	   the prototype's full-bleed map shows — logos, the first attribution and
	   the "Data attribution" lightbox link — clear of the readout at the left */
	.page :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom) {
		max-width: min(46%, 430px);
	}

	.page :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom .cesium-widget-credits) {
		display: flex;
		flex-wrap: nowrap;
		align-items: center;
		min-width: 0;
	}

	.page :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom .cesium-credit-logoContainer) {
		flex: 0 0 auto;
	}

	.page :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom .cesium-credit-logoContainer img) {
		height: 14px;
	}

	.page :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom .cesium-credit-expand-link) {
		flex: 0 0 auto;
		white-space: nowrap;
	}

	.page :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom .cesium-credit-textContainer) {
		flex: 0 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* map mode: the vitals card rides ABOVE the canvas chrome (never under it) */
	.page :global(.overlay) {
		z-index: 6;
		pointer-events: none;
	}

	.page :global(.overlay *) {
		pointer-events: auto;
	}

	/* ── operator gate: sign-in required (no canvas mounted) ─────────────── */
	.signin-wall {
		flex: 1;
		min-height: 0;
		display: grid;
		place-items: center;
		padding: 16px;
	}

	.signin-card {
		width: min(440px, calc(100vw - 32px));
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 20px;
		background: var(--v-surface-2);
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-panel);
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

	.gate-note {
		font-size: var(--v-text-xs);
		color: var(--v-ink-3);
	}
</style>
