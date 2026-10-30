/**
 * The V3 Map's pure rules (V3-SPEC §5.6, §6.5, §7.3) — no store, no DOM; tests/v3-map.unit.mjs drives them.
 *
 *   GROUPS        the four group chips, in job order: Live operations · Needs your decision · Reported in the city
 *                 · Coming up. A chip shows or hides its group on the map (the layers only it draws) and in the
 *                 Now list; a layer two groups share (corridor events: live AND planned) stays while either is on.
 *   DEFAULTS      §5.6 "layer defaults clean": events, convoy, traces, enforcement, osint on; cameras, signals,
 *                 flow, units, dispatch, anomalies, places off; the photoreal city is the 3D button's, not a layer.
 *                 The waterlogging nowcast is ON (a hazard on the road the officer must see); the forecast is off.
 *   SHEET         the Layers sheet: Operations (units, dispatches), City (ANPR cameras, junctions and signals,
 *                 traffic flow, named places, feed checks), Forecasts (waterlogging risk, traffic forecast) and City
 *                 feeds (air quality at the monitoring sites, the active cyclone; both off, $lib/cityfeeds);
 *                 the Vehicles-only rule note sits under it.
 *   NOW ITEMS     one row per object the Now list shows, built from Home's view models (decisionVM, opVM, reportVM,
 *                 plannedVM — no second copy of their honesty rules): the urn a click selects, the art, the title
 *                 (a mark is already masked by ops.plate there), one meta line, the right-hand state.
 *   SELECTION     which Now item a map pick or a row click shows in the selection card (the row the officer
 *                 picked wins; a map pick shows the operation first, then a report, a plan, a decision).
 *   STATS         the card's three figures for a protected movement, from the convoy's own feed (never invented).
 *   REPLAY        replay waits while a movement is live or a pursuit is open (v2 §7.3: never hide live work).
 */
import type { DecisionVM, OpVM, PlannedVM, PlateVM, ReportVM, TagVM } from '../home/view';
import { objectHref } from '../object/model';
import { feedLayerSub } from '$lib/cityfeeds/model';

export type GroupId = 'live' | 'decide' | 'reported' | 'planned';

export const GROUP_IDS: readonly GroupId[] = ['live', 'decide', 'reported', 'planned'];

export const GROUP_KEY: Readonly<Record<GroupId, string>> = {
	live: 'v3m_grp_live',
	decide: 'v3m_grp_decide',
	reported: 'v3m_grp_reported',
	planned: 'v3m_grp_planned',
};

/** The layers each group draws (canvas layer ids, layers/index.ts). */
export const GROUP_LAYERS: Readonly<Record<GroupId, readonly string[]>> = {
	live: ['events', 'convoy', 'traces'],
	decide: ['enforcement'],
	reported: ['osint'],
	planned: ['events'],
};

/** The layers on when the map opens (no share link): §5.6's five, plus the live city — traffic on every road (its
 *  colour, moving dots and names), the ANPR cameras, the field units and their dispatches (108 corridors), the City
 *  Pack's named places, the live readings at their places (pumps, tide, heat, rivers, fires, fresh situations) and
 *  air quality at the monitoring sites — so the map opens alive and labelled; each stays a switch in the sheet. */
export const V3_DEFAULT_LAYERS: readonly string[] = ['events', 'convoy', 'traces', 'enforcement', 'osint', 'flow', 'cameras', 'units', 'dispatch', 'waterlog', 'landmarks', 'livevalues', 'air'];

/** The layers the map starts OFF (each one a switch in the Layers sheet). */
export const V3_OFF_LAYERS: readonly string[] = ['signals', 'anomalies', 'places', 'forecast', 'cyclone'];

/** The sheet rows that open ON (the live city): every other sheet row starts off. */
export const V3_SHEET_ON: readonly string[] = ['units', 'dispatch', 'cameras', 'flow', 'landmarks', 'livevalues', 'waterlog', 'air'];

/** Each group layer's wanted state for the chips' on/off set: on while ANY group drawing it is on. */
export function groupLayerState(on: Readonly<Record<GroupId, boolean>>): Record<string, boolean> {
	const out: Record<string, boolean> = {};
	for (const g of GROUP_IDS) for (const id of GROUP_LAYERS[g]) out[id] = (out[id] ?? false) || !!on[g];
	return out;
}

export interface SheetRow {
	id: string;
	key: string;
}

export interface SheetSection {
	key: string;
	rows: readonly SheetRow[];
}

/** The Layers sheet below the base-map choice (§5.6). */
export const SHEET: readonly SheetSection[] = [
	{
		key: 'v3m_ops',
		rows: [
			{ id: 'units', key: 'v3m_l_units' },
			{ id: 'dispatch', key: 'v3m_l_dispatch' },
		],
	},
	{
		key: 'v3m_city',
		rows: [
			{ id: 'cameras', key: 'v3m_l_cameras' },
			{ id: 'signals', key: 'v3m_l_signals' },
			{ id: 'flow', key: 'v3m_l_flow' },
			{ id: 'landmarks', key: 'v3m_l_landmarks' },
			{ id: 'livevalues', key: 'v3m_l_livevalues' },
			{ id: 'places', key: 'v3m_l_places' },
			{ id: 'anomalies', key: 'v3m_l_anomalies' },
		],
	},
	{
		// the on-prem AI services ($lib/ai): the waterlogging nowcast (on by default) and the corridor forecast
		key: 'ai_sheet',
		rows: [
			{ id: 'waterlog', key: 'ai_l_waterlog' },
			{ id: 'forecast', key: 'ai_l_forecast' },
		],
	},
	{
		// the open city feeds ($lib/cityfeeds): air quality at the monitoring sites and the active cyclone (both off)
		key: 'cf_sheet',
		rows: [
			{ id: 'air', key: 'cf_l_air' },
			{ id: 'cyclone', key: 'cf_l_cyclone' },
		],
	},
];

/** The AI layers' rows in the sheet: what each holds now, in its own words (pack keys of $lib/ai/packs.ai). */
export function aiLayerSub(
	id: string,
	row: { visible: boolean; count: number; error: string | null; detail?: Record<string, number> } | undefined,
	hindsightOn: boolean,
	L: (key: string, ...args: unknown[]) => string,
): string | null {
	const feeds = feedLayerSub(id, row, L);
	if (feeds != null) return feeds;
	if (id !== 'waterlog' && id !== 'forecast') return null;
	if (!row) return L('v3m_l_none');
	if (!row.visible) return L(id === 'waterlog' ? 'ai_l_waterlog_about' : 'ai_l_forecast_about');
	if (row.error) return L('v3m_l_feed');
	if (id === 'waterlog') return hindsightOn ? L('ai_l_waterlog_hs', row.count) : row.count ? L('ai_l_waterlog_sub', row.count) : L('ai_l_waterlog_dry');
	return row.count ? L('ai_l_forecast_sub', row.count) : L('ai_l_forecast_none');
}

export const SHEET_LAYER_IDS: readonly string[] = SHEET.flatMap((s) => s.rows.map((r) => r.id));

// ── the Now list ─────────────────────────────────────────────────────────

export type RightTone = 'route' | 'alert' | 'neutral' | 'decide';

export interface NowItem {
	/** Unique in the list (a decision's unit key; an object's urn otherwise). */
	key: string;
	group: GroupId;
	/** What a click selects on the map (one selection everywhere). */
	urn: string | null;
	art: string;
	kind: string;
	title: string;
	plate: PlateVM | null;
	meta: string;
	/** The right-hand state word (Live / Open / Active), or null (a decision shows its timer instead). */
	right: { text: string; tone: RightTone } | null;
	/** A decision's deadline / waiting-since (epoch ms). */
	deadline: number | null;
	since: number | null;
	/** Decisions waiting on this object (one orange dot). */
	decisions: number;
	/** The object's one home for "Review" (a decision's /decide/<unit>), else null. */
	review: string | null;
	prov: TagVM | null;
}

const toneOf = (tag: TagVM): RightTone => (tag.tone === 'route' ? 'route' : tag.tone === 'alert' ? 'alert' : tag.tone === 'decide' ? 'decide' : 'neutral');

export function nowFromOp(vm: OpVM, review: string | null): NowItem {
	return {
		key: vm.key,
		group: 'live',
		urn: vm.key,
		art: vm.art,
		kind: vm.kindLine,
		title: vm.title,
		plate: null,
		meta: vm.meta || vm.next,
		right: { text: vm.state.text, tone: toneOf(vm.state) },
		deadline: null,
		since: null,
		decisions: vm.decisions,
		review,
		prov: vm.prov,
	};
}

export function nowFromDecision(vm: DecisionVM, subjectUrn: string): NowItem {
	return {
		key: vm.key,
		group: 'decide',
		urn: subjectUrn,
		art: vm.art,
		kind: vm.kindLine,
		title: vm.title,
		plate: vm.plate,
		meta: [vm.kindLine, vm.by.text].filter(Boolean).join(' · '),
		right: null,
		deadline: vm.deadline,
		since: vm.since,
		decisions: 1,
		review: vm.href,
		prov: vm.prov,
	};
}

export function nowFromReport(vm: ReportVM, review: string | null): NowItem {
	return {
		key: vm.key,
		group: 'reported',
		urn: vm.key,
		art: vm.art,
		kind: vm.kindLine,
		title: vm.title,
		plate: null,
		meta: vm.cred != null ? `${vm.verif.text} · ${vm.cred.toFixed(2)}` : vm.verif.text,
		right: null,
		deadline: null,
		since: null,
		decisions: review ? 1 : 0,
		review,
		prov: null,
	};
}

export function nowFromPlanned(vm: PlannedVM): NowItem {
	return {
		key: vm.key,
		group: 'planned',
		urn: vm.key,
		art: vm.art,
		kind: vm.kindLine,
		title: vm.title,
		plate: null,
		meta: vm.when && vm.when !== '—' ? vm.when : vm.meta || vm.next,
		right: null,
		deadline: null,
		since: null,
		decisions: 0,
		review: null,
		prov: vm.prov,
	};
}

/** The item the selection card shows: the officer's row while it still names the selection, else the best match. */
export function pickItem(items: readonly NowItem[], selKey: string | null, urn: string | null): NowItem | null {
	if (!urn) return null;
	const mine = selKey ? items.find((i) => i.key === selKey && i.urn === urn) : null;
	if (mine) return mine;
	for (const g of ['live', 'reported', 'planned', 'decide'] as const) {
		const hit = items.find((i) => i.group === g && i.urn === urn);
		if (hit) return hit;
	}
	return null;
}

// ── the selection card's figures ─────────────────────────────────────────

export interface Stat {
	value: string;
	label: string;
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v.trim() : null);

/**
 * A protected movement's three figures from its convoy's feed: the ETA, how much of the route is done, the time to
 * the next junction. Only what the feed reports — a missing figure is left out, never guessed.
 */
export function movementStats(
	props: Readonly<Record<string, unknown>> | null | undefined,
	now: number,
	fmt: { time: (ms: number) => string; dur: (sec: number) => string },
	L: (key: string, ...args: unknown[]) => string,
): Stat[] {
	if (!props) return [];
	const out: Stat[] = [];
	const eta = num(props.eta_sec);
	if (eta != null) out.push({ value: fmt.time(now + eta * 1000), label: L('v3m_stat_eta', str(props.destination_name) ?? '') });
	const p = num(props.progress_pct) ?? num(props.progress);
	if (p != null) out.push({ value: `${Math.round(p <= 1 ? p * 100 : p)} %`, label: L('v3m_stat_done') });
	const nextIn = num(props.next_junction_in_sec);
	const junction = str(props.next_junction_name);
	if (nextIn != null && junction) out.push({ value: fmt.dur(nextIn), label: L('v3m_stat_to', junction) });
	else {
		const speed = num(props.speed_kmh);
		if (speed != null) out.push({ value: `${Math.round(speed)} km/h`, label: L('v3m_stat_speed') });
	}
	return out.slice(0, 3);
}

/** One section of the corridor stats panel. */
export interface StatSection {
	key: string;
	title: string;
	figures: Stat[];
	tags: TagVM[];
	note: string | null;
}

/** The corridor summary's figures (oracle): average speed, congestion, roads congested / critical — or why there are none. */
export function trafficFigures(
	row: { avgSpeedKmh: number; avgCongestionIdx: number; congestedSegments: number; criticalSegments: number; totalSegments: number; status: string } | null,
	L: (key: string, ...args: unknown[]) => string,
): { figures: Stat[]; note: string | null } {
	if (!row) return { figures: [], note: L('v3m_stats_unread') };
	if (row.status === 'no_data') return { figures: [], note: L('v3m_stats_nodata') };
	return {
		figures: [
			{ value: `${Math.round(row.avgSpeedKmh)} km/h`, label: L('v3m_stats_speed') },
			{ value: `${Math.round(row.avgCongestionIdx * 100)} %`, label: L('v3m_stats_congestion') },
			{ value: `${row.congestedSegments} / ${row.totalSegments}`, label: L('v3m_stats_congested') },
			{ value: String(row.criticalSegments), label: L('v3m_stats_critical') },
		],
		note: null,
	};
}

/** Every figure string an overlay shows, to prove the stats panel repeats none of the chips' or the card's. */
export function repeatedFigures(a: readonly Stat[], b: readonly Stat[]): string[] {
	const key = (s: Stat) => `${s.value}|${s.label}`;
	const seen = new Set(a.map(key));
	return b.map(key).filter((k) => seen.has(k));
}

// ── replay, details, weather ─────────────────────────────────────────────

/** Replay waits while live work runs (v2 §7.3): the reason's pack key, or null when replay may open. */
export function replayBlock(events: readonly { eventKind: string; state: string | null | undefined; source?: string | null }[]): string | null {
	const live = events.filter((e) => e.source !== 'offline-fixture' && e.state === 'active');
	if (live.some((e) => e.eventKind === 'protected_movement')) return 'v3m_replay_live_move';
	if (live.some((e) => e.eventKind === 'vehicle_pursuit')) return 'v3m_replay_live_pursuit';
	return null;
}

/** "Details": the object's page (/o/<urn>, V3-P3), else Analyst's inspector. Never a mark in the URL. */
export function detailsHref(urn: string): string {
	return objectHref(urn) ?? `/analyst#items=${encodeURIComponent(urn)}`;
}

/** An OSINT report that is an OFFICIAL district-level weather warning (the chip, never a ring on the map). */
export function isOfficialWeather(e: { verificationState: string | null; label: string; props: Readonly<Record<string, unknown>> }): boolean {
	const official = e.verificationState === 'OFFICIAL-VERIFIED' || e.verificationState === 'CONFIRMED';
	const cls = `${str(e.props.sajag_event_kind) ?? ''} ${str(e.props.event_class) ?? ''} ${e.label}`;
	return official && /weather|rain|storm|heat|cyclone|district warning/i.test(cls);
}

/** The thermal-style palettes (the canvas's sensor modes, raw = normal colours). */
export const THERMAL_MODES = ['flir-whot', 'flir-bhot', 'flir-iron'] as const;
export const THERMAL_PALETTE_KEY: Readonly<Record<string, string>> = { 'flir-whot': 'map_pal_whot', 'flir-bhot': 'map_pal_bhot', 'flir-iron': 'map_pal_iron' };

/** The tool click's next sensor: off → the last thermal palette used (white-hot first); on → normal colours. */
export function nextSensor(current: string, lastThermal: string | null): string {
	if (current !== 'raw') return 'raw';
	return lastThermal && (THERMAL_MODES as readonly string[]).includes(lastThermal) ? lastThermal : 'flir-whot';
}

/** The map's keyboard (§7.1): L layers, F follow, 3 the 3D city; never a key that approves, unmasks or dispatches. */
export function mapKey(e: { key: string; ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean }, typing: boolean): 'layers' | 'follow' | '3d' | null {
	if (typing || e.ctrlKey || e.metaKey || e.altKey) return null;
	const k = e.key.toLowerCase();
	return k === 'l' ? 'layers' : k === 'f' ? 'follow' : k === '3' ? '3d' : null;
}

const VEHICLE_ART = new Set(['ambulance', 'auto_rickshaw', 'bus', 'car', 'fire_tender', 'patrol', 'suv', 'tempo', 'truck', 'two_wheeler']);
const AGENCY_ART: Readonly<Record<string, string>> = { police: 'police', traffic: 'traffic', ambulance: 'ems', ems: 'ems', '108': 'ems', fire: 'fire', municipal: 'municipal', disaster: 'disaster', sdrf: 'disaster', ndrf: 'disaster' };

/**
 * The illustration for an object the map picked that the Now list does not hold (a camera, a unit, a vehicle):
 * vehicle-class silhouettes for vehicles (never a person), generic agency marks for units and infrastructure.
 */
export function entityArt(kind: string, props: Readonly<Record<string, unknown>>, eventArt: (k: string | null) => string): string {
	switch (kind) {
		case 'vehicle': {
			const cls = str(props.vehicle_class)?.toLowerCase().replace(/[^a-z_]/g, '_') ?? 'car';
			return `/illustrations/vehicles/${VEHICLE_ART.has(cls) ? cls : 'car'}.svg`;
		}
		case 'unit':
		case 'dispatch': {
			const a = (str(props.agency) ?? '').toLowerCase();
			return `/illustrations/agencies/${AGENCY_ART[a] ?? (kind === 'dispatch' ? 'ems' : 'control_room')}.svg`;
		}
		case 'camera':
		case 'sighting':
		case 'junction':
		case 'segment':
		case 'recommendation':
			return '/illustrations/agencies/traffic.svg';
		case 'anomaly':
			return '/illustrations/agencies/control_room.svg';
		case 'convoy':
			return eventArt('protected_movement');
		case 'osint_event':
			return eventArt(str(props.sajag_event_kind) ?? str(props.event_class));
		default:
			return eventArt(str(props.event_kind) ?? null);
	}
}

/** A picked object that stands for a Now row (a convoy is its movement's operation). */
export function aliasUrn(urn: string | null, props: Readonly<Record<string, unknown>> | null | undefined): string | null {
	if (!urn) return null;
	if (urn.startsWith('convoy:')) {
		const ev = str(props?.event_id);
		if (ev) return `event:${ev}`;
	}
	return urn;
}
