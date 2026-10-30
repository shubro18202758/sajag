<script lang="ts">
	/**
	 * "Air today" (public, Marathi-first): the city's air in one plain sentence and what to do about it, from the city
	 * feeds' indicative National AQI (Open-Meteo's CAMS model at the WBPCB/CPCB sites, banded with CPCB's breakpoints),
	 * the site where it is worst and the next 48 hours, and a Listen button that reads it aloud in the page's
	 * language. When the CPCB stations' own 24-hour averages are in (the summary's `observed`), the headline is that
	 * measured value, labelled Measured; otherwise the model's, labelled MODELLED (not a station reading). The
	 * 48-hour outlook is always the model's and says so. Reads only the public GET /api/cityfeeds/feeds/summary; no
	 * operator code, no location is asked for or sent.
	 */
	import { onMount } from 'svelte';
	import { localizeNumber, t } from '$lib/i18n/strings';
	import '$lib/cityfeeds/packs.feeds';
	import { NAQI_ORDER, airToday } from '$lib/cityfeeds/model';
	import Glyph from '../Glyph.svelte';
	import PublicTag from './PublicTag.svelte';
	import ListenButton from './ListenButton.svelte';

	let { lang }: { lang: string } = $props();

	/** Every public string in the reader's digits (mr and hi ०–९), through the formatter. */
	const P = (key: string, ...args: unknown[]) => localizeNumber(t(lang, key, ...args), lang);

	interface AirChip {
		value: number | null;
		band: string | null;
		label: string;
		detail: { worst_site_name?: string; worst_site_mr?: string } | null;
		next_48h?: { aqi: number; band: string } | null;
		/** the CPCB stations' measured National AQI (worst site), when a keyed provider answers */
		observed?: { aqi: number; band: string; site?: string; site_name?: string | null; site_mr?: string | null } | null;
	}
	let chip = $state<AirChip | null>(null);
	let status = $state<'loading' | 'ready' | 'down'>('loading');

	async function load() {
		try {
			const res = await fetch('/api/cityfeeds/feeds/summary', { signal: AbortSignal.timeout(45_000), headers: { accept: 'application/json' } });
			if (!res.ok) throw new Error(String(res.status));
			const body = (await res.json()) as { chips?: { air?: AirChip } };
			const a = body.chips?.air ?? null;
			if (!a || a.value == null || !a.band) throw new Error('no air value');
			chip = a;
			status = 'ready';
		} catch {
			if (!chip) status = 'down';
		}
	}

	onMount(() => {
		void load();
		const id = setInterval(load, 10 * 60_000);
		return () => clearInterval(id);
	});

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	/** the measured value when the stations answer, else the model's */
	const obs = $derived(chip?.observed?.band ? chip.observed : null);
	const band = $derived(obs ? obs.band : (chip?.band ?? null));
	const value = $derived(obs ? obs.aqi : (chip?.value ?? null));
	const today = $derived(chip && band ? airToday(band, value, L) : null);
	const level = $derived(band ? NAQI_ORDER.indexOf(band as (typeof NAQI_ORDER)[number]) : -1);
	const site = $derived(
		obs ? ((lang === 'mr' ? obs.site_mr : obs.site_name) ?? null)
			: chip?.detail ? ((lang === 'mr' ? chip.detail.worst_site_mr : chip.detail.worst_site_name) ?? null) : null
	);
	const next = $derived(chip?.next_48h?.band ? L(`cf_naqi_${chip.next_48h.band}`) : null);
	const nextKey = $derived(obs ? 'cf_pub_tomorrow_model' : 'cf_pub_tomorrow');
	const spoken = $derived(today ? [today.head, today.advice, next ? L(nextKey, next) : ''].filter(Boolean).join(' ') : '');
</script>

<section class="air" aria-labelledby="air-title" data-testid="air-card" data-status={status} data-band={band ?? 'none'} data-measured={obs ? 'yes' : 'no'} lang={lang}>
	<header class="ah">
		<span class="ai"><Glyph name="globe" size={22} /></span>
		<div class="at">
			<h2 id="air-title">{t(lang, 'cf_pub_title')}</h2>
			<p class="lead">{P(obs ? 'cf_pub_lead_obs' : 'cf_pub_lead')}</p>
		</div>
		{#if obs}
			<span class="tagbox" data-label="OBSERVED"><PublicTag tone="live" glyph={null} label={t(lang, 'cf_pub_tag_obs')} title={P('cf_pub_tag_obs_tip')} /></span>
		{:else}
			<span class="tagbox" data-label="MODELLED"><PublicTag tone="dashed" glyph="graph" label={t(lang, 'cf_pub_tag')} title={t(lang, 'cf_pub_tag_tip')} /></span>
		{/if}
	</header>
	{#if status === 'down'}
		<p class="quiet">{t(lang, 'cf_pub_down')}</p>
	{:else if status === 'loading' || !today}
		<p class="quiet">{t(lang, 'cf_pub_loading')}</p>
	{:else}
		<div class={['verdict', `b${level}`]} aria-live="polite">
			<span class="meter" aria-hidden="true">{#each [0, 1, 2, 3, 4, 5] as i (i)}<i class={[level >= i && 'lit']}></i>{/each}</span>
			<div class="vt">
				<p class="big" data-testid="air-headline">{localizeNumber(today.head, lang)}</p>
				<p class="adv">{today.advice}</p>
			</div>
		</div>
		<ListenButton text={localizeNumber(spoken, lang)} {lang} />
		{#if site}<p class="more">{L('cf_pub_worst', site)}</p>{/if}
		{#if next}<p class="more">{P(nextKey, next)}</p>{/if}
	{/if}
	<p class="src">{P(obs ? 'cf_pub_source_obs' : 'cf_pub_source')}</p>
</section>

<style>
	.air {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 22px 20px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
		box-shadow: var(--v3-elev-1);
	}

	.ah {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 12px;
		align-items: start;
	}

	.ai {
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		border-radius: 50%;
		background: var(--v3-brand-veil);
		color: var(--v3-brand-text);
	}

	h2 {
		margin: 0;
		font-size: 22px;
		line-height: 30px;
		font-weight: 700;
	}

	.lead {
		margin: 2px 0 0;
		color: var(--v3-t2);
		font-size: 15px;
		line-height: 22px;
	}

	.tagbox {
		grid-column: 2;
	}

	.verdict {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 16px;
		border-radius: var(--v3-radius-l);
		background: var(--v3-bg);
	}

	.meter {
		display: flex;
		align-items: flex-end;
		gap: 3px;
		flex: none;
		height: 48px;
	}

	.meter i {
		display: block;
		width: 8px;
		border-radius: 3px;
		background: var(--v3-s3);
	}

	.meter i:nth-child(1) {
		height: 14px;
	}

	.meter i:nth-child(2) {
		height: 20px;
	}

	.meter i:nth-child(3) {
		height: 27px;
	}

	.meter i:nth-child(4) {
		height: 34px;
	}

	.meter i:nth-child(5) {
		height: 41px;
	}

	.meter i:nth-child(6) {
		height: 48px;
	}

	/* the band ladder (colour supports the words; the bar count carries the level too) */
	.b0 .meter i.lit,
	.b1 .meter i.lit {
		background: var(--v-band-green);
	}

	.b2 .meter i.lit {
		background: var(--v-band-amber);
	}

	.b3 .meter i.lit,
	.b4 .meter i.lit {
		background: var(--v-band-red);
	}

	.b5 .meter i.lit {
		background: var(--v-band-black-fill);
		box-shadow: 0 0 0 1px var(--v-band-black-hairline);
	}

	.vt {
		min-width: 0;
	}

	.big {
		margin: 0;
		color: var(--v3-t1);
		font-size: 19px;
		line-height: 27px;
		font-weight: 650;
	}

	.adv {
		margin: 4px 0 0;
		color: var(--v3-t2);
		font-size: 16px;
		line-height: 24px;
	}

	.more {
		margin: 0;
		color: var(--v3-t2);
		font-size: 15px;
		line-height: 22px;
	}

	.quiet {
		margin: 0;
		color: var(--v3-t3);
	}

	.src {
		margin: 0;
		color: var(--v3-t3);
		font-size: 13px;
		line-height: 18px;
	}
</style>
