<script lang="ts">
	/**
	 * The Record tab (V3-SPEC §3.3 L2 → L3) — EVERY field the v2 inspector's Properties tab shows, in one tab:
	 * the sections providers register for the kind (registerInspectorSection: the OSINT report and place
	 * sections and any later one — the page renders the Pursuit, decision-link and decision-support sections
	 * in their own homes on this page, so they are not repeated here), then the kind adapter's grouped
	 * properties (PropertyGroups, the inspector's own table) and, behind "Show system fields", the raw values
	 * (masked). Nothing is re-derived: these are the v2 components, composed by import.
	 */
	import type { Component } from 'svelte';
	import type { Dossier } from '$lib/gods-eye/city-api';
	import PropertyGroups from '$lib/workspace/components/inspector/PropertyGroups.svelte';
	import type { InspectorView } from '$lib/workspace/kinds/common';
	import type { InspectorSectionProps, ObjectRow } from '$lib/workspace/types';
	import { t } from '$lib/i18n/strings';
	import './packs.object';
	import Glyph from '../Glyph.svelte';
	import Panel from './Panel.svelte';

	let {
		row,
		view,
		dossier,
		sections,
		lang,
		now,
		onselect,
	}: {
		row: ObjectRow;
		view: InspectorView;
		dossier: Dossier | null;
		sections: readonly { id: string; component: Component<InspectorSectionProps> }[];
		lang: string;
		now: number;
		onselect: (urn: string) => void;
	} = $props();

	let system = $state(false);
</script>

<Panel title={t(lang, 'obj_rec_h')} testid="obj-record">
	<p class="sub">{t(lang, 'obj_rec_sub')}</p>
	{#each sections as s (s.id)}
		<div class="sec" data-section={s.id}><s.component {row} {dossier} /></div>
	{/each}
	<div class="props" data-testid="obj-props">
		<PropertyGroups groups={view.groups} {now} {onselect} />
		{#if system}
			<PropertyGroups groups={[{ title: t(lang, 'ws_grp_system'), rows: view.system }]} {now} {onselect} />
		{/if}
	</div>
	<button type="button" class="sys" aria-pressed={system} onclick={() => (system = !system)} data-testid="obj-system-toggle"
		><Glyph name="list" size={16} />{system ? t(lang, 'obj_rec_system_hide') : t(lang, 'obj_rec_system_show')}</button
	>
</Panel>

<style>
	.sub {
		margin: -6px 0 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
	}

	.sec {
		padding-bottom: 6px;
	}

	.props {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.sys {
		display: inline-flex;
		align-items: center;
		align-self: flex-start;
		gap: 6px;
		height: var(--v3-ctl);
		padding: 0 14px;
		border: 1px solid var(--v3-line-2);
		border-radius: 18px;
		background: none;
		color: var(--v3-t2);
		font: inherit;
		font-size: 14px;
		font-weight: 600;
		cursor: pointer;
	}

	.sys:hover {
		background: var(--v3-s2);
		color: var(--v3-t1);
	}

	.sys:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}
</style>
