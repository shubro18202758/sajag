<script lang="ts">
	/**
	 * A registration mark as a V3 chip (V3-SPEC P9, §7.7): the deck's own Plate (the identifier face, the
	 * lock after a masked mark, its "masked until a duty officer is named" tooltip, and its defence in
	 * depth — a mark without the mask is re-masked) inside a quiet chip. Screen readers hear "registration
	 * mark masked" instead of the bullets.
	 */
	import Plate from '$lib/ui/format/Plate.svelte';
	import { t } from '$lib/i18n/strings';
	import '../packs.v3';

	let { mark, masked, lang }: { mark: string; masked: boolean; lang: string } = $props();
</script>

<span class="chip" data-v3="plate" data-masked={masked ? 'true' : 'false'}>
	{#if masked}<span class="sr">{t(lang, 'v3_masked')}</span>{/if}
	<span aria-hidden={masked ? 'true' : undefined}><Plate {mark} {masked} {lang} /></span>
</span>

<style>
	.chip {
		display: inline-flex;
		align-items: center;
		padding: 1px 7px;
		border: 1px solid var(--v3-line-2);
		border-radius: 6px;
		background: var(--v3-redact-bg);
		color: var(--v3-t1);
		font-size: 0.95em;
		font-weight: 600;
		white-space: nowrap;
		vertical-align: middle;
	}

	.chip :global(.lock) {
		color: var(--v3-t3);
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
</style>
