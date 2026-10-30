<script lang="ts">
	/**
	 * ButtonGroup — Buttons side by side as one control (a toolbar group, a
	 * view switch). Inner corners square off; `minimal` groups keep their
	 * buttons flat; `vertical` stacks them; `fill` stretches them equally.
	 * The active button of a toggle group sets `pressed` (.is-pressed).
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		minimal?: boolean;
		vertical?: boolean;
		fill?: boolean;
		children?: Snippet;
	}

	let { minimal = false, vertical = false, fill = false, children, class: cls = '', ...rest }: Props = $props();
</script>

<div data-ui="button-group" role="group" class={['group', minimal && 'minimal', vertical && 'vertical', fill && 'fill', cls]} {...rest}>
	{@render children?.()}
</div>

<style>
	.group {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: stretch;
		border-radius: var(--v-radius-btn);
		vertical-align: middle;
	}

	.group :global([data-ui='button']) {
		border-radius: 0;
	}

	.group :global([data-ui='button']:focus-visible) {
		outline-offset: -2px;
	}

	.group > :global(:first-child [data-ui='button']),
	.group > :global([data-ui='button']:first-child) {
		border-top-left-radius: var(--v-radius-btn);
		border-bottom-left-radius: var(--v-radius-btn);
	}

	.group > :global(:last-child [data-ui='button']),
	.group > :global([data-ui='button']:last-child) {
		border-top-right-radius: var(--v-radius-btn);
		border-bottom-right-radius: var(--v-radius-btn);
	}

	/* non-minimal buttons share one hairline between them */
	.group:not(.minimal) > :global(* + *) {
		margin-left: -1px;
	}

	.minimal {
		gap: 2px;
	}

	.minimal :global([data-ui='button']) {
		border-radius: var(--v-radius-btn);
	}

	.vertical {
		flex-direction: column;
	}

	.vertical > :global(*) {
		margin-left: 0;
	}

	.vertical:not(.minimal) > :global(* + *) {
		margin-left: 0;
		margin-top: -1px;
	}

	.vertical > :global(:first-child [data-ui='button']),
	.vertical > :global([data-ui='button']:first-child) {
		border-radius: var(--v-radius-btn) var(--v-radius-btn) 0 0;
	}

	.vertical > :global(:last-child [data-ui='button']),
	.vertical > :global([data-ui='button']:last-child) {
		border-radius: 0 0 var(--v-radius-btn) var(--v-radius-btn);
	}

	.fill {
		display: flex;
		width: 100%;
	}

	.fill > :global(*) {
		flex: 1 1 0;
	}
</style>
