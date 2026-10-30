<script lang="ts">
	/**
	 * LayerRail — MapLegend bound to a layer list, rebuilt on src/lib/ui
	 * (SPEC §5.2): a sunk panel of legend rows with their eye toggles. The
	 * layer registry stays with the canvas (this component never imports
	 * $lib/gods-eye/**); callers map GodsEyeLayer + LayerCoverageStats into
	 * plain legend items:
	 *
	 *   items = GODS_EYE_LAYERS.map((l) => ({
	 *     id: l.id, label: l.label,
	 *     colorToken: '<token>', state: on ? 'on' : 'off', hint: stats.hint
	 *   }))
	 */
	import MapLegend, { type LegendItem } from './MapLegend.svelte';

	interface Props {
		items: LegendItem[];
		onToggle?: ((id: string) => void) | null;
		lang?: string;
	}

	let { items, onToggle = null, lang }: Props = $props();
</script>

<aside class="rail" data-prim="layer-rail">
	<MapLegend {items} {onToggle} {lang} />
</aside>

<style>
	.rail {
		display: flex;
		flex-direction: column;
		padding: 4px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-sink);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}
</style>
