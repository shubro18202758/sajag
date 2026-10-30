<script lang="ts">
	/**
	 * /citizen — "Your road, next 2 hours" (Daylight, trilingual).
	 *
	 * The public advisory, fed ONLY by the deck's public projection
	 * (public-feed.svelte.ts → GET /api/public/events): public-kind events,
	 * signage road names, hold lengths with their provenance. This page
	 * never starts the operator store, so an anonymous browser never pulls
	 * the ANPR watchlist, e-challans, dispatches or the audit tail.
	 *
	 * Under it, "Air today" ($lib/v3/public/AirToday, loaded after first paint): the city's indicative National AQI
	 * in plain words with a Listen button, from the public GET /api/cityfeeds/feeds/summary (labelled Modelled).
	 *
	 * Shell wiring: language (the shared lang preference, so the citizen
	 * bar's switch and the advisory agree) and the plain-language tier the
	 * citizen bar shows — never a band code.
	 */
	import { onMount } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { publicFeed } from '$lib/citizen/public-feed.svelte';
	import CitizenAdvisory from '$lib/citizen/CitizenAdvisory.svelte';
	import PublicCredits from '$lib/v3/public/PublicCredits.svelte';
	import EmergencyNumbers from '$lib/v3/public/EmergencyNumbers.svelte';
	import AirToday from '$lib/v3/public/LazyAir.svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/strings.citizen';
	import '$lib/i18n/packs.assistant';

	onMount(() => {
		// The persisted language (sajag_lang) once hydrated — the server render is English.
		ops.adoptLangCookie();
		publicFeed.start();
		return () => publicFeed.stop();
	});

	// R3 wiring: this page owns lang + the public tier on the citizen bar.
	$effect(() => {
		commandBar.lang = ops.lang;
		commandBar.tier = publicFeed.tier;
		commandBar.onLangChange = (l: string) => (ops.lang = l);
	});
</script>

<svelte:head>
	<!-- F-25: the tab title in the reader's language -->
	<title>{t(ops.lang, 'citizenTabTitle')} · Sajag</title>
</svelte:head>

<div class="citizen-page">
	<CitizenAdvisory lang={ops.lang} />
	<div class="air-wrap"><AirToday lang={ops.lang} /></div>
	<EmergencyNumbers lang={ops.lang} />
	<PublicCredits lang={ops.lang} />
</div>

<style>
	.citizen-page {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}

	.air-wrap {
		max-width: 720px;
		margin: 16px auto 0;
		padding: 0 16px;
	}
</style>
