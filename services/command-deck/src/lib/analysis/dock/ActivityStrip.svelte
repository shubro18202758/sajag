<script lang="ts">
	/**
	 * The inspector's activity strip (registered with registerActivityRenderer,
	 * props {row, dossier}): the object's own activity over the last 6 h as
	 * one line of ticks — the timeline's colour rule (an officer's action
	 * taller; red a watchlist read; orange a decision waiting) — and "Show in
	 * the timeline", which opens the bottom dock's Timeline tab, where the
	 * object's rows are drawn in blue (linked to the selection).
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.analysis';
	import { Button } from '$lib/ui';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import type { Dossier } from '$lib/gods-eye/city-api';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import type { ObjectRow } from '$lib/workspace/types';
	import { HOUR } from '../timeline/bins';
	import { isOfficerAction, toneOf } from '../timeline/lanes';
	import { dockState } from './dock-state.svelte';

	let { row, dossier }: { row: ObjectRow; dossier: Dossier | null } = $props();

	const lang = $derived(commandBar.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const now = $derived(dockState.clockOverride ?? Date.now());
	const start = $derived(now - 6 * HOUR);
	const rows = $derived((dossier?.audit ?? []).filter((r) => r.t >= start && r.t <= now));
	const W = 320;
	const x = (v: number) => 2 + ((v - start) / (now - start)) * (W - 4);

	function show() {
		workspace.bottomTab = 'timeline';
		if (workspace.docks.bottom === 'off') workspace.setBottom('compact');
	}
</script>

{#if row && dossier}
	<div class="strip" data-testid="activity-strip">
		<div class="head">
			<span class="n">{L('an_act_strip', rows.length)}</span>
			<Button small minimal icon="timeline-bar-chart" onclick={show}>{L('an_act_show')}</Button>
		</div>
		<svg viewBox="0 0 {W} 20" preserveAspectRatio="none" aria-hidden="true">
			<line class="base" x1="0" x2={W} y1="19.5" y2="19.5" />
			{#each rows as r (r.id)}
				{@const tone = toneOf(r, null)}
				{@const tall = isOfficerAction(r)}
				<rect class="tick t-{tone}" x={x(r.t) - 1} y={tall ? 3 : 9} width="2" height={tall ? 16 : 10} />
			{/each}
		</svg>
	</div>
{/if}

<style>
	.strip {
		padding: 8px 0 4px;
		border-top: 1px solid var(--v-line-1);
		margin-top: 8px;
	}

	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		font-size: 12px;
		color: var(--v-ink-2);
	}

	svg {
		display: block;
		width: 100%;
		height: 20px;
		margin-top: 4px;
	}

	.base {
		stroke: var(--v-line-2);
	}

	.tick {
		fill: color-mix(in srgb, var(--v-ink-2) 70%, transparent);
	}

	.tick.t-watch {
		fill: var(--v-map-alert);
	}

	.tick.t-decision {
		fill: var(--v-map-decision);
	}
</style>
