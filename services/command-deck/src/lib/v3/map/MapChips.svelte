<script lang="ts">
	/**
	 * MapChips (V3-SPEC §5.6, §6.5) — the four group toggles over the map, in job order (Live operations ·
	 * Needs your decision · Reported in the city · Coming up), each with its count and its colour as a swatch
	 * (never colour alone: the words are on the chip), then Layers with how many extra layers are on. A chip
	 * is a toggle button (aria-pressed); the map and the Now list follow it.
	 */
	import { t } from '$lib/i18n/strings';
	import Glyph from '../Glyph.svelte';
	import { GROUP_IDS, GROUP_KEY, type GroupId } from './model';
	import './packs.map3';

	let {
		on,
		counts,
		layersOn,
		sheetOpen,
		lang,
		ontoggle,
		onlayers,
	}: {
		on: Readonly<Record<GroupId, boolean>>;
		counts: Readonly<Record<GroupId, number>>;
		layersOn: number;
		sheetOpen: boolean;
		lang: string;
		ontoggle: (g: GroupId) => void;
		onlayers: () => void;
	} = $props();
</script>

<div class="chips" role="toolbar" aria-label={t(lang, 'v3m_now_list')} data-testid="v3-map-chips" data-ge-keepout>
	{#each GROUP_IDS as g (g)}
		<button
			type="button"
			class={['chip', 'v3-glass', `g-${g}`, on[g] && 'on']}
			aria-pressed={on[g]}
			title={t(lang, on[g] ? 'v3m_chip_on' : 'v3m_chip_off')}
			data-group={g}
			data-count={counts[g]}
			onclick={() => ontoggle(g)}
		>
			<span class="sw" aria-hidden="true"></span>{t(lang, GROUP_KEY[g])}<span class="n">{counts[g]}</span>
		</button>
	{/each}
	<button type="button" class={['chip', 'v3-glass', 'layers', sheetOpen && 'is-pressed']} aria-expanded={sheetOpen} aria-controls="v3-layers-sheet" data-testid="v3-map-layers" onclick={onlayers}>
		<Glyph name="layers" size={18} />{t(lang, 'v3m_layers')}{#if layersOn > 0}<span class="n">{t(lang, 'v3m_layers_on', layersOn)}</span>{/if}
	</button>
</div>

<style>
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		pointer-events: auto;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 40px;
		padding: 0 14px 0 12px;
		border: 1px solid var(--v3-glass-border);
		border-radius: 20px;
		background: var(--v3-glass-surface);
		box-shadow: var(--v3-elev-1);
		color: var(--v3-t2);
		font: inherit;
		font-size: 14px;
		font-weight: 650;
		white-space: nowrap;
		cursor: pointer;
		transition: border-color var(--v3-dur-1), color var(--v3-dur-1);
	}

	.chip:hover {
		border-color: var(--v3-line-3);
		color: var(--v3-t1);
	}

	.chip:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.chip.on {
		border-color: var(--v3-line-3);
		color: var(--v3-t1);
	}

	.chip.is-pressed {
		border-color: var(--v3-t2);
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.sw {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--v3-t3);
	}

	.g-live .sw {
		background: var(--v3-route);
	}

	.g-decide .sw {
		background: var(--v3-decide);
	}

	.g-reported .sw {
		background: var(--v3-t2);
	}

	.chip:not(.on) .sw {
		opacity: 0.35;
	}

	.n {
		color: var(--v3-t3);
		font-variant-numeric: tabular-nums;
	}

	.chip.on .n {
		color: var(--v3-t2);
	}

	@media (max-width: 1500px) {
		.chip {
			height: 36px;
			font-size: 13px;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.chip {
			transition: none;
		}
	}
</style>
