<script lang="ts">
	/**
	 * /welcome — the Sajag landing page (V3-LANDING). Public, static, trilingual. The language is the reader's
	 * sajag_lang choice (the server render already speaks it); a pick on the switch is persisted in the same cookie,
	 * its strings load (lib/i18n/load.ts) and <html lang> follows, so a screen reader pronounces हिंदी and मराठी.
	 */
	import { t } from '$lib/i18n/strings';
	import { ensureLang } from '$lib/i18n/load';
	import { writeLangCookie } from '$lib/i18n/lang-cookie';
	import '$lib/i18n/pack-registry.svelte'; // the reactive pack-version signal
	import '$lib/v3/landing/packs.landing';
	import Landing from '$lib/v3/landing/Landing.svelte';

	let { data } = $props();

	let picked = $state<string | null>(null);
	const lang = $derived(picked ?? data.lang);

	$effect(() => {
		document.documentElement.lang = lang;
		void ensureLang(lang);
	});

	function pick(code: string) {
		writeLangCookie(code);
		picked = code;
	}
</script>

<svelte:head>
	<title>{t(lang, 'v3l_doc')}</title>
	<meta name="description" content={t(lang, 'v3l_meta')} />
	<meta property="og:title" content={t(lang, 'v3l_doc')} />
	<meta property="og:description" content={t(lang, 'v3l_meta')} />
	<meta name="theme-color" content="black" />
</svelte:head>

<Landing {lang} onpick={pick} />
