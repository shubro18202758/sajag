<script lang="ts">
	/**
	 * The analysis dock (SPEC §5.3, §6.1): Timeline · Audit · AI trace, and the
	 * Live / Replay modes of the timeline. Two variants:
	 *
	 *   standalone  FusionRail: the whole bottom dock with its own tab strip
	 *               (`data-bottom-tab`) and its own size (compact / full)
	 *   tab         one of the WorkspaceFrame's registered bottom tabs: the
	 *               frame draws the tabs and owns the size
	 *               (workspace.docks.bottom); the timeline's controls sit in
	 *               the frame's 36 px tab row, right of the tabs. The Audit
	 *               and AI-trace tabs open the dock at full height and give
	 *               the timeline its size back when they close.
	 *
	 * The root carries `data-testid="fusion-rail"` in both (the frame mounts
	 * one tab at a time). The Live/Replay control is `replay-toggle`.
	 *
	 * Live ⇔ no window (workspace.timeWindow === null). A brush sets the window
	 * (Live off); the Live switch, switched on, clears it; switched off, it
	 * sets the last 15 minutes. Play moves the window forward until it reaches
	 * now (Live again); the steps move it by a third of its width. The travel
	 * bar and its one "Return to live" are the frame's.
	 *
	 * Range: 1 h · 6 h · 24 h · 7 d, or Fit to the data; the city feed holds
	 * its newest 500 rows, so a range before the oldest loaded row is marked
	 * "older rows not loaded".
	 */
	import { onDestroy, onMount } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.analysis';
	import { Button, Menu, Popover, Switch, Tooltip } from '$lib/ui';
	import type { MenuItemSpec } from '$lib/ui';
	import { fmtRange } from '$lib/ui/format/format';
	import { ops } from '$lib/ops/store.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { fusionFeed } from '$lib/gods-eye/hud/feed.svelte';
	import { replay } from '$lib/gods-eye/hud/replay.svelte';
	import ReplayBar from '$lib/gods-eye/hud/ReplayBar.svelte';
	import { frameContext } from '$lib/workspace/components/frame/context';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { liveWorld, selectors } from '$lib/workspace/world.svelte';
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';
	import { aiTrace, itemFromFeed } from '../audit/rows';
	import { eventHistory } from '../history.svelte';
	import Timeline from '../timeline/Timeline.svelte';
	import { FEED_CAP, MIN, RANGES, fitRange, olderNotLoaded, oldestOf, rangeMs } from '../timeline/bins';
	import { cursorOf, shiftWindow } from '../timeline/brush';
	import { dockState } from './dock-state.svelte';
	import type { AuditFilter, AuditScope } from '../audit/rows';

	/** The audit / AI-trace table (FIX-E-PERF2): loads when its tab is first shown. */
	const loadAuditTable = () => import('../audit/AuditTable.svelte');

	type Tab = 'timeline' | 'audit' | 'ai';

	interface Props {
		variant?: 'standalone' | 'tab';
		/** The tab variant's tab. */
		tab?: Tab;
		/** Start the city feed and event-history reads (false: a harness seeds them). */
		poll?: boolean;
		/** Replay is blocked (the reason: "A movement is live"). */
		replayBlocked?: string | null;
		lang?: string;
	}

	let { variant = 'standalone', tab: fixedTab = 'timeline', poll = true, replayBlocked = null, lang: langProp }: Props = $props();

	const lang = $derived(langProp ?? ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const frame = frameContext();
	const inFrame = $derived(variant === 'tab' && !!frame);

	const TABS: readonly Tab[] = ['timeline', 'audit', 'ai'];
	const tab = $derived<Tab>(variant === 'tab' ? fixedTab : (TABS as readonly string[]).includes(workspace.bottomTab) ? (workspace.bottomTab as Tab) : 'timeline');

	// ── the clock ─────────────────────────────────────────────────────────
	let tick = $state(Date.now());
	onMount(() => {
		const id = setInterval(() => (tick = Date.now()), 1000);
		if (poll) {
			fusionFeed.start();
			eventHistory.start();
		}
		return () => clearInterval(id);
	});
	onDestroy(() => {
		if (poll) {
			fusionFeed.stop();
			eventHistory.stop();
		}
		stopPlay();
	});
	const now = $derived(dockState.clockOverride ?? tick);

	// ── size: the frame's (tab variant) or the dock's own ────────────────
	/** The body's height (a standalone dock in a host of its own height picks its density from it). */
	let bodyH = $state(0);
	/** The body a full timeline needs: a 40 px histogram, seven 19 px lanes, the axis and the key. */
	const FULL_BODY = 236;
	const autoDensity = $derived<'compact' | 'full'>(bodyH >= FULL_BODY ? 'full' : 'compact');
	const density = $derived<'compact' | 'full'>(
		variant === 'tab' ? (tab !== 'timeline' || workspace.docks.bottom === 'full' ? 'full' : 'compact') : dockState.size === 'auto' ? autoDensity : dockState.size,
	);
	/**
	 * Audit and AI trace open at full height; the timeline gets its size back
	 * when they close. The "raised by us" mark is dockState's, not this
	 * instance's: Audit raises, AI trace inherits the mark, and whichever
	 * side runs first when the Timeline returns (the leaving tab's destroy or
	 * the timeline's mount) gives the size back once. A size the operator set
	 * meanwhile (compact, or off) clears the mark: the dock is theirs again.
	 */
	function giveBack() {
		if (!dockState.raisedBottom) return;
		if (workspace.docks.bottom !== 'full') {
			dockState.raisedBottom = false;
			return;
		}
		if (workspace.bottomTab !== 'timeline') return;
		dockState.raisedBottom = false;
		workspace.setBottom('compact');
	}
	onMount(() => {
		if (variant !== 'tab') return;
		if (fixedTab === 'timeline') giveBack();
		else if (workspace.docks.bottom === 'compact') {
			workspace.setBottom('full');
			dockState.raisedBottom = true;
		}
	});
	onDestroy(() => {
		if (variant === 'tab' && fixedTab !== 'timeline') giveBack();
	});

	// ── range and window ──────────────────────────────────────────────────
	const feed = $derived(liveWorld.feed());
	const spans = $derived(eventHistory.rows.filter((r) => r.span).map((r) => ({ urn: r.urn, title: r.title, start: r.span![0], end: r.span![1] })));
	const range = $derived.by((): [number, number] => {
		if (dockState.range === 'fit' && dockState.fitSpan) return [dockState.fitSpan[0], now];
		return [now - rangeMs(dockState.range === 'fit' ? '6h' : dockState.range), now];
	});
	const win = $derived(workspace.timeWindow);
	const live = $derived(workspace.live);
	const oldest = $derived(oldestOf(feed));
	const newestRow = $derived(feed.length ? Math.max(...feed.map((r) => r.t)) : null);
	const olderBefore = $derived(olderNotLoaded(range[0], oldest, feed.length, FEED_CAP) ? oldest : null);
	const cursor = $derived(cursorOf(win, now, dockState.cursor));
	$effect(() => {
		// a new window (or live again) drops the cursor the operator put down
		void win;
		dockState.cursor = null;
	});

	const related = $derived.by(() => {
		const cur = selection.current;
		if (!cur) return new Set<string>();
		return new Set([cur, ...selection.items, ...selectors.linked(cur).map((o) => o.urn)]);
	});

	function brush(a: number, b: number) {
		stopPlay();
		workspace.setTimeWindow(a, b);
	}

	function setLive(on: boolean) {
		stopPlay();
		if (on) workspace.returnToLive();
		else workspace.setTimeWindow(now - 15 * MIN, now);
	}

	function stepBy(dir: -1 | 1) {
		const w = win ?? ([now - 15 * MIN, now] as [number, number]);
		const step = Math.max(MIN, (w[1] - w[0]) / 3) * dir;
		const base: [number, number] = win ? w : [w[0] - (dir < 0 ? 0 : step), w[1] - (dir < 0 ? 0 : step)];
		const next = shiftWindow(base, step, now);
		if (next) workspace.setTimeWindow(next[0], next[1]);
		else workspace.returnToLive();
	}

	let playTimer: ReturnType<typeof setInterval> | null = null;
	function stopPlay() {
		if (playTimer) clearInterval(playTimer);
		playTimer = null;
		dockState.playing = false;
	}
	function play() {
		if (dockState.playing) return stopPlay();
		if (!win) workspace.setTimeWindow(range[0], Math.min(now, range[0] + (range[1] - range[0]) / 6));
		dockState.playing = true;
		playTimer = setInterval(() => {
			const w = workspace.timeWindow;
			if (!w) return stopPlay();
			const next = shiftWindow(w, Math.max(30_000, (w[1] - w[0]) / 6), now);
			if (next) workspace.setTimeWindow(next[0], next[1]);
			else {
				workspace.returnToLive();
				stopPlay();
			}
		}, 400);
	}

	function pickRange(id: (typeof RANGES)[number]['id'] | 'fit') {
		if (id === 'fit') {
			dockState.fitSpan = fitRange(feed, spans, now);
			dockState.range = 'fit';
		} else dockState.range = id;
	}

	let rangeOpen = $state(false);
	const rangeItems = $derived<MenuItemSpec[]>([
		...RANGES.map((r) => ({ id: r.id, label: L(`an_range_${r.id}`), selected: dockState.range === r.id, onclick: () => pickRange(r.id) })),
		{ id: 'div', kind: 'divider' as const },
		{ id: 'fit', label: L('an_fit'), icon: 'zoom-to-fit' as const, selected: dockState.range === 'fit', onclick: () => pickRange('fit') },
	]);
	const rangeName = $derived(dockState.range === 'fit' ? L('an_fit') : L(`an_range_${dockState.range}`));

	// ── replay ────────────────────────────────────────────────────────────
	const replaying = $derived(replay.mode === 'replay');
	function toggleReplay() {
		stopPlay();
		if (replaying) replay.exit();
		else if (!replayBlocked) void replay.enter();
	}

	// ── counts on the tabs ────────────────────────────────────────────────
	const auditCount = $derived(feed.length);
	const aiCount = $derived(feed.filter((r) => r.kind === 'brain').length);

	function pickTab(id: Tab) {
		workspace.bottomTab = id;
	}

	function onpick(urn: string) {
		selection.select(urn, { fly: true, source: 'timeline' });
	}

	// AI trace items (the city feed's model rows), built only while that tab shows
	const aiItems = $derived(tab === 'ai' ? aiTrace(feed.filter((r) => r.kind === 'brain').map((r) => itemFromFeed(r, { officer: ops.officerOn, lang }))) : []);

	// ── the frame's tab row: the controls start right of its tabs ─────────
	let dockEl: HTMLElement | null = $state(null);
	let dockW = $state(1200);
	let overlayLeft = $state(240);
	$effect(() => {
		if (!inFrame || !dockEl) return;
		const measure = () => {
			const tabs = dockEl?.closest('[data-dock="bottom"]')?.querySelector('[role="tablist"]');
			const a = tabs?.getBoundingClientRect();
			const b = dockEl?.getBoundingClientRect();
			if (a && b && a.width > 0) overlayLeft = Math.max(120, Math.round(a.right - b.left + 12));
		};
		measure();
		const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
		ro?.observe(dockEl);
		return () => ro?.disconnect();
	});
	const narrow = $derived(dockW < 980);
</script>

{#snippet timelineControls()}
	<Button
		small
		minimal
		icon="history"
		pressed={replaying}
		disabled={!replaying && !!replayBlocked}
		disabledReason={replayBlocked}
		tooltip={replaying ? L('an_replay_leave') : L('an_replay_tip')}
		data-testid="replay-toggle"
		aria-pressed={replaying}
		onclick={toggleReplay}>{L('an_replay')}</Button
	>
	{#if !replaying}
		<span class="sep" aria-hidden="true"></span>
		<Button small minimal icon={dockState.playing ? 'pause' : 'play'} tooltip={dockState.playing ? L('an_pause') : L('an_play')} aria-label={dockState.playing ? L('an_pause') : L('an_play')} onclick={play} />
		<Button small minimal icon="step-backward" tooltip={L('an_step_back')} aria-label={L('an_step_back')} onclick={() => stepBy(-1)} />
		<Button small minimal icon="step-forward" tooltip={L('an_step_fwd')} aria-label={L('an_step_fwd')} onclick={() => stepBy(1)} disabled={live} />
		<span class="sep" aria-hidden="true"></span>
		<Tooltip content={live ? L('an_live_on_tip') : L('an_live_off_tip')}>
			<Switch small checked={live} onchange={setLive} data-testid="live-switch">{L('an_live')}</Switch>
		</Tooltip>
		<span class="grow"></span>
		{#if !narrow}<span class="rng">{L('an_ist', fmtRange(range[0], range[1], now))}</span>{/if}
		<Popover bind:open={rangeOpen} placement="bottom-end" role="menu">
			<Button small minimal rightIcon="caret-down" tooltip={L('an_range')}>{rangeName}</Button>
			{#snippet content({ close })}
				<Menu items={rangeItems} autofocus label={L('an_range')} onselect={() => close()} />
			{/snippet}
		</Popover>
		<Button small minimal icon="zoom-to-fit" tooltip={L('an_fit')} aria-label={L('an_fit')} onclick={() => pickRange('fit')} />
	{:else}
		<span class="grow"></span>
	{/if}
{/snippet}

<section
	bind:this={dockEl}
	bind:clientWidth={dockW}
	class="dock"
	class:standalone={variant === 'standalone'}
	class:in-frame={inFrame}
	data-testid="fusion-rail"
	data-mode={replay.mode}
	data-tab={tab}
	data-density={density}
	data-live={live}
	aria-label={L('an_dock_label')}
>
	{#if variant === 'standalone'}
		<div class="head">
			<div class="tabs" role="tablist">
				{#each TABS as id (id)}
					<button type="button" role="tab" class="tab" class:on={tab === id} aria-selected={tab === id} data-bottom-tab={id} onclick={() => pickTab(id)}>
						<span>{L(`an_tab_${id}`)}</span>
						{#if id === 'audit'}<span class="count">{auditCount}</span>{/if}
						{#if id === 'ai'}<span class="count">{aiCount}</span>{/if}
					</button>
				{/each}
			</div>
			<span class="sep tall" aria-hidden="true"></span>
			{#if tab === 'timeline'}
				{@render timelineControls()}
			{:else}
				<span class="grow"></span>
			{/if}
			<Button
				small
				minimal
				icon={density === 'full' ? 'chevron-down' : 'chevron-up'}
				tooltip={density === 'full' ? L('an_compact') : L('an_expand')}
				aria-label={density === 'full' ? L('an_compact') : L('an_expand')}
				onclick={() => (dockState.size = density === 'full' ? 'compact' : 'full')}
			/>
		</div>
	{:else if tab === 'timeline'}
		<!-- in the frame, the controls sit in its tab row (right of the tabs); outside one, above the body -->
		<div class="ctl-row" class:overlay={inFrame} style:left={inFrame ? `${overlayLeft}px` : undefined}>{@render timelineControls()}</div>
	{/if}

	<div class="body" data-bottom-view={tab} bind:clientHeight={bodyH}>
		{#if tab === 'timeline'}
			{#if replaying}
				<ReplayBar {density} {lang} />
			{:else}
				<Timeline
					start={range[0]}
					end={range[1]}
					window={win}
					{live}
					{cursor}
					{related}
					{density}
					rows={feed}
					{spans}
					{olderBefore}
					onbrush={brush}
					oncursor={(v) => {
						if (!live) dockState.cursor = v;
					}}
					{onpick}
					onfit={() => pickRange('fit')}
					newest={newestRow}
					{lang}
				/>
			{/if}
		{:else if tab === 'audit'}
			<!-- the audit and AI-trace tables load when their tab is shown (FIX-E-PERF2):
			     the workspace frame mounts this dock as its timeline tab only -->
			<LazyMount
				load={loadAuditTable}
				scope={dockState.auditScope}
				filter={dockState.auditFilter}
				onscope={(s: AuditScope) => (dockState.auditScope = s)}
				onfilter={(f: AuditFilter) => (dockState.auditFilter = f)}
				eventDisabled={selection.current ? null : L('an_au_scope_event_none')}
				officer={ops.officerOn}
				{lang}
			/>
		{:else}
			<LazyMount load={loadAuditTable} mode="ai" scope="city" filter={dockState.aiFilter} items={aiItems} onfilter={(f: AuditFilter) => (dockState.aiFilter = f)} scopes={false} officer={ops.officerOn} {lang} />
		{/if}
	</div>
</section>

<style>
	.dock {
		position: relative;
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		min-width: 0;
		color: var(--v-ink-1);
		font-size: 12px;
		line-height: 16px;
	}

	/* inside the frame the body keeps its geometry even when the frame lets the dock take its content's height (map mode) */
	.dock.in-frame[data-density='compact'] .body {
		min-height: 88px;
	}

	.dock.in-frame[data-density='full'] .body {
		min-height: 242px;
	}

	.head {
		display: flex;
		align-items: center;
		gap: 4px;
		flex: 0 0 auto;
		height: 36px;
		padding: 0 8px 0 16px;
		border-bottom: 1px solid var(--v-line-1);
		min-width: 0;
		overflow: hidden;
		white-space: nowrap;
	}

	.tabs {
		display: flex;
		align-items: stretch;
		gap: 20px;
		height: 100%;
	}

	.tab {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 100%;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		font-size: 14px;
		cursor: pointer;
	}

	.tab:hover,
	.tab.on {
		color: var(--v-primary-text);
	}

	/* the tab underline: 3 px in the primary text ink (Blueprint) */
	.tab.on {
		box-shadow: inset 0 -3px 0 var(--v-primary-text);
	}

	.tab:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.count {
		display: inline-flex;
		align-items: center;
		height: 18px;
		padding: 0 6px;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		color: var(--v-ink-2);
		font-size: 12px;
		font-variant-numeric: tabular-nums;
	}

	.sep {
		width: 1px;
		height: 16px;
		margin: 0 6px;
		background: var(--v-line-2);
		flex: 0 0 auto;
	}

	.sep.tall {
		height: 20px;
		margin: 0 8px 0 14px;
	}

	.grow {
		flex: 1 1 auto;
	}

	.rng {
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.ctl-row {
		display: flex;
		align-items: center;
		gap: 4px;
		height: 32px;
		padding: 0 8px 0 16px;
		flex: 0 0 auto;
		white-space: nowrap;
		overflow: hidden;
	}

	/* the frame's tab row is 36 px above the body; the controls fill its free part (right of the tabs, left of its size button) */
	.ctl-row.overlay {
		position: absolute;
		top: -36px;
		right: 44px;
		height: 36px;
		padding: 0 0 0 14px;
		z-index: 1;
		box-shadow: inset 1px 0 0 var(--v-line-2);
		box-sizing: border-box;
		background-clip: padding-box;
	}

	.body {
		position: relative;
		flex: 1 1 auto;
		min-height: 0;
	}
</style>
