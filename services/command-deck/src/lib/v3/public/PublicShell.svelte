<script lang="ts">
	/**
	 * PublicShell — the V3 chrome of the public pages (V3-SPEC §6.8; V3-P6A). Day theme (the server already renders these
	 * routes with data-theme="daylight", so a phone never flashes dark; the (public) layout covers client-side arrival),
	 * the Sajag day lockup (the S road and its blue dot, black on paper), one column.
	 *
	 * It replaces CitizenShell and keeps its whole contract: `data-shell="citizen"`, the bar `data-shell="citizen-bar"`
	 * with the plain-language posture (`data-tier`; citizens see "Planned holds on", never a band code), the two public
	 * views, and the language switch in reach (`.lang button[lang]`). Deliberately nothing operator-side: no band code, no
	 * operator search, no Share, no link into the deck, and NO V3 operator code — only the V3 tokens (day), the lockup and
	 * the two public packs are loaded here.
	 *
	 * Page-owned bar fields are cleared whenever the route changes (before the next page mounts), and <html lang>
	 * follows the chosen language so screen readers pronounce HI/MR correctly. A choice made on the language switch is
	 * persisted in the sajag_lang cookie (C-M); a page's own default (Marathi on /driver) never is.
	 */
	import { page } from '$app/stores';
	import { onNavigate } from '$app/navigation';
	import '$lib/i18n/packs';
	import '$lib/v3/tokens.css';
	import './packs.pub3';
	import { SUPPORTED, t } from '$lib/i18n/strings';
	import { writeLangCookie } from '$lib/i18n/lang-cookie';
	import { ensureLang } from '$lib/i18n/load';
	import '$lib/i18n/pack-registry.svelte'; // the reactive pack-version signal
	import { provideUiLang } from '$lib/ui/lang';
	import { PUBLIC_NAV } from '$lib/shell/nav';
	import { commandBar, resetCommandBar } from '$lib/shell/command-bar.svelte';

	let { children } = $props();

	provideUiLang(() => commandBar.lang);

	const lang = $derived(commandBar.lang);
	const tier = $derived(commandBar.tier);
	const pathname = $derived($page.url.pathname);
	const active = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

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

<div class="shell" data-shell="citizen" data-v3="public">
	<a class="skip" href="#pub-main">{t(lang, 'v3p_skip')}</a>

	<header class="bar" data-shell="citizen-bar">
		<img class="logo" src="/brand/sajag-lockup-day.svg" alt={t(lang, 'v3p_logo')} width="90" height="30" />

		<div class="lang" role="group" aria-label={t(lang, 'shell_language')}>
			{#each SUPPORTED as s (s.code)}
				<button type="button" lang={s.code} class={[lang === s.code && 'is-pressed']} aria-pressed={lang === s.code} aria-label={s.label} onclick={() => pickLang(s.code)}>
					<span class="full">{s.label}</span><span class="short" aria-hidden="true">{t(lang, `v3p_lang_short_${s.code}`)}</span>
				</button>
			{/each}
		</div>

		<nav class="views" aria-label={t(lang, 'v3p_view_tabs')}>
			{#each PUBLIC_NAV as n (n.href)}
				<a href={n.href} class="view" aria-current={active(n.href) ? 'page' : undefined}>{t(lang, n.key)}</a>
			{/each}
		</nav>

		<span class={['tier', `tier-${tier ?? 'unknown'}`]} data-tier={tier ?? 'unknown'} aria-live="polite">
			<span class="dot" aria-hidden="true"></span>
			{t(lang, tier ? `tier_${tier}` : 'tier_unknown')}
		</span>
	</header>

	<main class="main" id="pub-main" tabindex="-1">
		{@render children?.()}
	</main>
</div>

<style>
	.shell {
		display: flex;
		flex-direction: column;
		height: 100vh;
		height: 100dvh;
		min-width: 0;
		overflow: hidden;
		background: var(--v3-bg);
		color: var(--v3-t1);
		font-family: var(--v-font-ui);
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
		font-feature-settings: 'cv11', 'ss01';
		-webkit-font-smoothing: antialiased;
	}

	/* Devanagari and Marathi: a taller line */
	.shell:lang(hi),
	.shell:lang(mr) {
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

	/* ── the bar: lockup · views · posture · language ───────────────────── */
	.bar {
		display: flex;
		flex: none;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px 16px;
		min-width: 0;
		padding: 10px 16px;
		border-bottom: 1px solid var(--v3-line-1);
		background: var(--v3-s1);
	}

	.logo {
		display: block;
		flex: none;
		height: 30px;
		width: auto;
	}

	.lang {
		display: inline-flex;
		order: 5;
		margin-left: auto;
		padding: 3px;
		gap: 2px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		box-shadow: inset 0 0 0 1px var(--v3-line-1);
	}

	.lang > button {
		min-width: 44px;
		min-height: 40px;
		margin: 0;
		padding: 0 12px;
		border: 0;
		border-radius: var(--v3-radius-s);
		background: transparent;
		color: var(--v3-t2);
		font: inherit;
		font-size: var(--v3-text-body);
		font-weight: 600;
		cursor: pointer;
	}

	.lang > button:hover {
		color: var(--v3-t1);
	}

	/* the chosen language: the day primary, words (never colour alone: aria-pressed) */
	.lang > button.is-pressed {
		background: var(--v3-s1) !important;
		box-shadow:
			0 0 0 1px var(--v3-line-2),
			0 1px 2px var(--v3-line-1) !important;
		color: var(--v3-t1) !important;
	}

	.lang > button:focus-visible,
	.view:focus-visible,
	.skip:focus-visible {
		outline: 2px solid var(--v3-brand-strong);
		outline-offset: 2px;
	}

	.short {
		display: none;
	}

	.views {
		display: inline-flex;
		order: 3;
		align-items: center;
		gap: 4px;
		margin-left: 4px;
	}

	.view {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		padding: 0 12px;
		border-radius: var(--v3-radius-s);
		color: var(--v3-t2);
		font-size: var(--v3-text-body);
		font-weight: 600;
		text-decoration: none;
		white-space: nowrap;
	}

	.view:hover {
		color: var(--v3-t1);
	}

	/* the current view: the underline (words and a 3 px rule — never colour alone) */
	.view[aria-current='page'] {
		color: var(--v3-t1);
		box-shadow: inset 0 -3px 0 var(--v3-brand-strong);
	}

	.tier {
		display: inline-flex;
		order: 4;
		align-items: center;
		gap: 8px;
		min-height: 30px;
		padding: 2px 12px;
		border-radius: 15px;
		background: var(--v3-s2);
		color: var(--v3-t1);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.dot {
		flex: none;
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: var(--v3-t3);
	}

	/* calm is the one green; every other posture is the brand blue — red and orange keep their frozen meanings */
	.tier-calm .dot {
		background: var(--v3-ok);
	}

	.tier-watch .dot,
	.tier-hold .dot,
	.tier-severe .dot {
		background: var(--v3-brand-strong);
	}

	.tier-severe .dot {
		box-shadow: 0 0 0 3px var(--v3-brand-veil);
	}

	.tier-unknown {
		background: transparent;
		box-shadow: inset 0 0 0 1px var(--v3-line-2);
		color: var(--v3-t2);
	}

	.main {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
		overflow-y: auto;
	}

	.main:focus {
		outline: 0;
	}

	/* wide enough: the lockup, the views, the posture and the language share one row */
	@media (min-width: 900px) {
		.bar {
			padding: 12px 32px;
		}

		.views {
			order: 2;
		}

		.tier {
			order: 3;
			margin-left: auto;
		}

		.lang {
			order: 4;
			margin-left: 0;
		}
	}

	/* phones: the lockup and the language share the first row; the two views and the posture the second */
	@media (max-width: 520px) {
		.bar {
			gap: 6px 12px;
			padding: 10px 12px;
		}

		.logo {
			height: 28px;
		}

		.lang > button {
			min-width: 44px;
			padding: 0 8px;
		}

		.lang {
			order: 2;
		}

		.views {
			order: 3;
			flex: 1 1 100%;
			margin-left: 0;
			gap: 0;
		}

		.view {
			flex: 1 1 0;
			justify-content: center;
			padding: 0 6px;
			text-align: center;
			white-space: normal;
			line-height: 1.25;
		}

		.tier {
			order: 4;
			flex: 1 1 100%;
		}
	}

	@media (max-width: 420px) {
		.full {
			display: none;
		}

		.short {
			display: inline;
		}
	}
</style>
