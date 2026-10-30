/**
 * Field AI smoke — LIVE: a dev deck of this tree wired to the real on-premises services (speech, vision, hydro,
 * forecast) and a sandbox backend. It drives the same client code an officer and a citizen use, end to end:
 *
 *   node tests/ai-field-smoke.mjs [deckUrl] [--shots <dir>] [--wav <file>]      (default http://127.0.0.1:5481)
 *
 *   1. VOICE    a Marathi report spoken by the service's own TTS (POST /speech/speak) is the microphone: Chrome's fake
 *               capture device plays the clip while the smoke HOLDS the button (MediaRecorder → webm/opus → POST
 *               /speech/report). Where the page may not use the microphone (the hooks patch not applied: the
 *               Permissions-Policy says microphone=()), the same clip goes through the sheet's own client path
 *               (window.__FIELD_REPORT__.submitAudio). Asserts a structured report labelled UNVERIFIED-FIELD with a
 *               Marathi transcript, the kind and the place; then "Send to the board" fires exactly ONE
 *               POST /api/v1/events — ANSWERED HERE, never written to the shared sandbox — whose body is unverified
 *               (metadata.source field-voice, no verification_state) and carries the named officer.
 *   2. TYPED    a typed Marathi report takes the same path.
 *   3. CAMERA   /o/camera:EM-J12 reads the credited waterlogged sample still ("Sample still · not live") through the
 *               vision model: a road state from the list, UNVERIFIED-CAMERA, never a person; its board POST is answered
 *               here too.
 *   4. SEGMENT  /o/segment:1052: the forecast panel (SIMULATED, a p10–p90 band) and the waterlogging panel (MODELLED,
 *               four drivers, pumps EMULATED) are ready.
 *   5. PUBLIC   /citizen and /driver in मराठी: the waterlogging card is ready (MODELLED), "শুনুন" plays a synthetic
 *               voice (POST /speech/speak → audio/wav, X-Speech-Label synthetic-voice); the public pages make no other
 *               write and never touch /api/v1/events.
 *
 * Zero page errors throughout. Exits 0 with `ok <name>` lines, 1 on any failure, 2 when the deck is not reachable.
 */
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const argv = process.argv.slice(2);
const opt = (name) => {
	const i = argv.indexOf(name);
	return i >= 0 ? argv[i + 1] : null;
};
const ORIGIN = argv.find((a, i) => !a.startsWith('--') && !['--shots', '--wav'].includes(argv[i - 1])) ?? 'http://127.0.0.1:5481';
const SHOTS = opt('--shots');
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const MR = /[ঀ-৿]/;

try {
	const r = await fetch(ORIGIN, { signal: AbortSignal.timeout(8000) });
	if (!r.ok && r.status >= 500) throw new Error(String(r.status));
} catch (e) {
	console.error(`ai-field-smoke: no deck at ${ORIGIN} (${e?.message ?? e}) — start a dev deck with SPEECH_PORT, VISION_PORT, HYDRO_PORT and FORECAST_PORT`);
	process.exit(2);
}

// ── the clip: the service's own synthetic Marathi voice, re-sampled to 48 kHz for Chrome's fake capture ──
let wav = opt('--wav');
if (!wav) {
	const tmp = mkdtempSync(path.join(os.tmpdir(), 'ai-field-'));
	const res = await fetch(`${ORIGIN}/api/speech/speech/speak`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({ text: 'গড়িয়াহাট মোড়ে হাঁটু জল জমেছে, একটা বাস আটকে আছে।', lang: 'mr' }),
		signal: AbortSignal.timeout(180000),
	});
	ok('voice: the clip is synthesised by the speech service (synthetic voice)', res.ok && res.headers.get('x-speech-label') === 'synthetic-voice', `${res.status} ${res.headers.get('x-speech-seconds')} s`);
	const raw = path.join(tmp, 'clip.wav');
	writeFileSync(raw, Buffer.from(await res.arrayBuffer()));
	wav = path.join(tmp, 'clip48.wav');
	const ff = spawnSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-i', raw, '-ar', '48000', '-ac', '1', '-sample_fmt', 's16', wav]);
	if (ff.status !== 0) wav = raw;
}

const require = createRequire(process.env.PUPPETEER_FROM ?? new URL('../../../frontend/package.json', import.meta.url));
const puppeteer = require('puppeteer');
const CHROME = [`${process.env.HOME}/.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome`].find((p) => existsSync(p));
const browser = await puppeteer.launch({
	executablePath: CHROME,
	headless: 'new',
	args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-audio-capture=${wav}%noloop`],
});
const errors = [];
const boardPosts = [];
const publicWrites = [];

async function page(w, h, lang, { answerBoard = false, publicPage = false } = {}) {
	const p = await browser.newPage();
	await p.setViewport({ width: w, height: h });
	p.on('pageerror', (e) => errors.push(`pageerror: ${e.message.slice(0, 200)}`));
	await p.setCookie({ name: 'sajag_lang', value: lang, url: ORIGIN });
	await p.setRequestInterception(true);
	p.on('request', (req) => {
		const u = new URL(req.url());
		const write = !['GET', 'HEAD', 'OPTIONS'].includes(req.method());
		if (publicPage && write && u.origin === new URL(ORIGIN).origin) publicWrites.push(`${req.method()} ${u.pathname}`);
		if (u.pathname === '/api/v1/events' && req.method() === 'POST') {
			if (answerBoard) {
				boardPosts.push(JSON.parse(req.postData() || '{}'));
				return req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ event_id: '6f2b8a43-1c55-4c3e-9b1a-0d2e7f4a9c10', status: 'planning' }) });
			}
			return req.abort();
		}
		return req.continue();
	});
	return p;
}

async function nameOfficer(p, name) {
	await p.click('[data-testid="v3-officer"]');
	await p.waitForSelector('.officer-input', { timeout: 10000 });
	await p.type('.officer-input', name);
	await p.keyboard.press('Enter').catch(() => {});
	await sleep(300);
	await p.keyboard.press('Escape').catch(() => {});
	await sleep(300);
}

const shot = async (p, name) => {
	if (SHOTS) await p.screenshot({ path: path.join(SHOTS, `${name}.png`) });
};
const report = (p) => p.evaluate(() => window.__FIELD_REPORT__?.report ?? null);
const waitReport = (p) =>
	p.waitForFunction(() => window.__FIELD_REPORT__?.phase === 'result' || (window.__FIELD_REPORT__?.phase === 'idle' && document.querySelector('[data-testid="field-sheet"] .problem')), { timeout: 180000 });

try {
	// ── 1. voice ──────────────────────────────────────────────────────────
	{
		const p = await page(1440, 1000, 'en', { answerBoard: true });
		const res = await p.goto(`${ORIGIN}/o/segment:1052`, { waitUntil: 'networkidle2', timeout: 120000 });
		const mic = /microphone=\(self\)/.test(res?.headers()['permissions-policy'] ?? '');
		await sleep(1500);
		await nameOfficer(p, 'Insp. R. Sen');
		await p.click('[data-testid="field-report-open"]');
		await p.waitForSelector('[data-testid="field-sheet"][open]', { timeout: 20000 });
		ok('voice: ONE top-bar entry opens the sheet (lazy), with the privacy line', (await p.$$('[data-testid="field-report-open"]')).length === 1 && /Audio is not stored/.test(await p.$eval('[data-testid="field-sheet"]', (e) => e.textContent)));
		if (mic) {
			const box = await (await p.$('[data-testid="field-hold"]')).boundingBox();
			await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
			await p.mouse.down();
			await sleep(2500);
			ok('voice: holding records (the button is pressed, the clock runs)', (await p.evaluate(() => window.__FIELD_REPORT__?.phase)) === 'recording');
			await shot(p, 'voice_recording');
			await sleep(3600);
			await p.mouse.up();
		} else {
			console.log('note voice: this page may not use the microphone (hooks patch not applied) — the clip goes through the sheet’s own client path');
			await p.evaluate(async (b64) => {
				const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
				await window.__FIELD_REPORT__.submitAudio(new Blob([bytes], { type: 'audio/wav' }));
			}, (await import('node:fs')).readFileSync(wav).toString('base64'));
		}
		await waitReport(p);
		await sleep(1200);
		const r = await report(p);
		ok(`voice: a structured report from ${mic ? 'the microphone (MediaRecorder)' : 'the clip'}, labelled UNVERIFIED-FIELD`, r?.verification === 'UNVERIFIED-FIELD' && MR.test(r.transcript ?? ''), JSON.stringify(r));
		ok('voice: the kind is waterlogging (the words that decided it are shown)', r?.kind === 'waterlogging' && (await p.$$('[data-testid="field-result"] mark')).length > 0, r?.kind);
		ok('voice: the place is on the mini map (gariahat) or offered as candidates', r?.place === 'gariahat' || (await p.$$('.cand')).length > 0, r?.place ?? 'candidates');
		ok('voice: the result wears the unverified tag', !!(await p.$('[data-testid="field-result"] [data-label="UNVERIFIED-FIELD"]')));
		await shot(p, 'voice_result');
		if (r?.place) {
			await p.click('[data-testid="field-send"]');
			await p.waitForSelector('[data-testid="field-sent"]', { timeout: 30000 }).catch(() => undefined);
			const b = boardPosts.at(-1);
			ok('voice: Send to the board fires ONE POST /api/v1/events (answered here, never written to the sandbox)', boardPosts.length === 1 && !!(await p.$('[data-testid="field-sent"]')));
			ok('voice: the board entry is unverified and named — metadata.source field-voice, no verification_state, the officer', b?.metadata?.source === 'field-voice' && b.metadata.verification === 'UNVERIFIED-FIELD' && !('verification_state' in b) && b.officer === 'Insp. R. Sen' && /^Unverified field report/.test(b.title));
			await shot(p, 'voice_sent');
		}
		// ── 2. typed ──────────────────────────────────────────────────────
		await p.evaluate(() => document.querySelector('[data-testid="field-sheet"] .ghost')?.click());
		await sleep(300);
		await p.type('[data-testid="field-text"]', 'উল্টোডাঙা আন্ডারপাসে কোমর জল, অ্যাম্বুলেন্স আটকে আছে');
		await p.click('[data-testid="field-text-go"]');
		await waitReport(p);
		const t = await report(p);
		ok('typed: a typed Marathi report takes the same path (UNVERIFIED-FIELD, kind and place read)', t?.verification === 'UNVERIFIED-FIELD' && t.kind === 'waterlogging' && !!t.place, JSON.stringify(t));
		await shot(p, 'voice_typed');
		await p.close();
	}

	// ── 3. camera ─────────────────────────────────────────────────────────
	{
		const p = await page(1440, 1200, 'en', { answerBoard: true });
		await p.goto(`${ORIGIN}/o/camera:EM-J12`, { waitUntil: 'networkidle2', timeout: 120000 });
		await p.waitForSelector('[data-testid="obj-road-state"]', { timeout: 60000 });
		await p.click('.strip button[title^="Mumbai, August 2017"]');
		await sleep(400);
		ok('camera: the still is labelled "Sample still · not live" with its credit', /Sample still · not live/.test(await p.$eval('[data-testid="obj-road-state"]', (e) => e.textContent)) && /Sumita Roy Dutta/.test(await p.$eval('[data-testid="obj-road-state"] figcaption', (e) => e.textContent)));
		await nameOfficer(p, 'Insp. R. Sen');
		await p.click('[data-testid="rs-read"]');
		await p.waitForFunction(() => document.querySelector('[data-testid="obj-road-state"]')?.getAttribute('data-phase') !== 'reading', { timeout: 240000 });
		await sleep(800);
		const st = await p.$eval('[data-testid="obj-road-state"]', (e) => e.getAttribute('data-state'));
		const txt = await p.$eval('[data-testid="obj-road-state"]', (e) => e.innerText);
		ok('camera: a road state from the list, UNVERIFIED-CAMERA', ['waterlogged', 'blocked', 'tree_fall', 'stalled_vehicle', 'crash_debris', 'congested', 'clear', 'unknown'].includes(st) && !!(await p.$('[data-label="UNVERIFIED-CAMERA"]')), st);
		ok('camera: the waterlogged still reads waterlogged, with a depth band', st === 'waterlogged' && /wheel|kerb/i.test(txt), st);
		ok('camera: no person words in the answer', !/\b(man|men|woman|women|person|people|pedestrian|boy|girl)\b/i.test(txt.replace(/never describes people/i, '')));
		await shot(p, 'camera_result');
		const before = boardPosts.length;
		if (await p.$('[data-testid="rs-send"]')) {
			await p.click('[data-testid="rs-send"]');
			await p.waitForSelector('[data-testid="rs-sent"]', { timeout: 30000 }).catch(() => undefined);
			const b = boardPosts.at(-1);
			ok('camera: Send fires ONE board POST (answered here), labelled camera-ai / UNVERIFIED-CAMERA', boardPosts.length === before + 1 && b?.metadata?.source === 'camera-ai' && b.metadata.verification === 'UNVERIFIED-CAMERA' && !('verification_state' in b));
		}
		await p.close();
	}

	// ── 4. segment ────────────────────────────────────────────────────────
	{
		const p = await page(1440, 1500, 'en');
		await p.goto(`${ORIGIN}/o/segment:1052`, { waitUntil: 'networkidle2', timeout: 120000 });
		await p.waitForFunction(() => ['obj-forecast', 'obj-water'].every((id) => !['loading', null].includes(document.querySelector(`[data-testid="${id}"]`)?.getAttribute('data-state') ?? null)), { timeout: 120000 });
		const fc = await p.$eval('[data-testid="obj-forecast"]', (e) => ({ state: e.getAttribute('data-state'), label: e.getAttribute('data-label'), band: !!e.querySelector('path.band'), sim: !!e.querySelector('[data-label="SIMULATED"]') }));
		ok('segment: the forecast is ready with its p10–p90 band and the SIMULATED tag', fc.state === 'ready' && fc.band && (fc.label !== 'SIMULATED' || fc.sim), JSON.stringify(fc));
		const wl = await p.$eval('[data-testid="obj-water"]', (e) => ({ state: e.getAttribute('data-state'), risk: e.getAttribute('data-risk'), modelled: !!e.querySelector('[data-label="MODELLED"]'), drivers: e.querySelectorAll('.drivers li').length, text: e.innerText }));
		ok('segment: the waterlogging panel is ready, MODELLED, four drivers, pumps Emulated', wl.state === 'ready' && wl.modelled && wl.drivers === 4 && /Emulated/.test(wl.text), JSON.stringify({ ...wl, text: undefined }));
		await shot(p, 'segment');
		await p.close();
	}

	// ── 5. public ─────────────────────────────────────────────────────────
	{
		for (const path_ of ['citizen', 'driver']) {
			const p = await page(390, 844, 'mr', { publicPage: true });
			await p.goto(`${ORIGIN}/${path_}`, { waitUntil: 'networkidle2', timeout: 120000 });
			await p.waitForFunction(() => document.querySelector('[data-testid="water-card"]')?.getAttribute('data-status') === 'ready', { timeout: 60000 }).catch(() => undefined);
			const card = await p.$eval('[data-testid="water-card"]', (e) => ({ status: e.getAttribute('data-status'), text: e.innerText, modelled: !!e.querySelector('[data-label="MODELLED"]') })).catch(() => null);
			ok(`public /${path_}: the waterlogging card is ready in Marathi, MODELLED`, card?.status === 'ready' && MR.test(card.text) && card.modelled, card?.status);
			if (path_ === 'citizen') {
				await (await p.$('[data-testid="water-card"]')).scrollIntoView();
				const speak = p.waitForResponse((r) => r.url().includes('/api/speech/speech/speak'), { timeout: 180000 });
				await p.click('[data-testid="water-card"] [data-testid="listen"] button');
				const r = await speak;
				ok('public: শুনুন plays a synthetic voice (audio/wav, X-Speech-Label synthetic-voice)', r.status() === 200 && /audio\/wav/.test(r.headers()['content-type'] ?? '') && r.headers()['x-speech-label'] === 'synthetic-voice', `${r.status()}`);
				await p.waitForFunction(() => document.querySelector('[data-testid="water-card"] [data-testid="listen"]')?.getAttribute('data-state') !== 'loading', { timeout: 30000 }).catch(() => undefined);
				ok('public: the Listen button plays', (await p.$eval('[data-testid="water-card"] [data-testid="listen"]', (e) => e.getAttribute('data-state'))) === 'playing');
				await shot(p, 'citizen_listen');
			}
			await p.close();
		}
		const other = publicWrites.filter((w) => !/\/api\/speech\/speech\/speak$/.test(w));
		ok('public: the only write a public page makes is the speak request; never /api/v1/events', other.length === 0, other.join(' | ') || `${publicWrites.length} speak`);
	}
} catch (e) {
	ok('smoke ran to the end', false, e?.message ?? String(e));
} finally {
	await browser.close();
}

ok('zero page errors', errors.length === 0, errors.slice(0, 4).join(' | '));
if (failures) {
	console.error(`\nai-field-smoke: ${failures} failure(s)`);
	process.exit(1);
}
console.log('\nall ai-field-smoke checks passed');
