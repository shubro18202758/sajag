<script lang="ts">
	/**
	 * A provenance tag on the public pages (V3-SPEC §4.2, §8): the words are the label, the colour only supports them.
	 *   live        the feed answered (clear green)
	 *   dashed      simulated / emulated / unverified / offline preview — outlined, never filled, never a live colour
	 *   neutral     anything else
	 * The label is shown sentence-cased (the first Latin letter capitalised; Devanagari and Marathi pass through), the
	 * way every deck badge shows it, so the strings the smokes pin read the same. No hidden extra text: the tag's text
	 * IS the label.
	 */
	import Glyph from '../Glyph.svelte';
	import { sentenceStart } from '$lib/primitives/text';

	let {
		tone = 'neutral',
		glyph = null,
		label,
		title = null,
	}: { tone?: 'live' | 'dashed' | 'neutral'; glyph?: string | null; label: string; title?: string | null } = $props();
</script>

<span class={['ptag', `tone-${tone}`]} title={title ?? undefined}>{#if glyph}<Glyph name={glyph} size={16} />{/if}<span class="tx">{sentenceStart(label)}</span></span>

<style>
	.ptag {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		max-width: 100%;
		min-height: 28px;
		padding: 2px 12px;
		border-radius: 14px;
		background: var(--v3-s3);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 600;
		line-height: var(--v3-lh-meta);
	}

	.ptag :global(.v3-glyph) {
		stroke-width: 2;
	}

	.tx {
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.tone-live {
		background: var(--v3-ok-veil);
		color: var(--v3-ok-text);
	}

	.tone-dashed {
		border: 1px dashed var(--v3-dashed);
		background: transparent;
		color: var(--v3-t2);
	}
</style>
