<script lang="ts">
	/**
	 * `/` — THE CORRIDOR WORKSPACE (SPEC §6.1): the map-led object workspace
	 * composed from the merged S2–S5 parts — the workspace frame's views Map
	 * (GodsEyeCanvas, chrome v2), Graph (LinkGraph) and Table (ObjectTable),
	 * Split beside them; the timeline, audit and AI trace in the bottom dock;
	 * the inspector, the Inbox and (while a movement is live) the Movement
	 * tab (ConvoyCard, the home of escort proposals) in the right dock; the
	 * Explorer, Layers, Histogram and Plan (PlanPanel) in the left dock's
	 * rail; and the canvas-mounted omnibar — the page's ONLY one (plan R30/
	 * X25): the canvas stays mounted (hidden, never destroyed) in every view.
	 *
	 * Defaults (map ≥ 60 % of the screen): the left dock closed, the timeline
	 * compact; the right dock shows the Movement tab while a movement is
	 * live, else the inspector when something is selected, else the Inbox
	 * when a decision waits. Auto-orbit never runs here (idleOrbit=false):
	 * never while something is selected or a dock is open. Replay is blocked
	 * while a movement or pursuit is live (the analysis dock's guard says
	 * which, SPEC §7.3).
	 *
	 * The canvas props come from the workspace: the time window, the
	 * multi-selection, the kind filters and the PROTECTED objects (§7.3) —
	 * the active movement, its convoy and route; every open pursuit and its
	 * vehicle; every subject of a waiting decision; every vehicle with a
	 * watchlist read in the last 30 min. A map lasso multi-selects through
	 * `onlasso → selection.selectMany`.
	 *
	 * One Share, in the view header (`data-share`): the current camera,
	 * layers, selection and workspace state as a masked share link (URNs
	 * only, never a mark).
	 *
	 * Operator gate on and nobody signed in: the workspace is not mounted —
	 * one sign-in card stands in.
	 */
	import { onDestroy, onMount, untrack } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import OperatorSignIn from '$lib/shell/OperatorSignIn.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { toasts } from '$lib/shell/toast.svelte';
	import { WORKSPACE_URL } from '$lib/shell/root-flip';
	import { godsEye } from '$lib/gods-eye/store.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { fusionFeed } from '$lib/gods-eye/hud/feed.svelte';
	import GodsEyeCanvas from '$lib/gods-eye/GodsEyeCanvas.svelte';
	import WorkspaceFrame from '$lib/workspace/components/WorkspaceFrame.svelte';
	import { registerProviders } from '$lib/workspace/providers';
	import { liveWorld, selectors } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { Button, provideUiLang } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.views';
	import '$lib/i18n/packs.wall';
	import '$lib/i18n/packs.corridor';
	import { parseUnitKey } from '$lib/decisions/homes';
	import { liveStripFeed, openPursuits } from '$lib/decisions/live';
	import { dataFeeds, feedRows, worstStatus } from '$lib/decisions/wall/feeds';
	import { corridor } from '$lib/ops/components/template/corridor.svelte';
	import { escortLifecycle } from '$lib/corridor/escort-state.svelte';
	import ActiveEvents from '$lib/corridor/ActiveEvents.svelte';
	import { Section } from '$lib/ui';

	provideUiLang(() => ops.lang);
	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	/** The operator gate's state is known (or the read gave up): mount the workspace, or the sign-in. */
	let sessionWaitOver = $state(false);
	const sessionKnown = $derived(ops.sessionGate !== null || sessionWaitOver);

	// ── the workspace's canvas props ────────────────────────────────────────
	/** Protected objects never fade or dim (SPEC §7.3), on the canvas and in the table. */
	const protectedSet = $derived(selectors.protectedUrns());
	/** The kinds the filters allow (null: every kind). */
	const kindFilter = $derived.by((): ReadonlySet<string> | null => {
		const kinds = workspace.filters.filter((f) => f.field === 'kind').flatMap((f) => [...f.values]);
		return kinds.length ? new Set(kinds) : null;
	});
	const selectionItems = $derived(selection.items);

	/** A map lasso (or Search around) selects many (plan X11). */
	function onlasso(urns: string[]) {
		selection.selectMany(urns, { source: 'lasso' });
	}

	/** The graph view follows the selection; empty focus renders the empty state. */
	const focusUrn = $derived(selection.current ?? '');
	const layout = $state<'radial' | 'force' | 'hierarchical'>('radial');

	function onGraphSelect(urn: string, mode: 'replace' | 'add' | 'toggle') {
		selection.select(urn, { source: 'graph', mode });
	}

	// ── the defaults (SPEC §6.1) ────────────────────────────────────────────
	const units = $derived(selectors.decisionUnits());
	const movementLive = $derived(
		ops.events.some((e) => e.source !== 'offline-fixture' && e.eventKind === 'protected_movement' && e.state === 'active'),
	);
	const pursuitLive = $derived(openPursuits(ops).length > 0);

	// ── the escort lifecycle: adopt a running escort, close it when the brain
	//    ends it (audit C S1: the corridor's controls — Launch/Stop/Clear, the
	//    proposal link — live on the Plan tab, which the OPERATOR opens; no
	//    dock ever opens itself and yanks the map under the decision)
	$effect(() => {
		void ops.events.length;
		void ops.escortsDeployed; // adoption waits for the lanes' first answer
		escortLifecycle.sync();
	});

	// ── the right dock: the Movement tab is the default while a movement is
	//    live (else the inspector when something is selected, else the Inbox
	//    when a decision waits); a NEW selection opens the inspector (the
	//    operator's intent); a tab the operator chose is never yanked — the
	//    auto default re-applies only while the tab is still the one we set
	let lastSelection = $state<string | null | undefined>(undefined);
	let seededTab = $state<string | null>(null);
	$effect(() => {
		const sel = selection.current;
		const picked = lastSelection !== undefined && sel !== lastSelection && !!sel;
		lastSelection = sel;
		const want = movementLive ? 'movement' : sel ? 'inspector' : units.length ? 'inbox' : null;
		const cur = workspace.rightTab;
		if (picked) {
			seededTab = null;
			if (sel) {
				workspace.rightTab = 'inspector';
				untrack(() => workspace.setDock('right', true));
			}
			return;
		}
		// seed on a TAB CHANGE only, and never reopen a dock the operator
		// closed (audit E round 2): the read of `cur` is the effect's only
		// tracked store write — the dock toggle reads+writes the docks, so it
		// is untracked; an earlier version re-ran on every dock toggle and
		// re-opened the right dock the operator had just closed (and, below
		// 1440 px where one side dock excludes the other, closed the left
		// dock with it — the S1 dock lock)
		if (want && (cur === '' || cur === seededTab) && cur !== want) {
			seededTab = want;
			workspace.rightTab = want;
			untrack(() => workspace.setDock('right', true));
		}
	});
	// ── deep links: #inbox=<kind:id> and #movement=<kind:id> (the homes' hrefs) ─
	function openUnitFromHash() {
		if (typeof location === 'undefined') return;
		const params = new URLSearchParams(location.hash.replace(/^#/, ''));
		for (const key of ['inbox', 'movement'] as const) {
			const parsed = parseUnitKey(params.get(key));
			if (!parsed) continue;
			const unit = units.find((u) => u.kind === parsed.kind && u.id === parsed.id);
			if (!unit) continue;
			workspace.openDecisionHome(unit, '/');
			return;
		}
		// the workspace keys of a share link (view, window, filters, docks, items)
		workspace.fromHash(location.hash);
	}

	// ── lifecycle ───────────────────────────────────────────────────────────
	onMount(() => {
		godsEye.followSelection = false; // free camera; /ops owns subject-follow
		registerProviders();
		ops.start();
		fusionFeed.start();
		const wait = setTimeout(() => (sessionWaitOver = true), 2500);
		// defaults once (SPEC §6.1): the left dock closed, the timeline compact;
		// the right dock's tab is the reactive effect's (Movement while a
		// movement is live, else the inspector on a pick, else the Inbox when a
		// decision waits) — no unregistered 'movement' seed here (audit C S2):
		// seeding an id no registered tab carries left the dock on the wrong tab
		workspace.docks = { ...workspace.docks, left: false, bottom: 'compact' };
		openUnitFromHash();
		return () => clearTimeout(wait);
	});

	onDestroy(() => {
		godsEye.subjectLockId = null;
		ops.stop();
		fusionFeed.stop();
	});

	// ── the command bar (plan R10/X12): what this page owns ────────────────
	let now = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(id);
	});

	// ── the Active events card (audit C S3): below ~900 px of map-pane width
	//    (Split view, half screens) a 300 px card would cover the map the
	//    operator is reading, so it collapses to its header — one disclosure
	//    the operator can open (their pin holds while the pane stays narrow)
	let paneW = $state(1920);
	let aePinned = $state(false);
	const aeCompact = $derived(paneW < 900);
	const aeOpen = $derived(aeCompact ? aePinned : true);
	$effect(() => {
		// reads sessionKnown: the workspace (and its map pane) mount once the
		// operator gate's state is known — until then there is no pane to watch
		if (!sessionKnown) return;
		const pane = document.querySelector<HTMLElement>('[data-pane="map"]');
		if (!pane || typeof ResizeObserver === 'undefined') return;
		const ro = new ResizeObserver(() => (paneW = Math.round(pane.getBoundingClientRect().width)));
		ro.observe(pane); // fires once on observe: the first measurement lands here
		return () => ro.disconnect();
	});

	/** The Data popover's rows: the same feedRows the wall composes (one honest list). */
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
		commandBar.onShare = null; // Share lives in the view header (SPEC §5.3)
		commandBar.onSearch = (q) => workspace.openOmnibar(q);
		commandBar.onInbox = () => {
			workspace.rightTab = 'inbox';
			workspace.setDock('right', true);
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
				? { label: f.label, text: L('wall_exercise_simulated', f.segments) }
				: null;
	});

	/** The navbar's band: the city band, Unknown while its engine poll fails — never a guessed Green. */
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
		commandBar.live = liveStripFeed({ route: '/' });
	});

	// ── one Share, in the view header ───────────────────────────────────────
	async function share() {
		// the canvas keeps the camera/layers hash current; the workspace adds
		// its keys — masked (URNs only, never a mark, SPEC §7.5)
		const hash = workspace.toHash(typeof location !== 'undefined' ? location.hash : '');
		const url = `${typeof location !== 'undefined' ? location.origin : ''}${WORKSPACE_URL}${hash ? `#${hash}` : ''}`;
		// F-22: the outcome is said — a toast for the copy, or for the refusal with what to do
		try {
			await navigator.clipboard.writeText(url);
			toasts.push({ kind: 'info', title: L('wall_share_done'), body: L('wall_share_body') });
		} catch {
			toasts.push({ kind: 'error', title: L('wall_share_failed') });
		}
	}

</script>

<svelte:head>
	<title>{L('nav_module_corridor')} · Sajag</title>
</svelte:head>

{#if ops.signInRequired}
	<!-- Gate on, nobody signed in: one sign-in card, no workspace, no refused reads. -->
	<div class="signin-wall" data-testid="cockpit-signin-required">
		<div class="signin-card">
			<h2>{tOps(lang, 'opsSigninTitle')}</h2>
			<p>{tOps(lang, 'cockpitSigninBody')}</p>
			<OperatorSignIn lang={ops.lang} inline />
		</div>
	</div>
{:else if !sessionKnown}
	<!-- the server render and the first instant: the workspace's frame (the
	     route contract scripts check: 200 + data-template), mounted in full
	     once the gate's state is known -->
	<div class="page" data-template="convoy-command" data-pending="session" aria-busy="true"></div>
{:else}
	<div class="page" data-template="convoy-command">
		<WorkspaceFrame route="/" mode="workspace" live={{ movement: movementLive, pursuit: pursuitLive }}>
			{#snippet headerRight()}
				<Button minimal small icon="share" class="share" data-share tooltip={L('shell_share')} aria-label={L('shell_share')} onclick={() => void share()} />
			{/snippet}
			{#snippet map()}
				<GodsEyeCanvas
					hud="wall"
					chrome="v2"
					timeWindow={workspace.timeWindow}
					protected={protectedSet}
					kindFilter={kindFilter}
					selectionItems={selectionItems}
					idleOrbit={false}
					{onlasso}
				/>
			{/snippet}
			{#snippet graph()}
				{#if focusUrn}
					{#await import('$lib/analysis/graph/LinkGraph.svelte') then graph}
						{@const LinkGraph = graph.default}
						<LinkGraph focus={focusUrn} selectionItems={selectionItems} {layout} onselect={onGraphSelect} window={workspace.timeWindow} {lang} />
					{/await}
				{:else}
					<div class="graph-empty"><p>{L('ws_frame_empty_hint')}</p></div>
				{/if}
			{/snippet}
			{#snippet table()}
				{#await import('$lib/workspace/components/table/ObjectTable.svelte') then table}
					{@const ObjectTable = table.default}
					<ObjectTable />
				{/await}
			{/snippet}
			{#snippet overlay()}
				{#if !(workspace.docks.left && workspace.leftTab === 'explorer')}
					<aside class="ae-card" class:compact={aeCompact} aria-label={t(lang, 'vw_ex_active_events')}>
						<Section
							title={t(lang, 'vw_ex_active_events')}
							collapsible={aeCompact}
							open={aeOpen}
							onopenchange={(o) => (aePinned = o)}
						>
							<ActiveEvents />
						</Section>
					</aside>
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

	/* the corridor's active events ride the map pane's overlay slot, top right
	   (the frame's own card slot): always in view on the cockpit, standing down
	   while the Explorer tab shows its own copy (never two on one page) and
	   collapsing to its header on a narrow pane (Split view) */
	.ae-card {
		width: 300px;
		max-height: min(40vh, 420px);
		display: flex;
		flex-direction: column;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
		box-shadow: var(--v-elev-2);
		overflow: hidden;
	}

	.ae-card :global([data-testid='active-events']) {
		min-height: 0;
		overflow-y: auto;
	}

	/* audit C S3 item 12, fix round 2 (audit E item 3): the credits are ONE
	   compact line — the logos, the first attribution and Cesium's "Data
	   attribution" lightbox link (the full list opens in the lightbox) —
	   never a max-height clamp that cuts a line mid-height and hides the
	   link, and never over the readout or the scale bar: the readout keeps
	   its 54 % at the left, the plate takes at most 40 % at the right */
	.page :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom) {
		max-width: min(40%, 430px);
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

	/* audit E item 4: in Split (a narrow pane) the collapsed Active events
	   card starts BELOW the canvas toolbar row — never under it (its title
	   was hidden beneath the toolbar's buttons) */
	.page :global(.overlay:has(.ae-card.compact)) {
		top: 52px;
	}

	.graph-empty {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
		color: var(--v-ink-2);
		font-size: var(--v-text-sm);
	}

	/* ── operator gate: sign-in required (no workspace mounted) ─────────── */
	.signin-wall {
		height: 100%;
		display: grid;
		place-items: center;
		padding: 16px;
	}

	.signin-card {
		width: min(440px, 100%);
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 20px;
		background: var(--v-surface-1);
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
</style>
