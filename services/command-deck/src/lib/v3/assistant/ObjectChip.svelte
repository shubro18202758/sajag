<script lang="ts">
	/**
	 * ObjectChip (V3-SPEC §5.7) — an object the assistant named, inside the sentence: its glyph and its label (a
	 * mark arrives masked through ops.text), an orange border when a decision waits on it. A button: it selects
	 * the object everywhere and opens it (the page decides where — Decide when a decision waits, else the map).
	 */
	import Glyph from '../Glyph.svelte';

	let { label, glyph, decide = false, title = null, onopen }: { label: string; glyph: string; decide?: boolean; title?: string | null; onopen: () => void } = $props();
</script>

<button type="button" class={['obj', decide && 'dec']} title={title ?? undefined} data-testid="v3-obj-chip" data-decide={decide ? 'true' : 'false'} onclick={onopen}
	><Glyph name={glyph} size={15} />{label}</button
>

<style>
	.obj {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		height: 26px;
		padding: 0 8px 0 6px;
		margin: 0 1px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-s);
		background: var(--v3-s2);
		color: var(--v3-t1);
		font: inherit;
		font-size: 14px;
		font-weight: 600;
		line-height: 1;
		vertical-align: 1px;
		cursor: pointer;
		white-space: nowrap;
	}

	.obj :global(.v3-glyph) {
		color: var(--v3-t2);
	}

	.obj:hover {
		background: var(--v3-s3);
	}

	.obj:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.dec {
		border-color: var(--v3-decide-line);
	}
</style>
