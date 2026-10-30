<script lang="ts">
	/**
	 * Inline runs through the formatter: text, identifiers (Id), times (Time,
	 * IST), windows (TimeRange: one run at one precision) and registration
	 * marks (Plate, masked unless an officer is named). With `plateHook` the
	 * first mark carries the pinned `dossier-plate` hook.
	 */
	import { Id, Plate, Time, TimeRange } from '$lib/ui';
	import type { Run } from '../../kinds/common';

	let { runs, plateHook = false, anchor }: { runs: readonly Run[]; plateHook?: boolean; anchor?: number } = $props();

	const isPlate = (r: Run): r is { plate: string | null; masked: boolean } => 'plate' in r;
	const isId = (r: Run): r is { id: string } => 'id' in r;
	const isTime = (r: Run): r is { time: number | null; seconds?: boolean } => 'time' in r;
	const isRange = (r: Run): r is { start: number; end: number | null } => 'start' in r;
	const textOf = (r: Run) => ('text' in r ? r.text : '');
	const firstPlate = $derived(runs.findIndex(isPlate));
</script>

{#each runs as r, i (i)}{#if isPlate(r)}{#if plateHook && i === firstPlate}<span class="dp" data-testid="dossier-plate"><Plate mark={r.plate} masked={r.masked} /></span>{:else}<Plate mark={r.plate} masked={r.masked} />{/if}{:else if isId(r)}<Id value={r.id} />{:else if isTime(r)}<Time value={r.time} seconds={r.seconds} {anchor} />{:else if isRange(r)}<TimeRange start={r.start} end={r.end} {anchor} />{:else}{textOf(r)}{/if}{/each}

<style>
	.dp {
		display: inline-flex;
		align-items: center;
	}
</style>
