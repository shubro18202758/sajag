<script lang="ts">
	/**
	 * Text with its redactions shown as chips (V3-SPEC §7.6): `[PERSON]` reads "name withheld", `[AGE]`
	 * "age withheld", anything else "detail withheld" — never the bracketed code, never what was removed.
	 */
	import { t } from '$lib/i18n/strings';
	import '../packs.v3';
	import { redactionKey, redactionParts } from './redaction';

	let { text, lang }: { text: string; lang: string } = $props();

	const parts = $derived(redactionParts(text));
	const label = (token: string) => t(lang, redactionKey(token));
</script>

{#each parts as p, i (i)}{#if p.token}<span class="redact" data-v3="redaction">{label(p.token)}</span>{:else}{p.text}{/if}{/each}

<style>
	.redact {
		display: inline-block;
		padding: 0 6px;
		border: 1px dashed var(--v3-dashed);
		border-radius: 6px;
		background: var(--v3-redact-bg);
		color: var(--v3-t2);
		font-size: 0.92em;
		line-height: 1.35;
		white-space: nowrap;
	}
</style>
