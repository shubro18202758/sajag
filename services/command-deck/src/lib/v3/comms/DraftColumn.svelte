<script lang="ts">
	/**
	 * One language's draft (V3-SPEC §6.7): the language name, a Copy, and the text at 16/26 (Devanagari and Marathi
	 * 17/29). The exercise prefix — `[SIMULATED FEED · EMULATED — …]` — renders as a quiet tag at the start of the text and
	 * stays in the string: Copy puts the WHOLE draft on the clipboard, prefix included, so a copied draft can never pass
	 * for a real road hold. A withheld draft (an OSINT audience) keeps its node and a disabled Copy; the page decides
	 * whether the columns show at all.
	 */
	import Glyph from '../Glyph.svelte';
	import type { AdvisoryDraft } from '$lib/comms/advisory';
	import { splitMarker } from './model';

	let {
		code,
		label,
		draft,
		copyLabel,
		copyAria,
		copiedLabel,
		oncopy,
	}: {
		code: string;
		label: string;
		draft: AdvisoryDraft | undefined;
		copyLabel: string;
		copyAria: string;
		copiedLabel: string;
		oncopy: (text: string) => void;
	} = $props();

	const parts = $derived(draft ? splitMarker(draft.text) : { marker: null, rest: '' });
	let copied = $state(false);
	let timer: ReturnType<typeof setTimeout> | null = null;

	function copy() {
		if (!draft || draft.withheld) return;
		oncopy(draft.text);
		copied = true;
		if (timer) clearTimeout(timer);
		timer = setTimeout(() => (copied = false), 1600);
	}

	$effect(() => () => {
		if (timer) clearTimeout(timer);
	});
</script>

<article
	class="lang-col"
	data-lang={code}
	data-withheld={draft?.withheld ? 'yes' : 'no'}
	data-facts={draft ? JSON.stringify(draft.facts) : ''}
>
	<header>
		<span class="lang-name" lang={code}>{label}</span>
		<!-- One Copy per column; the marker rides in the copied string. -->
		<button type="button" class="copy" onclick={copy} title={copyAria} aria-label={copyAria} data-copy={code} disabled={!draft || draft.withheld}>
			<Glyph name={copied ? 'check' : 'copy'} size={16} />
			<span>{copied ? copiedLabel : copyLabel}</span>
		</button>
	</header>
	<p class="adv-text" class:withheld={draft?.withheld} data-adv-lang={code} lang={code}>
		{#if parts.marker}
			<!-- The exercise prefix: on screen a quiet tag, in the string verbatim. -->
			<span class="marker">{parts.marker}</span>
			{' '}{parts.rest}
		{:else}
			{draft?.text ?? '…'}
		{/if}
	</p>
</article>

<style>
	.lang-col {
		display: flex;
		flex-direction: column;
		gap: 14px;
		min-width: 0;
		padding: 18px 20px 22px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
	}

	.lang-name {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 650;
		line-height: var(--v3-lh-meta);
	}

	.copy {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		min-height: var(--v3-ctl);
		padding: 0 12px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: transparent;
		color: var(--v3-t1);
		font: inherit;
		font-size: var(--v3-text-meta);
		font-weight: 600;
		cursor: pointer;
		transition:
			background var(--v3-dur-1) var(--v3-ease),
			border-color var(--v3-dur-1) var(--v3-ease);
	}

	.copy:hover:not(:disabled) {
		border-color: var(--v3-line-3);
		background: var(--v3-s3);
	}

	.copy:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.copy:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.adv-text {
		margin: 0;
		font-size: 16px;
		line-height: 26px;
		overflow-wrap: anywhere;
		color: var(--v3-t1);
	}

	.adv-text:lang(hi),
	.adv-text:lang(mr) {
		font-size: 17px;
		line-height: 29px;
	}

	.adv-text.withheld {
		color: var(--v3-t3);
	}

	/* The exercise prefix: the same words the string carries, quiet on screen. */
	.marker {
		display: inline-block;
		margin: 0 0 6px;
		padding: 2px 8px;
		border: 1px dashed var(--v3-dashed);
		border-radius: 8px;
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}
</style>
