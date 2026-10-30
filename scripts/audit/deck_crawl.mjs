/**
 * audit/deck_crawl.mjs — an end-to-end crawl of the command deck, as a user would see it.
 *
 *   node scripts/audit/deck_crawl.mjs [--origin http://127.0.0.1:5373] [--out <dir>]
 *        [--langs mr,en,hi] [--widths 1440,390] [--only /map,/plan] [--concurrency 3]
 *        [--settle 20000] [--signin 'Demo duty officer'] [--design] [--no-links] [--list]
 *
 * NOT a test and never a writer: a read-only crawl. Every route (public pages in an anonymous context, operator
 * pages in a signed-in one) is opened in each language (the sajag_lang cookie: mr | en | hi) at each width
 * (1440 × 900 and 390 × 844), left to settle for --settle ms after load, and then checked for:
 *
 *   console errors and uncaught page errors; failed requests (4xx/5xx and transport failures; the deliberate
 *   403s are listed apart); broken images (an <img> that finished with no pixels) and fonts that failed;
 *   raw i18n keys on screen (a visible token that IS a pack key) and English left on a mr/hi page where the
 *   pack has a translation for it (plus a review list of Latin-script runs); horizontal scroll and clipped or
 *   off-screen text at the phone width; spinners / loading text / aria-busy still showing after the settle;
 *   visible panels with nothing in them; buttons with no handler anywhere (a dead button); and every link the
 *   UI shows, fetched afterwards (a dead link / a 404 route).
 *
 * SAFETY (the live deck, :5373): every non-GET /api/* request is answered 503 here and never reaches the deck,
 * except the session itself and the compute reads the pages make on load (speech/vision/twin/hydro/forecast,
 * the flow layer's live POST read) — the crawl can never approve, reject, dispatch or plan anything. Response
 * bodies are never logged (a signed-in answer may carry a token). The operator PIN is read at run time by
 * scripts/lib/deck_session.mjs and never printed. /design/* is a developer harness (404 in production by
 * design): it is crawled only with --design (point --origin at a dev deck).
 *
 * Output (in --out): one JPEG per page view (<slug>.<lang>.<width>.jpg), report.json (every finding) and
 * summary.txt (the findings grouped by kind). Exit 0 always unless the crawl itself failed.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { puppeteerCookies, signIn, signOut } from '../lib/deck_session.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const DECK = path.join(ROOT, 'services', 'command-deck');
const require = createRequire(path.join(ROOT, 'frontend', 'package.json'));
const puppeteer = require('puppeteer-core');
const CHROME = process.env.CHROME_PATH
	|| `${process.env.HOME}/.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome`;

const argv = process.argv.slice(2);
const opt = (name, dflt) => {
	const i = argv.indexOf(name);
	return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : dflt;
};
const flag = (name) => argv.includes(name);
const ORIGIN = opt('--origin', 'http://127.0.0.1:5373').replace(/\/+$/, '');
const OUT = path.resolve(opt('--out', path.join(os.tmpdir(), 'sajag-deck-crawl')));
const LANGS = opt('--langs', 'mr,en,hi').split(',').map((s) => s.trim()).filter(Boolean);
const WIDTHS = opt('--widths', '1440,390').split(',').map((s) => Number(s.trim())).filter(Boolean);
const ONLY = opt('--only', '').split(',').map((s) => s.trim()).filter(Boolean);
const CONCURRENCY = Math.max(1, Number(opt('--concurrency', '3')));
const SETTLE = Number(opt('--settle', '20000'));
const OFFICER = opt('--signin', 'Demo duty officer');
const LIVE = new URL(ORIGIN).port === '5373';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
/** A step that may not hang the crawl: rejects after ms. */
const within = (ms, what, p) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error(`${what}: no answer in ${ms} ms`)), ms))]);

const VIEWS = {
	1440: { width: 1440, height: 900 },
	390: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
};

// ── the routes ───────────────────────────────────────────────────────────────
/** public: anonymous context. '@decide-unit' is resolved at run time (the first unit of the live queue). */
const ROUTES = [
	{ url: '/welcome', public: true },
	{ url: '/citizen', public: true },
	{ url: '/driver', public: true },
	{ url: '/' },
	{ url: '/home' },
	{ url: '/map' },
	{ url: '/decide' },
	{ url: '@decide-unit' },
	{ url: '/plan' },
	{ url: '/assistant' },
	{ url: '/o/camera:EM-CAM-04' },
	{ url: '/o/segment:1033' },
	{ url: '/analyst' },
	{ url: '/ops' },
	{ url: '/gods-eye' },
	{ url: '/chat' },
	{ url: '/comms' },
	{ url: '/v3-gallery' },
	// the operator console opened WITHOUT signing in (what a stranger on the LAN sees): one language, one width
	{ url: '/', anon: true, langs: ['en', 'mr'], widths: [1440] },
	{ url: '/decide', anon: true, langs: ['en'], widths: [1440] },
	{ url: '/map', anon: true, langs: ['en'], widths: [1440] },
	...(flag('--design')
		? ['/design', '/design/analysis', '/design/decisions', '/design/dss', '/design/map', '/design/osint', '/design/shell',
			'/design/views', '/design/workspace'].map((url) => ({ url, langs: ['en'], widths: [1440] }))
		: []),
];

if (flag('--list')) {
	for (const r of ROUTES) console.log(`${r.url}${r.public ? '  (public)' : r.anon ? '  (anonymous)' : ''}`);
	process.exit(0);
}

// ── the i18n packs: every key and its value per language ────────────────────
function packIndex() {
	const files = [];
	const walk = (d) => {
		for (const e of fs.readdirSync(d, { withFileTypes: true })) {
			const p = path.join(d, e.name);
			if (e.isDirectory()) walk(p);
			else if (/^(packs|strings)\..*\.ts$|^(packs|strings)\.ts$/.test(e.name)) files.push(p);
		}
	};
	walk(path.join(DECK, 'src'));
	const keys = new Set();
	const val = { en: new Map(), mr: new Map(), hi: new Map() };
	const re = /^\s*(?:'([^']+)'|"([^"]+)"|([A-Za-z_$][\w$.]*))\s*:\s*(?:'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\$\n]|\\.)*)`)\s*,?\s*$/gm;
	for (const f of files) {
		const lang = /\.mr\.ts$/.test(f) ? 'mr' : /\.hi\.ts$/.test(f) ? 'hi' : 'en';
		const src = fs.readFileSync(f, 'utf8');
		for (const m of src.matchAll(re)) {
			const k = m[1] ?? m[2] ?? m[3];
			const v = (m[4] ?? m[5] ?? m[6] ?? '').replace(/\\(['"`\\])/g, '$1');
			if (!k || k.length < 4) continue;
			keys.add(k);
			if (!val[lang].has(k)) val[lang].set(k, v);
		}
		// keys whose value is a function or spans lines still count as keys
		for (const m of src.matchAll(/^\s*(?:'([^']+)'|([A-Za-z_$][\w$]*_[\w$]*))\s*:/gm)) {
			const k = m[1] ?? m[2];
			if (k && k.length >= 4) keys.add(k);
		}
	}
	return { keys, val, files: files.length };
}
const PACKS = packIndex();
/** English value → the keys that carry it (only values with letters worth matching). */
const EN_BY_VALUE = new Map();
for (const [k, v] of PACKS.val.en) {
	const t = v.trim();
	if (t.length < 3 || !/[A-Za-z]{3}/.test(t)) continue;
	if (!EN_BY_VALUE.has(t)) EN_BY_VALUE.set(t, []);
	EN_BY_VALUE.get(t).push(k);
}

// ── the page probe (runs inside the page) ─────────────────────────────────────
/** Before any page script: record which elements get which listeners (a dead-button check needs it). */
function listenerRecorder() {
	const W = new WeakMap();
	Object.defineProperty(window, '__auditListeners', { value: W });
	const orig = EventTarget.prototype.addEventListener;
	EventTarget.prototype.addEventListener = function (type, fn, opts) {
		try {
			let s = W.get(this);
			if (!s) W.set(this, (s = new Set()));
			s.add(type);
		} catch {}
		return orig.call(this, type, fn, opts);
	};
}

function probe(narrow) {
	const vw = window.innerWidth;
	const vh = window.innerHeight;
	const out = {};
	const visible = (el) => {
		if (!el || !el.getBoundingClientRect) return false;
		const r = el.getBoundingClientRect();
		if (r.width < 1 || r.height < 1) return false;
		const cs = getComputedStyle(el);
		if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) return false;
		if (el.closest('[hidden], [aria-hidden="true"], [inert]')) return false;
		return true;
	};
	const sel = (el) => {
		if (!el || el.nodeType !== 1) return '';
		const parts = [];
		let e = el;
		for (let i = 0; e && e.nodeType === 1 && i < 4; i++, e = e.parentElement) {
			let s = e.tagName.toLowerCase();
			if (e.id) { s += `#${e.id}`; parts.unshift(s); break; }
			const tid = e.getAttribute('data-testid');
			if (tid) { s += `[data-testid="${tid}"]`; parts.unshift(s); break; }
			const cls = [...e.classList].filter((c) => !/^s-|^svelte-/.test(c)).slice(0, 2).join('.');
			if (cls) s += `.${cls}`;
			parts.unshift(s);
		}
		return parts.join(' > ');
	};

	// visible text nodes
	const texts = [];
	const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
	for (let n = tw.nextNode(); n; n = tw.nextNode()) {
		const t = n.nodeValue.replace(/\s+/g, ' ').trim();
		if (!t) continue;
		const p = n.parentElement;
		if (!p || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(p.tagName)) continue;
		if (!visible(p)) continue;
		// clipped by an ancestor (scrolled away) still counts as text on the page; only the box matters
		texts.push({ t, s: sel(p) });
	}
	for (const el of document.querySelectorAll('input[placeholder], textarea[placeholder]')) {
		if (visible(el)) texts.push({ t: el.getAttribute('placeholder').trim(), s: sel(el), attr: 'placeholder' });
	}
	for (const el of document.querySelectorAll('[title], [aria-label]')) {
		if (!visible(el)) continue;
		for (const a of ['title', 'aria-label']) {
			const v = el.getAttribute(a);
			if (v && v.trim()) texts.push({ t: v.trim(), s: sel(el), attr: a });
		}
	}
	out.texts = texts;
	out.title = document.title;
	out.lang = document.documentElement.lang;
	out.path = location.pathname + location.search;
	out.status404 = /\b404\b/.test(document.body.innerText.slice(0, 400)) && /not found/i.test(document.body.innerText.slice(0, 400));

	// broken images
	out.brokenImages = [...document.images]
		.filter((img) => img.getAttribute('src') && img.complete && img.naturalWidth === 0 && visible(img))
		.map((img) => ({ src: img.currentSrc || img.src, alt: img.alt, s: sel(img) }));
	// fonts
	out.fonts = [...document.fonts].map((f) => ({ family: f.family, status: f.status, weight: f.weight }))
		.filter((f) => f.status === 'error');

	// loading states still showing
	const loading = [];
	const loadRe = /^(loading|লোড হচ্ছে|लोड हो रहा)|(loading|লোড হচ্ছে|लोड हो रहा( है)?)\s*(…|\.\.\.)?$/i;
	for (const x of texts) if (!x.attr && loadRe.test(x.t)) loading.push({ kind: 'text', t: x.t, s: x.s });
	for (const el of document.querySelectorAll('[aria-busy="true"], [class*="spinner"], [class*="skeleton"], [class*="shimmer"], [role="progressbar"]:not([aria-valuenow])')) {
		if (visible(el)) loading.push({ kind: 'busy', s: sel(el), cls: String(el.className).slice(0, 80) });
	}
	out.loading = loading.slice(0, 20);

	// empty panels
	const empties = [];
	for (const el of document.querySelectorAll('section, article, aside, [role="region"], [role="tabpanel"], [role="dialog"], [class*="panel"], [class*="card"], [class*="tile"]')) {
		if (/^(CANVAS|IMG|SVG|VIDEO|IFRAME|PICTURE|svg)$/.test(el.tagName)) continue;
		if (!visible(el)) continue;
		const r = el.getBoundingClientRect();
		if (r.width < 120 || r.height < 60) continue;
		if (r.bottom < 0 || r.top > vh * 3) continue;
		if ((el.innerText || '').trim().length) continue;
		if (el.querySelector('img, canvas, svg, video, iframe, picture, input, select, textarea, object')) continue;
		const bg = getComputedStyle(el).backgroundImage;
		if (bg && bg !== 'none' && /url\(/.test(bg)) continue;
		empties.push({ s: sel(el), w: Math.round(r.width), h: Math.round(r.height) });
	}
	out.empty = empties.slice(0, 12);

	// dead buttons: no handler on the element, a near ancestor, or Svelte's delegated map anywhere up the tree
	const L = window.__auditListeners;
	const ACT = new Set(['click', 'pointerdown', 'pointerup', 'mousedown', 'mouseup', 'touchstart', 'touchend', 'keydown']);
	const svelteHas = (el) => {
		for (const sym of Object.getOwnPropertySymbols(el)) {
			if (sym.description === 'events') {
				const m = el[sym];
				if (m && (m.click || m.pointerdown || m.pointerup || m.mousedown || m.mouseup || m.touchstart)) return true;
			}
		}
		return false;
	};
	const dead = [];
	for (const el of document.querySelectorAll('button, [role="button"], [role="tab"], [role="switch"], [role="menuitem"], [role="option"], a:not([href])')) {
		if (!visible(el)) continue;
		if (el.disabled || el.getAttribute('aria-disabled') === 'true') continue;
		if (el.tagName === 'A' && !el.matches('[role]') && !el.onclick) continue; // a plain anchor without href: not a control
		if (el.type === 'submit' && el.form) continue;
		if (el.hasAttribute('popovertarget') || el.hasAttribute('commandfor')) continue;
		if (el.closest('summary, label')) continue;
		let live = !!el.onclick;
		for (let e = el, i = 0; e && e !== document.documentElement && !live; e = e.parentElement, i++) {
			if (svelteHas(e)) live = true;
			else if (i < 4 && L) {
				const s = L.get(e);
				if (s && [...s].some((t) => ACT.has(t))) live = true;
			}
			if (e.onclick && i < 4) live = true;
		}
		if (!live) dead.push({ s: sel(el), t: (el.innerText || el.getAttribute('aria-label') || el.title || '').trim().slice(0, 60) });
	}
	out.deadButtons = dead.slice(0, 20);

	// links
	out.links = [...document.querySelectorAll('a[href]')]
		.filter((a) => visible(a) || a.closest('nav, header, footer, menu'))
		.map((a) => ({ href: a.href, t: (a.innerText || a.getAttribute('aria-label') || '').trim().slice(0, 50) }));

	// layout at the phone width
	const se = document.scrollingElement || document.documentElement;
	out.hscroll = se.scrollWidth > vw + 1 ? se.scrollWidth : 0;
	out.overflow = [];
	out.clipped = [];
	if (narrow) {
		const scrollsX = (e) => {
			for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) {
				const cs = getComputedStyle(a);
				if (/(auto|scroll)/.test(cs.overflowX) && a.scrollWidth > a.clientWidth) return true;
				if (/(hidden|clip)/.test(cs.overflowX)) return 'clip';
			}
			return false;
		};
		for (const el of document.body.querySelectorAll('*')) {
			if (!el.childElementCount && !(el.textContent || '').trim()) continue;
			if (!visible(el)) continue;
			const cs = getComputedStyle(el);
			if (cs.position === 'fixed' && el.getBoundingClientRect().width >= vw) continue;
			const r = el.getBoundingClientRect();
			if (r.right > vw + 2 && r.left < vw && r.width < vw * 3) {
				const sx = scrollsX(el);
				// cut off by an overflow:hidden ancestor (no scroll to reach it) counts too: the reader never sees it
				if (sx !== true) out.overflow.push({ s: sel(el), right: Math.round(r.right), cut: sx === 'clip', t: (el.innerText || '').trim().slice(0, 50) });
			}
			const ownText = [...el.childNodes].some((c) => c.nodeType === 3 && c.nodeValue.trim());
			// a visually-hidden screen-reader label (1 px box) is not clipped text
			if (ownText && el.clientWidth > 4 && el.scrollWidth > el.clientWidth + 2 && /(hidden|clip)/.test(cs.overflowX) && cs.textOverflow !== 'ellipsis' && !/-webkit-box/.test(cs.display)) {
				out.clipped.push({ s: sel(el), t: el.textContent.trim().slice(0, 60), sw: el.scrollWidth, cw: el.clientWidth });
			}
		}
		// keep the outermost overflowing elements only
		out.overflow = out.overflow.filter((o, i, a) => !a.slice(0, i).some((p) => o.s.startsWith(p.s))).slice(0, 15);
		out.clipped = out.clipped.slice(0, 15);
	}
	out.docHeight = se.scrollHeight;
	return out;
}

// ── findings from one probe ─────────────────────────────────────────────────
const LATIN_OK = /^(?:[A-Z0-9][A-Z0-9 .:·/+\-–—()&%#°,]*|\S+@\S+|https?:\/\/\S+|[\d\s.:,·/–—+\-%°()]+|IST|AQI|PM2\.5|PM10|OSM|ETA|KMC|KTP|WBSDMA|WBTC|BMC|BEST|MTP|MMRDA|MSDMA|MSRDC|CSMT|BKC|WEH|EEH|LBS|JVLR|SCLR|KEM|LTT|ANPR|FIR|AI|ID|GPS|OK|km|m|min|s|h)$/;
function textFindings(view, lang) {
	const keys = [];
	const english = [];
	const latin = [];
	const seen = new Set();
	for (const x of view.texts) {
		const t = x.t;
		if (seen.has(t + x.attr)) continue;
		seen.add(t + x.attr);
		// a raw key: the whole text is a pack key, or a snake_case token that is one
		if (PACKS.keys.has(t)) keys.push({ t, s: x.s, attr: x.attr });
		else {
			for (const m of t.matchAll(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g)) {
				if (PACKS.keys.has(m[0])) keys.push({ t: m[0], in: t.slice(0, 80), s: x.s, attr: x.attr });
			}
		}
		if (lang === 'en') continue;
		const enKeys = EN_BY_VALUE.get(t);
		if (enKeys) {
			const tr = enKeys.map((k) => PACKS.val[lang].get(k)).find((v) => v && v.trim() && v.trim() !== t);
			if (tr) { english.push({ t: t.slice(0, 80), want: tr.slice(0, 80), key: enKeys[0], s: x.s, attr: x.attr }); continue; }
		}
		// a Latin-script run of two or more words that is not a code, a unit or an acronym (for review)
		const words = t.match(/[A-Za-z][A-Za-z'’-]+/g) || [];
		const nonLatin = (t.match(/[ऀ-ॿঀ-৿]/g) || []).length;
		if (words.length >= 2 && nonLatin === 0 && !LATIN_OK.test(t) && words.some((w) => /[a-z]{3}/.test(w))) {
			latin.push({ t: t.slice(0, 90), s: x.s, attr: x.attr });
		}
	}
	return { keys, english, latin };
}

// ── the crawl ─────────────────────────────────────────────────────────────────
const isDeliberate = (u, status) => status === 403 && /\/api\/(vision|speech|forecast|hydro|twin|cityfeeds)\//.test(u.pathname);
const COMPUTE = (u) => /^\/api\/(speech|vision|twin|hydro|forecast)\//.test(u.pathname)
	|| u.pathname.endsWith('/api/v1/traffic/live') || u.pathname === '/api/session';

async function openView(browser, ctx, session, route, lang, width) {
	const page = await ctx.newPage();
	await page.bringToFront().catch(() => {});
	const net = [];
	const errs = [];
	const blocked = [];
	const deliberate = [];
	try {
		await page.evaluateOnNewDocument(listenerRecorder);
		await page.setViewport(VIEWS[width]);
		const host = new URL(ORIGIN).hostname;
		const cookies = [{ name: 'sajag_lang', value: lang, domain: host, path: '/' }];
		if (!route.public && !route.anon && session && session.gate !== false) cookies.push(...puppeteerCookies(session));
		await page.setCookie(...cookies);
		page.on('pageerror', (e) => errs.push({ kind: 'pageerror', msg: String(e.message || e).slice(0, 300) }));
		page.on('console', (m) => {
			if (m.type() === 'error') errs.push({ kind: 'console', msg: m.text().slice(0, 300), at: m.location()?.url?.slice(0, 120) });
		});
		page.on('response', (res) => {
			const s = res.status();
			if (s < 400) return;
			const u = new URL(res.url());
			const rec = { status: s, method: res.request().method(), url: (u.origin === ORIGIN ? '' : u.origin) + u.pathname + u.search.slice(0, 120), type: res.request().resourceType() };
			if (isDeliberate(u, s)) deliberate.push(rec);
			else if (rec.method !== 'GET' && s === 503 && blocked.some((b) => b.url === rec.url)) { /* our own guard */ }
			else net.push(rec);
		});
		page.on('requestfailed', (req) => {
			const f = req.failure()?.errorText || 'failed';
			if (/ERR_ABORTED/.test(f) && /fetch|xhr|eventsource|other|ping/.test(req.resourceType())) return;
			const u = new URL(req.url());
			if (blocked.some((b) => b.url === u.pathname)) return;
			net.push({ status: f, method: req.method(), url: (u.origin === ORIGIN ? '' : u.origin) + u.pathname, type: req.resourceType() });
		});
		if (LIVE) {
			await page.setRequestInterception(true);
			page.on('request', (req) => {
				if (req.isInterceptResolutionHandled()) return;
				const u = new URL(req.url());
				if (u.origin === ORIGIN && u.pathname.startsWith('/api/') && req.method() !== 'GET' && req.method() !== 'HEAD' && !COMPUTE(u)) {
					blocked.push({ method: req.method(), url: u.pathname });
					return req.respond({ status: 503, contentType: 'application/json', body: '{"error":"deck_crawl: live writes refused"}' });
				}
				return req.continue();
			});
		}
		const t0 = Date.now();
		let navStatus = null;
		try {
			const res = await page.goto(ORIGIN + route.resolved, { waitUntil: 'load', timeout: 60000 });
			navStatus = res?.status() ?? null;
		} catch (e) {
			errs.push({ kind: 'goto', msg: String(e.message).slice(0, 200) });
		}
		const remain = SETTLE - (Date.now() - t0);
		if (remain > 0) await sleep(remain);
		const view = await within(60000, 'probe', page.evaluate(probe, width < 600)).catch((e) => ({ probeError: String(e).slice(0, 200), texts: [] }));
		const slug = route.resolved.replace(/^\/$/, 'root').replace(/^\//, '').replace(/[^a-z0-9]+/gi, '-').replace(/-+$/, '') + (route.anon ? '-anon' : '');
		const file = path.join(OUT, `${slug}.${lang}.${width}.jpg`);
		await within(45000, 'screenshot', page.screenshot({ path: file, type: 'jpeg', quality: 80 })).catch((e) => errs.push({ kind: 'crawl', msg: String(e).slice(0, 120) }));
		let full = null;
		if (width < 600 && view.docHeight > VIEWS[width].height + 40) {
			full = path.join(OUT, `${slug}.${lang}.${width}.full.jpg`);
			await within(45000, 'full screenshot', page.screenshot({ path: full, type: 'jpeg', quality: 70, fullPage: true, captureBeyondViewport: true })).catch(() => { full = null; });
		}
		const tf = textFindings(view, lang);
		return {
			route: route.resolved, anon: !!route.anon, public: !!route.public, lang, width, navStatus,
			landed: view.path, title: view.title, docLang: view.lang, shot: file, full,
			errors: errs.slice(0, 25), network: dedupe(net).slice(0, 30), deliberate: dedupe(deliberate).length,
			blockedWrites: dedupe(blocked), brokenImages: view.brokenImages ?? [], fonts: view.fonts ?? [],
			rawKeys: tf.keys, english: tf.english, latin: tf.latin,
			hscroll: view.hscroll ?? 0, overflow: view.overflow ?? [], clipped: view.clipped ?? [],
			loading: view.loading ?? [], empty: view.empty ?? [], deadButtons: view.deadButtons ?? [],
			notFound: navStatus === 404 || !!view.status404, links: view.links ?? [], probeError: view.probeError,
		};
	} finally {
		await within(15000, 'close', page.close()).catch(() => {});
	}
}

function dedupe(list) {
	const m = new Map();
	for (const x of list) {
		const k = JSON.stringify(x);
		m.set(k, { ...x, n: (m.get(k)?.n ?? 0) + 1 });
	}
	return [...m.values()];
}

/** The first decision unit of the queue (a deep link), else /decide itself. */
async function resolveDecideUnit(browser, session) {
	const page = await browser.defaultBrowserContext().newPage();
	try {
		await page.setViewport(VIEWS[1440]);
		const host = new URL(ORIGIN).hostname;
		await page.setCookie({ name: 'sajag_lang', value: 'en', domain: host, path: '/' }, ...(session?.gate ? puppeteerCookies(session) : []));
		await page.goto(ORIGIN + '/decide', { waitUntil: 'load', timeout: 60000 });
		for (let i = 0; i < 30; i++) {
			const p = await page.evaluate(() => location.pathname);
			if (/^\/decide\/.+/.test(p)) return decodeURIComponent(p);
			const clicked = await page.evaluate(() => {
				const c = document.querySelector('[data-testid="queue-card"], [data-testid="ai-queue-card"]');
				if (c) { c.click(); return true; }
				return false;
			});
			await sleep(clicked ? 1500 : 1000);
		}
		return null;
	} catch {
		return null;
	} finally {
		await page.close().catch(() => {});
	}
}

async function checkLinks(urls, session) {
	const out = [];
	const queue = [...urls];
	const worker = async () => {
		while (queue.length) {
			const href = queue.shift();
			let u;
			try { u = new URL(href); } catch { out.push({ href, status: 'bad url' }); continue; }
			if (!/^https?:$/.test(u.protocol)) continue;
			const same = u.origin === ORIGIN;
			try {
				const res = await fetch(u.origin + u.pathname + u.search, {
					method: same ? 'GET' : 'HEAD', redirect: 'manual',
					headers: same && session?.cookie ? { cookie: session.cookie } : { 'user-agent': 'Mozilla/5.0 (deck link check)' },
					signal: AbortSignal.timeout(same ? 20000 : 10000),
				});
				out.push({ href: same ? u.pathname + u.search : href, status: res.status, location: res.headers.get('location') || undefined, external: !same });
				await res.body?.cancel().catch(() => {});
			} catch (e) {
				out.push({ href: same ? u.pathname : href, status: `error: ${String(e.cause?.code || e.name || e).slice(0, 60)}`, external: !same });
			}
		}
	};
	await Promise.all(Array.from({ length: 6 }, worker));
	return out;
}

// ── main ──────────────────────────────────────────────────────────────────────
fs.mkdirSync(OUT, { recursive: true });
/** One browser per worker: a page's screenshot waits for a frame, and only a browser's foreground tab paints. */
const launch = () => puppeteer.launch({
	executablePath: CHROME,
	headless: 'new',
	protocolTimeout: 180000,
	args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--use-gl=angle', '--ignore-gpu-blocklist',
		'--window-size=1440,900', '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
		'--disable-backgrounding-occluded-windows', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required'],
});
const browsers = [];
let session = null;
const results = [];
let linkResults = [];
try {
	session = await signIn(ORIGIN, OFFICER);
	const first = await launch();
	browsers.push(first);
	const unit = (await resolveDecideUnit(first, session)) || '/decide';
	const todo = [];
	for (const r of ROUTES) {
		const resolved = r.url === '@decide-unit' ? unit : r.url;
		if (ONLY.length && !ONLY.includes(r.url) && !ONLY.includes(resolved)) continue;
		for (const lang of r.langs ?? LANGS) {
			if (!LANGS.includes(lang)) continue;
			for (const width of r.widths ?? WIDTHS) {
				if (!WIDTHS.includes(width)) continue;
				todo.push({ route: { ...r, resolved }, lang, width });
			}
		}
	}
	console.log(`deck_crawl: ${todo.length} page views on ${ORIGIN} (gate ${session.gate ? 'on, signed in' : 'off'}), packs: ${PACKS.keys.size} keys from ${PACKS.files} files`);
	let done = 0;
	const worker = async (w) => {
		const browser = w === 0 ? first : await launch();
		if (w) browsers.push(browser);
		const signedCtx = browser.defaultBrowserContext();
		const anonCtx = await browser.createBrowserContext();
		while (todo.length) {
			const job = todo.shift();
			const ctx = job.route.public || job.route.anon ? anonCtx : signedCtx;
			try {
				const r = await within(SETTLE + 240000, 'page view', openView(browser, ctx, session, job.route, job.lang, job.width));
				results.push(r);
				const n = r.errors.length + r.network.length + r.rawKeys.length + r.english.length + r.brokenImages.length
					+ (r.hscroll ? 1 : 0) + r.overflow.length + r.loading.length + r.empty.length + r.deadButtons.length + (r.notFound ? 1 : 0);
				console.log(`[${++done}] ${job.route.resolved}${job.route.anon ? ' (anon)' : ''} ${job.lang} ${job.width}: ${n} finding(s)`);
			} catch (e) {
				results.push({ route: job.route.resolved, lang: job.lang, width: job.width, crawlError: String(e).slice(0, 300) });
				console.log(`[${++done}] ${job.route.resolved} ${job.lang} ${job.width}: CRAWL ERROR ${String(e).slice(0, 160)}`);
			}
		}
	};
	await Promise.all(Array.from({ length: CONCURRENCY }, (_, w) => worker(w)));
	if (!flag('--no-links')) {
		const hrefs = new Set();
		for (const r of results) for (const l of r.links ?? []) hrefs.add(l.href.split('#')[0]);
		linkResults = await checkLinks([...hrefs], session);
	}
} finally {
	if (session && session.gate) await signOut(session).catch(() => {});
	await Promise.all(browsers.map((b) => within(15000, 'browser close', b.close()).catch(() => b.process()?.kill('SIGKILL'))));
}

// ── report ────────────────────────────────────────────────────────────────────
const at = (r) => `${r.route}${r.anon ? ' (anon)' : ''} [${r.lang} ${r.width}]`;
const lines = [];
const section = (title, rows) => {
	lines.push(`\n## ${title} (${rows.length})`);
	for (const row of rows) lines.push(row);
};
const by = (pick) => results.flatMap((r) => (pick(r) || []).map((x) => ({ r, x })));
section('crawl errors', results.filter((r) => r.crawlError || r.probeError).map((r) => `${at(r)} ${r.crawlError || r.probeError}`));
section('404 / not found', results.filter((r) => r.notFound).map((r) => `${at(r)} nav=${r.navStatus} landed=${r.landed}`));
section('console + page errors', by((r) => r.errors).map(({ r, x }) => `${at(r)} ${x.kind}: ${x.msg}`));
section('failed requests', by((r) => r.network).map(({ r, x }) => `${at(r)} ${x.status} ${x.method} ${x.url} (${x.type}) ×${x.n}`));
section('broken images', by((r) => r.brokenImages).map(({ r, x }) => `${at(r)} ${x.src} — ${x.s}`));
section('fonts failed', by((r) => r.fonts).map(({ r, x }) => `${at(r)} ${x.family} ${x.weight}`));
section('raw i18n keys on screen', by((r) => r.rawKeys).map(({ r, x }) => `${at(r)} "${x.t}"${x.in ? ` in "${x.in}"` : ''}${x.attr ? ` (${x.attr})` : ''} — ${x.s}`));
section('English shown where a translation exists', by((r) => r.english).map(({ r, x }) => `${at(r)} "${x.t}" → "${x.want}" [${x.key}]${x.attr ? ` (${x.attr})` : ''} — ${x.s}`));
section('horizontal scroll', results.filter((r) => r.hscroll).map((r) => `${at(r)} scrollWidth=${r.hscroll}`));
section('off-screen at the phone width', by((r) => r.overflow).map(({ r, x }) => `${at(r)} right=${x.right}${x.cut ? ' (cut off)' : ''} "${x.t}" — ${x.s}`));
section('clipped text', by((r) => r.clipped).map(({ r, x }) => `${at(r)} "${x.t}" ${x.sw}>${x.cw} — ${x.s}`));
section('still loading after the settle', by((r) => r.loading).map(({ r, x }) => `${at(r)} ${x.kind} ${x.t || x.cls || ''} — ${x.s}`));
section('empty panels', by((r) => r.empty).map(({ r, x }) => `${at(r)} ${x.w}×${x.h} — ${x.s}`));
section('dead buttons (no handler found)', by((r) => r.deadButtons).map(({ r, x }) => `${at(r)} "${x.t}" — ${x.s}`));
section('links: bad status', linkResults.filter((l) => typeof l.status !== 'number' || l.status >= 400).map((l) => `${l.status} ${l.href}`));
section('blocked live writes (informational)', by((r) => r.blockedWrites).map(({ r, x }) => `${at(r)} ${x.method} ${x.url} ×${x.n}`));
// the Latin review list, deduplicated across views
const latin = new Map();
for (const { r, x } of by((r) => r.latin)) {
	const k = x.t.replace(/\b[A-Z]{2}\s?\d{2}\s?[A-Z]{1,3}\s?\d{3,4}\b/g, '<plate>').replace(/\d+(\.\d+)?/g, '#');
	if (!latin.has(k)) latin.set(k, { x, where: new Set() });
	latin.get(k).where.add(`${r.route} ${r.lang}`);
}
section('Latin-script text on mr/hi pages (review)', [...latin.values()].map(({ x, where }) => `"${x.t}"${x.attr ? ` (${x.attr})` : ''} — ${x.s} — ${[...where].slice(0, 4).join(', ')}${where.size > 4 ? ` +${where.size - 4}` : ''}`));
fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify({ origin: ORIGIN, at: new Date().toISOString(), results: results.map(({ links, ...r }) => r), links: linkResults }, null, 1));
fs.writeFileSync(path.join(OUT, 'summary.txt'), `deck_crawl ${ORIGIN} ${new Date().toISOString()} — ${results.length} page views\n${lines.join('\n')}\n`);
console.log(`deck_crawl: done — ${path.join(OUT, 'summary.txt')}`);
process.exit(0);
