<script lang="ts">
	/**
	 * VerificationLadder (V3-SPEC §5.4, §6.3) — Unverified · News-reported · Official, the report's step lit.
	 * Never colour alone: the lit step is filled AND named for screen readers ("Verification: News-reported").
	 */
	import { t } from '$lib/i18n/strings';
	import './packs.object';
	import { LADDER_KEYS, ladderStep } from './model';

	let { verification, lang }: { verification: string | null; lang: string } = $props();

	const step = $derived(ladderStep(verification));
</script>

<div class="ladder-wrap">
	<div class="cap" id="obj-ladder-cap">{t(lang, 'obj_verif')}</div>
	<ol class="ladder" aria-labelledby="obj-ladder-cap" data-testid="obj-ladder" data-step={step} data-verification={verification ?? ''}>
		{#each LADDER_KEYS as key, i (key)}
			<li class={['step', i === step && 'lit']} aria-current={i === step ? 'step' : undefined}>{t(lang, key)}</li>
		{/each}
	</ol>
</div>

<style>
	.ladder-wrap {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.cap {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
		line-height: var(--v3-lh-micro);
	}

	.ladder {
		display: flex;
		gap: 6px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.step {
		flex: 1;
		padding: 7px 4px;
		border-radius: var(--v3-radius-s);
		background: var(--v3-s2);
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 650;
		line-height: var(--v3-lh-micro);
		text-align: center;
	}

	.step.lit {
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
	}
</style>
