<script lang="ts">
	/**
	 * WorkspaceFrame (SPEC §5.3) — the object workspace's frame: a rail, a
	 * left dock, a centre (pane header, the filter or travel bar, the views,
	 * the bottom dock) and a right dock. The page composes the centre views
	 * (map, graph, table; split = map beside graph) and passes them as
	 * snippets; the frame never imports a provider — the docks hold the tabs
	 * providers registered (registry.ts), and with none at all the frame
	 * shows a non-ideal state.
	 *
	 * Hooks: `data-ws="frame"`, `data-dock` + `data-open`, `data-view`,
	 * `data-pane`, `data-rail`, `data-bottom-tab`, `data-right-tab`.
	 *
	 * Keys: `[` and `]` toggle the side docks, `\` shows or hides the bottom
	 * dock; below 1440 px only one side dock is open at a time. Esc closes,
	 * then clears (the selection); it never navigates.
	 *
	 * The map pane, when the page gives one, stays mounted in every view
	 * (hidden, never destroyed: the canvas and its omnibar live there, R30).
	 * Map mode (`mode="map"`, /gods-eye): the page closes the docks; the map
	 * fills the centre and the bottom dock takes only its content's height.
	 */
	import type { Snippet } from 'svelte';
	import { ACTION_ICON } from '$lib/design/icons';
	import { Button, Icon, NonIdealState, SegmentedControl, Tooltip, provideUiLang } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.workspace';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { bottomTabsFor, leftTabsFor, rightTabsFor } from '../registry';
	import { liveWorld } from '../world.svelte';
	import { ONE_DOCK_BELOW_PX, workspace } from '../workspace.svelte';
	import type { TabContext, TabRoute, TabSpec, View } from '../types';
	import { provideFrame } from './frame/context';
	import FilterBar from './frame/FilterBar.svelte';

	let {
		route = '/',
		mode = 'workspace',
		live = { movement: false, pursuit: false },
		title = null,
		headerRight,
		map,
		graph,
		table,
		overlay,
		...rest
	}: {
		route?: TabRoute;
		mode?: 'workspace' | 'map';
		/** What is live now (a movement, a pursuit): tabs may depend on it (TabSpec.when). */
		live?: { movement: boolean; pursuit: boolean };
		/** The pane header's title (the saved view's name). */
		title?: string | null;
		/** The pane header's right end (the route's one Share). */
		headerRight?: Snippet;
		map?: Snippet;
		graph?: Snippet;
		table?: Snippet;
		/** Floating over the map pane (map mode: the vitals card). */
		overlay?: Snippet;
		[k: string]: unknown;
	} = $props();

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	/** A registered label is an i18n key (preferred) or literal text. */
	const label = (tab: TabSpec) => {
		const v = t(lang, tab.label);
		return v === tab.label ? tab.label : v;
	};

	const ctx = $derived<TabContext>({ route, mode, live });
	const leftTabs = $derived(leftTabsFor(ctx));
	const rightTabs = $derived(rightTabsFor(ctx));
	const bottomTabs = $derived(bottomTabsFor(ctx));
	const empty = $derived(!leftTabs.length && !rightTabs.length && !bottomTabs.length);

	const views = $derived.by((): View[] => {
		const out: View[] = [];
		if (map) out.push('map');
		if (graph) out.push('graph');
		if (table) out.push('table');
		if (map && graph) out.push('split');
		return out;
	});
	provideFrame({ views: () => views, route: () => route, mode: () => mode });

	const view = $derived<View>(views.includes(workspace.view) ? workspace.view : (views[0] ?? 'map'));
	const leftTab = $derived(leftTabs.find((x) => x.id === workspace.leftTab) ?? leftTabs[0] ?? null);
	const rightTab = $derived(rightTabs.find((x) => x.id === workspace.rightTab) ?? rightTabs[0] ?? null);
	const bottomTab = $derived(bottomTabs.find((x) => x.id === workspace.bottomTab) ?? bottomTabs[0] ?? null);
	const leftOpen = $derived(workspace.docks.left && !!leftTab);
	const rightOpen = $derived(workspace.docks.right && !!rightTab);
	// the bottom dock's size is the store's; in map mode its CSS lets it take its content's height (.map-mode)
	const bottomSize = $derived(!bottomTab ? 'none' : workspace.docks.bottom);

	let width = $state(1920);
	const rightW = $derived(width >= 1680 ? 'var(--v-ws-right)' : width >= ONE_DOCK_BELOW_PX ? 'var(--v-ws-right-md)' : 'var(--v-ws-right-sm)');

	// below 1440 px only one side dock is open at a time
	$effect(() => {
		if (width < ONE_DOCK_BELOW_PX) workspace.fitDocks(width);
	});

	// ── first-use prefetch (TabSpec.prefetch) ──────────────────────────────
	// A lazily loaded panel that declares `prefetch` (the inspector) starts
	// loading on the operator's FIRST press — pointer or key, anywhere — so the
	// first pick finds it in; an interaction-free cold load fetches nothing
	// (the omnibar's first-use rule, FIX-E-PERF2). Read at press time: the
	// page registers its providers after this frame mounts.
	$effect(() => {
		const types = ['pointerdown', 'keydown'] as const;
		const off = () => {
			for (const type of types) window.removeEventListener(type, first, true);
		};
		const first = () => {
			off();
			for (const tab of [...leftTabs, ...rightTabs, ...bottomTabs]) void tab.prefetch?.().catch(() => {});
		};
		for (const type of types) window.addEventListener(type, first, { capture: true, passive: true });
		return off;
	});

	// ── the live clock ─────────────────────────────────────────────────────

	let now = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(id);
	});
	const clock = $derived(new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).format(now));

	// ── keys ───────────────────────────────────────────────────────────────

	function typing(e: KeyboardEvent): boolean {
		const el = e.target as HTMLElement | null;
		return !!el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));
	}

	function onKey(e: KeyboardEvent) {
		if (e.defaultPrevented || typing(e) || e.metaKey || e.ctrlKey || e.altKey) return;
		if (e.key === 'Escape') {
			// closes, then clears; never navigates
			if (workspace.escape()) e.preventDefault();
			return;
		}
		if (e.key === '[') workspace.toggleDock('left', width);
		else if (e.key === ']') workspace.toggleDock('right', width);
		else if (e.key === '\\') workspace.toggleDock('bottom', width);
		else return;
		e.preventDefault();
	}

	function pickLeft(id: string) {
		if (workspace.docks.left && leftTab?.id === id) {
			workspace.setDock('left', false, width);
			return;
		}
		workspace.leftTab = id;
		workspace.setDock('left', true, width);
	}

	function pickRight(id: string) {
		workspace.rightTab = id;
		if (!workspace.docks.right) workspace.setDock('right', true, width);
	}

	function pickBottom(id: string) {
		workspace.bottomTab = id;
		if (workspace.docks.bottom === 'off') workspace.setBottom('compact');
	}

	const viewOptions = $derived(
		views.map((v) => ({
			value: v,
			label: L(`ws_view_${v}`),
			icon: (v === 'map' ? 'map' : v === 'graph' ? 'graph' : v === 'table' ? 'th' : 'two-columns') as 'map' | 'graph' | 'th' | 'two-columns',
			attrs: { 'data-view-option': v },
		})),
	);
</script>

<svelte:window bind:innerWidth={width} onkeydown={onKey} />

<div
	class="ws"
	class:no-left={!leftOpen}
	class:no-right={!rightOpen}
	class:map-mode={mode === 'map'}
	data-ws="frame"
	data-mode={mode}
	style:--right-w={rightW}
	{...rest}
>
	<nav class="rail" aria-label={L('ws_rail_label')}>
		{#each leftTabs as tab (tab.id)}
			<Tooltip content={label(tab)} placement="right">
				<button
					type="button"
					class="rail-btn"
					class:is-pressed={leftOpen && leftTab?.id === tab.id}
					aria-pressed={leftOpen && leftTab?.id === tab.id}
					aria-label={label(tab)}
					data-rail={tab.id}
					onclick={() => pickLeft(tab.id)}
				>
					<Icon name={tab.icon} />
				</button>
			</Tooltip>
		{/each}
		<span class="spacer"></span>
		{#if rightTabs.length}
			<Tooltip content={`${L('ws_kbd_right')} (])`} placement="right">
				<button
					type="button"
					class="rail-btn"
					class:is-pressed={rightOpen}
					aria-pressed={rightOpen}
					aria-label={L('ws_kbd_right')}
					data-rail-toggle="right"
					onclick={() => workspace.toggleDock('right', width)}
				>
					<Icon name="drawer-right" />
				</button>
			</Tooltip>
		{/if}
	</nav>

	<aside class="dock left" data-dock="left" data-open={leftOpen} aria-hidden={!leftOpen}>
		{#if leftOpen && leftTab}
			{@const C = leftTab.component}
			<header class="dock-head">
				<span class="dh-title">{label(leftTab)}</span>
				<Button
					minimal
					small
					icon="drawer-left"
					class="dh-hide"
					tooltip={`${L('ws_dock_hide')} ([)`}
					aria-label={L('ws_dock_hide')}
					onclick={() => workspace.setDock('left', false, width)}
				/>
			</header>
			<div class="dock-scroll" data-left-tab={leftTab.id}><C /></div>
		{/if}
	</aside>

	<main class="center" data-bottom={bottomSize}>
		<div class="pane-head">
			<span class="ph-title"><Icon name="bookmark" class="ph-glyph" /><span class="ph-name">{title ?? L('ws_frame_label')}</span></span>
			<span class="grow"></span>
			{#if workspace.live}
				<span class="live" data-testid="live-indicator"><span class="dot" aria-hidden="true"></span>{L('ws_live_at')} · <span class="tn">{clock}</span> IST</span>
			{/if}
			{#if views.length > 1}
				<SegmentedControl small options={viewOptions} value={view} onchange={(v) => (workspace.view = v)} label={L('ws_view_label')} class="views-switch" />
			{/if}
			{#if headerRight}{@render headerRight()}{/if}
		</div>

		<FilterBar {lang} {now} />

		<div class="views" class:split={view === 'split'} data-view={view}>
			<!-- the views stay mounted with no provider at all: the map pane holds the canvas and its omnibar (R30) -->
			{#if map}
				<div class="pane map" class:off={view !== 'map' && view !== 'split'} data-pane="map" aria-hidden={view !== 'map' && view !== 'split'}>
					{@render map()}
					{#if overlay}<div class="overlay">{@render overlay()}</div>{/if}
				</div>
			{/if}
			{#if view === 'split' && graph}<div class="splitter" aria-hidden="true"></div>{/if}
			{#if graph && (view === 'graph' || view === 'split')}
				<div class="pane graph" data-pane="graph">{@render graph()}</div>
			{/if}
			{#if table && view === 'table'}
				<div class="pane table" data-pane="table">{@render table()}</div>
			{/if}
			{#if !views.length && !empty}
				<div class="pane" data-pane="none"><NonIdealState icon="widget" iconSize={32} title={L('ws_view_empty')} description={L('ws_view_empty_hint')} /></div>
			{/if}
			{#if empty}
				<!-- no provider registered: said over the views (a card) or in their place (no view) -->
				<div class="empty-frame" class:alone={!views.length} data-pane="empty">
					<div class="ef-card"><NonIdealState icon="applications" iconSize={48} title={L('ws_frame_empty')} description={L('ws_frame_empty_hint')} /></div>
				</div>
			{/if}
		</div>

		{#if bottomTab}
			<section class="bottom" data-dock="bottom" data-open={workspace.docks.bottom !== 'off'} data-size={workspace.docks.bottom}>
				<div class="bt-head">
					<div class="bt-tabs" role="tablist">
						{#each bottomTabs as tab (tab.id)}
							<button
								type="button"
								role="tab"
								class="bt-tab"
								class:on={bottomTab.id === tab.id}
								aria-selected={bottomTab.id === tab.id}
								data-bottom-tab={tab.id}
								onclick={() => pickBottom(tab.id)}
							>
								<span>{label(tab)}</span>
							</button>
						{/each}
					</div>
					<span class="grow"></span>
					<Button
						minimal
						small
						icon={workspace.docks.bottom === 'full' ? 'chevron-down' : 'chevron-up'}
						tooltip={workspace.docks.bottom === 'full' ? L('ws_bottom_compact') : L('ws_bottom_expand')}
						aria-label={workspace.docks.bottom === 'full' ? L('ws_bottom_compact') : L('ws_bottom_expand')}
						onclick={() => workspace.setBottom(workspace.docks.bottom === 'full' ? 'compact' : 'full')}
					/>
				</div>
				{#if workspace.docks.bottom !== 'off'}
					{@const B = bottomTab.component}
					<div class="bt-body"><B /></div>
				{/if}
			</section>
		{/if}
	</main>

	<aside class="dock right" data-dock="right" data-open={rightOpen} aria-hidden={!rightOpen}>
		{#if rightOpen && rightTab}
			{@const R = rightTab.component}
			<div class="dock-tabs" class:crowded={rightTabs.length > 3} role="tablist">
				<!-- the tabs scroll within their row; the dock's hide button never
				     gives way to them (audit E item 7: with the Movement tab live
				     the button was pushed out of the row even at 1920) -->
				<div class="dt-row">
					{#each rightTabs as tab (tab.id)}
						<button
							type="button"
							role="tab"
							class="dt-tab"
							class:on={rightTab.id === tab.id}
							aria-selected={rightTab.id === tab.id}
							data-right-tab={tab.id}
							onclick={() => pickRight(tab.id)}
						>
							<Icon name={tab.icon} /><span class="dt-lbl">{label(tab)}</span>
						</button>
					{/each}
				</div>
				<Button
					minimal
					small
					icon="drawer-right"
					class="dt-hide"
					tooltip={`${L('ws_dock_hide')} (])`}
					aria-label={L('ws_dock_hide')}
					onclick={() => workspace.setDock('right', false, width)}
				/>
			</div>
			<div class="dock-scroll" data-right-panel={rightTab.id}><R /></div>
		{/if}
	</aside>
</div>

<style>
	.ws {
		display: grid;
		grid-template-columns: var(--v-ws-rail) var(--v-ws-left) minmax(0, 1fr) var(--right-w, var(--v-ws-right));
		height: 100%;
		min-height: 0;
		min-width: 0;
		background: var(--v-canvas);
		color: var(--v-ink-1);
		font-size: 14px;
		line-height: 18px;
	}

	.ws.no-left {
		grid-template-columns: var(--v-ws-rail) 0 minmax(0, 1fr) var(--right-w, var(--v-ws-right));
	}

	.ws.no-right {
		grid-template-columns: var(--v-ws-rail) var(--v-ws-left) minmax(0, 1fr) 0;
	}

	.ws.no-left.no-right {
		grid-template-columns: var(--v-ws-rail) 0 minmax(0, 1fr) 0;
	}

	.rail {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		padding: 8px 0;
		background: var(--v-surface-1);
		border-right: 1px solid var(--v-line-2);
		min-height: 0;
	}

	.rail-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 30px;
		height: 30px;
		border: 0;
		border-radius: var(--v-radius-btn);
		background: transparent;
		color: var(--v-ink-2);
		cursor: pointer;
	}

	.rail-btn:hover {
		background: var(--v-minimal-hover);
		color: var(--v-ink-1);
	}

	.rail-btn.is-pressed {
		background: var(--v-surface-4);
		color: var(--v-ink-1);
		box-shadow: inset 0 0 0 1px var(--v-line-strong);
	}

	.rail-btn:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 0;
	}

	.spacer,
	.grow {
		flex: 1 1 auto;
	}

	.dock {
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		overflow: hidden;
		background: var(--v-surface-1);
	}

	.dock.left {
		border-right: 1px solid var(--v-line-2);
	}

	.dock.right {
		border-left: 1px solid var(--v-line-2);
	}

	.ws.no-left .dock.left,
	.ws.no-right .dock.right {
		border: 0;
	}

	.dock-head {
		display: flex;
		align-items: center;
		gap: 8px;
		height: var(--v-ws-pane-head);
		padding: 0 4px 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		flex: 0 0 auto;
	}

	.dh-title {
		flex: 1 1 auto;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.dock-scroll {
		flex: 1 1 auto;
		min-height: 0;
		overflow: auto;
	}

	.dock-tabs {
		display: flex;
		align-items: center;
		gap: 8px;
		height: var(--v-ws-pane-head);
		padding: 0 4px 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		flex: 0 0 auto;
		min-width: 0;
	}

	/* the tab row gives way (it scrolls); the hide button does not (audit E item 7) */
	.dt-row {
		display: flex;
		align-items: stretch;
		gap: 16px;
		flex: 1 1 auto;
		min-width: 0;
		overflow-x: auto;
		scrollbar-width: none; /* the tooltip names the tab; the bar itself is noise */
	}

	.dt-row::-webkit-scrollbar {
		display: none;
	}

	.dt-hide {
		flex: 0 0 auto;
	}

	.dt-tab,
	.bt-tab {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 100%;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		font-size: 14px;
		white-space: nowrap;
		cursor: pointer;
	}

	.dt-tab :global(svg) {
		color: var(--v-ink-2);
	}

	.dt-tab:hover,
	.bt-tab:hover {
		color: var(--v-primary-text);
	}

	.dt-tab.on,
	.bt-tab.on {
		color: var(--v-primary-text);
	}

	.dt-tab.on :global(svg) {
		color: var(--v-primary-text);
	}

	/* the tab underline (SPEC §5.1 Tabs): 3 px in the primary text ink, an inset shadow as Blueprint draws it */
	.dt-tab.on,
	.bt-tab.on {
		box-shadow: inset 0 -3px 0 var(--v-primary-text);
	}

	/* with more than three tabs the labels give way to their glyphs (the tooltip keeps the name): four labels do not fit
	   the dock at any console size, and a scrolled row cut "Assistant" to "Assis" mid-word (audit E R2) */
	.dock-tabs.crowded .dt-lbl {
		display: none;
	}

	.center {
		display: grid;
		grid-template-rows: var(--v-ws-pane-head) auto minmax(0, 1fr) auto;
		/* without an explicit column the implicit `auto` track takes the Cesium canvas's min-content width, so the map
		   overflows the right dock whenever a dock opens (audit C, S1): the one column may shrink to the space it has */
		grid-template-columns: minmax(0, 1fr);
		min-width: 0;
		min-height: 0;
	}

	.pane-head {
		display: flex;
		align-items: center;
		gap: 12px;
		height: var(--v-ws-pane-head);
		padding: 0 8px 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
		min-width: 0;
	}

	.ph-title {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		font-weight: 600;
	}

	.ph-title :global(.ph-glyph) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.ph-name {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.live {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		font-size: 12px;
		color: var(--v-ink-2);
		white-space: nowrap;
	}

	.live .dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background-color: var(--v-success);
	}

	.tn {
		font-variant-numeric: tabular-nums;
	}

	.views {
		grid-row: 3;
		position: relative;
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		grid-template-rows: minmax(0, 1fr);
		min-height: 0;
		min-width: 0;
		background: var(--v-canvas);
	}

	.views.split {
		grid-template-columns: minmax(0, 1fr) 1px minmax(0, 1fr);
	}

	.pane {
		position: relative;
		min-width: 0;
		min-height: 0;
		overflow: hidden;
	}

	/* the map stays mounted in every view (R30): hidden, never destroyed */
	.pane.map.off {
		position: absolute;
		inset: 0;
		visibility: hidden;
		pointer-events: none;
	}

	.pane.table {
		background: var(--v-surface-1);
	}

	[data-pane='none'] {
		display: flex;
		align-items: center;
		justify-content: center;
	}

	/* no provider: a floating card over the mounted views; it takes no pointer events but its own */
	.empty-frame {
		position: absolute;
		inset: 0;
		z-index: 4;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 16px;
		pointer-events: none;
	}

	.ef-card {
		max-width: 480px;
		padding: 24px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-2);
		box-shadow: var(--v-elev-3);
		pointer-events: auto;
	}

	/* with no view at all the state stands in their place, flat */
	.empty-frame.alone {
		position: static;
	}

	.empty-frame.alone .ef-card {
		background: transparent;
		box-shadow: none;
	}

	.splitter {
		background: var(--v-line-2);
	}

	.overlay {
		position: absolute;
		top: 8px;
		right: 8px;
		z-index: 3;
	}

	.bottom {
		grid-row: 4;
		display: flex;
		flex-direction: column;
		min-height: 0;
		background: var(--v-surface-1);
		border-top: 1px solid var(--v-line-2);
	}

	.bottom[data-size='compact'] {
		height: var(--v-ws-timeline);
	}

	.bottom[data-size='full'] {
		height: 278px;
	}

	.bt-head {
		display: flex;
		align-items: center;
		gap: 8px;
		height: 36px;
		padding: 0 8px 0 16px;
		border-bottom: 1px solid var(--v-line-1);
		flex: 0 0 auto;
		min-width: 0;
		overflow: hidden;
	}

	.bt-tabs {
		display: flex;
		align-items: stretch;
		gap: 20px;
		height: 100%;
	}

	.bt-body {
		flex: 1 1 auto;
		min-height: 0;
		position: relative;
	}

	.ws.map-mode .bottom[data-size] {
		height: auto;
	}
</style>
