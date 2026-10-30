<script lang="ts">
	/**
	 * Kbd — a key cap ("Ctrl", "K", "?"). `keys` renders a combination, each
	 * key its own cap; or pass children for one cap.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';

	interface Props extends HTMLAttributes<HTMLElement> {
		keys?: readonly string[];
		children?: Snippet;
	}

	let { keys = [], children, class: cls = '', ...rest }: Props = $props();
</script>

{#if keys.length}
	<span data-ui="kbd" class={['combo', cls]} {...rest}>
		{#each keys as k, i (i)}<kbd class="kbd">{k}</kbd>{/each}
	</span>
{:else}
	<kbd data-ui="kbd" class={['kbd', cls]} {...rest}>{@render children?.()}</kbd>
{/if}

<style>
	.combo {
		display: inline-flex;
		align-items: center;
		gap: 2px;
		vertical-align: middle;
	}

	.kbd {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		box-sizing: border-box;
		min-width: 20px;
		height: 20px;
		padding: 0 4px;
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-3);
		color: var(--v-ink-2);
		box-shadow:
			inset 0 0 0 1px var(--v-line-1),
			inset 0 -1px 0 var(--v-line-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: 1;
		white-space: nowrap;
		vertical-align: middle;
	}
</style>
