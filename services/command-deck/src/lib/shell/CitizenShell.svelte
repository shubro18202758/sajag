<script lang="ts">
	/**
	 * CitizenShell — the public chrome (SPEC §6.6). Daylight tokens apply via
	 * the (public) layout's data-theme (the server already renders the page in
	 * daylight, so a phone never flashes dark). One bar, CitizenBar: brand,
	 * the plain-language posture, the two public views (a menu below 480 px)
	 * and the language switch. Nothing operator-side: no band code, no
	 * operator search, no Share, no link into the deck, no provenance tag of
	 * its own (the page states its provenance once).
	 *
	 * Page-owned bar fields are cleared whenever the route changes (before the
	 * next page mounts), and <html lang> follows the chosen language so
	 * screen readers pronounce HI/MR correctly. A choice made on the language
	 * switch is persisted in the sajag_lang cookie (C-M); a page's own default
	 * (Marathi on /driver) never is.
	 */
	import { page } from '$app/stores';
	import { onNavigate } from '$app/navigation';
	import '$lib/i18n/packs';
	import { writeLangCookie } from '$lib/i18n/lang-cookie';
	import { ensureLang } from '$lib/i18n/load';
	import '$lib/i18n/pack-registry.svelte'; // the reactive pack-version signal

	import { provideUiLang } from '$lib/ui/lang';
	import CitizenBar from './CitizenBar.svelte';
	import Toaster from './Toaster.svelte';
	import { commandBar, resetCommandBar } from './command-bar.svelte';

	let { children } = $props();

	provideUiLang(() => commandBar.lang);

	const pathname = $derived($page.url.pathname);

	onNavigate((nav) => {
		if (nav.from?.route.id !== nav.to?.route.id) resetCommandBar();
	});

	$effect(() => {
		document.documentElement.lang = commandBar.lang;
		void ensureLang(commandBar.lang); // this surface's pack chunk (FIX-E-PERF2)
	});

	/** The citizen's own choice: persisted, then handed to the page that owns the language. */
	function pickLang(code: string) {
		writeLangCookie(code);
		if (commandBar.onLangChange) commandBar.onLangChange(code);
		else commandBar.lang = code;
	}
</script>

<div class="shell" data-shell="citizen">
	<CitizenBar lang={commandBar.lang} tier={commandBar.tier} {pathname} onLangChange={pickLang} />
	<main class="main">
		{@render children?.()}
	</main>
	<Toaster position="bottom" />
</div>

<style>
	.shell {
		display: flex;
		flex-direction: column;
		height: 100vh;
		min-width: 0;
		overflow: hidden;
		background: var(--v-canvas);
		color: var(--v-ink-1);
	}

	.main {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
		overflow-y: auto;
	}
</style>
