<script lang="ts">
	/**
	 * ProvWord — the quiet form of an honest label, for rows that sit in a list: one word at the row's end ("Live",
	 * "Modelled", "Emulated" …) in the tertiary ink, its tip saying what it means. A label that is not a reading
	 * (modelled, emulated, simulated, hindsight) is underlined with dots, the same "dashed = not measured" the tags use.
	 * A list shows one of these per row instead of a chip per row; an unrecognised label renders nothing (never a guess).
	 */
	import { t } from '$lib/i18n/strings';
	import { PROV_LOOK, provOf, type Prov } from '../labels';
	import '../packs.ai';

	let { label = null, prov = null, lang }: { label?: string | null; prov?: Prov | null; lang: string } = $props();

	const kind = $derived(prov ?? provOf(label));
	const look = $derived(kind ? PROV_LOOK[kind] : null);
</script>

{#if kind && look}
	<span class={['pw', look.tone === 'dashed' && 'not-measured']} data-prov={kind} title={t(lang, look.tip)}>{t(lang, look.key)}</span>
{/if}

<style>
	.pw {
		flex: none;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
		line-height: var(--v3-lh-micro);
		white-space: nowrap;
	}

	.not-measured {
		text-decoration: underline dotted;
		text-decoration-color: var(--v3-dashed);
		text-underline-offset: 3px;
	}
</style>
