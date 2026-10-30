/**
 * Home's view models (V3-SPEC §5.2, §6.1) — built ONLY from the deck's existing stores and selectors
 * (no new endpoint): the decision units (decisions/units.ts) and their shared words (decisions/cards/
 * meta.ts), the ops store (board events, escorts, dispatches, the city band, the traffic feed, the
 * officer and the C6 plate rule), the city registry (OSINT reports, places, convoys, sightings,
 * cameras) and the road geometry the ops store already loads (ops.segmentLines).
 *
 * Honesty rules applied here, once:
 *   - every registration mark goes through ops.plate / ops.text (raw only for a named duty officer);
 *     a unit's stored title is already masked;
 *   - a figure is shown only when the feed reports it (a convoy's ETA, a hold's length); nothing is
 *     invented to fill a card;
 *   - one provenance tag per card: EMULATED (the emulator made it), SIMULATED (its numbers come from a
 *     simulated feed), TEST (a rehearsal row);
 *   - who proposed it is said in words (the convoy assistant only when a model proposed it — a
 *     deterministic rule is never labelled AI).
 */
import type { CityEntity } from '$lib/gods-eye/city-api';
import type { CorridorEvent } from '$lib/ops/types';
import { ops } from '$lib/ops/store.svelte';
import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
import { unitKey as homeUnitKey } from '$lib/decisions/homes';
import { corridorOf, dssOf, echallanOf, escortOf, pursuitOf, stolenOf, unitEmulated, unitTitle, type Unit } from '$lib/decisions/units';
import { escortRule, timeBoxed, waitingSince } from '$lib/decisions/cards/meta';
import { eventTestLabel } from '$lib/corridor/events';
import { safePathId } from '$lib/ops/endpoints';
import { WORKSPACE_URL } from '$lib/shell/root-flip';
import { readableIn, scriptOf } from '$lib/i18n/script';
import { t } from '$lib/i18n/strings';
import { tOps } from '$lib/i18n/strings.ops';
import '$lib/i18n/packs.decisions';
import '$lib/i18n/packs.dss';
import '../packs.v3';
import { fmtAgo, fmtDuration, fmtRange, fmtStamp, fmtTime } from '$lib/ui/format/format';
import type { LonLat } from '../map/mercator';
import type { ThumbOverlay, ThumbPoint } from '../map/overlay';
import { artFor, glyphFor, splitLabel, unitKey } from './model';
import { objectHref } from '../object/model';
import { keyArt, keyArtKind } from '../media/art';
import '../media/packs.media';
import { photoForText, photoNear, type PlacePhoto } from '../media/photos';
import { HUMAN } from '$lib/workspace/vocabulary';

export type Tone = 'decide' | 'ai' | 'alert' | 'ok' | 'route' | 'neutral' | 'dashed' | 'ghost' | 'brand';

export interface TagVM {
	text: string;
	tone: Tone;
	glyph?: string;
	title?: string;
}

export interface FactVM {
	value: string;
	label: string;
}

export interface ThumbVM {
	overlay: ThumbOverlay;
	alt: string;
	zoom?: number;
	/** Frame the points only (the route runs on past the edge). */
	frameOn?: 'all' | 'points';
}

/** The picture at the top of a card: the kind's key art, or a credited reference photo of the place. */
export interface CoverVM {
	art: string;
	photo: PlacePhoto | null;
	alt: string;
}

/** What a decision card shows over the corner of its map: the vehicle class's studio shot, or the kind's key art. */
export type InsetVM = { kind: 'vehicle'; cls: string } | { kind: 'art'; art: string } | null;

export interface PlateVM {
	mark: string;
	masked: boolean;
}

export interface DecisionVM {
	key: string;
	kind: string;
	kindLine: string;
	title: string;
	plate: PlateVM | null;
	why: string;
	by: { text: string; ai: boolean };
	art: string;
	href: string;
	deadline: number | null;
	since: number | null;
	timeBoxed: boolean;
	prov: TagVM | null;
	thumb: ThumbVM;
	inset: InsetVM;
	facts: FactVM[];
	ifNot: string;
	/** For the alert list: the stored, masked title. */
	maskedTitle: string;
	emulated: boolean;
}

export interface OpVM {
	key: string;
	kindLine: string;
	title: string;
	state: TagVM;
	meta: string;
	progress: number | null;
	next: string;
	art: string;
	href: string;
	prov: TagVM | null;
	thumb: ThumbVM;
	cover: CoverVM;
	decisions: number;
}

export interface ReportVM {
	key: string;
	kindLine: string;
	title: string;
	verif: TagVM;
	meta: string;
	cred: number | null;
	note: string;
	art: string;
	href: string;
	thumb: ThumbVM;
	cover: CoverVM;
	/** The publisher of the first source (its mark when one is on file). */
	source: string | null;
}

export interface PulseStat {
	id: string;
	n: number;
	label: string;
	sub: string;
	href: string;
	decide?: boolean;
}

export interface PlannedVM {
	key: string;
	kindLine: string;
	title: string;
	when: string;
	meta: string;
	next: string;
	art: string;
	href: string;
	prov: TagVM | null;
	thumb: ThumbVM;
	cover: CoverVM;
}

// ── geometry from the stores ─────────────────────────────────────────────

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v.trim() : null);
const pos = (e: { lon: number | null; lat: number | null } | null | undefined): LonLat | null =>
	e && e.lon != null && e.lat != null && Number.isFinite(e.lon) && Number.isFinite(e.lat) ? [e.lon, e.lat] : null;

function segmentMap(): Map<number, LonLat[]> {
	const m = new Map<number, LonLat[]>();
	for (const s of ops.segmentLines) if (s.coordinates?.length >= 2) m.set(s.segmentId, s.coordinates as LonLat[]);
	return m;
}

const d2 = (a: LonLat, b: LonLat) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2;

/** Segments chained in route order: each one turned so it starts where the last one ended. */
export function chain(ids: readonly number[], segs: Map<number, LonLat[]>): LonLat[] {
	const out: LonLat[] = [];
	for (const id of ids) {
		const s = segs.get(id);
		if (!s?.length) continue;
		let pts = s;
		if (out.length) {
			const end = out[out.length - 1];
			if (d2(end, s[s.length - 1]) < d2(end, s[0])) pts = [...s].reverse();
		} else {
			const next = ids.map((i) => segs.get(i)).find((x, i) => i > 0 && x?.length);
			if (next && Math.min(d2(s[0], next[0]), d2(s[0], next[next.length - 1])) < Math.min(d2(s[s.length - 1], next[0]), d2(s[s.length - 1], next[next.length - 1])))
				pts = [...s].reverse();
		}
		out.push(...(out.length ? pts.slice(1) : pts));
	}
	return out;
}

/** Split a route at the point nearest `at`: [travelled, ahead]. */
function splitAt(route: LonLat[], at: LonLat | null): [LonLat[], LonLat[]] {
	if (!at || route.length < 2) return [[], route];
	let best = 0;
	for (let i = 1; i < route.length; i++) if (d2(route[i], at) < d2(route[best], at)) best = i;
	return [[...route.slice(0, best + 1), at], [at, ...route.slice(best + 1)]];
}

function eventPos(ev: CorridorEvent, segs: Map<number, LonLat[]>): LonLat | null {
	if (ev.geotag) return [ev.geotag.lon, ev.geotag.lat];
	const ent = pos(cityRegistry.get(`event:${ev.eventId}`));
	if (ent) return ent;
	const route = chain(ev.routeSegmentIds, segs);
	return route.length ? route[Math.floor(route.length / 2)] : null;
}

function convoyFor(ev: CorridorEvent | null, movementId: string | null): CityEntity | null {
	const mv = movementId ?? ev?.movementId ?? null;
	return cityRegistry.byKind('convoy').find((c) => (mv && (c.props.movement_id === mv || c.id === mv)) || (!mv && false)) ?? null;
}

function trailOf(vehicleId: string): LonLat[] {
	const urn = `vehicle:${vehicleId}`;
	return cityRegistry
		.byKind('sighting')
		.filter((s) => s.links.includes(urn) || s.props.vehicle_id === vehicleId)
		.sort((a, b) => (a.t ?? 0) - (b.t ?? 0))
		.map(pos)
		.filter((p): p is LonLat => !!p);
}

function trailOverlay(points: LonLat[], decide: boolean, label?: string | null): ThumbOverlay {
	if (!points.length) return {};
	const newest = points[points.length - 1];
	return {
		lines: points.length > 1 ? [{ coords: points, style: 'trail' }] : [],
		points: [
			...points.slice(0, -1).map((p): ThumbPoint => ({ at: p, small: true })),
			{ at: newest, glyph: 'car', tone: 'alert', decide, halo: true, label: label ?? null },
		],
	};
}

// ── provenance ───────────────────────────────────────────────────────────

function provTag(lang: string, kind: 'emulated' | 'simulated' | 'test' | null): TagVM | null {
	if (!kind) return null;
	return {
		text: t(lang, `v3_prov_${kind}`),
		tone: 'dashed',
		glyph: kind === 'simulated' ? 'shuffle' : 'flask',
		title: t(lang, `v3_prov_${kind}_tip`),
	};
}

function eventProv(ev: CorridorEvent, lang: string): TagVM | null {
	if (eventTestLabel(ev) && /test|rehears|drill/i.test(eventTestLabel(ev) ?? '')) return provTag(lang, 'test');
	return ev.emulated ? provTag(lang, 'emulated') : null;
}

// ── decision units ───────────────────────────────────────────────────────

const KIND_LINE: Record<string, string> = {
	'escort-proposal': 'v3_kind_escort',
	dss: 'v3_kind_dss',
	'stolen-sighting': 'v3_kind_stolen',
	pursuit: 'v3_kind_pursuit',
	echallan: 'v3_kind_echallan',
	'corridor-request': 'v3_kind_corridor',
};

function plateVM(raw: string | null | undefined): PlateVM | null {
	const shown = ops.plate(raw);
	return shown ? { mark: shown, masked: !ops.officerOn } : null;
}

/** One decision unit as Home shows it (card and hero share it). */
/** The IST hour (picks the riverfront photo's time of day). */
function istHour(now: number): number {
	return Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Asia/Kolkata' }).format(now));
}

/** A cover: a reference photo of the place when one is near (or named), else the kind's key art. */
export function coverFor(kind: string | null | undefined, at: LonLat | null, text: string | null, lang: string, now: number, photos = true): CoverVM {
	const h = istHour(now);
	const photo = photos ? (at ? photoNear(at[0], at[1], 900, h) : null) ?? photoForText(text, h) : null;
	return { art: keyArt(kind), photo, alt: t(lang, 'v3i_art_alt', kindWord(keyArtKind(kind), lang)) };
}

/** The vehicle class a decision is about (the watchlisted car, the 108 unit, the convoy). */
function decisionInset(u: Unit): InsetVM {
	switch (u.kind) {
		case 'escort-proposal':
			return { kind: 'vehicle', cls: 'convoy' };
		case 'stolen-sighting':
		case 'pursuit':
		case 'echallan':
			return { kind: 'vehicle', cls: 'car' };
		case 'corridor-request':
			return { kind: 'vehicle', cls: 'ambulance' };
		case 'dss': {
			const d = dssOf(u);
			return { kind: 'art', art: keyArt(d.sajagEventKind ?? d.eventClass) };
		}
		default:
			return null;
	}
}

export function decisionVM(u: Unit, lang: string, now: number, segs = segmentMap()): DecisionVM {
	return { ...decisionCore(u, lang, now, segs), inset: decisionInset(u) };
}

function decisionCore(u: Unit, lang: string, now: number, segs: Map<number, LonLat[]>): Omit<DecisionVM, 'inset'> {
	// V3-P2: a decision's V3 home is /decide/<kind>:<id> (never a mark)
	const k = homeUnitKey(u.kind, u.id);
	const href = k ? `/decide/${encodeURIComponent(k)}` : '/decide';
	const kindLine = t(lang, KIND_LINE[u.kind] ?? 'v3_kind_decision');
	const base = {
		key: unitKey(u),
		kind: u.kind,
		kindLine,
		href,
		deadline: u.deadline,
		since: waitingSince(u),
		timeBoxed: timeBoxed(u),
		maskedTitle: u.title,
		emulated: unitEmulated(u),
		ifNot: t(lang, timeBoxed(u) ? 'v3_ifnot_escort' : u.kind === 'dss' ? 'v3_ifnot_expires' : 'v3_ifnot_waits'),
	};
	switch (u.kind) {
		case 'escort-proposal': {
			const d = escortOf(u);
			const p = d.proposal;
			const ev = d.event;
			const convoy = convoyFor(ev, p.movementId);
			const cpos = pos(convoy);
			const route = ev ? chain(ev.routeSegmentIds, segs) : [];
			const [done, ahead] = splitAt(route, cpos);
			const holdIds = p.proposed?.holdSegmentIds?.length ? p.proposed.holdSegmentIds : p.segmentIds;
			const hold = holdIds.length ? segs.get(holdIds[0]) : null;
			const junction = str(convoy?.props.next_junction_name);
			const holdAt: LonLat | null = hold ? (cpos && d2(hold[0], cpos) < d2(hold[hold.length - 1], cpos) ? hold[hold.length - 1] : hold[0]) : null;
			const pct = p.peakCongestion != null ? Math.round(p.peakCongestion * 100) : null;
			const roads = [...new Set(p.segmentIds.map((id) => ops.roadName(id) ?? `#${id}`))].slice(0, 3).join(', ');
			const nextIn = num(convoy?.props.next_junction_in_sec);
			const facts: FactVM[] = [];
			if (junction && nextIn != null) facts.push({ value: fmtDuration(nextIn, lang), label: t(lang, 'v3_fact_convoy_to', junction) });
			if (p.proposed?.maxHoldSec) facts.push({ value: fmtDuration(p.proposed.maxHoldSec, lang), label: t(lang, 'v3_fact_hold') });
			if (pct != null && facts.length < 2) facts.push({ value: `${pct}%`, label: t(lang, 'v3_fact_congestion') });
			const ai = !escortRule(u);
			return {
				...base,
				title: unitTitle(u, lang),
				plate: null,
				why: pct != null && roads ? t(lang, p.trigger === 'phase_transition' ? 'dec_why_escort_departure' : 'dec_why_escort', pct, roads) : t(lang, 'dec_why_escort_plain'),
				by: { text: t(lang, ai ? 'v3_by_ai' : 'v3_by_rule'), ai },
				art: artFor('protected_movement'),
				prov: provTag(lang, d.emulated ? 'emulated' : p.simulated ? 'simulated' : null),
				facts,
				thumb: {
					alt: t(lang, 'v3_map_alt', junction ?? (ev ? ops.text(ev.name) : t(lang, 'v3_kind_escort'))),
					frameOn: 'points',
					overlay: {
						lines: [
							...(done.length > 1 ? [{ coords: done, style: 'route-done' as const }] : []),
							...(ahead.length > 1 ? [{ coords: ahead, style: 'route' as const }] : []),
						],
						points: [
							...(holdAt ? [{ at: holdAt, glyph: 'signal', decide: true, halo: true, tone: 'neutral' as const, label: junction ?? (holdIds.length ? ops.roadName(holdIds[0]) : null) }] : []),
							...(cpos
								? [{ at: cpos, glyph: 'convoy', tone: 'route' as const, halo: true, label: nextIn != null ? t(lang, 'v3_map_convoy_in', fmtDuration(nextIn, lang)) : t(lang, 'v3_map_convoy') }]
								: []),
						],
					},
				},
			};
		}
		case 'stolen-sighting': {
			const d = stolenOf(u);
			const trail = trailOf(d.vehicleId);
			const last = trail.length ? null : pos(cityRegistry.get(`vehicle:${d.vehicleId}`));
			const road = str(d.newest.evidence?.road_name) ?? d.step.candidate?.anchor?.roadName ?? null;
			const at = d.newest.createdAt ? Date.parse(d.newest.createdAt) : NaN;
			const titleKey = !d.approved ? 'v3_title_stolen' : d.step.state === 'ready' ? 'v3_title_pursuit' : 'v3_title_stolen_after';
			const reads = trail.length || d.recs.length;
			const why = [
				d.fir ? t(lang, d.emulated ? 'dec_why_stolen_fir_demo' : 'dec_why_stolen_fir', d.fir) : t(lang, 'dec_why_stolen'),
				Number.isFinite(at) ? t(lang, road ? 'v3_why_reads_road' : 'v3_why_reads', reads, fmtAgo(at, now, lang), road) : null,
			]
				.filter(Boolean)
				.join(' ');
			return {
				...base,
				title: t(lang, titleKey),
				plate: plateVM(d.plate),
				why,
				by: { text: t(lang, 'v3_by_rules'), ai: false },
				art: artFor('crime_incident'),
				prov: provTag(lang, d.emulated ? 'emulated' : null),
				// how long ago the last read was is already the countdown slot's "waiting" (the newest sighting is the unit's age)
				facts: [{ value: String(reads), label: t(lang, 'v3_fact_reads') }],
				thumb: { alt: t(lang, 'v3_map_alt', road ?? t(lang, 'v3_kind_stolen')), overlay: trailOverlay(trail.length ? trail : last ? [last] : [], true) },
			};
		}
		case 'pursuit': {
			const d = pursuitOf(u);
			const s = d.candidate.vehicle.lastSighting;
			const at: LonLat | null = s ? [s.lon, s.lat] : null;
			return {
				...base,
				title: t(lang, 'v3_title_pursuit'),
				plate: plateVM(d.plate),
				why: [t(lang, 'dec_why_watchlisted'), s?.t ? t(lang, 'dec_why_last_read', fmtAgo(s.t, now, lang)) : null].filter(Boolean).join(' '),
				by: { text: t(lang, 'v3_by_rules'), ai: false },
				art: artFor('vehicle_pursuit'),
				prov: provTag(lang, d.emulated ? 'emulated' : null),
				facts: [],
				thumb: { alt: t(lang, 'v3_map_alt_plain'), overlay: trailOverlay(at ? [at] : [], true) },
			};
		}
		case 'echallan': {
			const d = echallanOf(u);
			const ent = cityRegistry.get(`recommendation:${d.rec.recommendationId}`);
			const at = pos(ent);
			return {
				...base,
				title: t(lang, d.stolen ? 'v3_title_echallan_stolen' : 'v3_title_echallan'),
				plate: plateVM(d.plate),
				why: echallanWhy(ops.text(d.rec.recommendation), lang) || t(lang, 'dec_why_echallan'),
				by: { text: t(lang, 'v3_by_rules'), ai: false },
				art: artFor('crime_incident'),
				prov: provTag(lang, d.emulated ? 'emulated' : null),
				facts: [],
				thumb: { alt: t(lang, 'v3_map_alt_plain'), overlay: at ? { points: [{ at, glyph: 'anpr', decide: true, halo: true }] } : {} },
			};
		}
		case 'corridor-request': {
			const d = corridorOf(u);
			const ds = d.dispatch;
			const ent = cityRegistry.get(`dispatch:${ds.dispatchId}`);
			const jn = ds.waypointJunction != null ? ops.junctions.find((j) => j.junctionId === ds.waypointJunction) : null;
			const at = pos(ent) ?? (jn ? ([jn.lon, jn.lat] as LonLat) : null);
			const by = ds.requestedBy === '108-driver' ? t(lang, 'v3_by_108') : t(lang, 'v3_by_officer');
			const wp = ds.waypointJunction != null ? ops.junctionName(ds.waypointJunction, lang) : null;
			return {
				...base,
				title: unitTitle(u, lang),
				plate: null,
				why: [
					t(lang, 'dec_why_corridor', agencyIn(ds.agency, ds.agencyLabel, lang), ds.unitId ?? '—', ds.requestedBy === '108-driver' ? tOps(lang, 'dispatch108') : requesterIn(ops.text(ds.requestedBy), lang) || '—', ds.createdAt ? fmtStamp(ds.createdAt, now) : '—'),
					wp ? t(lang, 'dec_why_corridor_waypoint', wp) : null,
				]
					.filter(Boolean)
					.join(' '),
				by: { text: by, ai: false },
				art: artFor('green_corridor'),
				prov: provTag(lang, d.emulated ? 'emulated' : null),
				facts: ds.unitId ? [{ value: ds.unitId, label: t(lang, 'v3_fact_unit') }] : [],
				thumb: { alt: t(lang, 'v3_map_alt', wp ?? t(lang, 'v3_kind_corridor')), overlay: at ? { points: [{ at, glyph: 'ambulance', decide: true, halo: true, label: wp }] } : {} },
			};
		}
		case 'dss': {
			const d = dssOf(u);
			const ent = cityRegistry.get(d.urn);
			const at = pos(ent);
			const cls = d.sajagEventKind ?? d.eventClass;
			const { title } = splitLabel(d.label);
			const why = d.situationSummary ? ops.text(d.situationSummary) : d.summary.topCoaLabel ? t(lang, 'dss_meta_top', d.summary.topCoaLabel) : t(lang, 'dss_by_engine');
			return {
				...base,
				title: ops.text(d.label),
				plate: null,
				why,
				by: { text: t(lang, 'v3_by_dss'), ai: false },
				art: artFor(cls),
				prov: null,
				facts: [
					...(d.credibility != null ? [{ value: d.credibility.toFixed(2), label: t(lang, 'v3_fact_credibility') }] : []),
					...(d.summary.topCoaLabel ? [{ value: d.summary.topCoaLabel, label: t(lang, 'v3_fact_recommended') }] : []),
				],
				thumb: { alt: t(lang, 'v3_map_alt', ops.text(title)), overlay: at ? { points: [{ at, glyph: glyphFor(cls), decide: true, halo: true }] } : {} },
			};
		}
		default:
			return {
				...base,
				title: unitTitle(u, lang),
				plate: null,
				why: '',
				by: { text: t(lang, 'v3_by_rules'), ai: false },
				art: artFor(null),
				prov: null,
				facts: [],
				thumb: { alt: t(lang, 'v3_map_alt_plain'), overlay: {} },
			};
	}
}

// ── live operations ──────────────────────────────────────────────────────

export function opVM(ev: CorridorEvent, lang: string, now: number, units: readonly Unit[], segs = segmentMap()): OpVM {
	return { ...opCore(ev, lang, now, units, segs), cover: coverFor(ev.eventKind, null, null, lang, now, false) };
}

function opCore(ev: CorridorEvent, lang: string, now: number, units: readonly Unit[], segs: Map<number, LonLat[]>): Omit<OpVM, 'cover'> {
	const route = chain(ev.routeSegmentIds, segs);
	const decisions = units.filter((u) => u.subjectUrn === `event:${ev.eventId}` || (u.kind === 'escort-proposal' && escortOf(u).proposal.eventId === ev.eventId)).length;
	const href = objectHref(`event:${ev.eventId}`) ?? `/ops#evt=${encodeURIComponent(safePathId(ev.eventId) ?? '')}`;
	const since = ev.windowStart ? t(lang, 'v3_op_since', fmtStamp(ev.windowStart, now)) : '';
	const name = eventLabel(ev, lang);
	const title = ev.eventKind === 'vehicle_pursuit' ? ops.text(ev.name) : upFirst(name.title);
	if (ev.eventKind === 'protected_movement') {
		const convoy = convoyFor(ev, ev.movementId ?? null);
		const cpos = pos(convoy);
		const [done, ahead] = splitAt(route, cpos);
		const speed = num(convoy?.props.speed_kmh);
		const eta = num(convoy?.props.eta_sec);
		const junction = str(convoy?.props.next_junction_name);
		const nextIn = num(convoy?.props.next_junction_in_sec);
		const progress = num(convoy?.props.progress_pct) ?? num(convoy?.props.progress);
		const pct = progress != null ? Math.round(progress <= 1 ? progress * 100 : progress) : null;
		return {
			key: `event:${ev.eventId}`,
			kindLine: t(lang, 'v3_op_movement', ev.protectionClass && ev.protectionClass !== 'none' ? ev.protectionClass : '—'),
			title,
			state: { text: t(lang, 'v3_op_live'), tone: 'route' },
			meta: [eta != null ? t(lang, 'v3_op_eta', fmtTime(now + eta * 1000)) : null, speed != null ? t(lang, 'v3_op_speed', Math.round(speed)) : null].filter(Boolean).join(' · ') || since,
			progress: pct,
			next: decisions ? t(lang, 'v3_op_decision_waits', decisions) : junction && nextIn != null ? t(lang, 'v3_op_next', junction, fmtDuration(nextIn, lang)) : '',
			art: artFor('protected_movement'),
			href,
			prov: eventProv(ev, lang),
			decisions,
			thumb: {
				alt: t(lang, 'v3_map_alt', title),
				frameOn: 'points',
				overlay: {
					lines: [...(done.length > 1 ? [{ coords: done, style: 'route-done' as const }] : []), ...(ahead.length > 1 ? [{ coords: ahead, style: 'route' as const }] : [])],
					points: cpos ? [{ at: cpos, glyph: 'convoy', tone: 'route', halo: true, decide: decisions > 0 }] : [],
				},
			},
		};
	}
	if (ev.eventKind === 'vehicle_pursuit') {
		const vehicleId = ev.metadata?.vehicleId ?? null;
		const trail = vehicleId ? trailOf(vehicleId) : [];
		const watch = vehicleId ? ops.watchlist.find((w) => w.vehicleId === vehicleId) : null;
		const readT = watch?.lastSighting?.t ?? null;
		return {
			key: `event:${ev.eventId}`,
			kindLine: t(lang, 'v3_op_pursuit'),
			title,
			state: { text: t(lang, 'v3_op_open'), tone: 'alert' },
			meta: readT ? t(lang, 'v3_op_last_read', fmtDuration((now - Date.parse(readT)) / 1000, lang)) : since,
			progress: null,
			next: decisions ? t(lang, 'v3_op_decision_waits', decisions) : '',
			art: artFor('vehicle_pursuit'),
			href,
			prov: eventProv(ev, lang),
			decisions,
			thumb: { alt: t(lang, 'v3_map_alt', title), overlay: trailOverlay(trail, decisions > 0) },
		};
	}
	const at = eventPos(ev, segs);
	return {
		key: `event:${ev.eventId}`,
		kindLine: name.kind ?? kindWord(ev.eventKind, lang),
		title,
		state: { text: t(lang, 'v3_op_active'), tone: 'neutral' },
		meta: ev.windowStart && ev.windowEnd ? `${fmtRange(ev.windowStart, ev.windowEnd, now)} IST` : since,
		progress: null,
		next: decisions ? t(lang, 'v3_op_decision_waits', decisions) : eventNote(ev, lang),
		art: artFor(ev.eventKind),
		href,
		prov: eventProv(ev, lang),
		decisions,
		thumb: {
			alt: t(lang, 'v3_map_alt', title),
			overlay: { lines: route.length > 1 ? [{ coords: route, style: 'dashed' }] : [], points: at ? [{ at, glyph: glyphFor(ev.eventKind), decide: decisions > 0 }] : [] },
		},
	};
}

// ── reported in the city ─────────────────────────────────────────────────

/** The publisher of a report's first source (Sachet, IMD, a newspaper …), never a URL. */
function firstPublisher(e: CityEntity): string | null {
	const p = e.props as Record<string, unknown>;
	const direct = str(p.publisher) ?? str(p.source_name) ?? str(p.feed);
	if (direct) return direct;
	const list = Array.isArray(p.sources) ? p.sources : Array.isArray(p.publishers) ? p.publishers : [];
	for (const it of list) {
		if (typeof it === 'string' && it.trim()) return it;
		if (it && typeof it === 'object') {
			const o = it as Record<string, unknown>;
			const n = str(o.publisher) ?? str(o.name) ?? str(o.source);
			if (n) return n;
		}
	}
	return null;
}

/** Report classes whose news text is about people (who did what to whom): never headlined on a card. */
const PERSON_STORY: ReadonlySet<string> = new Set(['reported_crime', 'crime_incident', 'public_conflict', 'public_disorder', 'unrest']);

export function reportVM(e: CityEntity, lang: string, now: number, units: readonly Unit[]): ReportVM {
	const v = e.verificationState;
	const verif: TagVM =
		v === 'OFFICIAL-VERIFIED'
			? { text: t(lang, 'v3_rep_official'), tone: 'ok', glyph: 'verified' }
			: v === 'CONFIRMED'
				? { text: t(lang, 'v3_rep_confirmed'), tone: 'ok', glyph: 'verified' }
				: v === 'NEWS-REPORTED'
					? { text: t(lang, 'v3_rep_news'), tone: 'ghost', glyph: 'news' }
					: { text: t(lang, 'v3_rep_unverified'), tone: 'dashed', glyph: 'unverified' };
	const cls = str(e.props.sajag_event_kind) ?? str(e.props.event_class);
	const label = splitLabel(ops.text(e.label));
	const kind = localKind(label.kind, cls, lang);
	const title = label.title;
	const proposed = units.some((u) => u.kind === 'dss' && u.subjectUrn === e.urn);
	const at = pos(e);
	const official = v === 'OFFICIAL-VERIFIED' || v === 'CONFIRMED';
	const reported = e.t != null ? fmtAgo(e.t, now, lang) : null;
	// a news story about people (a crime, a conflict) is shown by its place and kind, never by its headline (events are
	// about places, not people); its object page carries the source for the officer who opens it
	const raw = cls && PERSON_STORY.has(cls) && !official ? t(lang, 'v3_rep_news_withheld') : str(e.props.summary);
	// a text in a script the reader does not read (a Marathi IMD line on an English console) is never machine-translated:
	// the card says so in the reader's language and the object page keeps the original
	const sc = raw ? scriptOf(raw) : null;
	const summary = raw && !readableIn(raw, lang) && (sc === 'mr' || sc === 'hi') ? t(lang, `v3_text_in_${sc}`, official) : raw;
	return {
		key: e.urn,
		kindLine: kind ?? t(lang, 'v3_rep_kind'),
		title,
		verif,
		meta: summary ? ops.text(summary) : (reported ?? ''),
		cred: e.credibility,
		note: t(lang, proposed ? 'v3_rep_note_response' : official ? 'v3_rep_note_official' : 'v3_rep_note_verify'),
		art: artFor(cls),
		cover: coverFor(cls, at, title, lang, now),
		source: firstPublisher(e),
		href: objectHref(e.urn) ?? `${WORKSPACE_URL}#items=${encodeURIComponent(e.urn)}`,
		thumb: {
			alt: t(lang, 'v3_map_alt', title),
			zoom: official ? 12 : 15,
			overlay: at
				? {
						rings: official && /weather|district|warning/i.test(`${cls ?? ''} ${e.label}`) ? [{ at, radiusM: 2200 }] : [],
						points: [{ at, glyph: glyphFor(cls), decide: proposed, halo: !official }],
					}
				: {},
		},
	};
}

// ── coming up ────────────────────────────────────────────────────────────

export function plannedVM(ev: CorridorEvent, lang: string, now: number, segs = segmentMap()): PlannedVM {
	return { ...plannedCore(ev, lang, now, segs), cover: coverFor(ev.eventKind, null, null, lang, now, false) };
}

function plannedCore(ev: CorridorEvent, lang: string, now: number, segs: Map<number, LonLat[]>): Omit<PlannedVM, 'cover'> {
	const start = ev.windowStart ? Date.parse(ev.windowStart) : NaN;
	const when = !Number.isFinite(start)
		? '—'
		: start <= now
			? t(lang, 'v3_when_now')
			: istDayOffset(start, now) === 0
				? t(lang, 'v3_when_today', fmtTime(start))
				: istDayOffset(start, now) === 1
					? t(lang, 'v3_when_tomorrow', fmtTime(start))
					: fmtStamp(start, now);
	const route = chain(ev.routeSegmentIds, segs);
	const at = eventPos(ev, segs);
	const name = eventLabel(ev, lang);
	const title = upFirst(name.title);
	const approved = (ev.status ?? '').toLowerCase() === 'approved';
	return {
		key: `event:${ev.eventId}`,
		kindLine: name.kind ?? kindWord(ev.eventKind, lang),
		title,
		when,
		meta: ev.windowStart && ev.windowEnd ? `${fmtRange(ev.windowStart, ev.windowEnd, now)} IST` : ops.text(ev.description) || '',
		next: t(lang, approved ? 'v3_plan_approved' : 'v3_plan_planning'),
		art: artFor(ev.eventKind),
		href: objectHref(`event:${ev.eventId}`) ?? `/ops#evt=${encodeURIComponent(safePathId(ev.eventId) ?? '')}`,
		prov: eventProv(ev, lang),
		thumb: {
			alt: t(lang, 'v3_map_alt', title),
			overlay: { lines: route.length > 1 ? [{ coords: route, style: 'dashed' }] : [], points: at ? [{ at, glyph: glyphFor(ev.eventKind) }] : [] },
		},
	};
}

const upFirst = (x: string) => (x ? x.charAt(0).toLocaleUpperCase() + x.slice(1) : x);

/** English kind words (HUMAN's, the field report's) → their code, for a label that arrives as "<Kind> · <place>". */
let KIND_CODE: Map<string, string> | null = null;
function kindCodeOf(word: string): string | null {
	if (!KIND_CODE) {
		KIND_CODE = new Map();
		for (const [code, w] of Object.entries(HUMAN)) KIND_CODE.set(w.toLowerCase(), code);
	}
	const w = word.trim().toLowerCase();
	return KIND_CODE.get(w) ?? (/^[a-z][a-z -]*$/.test(w) ? w.replace(/[\s-]+/g, '_') : null);
}

/**
 * A label's kind word in the reader's language (V3 pack `v3_k_<code>`): the class code when the record carries one,
 * else the code behind the English word the server's label carries. English, or a word with no translation, stays as
 * it arrived.
 */
export function localKind(word: string | null, code: string | null | undefined, lang: string): string | null {
	if (lang === 'en') return word;
	for (const c of [word ? kindCodeOf(word) : null, code]) {
		if (!c) continue;
		const key = `v3_k_${c}`;
		const v = t(lang, key);
		if (v !== key) return v;
	}
	return word;
}

/**
 * An event's kind and title in the reader's language. The living city's rows carry their own Marathi title
 * (metadata.title_mr) and their cause; everything else splits the server's English "<Kind> · <title>" and translates
 * the kind word.
 */
export function eventLabel(ev: CorridorEvent, lang: string): { kind: string | null; title: string } {
	const cause = ev.metadata?.cause ?? null;
	if (lang === 'mr' && ev.metadata?.titleMr) {
		const mr = splitLabel(ev.metadata.titleMr);
		if (mr.title) return mr;
	}
	const name = splitLabel(ops.text(ev.name));
	if (lang !== 'en' && cause) {
		const key = `v3_cause_k_${cause}`;
		const v = t(lang, key);
		if (v !== key) return { kind: v, title: name.title };
	}
	return { kind: localKind(name.kind, null, lang), title: name.title };
}

/**
 * The rules engine's e-challan line in the reader's language. The oracle writes it in English from two templates
 * ("<mark> read at <v> km/h in a <limit> km/h segment", "<mark> crossed junction <n> on red (movement …)"); the
 * mark arrives as the page already masked it. Anything else stays verbatim.
 */
export function echallanWhy(text: string, lang: string): string {
	if (lang === 'en' || !text) return text;
	const body = text.replace(/^e-challan recommended:\s*/i, '');
	const sp = /^(.+?)\s+read at (\d+(?:\.\d+)?) km\/h in a (\d+(?:\.\d+)?) km\/h segment\.?$/i.exec(body);
	if (sp) return t(lang, 'v3_ech_speed', sp[1], sp[2], sp[3]);
	const red = /^(.+?)\s+crossed junction (\d+) on red(?:\s*\(movement \w+\))?\.?$/i.exec(body);
	if (red) return t(lang, 'v3_ech_red', red[1], red[2]);
	return text;
}

/** A dispatch's agency in the reader's language (the DSS pack's word for a known agency), else the server's label. */
export function agencyIn(code: string, label: string | null, lang: string): string {
	const key = `dss_agency_${code}`;
	const v = t(lang, key);
	return lang !== 'en' && v !== key ? v : (label ?? code);
}

/** Who asked for a corridor: the emulated 108 control room in the reader's language, anyone else as named. */
export function requesterIn(who: string, lang: string): string {
	if (lang !== 'en' && /^108 control\b/i.test(who)) return t(lang, /emulated/i.test(who) ? 'v3_req_108_control_emu' : 'v3_req_108_control');
	return who;
}

/** An event's description line: the living city's cause in the reader's language, else the server's own words. */
export function eventNote(ev: CorridorEvent, lang: string): string {
	const cause = ev.metadata?.cause ?? null;
	if (lang !== 'en' && cause) {
		const key = `v3_cause_${cause}`;
		const v = t(lang, key);
		if (v !== key) return t(lang, 'v3_op_cause', v);
	}
	return ops.text(ev.description) || '';
}

/** The event kind in words (the deck's own kind labels). */
export function kindWord(kind: string, lang: string): string {
	const key = `kind_${kind}`;
	const v = t(lang, key);
	return v === key ? kind.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()) : v;
}

/** Whole IST days from `now`'s day to `ms`'s day. */
function istDayOffset(ms: number, now: number): number {
	const IST = 5.5 * 3_600_000;
	const day = (x: number) => Math.floor((x + IST) / 86_400_000);
	return day(ms) - day(now);
}

/** The road network for the offline fallback (the deck's own geometry). */
export function roadLines(): LonLat[][] {
	return ops.segmentLines.filter((s) => s.coordinates?.length >= 2).map((s) => s.coordinates as LonLat[]);
}
