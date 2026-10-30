<script lang="ts">
	/**
	 * A V3 tag (V3-SPEC §4.2, §5.2): a pill whose colour is its meaning — decide (a named officer must
	 * decide), ai (written or proposed by the assistant), alert (a stolen / watchlisted vehicle), ok
	 * (approved, official), route (a protected movement), neutral, ghost (news-reported) and dashed
	 * (unverified, emulated, simulated). Never colour alone: every tag carries its words.
	 */
	import type { Snippet } from 'svelte';
	import Glyph from '../Glyph.svelte';

	let {
		tone = 'neutral',
		glyph = null,
		title = null,
		size = 'md',
		glass = false,
		children,
	}: { tone?: string; glyph?: string | null; title?: string | null; size?: 'sm' | 'md'; glass?: boolean; children: Snippet } = $props();
</script>

<span class={['tag', `tone-${tone}`, size === 'sm' && 'sm', glass && 'glass']} title={title ?? undefined} data-tone={tone}
	>{#if glyph}<Glyph name={glyph} size={size === 'sm' ? 13 : 15} />{/if}{@render children()}</span
>

<style>
	.tag {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 26px;
		padding: 0 10px;
		border-radius: 13px;
		background: var(--v3-s3);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 600;
		line-height: 1;
		white-space: nowrap;
	}

	.tag :global(.v3-glyph) {
		stroke-width: 2;
	}

	.sm {
		height: 22px;
		padding: 0 8px;
		font-size: var(--v3-text-micro);
	}

	.tone-decide {
		background: var(--v3-decide-veil);
		color: var(--v3-decide-text);
	}

	.tone-ai {
		background: var(--v3-ai-veil);
		color: var(--v3-ai-text);
	}

	.tone-alert {
		background: var(--v3-alert-veil);
		color: var(--v3-alert-text);
	}

	.tone-ok {
		background: var(--v3-ok-veil);
		color: var(--v3-ok-text);
	}

	.tone-route {
		background: var(--v3-route-veil);
		color: var(--v3-route-text);
	}

	.tone-brand {
		background: var(--v3-brand-veil);
		color: var(--v3-brand-text);
	}

	.tone-ghost {
		border: 1px solid var(--v3-line-3);
		background: transparent;
	}

	.tone-dashed {
		border: 1px dashed var(--v3-dashed);
		background: transparent;
		color: var(--v3-t2);
	}

	/* over a map: an opaque ground so the words stay legible on any tile */
	.glass.tone-ghost,
	.glass.tone-dashed,
	.glass.tone-neutral {
		background: var(--v3-glass);
	}

	.glass.tone-decide {
		background: linear-gradient(var(--v3-decide-veil), var(--v3-decide-veil)), var(--v3-glass);
	}

	.glass.tone-alert {
		background: linear-gradient(var(--v3-alert-veil), var(--v3-alert-veil)), var(--v3-glass);
	}

	.glass.tone-route {
		background: linear-gradient(var(--v3-route-veil), var(--v3-route-veil)), var(--v3-glass);
	}

	.glass.tone-ok {
		background: linear-gradient(var(--v3-ok-veil), var(--v3-ok-veil)), var(--v3-glass);
	}

	.glass.tone-ai {
		background: linear-gradient(var(--v3-ai-veil), var(--v3-ai-veil)), var(--v3-glass);
	}
</style>
