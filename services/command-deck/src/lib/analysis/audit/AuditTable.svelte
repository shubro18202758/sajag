<script lang="ts">
	/**
	 * AuditTable (SPEC §5.3 "AuditTable and AI trace [S4]") — the audit as a
	 * dense table, newest first.
	 *
	 *   Time (IST, one format per column) · Kind · Actor (glyph, display name,
	 *   Test tag) · What happened (displayText; ids and masked marks through
	 *   the formatter; the whole server sentence in the tooltip) · Object
	 *   (object tag) · a narrow provenance column that marks NON-LIVE rows only
	 *   (Emulated, Simulated, open-source with its verification label)
	 *
	 * Provenance (SPEC §9.2): in a MIXED list each non-live row carries the
	 * compact glyph; in a UNIFORM list (every row the same non-live source)
	 * the toolbar states it once and each row keeps the word as visually
	 * hidden text (`data-prov-word`), so a row's text still says "Emulated".
	 *
	 * Filters All / Officers / Machine / System; scope City or Selected event
	 * (`audit-scope-city`, `audit-scope-event`, `audit-view[data-view]` — the
	 * AI trace's view line is `ai-view`, so no test id repeats on a page); the
	 * probe "Ask why" (`.probe-toggle`, `audit-probe-answer`: the streamed
	 * answer exactly as sent, under the plate rule). The root is `audit-feed`
	 * (the AI trace's is `ai-trace`, so both can share a page); rows are
	 * `data-prim="feed-item"` with `.f-row[data-feed-id][data-urn]`, plus
	 * `data-actor-kind`, `data-row-id` (server rows) and `data-level`. A row
	 * naming the selection is `.is-selected`; one naming a linked object is
	 * `.linked`. The newest 200 rows render, with "Load older". Rows are one
	 * per id: a repeated row is shown once, never as a duplicate key.
	 *
	 * Sources: `items` (the ops ledger, built by AuditStream), else `rows`
	 * (city feed rows), else the live world's city feed — every row for City,
	 * the rows naming the selection for Selected event.
	 *
	 * AI trace (`mode="ai"`): the same table over model rows only, with phase,
	 * tier and confidence; no officer row.
	 */
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.analysis';
	import { Button, Dialog, Icon, NonIdealState, ObjectTag, ProvenanceTag, SegmentedControl, Tag, Tooltip } from '$lib/ui';
	import { colStamp, fmtFull } from '$lib/ui/format/format';
	import { kindIcon } from '$lib/design/icons';
	import { ops } from '$lib/ops/store.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { parseUrn, type FeedRow } from '$lib/gods-eye/city-api';
	import ProseText from '$lib/workspace/components/inspector/ProseText.svelte';
	import { human } from '$lib/workspace/display';
	import { kindOne } from '$lib/workspace/kinds/generic';
	import { liveWorld, selectors } from '$lib/workspace/world.svelte';
	import { eventHistory } from '../history.svelte';
	import { aiTrace, filterCounts, filterItems, itemFromFeed, masked, newestFirst, provWord, toCsv, uniformProv, uniqueById, type AuditFilter, type AuditItem, type AuditMode, type AuditScope } from './rows';

	interface Props {
		scope: AuditScope;
		filter: AuditFilter;
		rows?: FeedRow[];
		probe?: boolean;
		mode?: AuditMode;
		/** Prebuilt items (the ops ledger); wins over `rows`. */
		items?: readonly AuditItem[];
		/** Scope and filter changes (the controls are the table's; the state may be the caller's). */
		onscope?: (s: AuditScope) => void;
		onfilter?: (f: AuditFilter) => void;
		/** Selected event unavailable: the reason (the segment is disabled). */
		eventDisabled?: string | null;
		/** `audit-view[data-view]` (default: the scope). */
		view?: string;
		/** The view line's words (default: from the scope). */
		viewLabel?: string;
		/** Extra state on the view line (a rung, a note). */
		viewExtra?: Snippet;
		/** Show the scope control. */
		scopes?: boolean;
		/** A row was activated (default: select its object and fly to it). */
		onrow?: (item: AuditItem) => void;
		/** Rows rendered before "Load older". */
		limit?: number;
		/** The title in the toolbar (the /ops band). */
		title?: string | null;
		lang?: string;
		/** A named duty officer is on console (raw marks through props.plate only). */
		officer?: boolean;
		[k: string]: unknown;
	}

	let {
		scope = $bindable('city'),
		filter = $bindable('all'),
		rows,
		probe = false,
		mode = 'audit',
		items,
		onscope,
		onfilter,
		eventDisabled = null,
		view,
		viewLabel,
		viewExtra,
		scopes = true,
		onrow,
		limit = 200,
		title = null,
		lang = 'en',
		officer = false,
		...rest
	}: Props = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const ai = $derived(mode === 'ai');

	// ── the rows ──────────────────────────────────────────────────────────
	const subject = $derived(selection.current);
	const base = $derived.by((): AuditItem[] => {
		if (items) return uniqueById(items);
		let src: readonly FeedRow[] = rows ?? liveWorld.feed();
		if (!rows && scope === 'event') src = subject ? src.filter((r) => r.urns.includes(subject)) : [];
		return uniqueById(src.map((r) => itemFromFeed(r, { officer, lang })));
	});
	const scoped = $derived(ai ? aiTrace(base) : base);
	const counts = $derived(filterCounts(scoped));
	const filtered = $derived(newestFirst(filterItems(scoped, filter)));
	let shownMax = $state(200);
	$effect(() => {
		shownMax = limit;
	});
	const shown = $derived(filtered.slice(0, shownMax));
	/** A uniform list's one provenance (the toolbar states it; rows keep a hidden word), else null. */
	const uniform = $derived(uniformProv(filtered));
	const stamps = $derived(colStamp(shown.map((i) => i.t), Date.now(), { seconds: true }));
	const serverRows = $derived(base.filter((i) => i.rowId).length);
	const humanRows = $derived(base.filter((i) => i.rowId && i.actorKind === 'human').length);

	/** The selection and its linked objects (rows naming them are marked). */
	const related = $derived.by(() => {
		if (!subject) return new Set<string>();
		return new Set([subject, ...selectors.linked(subject).map((o) => o.urn)]);
	});

	// ── columns by width ──────────────────────────────────────────────────
	let width = $state(1200);
	const narrow = $derived(width < 640);
	type Col = 'time' | 'kind' | 'phase' | 'actor' | 'what' | 'tier' | 'conf' | 'object' | 'prov';
	const cols = $derived.by((): Col[] => {
		if (narrow) return ai ? ['time', 'actor', 'what', 'conf', 'prov'] : ['time', 'actor', 'what', 'prov'];
		// below 1000 px the phase goes first (the sentence opens with it), so What happened keeps its room
		if (ai) return width < 1000 ? ['time', 'what', 'tier', 'conf', 'prov'] : ['time', 'phase', 'actor', 'what', 'tier', 'conf', 'object', 'prov'];
		return width < 900 ? ['time', 'kind', 'actor', 'what', 'prov'] : ['time', 'kind', 'actor', 'what', 'object', 'prov'];
	});
	const COL_W: Record<Col, string> = {
		time: '108px',
		kind: '112px',
		phase: '156px',
		actor: '196px',
		what: 'auto',
		tier: '120px',
		conf: '96px',
		object: '196px',
		prov: '44px',
	};
	/** The provenance column grows by the evidence button when a row carries evidence. */
	const hasEvidence = $derived(shown.some((i) => i.detail !== undefined && i.detail !== null));
	const colW = (c: Col) => (c === 'prov' && hasEvidence ? '72px' : narrow && c === 'actor' ? '128px' : narrow && c === 'time' ? '96px' : COL_W[c]);
	const COL_KEY: Record<Col, string> = {
		time: 'an_au_time',
		kind: 'an_au_kind',
		phase: 'an_au_phase',
		actor: 'an_au_actor',
		what: 'an_au_what',
		tier: 'an_au_tier',
		conf: 'an_au_conf',
		object: 'an_au_object',
		prov: 'an_au_source',
	};

	// ── controls ──────────────────────────────────────────────────────────
	const filterOptions = $derived([
		{ value: 'all' as const, label: `${L('an_au_all')} ${counts.all}` },
		{ value: 'officers' as const, label: L('an_au_officers'), disabled: ai },
		{ value: 'machine' as const, label: L('an_au_machine') },
		{ value: 'system' as const, label: L('an_au_system') },
	]);
	const subjectRow = $derived(subject ? liveWorld.graph().get(subject) : null);
	const scopeOptions = $derived([
		{ value: 'city' as const, label: L('an_au_scope_city'), attrs: { 'data-testid': 'audit-scope-city' } },
		{
			value: 'event' as const,
			label: !items && subjectRow && subjectRow.kind !== 'event' ? L('an_au_scope_object') : L('an_au_scope_event'),
			disabled: !!eventDisabled,
			title: eventDisabled ?? undefined,
			attrs: { 'data-testid': 'audit-scope-event' },
		},
	]);
	const shownView = $derived(view ?? scope);
	const shownViewLabel = $derived(
		viewLabel ??
			(scope === 'city'
				? L('an_au_view_city')
				: subjectRow
					? subjectRow.kind === 'event'
						? L('an_au_view_event', subjectRow.label)
						: L('an_au_view_object', subjectRow.label)
					: L('an_au_scope_event_none')),
	);

	function setScope(s: AuditScope) {
		scope = s;
		onscope?.(s);
	}

	function setFilter(f: AuditFilter) {
		filter = f;
		onfilter?.(f);
	}

	// ── rows ──────────────────────────────────────────────────────────────
	function activate(i: AuditItem) {
		if (onrow) return onrow(i);
		if (i.urn && parseUrn(i.urn)) selection.select(i.urn, { fly: true, source: 'rail' });
	}

	function onRowKey(e: KeyboardEvent, i: AuditItem) {
		if (e.key !== 'Enter' && e.key !== ' ') return;
		e.preventDefault();
		activate(i);
	}

	/**
	 * The object column's tag. A recommendation reads by its rule and masked
	 * mark ("Speeding on a segment · MH47EM•••1"): the decision is about the
	 * vehicle, and a camera id belongs to the camera's own rows.
	 */
	function objectOf(urn: string): { kind: string; label: string } | null {
		const p = parseUrn(urn);
		if (!p) return null;
		const row = liveWorld.graph().get(urn);
		if (row?.kind === 'recommendation') {
			const rule = typeof row.props.rule_id === 'string' ? row.props.rule_id : null;
			const key = rule ? `ws_rule_${rule}` : null;
			const word = key && t(lang, key) !== key ? t(lang, key) : rule ? human(rule) : kindOne('recommendation', lang);
			const mark = typeof row.props.plate_masked === 'string' ? row.props.plate_masked : null;
			return { kind: row.kind, label: mark ? `${word} · ${mark}` : word };
		}
		if (row) return { kind: row.kind, label: row.label };
		// an event known only from the event history (a page without the frame's object sources): its title, masked at parse
		if (p.kind === 'event') {
			const h = eventHistory.rows.find((r) => r.urn === urn);
			if (h?.title) return { kind: 'event', label: masked(h.title, false) };
		}
		const id = /^[0-9a-f]{8}-[0-9a-f]{4}-/.test(p.id) ? p.id.slice(0, 8) : p.id;
		return { kind: p.kind, label: id };
	}

	let evidence = $state<AuditItem | null>(null);

	// ── probe ─────────────────────────────────────────────────────────────
	let probeOpen = $state(false);
	let probeText = $state('');
	const probeSubject = $derived(ops.selectedEvent && ops.selectedEvent.source !== 'offline-fixture' ? ops.text(ops.selectedEvent.name).slice(0, 60) : L('an_au_scope_city').toLowerCase());

	// ── export (masked) ───────────────────────────────────────────────────
	function exportCsv() {
		const csv = toCsv(filtered, lang);
		const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `sajag-${ai ? 'ai-trace' : 'audit'}-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, '')}.csv`;
		document.body.appendChild(a);
		a.click();
		a.remove();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}
</script>

<div class="au" class:ai class:narrow data-testid={ai ? 'ai-trace' : 'audit-feed'} data-mode={mode} bind:clientWidth={width} {...rest}>
	<div class="bar">
		{#if title}<h2 class="ttl">{title}</h2>{/if}
		{#if scopes && !ai}
			<SegmentedControl small options={scopeOptions} value={scope} onchange={setScope} label={L('an_au_scope_label')} />
		{/if}
		<SegmentedControl small options={filterOptions} value={filter} onchange={setFilter} label={L('an_au_filter_label')} />
		<span class="view" data-testid={ai ? 'ai-view' : 'audit-view'} data-view={shownView} data-server-rows={serverRows} data-human-rows={humanRows}>
			<span class="vl">{shownViewLabel}</span>
			<span class="vc">{L('an_au_counts', shown.length, filtered.length)}</span>
			{#if viewExtra}{@render viewExtra()}{/if}
		</span>
		{#if uniform}
			<!-- a uniform list states its provenance once (SPEC §9.2) -->
			<ProvenanceTag source={uniform.source} verification={uniform.verification} {lang} data-uniform-prov />
		{/if}
		<span class="grow"></span>
		{#if !officer}
			<Tooltip content={L('an_au_masked')}><span class="masked"><Icon name="lock" size={12} /><span class="sr">{L('an_au_masked')}</span></span></Tooltip>
		{/if}
		{#if probe}
			<Button small minimal icon="explain" pressed={probeOpen} class="probe-toggle" aria-expanded={probeOpen} onclick={() => (probeOpen = !probeOpen)}>{L('an_au_probe')}</Button>
		{/if}
		<Button small minimal icon="export" tooltip={L('an_au_export_tip')} aria-label={L('an_au_export')} onclick={exportCsv} disabled={!filtered.length} />
	</div>

	{#if probe && probeOpen}
		<div class="probe" data-probe-open>
			<div class="probe-row">
				<input class="probe-input" type="text" bind:value={probeText} placeholder={L('an_au_probe_default')} aria-label={L('an_au_probe_input')} />
				<Button small intent="primary" loading={ops.auditProbeRunning} onclick={() => void ops.runAuditProbe(probeText.trim() || L('an_au_probe_default'))}>{L('an_au_probe_run')}</Button>
				<Button small minimal onclick={() => ops.clearAudit()}>{L('an_au_probe_clear')}</Button>
			</div>
			<p class="hint">
				{L('an_au_probe_hint', probeSubject)}
				{#if ops.probeDone}
					· {L('an_au_probe_tiers', ops.probeDone.tiersUsed.join(', ') || '—')}{ops.probeDone.degraded ? ` (${L('an_au_probe_degraded')})` : ''}
				{/if}
			</p>
			{#if ops.ndjsonText}
				<div class="answer">
					<span class="a-l">{L('an_au_probe_answer')}</span>
					<!-- the streamed answer exactly as sent, under the plate rule (ops.text) -->
					<pre data-testid="audit-probe-answer">{masked(ops.text(ops.ndjsonText), officer)}</pre>
				</div>
			{/if}
		</div>
	{/if}

	<div class="scroll" role="region" aria-label={ai ? L('an_tab_ai') : L('an_au_title')}>
		{#if !shown.length}
			<div class="empty">
				<NonIdealState icon={ai ? 'predictive-analysis' : 'history'} iconSize={20} layout="horizontal" title={ai ? L('an_au_ai_empty') : L('an_au_empty')} description={ai ? L('an_au_ai_empty_hint') : L('an_au_empty_hint')} />
			</div>
		{:else}
			<table class="dt">
				<colgroup>
					{#each cols as c (c)}<col style:width={colW(c)} />{/each}
				</colgroup>
				<thead>
					<tr>
						{#each cols as c (c)}
							<th scope="col" class="th c-{c}">{c === 'time' ? `${L(COL_KEY[c])} (IST)` : c === 'prov' ? '' : L(COL_KEY[c])}{#if c === 'prov'}<span class="sr">{L(COL_KEY[c])}</span>{/if}</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each shown as it, k (it.id)}
						{@const obj = it.urn ? objectOf(it.urn) : null}
						<tr
							class="row f-row {it.actorKind}"
							class:is-selected={!!subject && it.urn === subject}
							class:linked={it.urns.some((u) => related.has(u))}
							class:local={it.local}
							class:pick={!!it.urn || !!onrow}
							data-prim="feed-item"
							data-feed-id={it.feedId}
							data-urn={it.urn ?? ''}
							data-row-id={it.rowId ?? undefined}
							data-actor-kind={it.actorKind}
							data-level={it.level}
							data-source={it.source}
							aria-selected={!!subject && it.urn === subject}
							tabindex="0"
							onclick={() => activate(it)}
							onkeydown={(e) => onRowKey(e, it)}
						>
							{#each cols as c (c)}
								<td class="cell c-{c}">
									{#if c === 'time'}
										<span class="tm" title={fmtFull(it.t)}>{stamps[k]}</span>
									{:else if c === 'kind'}
										<span class="txt" title={it.local ? L('an_au_local_tip') : undefined}>{it.kindLabel}</span>
									{:else if c === 'phase'}
										<span class="txt">{it.phase ?? it.kindLabel}</span>
									{:else if c === 'actor'}
										<span class="who">
											<span class="glyph" class:aig={it.ai}><Icon name={it.glyph} size={16} /></span>
											<span class="name" title={it.actorRaw}>{it.actor}</span>
											{#if it.actorTest}<ProvenanceTag source="test" {lang} />{/if}
										</span>
									{:else if c === 'what'}
										{#if it.text}
											<span class="txt what" title={it.full}><ProseText text={it.text} /></span>
										{:else if ai && !cols.includes('phase')}
											<!-- a model row with no sentence, Phase and Actor not shown: say what it is (dim) -->
											<span class="txt dim">{it.phase ?? it.kindLabel} · {it.actor}</span>
										{:else}
											<span class="txt dim">—</span>
										{/if}
									{:else if c === 'tier'}
										<span class="txt">{it.tier ?? '—'}</span>
									{:else if c === 'conf'}
										{#if it.confidence != null}
											<span class="conf"><span class="bar-c"><i style:width="{Math.round(Math.max(0, Math.min(1, it.confidence)) * 100)}%"></i></span>{it.confidence.toFixed(2)}</span>
										{:else}
											<span class="txt dim">—</span>
										{/if}
									{:else if c === 'object'}
										{#if it.urn && obj}
											<ObjectTag urn={it.urn} kind={obj.kind} label={obj.label} masked={obj.kind === 'vehicle' ? true : null} />
										{:else if it.local}
											<Tag icon="console">{L('an_au_local')}</Tag>
										{/if}
									{:else if c === 'prov'}
										<span class="prov">
											{#if it.prov && uniform}
												<span class="sr" data-prov-word data-source={it.prov.source} data-verification={it.prov.verification ?? undefined}>{provWord(it.prov, lang)}</span>
											{:else if it.prov}
												<ProvenanceTag source={it.prov.source} verification={it.prov.verification} compact {lang} />
											{/if}
											{#if it.simulated}<ProvenanceTag source="simulated" compact {lang} data-testid="row-simulated" />{/if}
											{#if it.detail !== undefined && it.detail !== null}
												<Button
													small
													minimal
													icon="document"
													tooltip={L('an_au_evidence')}
													aria-label={L('an_au_evidence')}
													onclick={(e: MouseEvent) => {
														e.stopPropagation();
														evidence = it;
													}}
												/>
											{/if}
										</span>
									{/if}
								</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
			{#if filtered.length > shown.length}
				<div class="older">
					<Button small minimal icon="history" onclick={() => (shownMax += 200)}>{L('an_au_load_older')}</Button>
				</div>
			{/if}
		{/if}
	</div>
</div>

<Dialog open={!!evidence} title={evidence ? L('an_au_evidence_title', evidence.actor) : null} icon="document" width={640} onclose={() => (evidence = null)}>
	{#if evidence}<pre class="detail">{JSON.stringify(evidence.detail, null, 2)}</pre>{/if}
</Dialog>

<style>
	.au {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		min-width: 0;
		color: var(--v-ink-1);
		font-size: 12px;
		line-height: 16px;
	}

	.bar {
		display: flex;
		align-items: center;
		gap: 8px;
		flex: 0 0 auto;
		min-height: 36px;
		padding: 4px 8px 4px 16px;
		border-bottom: 1px solid var(--v-line-1);
		min-width: 0;
		overflow: hidden;
		white-space: nowrap;
	}

	.ttl {
		margin: 0 8px 0 0;
		font-size: 14px;
		line-height: 18px;
		font-weight: 600;
	}

	.view {
		display: inline-flex;
		align-items: baseline;
		gap: 8px;
		min-width: 0;
		overflow: hidden;
		color: var(--v-ink-2);
	}

	.vl {
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.vc {
		font-variant-numeric: tabular-nums;
	}

	.grow {
		flex: 1 1 auto;
	}

	.masked {
		display: inline-flex;
		color: var(--v-ink-2);
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	.probe {
		flex: 0 0 auto;
		padding: 8px 16px;
		border-bottom: 1px solid var(--v-line-1);
		background: var(--v-surface-2);
	}

	.probe-row {
		display: flex;
		gap: 8px;
		align-items: center;
	}

	.probe-input {
		flex: 1 1 auto;
		min-width: 0;
		height: 24px;
		padding: 0 8px;
		border: 0;
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-sink);
		box-shadow: inset 0 0 0 1px var(--v-line-2);
		color: var(--v-ink-1);
		font: inherit;
	}

	.probe-input:focus-visible {
		outline: 2px solid var(--v-focus);
	}

	.hint {
		margin: 4px 0 0;
		color: var(--v-ink-2);
	}

	.answer {
		margin-top: 8px;
	}

	.a-l {
		color: var(--v-ink-2);
	}

	.answer pre {
		margin: 4px 0 0;
		max-height: 120px;
		overflow: auto;
		padding: 6px 8px;
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-sink);
		color: var(--v-ink-1);
		font: inherit;
		white-space: pre-wrap;
	}

	.scroll {
		flex: 1 1 auto;
		min-height: 0;
		overflow: auto;
		overscroll-behavior: contain;
	}

	.empty {
		padding: 12px 16px;
	}

	.dt {
		width: 100%;
		border-collapse: separate;
		border-spacing: 0;
		table-layout: fixed;
	}

	.th {
		position: sticky;
		top: 0;
		z-index: 1;
		height: 30px;
		padding: 0 8px;
		border-bottom: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
		color: var(--v-ink-2);
		font-weight: 400;
		text-align: left;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.th.c-time,
	.cell.c-time {
		padding-left: 16px;
	}

	.cell {
		height: 28px;
		padding: 0 8px;
		border-bottom: 1px solid var(--v-line-1);
		overflow: hidden;
		vertical-align: middle;
		white-space: nowrap;
	}

	.row {
		outline: 0;
	}

	.pick {
		cursor: pointer;
	}

	.row:hover > td {
		background: var(--v-row-hover);
	}

	.row:focus-visible > td {
		box-shadow:
			inset 0 1px 0 var(--v-focus),
			inset 0 -1px 0 var(--v-focus);
	}

	/* linked to the selection: a 2 px blue rule (no fill: the selected row alone takes the veil) */
	.row.linked > td:first-child {
		box-shadow: inset 2px 0 0 var(--v-map-select);
	}

	.row.is-selected {
		background: var(--v-primary-veil);
	}

	.row.is-selected > td:first-child {
		box-shadow: inset 2px 0 0 var(--v-primary-text);
	}

	.tm {
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
	}

	.txt {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.txt.dim {
		color: var(--v-ink-2);
	}

	.what {
		color: var(--v-ink-1);
	}

	.system .what {
		color: var(--v-ink-2);
	}

	.local .c-kind .txt {
		color: var(--v-ink-2);
	}

	.who {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
	}

	.glyph {
		display: inline-flex;
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.glyph.aig {
		color: var(--v-ai-text);
	}

	.name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		color: var(--v-ink-2);
	}

	.human .name {
		color: var(--v-ink-1);
		font-weight: 600;
	}

	.conf {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-variant-numeric: tabular-nums;
	}

	.bar-c {
		position: relative;
		width: 32px;
		height: 4px;
		border-radius: 2px;
		background: var(--v-line-2);
		overflow: hidden;
	}

	.bar-c i {
		position: absolute;
		inset: 0 auto 0 0;
		background: var(--v-ai-text);
	}

	.prov {
		display: inline-flex;
		align-items: center;
		gap: 2px;
	}

	.older {
		display: flex;
		justify-content: center;
		padding: 6px;
	}

	.detail {
		margin: 0;
		max-height: 60vh;
		overflow: auto;
		color: var(--v-ink-2);
		font: inherit;
		white-space: pre-wrap;
	}
</style>
