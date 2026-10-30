<script lang="ts">
	/**
	 * A vehicle's Overview card (V3-SPEC §6.4 "VehicleHero") — the class silhouette (an original illustration,
	 * never an image of the vehicle), the registration mark in its chip (masked until a duty officer is named,
	 * through ops.plate via the adapter's view), the lawful basis, the days of retention left and the last
	 * lawful read. A stolen vehicle carries the rule in words: evidence only, no fine is ever issued.
	 */
	import { t } from '$lib/i18n/strings';
	import { fmtStamp } from '$lib/ui/format/format';
	import { human } from '$lib/workspace/vocabulary';
	import type { ObjectRow } from '$lib/workspace/types';
	import type { InspectorView } from '$lib/workspace/kinds/common';
	import './packs.object';
	import Glyph from '../Glyph.svelte';
	import PlateChip from '../ui/PlateChip.svelte';
	import Panel from './Panel.svelte';
	import { retentionDaysLeft } from './model';
	import VehicleShot from '../media/VehicleShot.svelte';

	let { row, view, officer, lang, now }: { row: ObjectRow; view: InspectorView; officer: boolean; lang: string; now: number } = $props();

	const cls = $derived(typeof row.props.vehicle_class === 'string' ? row.props.vehicle_class : null);
	const basis = $derived(typeof row.props.lawful_basis === 'string' && row.props.lawful_basis ? human(row.props.lawful_basis) : null);
	const days = $derived(retentionDaysLeft(row.props.retention_until, now));
</script>

<Panel title={t(lang, 'obj_veh_h')} testid="obj-vehicle">
	<div class="veh">
		<VehicleShot cls={cls} {lang} width={190} class="sil" />
		<div class="facts">
			{#if view.plate?.mark}<div class="mark"><PlateChip mark={view.plate.mark} masked={view.plate.masked} {lang} /></div>{/if}
			<p class="who"><Glyph name="lock" size={15} />{officer ? t(lang, 'obj_veh_named') : t(lang, 'obj_veh_masked')}</p>
			<dl class="kv">
				{#if cls}<dt>{t(lang, 'obj_f_kind')}</dt><dd>{human(cls)}</dd>{/if}
				{#if basis}<dt>{t(lang, 'obj_veh_basis')}</dt><dd>{basis}</dd>{/if}
				{#if days != null}<dt>{t(lang, 'ws_p_retention')}</dt><dd data-testid="obj-retention">{t(lang, 'obj_veh_retention', days)}</dd>{/if}
				{#if row.t != null}<dt>{t(lang, 'obj_veh_last')}</dt><dd>{fmtStamp(row.t, now)} IST</dd>{/if}
			</dl>
		</div>
	</div>
	{#if view.note}
		<p class="rule" data-testid="obj-vehicle-rule"><Glyph name="shield" size={17} /><span>{#if view.note.title}<b>{view.note.title}</b>{' '}{/if}{view.note.text}</span></p>
	{/if}
</Panel>

<style>
	.veh {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 24px;
		align-items: center;
	}

	.veh :global(.sil) {
		width: 190px;
		height: auto;
		padding: 6px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.facts {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 0;
	}

	.mark {
		font-size: 22px;
	}

	.who {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
	}

	.kv {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 6px 18px;
		margin: 0;
		font-size: 14px;
	}

	dt {
		color: var(--v3-t2);
	}

	dd {
		margin: 0;
		color: var(--v3-t1);
		font-weight: 550;
	}

	.rule {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		margin: 0;
		padding: 12px 14px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-alert-veil);
		color: var(--v3-t1);
		font-size: var(--v3-text-meta);
		line-height: 19px;
	}

	.rule :global(.v3-glyph) {
		margin-top: 1px;
		color: var(--v3-alert-text);
	}
</style>
