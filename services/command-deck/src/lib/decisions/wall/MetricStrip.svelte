<script lang="ts">
	/**
	 * The /ops metric strip (SPEC §5.3, §6.3): one 76 px row of eight
	 * MetricCards on the canvas, 1 px dividers between them. The four
	 * commander counters carry `data-prim="data-tile"`, `data-counter` and
	 * `data-value` (the model in metrics.ts sets exactly four); the other four
	 * are plain figures. A zero recedes (MetricCard: ink-2 at 400). The
	 * sparklines (corridor speed, watchlist reads) show from 1600 px up only:
	 * below that the strip is too narrow for a line to say anything.
	 */
	import { Icon, MetricCard, Tooltip } from '$lib/ui';
	import type { MetricCell } from './metrics';

	interface Props {
		cells: readonly MetricCell[];
		/** The viewport is at least 1600 px wide (sparklines on). */
		wide?: boolean;
	}

	let { cells, wide = false }: Props = $props();
</script>

<div class="strip" role="group" data-wall="metric-strip">
	{#each cells as c, i (c.key)}
		{#snippet sub()}{#if c.subIcon}<Icon name={c.subIcon} size={12} />{/if}<span>{c.sub ?? ''}</span>{/snippet}
		<Tooltip content={c.tooltip} placement="bottom">
			<div class="cell" class:first={i === 0} data-metric={c.key}>
				{#if c.counter}
					<MetricCard
						caption={c.caption}
						value={c.value}
						unit={c.unit}
						sub={c.sub != null ? sub : null}
						intent={c.intent}
						spark={wide ? c.spark : null}
						zero={c.zero}
						large
						data-prim="data-tile"
						data-counter={c.counter}
						data-value={String(c.value ?? '')}
					/>
				{:else}
					<MetricCard
						caption={c.caption}
						value={c.value}
						unit={c.unit}
						sub={c.sub != null ? sub : null}
						intent={c.intent}
						spark={wide ? c.spark : null}
						zero={c.zero}
						large
					/>
				{/if}
			</div>
		</Tooltip>
	{/each}
</div>

<style>
	.strip {
		flex: none;
		display: grid;
		grid-template-columns: repeat(8, minmax(0, 1fr));
		min-width: 0;
		height: 76px;
		background: var(--v-canvas);
		border-bottom: 1px solid var(--v-line-2);
	}

	.cell {
		min-width: 0;
		overflow: hidden;
		border-left: 1px solid var(--v-line-1);
	}

	/* the Tooltip wrappers are display: contents, so each .cell is a grid item */
	.cell.first {
		border-left: 0;
	}

	.cell :global([data-ui='metric-card']) {
		height: 100%;
		box-sizing: border-box;
	}

	@media (max-width: 1599px) {
		.cell :global([data-ui='metric-card']) {
			padding-left: 12px;
		}
	}

	/* a phone: two rows of four, each figure with room for its label */
	@media (max-width: 720px) {
		.strip {
			grid-template-columns: repeat(4, minmax(0, 1fr));
			grid-auto-rows: 76px;
			height: auto;
		}
	}
</style>
