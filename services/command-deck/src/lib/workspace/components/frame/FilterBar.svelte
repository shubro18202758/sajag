<script lang="ts">
	/**
	 * The filter and travel bar (plan R24 — the frame's, not the timeline's).
	 *
	 * - While a time window is set (not live): "Viewing 01:20–01:42 IST · not
	 *   live" with the one **Return to live** (`return-to-live` →
	 *   workspace.returnToLive()). S4's timeline only sets and clears the
	 *   window.
	 * - Each filter is a removable chip; "Clear filters" clears them all.
	 * - When a filter hides protected objects (a live movement, a pursuit, a
	 *   waiting decision, a recent watchlist read: SPEC §7.3), the warning tag
	 *   "n live objects hidden" says so, with a Show action that removes the
	 *   filters hiding them.
	 * - With a selection and a window: "18 of 51 linked in window" (the scope
	 *   word is in the label; faded objects are not removed).
	 */
	import { ACTION_ICON } from '$lib/design/icons';
	import { Button, CompoundTag, Icon, Tag, TimeRange, Tooltip } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.workspace';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { inWindowLabel } from '../../selectors';
	import { hourOf, workspace } from '../../workspace.svelte';
	import { passesFilter } from '../../watches';
	import { selectors } from '../../world.svelte';
	import type { Filter } from '../../types';

	let { lang, now }: { lang: string; now: number } = $props();
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	const w = $derived(workspace.timeWindow);
	const filters = $derived(workspace.filters);
	const hidden = $derived(workspace.protectedHidden);
	const linked = $derived(w && selection.current ? selectors.linked(selection.current) : []);
	const inWin = $derived(w ? linked.filter((o) => selectors.inWindow(o, w)).length : 0);
	const empty = $derived(!w && !filters.length);

	const FIELD_KEY: Record<Filter['field'], string> = {
		kind: 'ws_p_kind',
		state: 'ws_p_status',
		source: 'ws_p_source',
		hour: 'ws_filter_hour',
		road: 'ws_p_road',
		camera: 'ws_p_camera',
		urns: 'ws_filter_objects',
	};

	/** Show: drop the filters that hide a protected object. */
	function showHidden() {
		for (const f of filters) {
			if (hidden.some((r) => !passesFilter(r, f, hourOf))) workspace.removeFilter(f.id);
		}
	}
</script>

<div class="fbar" class:empty data-testid="filter-bar" role="toolbar" aria-label={L('ws_frame_label')}>
	{#if w}
		<span class="travel" data-testid="travel-bar">
			<Icon name="time" size={16} />
			<span>{L('ws_travel_viewing')}</span>
			<TimeRange start={w[0]} end={w[1]} anchor={now} suffix />
			<span>· {L('ws_travel_not_live')}</span>
			<Button minimal small icon={ACTION_ICON.return_to_live} data-testid="return-to-live" onclick={() => workspace.returnToLive()}>{L('ws_return_to_live')}</Button>
		</span>
	{/if}
	{#each filters as f (f.id)}
		<CompoundTag
			left={L(FIELD_KEY[f.field])}
			value={f.label}
			icon="filter"
			removable
			onremove={() => workspace.removeFilter(f.id)}
			data-filter-id={f.id}
			data-filter-field={f.field}
		/>
	{/each}
	{#if filters.length}
		<Button minimal small onclick={() => workspace.clearFilters()}>{L('ws_clear_filters')}</Button>
	{/if}
	{#if hidden.length}
		<Tooltip content={L('ws_live_hidden_tip')}>
			<Tag intent="warning" icon={ACTION_ICON.layer_hidden} data-testid="live-hidden" data-count={hidden.length}>{L('ws_live_hidden', hidden.length)}</Tag>
		</Tooltip>
		<Button minimal small data-testid="live-hidden-show" onclick={showHidden}>{L('ws_show')}</Button>
	{/if}
	<span class="grow"></span>
	{#if w && selection.current}
		<span class="scope">{inWindowLabel(inWin, linked.length, lang)}</span>
	{/if}
</div>

<style>
	.fbar {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 36px;
		padding: 4px 8px 4px 16px;
		border-bottom: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
		min-width: 0;
		overflow: hidden;
		white-space: nowrap;
	}

	/* empty: still a grid item of the centre (zero height), so the views keep their row */
	.fbar.empty {
		min-height: 0;
		height: 0;
		padding: 0;
		border: 0;
	}

	.travel {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		height: 24px;
		padding: 0 4px 0 8px;
		border-radius: var(--v-radius-chip);
		background: var(--v-primary-veil);
		color: var(--v-ink-1);
		font-size: 12px;
		flex: 0 0 auto;
	}

	.travel :global(svg) {
		color: var(--v-primary-text);
	}

	.grow {
		flex: 1 1 auto;
	}

	.scope {
		font-size: 12px;
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
	}
</style>
