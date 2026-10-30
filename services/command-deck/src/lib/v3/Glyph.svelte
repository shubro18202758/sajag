<script lang="ts">
	/**
	 * One V3 glyph (V3-SPEC §4.4): a 24-unit stroke icon in currentColor. Decorative by default
	 * (aria-hidden); pass `label` when the glyph alone carries meaning (it then becomes role="img").
	 */
	import { glyphPath } from './icons';

	let { name, size = 20, label = null, class: cls = '' }: { name: string; size?: number; label?: string | null; class?: string } =
		$props();
</script>

<svg
	class={['v3-glyph', cls]}
	viewBox="0 0 24 24"
	width={size}
	height={size}
	aria-hidden={label ? undefined : 'true'}
	role={label ? 'img' : undefined}
	aria-label={label ?? undefined}
	focusable="false"><path d={glyphPath(name)} /></svg
>

<style>
	.v3-glyph {
		flex: none;
		fill: none;
		stroke: currentColor;
		stroke-width: 1.8;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
