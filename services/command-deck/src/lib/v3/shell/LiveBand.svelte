<script lang="ts">
	/**
	 * LiveBand (V3-SPEC §3.1, §5.1, §7.3) — "live operations are never hidden": the v2 LiveStrip as a 36 px band directly under
	 * the V3 top bar, the SAME place on every page that has something live to show (a movement, a pursuit, a decision with a
	 * deadline, an interrupt). V3Shell draws it from `commandBar.live`, which the operator pages and /comms fill
	 * (liveStripFeed); Home and Map already show what is live and supply none, so they carry no band. It stays the v2
	 * component — the same markup, the same test ids (`live-strip`, `data-live-seg`, `interrupt`) — drawn with the V3 tokens.
	 * It owns no data and imports no store (R4): everything arrives masked by the page.
	 */
	import { commandBar, liveHasContent } from '$lib/shell/command-bar.svelte';
	import LiveStrip from '$lib/shell/LiveStrip.svelte';

	const live = $derived(liveHasContent(commandBar.live) ? commandBar.live : null);
	const lang = $derived(commandBar.lang);
</script>

{#if live}
	<div class="live" data-v3="live-band"><LiveStrip {live} {lang} /></div>
{/if}

<style>
	.live {
		grid-row: 2;
		grid-column: 2;
		min-width: 0;
		--v-ws-strip: 36px;
		--v-surface-2: var(--v3-s1);
		--v-line-1: var(--v3-line-1);
		--v-line-2: var(--v3-line-1);
		--v-ink-1: var(--v3-t1);
		--v-ink-2: var(--v3-t2);
		--v-hover: var(--v3-s3);
		--v-text-xs: var(--v3-text-meta);
		--v-text-base: var(--v3-text-body);
		border-bottom: 1px solid var(--v3-line-1);
		background: var(--v3-s1);
	}

	@media (max-width: 720px) {
		.live {
			grid-column: 1;
		}
	}

	.live :global(.strip) {
		padding: 0 var(--v3-gut);
		border-bottom: 0;
	}
</style>
