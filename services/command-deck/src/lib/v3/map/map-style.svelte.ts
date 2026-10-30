/**
 * The shared map style (V3-P4C) — what every MapThumb draws and which base map /map opens on. One store per page
 * view, read by MapThumb, MapStyleSwitch, LayersSheet and MapPage (and, through the patch in INTEGRATION.patch,
 * the header menu). The rules are in style-rules.ts and the quota in satellite.ts; this file only holds the state.
 *
 * Whether the deck has the Cesium ion key comes from the deck's own mode endpoint (GODS_EYE_MODE_API — the answer
 * the God's-eye canvas reads; code-read, the token is never printed): `ensure()` asks it once per page view (6 s
 * budget in the canvas, 4 s here), or `provide()` takes the answer the canvas already holds. The token goes straight
 * into the satellite source; this store keeps only whether there is one.
 *
 * Nothing here runs on the server (the state starts empty and fills from `ensure()`, called from effects), so the
 * server render and the first client render agree.
 */
import { GODS_EYE_MODE_API } from '$lib/ops/endpoints';
import { BASE_KEY, STYLE_KEY, parseBasePref, parseStylePref, resolveBase, resolveThumbStyle, type BasePref, type StylePref, type ThumbStyle } from './style-rules';
import { satellite } from './tiles';

const read = (key: string): string | null => {
	try {
		return localStorage.getItem(key);
	} catch {
		return null;
	}
};
const write = (key: string, value: string): void => {
	try {
		localStorage.setItem(key, value);
	} catch {
		// storage unavailable: this visit only
	}
};

class MapStyleState {
	/** The thumbnails' style as the officer chose it (null: never chosen — the default applies). */
	pref = $state<StylePref | null>(null);
	/** /map's base map as the officer chose it. */
	base = $state<BasePref | null>(null);
	/** Does the deck hold the ion key? null until it has answered. */
	keyed = $state<boolean | null>(null);
	/** Why satellite stood down this session (denied / quota / cap / unreachable), or null. */
	degraded = $state<string | null>(null);
	/**
	 * The imagery credit of the satellite picture last drawn (plain text; '' while none). A page that keeps its own credit line
	 * (Decide's legend) reads it and asks its thumb not to print one (MapThumb `creditInside={false}`).
	 */
	imagery = $state('');
	#loading: Promise<void> | null = null;

	/** What a thumb draws now; null while the key question is open. */
	get effective(): ThumbStyle | null {
		return resolveThumbStyle({ pref: this.pref, keyed: this.keyed, degraded: this.degraded !== null });
	}

	/** The style the switch shows pressed (the choice, or the default when none was made). */
	get want(): StylePref {
		return this.pref ?? 'satellite';
	}

	/** The base map /map opens on, given whether the photoreal city can be had. */
	baseFor(can3d: boolean): BasePref {
		return resolveBase({ pref: this.base, can3d });
	}

	#start(): void {
		this.pref = parseStylePref(read(STYLE_KEY));
		this.base = parseBasePref(read(BASE_KEY));
		satellite.onDegrade = (why) => (this.degraded = why);
		this.degraded = satellite.degraded;
	}

	/** The key answer the canvas already holds (MapPage after godsEye.pollImageryMode): no second request. */
	provide(token: string | null | undefined): void {
		if (!this.#loading) {
			this.#start();
			this.#loading = Promise.resolve();
		}
		satellite.configure(token ?? null);
		this.keyed = !!token;
	}

	/** Ask the deck once per page view. Safe to call from every thumb. */
	ensure(): Promise<void> {
		if (!this.#loading) {
			this.#start();
			this.#loading = (async () => {
				let token: string | null = null;
				try {
					const res = await fetch(GODS_EYE_MODE_API, { signal: AbortSignal.timeout(4000), cache: 'no-store' });
					const body = res.ok ? ((await res.json()) as { mode?: unknown; token?: unknown }) : null;
					token = body && body.mode === 'ion-photoreal' && typeof body.token === 'string' && body.token ? body.token : null;
				} catch {
					token = null;
				}
				satellite.configure(token);
				this.keyed = token !== null;
			})();
		}
		return this.#loading;
	}

	setPref(p: StylePref): void {
		this.pref = p;
		write(STYLE_KEY, p);
	}

	setBase(b: BasePref): void {
		this.base = b;
		write(BASE_KEY, b);
	}
}

export const mapStyle = new MapStyleState();
