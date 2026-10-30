<script lang="ts">
	/**
	 * A vehicle's lawful reads (V3-SPEC §6.4 Reads tab) — newest first: when, which camera, the speed read.
	 * Only the reads the oracle may show reach the deck (an earmark's lawful basis, or a recommendation's
	 * evidence); the list says so, and never shows a vehicle image (there is none) or a raw mark without a
	 * named officer (each row's label is the masked row label).
	 */
	import { t } from '$lib/i18n/strings';
	import { fmtStamp } from '$lib/ui/format/format';
	import type { ObjectRow } from '$lib/workspace/types';
	import './packs.object';
	import Glyph from '../Glyph.svelte';
	import { objectHref } from './model';

	let { reads, lang, now }: { reads: readonly ObjectRow[]; lang: string; now: number } = $props();

	const rows = $derived([...reads].sort((a, b) => (b.t ?? 0) - (a.t ?? 0)));
	const cam = (r: ObjectRow) => (typeof r.props.camera_id === 'string' ? r.props.camera_id : null);
	const kmh = (r: ObjectRow) => (typeof r.props.speed_kmh === 'number' ? Math.round(r.props.speed_kmh) : null);
</script>

<p class="note"><Glyph name="shield" size={16} />{t(lang, 'obj_reads_note')}</p>
{#if rows.length}
	<ol class="reads" data-testid="obj-reads">
		{#each rows as r (r.urn)}
			{@const href = objectHref(r.urn)}
			<li>
				<a class="read" href={href ?? undefined}>
					<span class="tm">{r.t != null ? `${fmtStamp(r.t, now)} IST` : '—'}</span>
					<span class="g"><Glyph name="anpr" size={16} /></span>
					<span class="where">{cam(r) ? t(lang, 'obj_read_at', cam(r)) : r.label}</span>
					{#if kmh(r) != null}<span class="spd">{kmh(r)} km/h</span>{/if}
				</a>
			</li>
		{/each}
	</ol>
{:else}
	<p class="empty">{t(lang, 'obj_reads_empty')}</p>
{/if}

<style>
	.note {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.reads {
		display: flex;
		flex-direction: column;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.read {
		display: grid;
		grid-template-columns: 150px 28px minmax(0, 1fr) auto;
		gap: 12px;
		align-items: center;
		min-height: 44px;
		padding: 0 10px;
		border-radius: var(--v3-radius-s);
		color: var(--v3-t1);
		font-size: 14px;
		text-decoration: none;
	}

	.read:hover {
		background: var(--v3-s2);
	}

	.read:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.tm,
	.spd {
		color: var(--v3-t2);
		font-variant-numeric: tabular-nums;
	}

	.g {
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		border-radius: 8px;
		background: var(--v3-alert-veil);
		color: var(--v3-alert-text);
	}

	.where {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.empty {
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
	}
</style>
