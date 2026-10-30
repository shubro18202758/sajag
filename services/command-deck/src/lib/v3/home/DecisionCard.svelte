<script lang="ts">
	/**
	 * DecisionCard (V3-SPEC §5.2) — one decision unit: the map of its place, its countdown (time-boxed
	 * and expiring units) or how long it has waited, its art, kind and title (the mark masked in a chip
	 * with a lock until an officer is named), why, who proposed it, and one verb — Review — which opens
	 * the unit's one home (decisions/homes.ts; never a second Approve here).
	 */
	import { t } from '$lib/i18n/strings';
	import { fmtDuration } from '$lib/ui/format/format';
	import '../packs.v3';
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import PlateChip from '../ui/PlateChip.svelte';
	import RedactedText from '../ui/RedactedText.svelte';
	import type { LonLat } from '../map/mercator';
	import CardFrame from './CardFrame.svelte';
	import { countdownText } from './model';
	import type { DecisionVM } from './view';

	let { vm, now, lang, roads = null }: { vm: DecisionVM; now: number; lang: string; roads?: readonly (readonly LonLat[])[] | null } = $props();

	const left = $derived(vm.deadline != null ? countdownText(vm.deadline - now, lang) : null);
	const waited = $derived(vm.since != null ? fmtDuration((now - vm.since) / 1000, lang) : null);
	const when = $derived(left != null ? t(lang, 'v3_card_left', left) : waited ? t(lang, 'v3_card_waiting', waited) : '');
</script>

<CardFrame
	{lang}
	inset={vm.inset}
	href={vm.href}
	aria={t(lang, 'v3_card_decision_aria', vm.kindLine, vm.plate ? `${vm.title} ${vm.plate.masked ? t(lang, 'v3_masked') : vm.plate.mark}` : vm.title, when)}
	thumb={vm.thumb}
	art={vm.art}
	kind={vm.kindLine}
	title={vm.title}
	decide
	{roads}
	testid="v3-decision-card"
	data={{ kind: vm.kind, key: vm.key }}
>
	{#snippet badge()}
		{#if when}<V3Tag tone="decide" glyph="clock" glass><span class="timer">{when}</span></V3Tag>{/if}
		{#if vm.prov}<V3Tag tone="dashed" glyph={vm.prov.glyph} title={vm.prov.title} glass>{vm.prov.text}</V3Tag>{/if}
	{/snippet}
	{#snippet titleExtra()}
		{#if vm.plate}<PlateChip mark={vm.plate.mark} masked={vm.plate.masked} {lang} />{/if}
	{/snippet}
	<span class="w"><RedactedText text={vm.why} {lang} /></span>
	{#snippet foot()}
		{#if vm.by.ai}<V3Tag tone="ai" glyph="spark" size="sm">{vm.by.text}</V3Tag>{:else}<span class="by">{vm.by.text}</span>{/if}
		<span class="go">{t(lang, 'v3_card_review')}<Glyph name="chevR" size={16} /></span>
	{/snippet}
</CardFrame>

<style>
	.timer {
		font-variant-numeric: tabular-nums;
		font-weight: 700;
	}

	.w {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		color: var(--v3-t2);
		font-size: 14px;
		line-height: 20px;
	}

	.by {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.go {
		display: inline-flex;
		align-items: center;
		gap: 2px;
		margin-left: auto;
		color: var(--v3-brand-text);
		font-weight: 600;
		white-space: nowrap;
	}
</style>
