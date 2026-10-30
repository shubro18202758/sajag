<script lang="ts">
	/**
	 * ReportCard (V3-SPEC §5.2, §8) — one reported situation, about a PLACE, never a person: its honest
	 * label on the map (Official / News-reported / Unverified, dashed when unverified), the credibility
	 * bar with its value and what it means ("how far the sources agree, not whether it happened"), and one
	 * note: "Response proposed" when a decision waits on it, else "Verify before acting" (or "From an
	 * official source"). No news or social link is ever shown or stored.
	 */
	import { t } from '$lib/i18n/strings';
	import '../packs.v3';
	import V3Tag from '../ui/V3Tag.svelte';
	import RedactedText from '../ui/RedactedText.svelte';
	import type { LonLat } from '../map/mercator';
	import CardFrame from './CardFrame.svelte';
	import AgencyMark from '../media/AgencyMark.svelte';
	import { sourceMark } from '../media/logos';
	import '../media/packs.media';
	import type { ReportVM } from './view';

	let { vm, lang, roads = null }: { vm: ReportVM; lang: string; roads?: readonly (readonly LonLat[])[] | null } = $props();

	const cred = $derived(vm.cred != null ? Math.max(0, Math.min(1, vm.cred)) : null);
	const mark = $derived(sourceMark(vm.source));
</script>

<CardFrame
	{lang}
	cover={vm.cover}
	href={vm.href}
	aria={t(lang, 'v3_card_aria', `${vm.verif.text}, ${vm.kindLine}`, vm.title)}
	thumb={vm.thumb}
	art={vm.art}
	kind={vm.kindLine}
	title={vm.title}
	{roads}
	testid="v3-report-card"
	data={{ key: vm.key, verification: vm.verif.tone }}
>
	{#snippet badge()}
		<V3Tag tone={vm.verif.tone} glyph={vm.verif.glyph} glass>{vm.verif.text}</V3Tag>
	{/snippet}
	{#if vm.meta}<span class="meta"><RedactedText text={vm.meta} {lang} /></span>{/if}
	{#if vm.source}
		<span class="src" data-testid="v3-report-source">
			{#if mark}<AgencyMark role={null} {mark} {lang} size={20} decorative />{/if}
			<span class="src-t">{t(lang, 'v3i_reported_by', vm.source)}</span>
		</span>
	{/if}
	{#snippet foot()}
		{#if cred != null}
			<span class="cred" title={t(lang, 'v3_cred_tip', cred.toFixed(2))}
				>{t(lang, 'v3_cred')} <span class="bar" aria-hidden="true"><i style:width="{cred * 100}%"></i></span><span class="v">{cred.toFixed(2)}</span></span
			>
		{/if}
		<span class={['note', vm.note === t(lang, 'v3_rep_note_response') && 'decide']}>{vm.note}</span>
	{/snippet}
</CardFrame>

<style>
	.meta {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		font-weight: 500;
	}

	.src {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		font-weight: 500;
	}

	.src-t {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.cred {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--v3-t2);
		font-weight: 600;
		white-space: nowrap;
	}

	.bar {
		width: 44px;
		height: 5px;
		overflow: hidden;
		border-radius: 3px;
		background: var(--v3-s4);
	}

	.bar i {
		display: block;
		height: 100%;
		background: var(--v3-t2);
	}

	.v {
		font-variant-numeric: tabular-nums;
	}

	.note {
		margin-left: auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.note.decide {
		color: var(--v3-decide-text);
		font-weight: 600;
	}
</style>
