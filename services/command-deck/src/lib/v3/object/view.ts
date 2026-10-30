/**
 * The object page's view models (V3-SPEC §5.4, §6.3, §6.4) — built ONLY from the deck's existing stores and
 * models, no new endpoint:
 *
 *   the record      liveWorld.graph() (the one ObjectRow every view reads) and the dossier the page opens
 *                   (GET /city/entity/{kind}/{id}, the inspector's own loader)
 *   the facts       the kind adapters' inspector view (workspace/kinds/*: masked whole without an officer)
 *                   and, for a report, osint/model.ts (readReport, the whitelist reader)
 *   the decisions   decisions/units.ts decisionUnits() (the canonical units), sections/links.ts
 *                   unitsReferencing (what the v2 DecisionLinks section shows) and home/view.ts decisionVM
 *                   (the card every V3 surface shows a unit with)
 *   the map         ops.segmentLines (the road geometry the store already loads), the city registry's
 *                   sightings (a vehicle's lawful reads) and the routes on the board
 *   activity, links workspace/components/inspector/model.ts activityRows / linkGroups
 *
 * Masking: every label here is a row label (masked by the adapters' guard) or passes through ops.text /
 * maskMarks unless a duty officer is named (ops.officerOn).
 */
import type { Dossier } from '$lib/gods-eye/city-api';
import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
import { ops } from '$lib/ops/store.svelte';
import { decisionUnits, dssOf, type Unit } from '$lib/decisions/units';
import { unitsReferencing } from '$lib/decisions/sections/links';
import { relatedObject, situationClass, type OsintReportProps } from '$lib/osint/model';
import { kindOne } from '$lib/workspace/kinds/generic';
import { rowOf } from '$lib/workspace/kinds';
import { maskMarks } from '$lib/workspace/mask';
import type { ObjectLink, ObjectRow } from '$lib/workspace/types';
import type { InspectorView, Run } from '$lib/workspace/kinds/common';
import { activityRows, linkGroups, type ActivityRow, type LinkGroup } from '$lib/workspace/components/inspector/model';
import { t } from '$lib/i18n/strings';
import { fmtRange, fmtStamp, fmtTime } from '$lib/ui/format/format';
import { chain, decisionVM, type DecisionVM } from '../home/view';
import type { LonLat } from '../map/mercator';
import type { ThumbOverlay, ThumbPoint } from '../map/overlay';
import { classWord } from '$lib/osint/model';
import { markerGlyph, ringRadiusM, sourceTally, reportStatusKey } from './model';
import './packs.object';

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v.trim() : null);

/** Free text as this console may show it: raw only for a named duty officer (SPEC §9.3). */
export function shown(text: string | null | undefined): string {
	if (!text) return '';
	return ops.officerOn ? text : maskMarks(text);
}

function segmentMap(): Map<number, LonLat[]> {
	const m = new Map<number, LonLat[]>();
	for (const s of ops.segmentLines) if (s.coordinates?.length >= 2) m.set(s.segmentId, s.coordinates as LonLat[]);
	return m;
}

const posOf = (r: { lon: number | null; lat: number | null } | null | undefined): LonLat | null =>
	r && r.lon != null && r.lat != null && Number.isFinite(r.lon) && Number.isFinite(r.lat) ? [r.lon, r.lat] : null;

// ── runs (a view's title and subtitle) as plain text ───────────────────────

/** A run list as text (the tooltip / aria form; a mark stays as the view built it — masked without an officer). */
export function runsText(runs: readonly Run[], now: number): string {
	return runs
		.map((r) => {
			if ('text' in r) return r.text;
			if ('id' in r) return r.id;
			if ('plate' in r) return r.plate ?? '';
			if ('start' in r) return r.end != null ? fmtRange(r.start, r.end, now) : fmtStamp(r.start, now);
			if ('time' in r) return r.time != null ? fmtStamp(r.time, now) : '';
			return '';
		})
		.join('');
}

// ── the hero ───────────────────────────────────────────────────────────────

export interface HeroVM {
	overlay: ThumbOverlay | null;
	at: LonLat | null;
	alt: string;
	zoom: number;
}

/** A vehicle's lawful reads, oldest first (the registry's sightings linked to it: the oracle withholds the rest). */
export function readsOf(vehicleUrn: string, links: readonly ObjectLink[]): ObjectRow[] {
	const id = vehicleUrn.slice(vehicleUrn.indexOf(':') + 1);
	const seen = new Set<string>();
	const out: ObjectRow[] = [];
	for (const l of links) {
		if (l.row.kind !== 'sighting' || seen.has(l.row.urn)) continue;
		seen.add(l.row.urn);
		out.push(l.row);
	}
	for (const s of cityRegistry.byKind('sighting')) {
		if (seen.has(s.urn) || !(s.links.includes(vehicleUrn) || s.props.vehicle_id === id)) continue;
		seen.add(s.urn);
		out.push(rowOf(s));
	}
	return out.sort((a, b) => (a.t ?? 0) - (b.t ?? 0));
}

export function heroVM(row: ObjectRow, links: readonly ObjectLink[], report: OsintReportProps | null, decide: boolean, title: string, lang: string): HeroVM {
	const segs = segmentMap();
	const L = (k: string, ...a: unknown[]) => t(lang, k, ...a);
	const at0 = posOf(row);
	const glyph = markerGlyph(row);
	const alt = L('obj_hero_alt', title);

	if (row.kind === 'vehicle' || row.kind === 'sighting') {
		const reads = row.kind === 'vehicle' ? readsOf(row.urn, links).map(posOf).filter((p): p is LonLat => !!p) : [];
		const trail = reads.length ? reads : at0 ? [at0] : [];
		if (!trail.length) return { overlay: null, at: null, alt, zoom: 15 };
		const newest = trail[trail.length - 1];
		return {
			at: newest,
			alt,
			zoom: 15,
			overlay: {
				lines: trail.length > 1 ? [{ coords: trail, style: 'trail' }] : [],
				points: [
					...trail.slice(0, -1).map((p): ThumbPoint => ({ at: p, small: true })),
					{ at: newest, glyph: 'car', tone: 'alert', halo: true, decide, label: L('obj_hero_last_read'), labelSide: 'r' },
				],
			},
		};
	}

	if (row.kind === 'osint_event' && report) {
		if (!at0) return { overlay: null, at: null, alt, zoom: 15 };
		const road = report.segmentId != null ? segs.get(report.segmentId) : undefined;
		const conf = report.geocodeConfidence;
		const radius = ringRadiusM(conf, report.areaLevel);
		return {
			at: at0,
			alt,
			zoom: report.areaLevel ? 12 : 16,
			overlay: {
				lines: road ? [{ coords: road, style: 'road' }] : [],
				rings: [{ at: at0, radiusM: radius }],
				points: [
					{
						at: at0,
						glyph,
						decide,
						halo: true,
						label: L('obj_hero_reported'),
						sub: report.areaLevel ? L('obj_hero_area') : conf != null ? L('obj_hero_matched', Math.round(conf * 100)) : null,
						labelSide: 'r',
					},
				],
			},
		};
	}

	if (row.kind === 'event' || row.kind === 'convoy') {
		const ids = routeIdsOf(row);
		const route = chain(ids, segs);
		const at = at0 ?? (route.length ? route[Math.floor(route.length / 2)] : null);
		if (!at && route.length < 2) return { overlay: null, at: null, alt, zoom: 15 };
		const live = row.kind === 'convoy' || (row.state === 'active' && str(row.props.event_kind) === 'protected_movement');
		return {
			at,
			alt,
			zoom: 15,
			overlay: {
				lines: route.length > 1 ? [{ coords: route, style: live ? 'route' : 'dashed' }] : [],
				points: at ? [{ at, glyph, tone: live ? 'route' : 'neutral', halo: true, decide, label: L('obj_hero_here'), labelSide: 'r' }] : [],
			},
		};
	}

	if (!at0) return { overlay: null, at: null, alt, zoom: 15 };
	const seg = num(row.props.segment_id);
	const road = seg != null ? segs.get(seg) : row.kind === 'segment' ? segs.get(Number(row.id)) : undefined;
	return {
		at: at0,
		alt,
		zoom: row.kind === 'place' ? 16 : 16,
		overlay: {
			lines: road ? [{ coords: road, style: 'road' }] : [],
			points: [{ at: at0, glyph, halo: true, decide, label: L('obj_hero_here'), labelSide: 'r' }],
		},
	};
}

/** The route segments an event or a convoy runs (the board's routes, or the registry's links). */
function routeIdsOf(row: ObjectRow): number[] {
	if (row.kind === 'event') {
		const ev = ops.eventById(row.id);
		if (ev?.routeSegmentIds?.length) return ev.routeSegmentIds;
	}
	const fromProps = Array.isArray(row.props.route_segment_ids) ? row.props.route_segment_ids.filter((x): x is number => typeof x === 'number') : [];
	if (fromProps.length) return fromProps;
	const ent = cityRegistry.get(row.urn);
	return (ent?.links ?? []).filter((l) => l.startsWith('segment:')).map((l) => Number(l.slice(8))).filter(Number.isFinite);
}

// ── a report's key facts ───────────────────────────────────────────────────

export interface FactVM {
	key: string;
	value: string;
}

export function osintFacts(row: ObjectRow, p: OsintReportProps, dossier: Dossier | null, lang: string, now: number): FactVM[] {
	const L = (k: string, ...a: unknown[]) => t(lang, k, ...a);
	const out: FactVM[] = [];
	if (p.toponym) out.push({ key: L('obj_f_place'), value: shown(p.toponym) });
	const road = relatedObject(dossier, 'on_road');
	if (road) out.push({ key: L('obj_f_road'), value: shown(road.label) });
	const a = Date.parse(String(row.props.window_start ?? ''));
	const b = Date.parse(String(row.props.window_end ?? ''));
	if (Number.isFinite(a) && Number.isFinite(b)) out.push({ key: L('obj_f_when'), value: `${fmtRange(a, b, now)} IST` });
	else if (row.t != null) out.push({ key: L('obj_f_when'), value: `${fmtStamp(row.t, now)} IST` });
	const kind = situationClass(p.sajagEventKind, lang);
	const also = p.correlatedClasses.filter((c) => c !== p.eventClass && c !== p.sajagEventKind).map((c) => classWord(c).toLowerCase());
	if (kind) out.push({ key: L('obj_f_kind'), value: also.length ? `${kind} · ${L('obj_f_also', also.join(', '))}` : kind });
	out.push({ key: L('obj_f_status'), value: L(reportStatusKey(p)) });
	const tally = sourceTally(p);
	const publishers = tally.publishers || Math.max(0, p.independentPublishers ?? 0);
	out.push({ key: L('obj_f_sources'), value: `${L('obj_src_publishers', publishers)} · ${L('obj_src_official_n', tally.official)}` });
	return out;
}

/** The kind line under the art: "Road accident · reported 20 Oct, 19:10–19:29 IST" for a report; the kind and the subtitle otherwise. */
export function kindLine(row: ObjectRow, view: InspectorView | null, p: OsintReportProps | null, lang: string, now: number): string {
	if (row.kind === 'osint_event' && p) {
		const kind = situationClass(p.sajagEventKind, lang) ?? kindOne(row.kind, lang);
		const a = Date.parse(String(row.props.window_start ?? ''));
		const b = Date.parse(String(row.props.window_end ?? ''));
		const when = Number.isFinite(a) && Number.isFinite(b) ? `${fmtRange(a, b, now)} IST` : row.t != null ? `${fmtStamp(row.t, now)} IST` : null;
		return when ? `${kind} · ${t(lang, 'obj_reported_at', when)}` : kind;
	}
	if (!view) return kindOne(row.kind, lang);
	const parts = view.subtitle.map((seg) => runsText(seg, now)).filter(Boolean);
	return parts.slice(0, 2).join(' · ') || kindOne(row.kind, lang);
}

/** The display title: the view's title runs, with a report's "Kind · " prefix moved to the kind line. */
export function titleText(row: ObjectRow, view: InspectorView | null, now: number): string {
	const raw = view ? runsText(view.title, now) : row.label;
	if (row.kind === 'osint_event') {
		const at = raw.indexOf(' · ');
		const rest = at > 0 ? raw.slice(at + 3) : raw;
		// "Ruby crossing (EM Bypass)" reads as "Ruby crossing, EM Bypass"
		return rest.replace(/\s*\(([^()]+)\)\s*$/, ', $1');
	}
	// "Work zone · AJC Bose Road": the kind already reads on the kind line above the title
	if (row.kind === 'event') {
		const at = raw.indexOf(' · ');
		if (at > 0 && at < 40 && raw.length - at > 4) return raw.slice(at + 3);
	}
	return raw;
}

// ── decisions ──────────────────────────────────────────────────────────────

export interface CtaVM extends DecisionVM {
	/** True for a unit about another record that touches this one (the v2 DecisionLinks rule). */
	touches: boolean;
	recommended: string | null;
}

/**
 * The decisions this page links to (one home each, never a verb): the units whose subject is this record,
 * soonest deadline first, then the units about another record that touch it (sections/links.ts).
 */
export function decisionsFor(urn: string, lang: string, now: number, units: readonly Unit[] = decisionUnits()): CtaVM[] {
	const own = units.filter((u) => u.subjectUrn === urn);
	const ownKeys = new Set(own.map((u) => `${u.kind}:${u.id}`));
	const refs = unitsReferencing(urn, units as Unit[]).filter((u) => !ownKeys.has(`${u.kind}:${u.id}`));
	const vm = (u: Unit, touches: boolean): CtaVM => ({
		...decisionVM(u, lang, now),
		touches,
		recommended: u.kind === 'dss' ? (dssOf(u).summary?.topCoaLabel ?? null) : null,
	});
	return [...own.map((u) => vm(u, false)), ...refs.map((u) => vm(u, true))];
}

// ── activity and links ─────────────────────────────────────────────────────

export interface ActivityVM extends ActivityRow {
	/** The brief, masked unless an officer is named. */
	text: string;
	ai: boolean;
}

/** The dossier's audit, oldest first, masked (inspector model activityRows). */
export function activityOf(dossier: Dossier | null, lang: string, now: number): ActivityVM[] {
	if (!dossier) return [];
	return activityRows(dossier.audit, 'all', now, lang)
		.slice()
		.reverse()
		.map((r) => ({ ...r, text: shown(r.brief), full: shown(r.full), who: shown(r.who) }));
}

export function nearbyOf(links: readonly ObjectLink[], lang: string, now: number): LinkGroup[] {
	return linkGroups(links, lang, now);
}

/** The clock of a timeline row (hh:mm, its day when the rows span days). */
export function clockOf(r: ActivityRow): string {
	return r.day ? `${r.day} ${fmtTime(r.t)}` : fmtTime(r.t);
}
