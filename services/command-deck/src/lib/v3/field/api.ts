/**
 * The field AI's calls — same-origin /api/* only (the deck proxies each to its on-premises service; the operator
 * gate admits the public reads and the public speak anonymously and everything else with the officer's session).
 *
 *   POST /api/speech/speech/report?lang=   audio (the MediaRecorder blob) or {"text"} → a field report (UNVERIFIED-FIELD)
 *   POST /api/speech/speech/speak          {text, lang} → audio/wav (synthetic voice)
 *   POST /api/vision/vision/road-state     a JPEG/PNG still → a road state (UNVERIFIED-CAMERA) or a 403 policy refusal
 *   GET  /api/cityfeeds/feeds/street-image[.jpg]?lat=&lon=   the nearby street photo's facts, then its bytes (Mapillary,
 *                                          fetched by the city feeds so the page stays same-origin; officers only)
 *   GET  /api/hydro/hydro/nowcast | tide | rain
 *   GET  /api/forecast/forecast/segment/{id}
 *   (the board entry, POST /api/v1/events, is ./board.ts: operator pages only)
 *
 * Nothing is cached or stored here: the audio and the still live only in the request body.
 */
import {
	parseFieldReport,
	parseNowcast,
	parseReplay,
	parseRain,
	parseRoadState,
	parseSegmentForecast,
	parseStreetPhoto,
	parseTide,
	speakable,
	type FieldReport,
	type Nowcast,
	type RainNow,
	type RoadStateAnswer,
	type SegmentForecast,
	type StormReplay,
	type SpokenLang,
	type StreetPhotoInfo,
	type TideNow,
} from './model';

/**
 * The deck proxies /api/<service> to the service with the prefix stripped, and every service serves under its own
 * name (/speech/report, /hydro/nowcast …), so the same-origin path names the service twice — the paths the deck's
 * gate allow-lists for the public pages (GET /api/hydro/hydro/nowcast | tide | rain, POST /api/speech/speech/speak).
 */
export const SPEECH = '/api/speech/speech';
export const VISION = '/api/vision/vision';
export const HYDRO = '/api/hydro/hydro';
export const FORECAST = '/api/forecast/forecast';
export const FEEDS = '/api/cityfeeds/feeds';

/** Why a call did not answer: the model cannot load now (503), too many asks (429), refused, unreachable or bad input. */
export class FieldApiError extends Error {
	constructor(
		readonly kind: 'busy' | 'rate' | 'refused' | 'down' | 'bad' | 'gate',
		readonly status: number,
		readonly detail: string,
	) {
		super(`${kind} (${status}): ${detail}`);
	}
}

async function detailOf(res: Response): Promise<string> {
	try {
		const body = (await res.json()) as { detail?: unknown; reason?: unknown };
		const d = body?.detail ?? body?.reason;
		return typeof d === 'string' ? d : JSON.stringify(d ?? '').slice(0, 200);
	} catch {
		return res.statusText || String(res.status);
	}
}

export async function fail(res: Response): Promise<never> {
	const detail = await detailOf(res);
	const kind = res.status === 503 ? 'busy' : res.status === 429 ? 'rate' : res.status === 403 ? 'gate' : res.status >= 500 ? 'down' : 'bad';
	throw new FieldApiError(kind, res.status, detail);
}

export async function call(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
	try {
		return await fetch(url, { credentials: 'same-origin', ...init, signal: init.signal ?? AbortSignal.timeout(timeoutMs) });
	} catch (err) {
		if (err instanceof DOMException && err.name === 'AbortError' && init.signal?.aborted) throw err;
		throw new FieldApiError('down', 0, err instanceof Error ? err.message : String(err));
	}
}

async function getJson(url: string, timeoutMs = 20_000, signal?: AbortSignal): Promise<unknown> {
	const res = await call(url, { headers: { accept: 'application/json' }, signal }, timeoutMs);
	if (!res.ok) await fail(res);
	return res.json();
}

/** The MIME type the services accept for a recording (codec parameters dropped). */
export function audioType(blob: Blob): string {
	const t = (blob.type || 'audio/webm').split(';')[0].trim().toLowerCase();
	return /^audio\/(webm|ogg|wav|x-wav|wave|mpeg|mp4)$/.test(t) ? t : 'audio/webm';
}

/** A spoken report → its structured reading. */
export async function reportFromAudio(blob: Blob, lang: SpokenLang, signal?: AbortSignal): Promise<FieldReport> {
	const res = await call(`${SPEECH}/report?lang=${lang}`, { method: 'POST', headers: { 'content-type': audioType(blob) }, body: blob, signal }, 90_000);
	if (!res.ok) await fail(res);
	const r = parseFieldReport(await res.json(), false);
	if (!r) throw new FieldApiError('bad', 200, 'not a field report');
	return r;
}

/** A typed report → its structured reading (the same rules, no audio). */
export async function reportFromText(text: string, lang: SpokenLang, signal?: AbortSignal): Promise<FieldReport> {
	const res = await call(`${SPEECH}/report?lang=${lang}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text: text.slice(0, 600) }), signal }, 30_000);
	if (!res.ok) await fail(res);
	const r = parseFieldReport(await res.json(), true);
	if (!r) throw new FieldApiError('bad', 200, 'not a field report');
	return r;
}

/** An advisory read aloud: the wav as a blob (synthetic voice). */
export async function speak(text: string, lang: SpokenLang, signal?: AbortSignal): Promise<Blob> {
	const body = speakable(text);
	if (!body) throw new FieldApiError('bad', 0, 'nothing to read');
	const res = await call(`${SPEECH}/speak`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text: body, lang }), signal }, 90_000);
	if (!res.ok) await fail(res);
	return res.blob();
}

/** A camera still → its road state (or the service's policy refusal, which is an answer, not an error). */
export async function readRoadState(image: Blob, signal?: AbortSignal): Promise<RoadStateAnswer> {
	const type = (image.type || 'image/jpeg').split(';')[0];
	if (type !== 'image/jpeg' && type !== 'image/png') throw new FieldApiError('bad', 415, 'a JPEG or PNG still');
	const res = await call(`${VISION}/road-state`, { method: 'POST', headers: { 'content-type': type }, body: image, signal }, 90_000);
	if (res.status === 403) {
		const body = await res.json().catch(() => null);
		const refusal = parseRoadState(body);
		if (refusal && !refusal.ok) return refusal;
		await fail(res);
	}
	if (!res.ok) await fail(res);
	const r = parseRoadState(await res.json());
	if (!r) throw new FieldApiError('bad', 200, 'not a road state');
	return r;
}

/** The nearby street photo's facts for `query` (model.streetPhotoQuery); without the key the city feeds call nobody. */
export async function fetchStreetPhotoInfo(query: string, signal?: AbortSignal): Promise<StreetPhotoInfo> {
	return parseStreetPhoto(await getJson(`${FEEDS}/street-image?${query}`, 20_000, signal));
}

/** That photo as a JPEG/PNG blob, read into memory only (the city feeds fetch it from Mapillary's CDN). */
export async function fetchStreetPhoto(query: string, signal?: AbortSignal): Promise<Blob> {
	const res = await call(`${FEEDS}/street-image.jpg?${query}`, { headers: { accept: 'image/jpeg, image/png' }, signal }, 20_000);
	if (!res.ok) await fail(res);
	const type = (res.headers.get('content-type') ?? '').split(';')[0].trim().toLowerCase();
	if (type !== 'image/jpeg' && type !== 'image/png') throw new FieldApiError('bad', 415, 'not a JPEG or PNG');
	const blob = await res.blob();
	return blob.type === type ? blob : new Blob([blob], { type });
}

export async function fetchNowcast(signal?: AbortSignal): Promise<Nowcast> {
	const n = parseNowcast(await getJson(`${HYDRO}/nowcast`, 30_000, signal));
	if (!n) throw new FieldApiError('bad', 200, 'not a nowcast');
	return n;
}

/** The hydro service's replay of the 18–19 Aug 2025 storm (compute only: operator pages; the public gate refuses it). */
export async function fetchReplay(segmentId: number, signal?: AbortSignal): Promise<StormReplay> {
	const res = await call(`${HYDRO}/replay?event=2025-08-19`, { method: 'POST', headers: { accept: 'application/json' }, signal }, 120_000);
	if (!res.ok) await fail(res);
	const r = parseReplay(await res.json(), segmentId);
	if (!r) throw new FieldApiError('bad', 200, 'not a replay');
	return r;
}

export async function fetchTide(signal?: AbortSignal): Promise<TideNow> {
	const t = parseTide(await getJson(`${HYDRO}/tide?hours=24`, 20_000, signal));
	if (!t) throw new FieldApiError('bad', 200, 'not a tide answer');
	return t;
}

export async function fetchRain(signal?: AbortSignal): Promise<RainNow> {
	const r = parseRain(await getJson(`${HYDRO}/rain`, 20_000, signal));
	if (!r) throw new FieldApiError('bad', 200, 'not a rain answer');
	return r;
}

export async function fetchSegmentForecast(segmentId: number, signal?: AbortSignal): Promise<SegmentForecast> {
	if (!Number.isInteger(segmentId) || segmentId <= 0) throw new FieldApiError('bad', 0, 'segment id');
	const f = parseSegmentForecast(await getJson(`${FORECAST}/segment/${segmentId}?horizon_min=120`, 60_000, signal));
	if (!f) throw new FieldApiError('bad', 200, 'not a forecast');
	return f;
}
