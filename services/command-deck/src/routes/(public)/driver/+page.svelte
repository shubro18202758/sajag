<script lang="ts">
	/**
	 * /driver — "The Window" (Daylight, Marathi-first).
	 *
	 * The 108 driver green-corridor flow on the real dispatch lifecycle:
	 * request → a named duty officer approves on /ops → the window counts
	 * down from the approval (GreenCorridorDriver). Fed by the public
	 * projection only (no operator store). The labelled scripted fallback
	 * appears only while no live public event exists.
	 *
	 * Language: Marathi by default, held PAGE-LOCALLY — the page's default
	 * never rewrites the shared preference, so /ops does not reopen in
	 * Marathi after a visit here. An explicit choice persisted in the
	 * sajag_lang cookie (the switch on any page) wins, exactly as the server
	 * render's <html lang> does.
	 *
	 * Below the window: waterlogging on the road ahead (v3/public/WaterOnYourRoad,
	 * MODELLED) with its Listen button, in the page language.
	 */
	import { onMount } from 'svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { publicFeed } from '$lib/citizen/public-feed.svelte';
	import GreenCorridorDriver from '$lib/citizen/GreenCorridorDriver.svelte';
	import WaterOnYourRoad from '$lib/v3/public/LazyWater.svelte';
	import PublicCredits from '$lib/v3/public/PublicCredits.svelte';
	import { readLangCookie } from '$lib/i18n/lang-cookie';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/strings.citizen';
	import '$lib/i18n/packs.assistant';

	let lang = $state('en');

	onMount(() => {
		lang = readLangCookie() ?? lang;
		publicFeed.start();
		return () => publicFeed.stop();
	});

	// R3 wiring: English by default (the reader's saved choice wins); plain-language tier only.
	$effect(() => {
		commandBar.lang = lang;
		commandBar.tier = publicFeed.tier;
		commandBar.onLangChange = (l: string) => (lang = l);
	});
</script>

<svelte:head>
	<!-- F-25: the tab title in the reader's language -->
	<title>{t(lang, 'driverTitle')} · Sajag</title>
</svelte:head>

<div class="driver-page">
	<GreenCorridorDriver {lang} />
	<!-- waterlogging on the road ahead (the hydro nowcast, MODELLED), with Listen: a crew plans around deep water -->
	<div class="water-wrap"><WaterOnYourRoad {lang} /></div>
	<PublicCredits {lang} />
</div>

<style>
	.driver-page {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}

	.water-wrap {
		box-sizing: border-box;
		width: 100%;
		max-width: 592px;
		margin: 8px auto 24px;
		padding: 0 16px;
	}
</style>
