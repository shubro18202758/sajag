<script lang="ts">
	/**
	 * Root layout — reset, self-hosted fonts and tokens ONLY. No chrome, no
	 * data lifecycle: the shells own chrome via the (deck)/(public) group
	 * layouts.
	 *
	 * Fonts are self-hosted (src/lib/design/fonts.css → static/fonts/, SPEC
	 * §3.1): the deck requests nothing from a font CDN, so it renders the
	 * same on a venue network with no internet. The faces cover Latin,
	 * Devanagari and Marathi, so हिंदी and मराठी render in the deck's type.
	 *
	 * The two global rules below are the ONE active-state rule (SPEC §5.1):
	 * `.is-pressed` for controls and `.is-selected` for data, available to
	 * every surface; nothing else may paint an active state (style lint).
	 */
	import '$lib/design/fonts.css';
	import '$lib/design/tokens.css';

	let { children } = $props();
</script>

{@render children?.()}

<style>
	:global(html, body) {
		margin: 0;
		padding: 0;
		height: 100%;
		overflow: hidden;
		font-family: var(--v-font-ui);
		background: var(--v-canvas);
		color: var(--v-ink-1);
		-webkit-font-smoothing: antialiased;
		-moz-osx-font-smoothing: grayscale;
	}

	:global(*) {
		box-sizing: border-box;
	}

	:global(button, input, select, textarea) {
		font-family: inherit;
	}

	:global(:focus-visible) {
		outline-color: var(--v-focus);
	}

	:global(.is-pressed) {
		background: var(--v-surface-4) !important;
		color: var(--v-ink-1) !important;
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}

	:global(.is-selected) {
		background: var(--v-primary-veil) !important;
		box-shadow: inset 2px 0 0 var(--v-primary-text);
	}

	:global(::-webkit-scrollbar) {
		width: 6px;
	}

	:global(::-webkit-scrollbar-track) {
		background: transparent;
	}

	:global(::-webkit-scrollbar-thumb) {
		background: var(--v-minimal-active);
		border-radius: 3px;
	}

	:global(::-webkit-scrollbar-thumb:hover) {
		background: var(--v-ink-4);
	}
</style>
