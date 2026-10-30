<script lang="ts">
	/**
	 * /design/analysis — the UI-S4 harness (plan R18, X16): the link graph,
	 * the timeline (compact, full, brushed), the audit table and the AI trace
	 * over FIXTURE data, offline. Not linked from navigation; UI-S7B deletes it.
	 *
	 * Data: the committed vehicle fixture (tests/fixtures/workspace/
	 * captured.json — the prototype's emulated, masked capture: MH47EM•••1 and
	 * its 51 linked objects, 189 feed rows, every person replaced by the
	 * fictional "Sandbox Officer") and UI-S7A's event-history fixture
	 * (tests/contract/fixtures/events_history.sandbox.json, masked). The real
	 * stores are seeded (cityRegistry, dossier, the city feed, the event
	 * history) and the dock's clock is pinned to the capture time: nothing is
	 * fetched and the views read exactly what they read on a route.
	 *
	 *   ?w=500&h=600   the graph alone, in a W × H box (the label check)
	 *   ?layout=radial|force|hierarchical
	 *   ?sel=<urn>     select another object (the graph keeps the vehicle as focus)
	 *
	 * window.__ANALYSIS_HARNESS__ exposes the graph's layout timings
	 * (window.__LINK_GRAPH__) and select(urn).
	 */
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { ProvenanceTag, Tag, provideUiLang } from '$lib/ui';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { parseCitySnapshot, parseDossier, parseFeedRows, type Dossier } from '$lib/gods-eye/city-api';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { dossier } from '$lib/gods-eye/entities/dossier.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { fusionFeed } from '$lib/gods-eye/hud/feed.svelte';
	import FusionRail from '$lib/gods-eye/hud/FusionRail.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { selectors } from '$lib/workspace/world.svelte';
	import LinkGraph from '$lib/analysis/graph/LinkGraph.svelte';
	import type { LayoutMode } from '$lib/analysis/graph/layout';
	import Timeline from '$lib/analysis/timeline/Timeline.svelte';
	import AuditTable from '$lib/analysis/audit/AuditTable.svelte';
	import { aiTrace, itemFromFeed, type AuditFilter } from '$lib/analysis/audit/rows';
	import { HOUR, MIN } from '$lib/analysis/timeline/bins';
	import { eventHistory } from '$lib/analysis/history.svelte';
	import { parseEventHistory } from '$lib/analysis/history-api';
	import { dockState } from '$lib/analysis/dock/dock-state.svelte';
	import capture from '../../../../../tests/fixtures/workspace/captured.json';
	import historyFixture from '../../../../../tests/contract/fixtures/events_history.sandbox.json';

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);

	// ── the fixture world ──────────────────────────────────────────────────
	const AS_OF = Date.parse(capture.as_of);
	const VEHICLE = capture.vehicle;
	/**
	 * The capture has no open-source row: one FICTIONAL report (a synthetic
	 * replica, no person, no publisher) shows X8 — it rides the Events lane
	 * with the globe glyph and keeps its verification label in the audit.
	 */
	const FICTIONAL_OSINT = {
		id: 'fictional:osint-1',
		t: new Date(Date.parse(capture.as_of) - 52 * 60_000).toISOString(),
		kind: 'osint',
		urns: ['osint_event:6f1c2a9e-3b7d-4e21-9a55-0c8e7d4b1f20'],
		actor: 'osint-ingress (system)',
		actor_kind: 'system',
		text: 'Road accident reported near BKC, traffic slow towards Kalanagar (fictional harness row)',
		source: 'osint',
		verification_state: 'NEWS-REPORTED',
		credibility: 0.65,
		severity: 'warn',
		props: {},
	};
	const FEED = parseFeedRows({ items: [FICTIONAL_OSINT, ...capture.feed.items] });
	const feedById = new Map(capture.feed.items.map((i) => [i.id, i]));
	const SNAPSHOT = parseCitySnapshot(capture.snapshot);
	const DOSSIERS: Dossier[] = capture.dossiers
		.map((d) => parseDossier({ ...d, audit: d.audit.map((a) => (typeof a === 'string' ? feedById.get(a) : a)).filter(Boolean) }, AS_OF))
		.filter((d): d is Dossier => !!d);
	const HISTORY = parseEventHistory(historyFixture);
	const START = AS_OF - 6 * HOUR;
	const SPANS = HISTORY.filter((r) => r.span).map((r) => ({ urn: r.urn, title: r.title, start: r.span![0], end: r.span![1] }));
	/** The brushed example: 01:20–01:42 IST on the capture day (the prototype's window). */
	const BRUSHED: [number, number] = [Date.parse('2026-10-23T19:50:00Z'), Date.parse('2026-10-23T20:12:00Z')];

	// ── state from the URL ─────────────────────────────────────────────────
	const params = $derived($page.url.searchParams);
	const boxW = $derived(Number(params.get('w')) || 0);
	const boxH = $derived(Number(params.get('h')) || 0);
	const graphOnly = $derived(boxW > 0 && boxH > 0);
	const layout = $derived<LayoutMode>(params.get('layout') === 'force' ? 'force' : params.get('layout') === 'hierarchical' ? 'hierarchical' : 'radial');

	let ready = $state(false);
	onMount(() => {
		const feedBefore = fusionFeed.rows;
		cityRegistry.seed(SNAPSHOT, 'design harness: fixture data');
		dossier.seed(DOSSIERS);
		fusionFeed.rows = FEED;
		eventHistory.seed(HISTORY);
		dockState.clockOverride = AS_OF;
		dockState.size = 'full';
		workspace.bottomTab = 'timeline';
		workspace.returnToLive();
		const sel = $page.url.searchParams.get('sel');
		selection.select(sel && sel.includes(':') ? sel : VEHICLE, { source: 'map' });
		(window as unknown as Record<string, unknown>).__ANALYSIS_HARNESS__ = {
			graph: () => (window as unknown as Record<string, unknown>).__LINK_GRAPH__ ?? null,
			select: (urn: string, mode: 'replace' | 'add' | 'toggle' = 'replace') => selection.select(urn, { source: 'graph', mode }),
			linked: () => selectors.linked(VEHICLE).length,
		};
		ready = true;
		return () => {
			selection.clear();
			dossier.unseed();
			cityRegistry.unseed();
			eventHistory.unseed();
			dockState.clockOverride = null;
			if (fusionFeed.rows === FEED) fusionFeed.rows = feedBefore;
		};
	});

	const related = $derived.by(() => {
		const cur = selection.current;
		return cur ? new Set([cur, ...selection.items, ...selectors.linked(cur).map((o) => o.urn)]) : new Set<string>();
	});
	let auditFilter = $state<AuditFilter>('all');
	let aiFilter = $state<AuditFilter>('all');
	/**
	 * The capture's AI rows carry no text (the fixture keeps only what the
	 * selectors read), so the AI trace adds four FICTIONAL model rows, marked
	 * as such, to show its phase, tier and confidence columns.
	 */
	const FICTIONAL_AI = parseFeedRows({
		items: [
			{ id: 'fictional:ai-1', t: new Date(AS_OF - 41 * MIN).toISOString(), kind: 'brain', urns: [VEHICLE], actor: 'convoy-brain', actor_kind: 'machine', text: 'Pre movement: corridor holds clear of the Hindmata approach (fictional harness row)', source: 'emulated', severity: 'info', props: { phase: 'pre_movement', tier: 'decider', confidence: 0.81 } },
			{ id: 'fictional:ai-2', t: new Date(AS_OF - 33 * MIN).toISOString(), kind: 'brain', urns: [], actor: 'convoy-brain', actor_kind: 'machine', text: 'Decider checkpoint (approach): tier decider (fictional harness row)', source: 'emulated', severity: 'info', props: { phase: 'decider_checkpoint', tier: 'decider', confidence: 0.74 } },
			{ id: 'fictional:ai-3', t: new Date(AS_OF - 19 * MIN).toISOString(), kind: 'brain', urns: [], actor: 'convoy-brain', actor_kind: 'machine', text: 'Orchestrator turn: hold short of Hindmata proposed (confidence 0.66) via gemma (fictional harness row)', source: 'emulated', severity: 'warn', props: { phase: 'orchestrator_turn', tier: 'gemma', confidence: 0.66 } },
			{ id: 'fictional:ai-4', t: new Date(AS_OF - 6 * MIN).toISOString(), kind: 'brain', urns: [], actor: 'convoy-brain', actor_kind: 'machine', text: 'Decider checkpoint (release): tier tier0_cache_hit (fictional harness row)', source: 'emulated', severity: 'info', props: { phase: 'decider_checkpoint', tier: 'tier0_cache_hit', confidence: 0.9 } },
		],
	});
	const aiItems = $derived(aiTrace([...FICTIONAL_AI, ...FEED.filter((r) => r.kind === 'brain')].map((r) => itemFromFeed(r, { lang }))));

	function onselect(urn: string, mode: 'replace' | 'add' | 'toggle') {
		selection.select(urn, { source: 'graph', mode });
	}
</script>

<svelte:head><title>Analysis harness · Sajag</title></svelte:head>

{#snippet graph()}
	<LinkGraph focus={VEHICLE} selectionItems={selection.items} {layout} {onselect} window={workspace.timeWindow} {lang} />
{/snippet}

<div class="harness" class:graph-only={graphOnly} data-harness="analysis" data-ready={ready}>
	<header class="hb">
		<strong>Analysis</strong>
		<span class="muted">Haji Ali · stolen vehicle</span>
		<span class="grow"></span>
		<ProvenanceTag source="emulated" {lang} />
		<Tag icon="lab-test" tooltip="Design harness: the prototype's emulated, masked capture and the sandbox event history. Not linked from navigation.">Fixture data</Tag>
	</header>

	{#if !ready}
		<div class="wait"></div>
	{:else if graphOnly}
		<div class="box" style:width="{boxW}px" style:height="{boxH}px" data-box="graph">{@render graph()}</div>
	{:else}
		<div class="grid">
			<section class="cell graph" aria-label="Link graph">
				<div class="cap">Link graph · radial by link type · Shift-click a second object, then Find paths</div>
				<div class="fill">{@render graph()}</div>
			</section>

			<section class="cell dock-full" aria-label="Bottom dock, full and live">
				<FusionRail poll={false} />
			</section>

			<section class="cell tl-compact" aria-label="Timeline, compact">
				<div class="cap">Timeline · compact (124 px) · live</div>
				<div class="tl-body compact">
					<Timeline start={START} end={AS_OF} window={null} live={true} cursor={AS_OF} {related} density="compact" rows={FEED} onbrush={(a, b) => workspace.setTimeWindow(a, b)} oncursor={() => {}} {lang} />
				</div>
			</section>

			<section class="cell tl-brushed" aria-label="Timeline, brushed">
				<div class="cap">Timeline · full · brushed 01:20–01:42 IST · Live off</div>
				<div class="tl-body full">
					<Timeline start={START} end={AS_OF} window={BRUSHED} live={false} cursor={BRUSHED[1]} {related} density="full" rows={FEED} spans={SPANS} onbrush={() => {}} oncursor={() => {}} {lang} />
				</div>
			</section>

			<section class="cell audit" aria-label="Audit table">
				<AuditTable title="Audit" scope="city" filter={auditFilter} onfilter={(f) => (auditFilter = f)} rows={FEED} {lang} />
			</section>

			<section class="cell ai" aria-label="AI trace">
				<AuditTable title="AI trace" mode="ai" scope="city" filter={aiFilter} items={aiItems} scopes={false} onfilter={(f) => (aiFilter = f)} {lang} />
			</section>
		</div>
	{/if}
</div>

<style>
	.harness {
		position: fixed;
		inset: 0;
		z-index: 40;
		display: flex;
		flex-direction: column;
		background: var(--v-canvas);
		color: var(--v-ink-1);
		font-size: 14px;
	}

	.hb {
		display: flex;
		align-items: center;
		gap: 12px;
		flex: 0 0 auto;
		height: 40px;
		padding: 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
	}

	.muted {
		color: var(--v-ink-2);
	}

	.grow {
		flex: 1 1 auto;
	}

	.wait {
		flex: 1 1 auto;
	}

	.box {
		margin: 16px;
		border: 1px solid var(--v-line-2);
		overflow: hidden;
	}

	.grid {
		flex: 1 1 auto;
		min-height: 0;
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.12fr);
		grid-template-rows: 278px 124px 278px minmax(240px, 1fr);
		grid-template-areas:
			'graph dock'
			'graph compact'
			'graph brushed'
			'ai audit';
		gap: 1px;
		background: var(--v-line-2);
		overflow: auto;
	}

	.cell {
		position: relative;
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		background: var(--v-surface-1);
	}

	.graph {
		grid-area: graph;
		background: var(--v-canvas);
	}

	.dock-full {
		grid-area: dock;
	}

	.tl-compact {
		grid-area: compact;
	}

	.tl-brushed {
		grid-area: brushed;
	}

	.audit {
		grid-area: audit;
	}

	.ai {
		grid-area: ai;
	}

	.cap {
		flex: 0 0 auto;
		height: 24px;
		padding: 4px 16px 0;
		color: var(--v-ink-2);
		font-size: 12px;
		line-height: 16px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.fill {
		flex: 1 1 auto;
		min-height: 0;
		position: relative;
	}

	.tl-body {
		position: relative;
		flex: 1 1 auto;
		min-height: 0;
	}

	@media (max-width: 1500px) {
		.grid {
			grid-template-rows: 278px 124px 278px minmax(260px, 1fr);
		}
	}
</style>
