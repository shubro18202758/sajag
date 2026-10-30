<script lang="ts">
	/**
	 * DecisionCTA (V3-SPEC §5.4, §5.5) — a decision that waits on (or touches) this record, as a link card to the
	 * decision's ONE home: orange-bordered, the time left (a countdown for a time-boxed unit, `role="timer"`)
	 * or how long it has waited, the recommendation in words, why, and a SECONDARY "Review and decide" — the
	 * primary stays in the title bar, and no verb (approve, dispatch, publish) ever lives here. A time-boxed
	 * card says what happens if no one answers.
	 */
	import { t } from '$lib/i18n/strings';
	import { fmtDuration } from '$lib/ui/format/format';
	import './packs.object';
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import PlateChip from '../ui/PlateChip.svelte';
	import RedactedText from '../ui/RedactedText.svelte';
	import { countdownText } from '../home/model';
	import type { CtaVM } from './view';

	let { vm, now, lang }: { vm: CtaVM; now: number; lang: string } = $props();

	const left = $derived(vm.deadline != null ? vm.deadline - now : null);
	const leftText = $derived(left != null && left > 0 ? countdownText(left, lang) : null);
	const waited = $derived(vm.since != null ? fmtDuration((now - vm.since) / 1000, lang) : null);
</script>

<article class={['cta', vm.touches && 'touches']} data-testid="obj-decision" data-kind={vm.kind} data-key={vm.key}>
	<div class="row">
		{#if leftText}
			<span role="timer" aria-label={t(lang, 'obj_cta_left', leftText)}><V3Tag tone="decide" glyph="clock">{t(lang, 'obj_cta_left', leftText)}</V3Tag></span>
		{:else if waited}
			<V3Tag tone="decide" glyph="clock">{t(lang, 'obj_cta_waiting', waited)}</V3Tag>
		{/if}
		<span class="kind">{vm.touches ? t(lang, 'obj_cta_touches') : vm.kind === 'dss' ? t(lang, 'obj_cta_dss') : vm.kindLine}</span>
	</div>
	<h3 class="title">
		{#if vm.recommended}{t(lang, 'obj_cta_recommended', vm.recommended)}{:else}{vm.title}{/if}
		{#if vm.plate}<PlateChip mark={vm.plate.mark} masked={vm.plate.masked} {lang} />{/if}
	</h3>
	{#if vm.why}<p class="why"><RedactedText text={vm.why} {lang} /></p>{/if}
	<a class="go" href={vm.href} data-testid="obj-decision-link">{t(lang, 'obj_act_review')}<Glyph name="arrowR" size={18} /></a>
	{#if vm.timeBoxed}<p class="ifnot"><Glyph name="info" size={15} />{t(lang, 'obj_cta_ifnot')}</p>{/if}
</article>

<style>
	.cta {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 18px 20px;
		border: 1px solid var(--v3-decide-line);
		border-radius: var(--v3-radius-l);
		background: linear-gradient(var(--v3-decide-veil), var(--v3-decide-veil)), var(--v3-s1);
	}

	.cta.touches {
		background: var(--v3-s1);
	}

	.row {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.kind {
		margin-left: auto;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
		line-height: var(--v3-lh-micro);
		text-align: right;
	}

	.title {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
		margin: 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-sub);
		font-weight: 620;
		line-height: var(--v3-lh-sub);
	}

	.why {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 19px;
	}

	.go {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		height: var(--v3-ctl-lg);
		margin-top: 4px;
		border-radius: 22px;
		background: var(--v3-s3);
		color: var(--v3-t1);
		font-size: var(--v3-text-body);
		font-weight: 650;
		text-decoration: none;
	}

	.go:hover {
		background: var(--v3-s4);
	}

	.go:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.ifnot {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}
</style>
