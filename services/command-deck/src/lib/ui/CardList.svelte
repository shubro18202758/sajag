<script lang="ts">
	/**
	 * CardList — Cards stacked as one bordered list: no gaps, hairline
	 * dividers, the list (not each card) carries the radius and elevation.
	 * `bordered={false}` drops the outer frame (inside a dock).
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		bordered?: boolean;
		compact?: boolean;
		children?: Snippet;
	}

	let { bordered = true, compact = false, children, class: cls = '', ...rest }: Props = $props();
</script>

<div data-ui="card-list" role="list" class={['list', bordered && 'bordered', compact && 'compact', cls]} {...rest}>
	{@render children?.()}
</div>

<style>
	.list {
		display: flex;
		flex-direction: column;
		overflow: hidden;
		background: var(--v-surface-1);
	}

	.bordered {
		border-radius: var(--v-radius-panel);
		box-shadow: var(--v-elev-0);
	}

	.list > :global([data-ui='card']) {
		border-radius: 0;
		box-shadow: none;
	}

	.list > :global([data-ui='card']:not(:last-child)) {
		border-bottom: 1px solid var(--v-line-1);
	}

	.list > :global([data-ui='card'].interactive:hover) {
		box-shadow: none;
		background: var(--v-row-hover);
	}

	.compact > :global([data-ui='card']) {
		padding: 8px 12px;
	}
</style>
