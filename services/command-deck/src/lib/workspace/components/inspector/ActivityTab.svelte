<script lang="ts">
	/**
	 * Activity n — one row per entry (class `a-row`): time, actor glyph, actor
	 * (displayActor), and brief(row); the full text opens in the row's
	 * expander, its officer note exactly as sent. Filters All / Officers /
	 * Machine / System. Registered activity renderers follow the rows.
	 *
	 * In a 344–400 px dock a dated stamp ("23 Oct 22:08") would leave the
	 * brief a dozen characters: once the rows span days, the day sits UNDER
	 * every row's clock (one format for the column), and the actor and brief
	 * take up to two lines. Provenance (SPEC §9.2): one source for every row
	 * is said once above them; a mixed list marks each non-live row with the
	 * compact glyph — an OSINT row with its verification label (ethics 7).
	 */
	import type { FeedRow, Dossier } from '$lib/gods-eye/city-api';
	import { Icon, NonIdealState, ProvenanceTag, SegmentedControl } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.workspace';
	import { activityRenderersList } from '../../registry';
	import type { ObjectRow } from '../../types';
	import { activityCounts, activityRows, type ActivityFilter } from './model';
	import ProseText from './ProseText.svelte';

	let { rows, row, dossier, lang, now, mask }: { rows: readonly FeedRow[]; row: ObjectRow; dossier: Dossier | null; lang: string; now: number; mask: (s: string) => string } = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	let filter = $state<ActivityFilter>('all');
	let open = $state<Record<string, boolean>>({});

	const counts = $derived(activityCounts(rows));
	const shown = $derived(activityRows(rows, filter, now, lang));
	const options = $derived([
		{ value: 'all' as const, label: `${L('ws_act_all')} ${counts.all}` },
		{ value: 'human' as const, label: L('ws_act_officers') },
		{ value: 'machine' as const, label: L('ws_act_machine') },
		{ value: 'system' as const, label: L('ws_act_system') },
	]);
	const renderers = $derived(activityRenderersList());
	const prov = (s: string): 'emulated' | 'osint' | null => (s === 'emulated' || s === 'osint' ? s : null);
	/** An OSINT row's label as the tag knows it (the four OSINT states; EMULATED and SIMULATED are sources, said by the source). */
	const verif = (v: string | null): 'UNVERIFIED-OSINT' | 'NEWS-REPORTED' | 'OFFICIAL-VERIFIED' | 'CONFIRMED' | null =>
		v === 'UNVERIFIED-OSINT' || v === 'NEWS-REPORTED' || v === 'OFFICIAL-VERIFIED' || v === 'CONFIRMED' ? v : null;
	/** One provenance (source and verification) for every row is stated once, above the rows; a mixed list marks its non-live rows (SPEC §9.2). */
	const keys = $derived(new Set(shown.map((r) => `${r.source}|${r.verification ?? ''}`)));
	const uniform = $derived(keys.size === 1 && shown.length ? { source: prov(shown[0].source), verification: shown[0].verification } : null);
	const mixed = $derived(keys.size > 1);
	const actorTip = (kind: string, ai: boolean) =>
		kind === 'human' ? L('ws_actor_officer') : kind === 'system' ? L('ws_actor_system') : ai ? L('ws_actor_ai') : L('ws_actor_rules');
</script>

<div class="filters">
	<SegmentedControl small options={options} bind:value={filter} label={L('ws_tab_activity')} />
	{#if uniform?.source}<ProvenanceTag source={uniform.source} verification={verif(uniform.verification)} />{/if}
</div>
{#if !shown.length}
	<div class="empty"><NonIdealState icon="history" iconSize={32} title={L('ws_act_none')} description={L('ws_act_none_hint')} /></div>
{:else}
	<ol class="rows">
		{#each shown as r (r.id)}
			<li class="a-row" data-feed-id={r.id} data-actor-kind={r.actorKind}>
				<button type="button" class="line" aria-expanded={open[r.id] === true} title={mask(r.full)} onclick={() => (open = { ...open, [r.id]: !open[r.id] })}>
					<span class="tm" title={r.time}><span class="clock">{r.clock}</span>{#if r.day}<span class="day">{r.day}</span>{/if}</span>
					<span class="who-glyph" class:ai={r.ai} title={actorTip(r.actorKind, r.ai)}><Icon name={r.glyph} /></span>
					<span class="what"
						><b>{r.who}</b>{#if r.test}{' '}<ProvenanceTag source="test" />{/if}{' '}<span class="brief"><ProseText text={mask(r.brief)} /></span></span
					>
					{#if mixed && prov(r.source)}<ProvenanceTag source={prov(r.source)!} verification={verif(r.verification)} compact />{:else}<span></span>{/if}
					<Icon name={open[r.id] ? 'chevron-down' : 'chevron-right'} size={12} class="x" />
				</button>
				{#if open[r.id]}<p class="full"><ProseText text={mask(r.full)} /></p>{/if}
			</li>
		{/each}
	</ol>
{/if}
{#each renderers as rd (rd.id)}
	<rd.component {row} {dossier} />
{/each}

<style>
	.filters {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		padding: 8px 0;
	}

	.empty {
		padding: 16px 0;
	}

	.rows {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.a-row {
		border-bottom: 1px solid var(--v-line-1);
	}

	/* one entry: the cells align on its first line; a one-line entry sits centred in its 32 px */
	.line {
		display: grid;
		grid-template-columns: 40px 16px minmax(0, 1fr) auto 12px;
		gap: 8px;
		align-items: start;
		align-content: center;
		width: 100%;
		min-height: 32px;
		padding: 4px 0;
		border: 0;
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		font-size: 12px;
		line-height: 16px;
		text-align: left;
		cursor: pointer;
	}

	.line:hover {
		background: var(--v-row-hover);
	}

	/* the clock, and under it the day once the rows span days (every row the same: one format per column) */
	.tm {
		display: flex;
		flex-direction: column;
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.day {
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.who-glyph {
		display: inline-flex;
		color: var(--v-ink-2);
	}

	/* centred on the entry's first 16 px line: the 20 px compact tag (its tooltip wrapper is display: contents) and the 12 px chevron */
	.line :global(.prov.compact) {
		margin-top: -2px;
	}

	.line :global(.x) {
		margin-top: 2px;
		color: var(--v-ink-2);
	}

	.who-glyph.ai {
		color: var(--v-ai-text);
	}

	/* the actor and the brief take up to two lines, then end in an ellipsis (the full text is the tooltip and expander) */
	.what {
		display: -webkit-box;
		min-width: 0;
		overflow: hidden;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		overflow-wrap: anywhere;
	}

	.what b {
		font-weight: 600;
	}

	.brief {
		color: var(--v-ink-2);
	}

	.full {
		margin: 0;
		padding: 0 0 8px 48px;
		font-size: 12px;
		line-height: 18px;
		color: var(--v-ink-1);
	}
</style>
