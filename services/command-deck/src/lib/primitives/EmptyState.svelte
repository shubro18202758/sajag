<script lang="ts">
	/**
	 * EmptyState — the honest empty, rebuilt as src/lib/ui's NonIdealState
	 * (SPEC §5.2): the title, one line that says what to do, and an optional
	 * action. Every fixture-fed surface uses it instead of silence or invented
	 * data. `data-prim="empty-state"` stays on the root.
	 */
	import NonIdealState from '$lib/ui/NonIdealState.svelte';
	import Button from './Button.svelte';

	interface Props {
		title: string;
		hint?: string;
		action?: { label: string; onclick: () => void } | null;
	}

	let { title, hint, action = null }: Props = $props();
</script>

{#snippet act()}
	{#if action}
		<Button variant="secondary" size="sm" onclick={() => action.onclick()}>{action.label}</Button>
	{/if}
{/snippet}

<NonIdealState {title} description={hint ?? null} action={action ? act : undefined} class="empty" data-prim="empty-state" />

<style>
	:global(div[data-ui='non-ideal-state'].empty) {
		padding: 16px;
		gap: 8px;
	}
</style>
