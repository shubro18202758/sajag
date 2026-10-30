<script module lang="ts">
	/**
	 * One shared 1 s clock for every mounted panel's "updated n s ago" label:
	 * a single interval, started by the first panel that shows a status and
	 * stopped with the last one.
	 */
	const clock = $state({ now: Date.now() });
	let clockUsers = 0;
	let clockTimer: ReturnType<typeof setInterval> | null = null;

	function useClock(): () => void {
		clockUsers += 1;
		if (!clockTimer) {
			clock.now = Date.now();
			clockTimer = setInterval(() => (clock.now = Date.now()), 1000);
		}
		return () => {
			clockUsers -= 1;
			if (clockUsers <= 0 && clockTimer) {
				clearInterval(clockTimer);
				clockTimer = null;
				clockUsers = 0;
			}
		};
	}
</script>

<script lang="ts">
	/**
	 * Panel — the operator surface unit, rebuilt as src/lib/ui's Section
	 * (SPEC §5.2, §3.5). The 40 px header holds the title (an h2, sentence
	 * case) and at most ONE state word: the feed's state as a tag, its age in
	 * the tag's tooltip. Everything else the header used to carry sits in a
	 * status row under it: the age ("updated 42 s ago", `.age[data-age-sec]`,
	 * ticking on the shared clock) and the caller's `header-right` controls,
	 * wrapping rather than squeezing the title. Then at most one caption, the
	 * body and an optional footer. It renders ONLY what it is given
	 * (per-panel degradation stays the panel's concern).
	 *
	 * Freshness: a status whose last update is older than 3× the panel's poll
	 * interval reads Stale whatever state the caller passed, so a Live tag
	 * can never outlive the feed behind it (the raw state stays in
	 * data-state). No glass, no sweep: a `glass` panel (the cockpit's rails
	 * over the map) is an opaque surface like every other; it still clips a
	 * squeezed body, as it always did.
	 *
	 * Squeezed by a fixed-height host, the panel shrinks into its box and only
	 * the body gives way: a `scroll` body scrolls inside the panel, never over
	 * its neighbours. `data-prim="panel"` stays on the root.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.ui';
	import Section from '$lib/ui/Section.svelte';
	import Tag from '$lib/ui/Tag.svelte';
	import { fmtDuration } from '$lib/ui/format/format';
	import { uiLang } from '$lib/ui/lang';
	import { sentenceStart } from './text';

	type PanelStatusState = 'live' | 'mixed' | 'offline' | 'not-deployed' | 'stale';

	interface Props {
		title?: string;
		sub?: string;
		status?: { state: PanelStatusState; updatedAt: number } | null;
		/**
		 * The feed's poll interval (ms). The status turns Stale after 3× this
		 * without an update. Defaults to 10 s — the slowest ops-wall cadence.
		 */
		pollMs?: number;
		pad?: 'none' | 'normal' | 'roomy';
		scroll?: boolean;
		/**
		 * Fill the parent's height: the panel stretches and its body becomes
		 * a flex column, so one child (flex: 1) can be the scroller — the
		 * wall's fixed-height audit band uses this.
		 */
		fill?: boolean;
		variant?: 'flat' | 'raised' | 'sink' | 'glass';
		lang?: string;
		children?: import('svelte').Snippet;
		'header-right'?: import('svelte').Snippet;
		footer?: import('svelte').Snippet;
	}

	let {
		title,
		sub,
		status = null,
		pollMs = 10_000,
		pad = 'normal',
		scroll = false,
		fill = false,
		variant = 'flat',
		lang,
		children,
		'header-right': headerRight,
		footer
	}: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());

	// Subscribe to the shared clock only while a status is shown (a derived
	// boolean, so a fresh status object per poll does not re-subscribe).
	let hasStatus = $derived(!!status);
	$effect(() => {
		if (!hasStatus) return;
		return useClock();
	});

	let ageSecs = $derived(
		status && status.updatedAt ? Math.max(0, Math.floor((clock.now - status.updatedAt) / 1000)) : null
	);
	let ageLabel = $derived(
		ageSecs == null ? t(L, 'never_updated') : `${t(L, 'updated_ago')} ${t(L, 'ui_ago', fmtDuration(ageSecs, L))}`
	);
	/** Older than 3× the poll interval: the feed has stopped answering. */
	let overdue = $derived(ageSecs != null && ageSecs * 1000 > 3 * pollMs);
	let shownState = $derived<PanelStatusState | null>(
		status ? (overdue && status.state !== 'not-deployed' ? 'stale' : status.state) : null
	);
	const stateTip = $derived(overdue ? `${ageLabel}. ${t(L, 'panel_overdue', Math.round(pollMs / 1000))}` : ageLabel);
</script>

{#snippet right()}
	<span class="state" data-state={shownState} data-overdue={overdue || undefined}>
		<Tag intent={shownState === 'live' ? 'success' : 'none'} tooltip={stateTip}>{sentenceStart(t(L, `panel_state_${shownState}`))}</Tag>
	</span>
{/snippet}

<Section
	title={sentenceStart(title ?? '')}
	level={2}
	variant="card"
	right={status && shownState ? right : undefined}
	class={['v-panel', `v-${variant}`, fill && 'v-fill']}
	data-prim="panel"
>
	{#if (status && shownState) || headerRight}
		<div class="meta">
			{#if status && shownState}<span class="age" class:overdue data-age-sec={ageSecs ?? ''}>{ageLabel}</span>{/if}
			{#if headerRight}<div class="meta-r">{@render headerRight()}</div>{/if}
		</div>
	{/if}
	{#if sub}<p class="caption">{sentenceStart(sub)}</p>{/if}
	<div class="body" class:scroll class:fill-body={fill} class:pad-none={pad === 'none'} class:pad-roomy={pad === 'roomy'}>
		{@render children?.()}
	</div>
	{#if footer}
		<footer class="foot">
			{@render footer()}
		</footer>
	{/if}
</Section>

<style>
	/* the Section card is the panel; variants are surfaces, never glass */
	:global(section.v-panel) {
		min-height: 0;
	}

	:global(section.v-panel.v-raised) {
		background: var(--v-surface-2);
	}

	:global(section.v-panel.v-sink) {
		background: var(--v-surface-sink);
	}

	/* Section's body is the panel's flex column, for EVERY panel (as the
	   panel itself was before the rebuild). Squeezed by a fixed-height host
	   (the cockpit's rails, the wall's bands) the panel shrinks into its box:
	   the status row, the caption and the footer keep their height and the
	   body gives way. A `scroll` body then scrolls inside the box, a `fill`
	   body hands the height to its one scroller; nothing spills onto the
	   panel's neighbours. */
	:global(section.v-panel > .body) {
		display: flex;
		flex: 1 1 auto;
		flex-direction: column;
		min-height: 0;
	}

	/* a glass panel (the cockpit's rails over the map) clips what a squeezed
	   non-scroll body cannot show, as the glass panel always did */
	:global(section.v-panel.v-glass) {
		overflow: hidden;
	}

	/* fill: the panel takes its parent's height */
	:global(section.v-panel.v-fill) {
		height: 100%;
	}

	.meta,
	.caption,
	.foot {
		flex: 0 0 auto;
	}

	/* the status row under the header: the age, then the caller's controls (they wrap, never squeeze the title) */
	.meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 4px 8px;
		min-width: 0;
		padding: 8px 16px 0;
	}

	.meta-r {
		display: flex;
		flex: 0 1 auto;
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
		gap: 4px 8px;
		min-width: 0;
		margin-left: auto;
	}

	.caption {
		margin: 0;
		padding: 8px 16px 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	/* the one part that gives way when the panel is squeezed (see above) */
	.body {
		flex: 1 1 auto;
		min-height: 0;
		padding: 12px 16px;
	}

	.pad-none {
		padding: 0;
	}

	.pad-roomy {
		padding: 16px 20px;
	}

	.scroll {
		overflow-y: auto;
	}

	.fill-body {
		display: flex;
		flex: 1 1 auto;
		flex-direction: column;
		overflow: hidden;
	}

	.state {
		display: inline-flex;
	}

	.age {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.age.overdue {
		color: var(--v-ink-1);
	}

	.foot {
		padding: 8px 16px;
		border-top: 1px solid var(--v-line-1);
	}
</style>
