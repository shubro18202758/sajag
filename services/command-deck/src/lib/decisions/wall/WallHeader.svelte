<script lang="ts">
	/**
	 * The /ops view header (SPEC §6.3, 44 px): "Situation · Mumbai · whole
	 * city", the range presets (1 h / 6 h / 24 h / 7 d: the band chart's axis
	 * and the closed-event lists), "As of hh:mm:ss IST" (the newest answer
	 * behind the wall, not the wall clock), Share (the view header's, never
	 * the navbar's: `data-share`) and Refresh.
	 */
	import { MODULE_ICON } from '$lib/design/icons';
	import { Button, Icon, SegmentedControl } from '$lib/ui';
	import { fmtTime } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import { RANGES, type WallRange } from './range';

	interface Props {
		lang: string;
		range: WallRange;
		onrange: (r: WallRange) => void;
		/** Epoch ms of the newest answer behind the wall, or null before the first. */
		asOf: number | null;
		onshare: () => void;
		onrefresh: () => void;
		refreshing?: boolean;
	}

	let { lang, range, onrange, asOf, onshare, onrefresh, refreshing = false }: Props = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const options = $derived(RANGES.map((r) => ({ value: r, label: L(`wall_range_${r}`) })));
</script>

<header class="wall-head" data-wall="header">
	<Icon name={MODULE_ICON.situation} size={20} />
	<h1 class="h">{L('wall_title')}</h1>
	<span class="scope">{L('wall_scope')}</span>
	<span class="grow"></span>
	<SegmentedControl {options} value={range} onchange={(v) => onrange(v)} label={L('wall_range_label')} />
	<span class="asof" title={L('wall_as_of_tip')}>
		{#if asOf}{L('wall_as_of', fmtTime(asOf, { seconds: true }))}{:else}{L('wall_as_of_none')}{/if}
	</span>
	<Button minimal small icon="link" tooltip={L('wall_share_tip')} data-share onclick={onshare}>{L('wall_share')}</Button>
	<Button minimal small icon="refresh" tooltip={L('wall_refresh')} aria-label={L('wall_refresh')} loading={refreshing} onclick={onrefresh} />
</header>

<style>
	.wall-head {
		flex: none;
		display: flex;
		align-items: center;
		gap: 12px;
		min-width: 0;
		height: 44px;
		padding: 0 8px 0 16px;
		background: var(--v-surface-1);
		border-bottom: 1px solid var(--v-line-2);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.wall-head > :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.h {
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: 20px;
		white-space: nowrap;
	}

	.scope {
		min-width: 0;
		overflow: hidden;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.grow {
		flex: 1 1 auto;
	}

	.asof {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
</style>
