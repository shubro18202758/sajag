<script lang="ts">
	/** The microphone glyph (the V3 set's grid and stroke: 24 units, 1.8, round caps): the voice report's one mark. */
	let { size = 20 }: { size?: number } = $props();
</script>

<svg class="v3-glyph mic" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
	<path d="M12 3.5a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0v-5a3 3 0 0 0-3-3zM6 11.2a6 6 0 0 0 12 0M12 17.2v3.3M8.8 20.5h6.4" />
</svg>

<style>
	.mic {
		flex: none;
		fill: none;
		stroke: currentColor;
		stroke-width: 1.8;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
