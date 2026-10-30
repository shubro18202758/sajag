<script lang="ts">
	/**
	 * OutcomeState (V3-SPEC §5.3, §6.2) — what the sheet collapses to once a decision is done: a check, the
	 * outcome sentence ("Escort proposal approved · recorded with R. Mehta at 19:43 IST"), the writer's next
	 * step, and "Next decision →". Also the two endings nobody pressed a button for: a time-boxed proposal
	 * that ran out ("No one answered in time · the current plan is kept") and a unit that stopped waiting
	 * elsewhere. Focus moves to the heading so a screen reader hears the outcome.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.decisions';
	import { fmtTime } from '$lib/ui/format/format';
	import Glyph from '../Glyph.svelte';
	import './packs.decide';

	let {
		mode,
		verb = '',
		officer = '',
		at = null,
		next = null,
		hasNext,
		onnext,
		lang,
	}: {
		mode: 'done' | 'expired' | 'gone';
		verb?: string;
		officer?: string;
		at?: number | null;
		next?: string | null;
		hasNext: boolean;
		onnext: () => void;
		lang: string;
	} = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	let head = $state<HTMLHeadingElement | null>(null);
	$effect(() => {
		head?.focus();
	});
</script>

<div class="done-state" data-testid="v3-outcome" data-mode={mode}>
	<div class={['big', mode]}><Glyph name={mode === 'done' ? 'check' : mode === 'expired' ? 'clock' : 'info'} size={30} /></div>
	<h2 class="h" tabindex="-1" bind:this={head}>
		{mode === 'done' ? verb : mode === 'expired' ? L('v3d_expired_title') : L('v3d_gone_title')}
	</h2>
	<p class="meta" data-testid="decision-outcome">
		{#if mode === 'done'}
			{L('v3d_recorded_with', officer, at != null ? fmtTime(at) : '—')}
		{:else if mode === 'expired'}
			{L('v3d_expired_body')}
		{:else}
			{L('v3d_gone_body')}
		{/if}
	</p>
	{#if next}<p class="next"><Glyph name="arrowR" size={16} />{next}</p>{/if}
	{#if hasNext}
		<button type="button" class="btn primary" data-testid="v3-next-decision" onclick={onnext}>{L('v3d_next_decision')}<Glyph name="arrowR" size={18} /></button>
	{:else}
		<p class="meta">{L('v3d_all_done')}</p>
	{/if}
</div>

<style>
	.done-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		padding: 56px 32px;
		text-align: center;
	}

	.big {
		display: grid;
		place-items: center;
		width: 76px;
		height: 76px;
		border-radius: 38px;
		background: var(--v3-ok-veil);
		color: var(--v3-ok-text);
	}

	.big.expired,
	.big.gone {
		background: var(--v3-s3);
		color: var(--v3-t2);
	}

	.h {
		margin: 4px 0 0;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 650;
		color: var(--v3-t1);
		outline: none;
	}

	.meta {
		margin: 0;
		max-width: 380px;
		font-size: 14px;
		line-height: 21px;
		color: var(--v3-t2);
	}

	.next {
		display: flex;
		gap: 8px;
		align-items: flex-start;
		max-width: 400px;
		margin: 0;
		padding: 10px 14px;
		border-radius: 12px;
		background: var(--v3-s2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		color: var(--v3-t2);
		text-align: left;
	}

	.next :global(svg) {
		flex: none;
		margin-top: 1px;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: var(--v3-ctl-lg);
		margin-top: 8px;
		padding: 0 22px;
		border: 0;
		border-radius: 22px;
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		font: inherit;
		font-size: 15px;
		font-weight: 650;
		cursor: pointer;
	}

	.btn:hover {
		background: var(--v3-primary-hover);
	}

	.btn:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}
</style>
