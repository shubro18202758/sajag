<script lang="ts">
	/**
	 * The top bar's one entry point to "Report by voice": a microphone button that loads the sheet on the first press
	 * (the recorder, the map thumb and the board writer stay out of every page's first load) and opens it. The officer
	 * named on console rides into the sheet: a board entry carries a name.
	 */
	import type { Component } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import './packs.field.core';
	import Mic from './Mic.svelte';

	let { lang, officer }: { lang: string; officer: string | null } = $props();

	let Sheet = $state<Component<{ open?: boolean; lang: string; officer: string | null }> | null>(null);
	let open = $state(false);

	async function openSheet() {
		if (!Sheet) Sheet = (await import('./FieldReportSheet.svelte')).default as unknown as Component<{ open?: boolean; lang: string; officer: string | null }>;
		open = true;
	}
</script>

<button type="button" class="fr" aria-label={t(lang, 'fld_entry_aria')} title={t(lang, 'fld_entry_aria')} aria-haspopup="dialog" data-testid="field-report-open" onclick={() => void openSheet()}>
	<Mic size={20} /><span class="lbl">{t(lang, 'fld_entry')}</span>
</button>

{#if Sheet}<Sheet bind:open {lang} {officer} />{/if}

<style>
	.fr {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: var(--v3-ctl-lg);
		padding: 0 16px 0 12px;
		border: 1px solid var(--v3-line-2);
		border-radius: 22px;
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		font-size: 14px;
		font-weight: 650;
		white-space: nowrap;
		cursor: pointer;
		transition: background var(--v3-dur-1) var(--v3-ease), border-color var(--v3-dur-1) var(--v3-ease);
	}

	.fr:hover {
		border-color: var(--v3-brand);
		background: var(--v3-s3);
	}

	.fr :global(.mic) {
		color: var(--v3-brand-text);
	}

	.fr:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	@media (max-width: 1500px) {
		.fr {
			width: var(--v3-ctl-lg);
			padding: 0;
			justify-content: center;
		}

		.lbl {
			display: none;
		}
	}
</style>
