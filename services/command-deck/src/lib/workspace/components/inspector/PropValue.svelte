<script lang="ts">
	/**
	 * One property value through the formatter: text, an identifier, a masked
	 * registration mark, an IST time or range, a linked object (an ObjectTag
	 * that selects it), tags, a provenance, a coordinate.
	 */
	import { Coord, Id, ObjectTag, Plate, ProvenanceTag, Tag, Time, TimeRange } from '$lib/ui';
	import type { PropValue } from '../../kinds/common';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { localTitle } from '../../display';

	let {
		value,
		now,
		onselect,
		testid,
		attrs = {},
	}: {
		value: PropValue;
		now: number;
		onselect: (urn: string) => void;
		testid?: string;
		attrs?: Record<string, string>;
	} = $props();

	type P<T extends PropValue['t']> = Extract<PropValue, { t: T }>;
	const as = <T extends PropValue['t']>(v: PropValue, t: T): P<T> | null => (v.t === t ? (v as P<T>) : null);
	const eventKind = (v: P<'object'>) => (typeof v.row.props.event_kind === 'string' ? v.row.props.event_kind : null);
	const prov = (s: string): 'emulated' | 'simulated' | 'osint' | 'test' | null =>
		s === 'emulated' || s === 'simulated' || s === 'osint' || s === 'test' ? s : null;
	const verif = (v: string | null | undefined) =>
		v === 'UNVERIFIED-OSINT' || v === 'NEWS-REPORTED' || v === 'OFFICIAL-VERIFIED' || v === 'CONFIRMED' ? v : null;
	const hintOf = (v: PropValue) => ('hint' in v ? (v.hint ?? null) : null);
</script>

{#if as(value, 'text')}
	{@const v = as(value, 'text')!}
	<span class="val" data-testid={testid} {...attrs}>{v.v}</span>
{:else if as(value, 'id')}
	{@const v = as(value, 'id')!}
	<span class="val" data-testid={testid} {...attrs}><Id value={v.v} /></span>
{:else if as(value, 'plate')}
	{@const v = as(value, 'plate')!}
	<span class="val" data-testid={testid} {...attrs}><Plate mark={v.mark} masked={v.masked} /></span>
{:else if as(value, 'time')}
	{@const v = as(value, 'time')!}
	<span class="val" data-testid={testid} {...attrs}><Time value={v.ms} seconds={v.seconds} anchor={now} suffix fullTip /></span>
{:else if as(value, 'range')}
	{@const v = as(value, 'range')!}
	<span class="val" data-testid={testid} {...attrs}><TimeRange start={v.a} end={v.b} anchor={now} suffix /></span>
{:else if as(value, 'object')}
	{@const v = as(value, 'object')!}
	<span class="val" data-testid={testid} {...attrs}
		><ObjectTag urn={v.row.urn} kind={v.row.kind} label={localTitle(v.row.label, commandBar.lang)} masked={v.row.masked ? true : null} eventKind={eventKind(v)} onselect={onselect} /></span
	>
{:else if as(value, 'tags')}
	{@const v = as(value, 'tags')!}
	<span class="val tags" data-testid={testid} {...attrs}
		>{#each v.tags as tg, i (i)}<Tag intent={tg.intent} icon={tg.icon} tooltip={tg.tooltip ?? null}>{tg.text}</Tag>{/each}</span
	>
{:else if as(value, 'source')}
	{@const v = as(value, 'source')!}
	{@const p = prov(v.source)}
	<span class="val src" data-testid={testid} {...attrs}>{#if p}<ProvenanceTag source={p} verification={verif(v.verification)} compact />{/if}{v.text}</span>
{:else if as(value, 'coord')}
	{@const v = as(value, 'coord')!}
	<span class="val" data-testid={testid} {...attrs}><Coord lat={v.lat} lon={v.lon} /></span>
{/if}
{#if hintOf(value)}<span class="hint">{hintOf(value)}</span>{/if}

<style>
	.val {
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
		min-width: 0;
	}

	.tags {
		flex-wrap: wrap;
		gap: 4px;
	}

	.src {
		align-items: center;
	}

	.hint {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}
</style>
