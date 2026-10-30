<script lang="ts" module>
	export type LegendItemState = 'on' | 'off' | 'not-deployed' | 'empty';

	export interface LegendItem {
		id: string;
		label: string;
		/** CSS custom property name carrying the layer color. */
		colorToken: string;
		state?: LegendItemState;
		hint?: string;
	}
</script>

<script lang="ts">
	/**
	 * MapLegend — the layer legend, rebuilt on src/lib/ui (SPEC §5.2): 30 px
	 * tree-like rows with the layer's swatch (filled = shown, an outline =
	 * hidden, a neutral outline = not deployed, dimmed = empty now), its name
	 * and its one-line hint, and an EyeToggle when the caller can toggle it
	 * (an empty layer reads "None now", never broken). Maps 1:1 to the
	 * GodsEyeLayer + LayerCoverageStats contract; callers bind it, this
	 * component never imports the canvas layer modules (R4).
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import EyeToggle from '$lib/ui/EyeToggle.svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';
	import { uiLang } from '$lib/ui/lang';

	interface Props {
		items: LegendItem[];
		onToggle?: ((id: string) => void) | null;
		lang?: string;
	}

	let { items, onToggle = null, lang }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());

	const swatchStyle = (item: LegendItem) => `--layer-color: var(${item.colorToken}, var(--v-map-marker))`;
	const stateWord = (s: LegendItemState) =>
		s === 'on' ? t(L, 'legend_on') : s === 'off' ? t(L, 'legend_off') : s === 'empty' ? t(L, 'legend_empty') : t(L, 'legend_not_deployed');
</script>

<ul class="legend" data-prim="map-legend">
	{#each items as item (item.id)}
		{@const state = item.state ?? 'on'}
		<li class="row s-{state}" data-layer-id={item.id} data-state={state}>
			<Tooltip content={item.hint ?? null} placement="right">
				<span class="name">
					<i class="swatch" style={swatchStyle(item)} aria-hidden="true"></i>
					<span class="text">
						<span class="label">{item.label}</span>
						{#if item.hint}<span class="hint">{item.hint}</span>{/if}
					</span>
				</span>
			</Tooltip>
			{#if onToggle && state !== 'not-deployed'}
				<EyeToggle visible={state === 'on'} empty={state === 'empty'} label={item.label} lang={L} onchange={() => onToggle(item.id)} />
			{:else}
				<span class="word">{stateWord(state)}</span>
			{/if}
		</li>
	{/each}
</ul>

<style>
	.legend {
		display: flex;
		flex-direction: column;
		margin: 0;
		padding: 0;
		list-style: none;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.row {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 30px;
		padding: 0 4px 0 8px;
		border-radius: var(--v-radius-btn);
	}

	.row:hover {
		background: var(--v-row-hover);
	}

	.name {
		display: flex;
		flex: 1 1 auto;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.swatch {
		display: inline-block;
		flex: 0 0 auto;
		width: 10px;
		height: 10px;
		border-radius: 2px;
		background: var(--layer-color);
	}

	.s-off .swatch {
		background: transparent;
		box-shadow: inset 0 0 0 1.5px var(--layer-color);
	}

	.s-not-deployed .swatch {
		background: transparent;
		box-shadow: inset 0 0 0 1px var(--v-ink-4);
	}

	.s-empty .swatch {
		opacity: 0.4;
	}

	.text {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.label {
		overflow: hidden;
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.hint {
		overflow: hidden;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.s-not-deployed .label,
	.s-empty .label {
		color: var(--v-ink-disabled);
	}

	.word {
		flex: 0 0 auto;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}
</style>
