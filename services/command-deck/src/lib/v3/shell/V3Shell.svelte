<script lang="ts">
	/**
	 * V3Shell (V3-SPEC §3.1, §5.1) — the V3 application shell: the left rail (AppRail), the top bar (TopBar)
	 * and the screen. It replaces CommandShell: the (v3) routes use it, and since P6B so does the (deck) layout
	 * (the v2 operator pages: /analyst, /ops, /gods-eye, /chat, /comms), so every page has the same rail and top bar.
	 *
	 * Like CommandShell it owns no data and imports no store (R4): the page assigns the v2 shell↔page
	 * contract (commandBar: lang, onLangChange, onSearch, officer, exercise, inboxCount) and the V3 fields
	 * (v3Bar: title, sub, the decision list for the alerts). Both are cleared on every route change before
	 * the next page mounts. <html lang> follows the language; every choice is persisted (sajag_lang).
	 *
	 * Keys (§7.1): G then H / M / D / A / V goes to Home / Map / Decide / Assistant / Advisories; `/` and
	 * Ctrl/⌘ K belong to the page's Omnibar; Esc closes, then clears, never navigates. No single key
	 * approves, unmasks, dispatches or publishes. A "Skip to main content" link is the first stop.
	 */
	import { page } from '$app/stores';
	import { goto, onNavigate } from '$app/navigation';
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import '$lib/i18n/pack-registry.svelte';
	import { writeLangCookie } from '$lib/i18n/lang-cookie';
	import { ensureLang } from '$lib/i18n/load';
	import { provideUiLang } from '$lib/ui/lang';
	import Toaster from '$lib/shell/Toaster.svelte';
	import { commandBar, resetCommandBar } from '$lib/shell/command-bar.svelte';
	import '../packs.v3';
	import AppRail from './AppRail.svelte';
	import TopBar from './TopBar.svelte';
	import LiveBand from './LiveBand.svelte';
	import { V3_NAV, navActive, surfaceOf } from './nav';
	import './packs.shell';
	import { resetV3Bar, v3Bar } from './v3-bar.svelte';
	import { v3Alerts } from './alerts.svelte';

	let { children } = $props();

	provideUiLang(() => commandBar.lang);

	const lang = $derived(commandBar.lang);
	const pathname = $derived($page.url.pathname);
	// the v2 operator pages (route group (deck)) name their own title and rail item here (nav.ts: surfaceOf); a V3
	// page names them itself through v3Bar
	const surface = $derived(surfaceOf(pathname));
	const active = $derived(v3Bar.active ?? surface?.rail ?? navActive(pathname));

	onNavigate((nav) => {
		if (nav.from?.route.id !== nav.to?.route.id) {
			resetCommandBar();
			resetV3Bar();
			v3Alerts.reset();
		}
	});

	$effect(() => {
		document.documentElement.lang = commandBar.lang;
		void ensureLang(commandBar.lang);
	});

	// the alerts follow the page's decision list and the console's exercise statement
	$effect(() => {
		const list = v3Bar.decisions;
		if (list) v3Alerts.syncDecisions(list, !!commandBar.exercise);
	});

	onMount(() => {
		v3Alerts.load();
		// browsers allow sound only after a gesture: the first one unlocks the chime
		const unlock = () => v3Alerts.unlockAudio();
		window.addEventListener('pointerdown', unlock, { once: true });
		window.addEventListener('keydown', unlock, { once: true });
		return () => {
			window.removeEventListener('pointerdown', unlock);
			window.removeEventListener('keydown', unlock);
		};
	});

	function pickLang(code: string) {
		writeLangCookie(code);
		if (commandBar.onLangChange) commandBar.onLangChange(code);
		else commandBar.lang = code;
	}

	function typing(target: EventTarget | null): boolean {
		const el = target as HTMLElement | null;
		return el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement || !!el?.isContentEditable;
	}

	let chordAt = 0;
	function onKeydown(e: KeyboardEvent) {
		if (e.defaultPrevented || typing(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
		const k = e.key.toLowerCase();
		if (chordAt && Date.now() - chordAt < 1200) {
			chordAt = 0;
			const to = V3_NAV.find((n) => n.chord === k);
			if (to) {
				e.preventDefault();
				void goto(to.href);
			}
			return;
		}
		if (k === 'g') chordAt = Date.now();
	}

	const title = $derived(v3Bar.title ?? (surface ? t(lang, surface.title) : 'Sajag'));
</script>

<svelte:window onkeydown={onKeydown} />

<div class="v3-app" data-shell="v3">
	<a class="skip" href="#v3-main">{t(lang, 'v3_skip')}</a>
	<AppRail {active} {lang} badge={commandBar.inboxCount} />
	<TopBar {title} sub={v3Bar.sub} {lang} onLangPick={pickLang} />
	<LiveBand />
	<main class="v3-main" id="v3-main" tabindex="-1">
		{@render children?.()}
	</main>
	<Toaster />
</div>

<style>
	.v3-app {
		display: grid;
		grid-template-columns: var(--v3-rail) minmax(0, 1fr);
		grid-template-rows: var(--v3-top) auto minmax(0, 1fr);
		height: 100vh;
		min-width: 0;
		overflow: hidden;
		background: var(--v3-bg);
		color: var(--v3-t1);
		font-family: var(--v-font-ui);
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
		font-feature-settings: 'cv11', 'ss01';
		-webkit-font-smoothing: antialiased;
		/* the v2 toaster sits under the bar it was written for: under the V3 top bar */
		--v-ws-navbar: var(--v3-top);
	}

	.v3-main {
		grid-row: 3;
		grid-column: 2;
		position: relative;
		min-width: 0;
		min-height: 0;
		overflow: auto;
		scrollbar-width: thin;
		scrollbar-color: var(--v3-s4) transparent;
	}

	.v3-main:focus {
		outline: 0;
	}

	/* Devanagari and Marathi: a taller line (inherited; components that set their own keep theirs) */
	.v3-app:lang(hi),
	.v3-app:lang(mr) {
		line-height: 1.7;
	}

	.skip {
		position: absolute;
		left: 8px;
		top: -60px;
		z-index: 100;
		padding: 10px 16px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		font-weight: 650;
		text-decoration: none;
	}

	.skip:focus {
		top: 8px;
	}

	/* a phone (390 px): the rail becomes a tab bar along the bottom and the page takes the full width */
	@media (max-width: 720px) {
		.v3-app {
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: var(--v3-top) auto minmax(0, 1fr) auto;
			height: 100dvh;
			--v3-top: 56px;
			--v3-gut: 16px;
		}

		.v3-main {
			grid-column: 1;
		}
	}
</style>
