<script lang="ts">
	/**
	 * DataTile — one of the commander's counters, rebuilt as src/lib/ui's
	 * MetricCard (SPEC §5.2): a 12 px caption (sentence case: its first
	 * letter capitalised, HI and MR untouched), the value in Inter 600 with
	 * tabular figures (a zero recedes to ink-2 at 400), the unit, and the
	 * source honesty tag (live, emulated, fixture …) as its sub line. A tile
	 * with `onClick` is a button around the card. `data-prim="data-tile"`
	 * stays on the root (the /ops wall keeps exactly four).
	 */
	import MetricCard from '$lib/ui/MetricCard.svelte';
	import Badge, { type BadgeVariant } from './Badge.svelte';
	import { sentenceStart } from './text';

	interface Props {
		label: string;
		value: string | number;
		unit?: string;
		/** Source honesty chip (live / fixture / emulated …). */
		source?: { variant: BadgeVariant; label: string } | null;
		onClick?: (e: MouseEvent) => void;
	}

	let { label, value, unit, source = null, onClick }: Props = $props();

	const interactive = $derived(typeof onClick === 'function');
	const caption = $derived(sentenceStart(label));
</script>

{#snippet sourceTag()}
	{#if source}<Badge variant={source.variant} label={source.label} />{/if}
{/snippet}

{#if interactive}
	<button class="tile-btn" type="button" onclick={onClick} data-prim="data-tile">
		<MetricCard {caption} {value} unit={unit ?? null} sub={source ? sourceTag : null} />
	</button>
{:else}
	<MetricCard {caption} {value} unit={unit ?? null} sub={source ? sourceTag : null} class="tile" data-prim="data-tile" />
{/if}

<style>
	.tile-btn {
		display: block;
		width: 100%;
		margin: 0;
		padding: 0;
		border: 0;
		border-radius: var(--v-radius-panel);
		background: transparent;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.tile-btn:hover {
		background: var(--v-row-hover);
	}

	.tile-btn:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 2px;
	}

	:global([data-ui='metric-card'].tile) {
		background: var(--v-surface-1);
		border-radius: var(--v-radius-panel);
		box-shadow: var(--v-elev-0);
	}
</style>
