<script lang="ts">
	/**
	 * One object-page block (V3-SPEC §6.3): a surface-1 card, a quiet 13 px heading (the section's name, read
	 * by screen readers as the region's label) and its body. Decorative only — no state.
	 */
	import type { Snippet } from 'svelte';

	let {
		title = null,
		testid = undefined,
		flush = false,
		children,
		...rest
	}: { title?: string | null; testid?: string; flush?: boolean; children: Snippet; [k: string]: unknown } = $props();
	const uid = $props.id();
</script>

<section class={['panel', flush && 'flush']} aria-labelledby={title ? `obj-p-${uid}` : undefined} data-testid={testid} {...rest}>
	{#if title}<h2 class="ttl" id={`obj-p-${uid}`}>{title}</h2>{/if}
	{@render children()}
</section>

<style>
	.panel {
		display: flex;
		flex-direction: column;
		gap: 14px;
		min-width: 0;
		padding: 22px 24px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}

	.flush {
		padding: 18px 20px;
	}

	.ttl {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 700;
		line-height: var(--v3-lh-meta);
	}

	@media (max-width: 1500px) {
		.panel {
			padding: 18px 20px;
		}
	}
</style>
