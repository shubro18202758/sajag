<script lang="ts">
	/**
	 * "At a glance" (V3-SPEC §3.3) — the kind adapter's key figures (2 to 4; the adapter drops any it has no
	 * value for, so nothing is invented to fill a tile) as large numbers with their captions; a time reads in
	 * IST with its day when it is not today; the figure's own second line (an OSINT context note) under it.
	 */
	import { t } from '$lib/i18n/strings';
	import { fmtTime } from '$lib/ui/format/format';
	import { figureDay } from '$lib/workspace/components/inspector/model';
	import type { Figure } from '$lib/workspace/kinds/common';
	import './packs.object';
	import Panel from './Panel.svelte';

	let { figures, lang, now }: { figures: readonly Figure[]; lang: string; now: number } = $props();
</script>

{#if figures.length}
	<Panel title={t(lang, 'obj_figs_h')} testid="obj-figures">
		<div class="stats">
			{#each figures as f, i (i)}
				{@const day = f.time != null ? figureDay(f.time, now) : null}
				<div class="stat" title={f.hint ?? undefined}>
					<b>{#if f.time != null}{fmtTime(f.time)}{:else}{f.value ?? '—'}{/if}{#if f.unit}<small>{f.unit}</small>{/if}</b>
					<span>{f.caption}</span>
					{#if day}<span class="sub">{day}</span>{/if}
					{#if f.sub}<span class="sub">{f.sub}</span>{/if}
				</div>
			{/each}
		</div>
	</Panel>
{/if}

<style>
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 12px;
	}

	.stat {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
		padding: 14px 16px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	b {
		overflow: hidden;
		color: var(--v3-t1);
		font-size: 26px;
		font-weight: 650;
		line-height: 34px;
		font-variant-numeric: tabular-nums;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	small {
		margin-left: 4px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 600;
	}

	span {
		color: var(--v3-t2);
		font-size: 14px;
		font-weight: 500;
	}

	.sub {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}

	@media (max-width: 1500px) {
		b {
			font-size: 22px;
			line-height: 30px;
		}
	}
</style>
