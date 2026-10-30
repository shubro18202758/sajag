<script lang="ts">
	/**
	 * PlannedCard (V3-SPEC §5.2) — one planned event in the next 72 hours: when it starts (a tag on the
	 * map), its place and route, its window and the state of its plan.
	 */
	import { t } from '$lib/i18n/strings';
	import '../packs.v3';
	import V3Tag from '../ui/V3Tag.svelte';
	import type { LonLat } from '../map/mercator';
	import CardFrame from './CardFrame.svelte';
	import type { PlannedVM } from './view';

	let { vm, lang, roads = null }: { vm: PlannedVM; lang: string; roads?: readonly (readonly LonLat[])[] | null } = $props();
</script>

<CardFrame
	{lang}
	cover={vm.cover}
	href={vm.href}
	aria={t(lang, 'v3_card_aria', `${vm.when}, ${vm.kindLine}`, vm.title)}
	thumb={vm.thumb}
	art={vm.art}
	kind={vm.kindLine}
	title={vm.title}
	{roads}
	testid="v3-planned-card"
	data={{ key: vm.key }}
>
	{#snippet badge()}
		<V3Tag tone="neutral" glyph="calendar" glass>{vm.when}</V3Tag>
		{#if vm.prov}<V3Tag tone="dashed" glyph={vm.prov.glyph} title={vm.prov.title} glass>{vm.prov.text}</V3Tag>{/if}
	{/snippet}
	{#if vm.meta}<span class="meta">{vm.meta}</span>{/if}
	{#snippet foot()}
		<span>{vm.next}</span>
	{/snippet}
</CardFrame>

<style>
	.meta {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		font-weight: 500;
	}
</style>
