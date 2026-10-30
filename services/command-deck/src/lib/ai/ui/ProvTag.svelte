<script lang="ts">
	/**
	 * ProvTag — the honest label of an AI number, visible but quiet: a small V3 tag ("Live", "Modelled",
	 * "Emulated", "Simulated", "Hindsight" …) whose tooltip says what that means. A raw service label
	 * ("MODELLED (approximate)") or a kind; an unrecognised label renders nothing rather than a guess.
	 */
	import { t } from '$lib/i18n/strings';
	import V3Tag from '$lib/v3/ui/V3Tag.svelte';
	import { PROV_LOOK, provOf, type Prov } from '../labels';
	import '../packs.ai';

	let { label = null, prov = null, lang, size = 'sm' }: { label?: string | null; prov?: Prov | null; lang: string; size?: 'sm' | 'md' } = $props();

	const kind = $derived(prov ?? provOf(label));
	const look = $derived(kind ? PROV_LOOK[kind] : null);
</script>

{#if kind && look}
	<span class="prov" data-prov={kind}><V3Tag {size} tone={look.tone} glyph={look.glyph} title={t(lang, look.tip)}>{t(lang, look.key)}</V3Tag></span>
{/if}

<style>
	.prov {
		display: inline-flex;
		flex: none;
	}
</style>
