<script lang="ts">
	/**
	 * /design/views — the UI-S2X harness (plan R18, X16): the Explorer, the
	 * Histogram, the ObjectTable and the City vitals (card and Info tab) over
	 * FIXTURE objects, offline, inside the real workspace frame. Not linked
	 * from navigation; UI-S7B deletes it.
	 *
	 * Data: the committed selector fixture (tests/fixtures/workspace/
	 * captured.json — the prototype's emulated, masked capture, every person
	 * the fictional "Sandbox Officer") plus fictional objects of mixed
	 * provenance: a live junction, a simulated road and anomaly, an emulated
	 * procession (open, band Amber), an open pursuit of the vehicle (protected:
 * it never fades), a live dispatch request, two open-source
	 * reports (news-reported and unverified) and their place, and a rehearsal
	 * event (Test). The real stores are seeded (cityRegistry.seed,
	 * dossier.seed, cityVitals.seed): nothing is fetched, no poller starts.
	 *
	 *   ?left=explorer|histogram|info|none   the left dock's tab (default
	 *                                        explorer; histogram with ?brush)
	 *   ?sel=<kind|urn|none>                 the selection (default the vehicle)
	 *   ?brush=0120-0142                     a time window (IST, the fixture's day)
	 *   ?kinds=vehicle,sighting,…            a kind filter (as the Explorer or the
	 *                                        Histogram would add it)
	 *   ?mode=card|info                      a City vitals variant: the map-mode
	 *                                        card over a schematic map, or the
	 *                                        Info tab in the left dock
	 *   ?rows=500                            a synthetic table of n rows
	 *                                        (fictional ids), to time scrolling
	 *   ?standalone=explorer                 the Explorer alone, with an
	 *                                        `activeEvents` snippet filled
	 *
	 * window.__VIEWS_HARNESS__: scrollTest() scrolls the table end to end on
	 * animation frames and returns the frame times and how many rows were in
	 * the DOM (the table virtualises past 200); csv() returns the export of
	 * the rows in the table; counts() the Explorer's and the card's figures
	 * and the rows the table and the Histogram each hold (always equal).
	 */
	import { onMount, tick } from 'svelte';
	import { page } from '$app/stores';
	import { iconPaths, kindIcon } from '$lib/design/icons';
	import { istTimeToMs } from '$lib/ui/format/format';
	import { Icon, ProvenanceTag, Tag, provideUiLang } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.views';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { parseCitySnapshot, parseDossier, parseFeedRows, type CityEntity, type Dossier, type FeedRow } from '$lib/gods-eye/city-api';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { dossier } from '$lib/gods-eye/entities/dossier.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { fusionFeed } from '$lib/gods-eye/hud/feed.svelte';
	import { cityVitals } from '$lib/gods-eye/hud/vitals.svelte';
	import CityVitals from '$lib/gods-eye/hud/CityVitals.svelte';
	import WorkspaceFrame from '$lib/workspace/components/WorkspaceFrame.svelte';
	import Explorer from '$lib/workspace/components/explorer/Explorer.svelte';
	import Histogram from '$lib/workspace/components/histogram/Histogram.svelte';
	import ObjectTable from '$lib/workspace/components/table/ObjectTable.svelte';
	import { toCsv } from '$lib/workspace/components/table/csv';
	import { tableScope } from '$lib/workspace/components/table/scope.svelte';
	import { currentView } from '$lib/workspace/components/explorer/current-view.svelte';
	import { buildObjectGraph } from '$lib/workspace/objects';
	import { registerProviders } from '$lib/workspace/providers';
	import { registerDecisionUnits, registerLeftTab, resetRegistry } from '$lib/workspace/registry';
	import { liveWorld, selectors } from '$lib/workspace/world.svelte';
	import { kindOne } from '$lib/workspace/kinds/generic';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import type { ObjectRow } from '$lib/workspace/types';
	import capture from '../../../../../tests/fixtures/workspace/captured.json';

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	// ── the fixture world ──────────────────────────────────────────────────

	const AS_OF = Date.parse(capture.as_of);
	const iso = (msOffset: number) => new Date(AS_OF + msOffset).toISOString();
	const VEHICLE = capture.vehicle;
	const MIN = 60_000;
	const PROCESSION = '3f2a6c1e-9b4d-4f7a-8c21-5d6e7f8a9b01';
	const REHEARSAL = '4a3b7d2f-0c5e-4a8b-9d32-6e7f8a9b0c12';
	const DISPATCH = '5b4c8e30-1d6f-4b9c-8e43-7f8a9b0c1d23';
	const NEWS = '6c5d9f41-2e70-4cad-9f54-8a9b0c1d2e34';
	const SOCIAL = '7d6e0a52-3f81-4dbe-8a65-9b0c1d2e3f45';
	const PURSUIT = '8e7f1b63-4a92-4ecf-9b76-0c1d2e3f4a56';
	const istIso = (hhmm: string) => new Date(istTimeToMs(hhmm, AS_OF)).toISOString();

	/** Fictional objects of mixed provenance (no person, no raw mark, no real name). */
	const EXTRAS: Record<string, unknown>[] = [
		{ urn: 'junction:15', kind: 'junction', id: '15', label: 'Hindmata', lon: 72.8607, lat: 19.0021, state: 'planned_green', source: 'live', t: iso(-40_000), links: ['segment:1049'], props: { name: 'Hindmata', junction_type: 'roundabout', signal_control: true } },
		{ urn: 'segment:1049', kind: 'segment', id: '1049', label: 'Dr Ambedkar Road (Parel flyover)', lon: 72.8584, lat: 19.0033, state: 'flowing', source: 'live', t: null, links: [], props: { road_name: 'Dr Ambedkar Road (Parel flyover)', road_class: 'secondary', lanes: 2, speed_kmh: 23, data_quality: 'synthetic' } },
		{ urn: 'segment:1045', kind: 'segment', id: '1045', label: 'LBS Marg', lon: 72.7695, lat: 19.0329, state: 'flowing', source: 'live', t: null, links: [], props: { road_name: 'LBS Marg', road_class: 'trunk', lanes: 4, speed_kmh: 31, data_quality: 'synthetic' } },
		{ urn: 'anomaly:7622', kind: 'anomaly', id: '7622', label: 'speed_jump · medium', lon: 72.8327, lat: 18.9967, state: 'medium', source: 'live', t: iso(-6 * MIN), links: [], props: { anomaly_type: 'speed_jump', severity: 'medium', road_name: 'Eastern Metropolitan Bypass', count_15m: 3, data_quality: 'synthetic' } },
		{ urn: `event:${PROCESSION}`, kind: 'event', id: PROCESSION, label: 'Procession · Lalbaug (Emulated)', lon: 72.8490, lat: 19.0064, state: 'active', band: 'AMBER', source: 'emulated', t: iso(-95 * MIN), links: ['segment:1049'], props: { event_kind: 'procession', status: 'active', band_t: iso(-30_000), simulated_feed: true } },
		{ urn: `event:${REHEARSAL}`, kind: 'event', id: REHEARSAL, label: 'TIER-0 GATE TEST · VVIP movement to airport', lon: 72.8888, lat: 19.0566, state: 'completed', source: 'live', t: iso(-26 * 60 * MIN), links: [], props: { event_kind: 'protected_movement', status: 'completed' } },
		// an open pursuit of the vehicle (a protected object: it never fades, whatever the window)
		{ urn: `event:${PURSUIT}`, kind: 'event', id: PURSUIT, label: 'Pursuit of MH47EM•••1 (Emulated)', lon: 72.8553, lat: 19.0079, state: 'active', source: 'emulated', t: istIso('01:05'), links: [VEHICLE], props: { event_kind: 'vehicle_pursuit', status: 'active' } },
		{ urn: `dispatch:${DISPATCH}`, kind: 'dispatch', id: DISPATCH, label: 'Police · PCR-12', lon: 72.8607, lat: 19.0021, state: 'requested', source: 'live', t: iso(-6 * MIN), links: ['junction:15'], props: { agency: 'police', unit_id: 'PCR-12', status: 'requested', waypoint_junction: 15, requested_by: 'Sandbox Officer' } },
		{ urn: `osint_event:${NEWS}`, kind: 'osint_event', id: NEWS, label: 'Road accident · BKC connector', lon: 72.7701, lat: 19.0335, state: 'surfaced', source: 'osint', verification_state: 'NEWS-REPORTED', credibility: 0.65, t: iso(-35 * MIN), links: ['place:bkc_connector', 'segment:1045'], props: { event_class: 'road_accident', toponym: 'BKC connector', segment_id: 1045, window_start: iso(-48 * MIN), window_end: iso(-35 * MIN), source_count: 2, labels: ['NEWS-REPORTED'], synthetic: true } },
		{ urn: `osint_event:${SOCIAL}`, kind: 'osint_event', id: SOCIAL, label: 'Waterlogging · Hindmata', lon: 72.8284, lat: 18.9940, state: 'surfaced', source: 'osint', verification_state: 'UNVERIFIED-OSINT', credibility: 0.35, t: iso(-22 * MIN), links: [], props: { event_class: 'flooding', toponym: 'Hindmata', window_start: iso(-30 * MIN), window_end: iso(-22 * MIN), source_count: 3, labels: ['UNVERIFIED-OSINT'], synthetic: true } },
		{ urn: 'place:bkc_connector', kind: 'place', id: 'bkc_connector', label: 'BKC connector', lon: 72.7701, lat: 19.0335, state: null, source: 'osint', t: iso(-35 * MIN), links: [`osint_event:${NEWS}`], props: { feature_type: 'road', canonical_name: 'BKC connector', segment_id: 1045 } },
	];

	/** The feed rows (a dossier audit entry that is a string is a feed row's id). */
	const FEED: FeedRow[] = parseFeedRows({ items: capture.feed.items });
	const feedById = new Map(capture.feed.items.map((i) => [i.id, i]));

	function buildFixture(): { entities: CityEntity[]; dossiers: Dossier[] } {
		const snap = parseCitySnapshot({ ...capture.snapshot, entities: [...capture.snapshot.entities, ...EXTRAS] });
		const real: Dossier[] = capture.dossiers
			.map((d) => parseDossier({ ...d, audit: d.audit.map((a) => (typeof a === 'string' ? feedById.get(a) : a)).filter(Boolean) }, AS_OF))
			.filter((d): d is Dossier => !!d);
		// every other object gets a dossier from the fixture's own graph (links named from both ends)
		const byUrn = new Map<string, CityEntity>();
		for (const e of snap.entities) byUrn.set(e.urn, e);
		for (const d of real) for (const r of d.related) if (!byUrn.has(r.entity.urn)) byUrn.set(r.entity.urn, r.entity);
		const graph = buildObjectGraph({ entities: snap.entities, dossiers: real });
		const have = new Set(real.map((d) => d.entity.urn));
		const synthetic: Dossier[] = [];
		for (const [urn, entity] of byUrn) {
			if (have.has(urn)) continue;
			const related = graph
				.links(urn)
				.map((l) => ({ relation: l.relation, entity: byUrn.get(l.row.urn) }))
				.filter((r): r is { relation: string; entity: CityEntity } => !!r.entity);
			synthetic.push({ entity, related, audit: FEED.filter((f) => f.urns.includes(urn)).slice(0, 60), fetchedAt: AS_OF });
		}
		return { entities: snap.entities, dossiers: [...real, ...synthetic] };
	}

	const fixture = buildFixture();

	/** A kind's fixture object (?sel=camera …): the vehicle's own objects first. */
	function pickOf(kind: string): string | null {
		if (kind === 'vehicle') return VEHICLE;
		const first = [...fixture.entities, ...fixture.dossiers.flatMap((d) => d.related.map((r) => r.entity))].find((e) => e.kind === kind);
		return first?.urn ?? null;
	}

	/** n synthetic rows of mixed kinds and provenance (fictional ids; the scroll-timing table). */
	function syntheticRows(n: number): ObjectRow[] {
		const out: ObjectRow[] = [];
		const uuid = (i: number) => `00000000-0000-4000-8000-${String(i).padStart(12, '0')}`;
		for (let i = 0; i < n; i++) {
			const k = i % 5;
			const kind = ['sighting', 'camera', 'recommendation', 'anomaly', 'osint_event'][k];
			const cam = `SYN-CAM-${String(i % 40).padStart(2, '0')}`;
			const id = kind === 'camera' ? `${cam}-${i}` : kind === 'anomaly' ? String(90_000 + i) : uuid(i);
			const source = kind === 'osint_event' ? 'osint' : kind === 'anomaly' ? 'simulated' : i % 11 === 0 ? 'live' : 'emulated';
			const road = `Synthetic road ${i % 25}`;
			out.push({
				urn: `${kind}:${id}`,
				kind,
				id,
				label: kind === 'recommendation' ? `Speed sighting · ${cam}` : kind === 'osint_event' ? `Road accident · ${road}` : kind === 'anomaly' ? `Speed jump · ${road}` : cam,
				sublabel: road,
				icon: kindIcon(kind),
				state: kind === 'recommendation' ? (i % 3 ? 'rejected' : 'pending') : kind === 'camera' ? 'active' : null,
				stateIntent: kind === 'recommendation' && !(i % 3) ? 'warning' : 'none',
				t: AS_OF - i * 2 * MIN,
				end: null,
				lon: 72.76 + (i % 50) / 500,
				lat: 23 + (i % 40) / 500,
				source,
				verification: kind === 'osint_event' ? (i % 2 ? 'NEWS-REPORTED' : 'UNVERIFIED-OSINT') : null,
				credibility: kind === 'osint_event' ? 0.5 : null,
				test: false,
				masked: false,
				props: { road_name: road, camera_id: cam, speed_kmh: 30 + (i % 70), synthetic: true },
			} as ObjectRow);
		}
		return out;
	}

	// ── state from the URL ─────────────────────────────────────────────────

	const params = $derived($page.url.searchParams);
	const mode = $derived(params.get('mode'));
	const standalone = $derived(params.get('standalone') === 'explorer');
	const synthetic = $derived.by(() => {
		const n = Number(params.get('rows'));
		return Number.isFinite(n) && n > 0 ? syntheticRows(Math.min(2000, Math.floor(n))) : null;
	});

	let ready = $state(false);

	/** Seed this browser's saved views and watches once (fictional names; masked by the store). */
	function seedViews() {
		if (workspace.savedViews.length) return;
		const save = (name: string, setup: () => void) => {
			setup();
			workspace.saveView(name);
		};
		save('Feed anomalies, last 15 min', () => {
			selection.clear();
			workspace.addFilter({ field: 'kind', values: ['anomaly'], label: 'Feed anomaly' });
			workspace.view = 'table';
		});
		workspace.clearFilters();
		save('City overview', () => {
			selection.clear();
			workspace.view = 'map';
		});
		save('Visarjan corridor', () => selection.select(`event:${PROCESSION}`, { source: 'share' }));
		save('Haji Ali · stolen vehicle', () => {
			selection.select(VEHICLE, { source: 'share' });
			workspace.view = 'table';
		});
		if (!workspace.watches.length) {
			workspace.addWatch({ title: 'MH47EM•••1', subjectUrn: VEHICLE, filters: [] });
			workspace.addWatch({ title: 'Feed anomalies', subjectUrn: null, filters: [{ id: 'seed', field: 'kind', values: ['anomaly'], label: 'Feed anomaly' }] });
		}
	}

	onMount(() => {
		const p = $page.url.searchParams;
		const feedBefore = fusionFeed.rows;
		// no poller over the fixtures: the vitals store is seeded BEFORE any CityVitals mounts (it renders once ready)
		cityVitals.seed({
			ingest: { enabled: true, connected: true, subscribed: true, msgsPerMin: 42, lastMsgAgeSec: 2, emulatedLastMsgAgeSec: 3, rowsWritten5m: 210, subjects: [] },
			brain: { decider: 'connected', deciderDegraded: false, deciderDegradedReason: null, p95Ms: 2300, noveltyLatch: 'armed', tier0Cache: 'enabled', gemma: 'connected', status: 'ok' },
			retention: { defaultRetentionDays: 30, earmarkCapDays: 90, healthy: true, consecutiveFailures: 0, lastReap: { ran: true, removed: 3, failed: false, reason: null }, lastSuccessAt: Date.now() - 42 * MIN, due: false, policy: 'dpdp' },
			runs: [{ runId: 30, useCaseId: 'anpr_sweep', status: 'completed', clockScale: 1, createdAt: AS_OF - 3 * 3600_000, endedAt: AS_OF - 2 * 3600_000, isReplay: false, progress: null }],
			livingCity: { enabled: true, status: 'on', activeSlots: 4, nextCause: null },
		});
		cityRegistry.seed({ asOf: AS_OF, entities: fixture.entities, feeds: {}, tookMs: 84 }, 'design harness: fixture data');
		dossier.seed(fixture.dossiers);
		fusionFeed.rows = FEED;

		resetRegistry();
		registerProviders();
		registerLeftTab({ id: 'explorer', label: 'vw_tab_explorer', icon: 'diagram-tree', component: Explorer, order: 10 });
		registerLeftTab({ id: 'histogram', label: 'vw_tab_histogram', icon: 'horizontal-bar-chart', component: Histogram, order: 30 });
		registerLeftTab({ id: 'info', label: 'vw_tab_info', icon: 'info-sign', component: CityVitals, order: 50 });
		// the stolen-vehicle sightings as one waiting decision (S5A registers the real units): it protects the vehicle
		registerDecisionUnits(
			() => [{ kind: 'stolen_sightings', id: VEHICLE, subjectUrn: VEHICLE, title: 'Authorise pursuit of MH47EM•••1', deadline: null, severity: 2, homes: { '/': 'inbox', '/gods-eye': 'inbox', '/ops': 'decisions' } }],
			{ id: 'design-views' },
		);

		seedViews();
		workspace.clearFilters();
		workspace.returnToLive();

		const sel = p.get('sel');
		const urn = sel === 'none' ? null : sel ? (sel.includes(':') ? sel : pickOf(sel)) : VEHICLE;
		if (urn) selection.select(urn, { source: 'share' });
		else selection.clear();
		const current = workspace.savedViews.find((v) => v.name === (urn === VEHICLE ? 'Haji Ali · stolen vehicle' : 'City overview'));

		const brush = /^(\d{2})(\d{2})-(\d{2})(\d{2})$/.exec(p.get('brush') ?? '');
		if (brush) workspace.setTimeWindow(istTimeToMs(`${brush[1]}:${brush[2]}`, AS_OF), istTimeToMs(`${brush[3]}:${brush[4]}`, AS_OF));

		const kinds = (p.get('kinds') ?? '').split(',').filter((k) => /^[a-z_]{2,24}$/.test(k));
		if (kinds.length) workspace.addFilter({ field: 'kind', values: kinds, label: kinds.map((k) => kindOne(k, 'en')).join(', ') });

		const m = p.get('mode');
		const left = p.get('left') ?? (m === 'info' ? 'info' : brush ? 'histogram' : 'explorer');
		if (m === 'card') {
			workspace.view = 'map';
			workspace.docks = { left: false, right: false, bottom: 'off' };
		} else {
			workspace.view = 'table';
			workspace.leftTab = left;
			workspace.rightTab = 'inspector';
			workspace.docks = { left: left !== 'none', right: !brush && !!urn, bottom: 'off' };
		}
		currentView.set(current?.id ?? null);

		(window as unknown as Record<string, unknown>).__VIEWS_HARNESS__ = {
			scrollTest,
			csv: () => toCsv(tableScope.inTable(), { lang: 'en', get: (u: string) => liveWorld.graph().get(u) }),
			counts: () => ({
				vehicles: selectors.count('vehicle'),
				explorer: Number(document.querySelector('[data-testid="explorer-kinds"] [data-kind="vehicle"]')?.getAttribute('data-count') ?? NaN),
				card: Number(document.querySelector('[data-testid="city-vitals"] [data-vital="watchlisted"]')?.getAttribute('data-value') ?? NaN),
				objectSet: workspace.objectSet.length,
				scopeRows: tableScope.rows().length,
				inTable: tableScope.inTable().length,
				tableRows: Number(document.querySelector('[data-testid="object-table"]')?.getAttribute('data-rows') ?? NaN),
				histogramRows: Number(document.querySelector('[data-testid="histogram"]')?.getAttribute('data-rows') ?? NaN),
				linked: selectors.linked(VEHICLE).length,
			}),
		};
		ready = true;

		// leaving the harness (an SPA navigation): no fixture, tab or seed outlives it
		return () => {
			selection.clear();
			workspace.clearFilters();
			workspace.returnToLive();
			resetRegistry();
			registerProviders();
			dossier.unseed();
			cityRegistry.unseed();
			cityVitals.unseed();
			if (fusionFeed.rows === FEED) fusionFeed.rows = feedBefore;
		};
	});

	/** Scroll the table end to end, one step per animation frame: frame times and the rows in the DOM. */
	async function scrollTest(steps = 180) {
		await tick();
		const el = document.querySelector<HTMLElement>('[data-testid="object-table"] [data-ui="data-table"]');
		if (!el) return { error: 'no table' };
		const total = Number(document.querySelector('[data-testid="object-table"]')?.getAttribute('data-rows') ?? 0);
		const frames: number[] = [];
		let maxRendered = 0;
		el.scrollTop = 0;
		await new Promise((r) => requestAnimationFrame(r));
		let last = performance.now();
		for (let i = 1; i <= steps; i++) {
			el.scrollTop = ((el.scrollHeight - el.clientHeight) * i) / steps;
			await new Promise((r) => requestAnimationFrame(r));
			const now = performance.now();
			frames.push(now - last);
			last = now;
			maxRendered = Math.max(maxRendered, el.querySelectorAll('tbody tr.row').length);
		}
		const sorted = [...frames].sort((a, b) => a - b);
		const q = (p: number) => Math.round(sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))] * 10) / 10;
		const result = { total, steps, maxRendered, p50: q(0.5), p95: q(0.95), max: q(1), over33: frames.filter((f) => f > 33.4).length, reachedEnd: el.scrollTop + el.clientHeight >= el.scrollHeight - 2 };
		console.info('views harness scroll test', JSON.stringify(result));
		return result;
	}

	// ── the schematic map (card mode: fixture positions on a plain ground) ─

	let mapW = $state(800);
	let mapH = $state(600);
	const placed = $derived(ready ? liveWorld.graph().all().filter((r) => r.lon != null && r.lat != null) : []);
	const bounds = $derived.by(() => {
		const lons = placed.map((r) => r.lon as number);
		const lats = placed.map((r) => r.lat as number);
		if (!lons.length) return { x0: 72.7623, x1: 72.9623, y0: 18.9332, y1: 19.085 };
		return { x0: Math.min(...lons) - 0.01, x1: Math.max(...lons) + 0.01, y0: Math.min(...lats) - 0.01, y1: Math.max(...lats) + 0.01 };
	});
	const project = (r: ObjectRow) => {
		const b = bounds;
		const k = Math.min((mapW - 120) / Math.max(1e-6, b.x1 - b.x0), (mapH - 120) / Math.max(1e-6, b.y1 - b.y0));
		return { x: (mapW - (b.x1 - b.x0) * k) / 2 + ((r.lon as number) - b.x0) * k, y: (mapH - (b.y1 - b.y0) * k) / 2 + (b.y1 - (r.lat as number)) * k };
	};

	// the active events the page would hand the Explorer (S6A fills it with ActiveEvents)
	const openEvents = $derived(ready ? liveWorld.registry().filter((r) => r.kind === 'event' && r.state === 'active') : []);
	// the pane header names the saved view in force (the Explorer's current one)
	const title = $derived(workspace.savedViews.find((v) => v.id === currentView.id)?.name ?? 'Unsaved view');
</script>

{#snippet activeEvents()}
	<ul class="events" data-testid="active-events">
		{#each openEvents as e (e.urn)}
			<li data-event-id={e.id}>
				<button type="button" class="ev" onclick={() => selection.select(e.urn, { source: 'rail' })}>
					<Icon name={e.icon} /><span class="ev-l">{e.label}</span>
					{#if e.source === 'emulated'}<ProvenanceTag source="emulated" compact data-testid="liverail-emulated" />{/if}
				</button>
			</li>
		{:else}
			<li class="none">{L('vw_i_events_none')}</li>
		{/each}
	</ul>
{/snippet}

<svelte:head><title>Views harness · Sajag</title></svelte:head>

<div class="harness" data-harness="views" data-ready={ready}>
	{#if ready && standalone}
		<div class="standalone">
			<header class="sa-head">{L('vw_tab_explorer')}</header>
			<div class="sa-body"><Explorer {activeEvents} /></div>
		</div>
	{:else if ready}
		<WorkspaceFrame route={mode === 'card' ? '/gods-eye' : '/'} mode={mode === 'card' ? 'map' : 'workspace'} {title}>
			{#snippet headerRight()}<Tag icon="lab-test" tooltip="Design harness: the prototype's emulated, masked capture and fictional objects">Fixture data</Tag>{/snippet}
			{#snippet map()}
				<div class="schematic" bind:clientWidth={mapW} bind:clientHeight={mapH}>
					<svg width={mapW} height={mapH} role="img" aria-label="Schematic map of the fixture objects">
						<defs>
							<pattern id="vw-grid" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M 48 0 L 0 0 0 48" class="gridline" /></pattern>
						</defs>
						<rect width={mapW} height={mapH} fill="url(#vw-grid)" />
						{#each placed as r (r.urn)}
							{@const pt = project(r)}
							{@const g = iconPaths(r.icon, 16)}
							<g class="mk" class:alert={r.kind === 'vehicle'} transform="translate({pt.x},{pt.y})">
								<circle r="10.5" class="disc" />
								<g transform="translate(-6,-6) scale({12 / g.grid})">{#each g.paths as d, i (i)}<path {d} fill-rule="evenodd" class="glyph" />{/each}</g>
							</g>
						{/each}
					</svg>
					<span class="caption">Schematic · fixture positions</span>
				</div>
			{/snippet}
			{#snippet table()}
				<ObjectTable rows={synthetic ?? undefined} header={synthetic ? `Synthetic rows (fictional)` : null} now={AS_OF} />
			{/snippet}
			{#snippet overlay()}
				{#if mode === 'card'}<CityVitals variant="card" poll={false} />{/if}
			{/snippet}
		</WorkspaceFrame>
	{/if}
</div>

<style>
	/* above the deck's navbar (content layer), BELOW every portalled overlay: the popovers (column
	   picker, saved-view and watch menus), dialogs, toasts and tooltips must open over the harness */
	.harness {
		position: fixed;
		inset: 0;
		z-index: calc(var(--v-z-content) + 1);
		background: var(--v-canvas);
	}

	.standalone {
		display: flex;
		flex-direction: column;
		width: 300px;
		height: 100%;
		border-right: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
	}

	.sa-head {
		display: flex;
		align-items: center;
		height: 40px;
		padding: 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		font-weight: 600;
	}

	.sa-body {
		flex: 1 1 auto;
		min-height: 0;
		overflow: auto;
	}

	.events {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.ev {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		height: 30px;
		margin: 0;
		padding: 0 12px 0 16px;
		border: 0;
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.ev:hover {
		background: var(--v-row-hover);
	}

	.ev-l {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.none {
		padding: 0 16px 8px;
		color: var(--v-ink-2);
		font-size: 12px;
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
</style>
