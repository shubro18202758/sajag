<script lang="ts">
	/**
	 * The deck's error page (F-23): an unknown address — and /design/** in a
	 * production build without SAJAG_DESIGN_HARNESS (F-07) — answers a titled,
	 * themed page in the reader's language with a way back, never the bare
	 * built-in "404". It renders inside the root layout only (no navbar, no
	 * LiveStrip), so nothing on it reads as operational data.
	 */
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { t } from '$lib/i18n/strings';
	import { readLangCookie } from '$lib/i18n/lang-cookie';
	import '$lib/i18n/packs.ui';

	// the server render is English (the deck's rule); the persisted language follows on mount
	let lang = $state('en');
	onMount(() => {
		lang = readLangCookie() ?? document.documentElement.lang ?? 'en';
	});

	const notFound = $derived(page.status === 404);
	const title = $derived(t(lang, notFound ? 'ui_err_404_title' : 'ui_err_title'));
</script>

<svelte:head>
	<title>{title} · Sajag</title>
</svelte:head>

<main class="err" data-testid="error-page" data-status={page.status}>
	<div class="card">
		<p class="code">{page.status}</p>
		<h1>{title}</h1>
		<p class="body">{t(lang, notFound ? 'ui_err_404_body' : 'ui_err_body')}</p>
		<a class="home" href="/" data-sveltekit-reload>{t(lang, 'ui_err_home')}</a>
	</div>
</main>

<style>
	.err {
		height: 100%;
		display: grid;
		place-items: center;
		padding: 16px;
		background: var(--v-canvas);
	}

	.card {
		width: min(440px, 100%);
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 20px;
		background: var(--v-surface-1);
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-panel);
	}

	.code {
		margin: 0;
		font-size: var(--v-text-xs);
		color: var(--v-ink-3);
		font-variant-numeric: tabular-nums;
	}

	h1 {
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
		color: var(--v-ink-1);
	}

	.body {
		margin: 0;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.home {
		align-self: flex-start;
		font-size: var(--v-text-sm);
		color: var(--v-data);
	}
</style>
