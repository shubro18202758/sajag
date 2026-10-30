<script lang="ts">
	/**
	 * /map — the V3 Map (V3-SPEC §5.6, §6.5, §6.10; V3-P4). The SAME God's-eye canvas as /gods-eye (the Analyst
	 * city map, unchanged), mounted with chrome="v3": the v2 symbology, picking, follow, measure, the thermal-style
	 * filter, the photoreal city and the `window.__GODS_EYE__` contract — and none of the v2 canvas chrome. Around
	 * it, the V3 chrome:
	 *
	 *   MapChips      the four groups (Live operations · Needs your decision · Reported in the city · Coming up) +
	 *                 Layers; a chip hides its group on the map and in the Now list
	 *   WeatherChip   an OFFICIAL district weather warning, as a chip (never a ring)
 *   CityChips     the City row under Rain · Tide: Air · Heat · Cyclone · River · Quake ($lib/cityfeeds; a click opens
 *                 the sources and the proposal drafts)
	 *   LayersSheet   base map (City map · 3D city), the layers that start off, the Vehicles-only rule
	 *   NowPanel      the same objects as a list (the map's accessible equivalent), live countdowns, Replay
	 *   SelectionCard what is selected: ≤ 2 tags, ≤ 3 figures, one verb (Review → its ONE home in Decide), Follow,
	 *                 Details; never an Approve
	 *   MapTools      3D, thermal-style view (main toolbar, honest tooltip), measure, follow, zoom, north
	 *   Legend3       three lines, the live city's lines (road colour, moving dots, units, pulses) and the
 *                 "Map data updated hh:mm:ss IST" clock (hud/map/live-clock: the newest real feed answer)
	 *
	 * Clean by default (§5.6): events, convoy, traces, enforcement, osint on; the rest off (a share link's own
	 * layers win). The OSM night map shows at once — a graded tile placeholder until the canvas is up, and under the
	 * 3D city until its first tiles land (the canvas keeps the OSM layer for chrome v3). Selecting anything focuses
	 * it in the part of the map the panels leave clear (clearInsets). Honest provenance everywhere: the simulated
	 * traffic feed, emulated units and escorts, the OSINT verification words, "not a live image" on the 3D city,
	 * "a visual filter, no thermal sensor" on the thermal-style view. Every mark is masked unless a duty officer is
	 * named (ops.plate / ops.text, then PlateChip). Data: the existing stores only (ops, the city registry,
	 * decisionUnits, Home's view models) — no new endpoint.
	 *
	 * Operator gate on and nobody signed in: one sign-in card, no canvas, no pollers.
	 */
	import { onDestroy, onMount, untrack } from 'svelte';
	import type { Component } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { godsEye } from '$lib/gods-eye/store.svelte';
	import { replay } from '$lib/gods-eye/hud/replay.svelte';
	import { mapChrome } from '$lib/gods-eye/hud/map/map-state.svelte';
	import GodsEyeCanvas from '$lib/gods-eye/GodsEyeCanvas.svelte';
	import OperatorSignIn from '$lib/shell/OperatorSignIn.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { registerProviders } from '$lib/workspace/providers';
	import { selectors } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { decisionUnits, unitEmulated, type Unit } from '$lib/decisions/units';
	import { t } from '$lib/i18n/strings';
	import { readableIn, scriptOf } from '$lib/i18n/script';
	import '$lib/v3/packs.city';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.wall';
	import '$lib/i18n/packs.map';
	import { provideUiLang } from '$lib/ui';
	import { fmtAgo, fmtDuration, fmtTime } from '$lib/ui/format/format';
	import '../packs.v3';
	import './packs.map3';
	import { v3Bar } from '../shell/v3-bar.svelte';
	import { artFor, countdownText, liveOpsOf, plannedOf, unitKey } from '../home/model';
	import { decisionVM, opVM, plannedVM, reportVM, roadLines, type TagVM } from '../home/view';
	import MapThumb from './MapThumb.svelte';
	import { mapStyle } from './map-style.svelte';
	import { startLayers } from './style-rules';
	import MapChips from './MapChips.svelte';
	import NowPanel from './NowPanel.svelte';
	import SelectionCard from './SelectionCard.svelte';
	import MapTools from './MapTools.svelte';
	import LayersSheet from './LayersSheet.svelte';
	import WeatherChip from './WeatherChip.svelte';
	import Legend3 from './Legend3.svelte';
	import { liveClock } from '$lib/gods-eye/hud/map/live-clock';
	import { istClock } from '$lib/gods-eye/hud/map/live-marks';
	import StatsPanel from './StatsPanel.svelte';
	import Glyph from '../Glyph.svelte';
	import { glassSupported, glassVars } from './glass';
	import { CITY_BBOX, bboxArray, cityName } from '$lib/city';
	import { corridor } from '$lib/ops/components/template/corridor.svelte';
	import { page } from '$app/state';
	import { ai } from '$lib/ai/ai.svelte';
	import '$lib/ai/packs.ai';
	import { hideHindsight, showHindsight } from '$lib/ai/hindsight';
	import { istMs, replayClassAt, replayTimeline } from '$lib/ai/model';
	import RainTideChip from '$lib/ai/ui/RainTideChip.svelte';
	import CityChips from '$lib/cityfeeds/CityChips.svelte';
	import ForecastBand from '$lib/ai/ui/ForecastBand.svelte';
	import {
		GROUP_IDS,
		GROUP_LAYERS,
		THERMAL_MODES,
		THERMAL_PALETTE_KEY,
		V3_DEFAULT_LAYERS,
		aliasUrn,
		detailsHref,
		entityArt,
		groupLayerState,
		isOfficialWeather,
		mapKey,
		movementStats,
		nextSensor,
		nowFromDecision,
		nowFromOp,
		nowFromPlanned,
		nowFromReport,
		pickItem,
		replayBlock,
		SHEET_LAYER_IDS,
		trafficFigures,
		type GroupId,
		type NowItem,
		type StatSection,
		type Stat,
	} from './model';

	provideUiLang(() => ops.lang);
	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	let sessionWaitOver = $state(false);
	const sessionKnown = $derived(ops.sessionGate !== null || sessionWaitOver);

	// ── the base map (V3-P4C): the natural photoreal 3D city is the default whenever the deck has the ion key ──
	// The canvas reads its start layers once, at mount — so the deck's imagery answer (the same /gods-eye/mode the
	// canvas reads; the token goes to the canvas and the thumbnails' satellite source, never into this page's markup)
	// is waited for first, and the choice remembered per browser (map-style.svelte.ts) decides whether the photoreal
	// city starts on. Without the key: the city map, with the honest reason on the 3D control.
	let modeKnown = $state(false);
	let canvasLayers = $state<readonly string[]>(V3_DEFAULT_LAYERS);
	$effect(() => {
		if (!sessionKnown || modeKnown) return;
		untrack(() => {
			void godsEye.pollImageryMode().finally(() => {
				const keyed = godsEye.imageryMode === 'ion-photoreal' && !!godsEye.imageryToken;
				mapStyle.provide(godsEye.imageryToken);
				canvasLayers = startLayers(V3_DEFAULT_LAYERS, mapStyle.baseFor(keyed));
				modeKnown = true;
			});
		});
	});

	// ── clocks: 1 s for countdowns and the Now clock, 15 s for what ages ────
	let now = $state(Date.now());
	let slow = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => {
			now = Date.now();
			if (now - slow >= 15_000) slow = now;
		}, 1000);
		return () => clearInterval(id);
	});

	// ── what is on the map, as Home's view models (one set of honesty rules) ──
	const units = $derived.by((): Unit[] => {
		void cityRegistry.version;
		return decisionUnits(ops);
	});
	const decisionVMs = $derived(units.map((u) => ({ u, vm: decisionVM(u, lang, slow) })));
	/** The decision home ("Review") for an object, when a decision waits on it. */
	const reviewOf = $derived.by(() => {
		const m = new Map<string, { href: string; kind: string }>();
		for (const { u, vm } of decisionVMs) if (!m.has(u.subjectUrn)) m.set(u.subjectUrn, { href: vm.href, kind: u.kind });
		return m;
	});
	const liveEvents = $derived(liveOpsOf(ops.events));
	const opVMs = $derived(liveEvents.map((ev) => opVM(ev, lang, slow, units)));
	const reports = $derived.by(() => {
		void cityRegistry.version;
		return [...cityRegistry.byKind('osint_event')].sort((a, b) => (b.t ?? 0) - (a.t ?? 0));
	});
	const wxText = (r: { label: string; props: Readonly<Record<string, unknown>> }) => (typeof r.props.summary === 'string' && r.props.summary ? r.props.summary : r.label);
	/** English first: the official warning in the reader's language when the source sent one (IMD publishes English and Marathi). */
	const weather = $derived.by(() => {
		const all = reports.filter((r) => isOfficialWeather(r));
		return all.find((r) => readableIn(wxText(r), lang)) ?? all[0] ?? null;
	});
	/** Never a machine translation of an official warning: a text the reader does not read says so, and the object page keeps it. */
	const weatherLine = $derived.by(() => {
		if (!weather) return '';
		const text = wxText(weather);
		if (readableIn(text, lang)) return ops.text(text);
		// Marathi or Hindi named as such; any other script (script.ts 'other') never passes for Marathi
		const sc = scriptOf(text);
		return t(lang, sc === 'hi' ? 'v3_text_brief_hi' : sc === 'mr' ? 'v3_text_brief_mr' : 'city_text_brief_other');
	});
	const reportVMs = $derived(reports.map((e) => reportVM(e, lang, slow, units)));
	const planned = $derived(plannedOf(ops.events, slow));
	const plannedVMs = $derived(planned.map((ev) => plannedVM(ev, lang, slow)));

	/** The legend's "Map data updated hh:mm:ss IST": the newest real answer of a live map feed, re-read every second. */
	const liveUpdated = $derived.by(() => {
		void now;
		return liveClock.updatedAt != null ? istClock(liveClock.updatedAt) : null;
	});

	const items = $derived<NowItem[]>([
		...opVMs.map((vm) => nowFromOp(vm, reviewOf.get(vm.key)?.href ?? null)),
		...decisionVMs.map(({ u, vm }) => nowFromDecision(vm, u.subjectUrn)),
		...reportVMs.map((vm) => nowFromReport(vm, reviewOf.get(vm.key)?.href ?? null)),
		...plannedVMs.map((vm) => nowFromPlanned(vm)),
	]);
	const counts = $derived(Object.fromEntries(GROUP_IDS.map((g) => [g, items.filter((i) => i.group === g).length])) as Record<GroupId, number>);

	// ── the four groups (chips) ─────────────────────────────────────────────
	let on = $state<Record<GroupId, boolean>>({ live: true, decide: true, reported: true, planned: true });
	function toggleGroup(g: GroupId) {
		on = { ...on, [g]: !on[g] };
		const want = groupLayerState(on);
		for (const id of GROUP_LAYERS[g]) mapChrome.setLayer(id, want[id]);
	}

	// ── the selection (one everywhere) ──────────────────────────────────────
	/** The Now row the officer picked (several rows may share an object: the movement and its escort decision). */
	let selKey = $state<string | null>(null);
	const current = $derived(selection.current);
	const currentEntity = $derived.by(() => {
		void cityRegistry.version;
		return current ? (cityRegistry.get(current) ?? null) : null;
	});
	const selItem = $derived(pickItem(items, selKey, aliasUrn(current, currentEntity?.props)));
	const shownKey = $derived(selItem?.key ?? null);

	function selectRow(i: NowItem) {
		selKey = i.key;
		if (i.urn) selection.select(i.urn, { fly: true, source: 'rail' });
	}

	function closeCard() {
		selKey = null;
		selection.clear();
	}

	// ── focus mode (review item 1): a selected event or operation is framed (the canvas flies to its route's
	// extent) and everything unrelated steps back (MapView.focus); "Show all" clears it and returns to the city ──
	function showAll() {
		closeCard();
		mapChrome.act('home');
	}

	// ── the canvas's tools (mapChrome: the canvas implements them) ──────────
	const tools = $derived(mapChrome.tools);
	const is3d = $derived(mapChrome.basemap === 'photoreal');
	const can3d = $derived(mapChrome.photoreal.available);
	const why3d = $derived(L('map_basemap_needs_key'));
	const sensor = $derived(tools?.sensor ?? 'raw');
	let lastThermal = $state<string | null>(null);
	function thermal() {
		const next = nextSensor(sensor, lastThermal);
		mapChrome.act('sensor', next);
	}
	function palette(mode: string) {
		lastThermal = mode;
		mapChrome.act('sensor', mode);
	}
	const upFirst = (x: string) => (x ? x.charAt(0).toLocaleUpperCase() + x.slice(1) : x);
	function set3d(want: boolean) {
		if (want === is3d) return;
		mapStyle.setBase(want ? 'sat3d' : 'city'); // remembered per browser
		mapChrome.act('3d', want);
	}

	// ── the layers sheet ───────────────────────────────────────────────────
	let sheetOpen = $state(false);
	/** The corridor stats panel (review item 2): closed by default, opened from the map tools. */
	let statsOpen = $state(false);
	/** The legend (review item 3): the officer shows or hides it (kept per browser); hidden by default at 1366. */
	let legendOpen = $state(false);
	const LEGEND_KEY = 'sajag.v3.map.legend';
	function setLegend(open: boolean) {
		legendOpen = open;
		try {
			localStorage.setItem(LEGEND_KEY, open ? '1' : '0');
		} catch {
			// storage unavailable: this visit only
		}
	}
	let cardH = $state(0);
	/** The browser can blur behind the glass (else the solid fallback). */
	let glassBlur = $state(false);
	const sheetRows = $derived(mapChrome.rows.filter((r) => SHEET_LAYER_IDS.includes(r.id)));
	const layersOn = $derived(sheetRows.filter((r) => r.visible).length);

	// ── replay (v2 §7.3: it waits while a movement is live or a pursuit is open) ──
	const replaying = $derived(replay.mode === 'replay');
	const replayBlocked = $derived(replayBlock(ops.events));
	let ReplayBar = $state<Component | null>(null);
	function startReplay() {
		if (replayBlocked) return;
		void import('$lib/gods-eye/hud/ReplayBar.svelte').then((m) => (ReplayBar = m.default as unknown as Component));
		void replay.enter();
	}

	// ── the AI services: the Rain · Tide chip, the road card's forecast, the 23 Sep 2025 hindsight ─────────
	let hsOn = $state(false);
	let hsAt = $state<number | null>(null);
	let hsBusy = $state(false);
	let hsFailed = $state(false);
	const timeline = $derived(replayTimeline(ai.replay));
	/** The moments of the replay night the officer can step through (rising limb only: the model's first-reached times). */
	const hsSteps = $derived.by((): number[] => {
		const tl = timeline;
		if (!tl) return [];
		const snap = istMs(ai.replay?.runs?.imd_gauge_anchored?.snapshot?.at_ist ?? null);
		const out = [snap, tl.firstFlag, tl.peakHour?.from ?? null, tl.peakHour?.to ?? null, tl.peak].filter((x): x is number => x != null && x >= tl.start && x <= tl.peak);
		return [...new Set(out)].sort((a, b) => a - b);
	});
	const hsCounts = $derived.by(() => {
		const segs = ai.replay?.runs?.imd_gauge_anchored?.segments ?? [];
		if (!hsOn || hsAt == null) return null;
		let deep = 0;
		let impassable = 0;
		for (const sg of segs) {
			const c = replayClassAt(sg, hsAt);
			if (c >= 3) impassable++;
			else if (c === 2) deep++;
		}
		return { deep, impassable };
	});
	function hsStep(at: number) {
		const segs = ai.replay?.runs?.imd_gauge_anchored?.segments ?? [];
		hsAt = at;
		showHindsight(segs, at);
	}
	async function setHindsight(on: boolean) {
		if (!on) {
			hsOn = false;
			hsAt = null;
			hideHindsight();
			return;
		}
		hsBusy = true;
		hsFailed = false;
		const rep = await ai.loadReplay();
		hsBusy = false;
		const tl = replayTimeline(rep);
		if (!rep || !tl) {
			hsFailed = true;
			return;
		}
		hsOn = true;
		mapChrome.setLayer('waterlog', true);
		hsStep(tl.peakHour?.to ?? tl.peak);
	}

	// ── the selection card ──────────────────────────────────────────────────
	const roads = $derived(roadLines());
	interface CardVM {
		art: string;
		kind: string;
		title: string;
		plate: NowItem['plate'];
		tags: TagVM[];
		stats: Stat[];
		primary: { href: string; text: string } | null;
		details: string;
		/** A road (segment:<id>): its forecast band rides in the card. */
		segmentId?: number | null;
	}

	function reviewText(kind: string | undefined): string {
		return L(kind === 'escort-proposal' ? 'v3m_review_hold' : kind === 'corridor-request' ? 'v3m_review_request' : 'v3m_review');
	}

	function timerTag(deadline: number | null, since: number | null): TagVM | null {
		if (deadline != null && deadline > now) return { text: L('v3m_left', countdownText(deadline - now, lang)), tone: 'decide', glyph: 'clock' };
		if (since != null) return { text: L('v3m_waiting', fmtDuration((now - since) / 1000, lang)), tone: 'decide', glyph: 'clock' };
		return null;
	}

	/** A road picked on the map (flow, waterlogging or forecast): its waterlogging risk now (or on the replay night) and its forecast. */
	function roadCard(id: number, urn: string, label: string | null): CardVM {
		const hy = ai.nowcast?.segments.find((x) => x.segment_id === id) ?? null;
		const fc = ai.forecast?.segments.find((x) => x.segment_id === id) ?? null;
		const rp = hsOn ? (ai.replay?.runs?.imd_gauge_anchored?.segments.find((x) => x.segment_id === id) ?? null) : null;
		const geo = godsEye.segmentById.get(id);
		const name = hy?.road_name ?? fc?.road_name ?? geo?.roadName ?? label ?? `#${id}`;
		const place = hy ? (lang === 'mr' && hy.place_mr ? hy.place_mr : hy.place) : (fc?.place ?? null);
		const tags: TagVM[] = [];
		const stats: Stat[] = [];
		if (rp && hsAt != null) {
			const c = replayClassAt(rp, hsAt);
			tags.push({ text: `${L('ai_risk_tag', c)} · ${L(`ai_risk_${c}`)}`, tone: c >= 2 ? 'alert' : 'neutral', glyph: 'wave' });
			tags.push({ text: L('ai_prov_hindsight'), tone: 'dashed', glyph: 'history', title: L('ai_prov_hindsight_tip') });
			stats.push({ value: rp.peak_band, label: L('ai_stat_peak') });
			if (rp.first_class2_ist) stats.push({ value: rp.first_class2_ist.slice(11), label: L('ai_stat_first_deep') });
			stats.push({ value: `${Math.round(rp.rain_total_mm)} mm`, label: L('ai_prov_observed') });
		} else if (hy) {
			tags.push({ text: `${L('ai_risk_tag', hy.risk_class)} · ${L(`ai_risk_${Math.min(3, hy.risk_class)}`)}`, tone: hy.risk_class >= 2 ? 'alert' : 'neutral', glyph: 'wave' });
			tags.push({ text: L('ai_prov_modelled'), tone: 'dashed', glyph: 'graph', title: L('ai_prov_modelled_tip') });
			stats.push({ value: hy.expected_depth_band, label: L('ai_stat_depth') });
			if (hy.lead_time_deep_min != null) stats.push({ value: fmtDuration(hy.lead_time_deep_min * 60, lang), label: L('ai_stat_deep_in') });
			const r2 = hy.drivers?.rain?.next_2h_mm;
			if (typeof r2 === 'number') stats.push({ value: `${r2.toFixed(1)} mm`, label: L('ai_stat_rain2h') });
		}
		return {
			art: (rp && hsAt != null && replayClassAt(rp, hsAt) >= 1) || (!rp && hy && hy.risk_class >= 1) ? artFor('flooding') : entityArt('segment', {}, artFor),
			kind: place ? `${L('ai_sel_road')} · ${ops.text(place)}` : L('ai_sel_road'),
			title: ops.text(name),
			plate: null,
			tags: tags.slice(0, 2),
			stats: stats.slice(0, 3),
			primary: null,
			details: detailsHref(urn),
			segmentId: id,
		};
	}

	const card = $derived.by((): CardVM | null => {
		void slow;
		const urn = current;
		if (!urn) return null;
		const i = selItem;
		const ent = currentEntity;
		const segM = /^segment:(\d+)$/.exec(urn);
		if (segM && !i) return roadCard(Number(segM[1]), urn, ent?.label ?? null);
		if (i) {
			const tags: TagVM[] = [];
			let stats: Stat[] = [];
			let primary: CardVM['primary'] = null;
			const review = i.review ? { href: i.review, text: reviewText(reviewOf.get(i.urn ?? '')?.kind) } : null;
			if (i.group === 'live') {
				const vm = opVMs.find((o) => o.key === i.key);
				if (vm) tags.push(vm.state);
				if (i.decisions > 0) tags.push({ text: t(lang, 'v3_op_decision_waits', i.decisions), tone: 'decide', glyph: 'clock' });
				else if (i.prov) tags.push(i.prov);
				const ev = ops.events.find((e) => `event:${e.eventId}` === i.urn);
				if (ev?.eventKind === 'protected_movement') {
					const convoy = cityRegistry.byKind('convoy').find((c) => c.props.event_id === ev.eventId || (ev.movementId && c.props.movement_id === ev.movementId));
					stats = movementStats(convoy?.props, now, { time: (ms) => fmtTime(ms), dur: (s) => fmtDuration(s, lang) }, L);
				} else if (ev?.eventKind === 'vehicle_pursuit') {
					const vehicleId = ev.metadata?.vehicleId ?? null;
					const watch = vehicleId ? ops.watchlist.find((w) => w.vehicleId === vehicleId) : null;
					const readT = watch?.lastSighting?.t ? Date.parse(watch.lastSighting.t) : NaN;
					if (Number.isFinite(readT)) stats.push({ value: fmtDuration((now - readT) / 1000, lang), label: L('v3m_stat_since_read') });
					const reads = vehicleId ? cityRegistry.byKind('sighting').filter((s) => s.props.vehicle_id === vehicleId || s.links.includes(`vehicle:${vehicleId}`)).length : 0;
					if (reads) stats.push({ value: String(reads), label: L('v3m_stat_reads') });
				}
				primary = review;
			} else if (i.group === 'decide') {
				const d = decisionVMs.find((x) => x.vm.key === i.key)?.vm;
				if (d) {
					tags.push({ text: d.by.text, tone: d.by.ai ? 'ai' : 'neutral', glyph: d.by.ai ? 'spark' : undefined });
					const tm = timerTag(d.deadline, d.since);
					if (tm) tags.push(tm);
					else if (d.prov) tags.push(d.prov);
					stats = d.facts.map((f) => ({ value: f.value, label: f.label }));
					primary = { href: d.href, text: reviewText(d.kind) };
				}
			} else if (i.group === 'reported') {
				const r = reportVMs.find((x) => x.key === i.key);
				if (r) {
					tags.push(r.verif);
					tags.push({ text: r.note, tone: review ? 'decide' : 'neutral' });
					if (r.cred != null) stats.push({ value: r.cred.toFixed(2), label: L('v3m_stat_cred') });
					const rep = reports.find((x) => x.urn === r.key);
					if (rep?.t != null) stats.push({ value: fmtAgo(rep.t, now, lang), label: L('v3m_stat_reported') });
					const pubs = typeof rep?.props.publisher_count === 'number' ? rep.props.publisher_count : null;
					if (pubs != null) stats.push({ value: String(pubs), label: L('v3m_stat_publishers') });
				}
				primary = review;
			} else {
				const p = plannedVMs.find((x) => x.key === i.key);
				if (p) {
					tags.push({ text: p.when, tone: 'neutral', glyph: 'calendar' });
					if (p.prov) tags.push(p.prov);
					tags.push({ text: p.next, tone: 'neutral' });
				}
			}
			return { art: i.art, kind: i.kind, title: i.title, plate: i.plate, tags: tags.slice(0, 2), stats: stats.slice(0, 3), primary, details: detailsHref(i.urn ?? urn) };
		}
		// an object the Now list does not hold (a camera, a unit, a vehicle): its own words, masked
		if (!ent) return null;
		const kindKey = `v3m_kind_${ent.kind}`;
		const kindText = L(kindKey) === kindKey ? L('v3m_sel_object') : L(kindKey);
		const tags: TagVM[] = [];
		const rv = reviewOf.get(urn);
		if (rv) tags.push({ text: t(lang, 'v3_op_decision_waits', 1), tone: 'decide', glyph: 'clock' });
		if (ent.source === 'emulated') tags.push({ text: L('v3_prov_emulated'), tone: 'dashed', glyph: 'flask', title: L('v3_prov_emulated_tip') });
		const isVehicle = ent.kind === 'vehicle';
		const mark = isVehicle ? ops.plate(typeof ent.props.plate === 'string' ? ent.props.plate : null) : null;
		return {
			art: entityArt(ent.kind, ent.props, artFor),
			kind: kindText,
			title: isVehicle && mark ? L('v3m_kind_vehicle') : ops.text(ent.label),
			plate: isVehicle && mark ? { mark, masked: !ops.officerOn } : null,
			tags: tags.slice(0, 2),
			stats: [],
			primary: rv ? { href: rv.href, text: reviewText(rv.kind) } : null,
			details: detailsHref(urn),
		};
	});

	const focusTitle = $derived(current ? (card?.title ?? null) : null);

	// ── the canvas props ────────────────────────────────────────────────────
	const protectedSet = $derived(selectors.protectedUrns());
	let vw = $state(1920);
	/** The Now panel's width (§6.10: 380, 320 below 1500 px) and the strip it covers. */
	// a phone (≤ 720 px) has no Now column: the map takes the width, the chips and the Layers sheet sit over it
	const nowW = $derived(vw <= 720 ? 0 : vw <= 1500 ? 320 : 380);
	const clearInsets = $derived({ left: sheetOpen || statsOpen ? 400 : 0, right: nowW + 36, top: 64, bottom: 0 });

	// ── the corridor stats (each figure shown here only) ───────────────────
	const statSections = $derived.by((): StatSection[] => {
		void slow;
		const out: StatSection[] = [];
		const city = ops.cityBand;
		const band = city ? (city.stale ? null : city.band) : null;
		out.push({
			key: 'band',
			title: L('v3m_stats_band'),
			figures: band ? [{ value: upFirst(L(`v3_band_${band.toLowerCase()}`)), label: city?.since ? L('v3m_stats_since', fmtTime(city.since)) : '' }] : [],
			tags: city?.simulatedFeed ? [{ text: L('v3_prov_simulated'), tone: 'dashed', glyph: 'shuffle', title: L('v3_prov_simulated_tip') }] : [],
			note: city?.stale ? L('v3m_stats_band_stale') : band ? null : L('v3m_stats_band_none'),
		});
		const row = corridor.row;
		const tf = trafficFigures(row, L);
		const prov = row?.provenance;
		out.push({
			key: 'traffic',
			title: L('v3m_stats_traffic'),
			figures: tf.figures,
			tags:
				prov === 'emulated'
					? [{ text: L('v3_prov_simulated'), tone: 'dashed', glyph: 'shuffle', title: L('v3_prov_simulated_tip') }]
					: prov === 'mixed'
						? [{ text: L('v3m_prov_mixed'), tone: 'dashed', glyph: 'shuffle' }]
						: [],
			note: tf.note ?? (row?.dataAgeSec != null ? L('v3m_stats_age', fmtAgo(Date.now() - row.dataAgeSec * 1000, Date.now(), lang)) : null),
		});
		const lanes = ops.escorts.filter((l) => l.alive);
		const answered = lanes.reduce((n, l) => n + l.outcomes.length, 0);
		out.push({
			key: 'escorts',
			title: L('v3m_stats_escorts'),
			figures: lanes.length ? [{ value: String(lanes.length), label: L('v3m_stats_following') }, { value: String(answered), label: L('v3m_stats_answered') }] : [],
			tags: [
				...(lanes.some((l) => (l.gpsMode ?? '').includes('emul')) ? [{ text: L('v3m_stats_gps_emulated'), tone: 'dashed' as const, glyph: 'flask' }] : []),
				...(lanes.some((l) => l.trafficSimulated) ? [{ text: L('v3_prov_simulated'), tone: 'dashed' as const, glyph: 'shuffle' }] : []),
			],
			note: lanes.length ? null : L('v3m_stats_no_escort'),
		});
		return out;
	});

	// ── keys (§7.1): L layers, F follow, 3 the 3D city; Esc closes the sheet first ──
	function typing(el: EventTarget | null): boolean {
		const e = el as HTMLElement | null;
		return !!e && (e.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.tagName));
	}
	function onKey(e: KeyboardEvent) {
		if (e.defaultPrevented) return;
		if (e.key === 'Escape' && sheetOpen && !typing(e.target)) {
			sheetOpen = false;
			e.preventDefault(); // consumed: the canvas's Esc (stop a tool, clear the selection) waits for the next press
			return;
		}
		if (workspace.omnibar.open) return;
		const k = mapKey(e, typing(e.target));
		if (k === 'layers') sheetOpen = !sheetOpen;
		else if (k === 'follow' && tools?.follow && !tools.follow.disabled) mapChrome.act('follow');
		else if (k === '3d' && (can3d || is3d)) set3d(!is3d);
		else return;
		e.preventDefault();
	}

	// ── lifecycle ───────────────────────────────────────────────────────────
	onMount(() => {
		godsEye.followSelection = false; // a free camera; a row or a pick flies once on request
		registerProviders();
		ops.start();
		cityRegistry.start();
		corridor.start();
		const releaseAi = ai.use('hydro', 'tide', 'rain', 'forecast');
		// Home's "Show on the map" for the 23 Sep 2025 replay
		if (page.url.searchParams.get('replay') === '2025-08-19') void setHindsight(true);
		glassBlur = glassSupported();
		try {
			const kept = localStorage.getItem(LEGEND_KEY);
			legendOpen = kept != null ? kept === '1' : window.innerWidth > 1500;
		} catch {
			legendOpen = window.innerWidth > 1500;
		}
		const wait = setTimeout(() => (sessionWaitOver = true), 2500);
		window.addEventListener('keydown', onKey, { capture: true });
		return () => {
			clearTimeout(wait);
			releaseAi();
			window.removeEventListener('keydown', onKey, { capture: true });
		};
	});

	onDestroy(() => {
		godsEye.followSelection = false;
		godsEye.subjectLockId = null;
		if (replay.mode === 'replay') replay.exit();
		hideHindsight();
		selection.clear();
		cityRegistry.stop();
		corridor.stop();
		ops.stop();
		if (typeof window !== 'undefined') delete (window as unknown as Record<string, unknown>).__V3_MAP__;
	});

	// ── the shell (the v2 contract + the V3 bar) ───────────────────────────
	$effect(() => {
		commandBar.lang = ops.lang;
		commandBar.onLangChange = (l: string) => (ops.lang = l);
		commandBar.onShare = null;
		commandBar.onSearch = (q?: string) => workspace.openOmnibar(q);
		commandBar.onInbox = null;
	});
	$effect(() => {
		commandBar.officer = { value: ops.dutyOfficer, fromSession: ops.dutyOfficerFromSession, set: (v: string) => ops.setDutyOfficer(v) };
	});
	$effect(() => {
		const f = ops.trafficFeed;
		commandBar.exercise =
			f && (f.label === 'simulated' || f.label === 'mixed')
				? {
						label: f.label,
						text:
							f.label === 'simulated'
								? L('wall_exercise_simulated', f.segments)
								: L('wall_exercise_mixed', Math.round((100 * f.synthetic) / Math.max(1, f.real + f.synthetic))),
					}
				: null;
	});
	$effect(() => {
		commandBar.inboxCount = units.length;
		commandBar.inboxIntent = units.length ? 'warning' : 'none';
	});
	$effect(() => {
		v3Bar.title = L('v3m_title');
		v3Bar.sub = L('v3m_sub', cityName(lang));
		v3Bar.active = 'map';
	});
	const mountedAt = Date.now();
	const firstRound = $derived(
		(ops.boardUpdated > 0 && ops.recommendationsUpdated > 0 && ops.dispatchesUpdated > 0 && ops.escortsDeployed !== null && cityRegistry.status !== 'idle') ||
			now - mountedAt > 10_000,
	);
	$effect(() => {
		v3Bar.decisions = firstRound ? decisionVMs.map(({ u, vm }) => ({ key: unitKey(u), title: vm.maskedTitle, href: vm.href, emulated: unitEmulated(u) })) : null;
	});

	// ── the test hook (the smoke holds the page to the canonical selectors) ─
	$effect(() => {
		if (typeof window === 'undefined') return;
		(window as unknown as Record<string, unknown>).__V3_MAP__ = {
			canonical: { decisions: selectors.decisionUnits().length },
			counts: { ...counts },
			on: { ...on },
			rows: items.map((i) => ({ key: i.key, group: i.group, urn: i.urn })),
			selection: { urn: current, key: shownKey },
			card: card ? { title: card.title, tags: card.tags.length, stats: card.stats.length, primary: card.primary?.href ?? null } : null,
			sheetOpen,
			statsOpen,
			legendOpen,
			focus: focusTitle,
			statFigures: statSections.flatMap((x) => x.figures),
			cardFigures: card?.stats ?? [],
			is3d,
			sensor,
			tool: tools?.tool ?? null,
			ready: !!tools,
			replaying,
			replayBlocked,
			officerOn: ops.officerOn,
			layers: mapChrome.rows.map((r) => ({ id: r.id, visible: r.visible, count: r.count, hint: r.hint })),
			ai: { hindsight: hsOn, at: hsAt, counts: hsCounts, nowcast: !!ai.nowcast, tide: !!ai.tide, forecast: !!ai.forecast, road: card?.segmentId ?? null },
		};
	});

	// keep the officer's row only while it still names the selection (a pick elsewhere moves on)
	$effect(() => {
		const urn = current;
		const k = untrack(() => selKey);
		if (k && !items.some((i) => i.key === k && i.urn === aliasUrn(urn, untrack(() => currentEntity)?.props))) selKey = null;
	});
</script>

<svelte:head>
	<title>{L('v3m_title')} · Sajag</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<svelte:window bind:innerWidth={vw} />

{#if ops.signInRequired}
	<div class="signin" data-testid="cc-signin-required">
		<div class="signin-card">
			<h2>{tOps(lang, 'opsSigninTitle')}</h2>
			<p>{L('v3m_signin')}</p>
			<OperatorSignIn lang={ops.lang} inline />
		</div>
	</div>
{:else}
	<div class="map3" data-v3="map" data-ready={tools ? 'true' : 'false'} style:--now-w={`${nowW}px`} style={glassVars()} data-glass={glassBlur ? 'blur' : 'solid'}>
		<div class="stage">
			{#if !tools}
				<!-- the map at once (natural satellite tiles when the deck has the ion key, else the night map; the deck's own roads offline) while the canvas starts -->
				<div class="placeholder" aria-busy="true">
					<MapThumb bbox={bboxArray(CITY_BBOX)} zoom={13} maxTiles={48} eager alt={L('v3m_loading')} {roads} markerR={0} />
				</div>
			{/if}
			{#if sessionKnown && modeKnown}
				<div class="canvas" role="region" aria-label={L('v3m_map_alt')}>
					<GodsEyeCanvas
						hud="full"
						chrome="v3"
						defaultLayers={canvasLayers}
						protected={protectedSet}
						selectionItems={selection.items}
						{clearInsets}
					/>
				</div>
			{/if}
		</div>

		<!-- the LEFT column: the summary chips, the focus line, the official warning, then the collapsible panels
		     (layers and options, corridor stats) — review items 1, 2 and 4 -->
		<div class="left" style:bottom={card ? `${cardH + 36}px` : '18px'}>
			<MapChips {on} {counts} {layersOn} {sheetOpen} {lang} ontoggle={toggleGroup} onlayers={() => (sheetOpen = !sheetOpen)} />
			{#if focusTitle}
				<div class="focus v3-glass" role="status" data-testid="v3-focus" data-ge-keepout>
					<span class="ft">{L('v3m_focus', focusTitle)}</span>
					<button type="button" class="showall" title={L('v3m_show_all_tip')} data-testid="v3-show-all" onclick={showAll}><Glyph name="globe" size={16} />{L('v3m_show_all')}</button>
				</div>
			{/if}
			{#if weather && on.reported && !sheetOpen && !statsOpen}
				<WeatherChip text={weatherLine} href={detailsHref(weather.urn)} {lang} />
			{/if}
			{#if !sheetOpen && !statsOpen}
				<RainTideChip
					{lang}
					{now}
					nowcast={ai.nowcast}
					tide={ai.tide}
					rain={ai.rain}
					hydroDown={ai.feeds.hydro.status === 'down' || ai.feeds.hydro.status === 'not-deployed'}
					tideDown={ai.feeds.tide.status === 'down' || ai.feeds.tide.status === 'not-deployed'}
					hindsightOn={hsOn}
					steps={hsSteps}
					at={hsAt}
					counts={hsCounts}
					replayBusy={hsBusy}
					replayFailed={hsFailed}
					onhindsight={(v) => void setHindsight(v)}
					onstep={hsStep}
				/>
			{/if}
			{#if !sheetOpen && !statsOpen && !hsOn}
				<div class="city-chips"><CityChips {lang} /></div>
			{/if}
			{#if sheetOpen}
				<div class="panel">
					<LayersSheet
						hindsightOn={hsOn}
						rows={sheetRows}
						{is3d}
						{can3d}
						{why3d}
						{lang}
						onlayer={(id, v) => mapChrome.setLayer(id, v)}
						on3d={set3d}
						onclose={() => (sheetOpen = false)}
					/>
				</div>
			{/if}
			{#if statsOpen}
				<div class="panel">
					<StatsPanel sections={statSections} title={L('v3m_stats')} closeLabel={L('v3m_stats_close')} analystLabel={L('v3m_stats_analyst')} onclose={() => (statsOpen = false)} />
				</div>
			{/if}
		</div>

		<div class="now">
			<NowPanel
				{items}
				{on}
				selKey={shownKey}
				{now}
				clock={fmtTime(now, { seconds: true })}
				{lang}
				{replaying}
				{replayBlocked}
				onselect={selectRow}
				onreplay={startReplay}
				onlive={() => replay.exit()}
			/>
		</div>

		<div class="bottom-left">
			{#if card}
				<div class="card" bind:clientHeight={cardH}>
					<SelectionCard
						art={card.art}
						kind={card.kind}
						title={card.title}
						plate={card.plate}
						tags={card.tags}
						stats={card.stats}
						primary={card.primary}
						details={card.details}
						follow={tools?.follow ?? null}
						{lang}
						onclose={closeCard}
						onfollow={() => mapChrome.act('follow')}
					>
						{#if card.segmentId != null}
							<ForecastBand seg={ai.forecast?.segments.find((x) => x.segment_id === card.segmentId) ?? null} threshold={ai.forecast?.threshold_vc ?? 0.8} labels={ai.forecast?.data_labels ?? []} {lang} loading={!ai.forecast && ai.feeds.forecast.status !== 'down'} />
						{/if}
					</SelectionCard>
				</div>
			{/if}
			{#if legendOpen}<div class="legend"><Legend3 {lang} hideLabel={L('v3m_legend_hide')} onhide={() => setLegend(false)} water={mapChrome.rows.some((r) => r.id === 'waterlog' && r.visible && r.count > 0)} forecast={mapChrome.rows.some((r) => r.id === 'forecast' && r.visible && r.count > 0)} air={mapChrome.rows.some((r) => r.id === 'air' && r.visible && r.count > 0)} cyclone={mapChrome.rows.some((r) => r.id === 'cyclone' && r.visible && r.count > 0)} flow={mapChrome.rows.some((r) => r.id === 'flow' && r.visible && r.count > 0)} units={mapChrome.rows.some((r) => r.id === 'units' && r.visible && r.count > 0)} live={mapChrome.rows.some((r) => r.id === 'livevalues' && r.visible)} updatedAt={liveUpdated} /></div>{/if}
		</div>

		<div class="bottom-mid">
			{#if replaying && ReplayBar}
				<div class="replay v3-glass" data-ge-keepout>
					<p class="replay-note">{L('v3m_replay_note')}</p>
					<ReplayBar density="compact" {lang} />
				</div>
			{/if}
			{#if sensor !== 'raw'}
				<div class="label thermal v3-glass" role="status" data-testid="v3-thermal-label" data-ge-keepout>
					<span>{L('v3m_thermal_on')}</span>
					<span class="pal" role="group" aria-label={L('v3m_thermal_palette')}>
						{#each THERMAL_MODES as m (m)}
							<button type="button" class={['pb', sensor === m && 'is-pressed']} aria-pressed={sensor === m} onclick={() => palette(m)}>{upFirst(L(THERMAL_PALETTE_KEY[m]))}</button>
						{/each}
					</span>
				</div>
			{/if}
			{#if is3d}
				<div class="label v3-glass" role="status" data-testid="v3-3d-label" data-ge-keepout>{L(tools?.photorealReady ? 'v3m_credit_3d' : 'v3m_credit_3d_loading')}</div>
			{/if}
		</div>

		<div class="tools">
			<MapTools
				{is3d}
				{can3d}
				{why3d}
				{sensor}
				tool={tools?.tool ?? 'select'}
				follow={tools?.follow ?? null}
				heading={tools?.heading ?? 0}
				{statsOpen}
				{legendOpen}
				{lang}
				onstats={() => (statsOpen = !statsOpen)}
				onlegend={() => setLegend(!legendOpen)}
				on3d={() => set3d(!is3d)}
				onthermal={thermal}
				onmeasure={() => mapChrome.act('measure')}
				onfollow={() => mapChrome.act('follow')}
				onzoom={(s) => mapChrome.act('zoom', s)}
				onnorth={() => mapChrome.act('north')}
			/>
		</div>
	</div>
{/if}

<style>
	.map3 {
		position: relative;
		height: 100%;
		min-height: 480px;
		overflow: hidden;
		background: var(--v3-map-bg);
		color: var(--v3-t1);
	}

	.stage,
	.canvas,
	.placeholder {
		position: absolute;
		inset: 0;
	}

	.placeholder {
		z-index: 1;
	}

	.placeholder :global([data-v3='map-thumb']) {
		width: 100%;
		height: 100%;
	}

	/* the canvas fills the screen, square-cornered; its own loading line gives way to the night map above */
	.canvas :global(.ge-wrap) {
		border-radius: 0;
		background: var(--v3-map-bg);
	}

	.canvas :global(.ge-status) {
		display: none;
	}

	/* the canvas's tool hint and flash line sit under the chips; its proposals and replay banner under them too */
	.canvas :global(.ge-wrap) {
		--ge-hud-left: 20px;
		--ge-hud-top: 124px;
	}

	.canvas :global(.v2-top) {
		top: 124px;
		left: calc((100% - var(--now-w) - 36px) / 2);
	}

	/* Cesium's credits (Google's logo, Cesium ion, OSM): bottom right of the clear map, left of the tools */
	.map3 .stage :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom) {
		right: calc(var(--now-w) + 100px) !important;
		bottom: 6px !important;
		max-width: 420px;
		background: var(--v3-glass);
		color: var(--v3-t3);
	}

	/*
	 * The glass surface (review item 6): every overlay uses --v3-glass-surface. Opaque (--v3-glass-solid) where
	 * the browser has no backdrop-filter; translucent (--v3-glass-bg) where it has (data-glass, set from
	 * glassSupported() at mount). The tint alone keeps every text
	 * ink ≥ 4.5:1 over the darkest and the lightest map pixel (glass.ts; tests/v3-map.unit.mjs).
	 */
	.map3 {
		--v3-glass-surface: var(--v3-glass-solid);
	}

	.map3[data-glass='blur'] {
		--v3-glass-surface: var(--v3-glass-bg);
	}

	.map3[data-glass='blur'] :global(.v3-glass) {
		-webkit-backdrop-filter: var(--v3-glass-blur);
		backdrop-filter: var(--v3-glass-blur);
	}

	.left {
		position: absolute;
		left: 20px;
		top: 18px;
		right: calc(var(--now-w) + 110px);
		z-index: 7;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 12px;
		min-height: 0;
		pointer-events: none;
	}

	.left > :global(*) {
		pointer-events: auto;
	}

	.panel {
		display: flex;
		flex-direction: column;
		width: 360px;
		max-width: 100%;
		min-height: 0;
		flex: 0 1 auto;
	}

	.panel > :global(*) {
		min-height: 0;
		max-height: 100%;
	}

	.focus {
		display: inline-flex;
		align-items: center;
		gap: 12px;
		max-width: 100%;
		padding: 4px 4px 4px 14px;
		border: 1px solid var(--v3-glass-border);
		border-radius: 20px;
		background: var(--v3-glass-surface);
		box-shadow: var(--v3-elev-1);
		font-size: var(--v3-text-meta);
		color: var(--v3-t1);
	}

	.ft {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.showall {
		display: inline-flex;
		flex: none;
		align-items: center;
		gap: 6px;
		height: 32px;
		padding: 0 14px;
		border: 0;
		border-radius: 16px;
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		font: inherit;
		font-weight: 650;
		cursor: pointer;
	}

	.showall:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.now {
		position: absolute;
		top: 18px;
		right: 18px;
		bottom: 18px;
		width: var(--now-w);
		z-index: 6;
		display: flex;
		flex-direction: column;
	}

	.now > :global(*) {
		flex: 1;
		min-height: 0;
	}

	.bottom-left {
		position: absolute;
		left: 20px;
		bottom: 18px;
		right: calc(var(--now-w) + 110px);
		z-index: 7;
		display: flex;
		align-items: flex-end;
		gap: 20px;
		pointer-events: none;
	}

	.card {
		width: 520px;
		max-width: 100%;
		flex: none;
	}

	.legend {
		flex: none;
		pointer-events: none;
	}

	/* the honest on-map labels (thermal-style, 3D city) and the replay bar: right-aligned above Cesium's credits,
	   left of the tools — clear of the selection card and the legend at the bottom left */
	.bottom-mid {
		position: absolute;
		right: calc(var(--now-w) + 100px);
		bottom: 104px;
		z-index: 6;
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 8px;
		pointer-events: none;
	}

	.bottom-mid > :global(*) {
		pointer-events: auto;
	}

	.label {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		padding: 6px 12px;
		border: 1px solid var(--v3-glass-border);
		border-radius: 16px;
		background: var(--v3-glass-surface);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		white-space: nowrap;
	}

	.label.thermal {
		color: var(--v3-t1);
	}

	.pal {
		display: inline-flex;
		gap: 4px;
	}

	.pb {
		height: 26px;
		padding: 0 10px;
		border: 1px solid var(--v3-line-2);
		border-radius: 13px;
		background: none;
		color: var(--v3-t2);
		font: inherit;
		font-size: var(--v3-text-micro);
		font-weight: 600;
		cursor: pointer;
	}

	.pb.is-pressed {
		border-color: var(--v3-t1);
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.pb:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.replay {
		width: min(720px, 56vw);
		padding: 10px 12px;
		border: 1px solid var(--v3-glass-border);
		border-radius: var(--v3-radius-l);
		background: var(--v3-glass-surface);
		box-shadow: var(--v3-elev-2);
	}

	.replay-note {
		margin: 0 0 6px;
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
	}

	.tools {
		position: absolute;
		right: calc(var(--now-w) + 36px);
		bottom: 18px;
		z-index: 6;
	}

	.signin {
		display: grid;
		place-items: center;
		height: 100%;
		padding: 16px;
	}

	.signin-card {
		width: min(440px, calc(100vw - 32px));
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 20px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}

	.signin-card h2 {
		margin: 0;
		font-size: var(--v3-text-sub);
	}

	.signin-card p {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	@media (max-width: 1500px) {
		.card {
			width: 440px;
		}

		.legend {
			display: none;
		}

		.panel {
			width: 340px;
		}
	}

	/* a phone: no Now column (Home lists the same things); the chips scroll sideways in one row; the rain and tide line
	   stays; the city row (air, heat, cyclone …) is on Home; the selection card and the Layers sheet take the width */
	@media (max-width: 720px) {
		.now,
		.city-chips {
			display: none;
		}

		.left {
			left: 10px;
			right: 10px;
			top: 10px;
			gap: 8px;
		}

		.left > :global(.chips) {
			flex-wrap: nowrap;
			max-width: 100%;
			overflow-x: auto;
			scrollbar-width: none;
		}

		.panel {
			width: 100%;
		}

		.bottom-left {
			left: 10px;
			right: 10px;
			bottom: 10px;
		}

		.card {
			width: 100%;
		}

		.bottom-mid {
			right: 64px;
			bottom: 70px;
			left: 10px;
		}

		.label {
			white-space: normal;
		}

		.replay {
			width: 100%;
		}

		.tools {
			right: 10px;
			bottom: 10px;
		}

		/* the imagery credits stay readable but small, clear of the tools */
		.map3 .stage :global(.ge-wrap[data-chrome='v2'] .ge-canvas .cesium-viewer-bottom) {
			left: 6px;
			right: 64px !important;
			max-width: none;
			font-size: 10px;
			line-height: 13px;
		}
	}
</style>
