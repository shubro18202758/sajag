/**
 * AI-route gate self-test — bundled with the vendored esbuild and run by node (tests/test_deck_proxy_guard.py
 * test_ai_gate_bundle_behaviour runs exactly this). Hermetic: fetch is stubbed, nothing leaves the process.
 *
 *   node_modules/.bin/esbuild tests/ai-gate.entry.ts --bundle --platform=node --format=esm \
 *     --alias:\$lib=./src/lib --outfile=tests/artifacts/ai-gate-bundle.mjs && node tests/artifacts/ai-gate-bundle.mjs
 *
 * With SAJAG_OPERATOR_PIN set and no session, src/hooks.server.ts default-denies the on-prem AI services
 * (/api/speech, /api/forecast, /api/vision, /api/hydro, /api/twin, /api/cityfeeds) on the canonical path, except the citizen page's
 * two needs: GET /api/hydro/hydro/nowcast | tide | rain (no forced refresh) and POST /api/speech/speech/speak (JSON
 * text ≤ 400 characters → else 413; ≤ 10 per client per minute → else 429). Signed in, gate off and server-side
 * sub-requests pass. The public page keeps its strict CSP.
 */
import { handle } from '../src/hooks.server';
import { issueToken, SESSION_COOKIE } from '../src/lib/shell/operator-session.server';
import { aiGateDecision, resetSpeak, SPEAK_MAX_PER_WINDOW } from '../src/lib/ai/gate.server';

let failures = 0;
const fetched: string[] = [];
globalThis.fetch = (async (input: RequestInfo | URL) => {
	fetched.push(String(input instanceof URL ? input.href : input));
	return new Response('{"ok":true}', { status: 200, headers: { 'content-type': 'application/json' } });
}) as typeof fetch;

function check(name: string, cond: boolean, detail = ''): void {
	if (cond) console.log(`ok ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
		failures++;
	}
}

async function run(rawPath: string, method = 'GET', opts: { body?: string; cookie?: string; client?: string; sub?: boolean } = {}): Promise<Response> {
	fetched.length = 0;
	const url = new URL(rawPath, 'http://deck.internal');
	const headers: Record<string, string> = { 'content-type': 'application/json' };
	if (opts.cookie) headers.cookie = opts.cookie;
	const init: RequestInit = { method, headers };
	if (method !== 'GET' && method !== 'HEAD') init.body = opts.body ?? '{}';
	const event = {
		url,
		request: new Request(url, init),
		route: { id: null },
		isSubRequest: opts.sub === true,
		getClientAddress: () => opts.client ?? '10.0.0.40',
		resolve: async () => {
			throw new Error('resolve must not run for proxied paths');
		},
	};
	// biome-ignore lint/suspicious/noExplicitAny: a test double for the SvelteKit event
	return handle({ event: event as any, resolve: event.resolve as any });
}

const HYDRO = `http://127.0.0.1:${process.env.HYDRO_PORT ?? '8197'}`;
const SPEECH = `http://127.0.0.1:${process.env.SPEECH_PORT ?? '8194'}`;

// gate OFF: every AI route proxies as before
delete process.env.SAJAG_OPERATOR_PIN;
{
	const r = await run('/api/forecast/forecast/segments?horizon_min=120');
	check('ai gate off: the forecast proxies', r.status === 200 && fetched.length === 1);
	const t = await run('/api/twin/twin/propose', 'POST', { body: '{}' });
	check('ai gate off: the twin proposes (compute only) as before', t.status === 200 && fetched.length === 1);
}

process.env.SAJAG_OPERATOR_PIN = '1234';
process.env.SAJAG_SESSION_SECRET = 'ai-gate-secret';

const DENY: Array<[string, string, string?]> = [
	['GET', '/api/forecast/forecast/segments?horizon_min=120'],
	['GET', '/api/forecast/forecast/metrics'],
	['GET', '/api/forecast/health'],
	['POST', '/api/twin/twin/propose', '{}'],
	['POST', '/api/twin/twin/simulate', '{}'],
	['GET', '/api/twin/twin/baselines/17'],
	['POST', '/api/hydro/hydro/replay?event=2025-08-19'],
	['GET', '/api/hydro/hydro/pumps'],
	['GET', '/api/hydro/hydro/nowcast?force=true'],
	['GET', '/api/hydro/hydro/rain?force=1'],
	['POST', '/api/hydro/hydro/nowcast', '{}'],
	['POST', '/api/speech/speech/transcribe', '{}'],
	['POST', '/api/speech/speech/report', '{}'],
	['GET', '/api/speech/speech/speak'],
	['POST', '/api/vision/vision/road-state', '{}'],
	['GET', '/api/hydro/nowcast'],
	['GET', '/api/forecast/%66orecast/segments'],
	['GET', '/api/hydro/hydro%2Fpumps'],
	['GET', '/api/hydro/hydro/%2576owcast'],
	['GET', '/api/hydro//hydro/pumps'],
	// city feeds: only the citizen page's two reads are public
	['GET', '/api/cityfeeds/feeds/cyclones'],
	['GET', '/api/cityfeeds/feeds/river'],
	['GET', '/api/cityfeeds/feeds/proposals'],
	['GET', '/api/cityfeeds/health'],
	// the road-state panel's nearby street photo (Mapillary through the city feeds): officers only
	['GET', '/api/cityfeeds/feeds/street-image?lat=22.564600&lon=88.351000'],
	['GET', '/api/cityfeeds/feeds/street-image.jpg?lat=22.564600&lon=88.351000'],
	['HEAD', '/api/cityfeeds/feeds/street-image.jpg?lat=22.564600&lon=88.351000'],
	['GET', '/api/cityfeeds/feeds/street-image%2Ejpg?lat=22.5646&lon=88.351'],
	['GET', '/api/cityfeeds/feeds/air?force=1'],
	['GET', '/api/cityfeeds/feeds/summary?force=true'],
	['POST', '/api/cityfeeds/feeds/air', '{}'],
	['GET', '/api/cityfeeds/feeds%2Fheat'],
];
for (const [method, path, body] of DENY) {
	const r = await run(path, method, { body });
	check(`ai gate on, anonymous ${method} ${path} → 403`, r.status === 403 && fetched.length === 0, `status ${r.status}`);
}

const ALLOW: Array<[string, string]> = [
	['GET', '/api/hydro/hydro/nowcast'],
	['GET', '/api/hydro/hydro/tide?hours=24'],
	['GET', '/api/hydro/hydro/rain'],
	['HEAD', '/api/hydro/hydro/tide'],
	['GET', '/api/hydro/hydro/%6Eowcast'],
];
for (const [method, path] of ALLOW) {
	const r = await run(path, method);
	check(`ai gate on, anonymous ${method} ${path} passes (public read)`, r.status === 200 && fetched.length === 1 && fetched[0].startsWith(`${HYDRO}/hydro/`), `status ${r.status} ${fetched[0] ?? ''}`);
}

const CITYFEEDS = `http://127.0.0.1:${process.env.CITYFEEDS_PORT ?? '8199'}`;
for (const [method, path] of [['GET', '/api/cityfeeds/feeds/summary'], ['GET', '/api/cityfeeds/feeds/air'], ['HEAD', '/api/cityfeeds/feeds/air']] as const) {
	const r = await run(path, method);
	check(`ai gate on, anonymous ${method} ${path} passes (citizen air today)`, r.status === 200 && fetched.length === 1 && fetched[0].startsWith(`${CITYFEEDS}/feeds/`), `status ${r.status} ${fetched[0] ?? ''}`);
}

resetSpeak();
{
	const ok = await run('/api/speech/speech/speak', 'POST', { body: JSON.stringify({ text: 'জমা জলে বিদ্যুতের খুঁটি ছোঁবেন না।', lang: 'mr' }), client: '10.0.0.50' });
	check('ai gate on: anonymous speak with a short advisory passes', ok.status === 200 && fetched.length === 1 && fetched[0] === `${SPEECH}/speech/speak`, `status ${ok.status}`);
	const long = await run('/api/speech/speech/speak', 'POST', { body: JSON.stringify({ text: 'ক'.repeat(401) }), client: '10.0.0.50' });
	check('ai gate on: speak with more than 400 characters → 413, never fetched', long.status === 413 && fetched.length === 0, `status ${long.status}`);
	const notJson = await run('/api/speech/speech/speak', 'POST', { body: 'text=hello', client: '10.0.0.50' });
	check('ai gate on: speak without a JSON text → 413', notJson.status === 413 && fetched.length === 0);
	const empty = await run('/api/speech/speech/speak', 'POST', { body: '{"text":"   "}', client: '10.0.0.50' });
	check('ai gate on: speak with an empty text → 413', empty.status === 413 && fetched.length === 0);
	resetSpeak();
	const statuses: number[] = [];
	for (let i = 0; i <= SPEAK_MAX_PER_WINDOW; i++) statuses.push((await run('/api/speech/speech/speak', 'POST', { body: '{"text":"Avoid Gariahat crossing."}', client: '10.0.0.60' })).status);
	check(`ai gate on: anonymous speak capped per client (${SPEAK_MAX_PER_WINDOW} a minute, then 429)`, statuses.slice(0, -1).every((st) => st === 200) && statuses[statuses.length - 1] === 429 && fetched.length === 0, statuses.join(','));
	const other = await run('/api/speech/speech/speak', 'POST', { body: '{"text":"Avoid Gariahat crossing."}', client: '10.0.0.61' });
	check('ai gate on: the speak cap is per client', other.status === 200);
	resetSpeak();
}

{
	const { token } = issueToken('S. Haldar');
	const cookie = `${SESSION_COOKIE}=${encodeURIComponent(token)}`;
	let all = true;
	for (const [method, path, body] of DENY.filter(([, p]) => !p.includes('%') && !p.includes('//'))) {
		const r = await run(path, method, { body, cookie });
		if (r.status !== 200) all = false;
	}
	check('ai gate on, signed in: every AI route proxies', all);
	// the street photo: the query reaches the city feeds as sent, and the JPEG comes back byte for byte with its type
	const JPEG = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 16, 74, 70, 73, 70, 0, 1, 0xff, 0xd9]);
	const stub = globalThis.fetch;
	globalThis.fetch = (async (input: RequestInfo | URL) => {
		fetched.push(String(input instanceof URL ? input.href : input));
		return new Response(JPEG, { status: 200, headers: { 'content-type': 'image/jpeg', 'cache-control': 'no-store' } });
	}) as typeof fetch;
	try {
		const q = '?lat=22.564600&lon=88.351000';
		const photo = await run(`/api/cityfeeds/feeds/street-image.jpg${q}`, 'GET', { cookie });
		const bytes = new Uint8Array(await photo.arrayBuffer());
		check(
			'ai gate on, signed in: the street photo proxies to the city feeds and its JPEG comes back intact',
			photo.status === 200 && fetched.length === 1 && fetched[0] === `${CITYFEEDS}/feeds/street-image.jpg${q}` && photo.headers.get('content-type') === 'image/jpeg' && photo.headers.get('x-content-type-options') === 'nosniff' && bytes.length === JPEG.length && bytes.every((b, i) => b === JPEG[i]),
			`status ${photo.status} ${fetched[0] ?? ''}`,
		);
	} finally {
		globalThis.fetch = stub;
	}
	const sub = await run('/api/forecast/forecast/segments', 'GET', { sub: true });
	check('ai gate on: a server-side sub-request passes', sub.status === 200 && fetched.length === 1);
}

check(
	'ai gate decision: the platform prefixes are not the AI gate’s (they keep their own gate)',
	aiGateDecision('GET', '/api/v1/vehicles') === 'not-ai' && aiGateDecision('POST', '/api/convoy/chat/stream') === 'not-ai' && aiGateDecision('GET', '/api/hydro/hydro/nowcast') === 'allow' && aiGateDecision('POST', '/api/speech/speech/speak') === 'check-speak',
);

delete process.env.SAJAG_OPERATOR_PIN;
if (failures) {
	console.error(`\nFAIL ai-gate — ${failures} assertion(s) failed`);
	process.exit(1);
}
console.log('all ai gate assertions passed');
