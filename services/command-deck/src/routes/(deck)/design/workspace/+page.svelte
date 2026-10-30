<script lang="ts">
	/**
	 * /design/workspace — the UI-S2 harness (plan R18, X16): the workspace
	 * frame, the omnibar and the inspector over FIXTURE objects, offline. Not
	 * linked from navigation; UI-S7B deletes it.
	 *
	 * Data: the committed selector fixture (tests/fixtures/workspace/
	 * captured.json — the prototype's emulated, masked capture, every person
	 * replaced by the fictional "Sandbox Officer") plus a few fictional objects
	 * for the kinds the capture lacks (a junction, a road, a unit, a convoy, a
	 * dispatch, a feed anomaly, an open-source report and its place). The real
	 * stores are seeded (cityRegistry.seed, dossier.seed): nothing is fetched,
	 * and the views read exactly what they read on a route.
	 *
	 *   ?sel=<kind|urn>   select an object (a kind picks its fixture object); sel=none clears
	 *   ?omni=<q>         open the omnibar with a query
	 *   ?providers=0      register no provider: the frame's non-ideal state
	 *   ?view=map|table   the centre view
	 *
	 * window.__WS_HARNESS__ exposes select(urn) and openOmnibar(q), each
	 * timed with performance.now() to the DOM update (the S2 budgets: a
	 * selection updates every view in < 100 ms, the omnibar opens in < 50 ms).
	 */
	import { onMount, tick } from 'svelte';
	import { page } from '$app/stores';
	import { iconPaths, kindIcon } from '$lib/design/icons';
	import { svgLabel } from '$lib/ui/format/format';
	import { DataTable, Icon, Tag, provideUiLang, type DataColumn } from '$lib/ui';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import {
		parseCitySnapshot,
		parseDossier,
		parseFeedRows,
		type CityEntity,
		type Dossier,
		type FeedRow,
	} from '$lib/gods-eye/city-api';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { dossier } from '$lib/gods-eye/entities/dossier.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { fusionFeed } from '$lib/gods-eye/hud/feed.svelte';
	import WorkspaceFrame from '$lib/workspace/components/WorkspaceFrame.svelte';
	import Omnibar from '$lib/workspace/components/omnibar/Omnibar.svelte';
	import { buildObjectGraph } from '$lib/workspace/objects';
	import { registerProviders } from '$lib/workspace/providers';
	import { resetRegistry } from '$lib/workspace/registry';
	import { kindMany, stateWord } from '$lib/workspace/kinds/generic';
	import { linkedLabel } from '$lib/workspace/selectors';
	import { liveWorld, selectors } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import type { ObjectRow } from '$lib/workspace/types';
	import capture from '../../../../../tests/fixtures/workspace/captured.json';

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);

	// ── the fixture world ──────────────────────────────────────────────────

	const AS_OF = Date.parse(capture.as_of);
	const iso = (msOffset: number) => new Date(AS_OF + msOffset).toISOString();
	const PURSUIT = (capture.dossiers[0].related.find((r) => r.entity.kind === 'event')?.entity.id as string) ?? '';
	const OSINT_ID = '6f1c2a9e-3b7d-4e21-9a55-0c8e7d4b1f20';
	const DISPATCH_ID = '2d4b8f61-7a3c-4c19-b0e2-91f5a6c3d7e8';

	/** Fictional objects for the kinds the capture lacks (no person, no raw mark). */
	const EXTRAS: Record<string, unknown>[] = [
		{ urn: 'junction:15', kind: 'junction', id: '15', label: 'Hindmata', lon: 72.8607, lat: 19.0021, state: 'planned_green', source: 'live', t: iso(-40_000), links: ['segment:1049'], props: { name: 'Hindmata', name_mr: 'हिंदमाता', junction_type: 'roundabout', signal_control: true, program_source: 'osm_assumed', cycle_sec: 110, offset_sec: 17, green_ratio: 0.42, active_phase: { index: 1, remaining_sec: 31 }, phase_basis: 'program_clock', phase_status: 'planned (signal program)', live_phase: false } },
		{ urn: 'segment:1049', kind: 'segment', id: '1049', label: 'Dr Ambedkar Road (Parel flyover)', lon: 72.8584, lat: 19.0033, state: 'flowing', source: 'live', t: null, links: [], props: { road_name: 'Dr Ambedkar Road (Parel flyover)', road_class: 'secondary', lanes: 2, speed_limit_kmh: 40, oneway: false, length_m: 640, speed_kmh: 23, congestion_idx: 0.46, data_quality: 'synthetic' } },
		{ urn: 'segment:1045', kind: 'segment', id: '1045', label: 'LBS Marg', lon: 72.7695, lat: 19.0329, state: 'flowing', source: 'live', t: null, links: [], props: { road_name: 'LBS Marg', road_class: 'trunk', lanes: 4, speed_limit_kmh: 60, oneway: false, length_m: 1180, speed_kmh: 31, congestion_idx: 0.38, data_quality: 'synthetic' } },
		{ urn: 'unit:PCR-12', kind: 'unit', id: 'PCR-12', label: 'Police PCR 12', lon: 72.8553, lat: 19.0079, state: 'patrol', source: 'emulated', t: iso(-20_000), links: [], props: { agency: 'police', agency_label: 'Police', unit_source: 'emulated', progress: 0.4, eta_sec: 210, waypoint_junction: 15 } },
		{ urn: 'convoy:mv-demo', kind: 'convoy', id: 'mv-demo', label: 'VVIP convoy · Z', lon: 72.8509, lat: 19.0106, state: 'active', source: 'emulated', t: iso(-5_000), links: [], props: { movement_id: 'mv-demo', speed_kmh: 38, heading: 64, progress: 0.31, position_source: 'emulated_gps' } },
		{ urn: `dispatch:${DISPATCH_ID}`, kind: 'dispatch', id: DISPATCH_ID, label: 'Police · PCR-12', lon: 72.8607, lat: 19.0021, state: 'requested', source: 'live', t: iso(-6 * 60_000), links: PURSUIT ? [`event:${PURSUIT}`, 'junction:15', 'unit:PCR-12'] : ['junction:15', 'unit:PCR-12'], props: { agency: 'police', agency_label: 'Police', unit_id: 'PCR-12', unit_emulated: true, status: 'requested', event_id: PURSUIT || null, waypoint_junction: 15, requested_by: 'Sandbox Officer', created_at: iso(-6 * 60_000), event_title: 'PURSUIT — stolen MH47EM•••1 (FIR 4401/2026, Azad Maidan PS)', eta_sec: 240 } },
		{ urn: 'anomaly:7622', kind: 'anomaly', id: '7622', label: 'speed_jump · medium', lon: 72.8327, lat: 18.9967, state: 'medium', source: 'live', t: iso(-30_000), links: [], props: { anomaly_type: 'speed_jump', severity: 'medium', segment_id: 1036, road_name: 'Eastern Metropolitan Bypass', count_15m: 3, anomaly_flags: ['speed_jump', 'speed_zscore'], data_quality: 'synthetic' } },
		{ urn: `osint_event:${OSINT_ID}`, kind: 'osint_event', id: OSINT_ID, label: 'Road accident · BKC connector', lon: 72.7701, lat: 19.0335, state: 'surfaced', source: 'osint', verification_state: 'NEWS-REPORTED', credibility: 0.65, t: iso(-35 * 60_000), links: ['place:bkc_connector', 'segment:1045'], props: { event_class: 'road_accident', sajag_event_kind: 'road_accident', toponym: 'BKC connector', segment_id: 1045, window_start: iso(-48 * 60_000), window_end: iso(-35 * 60_000), source_count: 2, independent_publishers: 2, summary: 'Two-vehicle collision reported near Sector V; traffic slow towards Sola.', labels: ['NEWS-REPORTED'] } },
		{ urn: 'place:bkc_connector', kind: 'place', id: 'bkc_connector', label: 'BKC connector', lon: 72.7701, lat: 19.0335, state: null, source: 'osint', t: iso(-35 * 60_000), links: [`osint_event:${OSINT_ID}`], props: { feature_type: 'road', canonical_name: 'BKC connector', segment_id: 1045, osint_event_count: 1 } },
	];

	/** The feed rows (a dossier audit entry that is a string is a feed row's id). */
	const FEED: FeedRow[] = parseFeedRows({ items: capture.feed.items });
	const feedById = new Map(capture.feed.items.map((i) => [i.id, i]));

	function buildFixture(): { entities: CityEntity[]; dossiers: Dossier[] } {
		const snap = parseCitySnapshot({ ...capture.snapshot, entities: [...capture.snapshot.entities, ...EXTRAS] });
		const real: Dossier[] = capture.dossiers
			.map((d) => parseDossier({ ...d, audit: d.audit.map((a) => (typeof a === 'string' ? feedById.get(a) : a)).filter(Boolean) }, AS_OF))
			.filter((d): d is Dossier => !!d);
		// every other object gets a dossier from the fixture's own graph (links named from both ends, its feed rows)
		const byUrn = new Map<string, CityEntity>();
		for (const e of snap.entities) byUrn.set(e.urn, e);
		for (const d of real) {
			byUrn.set(d.entity.urn, byUrn.get(d.entity.urn) ?? d.entity);
			for (const r of d.related) if (!byUrn.has(r.entity.urn)) byUrn.set(r.entity.urn, r.entity);
		}
		const graph = buildObjectGraph({ entities: snap.entities, dossiers: real });
		const have = new Set(real.map((d) => d.entity.urn));
		const synthetic: Dossier[] = [];
		for (const [urn, entity] of byUrn) {
			if (have.has(urn)) continue;
			const related = graph
				.links(urn)
				.map((l) => ({ relation: l.relation, entity: byUrn.get(l.row.urn) }))
				.filter((r): r is { relation: string; entity: CityEntity } => !!r.entity);
			const audit = FEED.filter((f) => f.urns.includes(urn)).slice(0, 60);
			synthetic.push({ entity, related, audit, fetchedAt: AS_OF });
		}
		return { entities: snap.entities, dossiers: [...real, ...synthetic] };
	}

	const fixture = buildFixture();
	const VEHICLE = capture.vehicle;

	/** A kind's fixture object (?sel=vehicle …): the vehicle's own objects first. */
	function pickOf(kind: string): string | null {
		if (kind === 'vehicle') return VEHICLE;
		if (kind === 'event') return PURSUIT ? `event:${PURSUIT}` : null;
		if (kind === 'recommendation') {
			const recs = fixture.dossiers[0].related.filter((r) => r.entity.kind === 'recommendation').map((r) => r.entity);
			return (recs.find((e) => e.state === 'pending') ?? recs[0])?.urn ?? null;
		}
		const first = [...fixture.entities, ...fixture.dossiers.flatMap((d) => d.related.map((r) => r.entity))].find((e) => e.kind === kind);
		return first?.urn ?? null;
	}

	// ── state from the URL ─────────────────────────────────────────────────

	const params = $derived($page.url.searchParams);
	const providersOn = $derived(params.get('providers') !== '0');

	let ready = $state(false);
	const perf = { select: [] as number[], omni: [] as number[] };

	async function timedSelect(urn: string | null, opts: { mode?: 'replace' | 'add' | 'toggle'; source?: 'map' | 'table' | 'omnibar' } = {}) {
		const t0 = performance.now();
		if (urn) selection.select(urn, { source: opts.source ?? 'map', mode: opts.mode });
		else selection.clear();
		await tick();
		const ms = performance.now() - t0;
		perf.select.push(Math.round(ms * 100) / 100);
		return ms;
	}

	async function timedOmnibar(q: string) {
		const t0 = performance.now();
		workspace.openOmnibar(q);
		await tick();
		const ms = performance.now() - t0;
		perf.omni.push(Math.round(ms * 100) / 100);
		return { ms, rows: document.querySelectorAll('[data-testid="command-palette"] [role="option"]').length };
	}

	onMount(() => {
		const p = $page.url.searchParams;
		if (p.get('providers') === '0') resetRegistry();
		else registerProviders();
		const feedBefore = fusionFeed.rows;
		cityRegistry.seed({ asOf: AS_OF, entities: fixture.entities, feeds: {}, tookMs: null }, 'design harness: fixture data');
		dossier.seed(fixture.dossiers);
		fusionFeed.rows = FEED;
		workspace.docks = { left: false, right: p.get('providers') !== '0', bottom: 'compact' };
		const v = p.get('view');
		if (v === 'map' || v === 'table') workspace.view = v;
		const sel = p.get('sel');
		const urn = sel === 'none' ? null : sel ? (sel.includes(':') ? sel : pickOf(sel)) : VEHICLE;
		if (urn) {
			selection.select(urn, { source: 'map' });
			workspace.rightTab = 'inspector';
		}
		const omni = p.get('omni');
		if (omni != null) void timedOmnibar(omni);
		(window as unknown as Record<string, unknown>).__WS_HARNESS__ = {
			perf,
			select: timedSelect,
			openOmnibar: timedOmnibar,
			pick: pickOf,
			counts: () => ({ linked: selectors.linked(VEHICLE).length, objectSet: workspace.objectSet.length }),
		};
		ready = true;
		// leaving the harness (an SPA navigation): no fixture outlives it and nothing stays offline
		return () => {
			workspace.closeOmnibar();
			selection.clear();
			dossier.unseed();
			cityRegistry.unseed();
			if (fusionFeed.rows === FEED) fusionFeed.rows = feedBefore;
		};
	});

	// ── the schematic map (harness only: fixture positions on a plain ground) ─

	let mapW = $state(800);
	let mapH = $state(600);
	const graph = $derived(liveWorld.graph());
	const placed = $derived(graph.all().filter((r) => r.lon != null && r.lat != null));
	/** Fit to the selection and its linked objects when there is one (a map follows its subject), else everything. */
	const framed = $derived.by(() => {
		if (!selection.current) return placed;
		const scope = new Set([selection.current, ...selectors.linked(selection.current).map((r) => r.urn)]);
		const sub = placed.filter((r) => scope.has(r.urn));
		return sub.length >= 2 ? sub : placed;
	});
	const bounds = $derived.by(() => {
		const lons = framed.map((r) => r.lon as number);
		const lats = framed.map((r) => r.lat as number);
		if (!lons.length) return { x0: 72.7623, x1: 72.9623, y0: 18.9332, y1: 19.085 };
		const pad = 0.002;
		return { x0: Math.min(...lons) - pad, x1: Math.max(...lons) + pad, y0: Math.min(...lats) - pad, y1: Math.max(...lats) + pad };
	});
	const project = (r: ObjectRow) => {
		const b = bounds;
		const kx = (mapW - 80) / Math.max(1e-6, b.x1 - b.x0);
		const ky = (mapH - 80) / Math.max(1e-6, b.y1 - b.y0);
		const k = Math.min(kx, ky);
		const ox = (mapW - (b.x1 - b.x0) * k) / 2;
		const oy = (mapH - (b.y1 - b.y0) * k) / 2;
		return { x: ox + ((r.lon as number) - b.x0) * k, y: oy + (b.y1 - (r.lat as number)) * k };
	};
	const focus = $derived(new Set([...(selection.current ? [selection.current] : []), ...selection.items]));
	const near = $derived(new Set(selection.current ? selectors.linked(selection.current).map((r) => r.urn) : []));
	const glyph = (r: ObjectRow) => iconPaths(r.kind === 'event' ? r.icon : kindIcon(r.kind), 16);
	/** The selected vehicle's latest pass (its reads within 30 min of the newest, in time order), as the map draws it. */
	const track = $derived.by(() => {
		const cur = selection.current ? graph.get(selection.current) : null;
		if (cur?.kind !== 'vehicle') return '';
		const reads = selectors.reads(cur.urn).filter((r) => r.lon != null && r.lat != null);
		const newest = reads[reads.length - 1]?.t ?? 0;
		return reads
			.filter((r) => (r.t ?? 0) >= newest - 30 * 60_000)
			.map((r) => project(r))
			.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
			.join(' ');
	});
	/** Cameras linked to the selection carry their id. */
	const labelled = $derived(placed.filter((r) => r.kind === 'camera' && near.has(r.urn)));
	const inFrame = (p: { x: number; y: number }) => p.x > -40 && p.y > -40 && p.x < mapW + 40 && p.y < mapH + 40;

	// ── the table (harness only: the object set, as S2X's ObjectTable will read it) ─

	const rows = $derived(workspace.objectSet);
	const columns: DataColumn<ObjectRow>[] = [
		// the 32 px glyph column draws the row's kind glyph (a column without a render shows its value as text)
		{ key: 'icon', icon: true, render: glyphCell },
		{ key: 'label', title: 'Object', minWidth: 160 },
		{ key: 'kind', title: 'Type', width: 140, format: (_v, r) => kindMany(r.kind, 'en') },
		{ key: 'state', title: 'State', width: 130, format: (_v, r) => stateWord(r.state, 'en') ?? '—' },
		{ key: 't', title: 'Time (IST)', width: 120, time: { anchor: AS_OF } },
		{ key: 'sublabel', title: 'Detail', minWidth: 140, format: (v) => (typeof v === 'string' ? v : '—') },
	];
	const tableTitle = $derived(
		selection.current && graph.get(selection.current) ? `${graph.get(selection.current)?.label} and its ${linkedLabel(selectors.linked(selection.current).length, lang)} objects` : 'Every object',
	);

	// the pane header names the fixture honestly
	const title = 'Haji Ali · stolen vehicle';
</script>

{#snippet glyphCell(r: ObjectRow)}<Icon name={r.icon} />{/snippet}

<svelte:head><title>Workspace harness · Sajag</title></svelte:head>

<div class="harness" data-harness="workspace" data-ready={ready}>
	<WorkspaceFrame route="/" {title}>
		{#snippet headerRight()}<Tag icon="lab-test" tooltip="Design harness: the prototype's emulated, masked capture and fictional objects">Fixture data</Tag>{/snippet}
		{#snippet map()}
			<div class="schematic" bind:clientWidth={mapW} bind:clientHeight={mapH}>
				<svg width={mapW} height={mapH} role="img" aria-label="Schematic map of the fixture objects">
					<defs>
						<pattern id="ws-grid" width="48" height="48" patternUnits="userSpaceOnUse">
							<path d="M 48 0 L 0 0 0 48" class="gridline" />
						</pattern>
					</defs>
					<rect width={mapW} height={mapH} fill="url(#ws-grid)" />
					{#if track}
						<path d={track} class="track-casing" />
						<path d={track} class="track" />
					{/if}
					{#each placed as r (r.urn)}
						{@const p = project(r)}
						{@const g = glyph(r)}
						{@const sel = focus.has(r.urn)}
						<!-- svelte-ignore a11y_click_events_have_key_events -->
						<g
							class="mk"
							class:dim={selection.current && !sel && !near.has(r.urn)}
							class:alert={r.kind === 'vehicle'}
							class:sel
							transform="translate({p.x},{p.y})"
							role="button"
							tabindex="-1"
							aria-label={r.label}
							data-urn={r.urn}
							onclick={(e) => void timedSelect(r.urn, { mode: e.shiftKey ? 'add' : 'replace' })}
						>
							{#if sel}<circle r="17" class="halo" />{/if}
							<circle r="10.5" class="disc" />
							<g transform="translate(-6,-6) scale({12 / g.grid})">{#each g.paths as d, i (i)}<path {d} fill-rule="evenodd" class="glyph" />{/each}</g>
						</g>
					{/each}
					{#each labelled as r (r.urn)}
						{@const p = project(r)}
						{#if inFrame(p)}
							<g class="mlabel" transform="translate({p.x + 14},{p.y + 4})">
								<rect x="-3" y="-13" width={r.id.length * 7.6 + 6} height="18" rx="2" />
								<text>{@html svgLabel([{ id: r.id }])}</text>
							</g>
						{/if}
					{/each}
				</svg>
				<span class="caption">Schematic · fixture positions</span>
			</div>
		{/snippet}
		{#snippet table()}
			<div class="tbl">
				<div class="tbl-head"><span class="tt">{tableTitle}</span><span class="n">{rows.length === 1 ? '1 row' : `${rows.length} rows`}</span></div>
				<DataTable
					{columns}
					{rows}
					rowKey={(r: ObjectRow) => r.urn}
					selected={selection.items}
					density="compact"
					onselect={(_k, r, e) => void timedSelect(r.urn, { source: 'table', mode: e.ctrlKey || e.metaKey ? 'toggle' : e.shiftKey ? 'add' : 'replace' })}
				/>
			</div>
		{/snippet}
	</WorkspaceFrame>
	<Omnibar />
</div>

<style>
	.harness {
		position: fixed;
		inset: 0;
		z-index: 40;
		background: var(--v-canvas);
	}

	.schematic {
		position: absolute;
		inset: 0;
		background: var(--v-surface-sink);
	}

	.schematic svg {
		display: block;
	}

	.gridline {
		fill: none;
		stroke: var(--v-line-1);
		stroke-width: 1;
	}

	.mk {
		cursor: pointer;
	}

	.mk .disc {
		fill: var(--v-map-marker-fill);
		stroke: var(--v-map-marker);
		stroke-width: 1.5;
	}

	.mk.alert .disc {
		stroke: var(--v-map-alert);
		stroke-width: 2;
	}

	.mk .glyph {
		fill: var(--v-ink-1);
	}

	.mk.sel .disc {
		stroke: var(--v-map-select);
		stroke-width: 2.5;
	}

	.mk .halo {
		fill: color-mix(in srgb, var(--v-map-select) 30%, transparent);
	}

	.mk.dim {
		opacity: 0.35;
	}

	.track-casing {
		fill: none;
		stroke: var(--v-map-casing);
		stroke-width: 7;
		stroke-linejoin: round;
		stroke-linecap: round;
	}

	.track {
		fill: none;
		stroke: var(--v-map-alert);
		stroke-width: 3;
		stroke-linejoin: round;
		stroke-linecap: round;
	}

	.mlabel rect {
		fill: var(--v-map-label-bg);
	}

	.mlabel text {
		font-size: 12px;
		fill: var(--v-map-label-ink);
	}

	.caption {
		position: absolute;
		left: 8px;
		bottom: 8px;
		padding: 2px 6px;
		border-radius: var(--v-radius-chip);
		background: var(--v-map-label-bg);
		color: var(--v-ink-2);
		font-size: 12px;
	}

	.tbl {
		display: flex;
		flex-direction: column;
		position: absolute;
		inset: 0;
		overflow: hidden;
	}

	.tbl-head {
		display: flex;
		align-items: center;
		gap: 12px;
		height: 40px;
		padding: 0 16px;
		border-bottom: 1px solid var(--v-line-1);
		flex: 0 0 auto;
	}

	.tt {
		font-weight: 600;
	}

	.n {
		font-size: 12px;
		color: var(--v-ink-2);
	}
</style>
