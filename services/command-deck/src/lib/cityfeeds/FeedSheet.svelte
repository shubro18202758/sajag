<script lang="ts">
	/**
	 * The City chip's sheet: what the feed is (in the reader's language), its figures now (only numbers the service
	 * gave), its honest label, the proposal draft in मराठी · English · हिंदी — or why there is none, with the threshold —
	 * and the sources as links. A proposal is a draft for a named officer: no button here acts on the city.
	 * Data: GET /api/cityfeeds/feeds/<chip> on open.
	 */
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import Glyph from '$lib/v3/Glyph.svelte';
	import V3Tag from '$lib/v3/ui/V3Tag.svelte';
	import ProvTag from '$lib/ai/ui/ProvTag.svelte';
	import { getView } from './client';
	import { CHIP_GLYPH, CHIP_SOURCES, chipVM, sheetFigures } from './model';
	import type { AnyView, Chip, ChipId, Proposal } from './types';
	import './packs.feeds';

	let { id, lang, chip = null, onclose }: { id: ChipId; lang: string; chip?: Chip | null; onclose: () => void } = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	let view = $state<AnyView | null>(null);
	let status = $state<'loading' | 'ok' | 'down'>('loading');
	let panel = $state<HTMLElement | null>(null);

	$effect(() => {
		const want = id;
		status = 'loading';
		view = null;
		let gone = false;
		getView(want)
			.then((v) => {
				if (gone) return;
				view = v;
				status = 'ok';
			})
			.catch(() => {
				if (!gone) status = 'down';
			});
		return () => {
			gone = true;
		};
	});

	onMount(() => panel?.focus());

	const vm = $derived(chipVM(id, chip ?? undefined, L));
	const figures = $derived(sheetFigures(id, view as Record<string, unknown> | null, L, lang));
	const proposal = $derived.by((): Proposal | null => {
		const p = view?.proposal as Proposal | { none: string } | undefined;
		return p && 'proposal_id' in p ? p : null;
	});
	const none = $derived.by((): string | null => {
		const p = view?.proposal as { none?: string } | undefined;
		return p && typeof p.none === 'string' ? p.none : null;
	});
	const draft = $derived(proposal?.text ? (proposal.text[lang as 'en' | 'mr' | 'hi'] ?? proposal.text.en ?? null) : null);
	const others = $derived(proposal?.text ? (['en', 'hi', 'mr'] as const).filter((k) => k !== lang && proposal?.text?.[k]) : []);
	const feedSource = $derived((view?.feed as { source?: string; home?: string } | undefined) ?? null);
</script>

<div class="scrim" role="presentation" onclick={onclose}></div>
<div class="sheet v3-glass" role="dialog" aria-modal="true" aria-labelledby="cf-sheet-h" tabindex="-1" bind:this={panel} data-testid="cf-sheet" data-chip={id} data-status={status} data-ge-keepout>
	<div class="head">
		<span class="ic"><Glyph name={CHIP_GLYPH[id]} size={20} /></span>
		<h2 id="cf-sheet-h">{L(`cf_title_${id}`)}</h2>
		<button type="button" class="x" aria-label={L('cf_sheet_close')} title={L('cf_sheet_close')} onclick={onclose}><Glyph name="close" size={18} /></button>
	</div>
	<div class="line">
		{#if vm.available}<b>{vm.value}</b>{#if vm.band}<span>· {vm.band}</span>{/if}<ProvTag label={vm.label} {lang} />{#if id === 'air'}<V3Tag size="sm" tone="dashed" title={L('cf_tag_indicative_tip')}>{L('cf_tag_indicative')}</V3Tag>{/if}
		{:else}<span class="dim">{L('cf_unavailable')}</span><ProvTag prov="unavailable" {lang} />{/if}
	</div>
	<p class="what">{L(`cf_what_${id}`)}</p>

	{#if status === 'loading'}
		<p class="dim">{L('cf_loading')}</p>
	{:else if status === 'down'}
		<p class="dim" role="status">{L('cf_sheet_down')}</p>
	{:else}
		{#if figures.length}
			<h3>{L('cf_figures')}</h3>
			<ul class="figs" data-testid="cf-figures">
				{#each figures as f, i (i)}<li>{f}</li>{/each}
			</ul>
		{/if}
		{#if id === 'air' || id === 'heat' || id === 'cyclone'}
			<h3>{L('cf_proposal')}</h3>
			{#if proposal}
				<div class="prop" data-testid="cf-proposal">
					<div class="ph"><V3Tag size="sm" tone="ai" glyph="spark">{L('ai_tag')}</V3Tag></div>
					<p class="sum">{proposal.summary}</p>
					{#if draft}<blockquote lang={lang}>{draft}</blockquote>{/if}
					{#each others as k (k)}<blockquote class="alt" lang={k}>{proposal.text?.[k]}</blockquote>{/each}
					<p class="officer"><Glyph name="shield" size={16} />{L('cf_officer')}</p>
				</div>
			{:else}
				<p class="none" data-testid="cf-no-proposal" title={none ?? undefined}><b>{L('cf_no_proposal')}</b> <span class="dim">{L(`cf_none_${id}`)}</span></p>
			{/if}
		{/if}
	{/if}

	<h3>{L('cf_sources')}</h3>
	<ul class="src">
		{#each CHIP_SOURCES[id] as s (s.name)}
			<li>{#if s.url}<a href={s.url} target="_blank" rel="noopener noreferrer">{s.name}</a>{:else}{s.name}{/if}</li>
		{/each}
		{#if feedSource?.source}<li class="dim">{feedSource.source}</li>{/if}
	</ul>
</div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 200;
		background: var(--v3-scrim, transparent);
	}

	.sheet {
		position: fixed;
		top: 72px;
		right: 18px;
		bottom: 18px;
		z-index: 201;
		display: flex;
		flex-direction: column;
		gap: 8px;
		width: 440px;
		max-width: calc(100vw - 36px);
		padding: 16px 18px;
		overflow-y: auto;
		border: 1px solid var(--v3-glass-border);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
		box-shadow: var(--v3-elev-2);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.sheet:focus-visible {
		outline: 2px solid var(--v3-brand);
	}

	.head {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.ic {
		display: inline-flex;
		color: var(--v3-t2);
	}

	h2 {
		flex: 1;
		margin: 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-title);
		font-weight: 650;
	}

	h3 {
		margin: 8px 0 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-sub);
		font-weight: 650;
	}

	.x {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 32px;
		height: 32px;
		border: 1px solid var(--v3-line-2);
		border-radius: 16px;
		background: none;
		color: var(--v3-t2);
		cursor: pointer;
	}

	.line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
	}

	b {
		color: var(--v3-t1);
		font-weight: 650;
	}

	.what {
		margin: 0;
	}

	.figs,
	.src {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0;
		padding-left: 18px;
	}

	.src a {
		color: var(--v3-t1);
	}

	.prop {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 10px 12px;
		border: 1px solid var(--v3-line-2);
		border-radius: 10px;
		background: var(--v3-s2);
	}

	.sum {
		margin: 0;
		color: var(--v3-t1);
	}

	blockquote {
		margin: 0;
		padding: 6px 10px;
		border-left: 3px solid var(--v3-line-3);
		color: var(--v3-t1);
	}

	blockquote.alt {
		color: var(--v3-t3);
	}

	.officer {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 0;
		color: var(--v3-t2);
	}

	.none {
		margin: 0;
	}

	.dim {
		color: var(--v3-t3);
	}
</style>
