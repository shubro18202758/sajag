<script lang="ts">
	/**
	 * Coord — a WGS 84 position in the identifier face:
	 * "19.0176° N 72.8562° E" (4 decimals ≈ 11 m). Coordinates are the other
	 * thing besides identifiers that the mono face is for.
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { fmtCoord } from './format';

	interface Props extends HTMLAttributes<HTMLSpanElement> {
		lat: number | null | undefined;
		lon: number | null | undefined;
		digits?: number;
	}

	let { lat, lon, digits = 4, class: cls = '', ...rest }: Props = $props();
</script>

<span data-ui="coord" class={['coord', cls]} {...rest}>{fmtCoord(lat, lon, digits)}</span>

<style>
	.coord {
		font-family: var(--v-font-mono);
		font-size: max(12px, 0.9em);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
</style>
