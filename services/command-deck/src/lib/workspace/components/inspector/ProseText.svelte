<script lang="ts">
	/**
	 * Server text with its identifiers through the formatter: camera and
	 * junction ids as Id, masked registration marks as Plate. The text is
	 * already humanised (display.ts) and masked by the caller. A figure and
	 * its unit ("95 km/h") never break across lines; the text is unchanged.
	 */
	import { Id, Plate } from '$lib/ui';

	let { text }: { text: string } = $props();

	const TOKEN = /\b(EM-[A-Z0-9-]+|CAM-[A-Z0-9-]+|J\d{1,4}\b|[A-Z]{2}\d{1,2}[A-Z]{0,3}•••\d|\d+(?:\.\d+)? (?:km\/h|km)\b)/g;

	const parts = $derived.by(() => {
		const out: { s: string; k: 'text' | 'id' | 'mark' | 'unit' }[] = [];
		let at = 0;
		for (const m of text.matchAll(TOKEN)) {
			const i = m.index ?? 0;
			if (i > at) out.push({ s: text.slice(at, i), k: 'text' });
			out.push({ s: m[0], k: m[0].includes('•') ? 'mark' : /^\d/.test(m[0]) ? 'unit' : 'id' });
			at = i + m[0].length;
		}
		if (at < text.length) out.push({ s: text.slice(at), k: 'text' });
		return out;
	});
</script>

{#each parts as p, i (i)}{#if p.k === 'mark'}<Plate mark={p.s} masked />{:else if p.k === 'id'}<Id value={p.s} />{:else if p.k === 'unit'}<span class="nw">{p.s}</span>{:else}{p.s}{/if}{/each}

<style>
	.nw {
		white-space: nowrap;
	}
</style>
