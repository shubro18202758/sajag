/**
 * Deck edge — the adapter-node reverse proxy (counterpart of the vite dev
 * proxy, vite.config.ts server.proxy, mirroring frontend/nginx.gb10.conf),
 * the security headers of every response, and the opt-in operator gate.
 *
 * The gods-eye-deck runs host-networked like traffic-oracle and convoy-brain
 * (compose service names do not resolve off the bridge and bridge→host-
 * gateway traffic is firewall-dropped — verified in the gb10 override
 * header), so every upstream is a FIXED LOOPBACK CONFIG CONSTANT (the C5
 * carve-out; none of these is external input). The HOST is pinned to
 * 127.0.0.1 unconditionally; only the PORTS are env-overridable so a
 * parallel clone of the stack (compose.argus-override.yml) can proxy to its
 * own peers without touching the loopback-only security contract:
 *
 *   /api/v1      → http://127.0.0.1:${ORACLE_PORT:-8091}     (traffic-oracle)
 *   /api/traffic → http://127.0.0.1:${ORACLE_PORT:-8091}     (traffic-oracle)
 *   /api/convoy  → http://127.0.0.1:${BRAIN_PORT:-8092}      (convoy-brain, strip)
 *   /api/emulator→ http://127.0.0.1:${EMULATOR_PORT:-8090}   (event-emulator, strip)
 *   /api/speech  → http://127.0.0.1:${SPEECH_PORT:-8194}     (Marathi voice: transcribe, field report, speak; strip)
 *   /api/forecast→ http://127.0.0.1:${FORECAST_PORT:-8195}   (corridor forecasting; strip)
 *   /api/vision  → http://127.0.0.1:${VISION_PORT:-8196}     (camera road state, vehicles and roads only; strip)
 *   /api/hydro   → http://127.0.0.1:${HYDRO_PORT:-8197}      (waterlogging nowcast; strip)
 *   /api/twin    → http://127.0.0.1:${TWIN_PORT:-8198}       (signal-timing twin; computes, never writes; strip)
 *   /api/cityfeeds → http://127.0.0.1:${CITYFEEDS_PORT:-8199} (open city feeds: air, heat, cyclones, rivers, quakes; strip)
 *
 * WebSockets: adapter-node cannot upgrade, so an upgrade request is answered
 * 501 IMMEDIATELY (the /ops audit ladder falls straight to its poll rung
 * instead of hanging on a handshake that never completes). In dev the vite
 * proxy intercepts these prefixes before SvelteKit sees them, so the proxy
 * and gate below are the prod path only.
 *
 * AUTHORITY PINNING (security contract): WHATWG URL parsing lets a
 * protocol-relative path (`//host/...`, or the backslash spelling `\/host/`
 * — special schemes treat `\` as `/`) OVERRIDE the base's authority, which
 * would turn this proxy into an open relay. The request path is therefore
 * untrusted input: after building the upstream URL we assert its origin is
 * still the rule's fixed loopback target and refuse with 400 otherwise
 * (regression: /api/convoy//127.0.0.1:8091/health once fetched the oracle
 * through the brain rule — live-confirmed, fixed 2026-10-19; covered by
 * tests/ops-guard.entry.ts).
 *
 * HEADERS: every response gets nosniff, a referrer policy (origin only
 * cross-site — OSM's tile policy needs the Referer), DENY framing and a
 * permissions policy (no geolocation: the citizen page promises it
 * collects no location; the microphone only for this origin and only on the
 * V3 console's documents — the (v3) group, where the voice field report
 * records, lib/v3/field — never on a public page). Pages also get a nonce-based CSP: self, Google
 * Fonts, OSM tiles and Cesium ion (+ its Bing imagery), frame-ancestors
 * 'none'. Public pages get no eval and no blob scripts at all; operator
 * pages allow what Cesium needs (knockout's eval, blob task workers),
 * Google's Map Tiles API (the ion-keyed photoreal 3D tiles stream only
 * into the operator canvas) and the Bing aerial tiles behind ion asset 2
 * over plain http: Cesium asks Bing for tile URLs in the PAGE's scheme and
 * the demo deck is served as http://127.0.0.1:5273 (a user decision), so
 * those tiles arrive as http://ecn.t{0-3}.tiles.virtualearth.net — refused,
 * they flooded the console and tipped the canvas into its offline-schematic
 * fallback while the 3D city rendered. A CSP is per document, and the
 * public shell links no operator route, so a citizen never client-navigates
 * into Cesium under the strict policy.
 * Relayed upstream bodies are already decoded by fetch, so
 * content-encoding / content-length are never
 * relayed with them.
 *
 * MACHINE INGEST (plan R26): `POST /api/v1/osint/signals` is the loopback
 * ingest path osint-ingress posts to the oracle DIRECTLY — never through the
 * deck. The deck proxies all of /api/v1, so a browser (signed in or not)
 * could otherwise post a fabricated "official" signal. Any write to that
 * path — checked on every decoding of the path (once-decoded canonical, %2F
 * spellings, any case, a trailing slash) — is answered 403 "machine ingest:
 * loopback only" BEFORE the gate and before any upstream fetch, gate on or
 * off. Every other /api/v1/osint/* read proxies as usual.
 *
 * AI SERVICES UNDER THE GATE ($lib/ai/gate.server.ts): with the gate on, every anonymous request to
 * /api/speech, /api/forecast, /api/vision, /api/hydro, /api/twin and /api/cityfeeds is default-denied (403) on its
 * canonical path, except the citizen page's needs: GET /api/hydro/hydro/nowcast | tide | rain and GET
 * /api/cityfeeds/feeds/summary | air (read-only, no forced refresh) and POST /api/speech/speech/speak (a JSON `text` of at most 400 characters, else 413; at most 10 per
 * client per minute, else 429). The public pages keep the strict CSP below. The road-state panel's nearby street photo
 * (GET /api/cityfeeds/feeds/street-image.jpg, Mapillary's JPEG fetched server-side by the city feeds) is not on that
 * list: signed-in officers only, and the page keeps loading images from its own origin (img-src is unchanged).
 *
 * OPERATOR GATE (opt-in, SAJAG_OPERATOR_PIN — see
 * $lib/shell/operator-session.server.ts): without the signed session
 * cookie POST /api/session issues, every proxied request is DEFAULT-DENIED
 * (403) on its canonical (once-decoded) path, except the public road
 * geometry, the liveness probes and the 108 driver's ambulance request
 * (capped per client: 429 beyond PUBLIC_DISPATCH_MAX). The deck's own
 * server-side reads (the public projection, /api/public/*) are
 * sub-requests and pass.
 *
 * ROUTES vs URLS (the V3 root flip, src/hooks.ts + $lib/shell/root-flip.ts): `/` is Home and `/analyst` the v2
 * workspace, by a `reroute` — so `event.route.id` is the RESOLVED node (`/(v3)/home`, `/(deck)`) while
 * `event.url.pathname` stays what the client asked for. Everything here that decides per page (the operator
 * CSP, the theme, the default language) reads the route id and never the URL, which is what keeps `/analyst`
 * on exactly the policy the old `/` had (tests/ops-guard.entry.ts holds it). The gate and the proxy rules
 * name /api paths only; no page URL is special to them.
 *
 * DOCUMENTS: every route sets its own <title>; a document that rendered
 * none (SvelteKit's built-in error page for an unknown path) gets the
 * brand title here, so no page ships untitled. <html lang> is the reader's
 * chosen language — the sajag_lang cookie (en | hi | mr, written by the
 * language switch, contract C-M) — else the route's default (/driver is
 * Marathi-first), so a choice survives the sign-in reload.
 */

import { randomBytes } from 'node:crypto';
import type { Handle, RequestEvent } from '@sveltejs/kit';
import {
	PUBLIC_DISPATCH_MAX,
	canonicalGatePath,
	gateDecision,
	gateEnabled,
	sessionFromCookieHeader,
	takePublicDispatch,
} from './lib/shell/operator-session.server';
import { langFromCookieHeader } from './lib/i18n/lang-cookie';
import { SPEAK_MAX_CHARS, SPEAK_MAX_PER_WINDOW, aiGateDecision, speakBodyOk, takeSpeak } from './lib/ai/gate.server';
import { clientAbort, proxyBudgetMs } from './lib/shell/proxy-limits';

interface ProxyRule {
	prefix: string;
	target: string;
	strip: boolean;
}

const ORACLE_TARGET = `http://127.0.0.1:${process.env.ORACLE_PORT ?? '8091'}`;
const BRAIN_TARGET = `http://127.0.0.1:${process.env.BRAIN_PORT ?? '8092'}`;
const EMULATOR_TARGET = `http://127.0.0.1:${process.env.EMULATOR_PORT ?? '8090'}`;
/** The on-prem AI services: each only computes and proposes; none writes city state. */
const AI_TARGET = (env: string, port: string): string => `http://127.0.0.1:${process.env[env] ?? port}`;

const PROXY_RULES: readonly ProxyRule[] = Object.freeze([
	{ prefix: '/api/v1', target: ORACLE_TARGET, strip: false },
	{ prefix: '/api/traffic', target: ORACLE_TARGET, strip: false },
	{ prefix: '/api/convoy', target: BRAIN_TARGET, strip: true },
	{ prefix: '/api/emulator', target: EMULATOR_TARGET, strip: true },
	{ prefix: '/api/speech', target: AI_TARGET('SPEECH_PORT', '8194'), strip: true },
	{ prefix: '/api/forecast', target: AI_TARGET('FORECAST_PORT', '8195'), strip: true },
	{ prefix: '/api/vision', target: AI_TARGET('VISION_PORT', '8196'), strip: true },
	{ prefix: '/api/hydro', target: AI_TARGET('HYDRO_PORT', '8197'), strip: true },
	{ prefix: '/api/twin', target: AI_TARGET('TWIN_PORT', '8198'), strip: true },
	{ prefix: '/api/cityfeeds', target: AI_TARGET('CITYFEEDS_PORT', '8199'), strip: true },
]);

/** Hop-by-hop headers that must not be forwarded verbatim (either way). */
const HOP_BY_HOP = new Set([
	'connection',
	'keep-alive',
	'transfer-encoding',
	'upgrade',
	'proxy-authenticate',
	'proxy-authorization',
	'proxy-connection',
	'te',
	'trailer',
]);

/** fetch() decodes upstream bodies, so these would describe the wrong bytes. */
const DECODED_BODY_HEADERS = new Set(['content-encoding', 'content-length']);

/** Upstream-only identity header: set from a verified session, never from the client. */
const OFFICER_HEADER = 'x-sajag-officer';

/** vite dev injects its own scripts/HMR socket; the CSP is a production contract. */
const DEV = process.env.NODE_ENV === 'development';

const CSP_SOURCES = {
	tiles: 'https://tile.openstreetmap.org https://*.tile.openstreetmap.org',
	// Cesium ion: api/assets/tile.cesium.com; ion asset 2 imagery is Bing.
	ion: 'https://*.cesium.com https://*.virtualearth.net',
	// Google Photorealistic 3D Tiles (ion asset 2275207) stream from Google's
	// Map Tiles API once ion hands out the session (photoreal-3d layer,
	// operator canvas only — public pages never load them)
	tiles3d: 'https://tile.googleapis.com',
	// ion asset 2's Bing tiles in the page's scheme: on the plain-http demo
	// origin Cesium requests http://ecn.t{0-3}.tiles.virtualearth.net (the ion
	// imagery factory gives no way to ask for https) — operator canvas only
	ionHttpImagery: 'http://*.virtualearth.net',
	fontsCss: 'https://fonts.googleapis.com',
	fontFiles: 'https://fonts.gstatic.com',
};

/**
 * The page CSP. `cesium` relaxes script-src for the operator routes only:
 * the Cesium build bundles knockout, which runs `(0,eval)("this")` while
 * loading ('unsafe-eval'), and Cesium's task workers are blob workers that
 * importScripts() blob URLs (workers inherit this policy, so 'blob:').
 * Without either the God's-eye canvas never starts or never loads a tile.
 * Public pages (no Cesium) keep the strict policy — and never admit the
 * photoreal 3D tile host or the plain-http Bing tiles, which only the
 * operator canvas streams from.
 */
function contentSecurityPolicy(nonce: string, cesium: boolean): string {
	const operatorTiles = cesium ? ` ${CSP_SOURCES.tiles3d} ${CSP_SOURCES.ionHttpImagery}` : '';
	return [
		"default-src 'self'",
		`script-src 'self' 'nonce-${nonce}' 'wasm-unsafe-eval'${cesium ? " 'unsafe-eval' blob:" : ''}`,
		`style-src 'self' 'unsafe-inline' ${CSP_SOURCES.fontsCss}`,
		`font-src 'self' data: ${CSP_SOURCES.fontFiles}`,
		`img-src 'self' data: blob: ${CSP_SOURCES.tiles} ${CSP_SOURCES.ion}${operatorTiles}`,
		`connect-src 'self' ${CSP_SOURCES.tiles} ${CSP_SOURCES.ion}${operatorTiles}`,
		// the Listen button and the voice field report play synthetic speech the page fetched (an in-memory blob URL);
		// without this the policy falls back to default-src and the browser refuses to play it
		"media-src 'self' blob:",
		"worker-src 'self' blob:",
		"child-src 'self' blob:",
		"object-src 'none'",
		"base-uri 'self'",
		"form-action 'self'",
		"frame-ancestors 'none'",
	].join('; ');
}

/** Security headers on every response this hook returns. */
function harden(response: Response, nonce: string | null, cesium = false, microphone = false): Response {
	let res = response;
	try {
		res.headers.set('x-content-type-options', 'nosniff');
	} catch {
		// Immutable headers (e.g. a Response.redirect from an endpoint): copy.
		res = new Response(response.body, response);
	}
	const h = res.headers;
	h.set('x-content-type-options', 'nosniff');
	h.set('referrer-policy', 'strict-origin-when-cross-origin');
	h.set('x-frame-options', 'DENY');
	h.set('permissions-policy', `geolocation=(), camera=(), microphone=(${microphone ? 'self' : ''}), payment=()`);
	if (nonce && !DEV && (h.get('content-type') ?? '').includes('text/html')) {
		h.set('content-security-policy', contentSecurityPolicy(nonce, cesium));
	}
	return res;
}

function jsonResponse(status: number, body: Record<string, unknown>): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
	});
}

function matchRule(pathname: string): ProxyRule | null {
	for (const rule of PROXY_RULES) {
		if (pathname === rule.prefix || pathname.startsWith(`${rule.prefix}/`)) return rule;
	}
	return null;
}

function isUpgrade(request: Request): boolean {
	return Boolean(request.headers.get('upgrade'));
}

/** The oracle's machine-ingest path (osint-ingress → oracle on loopback, never via the deck). */
const MACHINE_INGEST_PATH = '/api/v1/osint/signals';
const MACHINE_INGEST_DETAIL = 'machine ingest: loopback only';

/** Collapse repeated slashes, resolve '.' / '..' segments, drop a trailing slash, lower-case. */
function normaliseIngestPath(path: string): string {
	const out: string[] = [];
	for (const seg of path.replace(/\\/g, '/').split('/')) {
		if (seg === '' || seg === '.') continue;
		if (seg === '..') out.pop();
		else out.push(seg);
	}
	return `/${out.join('/')}`.toLowerCase();
}

/**
 * True for a write (anything but GET/HEAD/OPTIONS) to the machine-ingest path
 * in ANY spelling: the raw pathname, its canonical once-decoded form (what
 * uvicorn routes on) and up to three further decodings (so %252F, %2e%2e and
 * friends cannot slip past), each normalised. Refusing a spelling the oracle
 * would 404 costs nothing; letting one through would be a forged signal.
 */
function isMachineIngestWrite(method: string, pathname: string): boolean {
	const m = method.toUpperCase();
	if (m === 'GET' || m === 'HEAD' || m === 'OPTIONS') return false;
	const spellings = new Set<string>([pathname]);
	const canonical = canonicalGatePath(pathname);
	if (canonical) spellings.add(canonical);
	let decoded = pathname;
	for (let i = 0; i < 3; i++) {
		try {
			const next = decodeURIComponent(decoded);
			if (next === decoded) break;
			decoded = next;
			spellings.add(decoded);
		} catch {
			break;
		}
	}
	for (const p of spellings) if (normaliseIngestPath(p) === MACHINE_INGEST_PATH) return true;
	return false;
}

/**
 * Per-route document defaults: public pages render daylight; the language
 * is the reader's sajag_lang choice — read by the same pure parser the
 * browser uses (lib/i18n/lang-cookie langFromCookieHeader: only en | hi |
 * mr count, a malformed escape is no choice, never a 500) — else the
 * route's (/driver is Marathi-first); only operator routes (which embed
 * Cesium) relax eval. Operator routes are the whole console: the (deck) group
 * AND the (v3) group (Home, Decide, Map, Plan, Assistant, object pages) — a CSP is
 * per DOCUMENT and a client-side navigation from Home to the map or to Analyst
 * keeps the document it started in, so Home must already carry the policy the
 * canvas needs (the public pages stay strict; user decision 2026-10-26).
 *
 * The landing page (/welcome, route group (landing), V3-LANDING) is public as
 * well: the STRICT policy (never the operator one — its links into the console
 * reload, so it never client-navigates into Cesium) and the NIGHT theme, the
 * console's own ground, rendered by the server so it never flashes daylight.
 */
function documentDefaults(event: RequestEvent): { theme: string; lang: string; operator: boolean } {
	const id = event.route.id ?? '';
	return {
		// (landing) falls to 'command' with the console: the night ground
		theme: id.startsWith('/(public)') ? 'daylight' : 'command',
		lang: langFromCookieHeader(event.request.headers.get('cookie')) ?? 'en',
		// only the two operator groups; (public) and (landing) keep the strict policy
		operator: id.startsWith('/(deck)') || id.startsWith('/(v3)'),
	};
}

/** The client address for per-client caps ('unknown' off adapter-node). */
function clientKey(event: RequestEvent): string {
	try {
		return event.getClientAddress();
	} catch {
		return 'unknown';
	}
}

/** Fallback for a document that rendered no <title> (the built-in error page). */
function ensureTitle(html: string): string {
	const headEnd = html.indexOf('</head>');
	if (headEnd < 0 || /<title[\s>]/i.test(html.slice(0, headEnd))) return html;
	return `${html.slice(0, headEnd)}<title>Sajag</title>${html.slice(headEnd)}`;
}

/** Anonymous dispatch requests are the 108 flow only: agency 'ambulance'. */
async function isAmbulanceRequest(request: Request): Promise<boolean> {
	try {
		const body = (await request.clone().json()) as { agency?: unknown } | null;
		return body?.agency === 'ambulance';
	} catch {
		return false;
	}
}

async function proxy(event: RequestEvent, rule: ProxyRule, officer: string | null): Promise<Response> {
	const suffix = rule.strip ? event.url.pathname.slice(rule.prefix.length) : event.url.pathname;
	const base = new URL(rule.target);
	const upstream = new URL(`${suffix}${event.url.search}`, base);
	// The request path is untrusted input: a protocol-relative suffix
	// (`//host/...`) overrides the base authority under WHATWG URL parsing.
	// Whatever parsing did with it, the upstream origin must still be the
	// rule's fixed loopback target — refuse anything that escaped it.
	if (upstream.origin !== base.origin) {
		return jsonResponse(400, { detail: 'deck proxy: refused authority-override path' });
	}

	const headers = new Headers(event.request.headers);
	headers.delete('host'); // fetch sets the upstream host
	headers.delete('cookie'); // deck sessions never travel upstream
	headers.delete(OFFICER_HEADER); // only a verified session may assert an officer
	for (const name of HOP_BY_HOP) headers.delete(name);
	// Percent-encoded: officer names may be Devanagari/Marathi (header
	// values must be ByteStrings). Advisory for upstream audit trails.
	if (officer) headers.set(OFFICER_HEADER, encodeURIComponent(officer));

	const method = event.request.method.toUpperCase();
	const budgetMs = proxyBudgetMs(rule.prefix, event.url.pathname);
	// F-CONN-04: the upstream request ends when the CLIENT gives up too (a
	// closed tab, an aborted fetch, a superseded poll) — never left running
	// to its budget on the oracle or the brain.
	const client = clientAbort(event);
	const init: RequestInit & { duplex?: 'half' } = {
		method: event.request.method,
		headers,
		redirect: 'manual',
		signal: AbortSignal.any([AbortSignal.timeout(budgetMs), client.signal]),
	};
	if (method !== 'GET' && method !== 'HEAD') {
		init.body = event.request.body;
		init.duplex = 'half';
	}

	try {
		const res = await fetch(upstream, init);
		const outHeaders = new Headers();
		res.headers.forEach((value, key) => {
			const k = key.toLowerCase();
			if (!HOP_BY_HOP.has(k) && !DECODED_BODY_HEADERS.has(k)) outHeaders.set(key, value);
		});
		// the client watch lasts as long as the body streams (an NDJSON chat stream included)
		const body = res.body ? res.body.pipeThrough(new TransformStream({ flush: () => client.release() })) : (client.release(), null);
		return new Response(body, {
			status: res.status,
			statusText: res.statusText,
			headers: outHeaders,
		});
	} catch (err) {
		client.release();
		return jsonResponse(502, {
			detail: `deck proxy: upstream ${rule.target} unreachable (${
				err instanceof Error ? err.message : String(err)
			})`,
		});
	}
}

export const handle: Handle = async ({ event, resolve }) => {
	// adapter-node cannot complete a WebSocket handshake: say so at once.
	if (isUpgrade(event.request)) {
		return harden(
			jsonResponse(501, {
				detail: 'deck proxy: WebSocket upgrade is not supported on this origin — use the polling rung',
			}),
			null,
		);
	}

	// R26: the machine-ingest path is loopback-only — refused for every caller,
	// gate on or off, signed in or not, before the gate and any upstream fetch.
	if (isMachineIngestWrite(event.request.method, event.url.pathname)) {
		return harden(jsonResponse(403, { detail: MACHINE_INGEST_DETAIL }), null);
	}

	const rule = matchRule(event.url.pathname);
	if (rule) {
		const gated = gateEnabled();
		const session = gated ? sessionFromCookieHeader(event.request.headers.get('cookie')) : null;
		if (gated && !session && !event.isSubRequest) {
			// the AI services: default-deny too; only the citizen page's public reads and its speak request pass
			const ai = aiGateDecision(event.request.method, event.url.pathname, event.url.search);
			if (ai === 'check-speak') {
				if (!(await speakBodyOk(event.request))) {
					return harden(jsonResponse(413, { detail: `speak: a JSON body with text of at most ${SPEAK_MAX_CHARS} characters` }), null);
				}
				if (!takeSpeak(clientKey(event))) {
					return harden(jsonResponse(429, { detail: `too many read-aloud requests from this device (max ${SPEAK_MAX_PER_WINDOW} per minute)` }), null);
				}
			} else if (ai === 'deny') {
				return harden(
					jsonResponse(403, {
						detail: 'operator session required — sign in as the duty officer (POST /api/session)',
						gate: 'SAJAG_OPERATOR_PIN',
					}),
					null,
				);
			}
			let verdict = ai === 'not-ai' ? gateDecision(event.request.method, event.url.pathname) : 'allow';
			if (verdict === 'check-body') {
				verdict = (await isAmbulanceRequest(event.request)) ? 'allow' : 'deny';
				if (verdict === 'allow' && !takePublicDispatch(clientKey(event))) {
					return harden(
						jsonResponse(429, {
							detail: `too many ambulance requests from this device (max ${PUBLIC_DISPATCH_MAX} per 10 minutes) — call 108 control`,
						}),
						null,
					);
				}
			}
			if (verdict === 'deny') {
				return harden(
					jsonResponse(403, {
						detail: 'operator session required — sign in as the duty officer (POST /api/session)',
						gate: 'SAJAG_OPERATOR_PIN',
					}),
					null,
				);
			}
		}
		return harden(await proxy(event, rule, session?.officer ?? null), null);
	}

	const nonce = randomBytes(16).toString('base64');
	const { theme, lang, operator } = documentDefaults(event);
	const response = await resolve(event, {
		transformPageChunk: ({ html }) =>
			ensureTitle(
				html
					.replace('%sajag.theme%', theme)
					.replace('%sajag.lang%', lang)
					// Every inline/bootstrap script SvelteKit renders carries the
					// per-response nonce the CSP allows (no 'unsafe-inline').
					.replace(/<script(?=[\s>])(?![^>]*\snonce=)/g, `<script nonce="${nonce}"`),
			),
	});
	// the V3 console's documents may record for the voice field report (the (v3) shell's "Report by voice"); no other page
	return harden(response, nonce, operator, (event.route.id ?? '').startsWith('/(v3)'));
};
