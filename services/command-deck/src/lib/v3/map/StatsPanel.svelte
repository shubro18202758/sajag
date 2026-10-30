<script lang="ts">
	/**
	 * StatsPanel (V3-P4 review item 2) — the corridor figures, one level down: the signal band, traffic on the
	 * corridors (average speed, congestion, roads congested / critical, how fresh) and the escorts being followed.
	 * Closed by default; the map tools open it. Every figure lives HERE only — the chips keep the counts, the
	 * selection card keeps the selected object's own figures, nothing is repeated. Provenance in words on each
	 * section (simulated feed, emulated GPS); a missing reading says so instead of a number. Analysis and audit
	 * tables stay in Analyst (one link).
	 */
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import type { StatSection } from './model';

	let { sections, title, closeLabel, analystLabel, onclose }: { sections: readonly StatSection[]; title: string; closeLabel: string; analystLabel: string; onclose: () => void } = $props();
</script>

<section class="stats v3-glass" id="v3-stats-panel" aria-labelledby="v3-stats-h" data-testid="v3-stats" data-ge-keepout>
	<div class="head">
		<h2 id="v3-stats-h">{title}</h2>
		<button type="button" class="x" aria-label={closeLabel} title={closeLabel} onclick={onclose}><Glyph name="close" size={18} /></button>
	</div>
	{#each sections as sec (sec.key)}
		<div class="sec" data-stats-section={sec.key}>
			<div class="sh">
				<span class="micro">{sec.title}</span>
				{#each sec.tags as tag, i (i)}<V3Tag size="sm" tone={tag.tone} glyph={tag.glyph ?? null} title={tag.title ?? null}>{tag.text}</V3Tag>{/each}
			</div>
			{#if sec.figures.length}
				<div class="figs">
					{#each sec.figures as f, i (i)}<div class="fig" data-testid="v3-stat-figure"><b>{f.value}</b><span>{f.label}</span></div>{/each}
				</div>
			{/if}
			{#if sec.note}<p class="note">{sec.note}</p>{/if}
		</div>
	{/each}
	<a class="link" href="/analyst">{analystLabel}<Glyph name="chevR" size={16} /></a>
</section>

<style>
	.stats {
		display: flex;
		flex-direction: column;
		gap: 12px;
		min-height: 0;
		overflow: auto;
		padding: 16px 18px;
		border: 1px solid var(--v3-glass-border);
		border-radius: var(--v3-radius-l);
		background: var(--v3-glass-surface);
		box-shadow: var(--v3-elev-2);
		scrollbar-width: thin;
		pointer-events: auto;
	}

	.head {
		display: flex;
		align-items: center;
	}

	h2 {
		margin: 0;
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 650;
	}

	.x {
		margin-left: auto;
		display: grid;
		place-items: center;
		width: 36px;
		height: 36px;
		border: 0;
		border-radius: 18px;
		background: none;
		color: var(--v3-t2);
		cursor: pointer;
	}

	.x:hover {
		background: var(--v3-s3);
	}

	.sec {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.sh {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
	}

	.micro {
		margin-right: auto;
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 650;
	}

	.figs {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
	}

	.fig {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
		padding: 8px 10px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.fig b {
		font-size: 16px;
		line-height: 21px;
		font-variant-numeric: tabular-nums;
	}

	.fig span {
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.note {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.link {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		width: fit-content;
		color: var(--v3-brand-text);
		font-size: var(--v3-text-meta);
		font-weight: 600;
		text-decoration: none;
	}

	.x:focus-visible,
	.link:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}
</style>
