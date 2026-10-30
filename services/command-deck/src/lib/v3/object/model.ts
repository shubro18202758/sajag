/**
 * The object page's pure rules (V3-SPEC §5.4, §6.3, §6.4, §8) — no store, no DOM; tests/object-page.unit.mjs
 * reads them as plain data. The page (ObjectPage.svelte) and its view builder (view.ts) apply them to the
 * deck's own stores; nothing here invents a figure.
 *
 *   objectHref / urnFromParam   /o/<kind>:<id> — the URN grammar of city-api (parseUrn), nothing else
 *   tabsFor                     Overview · Sources (a report) · Reads (a vehicle) · Pursuit (one is open) ·
 *                               Timeline · Nearby · Record, with the counts the pills show
 *   provenanceOf / PROVENANCE   the ONE honest provenance tag: Emulated · Simulated · Test · Unverified ·
 *                               Unverified field report · Unverified camera reading (a board entry from lib/v3/field) ·
 *                               News-reported · Official (an OSINT row without a label is never shown as
 *                               more than Unverified; officialness rides the label or the source tier,
 *                               never a web address)
 *   reportingSources            the sources that REPORT the situation: a context member (an alert in effect
 *   sourceTally                 for the district) is listed apart and is never counted, never corroboration
 *   credibilityChecks           the four plain checks under the gauge
 *   ladderStep                  Unverified · News-reported · Official
 *   ringRadiusM                 the hero's dashed "place matched" ring from the geocoder's confidence
 *   artOf / markerGlyph         the illustration or glyph a kind shows (never a photo)
 *   effectTiles                 "What it may affect" from the report's second-order flags (live flags,
 *                               not forecasts)
 *   mapHref / analystHref       the Map share link (camera + layers + sel; URNs only, never a mark) and
 *                               the Analyst workspace link
 *   retentionDaysLeft           a watchlist entry's days of retention left
 */
import { parseUrn } from '$lib/gods-eye/city-api';
import { buildShareHash } from '$lib/gods-eye/share-link';
import { geocodeBucket, sourceRows, type OsintReportProps, type SourceRow } from '$lib/osint/model';
import type { ObjectRow } from '$lib/workspace/types';
import type { PropValue } from '$lib/workspace/kinds/common';
import { artFor, glyphFor } from '../home/model';
import type { LonLat } from '../map/mercator';
import { keyArt, keyArtKind, vehicleShotClass } from '../media/art';
import { photoForText, photoNear, type PlacePhoto } from '../media/photos';
import { fieldLabelOf } from '../field/labels';
import '../field/packs.field.core';

const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v.trim() : null);

// ── the route ──────────────────────────────────────────────────────────────

/** The kinds the page is designed for (any other valid URN still renders, through the generic layout). */
export const OBJECT_KINDS = ['event', 'osint_event', 'vehicle', 'place', 'convoy', 'junction', 'camera', 'dispatch', 'recommendation', 'sighting'] as const;

/** `/o/<kind>:<id>` for a valid URN (the id URL-encoded), else null. The path carries a URN only — never a mark. */
export function objectHref(urn: string | null | undefined): string | null {
	const p = parseUrn(urn);
	return p ? `/o/${p.kind}:${encodeURIComponent(p.id)}` : null;
}

/** The URN a route parameter names, or null when it names nothing the oracle's grammar allows. */
export function urnFromParam(raw: string | null | undefined): string | null {
	if (typeof raw !== 'string' || !raw || raw.length > 240) return null;
	let v = raw;
	if (/%[0-9A-Fa-f]{2}/.test(v)) {
		try {
			v = decodeURIComponent(v);
		} catch {
			return null;
		}
	}
	const p = parseUrn(v);
	return p ? `${p.kind}:${p.id}` : null;
}

// ── tabs ───────────────────────────────────────────────────────────────────

export type TabId = 'overview' | 'sources' | 'reads' | 'pursuit' | 'timeline' | 'nearby' | 'record';

export interface TabSpec {
	id: TabId;
	key: string;
	/** The pill's number, or null for none. */
	count: number | null;
}

export interface TabCounts {
	sources: number;
	reads: number;
	pursuit: boolean;
	timeline: number;
	nearby: number;
	record: number;
}

/** The tabs of a kind, in order (V3-SPEC §3.3 L2, §6.3, §6.4). */
export function tabsFor(kind: string, c: TabCounts): TabSpec[] {
	const out: TabSpec[] = [{ id: 'overview', key: 'obj_tab_overview', count: null }];
	if (kind === 'osint_event') out.push({ id: 'sources', key: 'obj_tab_sources', count: c.sources });
	if (kind === 'vehicle') out.push({ id: 'reads', key: 'obj_tab_reads', count: c.reads });
	if (c.pursuit && (kind === 'vehicle' || kind === 'event')) out.push({ id: 'pursuit', key: 'obj_tab_pursuit', count: null });
	out.push({ id: 'timeline', key: 'obj_tab_timeline', count: c.timeline });
	out.push({ id: 'nearby', key: 'obj_tab_nearby', count: c.nearby });
	out.push({ id: 'record', key: 'obj_tab_record', count: c.record });
	return out;
}

/** The tab a key moves to (←/→ wrap, Home/End), as a tablist's roving focus does. */
export function tabStep(tabs: readonly { id: string }[], current: string, key: string): string | null {
	const i = tabs.findIndex((t) => t.id === current);
	if (i < 0 || !tabs.length) return null;
	if (key === 'ArrowRight') return tabs[(i + 1) % tabs.length].id;
	if (key === 'ArrowLeft') return tabs[(i - 1 + tabs.length) % tabs.length].id;
	if (key === 'Home') return tabs[0].id;
	if (key === 'End') return tabs[tabs.length - 1].id;
	return null;
}

/** One key fact: plain text (a report's facts) or an inspector property value (rendered by PropValue). */
export type FactRow = { key: string; value: string } | { key: string; prop: PropValue; testid?: string; attrs?: Record<string, string> };

/** One tag of the title bar (V3Tag tone + words; `attrs` carry the test hooks). */
export interface TitleTag {
	text: string;
	tone: string;
	glyph?: string | null;
	title?: string | null;
	attrs?: Record<string, string>;
}

// ── provenance (one honest tag) ────────────────────────────────────────────

export type Provenance = 'EMULATED' | 'SIMULATED' | 'TEST' | 'UNVERIFIED-OSINT' | 'UNVERIFIED-FIELD' | 'UNVERIFIED-CAMERA' | 'NEWS-REPORTED' | 'OFFICIAL-VERIFIED' | 'CONFIRMED';

/**
 * The ONE provenance tag a record wears: a rehearsal first, then the emulator, a simulated feed, and an open-source
 * report's verification. An OSINT row that carries no label (or an unknown one) is UNVERIFIED — never more. A
 * gazetteer place is reference data, not a report: no tag. A live record needs none.
 */
export function provenanceOf(row: Pick<ObjectRow, 'kind' | 'source' | 'verification' | 'test'> & { props?: ObjectRow['props'] }): Provenance | null {
	if (row.test) return 'TEST';
	if (row.source === 'emulated') return 'EMULATED';
	if (row.source === 'simulated') return 'SIMULATED';
	// a board entry sent from a voice field report or a camera reading (lib/v3/field): unverified until an officer confirms
	if (row.kind === 'event') {
		const field = fieldLabelOf(row.props?.metadata);
		if (field) return field;
	}
	if (row.source === 'osint') {
		if (row.kind === 'place') return null;
		const v = row.verification;
		return v === 'OFFICIAL-VERIFIED' || v === 'CONFIRMED' || v === 'NEWS-REPORTED' ? v : 'UNVERIFIED-OSINT';
	}
	return null;
}

export interface ProvenanceSpec {
	key: string;
	tip: string;
	tone: 'dashed' | 'ghost' | 'ok';
	glyph: string;
}

export const PROVENANCE: Readonly<Record<Provenance, ProvenanceSpec>> = {
	EMULATED: { key: 'obj_prov_emulated', tip: 'obj_prov_emulated_tip', tone: 'dashed', glyph: 'flask' },
	SIMULATED: { key: 'obj_prov_simulated', tip: 'obj_prov_simulated_tip', tone: 'dashed', glyph: 'shuffle' },
	TEST: { key: 'obj_prov_test', tip: 'obj_prov_test_tip', tone: 'dashed', glyph: 'flask' },
	'UNVERIFIED-OSINT': { key: 'obj_prov_unverified', tip: 'obj_prov_unverified_tip', tone: 'dashed', glyph: 'unverified' },
	'UNVERIFIED-FIELD': { key: 'fld_tag_unverified', tip: 'fld_not_action', tone: 'dashed', glyph: 'unverified' },
	'UNVERIFIED-CAMERA': { key: 'fld_tag_camera', tip: 'fld_not_action', tone: 'dashed', glyph: 'unverified' },
	'NEWS-REPORTED': { key: 'obj_prov_news', tip: 'obj_prov_news_tip', tone: 'ghost', glyph: 'news' },
	'OFFICIAL-VERIFIED': { key: 'obj_prov_official', tip: 'obj_prov_official_tip', tone: 'ok', glyph: 'verified' },
	CONFIRMED: { key: 'obj_prov_confirmed', tip: 'obj_prov_confirmed_tip', tone: 'ok', glyph: 'verified' },
};

/** The verification ladder's step: 0 Unverified, 1 News-reported, 2 Official. */
export function ladderStep(v: string | null | undefined): 0 | 1 | 2 {
	if (v === 'OFFICIAL-VERIFIED' || v === 'CONFIRMED') return 2;
	if (v === 'NEWS-REPORTED') return 1;
	return 0;
}

export const LADDER_KEYS = ['obj_ladder_unverified', 'obj_ladder_news', 'obj_ladder_official'] as const;

// ── sources: reporting, never context ──────────────────────────────────────

/**
 * The sources that REPORT the situation (osint/model.ts sourceRows: one per source, its own tier, a link
 * only on an official tier's https url) — minus any CONTEXT member: an alert in effect for the district is
 * listed apart and never counted as corroboration, even if a source row names the same publisher.
 */
export function reportingSources(p: OsintReportProps): SourceRow[] {
	const context = new Set(p.provenance.contextPublishers.map((x) => x.toLowerCase()));
	return sourceRows(p).filter((r) => !context.has(r.publisher.toLowerCase()));
}

export interface SourceTally {
	/** Distinct reporting publishers (context excluded). */
	publishers: number;
	/** Of them, on an official tier (by tier, never by domain). */
	official: number;
	/** Context members (listed apart; never counted above). */
	context: number;
}

export function sourceTally(p: OsintReportProps): SourceTally {
	const rows = reportingSources(p);
	const pubs = new Set(rows.map((r) => r.publisher.toLowerCase()));
	const official = new Set(rows.filter((r) => r.official).map((r) => r.publisher.toLowerCase()));
	return { publishers: pubs.size, official: official.size, context: new Set(p.provenance.contextPublishers.map((x) => x.toLowerCase())).size };
}

/** An official source's link, when the deck may render one: an official tier and an https url, nothing else. */
export function officialLink(r: Pick<SourceRow, 'official' | 'url'>): string | null {
	if (!r.official || typeof r.url !== 'string') return null;
	try {
		const u = new URL(r.url);
		return u.protocol === 'https:' && !!u.hostname ? u.href : null;
	} catch {
		return null;
	}
}

// ── how sure are we ────────────────────────────────────────────────────────

export interface Check {
	id: 'publishers' | 'place' | 'official' | 'cross';
	ok: boolean;
	key: string;
	args: readonly unknown[];
}

/**
 * The four plain checks under the credibility gauge (V3-SPEC §6.3). Independent publishers are the oracle's
 * count (context excluded there too); "official" is the verification label or a reporting source on an
 * official tier — never a context member, never a domain.
 */
export function credibilityChecks(p: OsintReportProps, where: string | null): Check[] {
	const out: Check[] = [];
	const pubs = p.independentPublishers;
	out.push(pubs != null && pubs >= 2 ? { id: 'publishers', ok: true, key: 'obj_chk_pubs', args: [pubs] } : { id: 'publishers', ok: false, key: 'obj_chk_pubs_one', args: [] });
	const place = where ?? p.toponym;
	const conf = p.geocodeConfidence;
	if (p.areaLevel) out.push({ id: 'place', ok: false, key: 'obj_chk_place_area', args: [] });
	else if (conf == null || !place) out.push({ id: 'place', ok: false, key: 'obj_chk_place_none', args: [] });
	else {
		const firm = geocodeBucket(conf) !== 'low';
		out.push({ id: 'place', ok: firm, key: firm ? 'obj_chk_place' : 'obj_chk_place_loose', args: [place, Math.round(conf * 100)] });
	}
	const official = ladderStep(p.verification) === 2 || reportingSources(p).some((r) => r.official);
	out.push({ id: 'official', ok: official, key: official ? 'obj_chk_official_yes' : 'obj_chk_official_no', args: [] });
	out.push({ id: 'cross', ok: p.crossTypeCorroborated, key: p.crossTypeCorroborated ? 'obj_chk_cross_yes' : 'obj_chk_cross_no', args: [] });
	return out;
}

/** The radius of the hero's dashed "place matched" ring, in metres: wider the less sure the geocoder is. */
export function ringRadiusM(confidence: number | null, areaLevel: boolean): number {
	if (areaLevel) return 2200;
	if (confidence == null) return 450;
	if (confidence >= 0.75) return 160;
	if (confidence >= 0.5) return 280;
	return 600;
}

/** The live state of a report in words (the key). */
export function reportStatusKey(p: Pick<OsintReportProps, 'promotedEventId' | 'corroboratesLiveUrn' | 'novel'>): string {
	if (p.promotedEventId) return 'obj_status_promoted';
	if (p.corroboratesLiveUrn) return 'obj_status_corroborates';
	if (p.novel) return 'obj_status_new';
	return 'obj_status_seen';
}

// ── what it may affect ─────────────────────────────────────────────────────

export interface EffectTile {
	urn: string;
	kind: string;
	glyph: string;
	/** The affected record's (masked) label, from the resolver; else null (the kind name is shown). */
	label: string | null;
	/** The oracle's own wording(s) for the flag. */
	notes: string[];
}

/** One tile per affected record (its flags' wordings joined), in the oracle's order. */
export function effectTiles(p: Pick<OsintReportProps, 'secondOrder'>, label: (urn: string) => string | null): EffectTile[] {
	const by = new Map<string, EffectTile>();
	for (const f of p.secondOrder) {
		let tile = by.get(f.urn);
		if (!tile) {
			tile = { urn: f.urn, kind: f.kind, glyph: effectGlyph(f.kind, f.note), label: label(f.urn), notes: [] };
			by.set(f.urn, tile);
		}
		if (f.note && !tile.notes.includes(f.note)) tile.notes.push(f.note);
	}
	return [...by.values()];
}

function effectGlyph(kind: string, note: string | null): string {
	const n = (note ?? '').toLowerCase();
	if (/108|ambulance|hospital/.test(n) || kind === 'dispatch') return 'ambulance';
	if (/movement|convoy|corridor|escort/.test(n) || kind === 'convoy') return 'convoy';
	if (/closure|closed|enforcement/.test(n)) return 'cone';
	if (kind === 'segment') return 'car';
	if (kind === 'junction') return 'signal';
	return 'alert';
}

// ── art (never a photo) ────────────────────────────────────────────────────

const VEHICLE_ART = new Set(['ambulance', 'auto_rickshaw', 'bus', 'car', 'fire_tender', 'patrol', 'suv', 'tempo', 'truck', 'two_wheeler']);
const VEHICLE_ALIAS: Record<string, string> = {
	motorcycle: 'two_wheeler',
	motorbike: 'two_wheeler',
	scooter: 'two_wheeler',
	bike: 'two_wheeler',
	'2w': 'two_wheeler',
	auto: 'auto_rickshaw',
	three_wheeler: 'auto_rickshaw',
	rickshaw: 'auto_rickshaw',
	lcv: 'tempo',
	van: 'tempo',
	hgv: 'truck',
	lorry: 'truck',
	jeep: 'suv',
	fire: 'fire_tender',
};

/** A vehicle class's silhouette (static/illustrations/vehicles; a car when the class is unknown). */
export function vehicleArt(cls: string | null | undefined): string {
	const k = (cls ?? '').toLowerCase().replace(/[\s-]+/g, '_');
	const name = VEHICLE_ART.has(k) ? k : (VEHICLE_ALIAS[k] ?? 'car');
	return `/illustrations/vehicles/${name}.svg`;
}

const AGENCY_ART: Record<string, string> = {
	ambulance: 'ems',
	ems: 'ems',
	'108': 'ems',
	police: 'police',
	fire: 'fire',
	traffic: 'traffic',
	municipal: 'municipal',
	jan_rakshak: 'volunteers',
	volunteers: 'volunteers',
	disaster: 'disaster',
};

/** The generic agency mark of a dispatch (never a real emblem). */
export function agencyArt(agency: string | null | undefined): string {
	const k = (agency ?? '').toLowerCase();
	return `/illustrations/agencies/${AGENCY_ART[k] ?? 'control_room'}.svg`;
}

const KIND_GLYPH: Record<string, string> = {
	place: 'pin',
	junction: 'signal',
	camera: 'anpr',
	sighting: 'anpr',
	recommendation: 'shield',
	unit: 'shield',
	segment: 'car',
	anomaly: 'alert',
	convoy: 'convoy',
	vehicle: 'car',
	dispatch: 'ambulance',
};

/** The map marker's glyph for a record (its TYPE; the state is the colour). */
export function markerGlyph(row: Pick<ObjectRow, 'kind' | 'props'>): string {
	if (row.kind === 'event') return glyphFor(str(row.props.event_kind));
	if (row.kind === 'osint_event') return glyphFor(str(row.props.sajag_event_kind) ?? str(row.props.event_class));
	if (row.kind === 'dispatch' && str(row.props.agency) && !/ambulance|108|ems/i.test(String(row.props.agency))) return 'shield';
	return KIND_GLYPH[row.kind] ?? 'pin';
}

/** The title bar's art: an original illustration where one exists, else a glyph tile. */
export function artOf(row: Pick<ObjectRow, 'kind' | 'props'>): { src: string | null; glyph: string } {
	const glyph = markerGlyph(row);
	switch (row.kind) {
		case 'event':
			return { src: artFor(str(row.props.event_kind)), glyph };
		case 'osint_event':
			return { src: artFor(str(row.props.sajag_event_kind) ?? str(row.props.event_class)), glyph };
		case 'vehicle':
		case 'sighting':
			return { src: vehicleArt(str(row.props.vehicle_class)), glyph };
		case 'convoy':
			return { src: artFor('protected_movement'), glyph };
		case 'dispatch':
			return { src: agencyArt(str(row.props.agency)), glyph };
		default:
			return { src: null, glyph };
	}
}

/**
 * The picture beside an object's hero map (V3-P7): an event's key art — or a credited reference photo when the place
 * has one —, a vehicle's class shot, a dispatch's agency mark over its vehicle class. Never a camera image.
 */
export type PosterVM =
	| { kind: 'cover'; art: string; photo: PlacePhoto | null; label: string }
	| { kind: 'vehicle'; cls: string }
	| { kind: 'agency'; role: string; cls: string }
	| null;

export function posterOf(row: Pick<ObjectRow, 'kind' | 'props' | 'lon' | 'lat' | 'label'>, hour: number | null = null): PosterVM {
	const near = () => photoNear(row.lon, row.lat, 900, hour) ?? photoForText(row.label, hour);
	switch (row.kind) {
		case 'event': {
			// a movement along a route (a convoy, a pursuit, a 108 corridor) is not one place: it leads with its key art
			const k = str(row.props.event_kind);
			const onRoute = ['protected_movement', 'vehicle_pursuit', 'green_corridor'].includes(keyArtKind(k));
			return { kind: 'cover', art: keyArt(k), photo: onRoute ? null : near(), label: keyArtKind(k) };
		}
		case 'osint_event': {
			const k = str(row.props.sajag_event_kind) ?? str(row.props.event_class);
			return { kind: 'cover', art: keyArt(k), photo: near(), label: keyArtKind(k) };
		}
		case 'convoy':
			return { kind: 'vehicle', cls: 'convoy' };
		case 'vehicle':
		case 'sighting':
			return { kind: 'vehicle', cls: vehicleShotClass(str(row.props.vehicle_class)) };
		case 'dispatch':
		case 'unit': {
			const a = (str(row.props.agency) ?? '').toLowerCase();
			const cls = /108|ems|ambulance/.test(a) ? 'ambulance' : /fire/.test(a) ? 'fire_tender' : 'patrol';
			return { kind: 'agency', role: a || 'police', cls };
		}
		case 'place':
		case 'junction': {
			const photo = near();
			return photo ? { kind: 'cover', art: keyArt('advisory'), photo, label: 'advisory' } : null;
		}
		default:
			return null;
	}
}

// ── links out ──────────────────────────────────────────────────────────────

/** Every layer the Map knows (share-link's known set). */
export const MAP_LAYERS = ['events', 'convoy', 'traces', 'enforcement', 'osint', 'places', 'cameras', 'signals', 'flow', 'units', 'dispatch', 'anomalies'] as const;
/** The Map's clean default (V3-SPEC §5.6), plus the layer the record lives on. */
const DEFAULT_ON = ['events', 'convoy', 'traces', 'enforcement', 'osint'];
const KIND_LAYER: Record<string, string> = { camera: 'cameras', junction: 'signals', place: 'places', dispatch: 'dispatch', unit: 'units', anomaly: 'anomalies', segment: 'flow' };

/**
 * The Map focused on the record: the share-link hash (camera over the place, the clean layers, `sel` = the
 * URN when its grammar allows). The plain City map style, never the thermal-style filter. URNs only.
 */
export function mapHref(urn: string, at: LonLat | null, kind: string): string {
	if (!at) return '/gods-eye';
	const layers = [...DEFAULT_ON, ...(KIND_LAYER[kind] ? [KIND_LAYER[kind]] : [])];
	const hash = buildShareHash(
		{ lat: at[1], lon: at[0], alt: 1800, heading: 0, pitch: -58, roll: 0, style: 'raw', bhot: false, layers, selected: urn },
		MAP_LAYERS,
	);
	return `/gods-eye#${hash}`;
}

/** The record in the Analyst workspace (the v2 page, served at `/analyst` since the root flip). */
export function analystHref(urn: string): string {
	return `/analyst#items=${encodeURIComponent(urn)}`;
}

// ── a vehicle ──────────────────────────────────────────────────────────────

/** Whole days of retention left (rounded up), or null without a date. */
export function retentionDaysLeft(until: unknown, now: number): number | null {
	const t = typeof until === 'string' ? Date.parse(until) : typeof until === 'number' ? until : NaN;
	if (!Number.isFinite(t)) return null;
	return Math.max(0, Math.ceil((t - now) / 86_400_000));
}

/** Percent, rounded, of a 0..1 progress; null outside the range. */
export function percent(v: unknown): number | null {
	return typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1 ? Math.round(v * 100) : null;
}
