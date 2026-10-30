<script lang="ts">
	/**
	 * The on-premises AI panels an object page adds for its kind (loaded lazily by LazyFieldPanels, so no other page pays
	 * for them): a camera's road state from a still; a road's two-hour forecast and its waterlogging outlook.
	 */
	import type { ObjectRow } from '$lib/workspace/types';
	import RoadStatePanel from './RoadStatePanel.svelte';
	import SegmentForecastPanel from './SegmentForecastPanel.svelte';
	import SegmentWaterPanel from './SegmentWaterPanel.svelte';

	let { row, lang, officer }: { row: ObjectRow; lang: string; officer: string | null } = $props();
	const segmentId = $derived(row.kind === 'segment' && /^\d+$/.test(row.id) ? Number(row.id) : null);
</script>

{#if row.kind === 'camera'}
	<RoadStatePanel {row} {lang} {officer} />
{:else if segmentId !== null}
	<SegmentForecastPanel {segmentId} {lang} />
	<SegmentWaterPanel {segmentId} {lang} />
{/if}
