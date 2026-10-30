/**
 * The field AI's pure rules — no store, no DOM, no fetch. tests/field.unit.mjs reads them as plain data; the
 * components (FieldReportSheet, the object page's road-state, forecast and waterlogging panels, the public water card)
 * apply them to what the on-premises services answer.
 *
 *   parseFieldReport        POST /api/speech/report → a FieldReport (always UNVERIFIED-FIELD, whatever the wire says)
 *   parseRoadState          POST /api/vision/road-state → a RoadState (always UNVERIFIED-CAMERA) or a policy refusal
 *   parseStreetPhoto        GET /api/cityfeeds/feeds/street-image → the nearby street photo (Mapillary, "Reference photo
 *                           · not live", its capture date) or why there is none (no key: the city feeds made no call)
 *   parseNowcast / waterOf  GET /api/hydro/nowcast → one segment's waterlogging (MODELLED; drivers with their labels)
 *   parseTide / parseRain   GET /api/hydro/tide | rain → the plain-word state a citizen reads
 *   parseSegmentForecast    GET /api/forecast/segment/{id} → V/C steps with the p10–p90 band (SIMULATED until real traffic)
 *   forecastChart           the forecast's SVG geometry (band, median, baseline, threshold, crossing)
 *   boardDraft              the ONE ingestion payload for the board (POST /api/v1/events): status planning, never
 *                           confirmed, labelled unverified in its title, metadata and provenance, created by a named officer
 *   nearestSegment          the network road a reported place sits on (the board's events live on the road graph)
 *
 * Honesty: every claim keeps its label. A field report is UNVERIFIED-FIELD, a camera reading UNVERIFIED-CAMERA, the
 * waterlogging MODELLED (pumps EMULATED), the forecast SIMULATED while its history is. Nothing here confirms anything.
 * Ethics: the camera reading is about roads and vehicles only; no field here names, describes or counts a person.
 */

import { FIELD_SOURCES, FIELD_VERIFICATION } from './labels';
import { CITY_BBOX, inBox } from '$lib/city';

/** How far past the city box a camera may stand and still ask the city feeds for a street photo (degrees). */
export const STREET_PHOTO_MARGIN_DEG = 0.5;

export { FIELD_SOURCES, FIELD_VERIFICATION, fieldLabelOf } from './labels';

// ── small readers ──────────────────────────────────────────────────────────

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v.trim() : null);
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const strs = (v: unknown): string[] => (Array.isArray(v) ? v.map(str).filter((x): x is string => x !== null) : []);

// ── the field report (speech) ──────────────────────────────────────────────

export const REPORT_KINDS = ['waterlogging', 'jam', 'accident', 'tree_fall', 'blockade', 'procession', 'fire', 'live_wire', 'other'] as const;
export type ReportKind = (typeof REPORT_KINDS)[number];
export const SEVERITIES = ['low', 'medium', 'high'] as const;
export type Severity = (typeof SEVERITIES)[number];
export const SPOKEN_LANGS = ['mr', 'en', 'hi'] as const;
export type SpokenLang = (typeof SPOKEN_LANGS)[number];

export interface ReportPlace {
	id: string;
	nameEn: string;
	nameMr: string;
	lat: number;
	lon: number;
	/** 0..1, the matcher's score. */
	score: number;
	/** The words of the transcript that matched. */
	said: string | null;
	/** The officer picked it from the city's places (the matcher was not sure or was wrong). */
	chosen?: boolean;
}

/** A city landmark as the place an officer picks by hand (score 1: the officer's word, flagged as chosen). */
export function chosenPlace(l: { id: string; en: string; mr: string; lat: number; lon: number }): ReportPlace {
	return { id: l.id, nameEn: l.en, nameMr: l.mr, lat: l.lat, lon: l.lon, score: 1, said: null, chosen: true };
}

export interface FieldReport {
	reportId: string | null;
	receivedAt: string | null;
	place: ReportPlace | null;
	candidates: ReportPlace[];
	kind: ReportKind;
	kindCues: string[];
	severity: Severity;
	severityCues: string[];
	transcript: string;
	language: string;
	asrModel: string | null;
	asrConfidence: number | null;
	audioSeconds: number | null;
	latencyS: number | null;
	/** Always the honest label: a field report is a claim awaiting an officer, never anything more. */
	verification: 'UNVERIFIED-FIELD';
	typed: boolean;
}

function placeOf(v: unknown): ReportPlace | null {
	if (!isObj(v)) return null;
	const id = str(v.id);
	const lat = num(v.lat);
	const lon = num(v.lon);
	if (!id || lat === null || lon === null) return null;
	return {
		id,
		nameEn: str(v.name_en) ?? id,
		nameMr: str(v.name_mr) ?? str(v.name_en) ?? id,
		lat,
		lon,
		score: Math.max(0, Math.min(1, num(v.match_score) ?? 0)),
		said: str(v.matched_text),
	};
}

/** The structured report, or null when the answer is not one. The label is UNVERIFIED-FIELD whatever the wire says. */
export function parseFieldReport(raw: unknown, typed = false): FieldReport | null {
	if (!isObj(raw)) return null;
	const transcript = str(raw.transcript);
	if (transcript === null) return null;
	const kind = (REPORT_KINDS as readonly string[]).includes(String(raw.kind)) ? (raw.kind as ReportKind) : 'other';
	const severity = (SEVERITIES as readonly string[]).includes(String(raw.severity)) ? (raw.severity as Severity) : 'medium';
	const asr = isObj(raw.asr) ? raw.asr : {};
	const place = placeOf(raw.place);
	const seen = new Set<string>();
	const candidates: ReportPlace[] = [];
	for (const c of Array.isArray(raw.place_candidates) ? raw.place_candidates : []) {
		const p = placeOf(c);
		if (p && !seen.has(p.id)) {
			seen.add(p.id);
			candidates.push(p);
		}
	}
	return {
		reportId: str(raw.report_id),
		receivedAt: str(raw.received_at),
		place,
		candidates: candidates.slice(0, 3),
		kind,
		kindCues: strs(raw.kind_cues).slice(0, 6),
		severity,
		severityCues: strs(raw.severity_cues).slice(0, 6),
		transcript,
		language: str(raw.language) ?? 'mr',
		asrModel: str(asr.model),
		asrConfidence: num(asr.confidence),
		audioSeconds: num(asr.audio_seconds),
		latencyS: num(raw.latency_s),
		verification: 'UNVERIFIED-FIELD',
		typed,
	};
}

/** The cue words of a transcript, as runs to highlight (the cue's own "(≈)" suffix — a fuzzy match — is not in the text). */
export function cueRuns(transcript: string, cues: readonly string[]): Array<{ text: string; cue: boolean }> {
	const words = cues.map((c) => c.replace(/\s*\(≈\)\s*$/, '').trim()).filter((c) => c.length >= 2);
	if (!words.length) return [{ text: transcript, cue: false }];
	const esc = words.sort((a, b) => b.length - a.length).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
	const re = new RegExp(`(${esc.join('|')})`, 'g');
	const out: Array<{ text: string; cue: boolean }> = [];
	let last = 0;
	for (const m of transcript.matchAll(re)) {
		const at = m.index ?? 0;
		if (at > last) out.push({ text: transcript.slice(last, at), cue: false });
		out.push({ text: m[0], cue: true });
		last = at + m[0].length;
	}
	if (last < transcript.length) out.push({ text: transcript.slice(last), cue: false });
	return out;
}

/** The radius of the place's dashed ring in metres: wider the less sure the matcher is. */
export function placeRingM(score: number): number {
	if (score >= 0.95) return 140;
	if (score >= 0.85) return 260;
	return 480;
}

// ── the camera reading (vision) ────────────────────────────────────────────

export const ROAD_STATES = ['waterlogged', 'blocked', 'tree_fall', 'stalled_vehicle', 'crash_debris', 'congested', 'clear', 'unknown'] as const;
export type RoadStateName = (typeof ROAD_STATES)[number];
export const DEPTH_BANDS = ['none', 'below_kerb', 'up_to_wheel_hub', 'above_wheel_hub', 'unknown'] as const;
export type DepthBand = (typeof DEPTH_BANDS)[number];
export const VEHICLE_KEYS = ['cars', 'buses', 'two_wheelers', 'autos'] as const;

export interface RoadState {
	state: RoadStateName;
	confidence: number | null;
	vehicles: Record<(typeof VEHICLE_KEYS)[number], number | null>;
	depth: DepthBand | null;
	rationale: string | null;
	model: string | null;
	latencyS: number | null;
	/** A sentence about a person was removed by the service's output filter. */
	filtered: boolean;
	verification: 'UNVERIFIED-CAMERA';
}

export type RoadStateAnswer = { ok: true; reading: RoadState } | { ok: false; refused: true; policy: string; reason: string };

/** The reading (UNVERIFIED-CAMERA whatever the wire says) or a policy refusal; null for anything else. */
export function parseRoadState(raw: unknown): RoadStateAnswer | null {
	if (!isObj(raw)) return null;
	if (raw.refused === true) return { ok: false, refused: true, policy: str(raw.policy) ?? 'policy', reason: str(raw.reason) ?? str(raw.detail) ?? '' };
	const state = str(raw.state);
	if (!state || !(ROAD_STATES as readonly string[]).includes(state)) return null;
	const ve = isObj(raw.vehicles_estimate) ? raw.vehicles_estimate : {};
	const vehicles = Object.fromEntries(VEHICLE_KEYS.map((k) => [k, num(ve[k]) === null ? null : Math.max(0, Math.round(num(ve[k]) as number))])) as RoadState['vehicles'];
	const band = str(raw.water_depth_band);
	const reading: RoadState = {
		state: state as RoadStateName,
		confidence: num(raw.confidence) === null ? null : Math.max(0, Math.min(1, num(raw.confidence) as number)),
		vehicles,
		depth: band && (DEPTH_BANDS as readonly string[]).includes(band) ? (band as DepthBand) : null,
		rationale: str(raw.rationale),
		model: str(raw.model),
		latencyS: num(raw.latency_s),
		filtered: raw.filtered === true,
		verification: 'UNVERIFIED-CAMERA',
	};
	return { ok: true, reading };
}

/** A reading worth a board entry: never "clear" or "unclear". */
export function sendableState(s: RoadStateName): boolean {
	return s !== 'clear' && s !== 'unknown';
}

// ── the nearby street photo (city feeds → Mapillary) ───────────────────────

/** The credit and licence a Mapillary photo carries wherever it shows (data, not UI copy). */
export const STREET_PHOTO_CREDIT = '© Mapillary contributors';
export const STREET_PHOTO_LICENCE = 'CC BY-SA 4.0';
export const STREET_PHOTO_LICENCE_URL = 'https://creativecommons.org/licenses/by-sa/4.0/';
/** How far round the camera the city feeds look (their 150 m box). */
export const STREET_PHOTO_RANGE_M = 150;

export interface StreetPhoto {
	id: string;
	/** ISO capture time: a past photograph, possibly years old. */
	capturedAt: string | null;
	distanceM: number | null;
	/** The photo's own page on mapillary.com, where its contributor is credited (built from the id, never the wire). */
	pageUrl: string;
}

/** What the panel can offer: the photo, or why not (no key → the city feeds made no call). */
export type StreetPhotoInfo =
	| { kind: 'ready'; photo: StreetPhoto }
	| { kind: 'needs_key'; env: string }
	| { kind: 'none'; rangeM: number }
	| { kind: 'unavailable'; detail: string }
	| { kind: 'no_position' };

/** `lat=…&lon=…` for a camera inside the box the city feeds answer for (the City Pack's box and ~0.5° round it), else null. */
export function streetPhotoQuery(lon: number | null, lat: number | null): string | null {
	if (num(lon) === null || num(lat) === null) return null;
	if (!inBox(lon as number, lat as number, CITY_BBOX, STREET_PHOTO_MARGIN_DEG)) return null;
	return `lat=${(lat as number).toFixed(6)}&lon=${(lon as number).toFixed(6)}`;
}

/** The city feeds' GET /feeds/street-image answer → the panel's offer. */
export function parseStreetPhoto(raw: unknown): StreetPhotoInfo {
	if (!isObj(raw)) return { kind: 'unavailable', detail: 'no answer' };
	const state = str(raw.state) ?? '';
	const needs = /^needs ([A-Z][A-Z0-9_]*)$/.exec(state);
	if (needs) return { kind: 'needs_key', env: needs[1] };
	if (state !== 'live') return { kind: 'unavailable', detail: state || 'no answer' };
	const im = isObj(raw.image) ? raw.image : null;
	if (!im) return { kind: 'none', rangeM: num(raw.searched_m) ?? STREET_PHOTO_RANGE_M };
	const id = str(im.id);
	if (!id || !/^\d{1,24}$/.test(id)) return { kind: 'unavailable', detail: 'not a Mapillary image' };
	const at = str(im.captured_at);
	const d = num(im.distance_m);
	return {
		kind: 'ready',
		photo: { id, capturedAt: at && Number.isFinite(Date.parse(at)) ? at : null, distanceM: d === null ? null : Math.round(d), pageUrl: `https://www.mapillary.com/app/?pKey=${id}` },
	};
}

/** A capture date for the console: "29 Jun 2018" (IST, Latin digits, the month in the reader's language); null for none. */
export function photoDate(iso: string | null, lang: string): string | null {
	const ms = iso ? Date.parse(iso) : Number.NaN;
	if (!Number.isFinite(ms)) return null;
	const locale = lang === 'mr' ? 'mr-IN-u-nu-latn' : lang === 'hi' ? 'hi-IN-u-nu-latn' : 'en-GB';
	return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' }).format(ms);
}

// ── the board (the platform's ingestion path for a reported situation) ──────

/**
 * The corridor event kind a report maps to (traffic_oracle.events.EVENT_KINDS). Only kinds the public projection never
 * shows are used for what is not a gathering; the public feed drops every field- or camera-sourced row anyway.
 */
export const BOARD_KIND_FOR_REPORT: Readonly<Record<ReportKind, string>> = {
	waterlogging: 'flooding',
	jam: 'hazard',
	accident: 'road_accident',
	tree_fall: 'hazard',
	blockade: 'hazard',
	procession: 'procession',
	fire: 'hazard',
	live_wire: 'infra_failure',
	other: 'hazard',
};

export const BOARD_KIND_FOR_STATE: Readonly<Record<RoadStateName, string | null>> = {
	waterlogged: 'flooding',
	blocked: 'hazard',
	tree_fall: 'hazard',
	stalled_vehicle: 'hazard',
	crash_debris: 'road_accident',
	congested: 'hazard',
	clear: null,
	unknown: null,
};

const REPORT_WORDS: Record<ReportKind, string> = {
	waterlogging: 'waterlogging',
	jam: 'traffic jam',
	accident: 'accident',
	tree_fall: 'tree fall',
	blockade: 'road blocked',
	procession: 'procession',
	fire: 'fire',
	live_wire: 'live wire',
	other: 'situation',
};
const STATE_WORDS: Record<RoadStateName, string> = {
	waterlogged: 'waterlogged',
	blocked: 'road blocked',
	tree_fall: 'tree fall',
	stalled_vehicle: 'stalled vehicle',
	crash_debris: 'crash debris',
	congested: 'congested',
	clear: 'clear',
	unknown: 'unclear',
};

export interface BoardDraft {
	event_kind: string;
	protection_class: 'none';
	crowd_class: 'LOW';
	title: string;
	description: string;
	officer: string;
	source_kind: 'operator';
	route_spines: Array<{ label: string; segment_ids: number[] }>;
	planned_start: string;
	planned_end: string;
	metadata: Record<string, string | number | boolean>;
	provenance: Record<string, unknown>;
	geotag: { lon: number; lat: number } | null;
}

/** A named officer as the contract fields carry it (2..64 characters, no control or bidirectional characters), or null. */
export function officerOf(name: string | null | undefined): string | null {
	const who = (name ?? '').split(/\s+/).filter(Boolean).join(' ').slice(0, 64);
	if (who.length < 2) return null;
	if (/[\u0000-\u001f\u007f‎‏‪-‮⁦-⁩]/.test(who)) return null;
	return who;
}

const clip = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

/**
 * The board entry of a field report (POST /api/v1/events). It is created in `planning` — the oracle's own state for a
 * new event — by the named officer who sends it, labelled unverified in its title, metadata and provenance; nothing
 * here can confirm it (the oracle refuses CONFIRMED on create, and no closure, phase or route action rides along).
 */
export function boardDraftFromReport(r: FieldReport, place: ReportPlace, segmentId: number, officer: string, nowMs: number, inCity: boolean): BoardDraft {
	const kindWords = REPORT_WORDS[r.kind];
	return {
		event_kind: BOARD_KIND_FOR_REPORT[r.kind],
		protection_class: 'none',
		crowd_class: 'LOW',
		title: clip(`Unverified field report: ${kindWords} at ${place.nameEn}`, 200),
		description: clip(
			[
				`Field report by ${r.typed ? 'text' : 'voice'}, unverified (UNVERIFIED-FIELD). It is a claim awaiting an officer's confirmation, not an action.`,
				`Transcript (${r.language}): ${r.transcript}`,
				`Place: ${place.nameEn} / ${place.nameMr} (${place.chosen ? 'chosen by the officer' : `match ${Math.round(place.score * 100)}%`}). Kind: ${kindWords}. Severity: ${r.severity}.`,
				r.kindCues.length || r.severityCues.length ? `Cues: ${[...r.kindCues, ...r.severityCues].join(', ')}.` : '',
				r.typed ? '' : 'Audio was not stored.',
			]
				.filter(Boolean)
				.join('\n'),
			1800,
		),
		officer,
		source_kind: 'operator',
		route_spines: [{ label: 'field report location', segment_ids: [segmentId] }],
		planned_start: new Date(nowMs).toISOString(),
		planned_end: new Date(nowMs + 2 * 3600_000).toISOString(),
		metadata: {
			source: FIELD_SOURCES.voice,
			verification: FIELD_VERIFICATION.voice,
			opened_by: officer,
			report_kind: r.kind,
			severity: r.severity,
			place_id: place.id,
			...(r.reportId ? { report_id: r.reportId } : {}),
		},
		provenance: {
			feed: FIELD_SOURCES.voice,
			verification: FIELD_VERIFICATION.voice,
			input: r.typed ? 'text' : 'voice',
			asr_model: r.asrModel,
			asr_confidence: r.asrConfidence,
			place_match: place.chosen ? null : Math.round(place.score * 100) / 100,
			place_chosen_by_officer: place.chosen === true,
			kind_cues: r.kindCues,
			severity_cues: r.severityCues,
			audio_stored: false,
		},
		geotag: inCity ? { lon: place.lon, lat: place.lat } : null,
	};
}

/**
 * The board entry of a camera reading (same path, UNVERIFIED-CAMERA); null for a state that is not worth one. The still
 * it was read from is named: a sample still, or the nearby street photo (Mapillary, with its capture date) — never a
 * live frame.
 */
export function boardDraftFromReading(
	reading: RoadState,
	camera: { id: string; label: string; lon: number | null; lat: number | null; sample: string | null; reference?: { id: string; capturedAt: string | null } | null },
	segmentId: number,
	officer: string,
	nowMs: number,
	inCity: boolean,
): BoardDraft | null {
	const kind = BOARD_KIND_FOR_STATE[reading.state];
	if (!kind) return null;
	const words = STATE_WORDS[reading.state];
	const ref = camera.sample ? null : (camera.reference ?? null);
	const still = camera.sample
		? ` (sample still ${camera.sample}, not a live frame)`
		: ref
			? ` (reference photo: Mapillary ${ref.id}${photoDate(ref.capturedAt, 'en') ? `, taken ${photoDate(ref.capturedAt, 'en')}` : ''}, not a live frame)`
			: '';
	return {
		event_kind: kind,
		protection_class: 'none',
		crowd_class: 'LOW',
		title: clip(`Unverified camera reading: ${words} at ${camera.label}`, 200),
		description: clip(
			[
				`Camera still read by the on-premises vision model, unverified (UNVERIFIED-CAMERA). It is a claim awaiting an officer's confirmation, not an action.`,
				`Camera: ${camera.id}${still}.`,
				`Reading: ${words}${reading.confidence !== null ? ` (model confidence ${reading.confidence.toFixed(2)}, not calibrated)` : ''}.`,
				reading.rationale ? `Rationale: ${reading.rationale}` : '',
				'Roads and vehicles only; the still was not stored.',
			]
				.filter(Boolean)
				.join('\n'),
			1800,
		),
		officer,
		source_kind: 'operator',
		route_spines: [{ label: 'camera location', segment_ids: [segmentId] }],
		planned_start: new Date(nowMs).toISOString(),
		planned_end: new Date(nowMs + 2 * 3600_000).toISOString(),
		metadata: {
			source: FIELD_SOURCES.camera,
			verification: FIELD_VERIFICATION.camera,
			opened_by: officer,
			road_state: reading.state,
			camera_id: camera.id,
			...(camera.sample ? { sample: true } : {}),
			...(ref ? { reference_photo: true } : {}),
		},
		provenance: {
			feed: FIELD_SOURCES.camera,
			verification: FIELD_VERIFICATION.camera,
			model: reading.model,
			confidence: reading.confidence,
			water_depth_band: reading.depth,
			vehicles_estimate: reading.vehicles,
			sample_still: camera.sample,
			...(ref ? { reference_photo: { source: 'Mapillary', id: ref.id, captured_at: ref.capturedAt, licence: STREET_PHOTO_LICENCE } } : {}),
			image_stored: false,
		},
		geotag: inCity && camera.lon !== null && camera.lat !== null ? { lon: camera.lon, lat: camera.lat } : null,
	};
}

// ── the road under a place ─────────────────────────────────────────────────

type LonLat = readonly [number, number];

/** Metres between two lon/lat points (equirectangular: plenty at city scale). */
export function metresBetween(a: LonLat, b: LonLat): number {
	const k = Math.PI / 180;
	const x = (b[0] - a[0]) * k * Math.cos(((a[1] + b[1]) / 2) * k);
	const y = (b[1] - a[1]) * k;
	return Math.hypot(x, y) * 6_371_000;
}

function pointToSegmentM(p: LonLat, a: LonLat, b: LonLat): number {
	const k = Math.cos(p[1] * (Math.PI / 180));
	const ax = (a[0] - p[0]) * k, ay = a[1] - p[1];
	const bx = (b[0] - p[0]) * k, by = b[1] - p[1];
	const dx = bx - ax, dy = by - ay;
	const len2 = dx * dx + dy * dy;
	const t = len2 > 0 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2)) : 0;
	const cx = ax + t * dx, cy = ay + t * dy;
	return Math.hypot(cx, cy) * (Math.PI / 180) * 6_371_000;
}

/** The network road nearest a point, within `maxM` metres; null when none is that close. */
export function nearestSegment(
	at: LonLat,
	segments: Iterable<{ segmentId: number; coordinates: ReadonlyArray<readonly [number, number]> }>,
	maxM = 1500,
): { segmentId: number; distanceM: number } | null {
	let best: { segmentId: number; distanceM: number } | null = null;
	for (const s of segments) {
		const c = s.coordinates;
		for (let i = 0; i + 1 < c.length; i++) {
			const d = pointToSegmentM(at, c[i], c[i + 1]);
			if (d <= maxM && (!best || d < best.distanceM)) best = { segmentId: s.segmentId, distanceM: Math.round(d) };
		}
		if (c.length === 1) {
			const d = metresBetween(at, c[0]);
			if (d <= maxM && (!best || d < best.distanceM)) best = { segmentId: s.segmentId, distanceM: Math.round(d) };
		}
	}
	return best;
}

// ── waterlogging (hydro) ───────────────────────────────────────────────────

export type RiskClass = 0 | 1 | 2 | 3;

export interface WaterDrivers {
	rain: { label: string; past1h: number | null; next2h: number | null; peakMmH: number | null } | null;
	tide: { label: string; levelM: number | null; gateClosed: boolean; gateClosedMin: number | null; nextHighAt: string | null; nextHighM: number | null } | null;
	ground: { label: string; score: number | null; drainM: number | null; hotspot: string | null; hotspotM: number | null } | null;
	pumps: { label: string; station: string | null; available: number | null; total: number | null } | null;
}

export interface SegmentWater {
	segmentId: number;
	roadName: string;
	place: string | null;
	placeMr: string | null;
	lat: number | null;
	lon: number | null;
	risk: RiskClass;
	riskNow: RiskClass;
	depthBand: string | null;
	peakDepthCm: number | null;
	leadMin: number | null;
	deepLeadMin: number | null;
	elevated: boolean;
	drivers: WaterDrivers;
}

export interface Nowcast {
	generatedAt: string | null;
	horizonMin: number;
	labels: Record<string, string>;
	segments: SegmentWater[];
	flagged: number[];
	counts: [number, number, number, number];
}

const riskOf = (v: unknown): RiskClass => {
	const n = num(v);
	return n === null ? 0 : (Math.max(0, Math.min(3, Math.round(n))) as RiskClass);
};

function driversOf(v: unknown): WaterDrivers {
	const d = isObj(v) ? v : {};
	const rain = isObj(d.rain) ? d.rain : null;
	const tide = isObj(d.tide) ? d.tide : null;
	const ground = isObj(d.susceptibility) ? d.susceptibility : null;
	const pumps = isObj(d.pumps) ? d.pumps : null;
	const next = tide && isObj(tide.next_high_water) ? tide.next_high_water : null;
	return {
		rain: rain ? { label: str(rain.label) ?? 'LIVE', past1h: num(rain.past_1h_mm), next2h: num(rain.next_2h_mm), peakMmH: num(rain.peak_next_2h_mm_h) } : null,
		tide: tide
			? {
					label: str(tide.label) ?? 'MODELLED',
					levelM: num(tide.level_m),
					gateClosed: tide.gate_closed_now === true,
					gateClosedMin: num(tide.gate_closed_minutes_in_horizon),
					nextHighAt: next ? str(next.at) : null,
					nextHighM: next ? num(next.level_m) : null,
				}
			: null,
		ground: ground ? { label: str(ground.label) ?? 'MODELLED', score: num(ground.score), drainM: num(ground.dist_drain_m), hotspot: str(ground.nearest_hotspot), hotspotM: num(ground.dist_hotspot_m) } : null,
		pumps: pumps ? { label: str(pumps.label) ?? 'EMULATED', station: str(pumps.station), available: num(pumps.pumps_available), total: num(pumps.pumps_total) } : null,
	};
}

export function parseSegmentWater(v: unknown): SegmentWater | null {
	if (!isObj(v)) return null;
	const id = num(v.segment_id);
	if (id === null) return null;
	return {
		segmentId: id,
		roadName: str(v.road_name) ?? `#${id}`,
		place: str(v.place),
		placeMr: str(v.place_mr),
		lat: num(v.lat),
		lon: num(v.lon),
		risk: riskOf(v.risk_class),
		riskNow: riskOf(v.risk_class_now),
		depthBand: str(v.expected_depth_band),
		peakDepthCm: num(v.modelled_peak_depth_cm),
		leadMin: num(v.lead_time_min),
		deepLeadMin: num(v.lead_time_deep_min),
		elevated: v.elevated === true,
		drivers: driversOf(v.drivers),
	};
}

export function parseNowcast(raw: unknown): Nowcast | null {
	if (!isObj(raw) || !Array.isArray(raw.segments)) return null;
	const segments = raw.segments.map(parseSegmentWater).filter((s): s is SegmentWater => s !== null);
	const counts: [number, number, number, number] = [0, 0, 0, 0];
	for (const s of segments) counts[s.risk]++;
	const labels: Record<string, string> = {};
	if (isObj(raw.labels)) for (const [k, v] of Object.entries(raw.labels)) if (typeof v === 'string') labels[k] = v;
	return {
		generatedAt: str(raw.generated_at),
		horizonMin: num(raw.horizon_min) ?? 120,
		labels,
		segments,
		flagged: segments.filter((s) => s.risk >= 2).map((s) => s.segmentId),
		counts,
	};
}

/** The roads at risk, worst first, then soonest. */
export function atRisk(n: Nowcast, min: RiskClass = 1): SegmentWater[] {
	return n.segments.filter((s) => s.risk >= min).sort((a, b) => b.risk - a.risk || (a.leadMin ?? 999) - (b.leadMin ?? 999));
}

/** The minutes a public sentence names: the class-2 lead for deep water, else the peak lead; null when it is already so. */
export function leadFor(s: SegmentWater): number | null {
	const m = s.risk >= 2 && s.deepLeadMin !== null ? s.deepLeadMin : s.leadMin;
	return m !== null && m > 0 ? Math.round(m) : null;
}

/** An honest label in words for a driver (the service's LIVE / MODELLED (approximate) / EMULATED). */
export function labelKey(label: string | null | undefined): 'live' | 'modelled' | 'emulated' | 'simulated' {
	const l = String(label ?? '').toUpperCase();
	if (l.startsWith('EMULATED')) return 'emulated';
	if (l.startsWith('SIMULATED')) return 'simulated';
	if (l.startsWith('LIVE')) return 'live';
	return 'modelled';
}

// ── the storm replay (hindsight) ───────────────────────────────────────────

export interface ReplaySegment {
	peakClass: RiskClass;
	peakBand: string | null;
	peakAt: string | null;
	firstDeep: string | null;
	rainMm: number | null;
	elevated: boolean;
}

export interface StormReplay {
	title: string;
	label: string;
	aliporeMm: number | null;
	reportedOnNetwork: number | null;
	reportedFlagged: number | null;
	segment: ReplaySegment | null;
}

/** "2025-08-19 06:20" (IST, as the service writes it) → "03:15"; anything else as it is. */
const hhmm = (v: unknown): string | null => {
	const t = str(v);
	if (!t) return null;
	const m = /(\d{2}:\d{2})/.exec(t);
	return m ? m[1] : t;
};

/**
 * One road in the hydro service's replay of 18–19 Aug 2025, from its IMD-gauge-anchored run (observed rain totals, a
 * modelled 15-minute shape, the same depth model): HINDSIGHT, never a forecast. The archive run (gridded rain that
 * missed the storm) is the service's own finding and is not shown per road.
 */
export function parseReplay(raw: unknown, segmentId: number): StormReplay | null {
	if (!isObj(raw) || !isObj(raw.runs) || !isObj(raw.runs.imd_gauge_anchored)) return null;
	const run = raw.runs.imd_gauge_anchored;
	const check = isObj(run.reported_check) ? run.reported_check : {};
	const seg = (Array.isArray(run.segments) ? run.segments : []).filter(isObj).find((x) => num(x.segment_id) === segmentId) ?? null;
	return {
		title: str(raw.title) ?? '22–23 September 2025',
		label: str(run.label) ?? 'OBSERVED totals · MODELLED depth',
		aliporeMm: num(run.observed_window_total_mm ?? run.alipore_window_total_mm),
		reportedOnNetwork: num(check.on_network),
		reportedFlagged: num(check.flagged),
		segment: seg
			? {
					peakClass: riskOf(seg.peak_class),
					peakBand: str(seg.peak_band),
					peakAt: hhmm(seg.peak_at_ist),
					firstDeep: hhmm(seg.first_class2_ist),
					rainMm: num(seg.rain_total_mm),
					elevated: seg.elevated === true,
				}
			: null,
	};
}

// ── tide and rain in plain words ───────────────────────────────────────────

export interface TideNow {
	label: string;
	levelM: number | null;
	rising: boolean;
	gateClosed: boolean;
	gateCloseM: number | null;
	nextHighAt: number | null;
	nextHighM: number | null;
	nextLowAt: number | null;
	series: Array<{ t: number; m: number }>;
}

export function parseTide(raw: unknown, nowMs = Date.now()): TideNow | null {
	if (!isObj(raw)) return null;
	const now = isObj(raw.now) ? raw.now : null;
	if (!now) return null;
	const ext = Array.isArray(raw.extremes) ? raw.extremes.filter(isObj) : [];
	const after = (kind: string) =>
		ext
			.filter((e) => e.kind === kind)
			.map((e) => ({ at: Date.parse(String(e.at)), m: num(e.level_m) }))
			.filter((e) => Number.isFinite(e.at) && e.at >= nowMs - 60_000)
			.sort((a, b) => a.at - b.at)[0] ?? null;
	const hi = after('high');
	const lo = after('low');
	const series = (Array.isArray(raw.series) ? raw.series : [])
		.filter(isObj)
		.map((p) => ({ t: Date.parse(String(p.t)), m: num(p.level_m) }))
		.filter((p): p is { t: number; m: number } => Number.isFinite(p.t) && p.m !== null);
	return {
		label: str(raw.label) ?? 'MODELLED',
		levelM: num(now.level_m),
		rising: now.rising === true,
		gateClosed: now.gate_closed === true,
		gateCloseM: num(raw.gate_close_level_m),
		nextHighAt: hi?.at ?? null,
		nextHighM: hi?.m ?? null,
		nextLowAt: lo?.at ?? null,
		series,
	};
}

export interface RainNow {
	label: string;
	stale: boolean;
	nowMmH: number;
	next2hMm: number;
	past3hMm: number;
}

/** The city's rain: the mean series' current quarter-hour and the totals around it (mm/h steps of 15 min). */
export function parseRain(raw: unknown, nowMs = Date.now()): RainNow | null {
	if (!isObj(raw) || !isObj(raw.city) || !Array.isArray(raw.city.series)) return null;
	const pts = raw.city.series
		.filter(isObj)
		.map((p) => ({ t: Date.parse(String(p.t)), v: num(p.mm_h) ?? 0 }))
		.filter((p) => Number.isFinite(p.t))
		.sort((a, b) => a.t - b.t);
	if (!pts.length) return null;
	const q = 15 * 60_000;
	const cur = [...pts].reverse().find((p) => p.t <= nowMs) ?? pts[0];
	const sum = (from: number, to: number) => pts.filter((p) => p.t > from && p.t <= to).reduce((n, p) => n + p.v * 0.25, 0);
	return {
		label: str(raw.label) ?? 'LIVE',
		stale: raw.stale === true,
		nowMmH: Math.round(cur.v * 10) / 10,
		next2hMm: Math.round(sum(nowMs, nowMs + 8 * q) * 10) / 10,
		past3hMm: Math.round(sum(nowMs - 12 * q, nowMs) * 10) / 10,
	};
}

/** The rain in one word: none, light or heavy (IMD's 24-h "heavy" scaled to 2 h is far above this; 7.5 mm/h is IMD's "heavy" hourly cue). */
export function rainWord(r: RainNow): 'none' | 'light' | 'heavy' {
	if (r.next2hMm >= 15 || r.nowMmH >= 7.5) return 'heavy';
	if (r.next2hMm >= 0.5 || r.nowMmH >= 0.5) return 'light';
	return 'none';
}

// ── the corridor forecast ──────────────────────────────────────────────────

export interface ForecastStep {
	lead: number;
	t: number;
	p10: number;
	p50: number;
	p90: number;
	baseline: number | null;
}

export interface SegmentForecast {
	segmentId: number;
	roadName: string;
	place: string | null;
	model: string | null;
	threshold: number;
	horizonMin: number;
	dataLabel: string;
	historySource: string | null;
	nowVc: number | null;
	nowSpeed: number | null;
	steps: ForecastStep[];
	crossing: { inMin: number; p10: number | null; p50: number | null; p90: number | null } | null;
	aboveNow: boolean;
	proposal: { summary: string; labels: string[] } | null;
	note: string | null;
}

export function parseSegmentForecast(raw: unknown): SegmentForecast | null {
	if (!isObj(raw) || !isObj(raw.segment)) return null;
	const s = raw.segment;
	const id = num(s.segment_id);
	if (id === null) return null;
	const steps: ForecastStep[] = [];
	for (const st of Array.isArray(s.steps) ? s.steps : []) {
		if (!isObj(st) || !isObj(st.vc)) continue;
		const lead = num(st.lead_min);
		const p10 = num(st.vc.p10), p50 = num(st.vc.p50), p90 = num(st.vc.p90);
		if (lead === null || p10 === null || p50 === null || p90 === null) continue;
		steps.push({ lead, t: Date.parse(String(st.t)), p10: Math.min(p10, p50), p50, p90: Math.max(p90, p50), baseline: num(st.baseline_vc_p50) });
	}
	steps.sort((a, b) => a.lead - b.lead);
	const now = isObj(s.now) ? s.now : {};
	const cr = isObj(s.crossing) ? s.crossing : null;
	const prop = isObj(raw.proposal) ? raw.proposal : null;
	return {
		segmentId: id,
		roadName: str(s.road_name) ?? `#${id}`,
		place: str(s.place),
		model: str(s.model) ?? str(raw.model),
		threshold: num(raw.threshold_vc) ?? 0.8,
		horizonMin: num(raw.horizon_min) ?? 120,
		dataLabel: str(s.data_label) ?? 'SIMULATED',
		historySource: str(s.history_source),
		nowVc: num(now.vc),
		nowSpeed: num(now.speed_kmh),
		steps,
		crossing: cr && num(cr.in_min) !== null ? { inMin: num(cr.in_min) as number, p10: num(cr.vc_p10), p50: num(cr.vc_p50), p90: num(cr.vc_p90) } : null,
		aboveNow: s.above_threshold_now === true,
		proposal: prop && str(prop.summary) ? { summary: str(prop.summary) as string, labels: strs(prop.labels) } : null,
		note: str(raw.data_note),
	};
}

export interface ForecastChart {
	w: number;
	h: number;
	yMin: number;
	yMax: number;
	band: string;
	median: string;
	baseline: string | null;
	thresholdY: number;
	nowPt: { x: number; y: number } | null;
	crossPt: { x: number; y: number } | null;
	ticks: Array<{ x: number; min: number }>;
	yTicks: Array<{ y: number; v: number }>;
	pad: { l: number; r: number; t: number; b: number };
}

const f1 = (v: number) => Math.round(v * 10) / 10;

/** The chart's geometry: x is minutes ahead (0 = now), y is V/C over a range rounded to 0.2 around the band and 0.8. */
export function forecastChart(fc: SegmentForecast, w = 640, h = 220): ForecastChart {
	const pad = { l: 40, r: 16, t: 14, b: 26 };
	const horizon = Math.max(15, fc.horizonMin);
	const values = [fc.threshold, ...(fc.nowVc !== null ? [fc.nowVc] : []), ...fc.steps.flatMap((s) => [s.p10, s.p90, ...(s.baseline !== null ? [s.baseline] : [])])];
	const yMax = Math.ceil((Math.max(...values) + 0.05) * 5) / 5;
	const yMin = Math.max(0, Math.floor((Math.min(...values) - 0.05) * 5) / 5);
	const span = Math.max(0.2, yMax - yMin);
	const x = (m: number) => f1(pad.l + (m / horizon) * (w - pad.l - pad.r));
	const y = (v: number) => f1(pad.t + (1 - (Math.max(yMin, Math.min(yMax, v)) - yMin) / span) * (h - pad.t - pad.b));
	const pts = [...(fc.nowVc !== null ? [{ lead: 0, p10: fc.nowVc, p50: fc.nowVc, p90: fc.nowVc, baseline: null as number | null }] : []), ...fc.steps];
	const line = (sel: (s: (typeof pts)[number]) => number | null) => {
		const xs = pts.filter((s) => sel(s) !== null);
		return xs.length >= 2 ? xs.map((s, i) => `${i ? 'L' : 'M'}${x(s.lead)} ${y(sel(s) as number)}`).join(' ') : '';
	};
	const upper = pts.map((s) => `${x(s.lead)} ${y(s.p90)}`);
	const lower = [...pts].reverse().map((s) => `${x(s.lead)} ${y(s.p10)}`);
	const band = pts.length >= 2 ? `M${upper.join(' L')} L${lower.join(' L')} Z` : '';
	const cross = fc.crossing ? (fc.steps.find((s) => s.lead === fc.crossing?.inMin) ?? null) : null;
	const ticks = [0, 30, 60, 90, 120].filter((m) => m <= horizon).map((m) => ({ x: x(m), min: m }));
	const step = span > 0.8 ? 0.4 : span > 0.4 ? 0.2 : 0.1;
	const yTicks: Array<{ y: number; v: number }> = [];
	for (let v = yMin; v <= yMax + 1e-9; v += step) yTicks.push({ y: y(v), v: Math.round(v * 10) / 10 });
	return {
		w,
		h,
		yMin,
		yMax,
		band,
		median: line((s) => s.p50),
		baseline: line((s) => s.baseline) || null,
		thresholdY: y(fc.threshold),
		nowPt: fc.nowVc !== null ? { x: x(0), y: y(fc.nowVc) } : null,
		crossPt: cross ? { x: x(cross.lead), y: y(cross.p50) } : null,
		ticks,
		yTicks,
		pad,
	};
}

// ── text to speech (public "Listen") ───────────────────────────────────────

/** A clock for the ear (IST): the part of the day, the 12-hour hour, the minute, and whether it is tomorrow. */
export function spokenClock(ms: number, nowMs = Date.now()): { part: 'night' | 'dawn' | 'morning' | 'noon' | 'afternoon' | 'evening'; hour: number; minute: number; tomorrow: boolean } {
	const ist = (v: number) => new Date(v + 5.5 * 3600_000);
	const d = ist(ms);
	const h = d.getUTCHours();
	const part = h < 4 ? 'night' : h < 6 ? 'dawn' : h < 12 ? 'morning' : h < 16 ? 'noon' : h < 18 ? 'afternoon' : h < 20 ? 'evening' : 'night';
	const day = (x: Date) => `${x.getUTCFullYear()}-${x.getUTCMonth()}-${x.getUTCDate()}`;
	return { part, hour: h % 12 || 12, minute: d.getUTCMinutes(), tomorrow: day(d) !== day(ist(nowMs)) };
}

/** The public speak limit (the deck's gate admits ≤ 400 characters anonymously). */
export const SPEAK_MAX = 400;

/** The text a Listen button sends: whitespace folded, cut at a sentence end within the limit. */
export function speakable(text: string, max = SPEAK_MAX): string {
	const t = text.replace(/\s+/g, ' ').trim();
	if (t.length <= max) return t;
	const cut = t.slice(0, max);
	const end = Math.max(cut.lastIndexOf('।'), cut.lastIndexOf('. '), cut.lastIndexOf('? '), cut.lastIndexOf('! '));
	return (end > max * 0.4 ? cut.slice(0, end + 1) : cut).trim();
}

/** The language a public page speaks in: its own (mr | en | hi), English for anything else (the product's default). */
export function speakLang(lang: string | null | undefined): SpokenLang {
	return lang === 'mr' || lang === 'hi' ? lang : 'en';
}
