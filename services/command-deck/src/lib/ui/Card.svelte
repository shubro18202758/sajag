<script lang="ts">
	/**
	 * Card — a raised block (elevation 0–4) with 16 px padding (12 compact).
	 * `interactive` adds hover lift and a pointer; `selected` uses
	 * .is-selected (the data active-state rule). With onclick and
	 * interactive the card is keyboard-activatable (role="button").
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		elevation?: 0 | 1 | 2 | 3 | 4;
		interactive?: boolean;
		selected?: boolean;
		compact?: boolean;
		children?: Snippet;
	}

	let {
		elevation = 0,
		interactive = false,
		selected = false,
		compact = false,
		children,
		class: cls = '',
		...rest
	}: Props = $props();

	function activate(e: KeyboardEvent) {
		if (e.key !== 'Enter' && e.key !== ' ') return;
		e.preventDefault();
		(e.currentTarget as HTMLElement).click();
	}
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex (role is "button" whenever tabindex is set) -->
<div
	data-ui="card"
	class={['card', `e${elevation}`, interactive && 'interactive', compact && 'compact', selected && 'is-selected', cls]}
	role={interactive ? 'button' : undefined}
	tabindex={interactive ? 0 : undefined}
	aria-pressed={interactive && selected ? 'true' : undefined}
	onkeydown={interactive ? activate : undefined}
	{...rest}
>
	{@render children?.()}
</div>

<style>
	.card {
		box-sizing: border-box;
		padding: 16px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		transition: box-shadow var(--v-dur-out) var(--v-ease);
	}

	.compact {
		padding: 12px;
	}

	.e0 {
		box-shadow: var(--v-elev-0);
	}

	.e1 {
		box-shadow: var(--v-elev-1);
	}

	.e2 {
		box-shadow: var(--v-elev-2);
	}

	.e3 {
		box-shadow: var(--v-elev-3);
	}

	.e4 {
		box-shadow: var(--v-elev-4);
	}

	.interactive {
		cursor: pointer;
	}

	.interactive:hover {
		box-shadow: var(--v-elev-2);
	}

	.interactive:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 2px;
	}

	.card.is-selected {
		background: var(--v-surface-1);
		background-image: linear-gradient(var(--v-primary-veil), var(--v-primary-veil));
		box-shadow:
			inset 2px 0 0 var(--v-primary-text),
			var(--v-elev-0);
	}
</style>
