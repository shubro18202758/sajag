/**
 * The V3 Map string pack (V3-SPEC §5.6, §6.5, §7.8) — every string /map prints that the canvas's own map pack
 * (packs.map, loaded with the canvas: the tool names, the thermal-style copy, zoom, north) and the V3 pack
 * (packs.v3: kinds, states, provenance) do not already say. EN here; HI and MR in ./packs.map3.hi.ts and
 * ./packs.map3.mr.ts, complete for every key (tests/v3-map.unit.mjs checks it). Registered additively through
 * registerPack(); loaded only by /map (never on /gods-eye, /, /ops). Every key starts with `v3m_`.
 *
 * Copy rules (v2 §11 + V3 §7.6): sentence case, no ALL-CAPS word outside the acronym list, at most one " · " per
 * string, titles ≤ 32 characters. Honest labels: a simulated feed says so, emulated units say so, the photoreal
 * city is "not a live image", the thermal-style view is "a visual filter, no thermal sensor". Numbers and times
 * stay in Latin digits in all three languages.
 */
import { registerPack } from '$lib/i18n/strings';
import { langChunks } from '$lib/i18n/load';

type Fn = (...args: unknown[]) => string;
export type MapPack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');
const n = (v: unknown) => Number(v);

const en = {
	// ── the screen ──
	v3m_title: 'Map',
	v3m_sub: (city: unknown) => `${s(city)} · clean by default, layers on demand`,
	v3m_map_alt: 'Map of the city: live operations, decisions waiting and reported events. The Now list beside it holds the same objects.',
	v3m_loading: 'Loading the map',

	// ── the four group chips (and the Now list's groups) ──
	v3m_grp_live: 'Live operations',
	v3m_grp_decide: 'Needs your decision',
	v3m_grp_reported: 'Reported in the city',
	v3m_grp_planned: 'Coming up',
	v3m_chip_on: 'On the map. Select to hide it.',
	v3m_chip_off: 'Hidden on the map. Select to show it.',
	v3m_layers: 'Layers',
	v3m_layers_on: (k: unknown) => `${s(k)} on`,

	// ── the weather chip ──
	v3m_wx_official: 'Official weather warning',

	// ── the Now panel ──
	v3m_now: 'Now',
	v3m_now_live: (at: unknown) => `Live · ${s(at)} IST`,
	v3m_now_replay: 'Replaying a recorded tape',
	v3m_now_empty: 'Nothing here right now',
	v3m_now_list: 'What is on the map',
	v3m_replay: 'Replay',
	v3m_replay_live_move: 'A movement is live. Replay opens when it ends.',
	v3m_replay_live_pursuit: 'A pursuit is open. Replay opens when it closes.',
	v3m_replay_back: 'Back to live',
	v3m_replay_note: 'Every replayed object is emulated. Decisions stay live.',
	v3m_left: (at: unknown) => `${s(at)} left`,
	v3m_waiting: (at: unknown) => `waiting ${s(at)}`,
	v3m_cred: (c: unknown) => `credibility ${s(c)}`,
	v3m_emulated_word: 'emulated',

	// ── the selection card ──
	v3m_close: 'Close',
	v3m_review: 'Review',
	v3m_review_hold: 'Review the hold',
	v3m_review_request: 'Review the request',
	v3m_follow: 'Follow',
	v3m_following: 'Following',
	v3m_details: 'Details',
	v3m_details_tip: 'Opens the object in Analyst',
	v3m_sel_object: 'On the map',
	v3m_stat_eta: (place: unknown) => (s(place) ? `ETA ${s(place)}` : 'ETA'),
	v3m_stat_done: 'of the route done',
	v3m_stat_to: (place: unknown) => `to ${s(place)}`,
	v3m_stat_speed: 'speed',
	v3m_stat_since_read: 'since the last read',
	v3m_stat_last_speed: 'last speed',
	v3m_stat_reads: 'reads',
	v3m_stat_cred: 'credibility',
	v3m_stat_reported: 'reported',
	v3m_stat_publishers: 'publishers',
	v3m_stat_starts: 'starts',
	v3m_stat_ends: 'ends',
	v3m_kind_camera: 'ANPR camera',
	v3m_kind_junction: 'Junction',
	v3m_kind_unit: 'Unit',
	v3m_kind_vehicle: 'Vehicle',
	v3m_kind_sighting: 'Camera read',
	v3m_kind_convoy: 'Convoy',
	v3m_kind_dispatch: 'Dispatch',
	v3m_kind_recommendation: 'Penalty recommendation',
	v3m_kind_anomaly: 'Feed check',
	v3m_kind_place: 'Place',
	v3m_kind_segment: 'Road',
	v3m_kind_event: 'Event',
	v3m_kind_osint_event: 'Reported event',

	// ── the tools ──
	v3m_tools: 'Map tools',
	v3m_3d: 'Satellite 3D',
	v3m_3d_on: 'Switch to satellite 3D',
	v3m_3d_off: 'Switch to the city map',
	v3m_thermal_on: 'Thermal-style view: a visual filter, no thermal sensor',
	v3m_thermal_palette: 'Palette',

	// ── the layers sheet ──
	v3m_sheet: 'Layers',
	v3m_sheet_close: 'Close the layers',
	v3m_base: 'Base map',
	v3m_base_city: 'City map',
	v3m_base_3d: 'Satellite 3D',
	v3m_ops: 'Operations',
	v3m_city: 'City',
	v3m_l_units: 'Units',
	v3m_l_dispatch: 'Dispatches',
	v3m_l_cameras: 'ANPR cameras',
	v3m_l_signals: 'Junctions and signals',
	v3m_l_flow: 'Traffic flow',
	v3m_l_landmarks: 'City places',
	v3m_l_landmarks_about: 'Landmarks, areas, stations and hospitals',
	v3m_l_landmarks_sub: (k: unknown) => `${s(k)} places from the City Pack`,
	v3m_l_livevalues: 'Live readings',
	v3m_l_livevalues_about: 'Pumps, tide, heat, rivers and fresh reports',
	v3m_l_livevalues_sub: (k: unknown) => `${s(k)} readings at their places`,
	v3m_l_places: 'Named places',
	v3m_l_anomalies: 'Feed checks',
	v3m_l_count: (k: unknown) => `${s(k)} on the map`,
	v3m_l_cameras_sub: (k: unknown) => `${s(k)} · read registration marks only`,
	v3m_l_flow_sim: (k: unknown) => `Simulated on ${s(k)} roads`,
	v3m_l_places_sub: 'Reference geography',
	v3m_l_units_about: 'Police, traffic and 108 units',
	v3m_l_dispatch_about: 'Units sent to a place, and their way there',
	v3m_l_cameras_about: 'Read registration marks only',
	v3m_l_signals_about: 'Signal state at each junction',
	v3m_l_flow_about: 'How fast each road is moving',
	v3m_l_places_about: 'Reference geography',
	v3m_l_anomalies_about: 'Where a feed is misbehaving',
	v3m_l_none: 'None right now',
	v3m_l_paused: 'Paused during the replay',
	v3m_l_feed: 'Feed problem',
	v3m_vehicles_only: 'Vehicles only. Cameras read registration marks; no images, frames or faces are kept.',

	// ── the legend and the credits ──
	v3m_stats: 'Corridor stats',
	v3m_stats_close: 'Close the corridor stats',
	v3m_stats_band: 'Signal band',
	v3m_stats_since: (at: unknown) => `since ${s(at)} IST`,
	v3m_stats_band_stale: 'The band reading is not current.',
	v3m_stats_band_none: 'No band reported yet.',
	v3m_stats_traffic: 'Traffic on the corridors',
	v3m_stats_speed: 'average speed',
	v3m_stats_congestion: 'congestion',
	v3m_stats_congested: 'roads congested',
	v3m_stats_critical: 'roads critical',
	v3m_stats_nodata: 'No fresh traffic reading.',
	v3m_stats_unread: 'Not read yet.',
	v3m_stats_age: (ago: unknown) => `Read ${s(ago)}.`,
	v3m_stats_escorts: 'Escorts',
	v3m_stats_following: 'movements followed',
	v3m_stats_answered: 'proposals answered',
	v3m_stats_no_escort: 'No escort is running.',
	v3m_stats_gps_emulated: 'GPS emulated',
	v3m_prov_mixed: 'Partly simulated',
	v3m_stats_analyst: 'Full analysis in Analyst',
	v3m_focus: (title: unknown) => `Focused on ${s(title)}`,
	v3m_show_all: 'Show all',
	v3m_show_all_tip: 'Back to the whole city',
	v3m_legend_hide: 'Hide the legend',
	v3m_legend: 'Legend',
	v3m_lg_decide: 'A decision waits',
	v3m_lg_alert: 'Stolen or watchlisted vehicle',
	v3m_lg_flow: 'Road colour: green free, amber slow, red jammed',
	v3m_lg_dots: 'Moving dots: traffic on the simulated feed, 20× speed',
	v3m_lg_units: 'Field units on real roads (emulated)',
	v3m_lg_pulse: 'Pulse: reported in the last 20 min',
	v3m_lg_updated: (at: unknown) => `Map data updated ${s(at)} IST`,
	v3m_lg_waiting: 'Waiting for the first reading',
	v3m_lg_route: 'Protected route',
	v3m_credit_osm: 'Map data © OpenStreetMap contributors',
	v3m_credit_3d: 'Photoreal 3D city from Google, via Cesium ion · not a live image',
	v3m_credit_3d_loading: 'Loading the 3D city. The flat map shows until it arrives.',
	v3m_offline: 'Map tiles are not answering. The roads are drawn from Sajag’s own network.',
	v3m_signin: 'Sign in to open the map',
	v3m_items: (k: unknown) => `${s(k)} ${n(k) === 1 ? 'item' : 'items'}`,
};

export type MapKey = keyof typeof en;

registerPack('en', en);

export const MAP3_PACK_KEYS: readonly MapKey[] = Object.keys(en) as MapKey[];
export const MAP3_PACKS: Record<string, MapPack> = { en };

/** Register one language chunk (lib/i18n/load.ts's landing site; additive, first registration wins). */
export function adopt(code: 'hi' | 'mr', pack: MapPack): void {
	MAP3_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (the deck's FIX-E-PERF2 pattern, as packs.v3): HI and MR live only in their own files.
 * The server render and every non-production run register both before this module finishes evaluating;
 * the production browser awaits the document's language and loads the other on the first switch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.map3.hi')).hi);
	adopt('mr', (await import('./packs.map3.mr')).mr);
} else {
	await langChunks('packs.map3', (code) =>
		code === 'hi' ? import('./packs.map3.hi').then((c) => adopt('hi', c.hi)) : import('./packs.map3.mr').then((c) => adopt('mr', c.mr)),
	);
}
