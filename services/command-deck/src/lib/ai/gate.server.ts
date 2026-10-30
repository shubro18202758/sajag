/**
 * The operator gate for the on-prem AI services (server-only; used by src/hooks.server.ts).
 *
 * With SAJAG_OPERATOR_PIN set, every proxied AI request without the operator session is DEFAULT-DENIED (403),
 * exactly like the oracle, brain and emulator prefixes — forecasts, the twin, vision and the hydro proposals are
 * operator material. The public pages need a short allowlist, decided on the CANONICAL path (once-decoded, the
 * string uvicorn routes on; canonicalGatePath) and on the path the service actually serves (the deck strips the
 * prefix, so /api/hydro/hydro/nowcast reaches the service as /hydro/nowcast):
 *
 *   GET|HEAD /api/hydro/hydro/nowcast | tide | rain    read-only, no "force" (a forced refresh calls out to the
 *                                                      rain provider: operators only)
 *   GET|HEAD /api/cityfeeds/feeds/summary | air        the citizen page's "Air today" (read-only, no "force")
 *   POST     /api/speech/speech/speak                  the citizen page reads an advisory aloud: a JSON body with
 *                                                      `text` of at most SPEAK_MAX_CHARS characters, at most
 *                                                      SPEAK_MAX_PER_WINDOW requests per client per minute (429)
 *
 * Nothing else under /api/speech, /api/forecast, /api/vision, /api/hydro, /api/twin or /api/cityfeeds passes anonymously — not
 * transcription or field reports (an officer's tool), not the replay, the pumps or any proposal, not the road-state
 * panel's street photo (GET /api/cityfeeds/feeds/street-image[.jpg]: a signed-in officer's, like every route above
 * once the session cookie is valid). An allowlist on
 * purpose: a route added to a service later is gated the day it ships. Routes that do not exist upstream are never
 * allow-listed.
 */
import { canonicalGatePath } from '$lib/shell/operator-session.server';

export const AI_PREFIXES = ['/api/speech', '/api/forecast', '/api/vision', '/api/hydro', '/api/twin', '/api/cityfeeds'] as const;

export const SPEAK_MAX_CHARS = 400;
export const SPEAK_MAX_BYTES = 4096;
export const SPEAK_MAX_PER_WINDOW = 10;
const SPEAK_WINDOW_MS = 60_000;

const PUBLIC_AI_READS: readonly RegExp[] = [/^\/api\/hydro\/hydro\/(?:nowcast|tide|rain)$/, /^\/api\/cityfeeds\/feeds\/(?:summary|air)$/];
const PUBLIC_SPEAK = /^\/api\/speech\/speech\/speak$/;

export function underAiPrefix(path: string): boolean {
	return AI_PREFIXES.some((p) => path === p || path.startsWith(`${p}/`));
}

/**
 * Whether an ANONYMOUS request (gate on, no session, not a sub-request) to an AI prefix may pass:
 * 'allow' (a public read), 'check-speak' (the speak request: the hook checks its body and the client's rate),
 * or 'deny'. 'not-ai' for a path outside the AI prefixes (the platform gate decides those).
 */
export function aiGateDecision(method: string, pathname: string, search = ''): 'not-ai' | 'allow' | 'check-speak' | 'deny' {
	const path = canonicalGatePath(pathname);
	if (!underAiPrefix(pathname) && !(path && underAiPrefix(path))) return 'not-ai';
	if (path === null) return 'deny';
	const m = method.toUpperCase();
	if (m === 'GET' || m === 'HEAD') {
		if (/(?:^|[?&])force(?:=|&|$)/i.test(search)) return 'deny';
		return PUBLIC_AI_READS.some((re) => re.test(path)) ? 'allow' : 'deny';
	}
	if (m === 'POST' && PUBLIC_SPEAK.test(path)) return 'check-speak';
	return 'deny';
}

/** The speak body an anonymous caller may send: JSON with a non-empty `text` of at most SPEAK_MAX_CHARS characters. */
export async function speakBodyOk(request: Request): Promise<boolean> {
	const len = Number(request.headers.get('content-length') ?? '0');
	if (Number.isFinite(len) && len > SPEAK_MAX_BYTES) return false;
	try {
		const raw = await request.clone().text();
		if (raw.length > SPEAK_MAX_BYTES) return false;
		const body = JSON.parse(raw) as { text?: unknown } | null;
		const text = typeof body?.text === 'string' ? body.text.trim() : '';
		return text.length > 0 && [...text].length <= SPEAK_MAX_CHARS;
	} catch {
		return false;
	}
}

const speakLog = new Map<string, number[]>();

/** Records one anonymous speak request for `key`; false once the client is over its per-minute allowance. */
export function takeSpeak(key: string, now = Date.now()): boolean {
	const list = (speakLog.get(key) ?? []).filter((t) => now - t < SPEAK_WINDOW_MS);
	if (list.length >= SPEAK_MAX_PER_WINDOW) {
		speakLog.set(key, list);
		return false;
	}
	list.push(now);
	speakLog.set(key, list);
	if (speakLog.size > 5000) for (const [k, v] of speakLog) if (!v.some((t) => now - t < SPEAK_WINDOW_MS)) speakLog.delete(k);
	return true;
}

/** Test hook: forget every recorded speak request. */
export function resetSpeak(): void {
	speakLog.clear();
}
