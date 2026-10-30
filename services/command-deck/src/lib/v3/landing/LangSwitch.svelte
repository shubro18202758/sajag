<script lang="ts">
	/**
	 * The landing page's language switch: English · हिंदी · मराठी (English first, the product's default; the console's order), each label in its own
	 * script (and `lang`), the chosen one pressed (words and aria-pressed, never colour alone). The page owns the
	 * language; this only reports the pick.
	 */
	import { SUPPORTED } from '$lib/i18n/strings';

	const ORDER: readonly string[] = ['en', 'hi', 'mr'];
	const rank = (code: string) => (ORDER.includes(code) ? ORDER.indexOf(code) : ORDER.length);
	const LANGS = [...SUPPORTED].sort((a, b) => rank(a.code) - rank(b.code));

	let { lang, label, onpick, compact = false }: { lang: string; label: string; onpick: (code: string) => void; compact?: boolean } = $props();
</script>

<div class={['lang', compact && 'compact']} role="group" aria-label={label} data-testid="land-lang">
	{#each LANGS as s (s.code)}
		<button type="button" lang={s.code} class={[lang === s.code && 'is-pressed']} aria-pressed={lang === s.code} onclick={() => onpick(s.code)}>{s.label}</button>
	{/each}
</div>

<style>
	.lang {
		display: inline-flex;
		flex: none;
		gap: 2px;
		padding: 3px;
		border-radius: 24px;
		background: var(--v3-glass);
		box-shadow: inset 0 0 0 1px var(--v3-line-2);
	}

	.lang > button {
		min-width: 44px;
		min-height: 40px;
		margin: 0;
		padding: 0 14px;
		border: 0;
		border-radius: 20px;
		background: transparent;
		color: var(--v3-t2);
		font: inherit;
		font-size: var(--v3-text-body);
		font-weight: 600;
		line-height: 1;
		cursor: pointer;
		transition: color var(--v3-dur-1);
	}

	.lang > button:hover {
		color: var(--v3-t1);
	}

	/* the chosen language: the night primary (white pill, black words) */
	.lang > button.is-pressed {
		background: var(--v3-primary-bg) !important;
		box-shadow: none !important;
		color: var(--v3-primary-ink) !important;
	}

	.lang > button:focus-visible {
		outline: 2px solid var(--v3-brand-text);
		outline-offset: 2px;
	}

	.compact > button {
		min-height: 36px;
		padding: 0 10px;
		font-size: var(--v3-text-meta);
	}
</style>
