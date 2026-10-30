/**
 * The natural-colour satellite source of every MapThumb (V3-P4C) — Cesium ion asset 2 (Bing aerial imagery),
 * the same imagery the God's-eye canvas shows under its 3D city, fetched as plain 256 px raster tiles and
 * drawn UNGRADED. Pure of the DOM at import; the browser parts (fetch, createImageBitmap, sessionStorage) are
 * injectable so tests/v3-map-style.unit.mjs drives every rule below without a network.
 *
 * How a tile is reached (the same two steps Cesium's IonImageryProvider takes, no Cesium needed):
 *   1. ion's asset endpoint  https://api.cesium.com/v1/assets/2/endpoint?access_token=…  names the external
 *      Bing source (`externalType: 'BING'`, `options.url / key / mapStyle`) and the attributions the use requires;
 *   2. Bing's imagery metadata (…/REST/v1/Imagery/Metadata/Aerial?incl=ImageryProviders&uriScheme=https&key=…)
 *      gives the tile URL template (quadkey + subdomains), the highest zoom and the per-area copyright lines.
 * The token is the one the deck's own mode endpoint hands the canvas (stores/godsEye.imageryToken); it lives only
 * in this object's private field and in those request URLs — never in the DOM, a log, an error or a thrown message.
 *
 * QUOTA — thumbnails can never exhaust ion (the user's rule). Everything below is a hard limit, not a hope:
 *   • ≤ SAT_CARD_TILES (6) tiles on a card, ≤ SAT_HERO_TILES (40) on an eager hero/stage (MapThumb frames to it);
 *   • ≤ SAT_MAX_IN_FLIGHT (4) requests in flight, through the SAME queue as the night tiles (tiles.ts);
 *   • one shared LRU (tiles.ts) — a tile already drawn is never fetched twice;
 *   • at most SAT_SESSION_CAP (800) network requests per browser-tab session, endpoint + metadata + tiles all counted,
 *     kept in sessionStorage so a reload loop cannot reset it (≈ 55 Bing billable transactions: negligible);
 *   • the last SAT_HERO_RESERVE (200) of them are kept for the eager heroes (Home's featured decision, a stage): a card
 *     asks with priority 'card' and draws the night tiles once the session is that close to the cap, so a long shift
 *     of browsing cards never leaves the featured decision without its satellite picture (the cap itself is unchanged);
 *   • the first 401 / 403 (a dead token) or 429 (a spent quota) switches the whole session to the night tiles,
 *     silently, and is remembered for the session; transient network failures retry, then (3 in a row) do the same
 *     for this page view; requests still queued behind the failure are NOT sent.
 * When satellite is off, the thumbs draw the keyless night tiles (OSM) — never a blank, never an error colour.
 */

export const ION_ENDPOINT_URL = 'https://api.cesium.com/v1/assets/2/endpoint';
export const SAT_CARD_TILES = 6;
export const SAT_HERO_TILES = 40;
export const SAT_MAX_IN_FLIGHT = 4;
export const SAT_SESSION_CAP = 800;
/** Of the session cap, the requests only an eager hero / stage may spend (a card yields them; the cap stays 800). */
export const SAT_HERO_RESERVE = 200;
/** Who asks for a tile: an eager hero or stage (the whole budget) or a card (all but the hero reserve). */
export type SatPriority = 'hero' | 'card';
/** Endpoint + metadata attempts per page view (a flaky network cannot loop on them). */
export const SAT_SETUP_CAP = 4;
/** Consecutive transient failures before satellite stands down for this page view. */
export const SAT_FAIL_LIMIT = 3;
export const SAT_TILE_TIMEOUT_MS = 12_000;
/**
 * A setup that failed for a transient reason (no answer, a refused TLS handshake from one of api.cesium.com's edges, a 5xx)
 * is retried ONCE after this pause, inside the same burst of thumbs — so a hiccup does not leave a whole page on the night
 * tiles. Bounded by SAT_SETUP_CAP like every other attempt.
 */
export const SAT_RETRY_MS = 1500;

export type Degrade = 'denied' | 'quota' | 'cap' | 'unreachable' | 'unsupported';

/** What a tile fetch answers: the HTTP status and, on 200, the decoded image. */
export interface TileReply {
	status: number;
	image: CanvasImageSource | null;
}
export interface JsonReply {
	status: number;
	json: unknown;
}

export interface SatDeps {
	fetchJson(url: string): Promise<JsonReply>;
	fetchTile(url: string): Promise<TileReply>;
	/** A pause (the setup's one retry); setTimeout in the browser, instant in tests. */
	wait?: (ms: number) => Promise<void>;
	/** The shared request queue (≤ 4 in flight across night + satellite tiles). */
	limiter: { acquire(): Promise<void>; release(): void };
	/** The per-tab-session counters (sessionStorage; memory when it is unavailable). */
	store: { used(): number; add(n: number): void; flag(): Degrade | null; setFlag(d: Degrade | null): void };
}

interface Provider {
	attribution: string;
	coverage: { zoomMin: number; zoomMax: number; bbox: [number, number, number, number] }[];
}
interface Setup {
	template: string;
	subdomains: string[];
	zoomMax: number;
	providers: Provider[];
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null;
const str = (v: unknown): string => (typeof v === 'string' ? v : '');

/** Bing's quadkey for an XYZ tile (identical to Cesium's tileXYToQuadKey). */
export function quadKey(z: number, x: number, y: number): string {
	let out = '';
	for (let i = z; i > 0; i--) {
		const mask = 1 << (i - 1);
		let digit = 0;
		if ((x & mask) !== 0) digit += 1;
		if ((y & mask) !== 0) digit += 2;
		out += digit;
	}
	return out;
}

/** An https URL on virtualearth.net — the only host Bing metadata and tiles may come from (the deck's CSP allows exactly it). */
export function isBingHost(url: string): boolean {
	try {
		const u = new URL(url);
		return u.protocol === 'https:' && (u.hostname === 'virtualearth.net' || u.hostname.endsWith('.virtualearth.net'));
	} catch {
		return false;
	}
}

/** A Bing tile URL from the metadata template (integers only; `n=z` as Cesium sends it: no placeholder for a hole). */
export function bingTileUrl(setup: Pick<Setup, 'template' | 'subdomains'>, z: number, x: number, y: number): string {
	const zi = Math.trunc(z);
	const xi = Math.trunc(x);
	const yi = Math.trunc(y);
	const sub = setup.subdomains.length ? setup.subdomains[(xi + yi + zi) % setup.subdomains.length] : '';
	const url = setup.template.replace('{subdomain}', sub).replace('{quadkey}', quadKey(zi, xi, yi)).replace('{culture}', '');
	return url + (url.includes('?') ? '&' : '?') + 'n=z';
}

const ENTITIES: Record<string, string> = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&apos;': "'", '&copy;': '©', '&nbsp;': ' ' };

/** Plain text of an HTML attribution (shown as a text node only — never injected as HTML). */
export function plainText(html: unknown): string {
	return str(html)
		// an <img alt="Cesium ion"> credit is its alt text; every other tag is dropped
		.replace(/<img\b[^>]*?\balt\s*=\s*(?:"([^"]*)"|'([^']*)')[^>]*>/gi, (_m, a, b) => ` ${a ?? b ?? ''} `)
		.replace(/<[^>]*>/g, ' ')
		.replace(/&(?:amp|lt|gt|quot|apos|copy|nbsp|#39);/g, (m) => ENTITIES[m] ?? m)
		.replace(/\s+/g, ' ')
		.trim();
}

/** The attribution lines the ion endpoint's answer requires (plain text, deduplicated). */
export function endpointCredits(endpoint: unknown): string[] {
	const a = isObj(endpoint) && Array.isArray(endpoint.attributions) ? endpoint.attributions : [];
	const out: string[] = [];
	for (const item of a) {
		const text = plainText(isObj(item) ? item.html : '');
		if (text && !out.includes(text)) out.push(text);
	}
	return out;
}

/** Parse Bing's metadata answer into what tiles and credits need (null when it is not the shape we know). */
export function parseBingMetadata(json: unknown): Setup | null {
	if (!isObj(json) || !Array.isArray(json.resourceSets) || json.resourceSets.length !== 1) return null;
	const set = json.resourceSets[0];
	const r = isObj(set) && Array.isArray(set.resources) ? set.resources[0] : null;
	if (!isObj(r)) return null;
	const template = str(r.imageUrl);
	const subdomains = Array.isArray(r.imageUrlSubdomains) ? r.imageUrlSubdomains.filter((s): s is string => typeof s === 'string' && /^[a-z0-9]+$/i.test(s)) : [];
	const w = Number(r.imageWidth);
	const h = Number(r.imageHeight);
	if (!template.includes('{quadkey}') || !isBingHost(template.replace('{subdomain}', 't0')) || (w && w !== 256) || (h && h !== 256)) return null;
	const providers: Provider[] = [];
	for (const p of Array.isArray(r.imageryProviders) ? r.imageryProviders : []) {
		if (!isObj(p)) continue;
		const attribution = plainText(p.attribution);
		const coverage: Provider['coverage'] = [];
		for (const c of Array.isArray(p.coverageAreas) ? p.coverageAreas : []) {
			if (!isObj(c) || !Array.isArray(c.bbox) || c.bbox.length !== 4) continue;
			const bbox = c.bbox.map(Number) as [number, number, number, number];
			if (bbox.every(Number.isFinite)) coverage.push({ zoomMin: Number(c.zoomMin) || 0, zoomMax: Number(c.zoomMax) || 99, bbox });
		}
		if (attribution && coverage.length) providers.push({ attribution, coverage });
	}
	return { template, subdomains, zoomMax: Number(r.zoomMax) > 0 ? Number(r.zoomMax) : 19, providers };
}

/** Bing's copyright lines for the area a thumb shows (bbox: west, south, east, north; Bing's own is south, west, north, east). */
export function providerCredits(providers: readonly Provider[], z: number, bbox: readonly [number, number, number, number]): string[] {
	const [w, s, e, n] = bbox;
	const out: string[] = [];
	for (const p of providers) {
		const hit = p.coverage.some((c) => z >= c.zoomMin && z <= c.zoomMax && c.bbox[0] <= n && c.bbox[2] >= s && c.bbox[1] <= e && c.bbox[3] >= w);
		if (hit && !out.includes(p.attribution)) out.push(p.attribution);
	}
	return out;
}

/** The on-thumb credit: the area's copyright lines first (at most two), then what ion's endpoint requires. */
export function creditLine(area: readonly string[], endpoint: readonly string[]): string {
	const parts = [...area.slice(0, 2), ...endpoint].filter((p, i, a) => p && a.indexOf(p) === i);
	return parts.join(' · ');
}

/**
 * The compact credit for a small card: the first copyright line and ion's name — the endpoint's own sentences (the
 * "Upgrade for commercial use." notice) stay in the full line, which a wide thumb and every title / tooltip carry.
 */
export function creditShort(area: readonly string[], endpoint: readonly string[]): string {
	return creditLine(area.slice(0, 1), endpoint.filter((e) => !/[.!?]$/.test(e)));
}

export class SatelliteSource {
	#token: string | null = null;
	#setup: Promise<Setup | null> | null = null;
	#info: Setup | null = null;
	#endpointCredits: string[] = [];
	#degraded: Degrade | null;
	#failures = 0;
	#setupTries = 0;
	/** The last setup attempt failed for a transient reason (worth one retry). */
	#transient = false;
	readonly #deps: SatDeps;
	/** Called once, when the session falls back to the night tiles. */
	onDegrade: ((why: Degrade) => void) | null = null;

	constructor(deps: SatDeps) {
		this.#deps = deps;
		this.#degraded = deps.store.flag();
	}

	/** The token the deck handed the canvas (idempotent; a changed token starts fresh, a latched denial stays). */
	configure(token: string | null | undefined): void {
		const next = token && token.length > 0 ? token : null;
		if (next === this.#token) return;
		this.#token = next;
		this.#setup = null;
		this.#info = null;
		this.#failures = 0;
		this.#setupTries = 0;
	}

	get available(): boolean {
		return this.#token !== null && this.#degraded === null;
	}
	get degraded(): Degrade | null {
		return this.#degraded;
	}
	/** Network requests spent this tab session (tests and the gallery). */
	get used(): number {
		return this.#deps.store.used();
	}

	#degrade(why: Degrade, persist: boolean): void {
		if (this.#degraded) return;
		this.#degraded = why;
		if (persist) this.#deps.store.setFlag(why);
		this.onDegrade?.(why);
	}

	/** Spend one request from the session budget; false (and the session stands down) when it is spent. */
	#take(): boolean {
		if (this.#deps.store.used() >= SAT_SESSION_CAP) {
			this.#degrade('cap', false);
			return false;
		}
		this.#deps.store.add(1);
		return true;
	}

	/** A reply that ends satellite for the session (a dead token, a spent quota). True when it did. */
	#refused(status: number): boolean {
		if (status === 401 || status === 403) this.#degrade('denied', true);
		else if (status === 429) this.#degrade('quota', true);
		else return false;
		return true;
	}

	#fail(): void {
		this.#transient = true;
		if (++this.#failures >= SAT_FAIL_LIMIT) this.#degrade('unreachable', false);
	}

	async #resolve(): Promise<Setup | null> {
		const token = this.#token;
		if (!token) return null;
		this.#transient = false;
		if (this.#setupTries >= SAT_SETUP_CAP) {
			this.#degrade('unreachable', false);
			return null;
		}
		this.#setupTries++;
		if (!this.#take()) return null;
		let endpoint: JsonReply;
		try {
			endpoint = await this.#deps.fetchJson(`${ION_ENDPOINT_URL}?access_token=${encodeURIComponent(token)}`);
		} catch {
			this.#fail();
			return null;
		}
		if (this.#refused(endpoint.status)) return null;
		const ep = endpoint.json;
		if (endpoint.status !== 200 || !isObj(ep)) {
			this.#fail();
			return null;
		}
		const opts = isObj(ep.options) ? ep.options : null;
		const base = opts ? str(opts.url) : '';
		const key = opts ? str(opts.key) : '';
		if (str(ep.externalType) !== 'BING' || !opts || !key || !isBingHost(base)) {
			this.#degrade('unsupported', false);
			return null;
		}
		this.#endpointCredits = endpointCredits(ep);
		const style = /^[A-Za-z]+$/.test(str(opts.mapStyle)) ? str(opts.mapStyle) : 'Aerial';
		if (!this.#take()) return null;
		let meta: JsonReply;
		try {
			meta = await this.#deps.fetchJson(`${base.replace(/\/+$/, '')}/REST/v1/Imagery/Metadata/${style}?incl=ImageryProviders&uriScheme=https&key=${encodeURIComponent(key)}`);
		} catch {
			this.#fail();
			return null;
		}
		if (this.#refused(meta.status)) return null;
		const info = meta.status === 200 ? parseBingMetadata(meta.json) : null;
		if (!info) {
			this.#fail();
			return null;
		}
		this.#failures = 0;
		this.#info = info;
		return info;
	}

	async #ready(): Promise<Setup | null> {
		if (this.#info) return this.#info;
		if (!this.#setup) {
			this.#setup = (async () => {
				let s = await this.#resolve();
				if (!s && this.#transient && this.available) {
					await (this.#deps.wait ?? ((ms) => new Promise<void>((r) => setTimeout(r, ms))))(SAT_RETRY_MS);
					if (this.available) s = await this.#resolve();
				}
				if (!s) this.#setup = null; // a later tile may try again (bounded by SAT_SETUP_CAP)
				return s;
			})();
		}
		return this.#setup;
	}

	/** One natural-colour tile (XYZ, as the night tiles), or null: no imagery there, or satellite is off. */
	async tile(z: number, x: number, y: number, priority: SatPriority = 'hero'): Promise<CanvasImageSource | null> {
		if (!this.available) return null;
		// a card leaves the last of the budget to the heroes: it draws the night tiles, and the session stays on satellite
		if (priority === 'card' && this.#deps.store.used() >= SAT_SESSION_CAP - SAT_HERO_RESERVE) return null;
		const info = await this.#ready();
		if (!info || !this.available || z > info.zoomMax) return null;
		if (!this.#take()) return null;
		await this.#deps.limiter.acquire();
		try {
			// a refusal while this request queued ends the session's requests: none of the queue is sent
			if (!this.available) return null;
			let reply: TileReply;
			try {
				reply = await this.#deps.fetchTile(bingTileUrl(info, z, x, y));
			} catch {
				this.#fail();
				return null;
			}
			if (this.#refused(reply.status)) return null;
			if (reply.status === 200 && reply.image) {
				this.#failures = 0;
				return reply.image;
			}
			// 404 / 204: Bing has no tile there — not a failure of the source
			if (reply.status >= 500) this.#fail();
			return null;
		} finally {
			this.#deps.limiter.release();
		}
	}

	/** The credit lines for a framed area (empty until a tile has been asked for): the full line and the compact one. */
	credit(z: number, bbox: readonly [number, number, number, number]): { full: string; short: string } {
		if (!this.#info && !this.#endpointCredits.length) return { full: '', short: '' };
		const area = providerCredits(this.#info?.providers ?? [], z, bbox);
		return { full: creditLine(area, this.#endpointCredits), short: creditShort(area, this.#endpointCredits) };
	}
}

// ─── the browser deps ────────────────────────────────────────────────────────

const COUNT_KEY = 'sajag.v3.sat.n';
const FLAG_KEY = 'sajag.v3.sat.off';

/** sessionStorage-backed counters (memory when storage is blocked: the budget still holds for this page view). */
export function sessionStore(): SatDeps['store'] {
	let mem = 0;
	let flag: Degrade | null = null;
	const ss = (): Storage | null => {
		try {
			return typeof sessionStorage === 'undefined' ? null : sessionStorage;
		} catch {
			return null;
		}
	};
	const used = (): number => {
		try {
			const v = Number(ss()?.getItem(COUNT_KEY));
			return Math.max(mem, Number.isFinite(v) ? v : 0);
		} catch {
			return mem;
		}
	};
	return {
		used,
		add(n) {
			mem = used() + n;
			try {
				ss()?.setItem(COUNT_KEY, String(mem));
			} catch {
				// storage blocked: memory only
			}
		},
		flag() {
			try {
				const v = ss()?.getItem(FLAG_KEY);
				if (v === 'denied' || v === 'quota') return v;
			} catch {
				// ignore
			}
			return flag;
		},
		setFlag(d) {
			flag = d;
			try {
				const s = ss();
				if (!s) return;
				if (d) s.setItem(FLAG_KEY, d);
				else s.removeItem(FLAG_KEY);
			} catch {
				// ignore
			}
		},
	};
}

/** fetch + decode in the browser. CORS (Bing and ion answer with it, as Cesium's own WebGL textures need); no cookies. */
export function browserFetchJson(url: string): Promise<JsonReply> {
	return fetch(url, { credentials: 'omit', signal: AbortSignal.timeout(SAT_TILE_TIMEOUT_MS) }).then(async (res) => ({
		status: res.status,
		json: res.ok ? await res.json().catch(() => null) : null,
	}));
}

export async function browserFetchTile(url: string): Promise<TileReply> {
	const res = await fetch(url, { credentials: 'omit', referrerPolicy: 'strict-origin-when-cross-origin', signal: AbortSignal.timeout(SAT_TILE_TIMEOUT_MS) });
	if (!res.ok) return { status: res.status, image: null };
	const blob = await res.blob();
	if (blob.size === 0) return { status: 204, image: null };
	if (typeof createImageBitmap === 'function') return { status: 200, image: await createImageBitmap(blob) };
	const img = new Image();
	img.decoding = 'async';
	const href = URL.createObjectURL(blob);
	try {
		img.src = href;
		await img.decode();
	} finally {
		URL.revokeObjectURL(href);
	}
	return { status: 200, image: img };
}
