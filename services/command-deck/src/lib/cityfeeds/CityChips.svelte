<script lang="ts">
	/**
	 * City (the god's-eye situational row, on the map under Rain · Tide and on Home under "Next 2 hours"): Air · Heat ·
	 * Cyclone · River · Quake, each with its value, its band in words (and a dot in the band's colour — colour only
	 * supports the word) and its honest label (Live, Modelled; Indicative for the National AQI; Recorded or Stale when
	 * the service says so). A feed that does not answer says "Unavailable", never zero. A click opens the sheet with
	 * the sources and the proposal drafts (FeedSheet, loaded on first open). Calm on the surface: the honest label is a
	 * quiet word at the row's end (its tip says what it means), not a chip per row; states (Stale, a proposal) stay tags. Data: the shared summary poller
	 * (./store.svelte), GET /api/cityfeeds/feeds/summary.
	 */
	import { onMount, type Component } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import Glyph from '$lib/v3/Glyph.svelte';
	import V3Tag from '$lib/v3/ui/V3Tag.svelte';
	import ProvWord from '$lib/ai/ui/ProvWord.svelte';
	import { cityFeeds } from './store.svelte';
	import { CHIP_GLYPH, TONE_TOKEN, chipRow, type ChipVM } from './model';
	import type { ChipId } from './types';
	import './packs.feeds';

	let { lang, variant = 'map' }: { lang: string; variant?: 'map' | 'home' } = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const rows = $derived(chipRow(cityFeeds.summary, L));
	const down = $derived(!cityFeeds.summary && (cityFeeds.status === 'down' || cityFeeds.status === 'not-deployed'));
	const recorded = $derived(Object.values(cityFeeds.summary?.chips ?? {}).some((c) => c?.mode === 'RECORDED'));

	let open = $state<ChipId | null>(null);
	let Sheet = $state<Component<Record<string, unknown>> | null>(null);
	async function show(id: ChipId) {
		if (!Sheet) Sheet = (await import('./FeedSheet.svelte')).default as unknown as Component<Record<string, unknown>>;
		open = id;
	}

	onMount(() => cityFeeds.use());

	const dot = (c: ChipVM) => `var(${TONE_TOKEN[c.tone].fill})`;
	const ring = (c: ChipVM) => (TONE_TOKEN[c.tone].ring ? `var(${TONE_TOKEN[c.tone].ring})` : 'transparent');
</script>

<section class={['cf', variant === 'map' && 'v3-glass', `v-${variant}`]} aria-label={L('cf_row_aria')} data-testid="cf-chips" data-status={cityFeeds.status} data-ge-keepout>
	<div class="head">
		<h3>{L('cf_row_title')}</h3>
		{#if recorded}<V3Tag size="sm" tone="dashed" glyph="history" title={L('cf_tag_recorded_tip')}>{L('cf_tag_recorded')}</V3Tag>{/if}
	</div>
	{#if down}
		<p class="down" role="status">{L('cf_down')}</p>
	{:else}
		<ul class="rows">
			{#each rows as c (c.id)}
				<li>
					<button type="button" class="row" data-chip={c.id} data-band={c.tone} data-label={c.label} title={c.id === 'air' ? `${L('cf_tag_indicative_tip')} ${L('cf_open_tip')}` : L('cf_open_tip')} onclick={() => void show(c.id)}>
						<span class="ic"><Glyph name={CHIP_GLYPH[c.id]} size={16} /></span>
						<span class="nm">{L(`cf_chip_${c.id}`)}</span>
						<span class="v">
							{#if c.available}
								<b>{c.value}</b>{#if c.band}<span class="band"><i class="dot" style:background={dot(c)} style:box-shadow={`0 0 0 1.5px ${ring(c)}`} aria-hidden="true"></i>{c.band}</span>{/if}
							{:else}<span class="dim">{cityFeeds.status === 'loading' ? L('cf_loading') : c.value}</span>{/if}
						</span>
						<span class="pv">
							{#if c.available}
								<ProvWord label={c.label} {lang} />
								{#if c.stale}<V3Tag size="sm" tone="dashed" title={L('cf_tag_stale_tip')}>{L('cf_tag_stale')}</V3Tag>{/if}
								{#if c.proposal}<V3Tag size="sm" tone="decide" glyph="spark">{L('cf_tag_proposal')}</V3Tag>{/if}
							{:else if cityFeeds.status !== 'loading'}<ProvWord prov="unavailable" {lang} />{/if}
						</span>
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</section>

<svelte:window
	onkeydown={(e) => {
		if (open && e.key === 'Escape') open = null;
	}}
/>

{#if open && Sheet}
	<Sheet id={open} {lang} chip={cityFeeds.summary?.chips?.[open] ?? null} onclose={() => (open = null)} />
{/if}

<style>
	.cf {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.cf.v-map {
		width: 380px;
		max-width: 100%;
		padding: 10px 12px;
		border: 1px solid var(--v3-glass-border);
		border-radius: var(--v3-radius-l);
		background: var(--v3-glass-surface);
		box-shadow: var(--v3-elev-1);
		pointer-events: auto;
	}

	.cf.v-home {
		padding: 14px 16px 12px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s2);
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	h3 {
		margin: 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-body);
		font-weight: 650;
	}

	.rows {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.row {
		display: grid;
		grid-template-columns: 18px auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 8px;
		width: 100%;
		min-height: 32px;
		padding: 3px 6px;
		border: 1px solid transparent;
		border-radius: 8px;
		background: none;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.row:hover {
		border-color: var(--v3-line-2);
		background: var(--v3-s2);
	}

	.row:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 1px;
	}

	.ic {
		display: inline-flex;
		color: var(--v3-t3);
	}

	.nm {
		min-width: 52px;
		color: var(--v3-t2);
		font-weight: 600;
	}

	.v {
		font-variant-numeric: tabular-nums;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		column-gap: 8px;
		min-width: 0;
	}

	b {
		color: var(--v3-t1);
		font-weight: 650;
	}

	.band {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		color: var(--v3-t2);
		white-space: nowrap;
	}

	.dot {
		display: inline-block;
		flex: none;
		width: 9px;
		height: 9px;
		border-radius: 50%;
	}

	.pv {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}


	.dim {
		color: var(--v3-t3);
	}

	.down {
		margin: 0;
		color: var(--v3-t3);
	}
</style>
