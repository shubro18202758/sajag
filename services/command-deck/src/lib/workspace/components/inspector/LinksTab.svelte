<script lang="ts">
	/**
	 * Links n — the object's links grouped by relation, named from this end
	 * (`rel-group[data-relation]`, rows `rel-chip[data-urn]`). A group whose
	 * rows share one state says it once in its header; a mixed group tags each
	 * row. One time format per group. Five rows show; the rest stay in the
	 * DOM behind "Show n more". A decided recommendation is a two-line row
	 * with its decider.
	 *
	 * A group's name is never cut for its provenance: a uniform group says its
	 * provenance in words while the name fits beside it, and with its compact
	 * glyph (the same label, as its tooltip and hidden text) when it does not.
	 */
	import { eventKindIcon, kindIcon } from '$lib/design/icons';
	import { Button, Icon, Id, NonIdealState, Plate, ProvenanceTag, Tag } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.workspace';
	import { actorName, actorParts, localTitle } from '../../display';
	import { shortStateWord } from '../../kinds/generic';
	import type { ObjectLink, ObjectRow } from '../../types';
	import { linkGroups, sharedStateWord } from './model';

	let {
		links,
		lang,
		now,
		onselect,
		ongraph,
		ontable,
	}: {
		links: readonly ObjectLink[];
		lang: string;
		now: number;
		onselect: (urn: string, add: boolean) => void;
		ongraph?: ((urns: string[]) => void) | null;
		/** Open a group's rows in the table; `group` is the group's name (the filter's label says it). */
		ontable?: ((urns: string[], group: string) => void) | null;
	} = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const SHOWN = 5;

	const groups = $derived(linkGroups(links, lang, now));
	let open = $state<Record<string, boolean>>({});
	let collapsed = $state<Record<string, boolean>>({});

	const glyph = (row: ObjectRow) => (row.kind === 'event' ? eventKindIcon(typeof row.props.event_kind === 'string' ? row.props.event_kind : null) : kindIcon(row.kind));
	const str = (v: unknown) => (typeof v === 'string' && v.trim() ? v : null);
	const evidence = (row: ObjectRow) => (row.props.evidence ?? {}) as Record<string, unknown>;
	const prov = (row: ObjectRow): 'emulated' | 'simulated' | 'osint' | null =>
		row.source === 'emulated' || row.source === 'simulated' || row.source === 'osint' ? row.source : null;
	const decided = (row: ObjectRow) => (row.kind === 'recommendation' && str(row.props.decided_by) ? actorParts(String(row.props.decided_by)) : null);
	const verif = (row: ObjectRow) => {
		const v = row.verification;
		return row.source === 'osint' && (v === 'UNVERIFIED-OSINT' || v === 'NEWS-REPORTED' || v === 'OFFICIAL-VERIFIED' || v === 'CONFIRMED') ? v : null;
	};
	/** A mixed group marks non-live rows with a compact glyph; a uniform one says it once, in words (SPEC §9.2). */
	const mixedSources = (rows: ObjectRow[]) => new Set(rows.map((r) => `${r.source}|${verif(r) ?? ''}`)).size > 1;

	/**
	 * The header's provenance in words while the group's name fits beside it;
	 * else (`data-tight`) its compact glyph, so the name is never cut for it.
	 * Measured with the words shown, again on every resize of the header.
	 */
	function fitProv(node: HTMLElement, _key: string) {
		const fit = () => {
			delete node.dataset.tight;
			const name = node.querySelector<HTMLElement>('.rel-name');
			if (name && node.querySelector('.hp-full') && name.scrollWidth > name.clientWidth) node.dataset.tight = 'true';
		};
		const ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(fit);
		ro?.observe(node);
		fit();
		return { update: fit, destroy: () => ro?.disconnect() };
	}
</script>

{#if !groups.length}
	<div class="empty"><NonIdealState icon="graph" iconSize={32} title={L('ws_links_none')} description={L('ws_links_none_hint')} /></div>
{:else}
	{#each groups as g (g.relation)}
		{@const shared = sharedStateWord(g, lang)}
		{@const mixed = mixedSources(g.rows)}
		{@const showAll = open[g.relation] === true}
		{@const shut = collapsed[g.relation] === true}
		<section class="rel-group" data-relation={g.relation} data-count={g.rows.length}>
			<div class="lg-head">
				<button
					type="button"
					class="lg-toggle"
					aria-expanded={!shut}
					onclick={() => (collapsed = { ...collapsed, [g.relation]: !shut })}
					use:fitProv={`${g.label}|${shared ?? ''}|${g.rows.length}|${mixed}`}
				>
					<Icon name={shut ? 'chevron-right' : 'chevron-down'} class="chev" />
					<Icon name={kindIcon(g.kind)} class="kind" />
					<span class="rel-name" title={g.label}>{g.label}</span>
					<span class="count">{g.rows.length}</span>
					{#if shared}<span class="meta">{shared}</span>{/if}
					{#if !mixed && prov(g.rows[0])}<span class="hp hp-full"><ProvenanceTag source={prov(g.rows[0])!} verification={verif(g.rows[0])} /></span><span
							class="hp hp-compact"><ProvenanceTag source={prov(g.rows[0])!} verification={verif(g.rows[0])} compact /></span
						>{/if}
				</button>
				<span class="acts">
					{#if ongraph}<Button minimal small icon="send-to-graph" tooltip={L('ws_links_add_graph')} aria-label={L('ws_links_add_graph')} onclick={() => ongraph?.(g.rows.map((r) => r.urn))} />{/if}
					{#if ontable}<Button minimal small icon="th" tooltip={L('ws_links_open_table')} aria-label={L('ws_links_open_table')} onclick={() => ontable?.(g.rows.map((r) => r.urn), g.label)} />{/if}
				</span>
			</div>
			{#each g.rows as row, i (row.urn)}
				{@const d = decided(row)}
				<button
					type="button"
					class="rel-chip"
					class:two={!!d}
					hidden={shut || (!showAll && i >= SHOWN)}
					data-urn={row.urn}
					data-kind={row.kind}
					data-state={row.state ?? ''}
					onclick={(e) => onselect(row.urn, e.shiftKey || e.ctrlKey || e.metaKey)}
				>
					<span class="l1">
						<Icon name={glyph(row)} class="kind" />
						<span class="lbl">
							{#if row.kind === 'vehicle'}<Plate mark={row.label} masked />
							{:else if row.kind === 'sighting' || row.kind === 'camera'}<Id value={row.kind === 'camera' ? row.id : row.label} />{#if row.kind === 'camera' && row.sublabel}<span class="muted">{` · ${row.sublabel}`}</span>{/if}
							{:else if row.kind === 'recommendation'}{#if str(evidence(row).road_name)}{`${str(evidence(row).road_name)} · `}{/if}<Id value={str(evidence(row).camera_id) ?? str(row.props.camera_id) ?? row.id.slice(0, 8)} />
							{:else}{localTitle(row.label, lang)}{/if}
						</span>
						{#if !shared && row.state && row.kind !== 'sighting' && row.kind !== 'camera' && row.kind !== 'vehicle'}
							<Tag intent={row.stateIntent}>{shortStateWord(row.state, lang)}</Tag>
						{/if}
						{#if row.test}<ProvenanceTag source="test" />{/if}
						{#if mixed && prov(row)}<ProvenanceTag source={prov(row)!} verification={verif(row)} compact />{/if}
						<span class="when">{g.times[i]}</span>
					</span>
					{#if d}
						<span class="l2">{actorName(d, lang)}{#if d.scenario}{' '}<span class="scn">{d.scenario}</span>{/if}</span>
					{/if}
				</button>
			{/each}
			{#if !shut && g.rows.length > SHOWN}
				<button type="button" class="more" onclick={() => (open = { ...open, [g.relation]: !showAll })}>
					{showAll ? L('ws_links_less') : L('ws_links_more', g.rows.length - SHOWN)}
				</button>
			{/if}
		</section>
	{/each}
{/if}

<style>
	.empty {
		padding: 24px 0;
	}

	.rel-group {
		border-bottom: 1px solid var(--v-line-1);
		padding: 4px 0;
	}

	.lg-head {
		display: flex;
		align-items: center;
		gap: 4px;
		height: 32px;
	}

	.lg-toggle {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		flex: 1 1 auto;
		min-width: 0;
		height: 28px;
		padding: 0 4px 0 0;
		border: 0;
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		font-size: 14px;
		cursor: pointer;
		text-align: left;
	}

	.lg-toggle :global(.chev),
	.lg-toggle :global(.kind) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	/* the name yields last: the count, the state word and the provenance never shrink (an ellipsis only when even the glyph leaves no room) */
	.rel-name {
		flex: 0 1 auto;
		min-width: 0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.count,
	.meta,
	.hp {
		flex: 0 0 auto;
	}

	.hp {
		display: inline-flex;
	}

	/* data-tight is set by fitProv (an action), so the compiler must keep these rules as written */
	.hp-compact,
	.lg-toggle:global([data-tight='true']) .hp-full {
		display: none;
	}

	.lg-toggle:global([data-tight='true']) .hp-compact {
		display: inline-flex;
	}

	.count {
		display: inline-flex;
		align-items: center;
		height: 20px;
		padding: 0 8px;
		border-radius: var(--v-radius-pill);
		background: var(--v-neutral-veil);
		color: var(--v-ink-1);
		font-size: 12px;
		font-variant-numeric: tabular-nums;
	}

	.meta {
		font-size: 12px;
		color: var(--v-ink-2);
		white-space: nowrap;
	}

	.acts {
		display: inline-flex;
		gap: 4px;
		margin-left: auto;
		flex: 0 0 auto;
	}

	.rel-chip {
		display: flex;
		flex-direction: column;
		justify-content: center;
		width: 100%;
		min-height: 28px;
		padding: 0 4px 0 24px;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		font-size: 12px;
		line-height: 16px;
		text-align: left;
		cursor: pointer;
	}

	.rel-chip[hidden] {
		display: none;
	}

	.rel-chip.two {
		min-height: 40px;
		padding-top: 4px;
		padding-bottom: 4px;
	}

	.rel-chip:hover {
		background: var(--v-row-hover);
	}

	.l1 {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.l1 :global(.kind) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.lbl {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.muted {
		color: var(--v-ink-2);
	}

	.when {
		margin-left: auto;
		flex: 0 0 auto;
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.l2 {
		display: block;
		padding-left: 24px;
		color: var(--v-ink-2);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.scn {
		color: var(--v-ink-2);
	}

	.more {
		display: block;
		width: 100%;
		height: 28px;
		padding: 0 0 0 48px;
		border: 0;
		background: transparent;
		color: var(--v-primary-text);
		font: inherit;
		font-size: 12px;
		text-align: left;
		cursor: pointer;
	}

	.more:hover {
		text-decoration: underline;
	}
</style>
