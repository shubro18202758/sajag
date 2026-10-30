<script lang="ts">
	/**
	 * MapThumb (V3-SPEC §4.6) — the real map at the place, with only the one thing that matters drawn on
	 * it. Poster art, made honest: raster tiles at most `maxTiles` of them from one shared LRU
	 * (map/tiles.ts) and an SVG overlay projected with the same Web Mercator math (map/mercator.ts). NO Cesium
	 * viewer per card.
	 *
	 * Two styles (V3-P4C, the shared preference in map-style.svelte.ts):
	 *   'satellite'  NATURAL colours — Cesium ion's Bing aerial imagery, drawn ungraded and credited (the imagery the
	 *                God's-eye canvas shows under its 3D city). The default whenever the deck has the ion key.
	 *                Quota-safe by construction (satellite.ts): ≤ 6 tiles a card, ≤ 4 in flight, a session cap, and a
	 *                silent fall back to 'night' on 401 / 403 / 429.
	 *   'night'      the keyless OpenStreetMap raster graded to the Sajag night palette in the browser (tiles.ts).
	 * Every caller inherits the style (no prop needed); `style` forces one (the Layers sheet's base-map pictures).
	 *
	 * Lazy: nothing loads until the thumb is within 300 px of the viewport (IntersectionObserver), unless
	 * `eager` (the hero). Until the tiles arrive — or if they never do (offline) — the night placeholder
	 * shows, with the deck's own road network drawn on it when the page passed `roads` (honest and keyless).
	 *
	 * Overlays stay readable on imagery of any brightness: every line has a dark casing, every pin a dark ring, every
	 * label a dark halo, and on satellite the thin neutral lines are drawn stronger (see the styles).
	 *
	 * Accessibility: the map is one `role="img"` with `alt`; the overlay is decorative. The imagery credit is a real
	 * text line (satellite) or the OSM link (night, `credit`); every page that shows night thumbs also credits OSM.
	 */
	import { untrack, type Snippet } from 'svelte';
	import Glyph from '../Glyph.svelte';
	import { glyphPath } from '../icons';
	import { bboxOf, frame, framedBBox, toBox, type BBox, type Framing, type LonLat } from './mercator';
	import { overlayPoints, type LineStyle, type ThumbOverlay, type ThumbPoint } from './overlay';
	import { gradedTile, satellite, satelliteTile, type Grade } from './tiles';
	import { mapStyle } from './map-style.svelte';
	import { SAT_CARD_TILES, SAT_HERO_TILES } from './satellite';
	import type { ThumbStyle } from './style-rules';

	/** How long a thumb waits for its first satellite tiles before laying the night tiles underneath. */
	const SAT_SLOW_MS = 2500;

	interface Props {
		overlay?: ThumbOverlay | null;
		/** Frame this bbox; else the overlay's points; a single point is framed at `zoom`. */
		bbox?: BBox | null;
		zoom?: number;
		/** Where the subject sits in the box (0..1; the hero puts it right of its copy). */
		focus?: readonly [number, number];
		maxTiles?: number;
		/** The marker radius in px (thumbs 13, the hero 17). */
		markerR?: number;
		alt: string;
		/** Force a style; else the shared preference (satellite when the deck has the ion key). */
		style?: ThumbStyle;
		grade?: Grade;
		eager?: boolean;
		/** Show the © OpenStreetMap contributors link in the corner. */
		credit?: boolean;
		creditLabel?: string;
		/** Print the satellite imagery credit on the thumb (default). A page with its own credit line sets false and prints `mapStyle.imagery` there. */
		creditInside?: boolean;
		/** Draw the points' labels (the hero; card thumbs stay quiet). */
		labels?: boolean;
		/** Frame every overlay coordinate, or only the points (the hero: the subject, with its route running on). */
		frameOn?: 'all' | 'points';
		/** The deck's own road lines, drawn only while no tile could load. */
		roads?: readonly (readonly LonLat[])[] | null;
		class?: string;
		children?: Snippet;
	}

	let {
		overlay = null,
		bbox = null,
		zoom = 15,
		focus = [0.5, 0.5],
		maxTiles = 6,
		markerR = 13,
		alt,
		style = undefined,
		grade = 'night',
		eager = false,
		credit = false,
		creditLabel = '© OpenStreetMap contributors',
		creditInside = true,
		roads = null,
		frameOn = 'all',
		labels = false,
		class: cls = '',
		children,
	}: Props = $props();

	let box = $state<HTMLDivElement | null>(null);
	let canvas = $state<HTMLCanvasElement | null>(null);
	let w = $state(0);
	let h = $state(0);
	let seen = $state(false);
	let status = $state<'idle' | 'loading' | 'ready' | 'offline'>('idle');
	/** What is drawn now (the satellite may fall back to night tiles for one draw when none arrived). */
	let shown = $state<ThumbStyle | null>(null);
	/** The imagery credit of what is drawn (satellite only; plain text): the full line and the compact one. */
	let imagery = $state({ full: '', short: '' });
	/** A wide thumb carries the full credit line; a card the compact one (its tooltip always the full line). */
	const creditText = $derived(w >= 520 ? imagery.full : imagery.short);
	/** A swatch too small to hold a credit line (the Layers sheet's pictures) carries it in its tooltip; the map beside it shows the credit. */
	const creditRoom = $derived(w >= 200 && h >= 80);

	/** The style this thumb draws: forced, or the shared preference (null while the deck's key answer is open). */
	const eff = $derived<ThumbStyle | null>(style ?? mapStyle.effective);
	/** Satellite frames to fewer tiles: a card 6, an eager hero / stage 40 (satellite.ts documents the quota). */
	const tileCap = $derived(eff === 'satellite' ? Math.min(maxTiles, eager ? SAT_HERO_TILES : SAT_CARD_TILES) : maxTiles);

	const pts = $derived(
		frameOn === 'points' && overlay?.points?.length ? [...overlay.points.map((p) => p.at), ...(overlay.rings ?? []).map((r) => r.at)] : overlayPoints(overlay),
	);
	const target = $derived.by((): { bbox: BBox | null; center: LonLat | null } => {
		if (bbox) return { bbox, center: null };
		const b = bboxOf(pts);
		if (!b) return { bbox: null, center: null };
		// one point (or a tight cluster): centre it at the given zoom
		if (Math.abs(b[2] - b[0]) < 0.0015 && Math.abs(b[3] - b[1]) < 0.0015) return { bbox: null, center: [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] };
		return { bbox: b, center: null };
	});
	const f = $derived<Framing | null>(
		w > 0 && h > 0 && (target.bbox || target.center)
			? frame({ bbox: target.bbox, center: target.center, zoom, focus, maxTiles: tileCap, pad: Math.max(28, markerR * 2.4) }, w, h)
			: null,
	);

	$effect(() => {
		if (eager || seen || !box) return;
		if (typeof IntersectionObserver === 'undefined') {
			seen = true;
			return;
		}
		const io = new IntersectionObserver(
			(entries) => {
				if (entries.some((e) => e.isIntersecting)) {
					seen = true;
					io.disconnect();
				}
			},
			{ rootMargin: '300px 600px' },
		);
		io.observe(box);
		return () => io.disconnect();
	});

	/** Ask the deck (once per page view, shared) whether it has the ion key, when this thumb follows the preference. */
	$effect(() => {
		if (style === undefined && (eager || seen)) untrack(() => void mapStyle.ensure());
	});

	/** The framing last drawn: a poll that hands an equal overlay never redraws (no flicker). */
	let drawn = '';
	$effect(() => {
		const fr = f;
		const c = canvas;
		const st = eff;
		if (!fr || !c || !(eager || seen) || st === null) return;
		const key = `${st}|${grade}|${fr.z}|${Math.round(fr.x0)}|${Math.round(fr.y0)}|${w}|${h}`;
		if (key === drawn) return;
		drawn = key;
		const dpr = Math.min(2, typeof devicePixelRatio === 'number' ? devicePixelRatio : 1);
		c.width = Math.round(w * dpr);
		c.height = Math.round(h * dpr);
		const g = c.getContext('2d');
		if (!g) return;
		g.setTransform(dpr, 0, 0, dpr, 0, 0);
		g.imageSmoothingQuality = 'high';
		g.clearRect(0, 0, w, h);
		if (status !== 'ready') status = 'loading';
		const bbox = framedBBox(fr, w, h);
		/** `under`: draw beneath what is already there (the night tiles laid under a slow satellite picture). */
		const paint = async (as: ThumbStyle, under = false): Promise<number> => {
			let ok = 0;
			await Promise.all(
				fr.tiles.map((t) =>
					(as === 'satellite' ? satelliteTile(t.z, t.x, t.y, eager ? 'hero' : 'card') : gradedTile(t.z, t.x, t.y, grade, under)).then((tile) => {
						if (drawn !== key || !tile) return;
						ok++;
						g.globalCompositeOperation = under ? 'destination-over' : 'source-over';
						g.drawImage(tile, t.dx, t.dy, 256, 256);
						g.globalCompositeOperation = 'source-over';
					}),
				),
			);
			return ok;
		};
		void (async () => {
			let used = st;
			// a slow satellite source (no answer within SAT_SLOW_MS: an unreachable ion, a cold setup) never leaves the place
			// black: the night tiles go down UNDER the canvas at once and the satellite tiles land on top as they come
			let under = 0;
			let underRun: Promise<number> | null = null;
			const slow =
				st === 'satellite'
					? setTimeout(() => {
							if (drawn !== key) return;
							underRun = paint('night', true).then((n) => {
								under = n;
								if (drawn === key && n > 0 && status !== 'ready') status = 'ready';
								return n;
							});
						}, SAT_SLOW_MS)
					: null;
			let ok = await paint(st);
			if (slow) clearTimeout(slow);
			// no satellite tile came (a refusal, the cap, or no network for it): the night tiles for this draw
			if (ok === 0 && st === 'satellite' && drawn === key) {
				used = 'night';
				ok = underRun ? await underRun : await paint('night');
			}
			if (drawn !== key) return;
			shown = ok > 0 ? used : null;
			imagery = ok > 0 && used === 'satellite' ? satellite.credit(fr.z, bbox) : { full: '', short: '' };
			// satellite drew only part of the frame over the night tiles: the picture is both, and so is its credit
			if (used === 'satellite' && under > 0 && ok < fr.tiles.length && imagery.full) imagery = { full: `${imagery.full} · © OpenStreetMap contributors`, short: `${imagery.short} · © OpenStreetMap contributors` };
			status = ok > 0 ? 'ready' : 'offline';
			if (imagery.full) mapStyle.imagery = imagery.full;
		})();
	});

	const path = (coords: readonly LonLat[]) => {
		if (!f || coords.length < 2) return '';
		return coords.map((p, i) => {
			const [x, y] = toBox(p, f);
			return `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`;
		}).join(' ');
	};

	const WIDTH: Record<LineStyle, number> = { route: 6, 'route-done': 4.5, trail: 3, green: 5, road: 8, water: 8, dashed: 5, flood: 8 };

	function at(p: ThumbPoint): [number, number] {
		return f ? toBox(p.at, f) : [0, 0];
	}

	/** Metres per pixel at a latitude for the framed zoom. */
	const mpp = (lat: number) => (f ? (156543.03392 * Math.cos((lat * Math.PI) / 180)) / 2 ** f.z : 1);
</script>

<div class={['thumb', cls]} title={shown === 'satellite' && creditText && !creditRoom ? imagery.full : undefined} bind:this={box} bind:clientWidth={w} bind:clientHeight={h} data-v3="map-thumb" data-state={status} data-style={shown ?? eff ?? ''} data-zoom={f?.z ?? ''} data-tiles={f?.tiles.length ?? 0}>
	<div class="map" role="img" aria-label={alt}>
		<canvas bind:this={canvas} class={['tiles', status === 'ready' && 'shown']} aria-hidden="true"></canvas>
		{#if f}
			<svg class="ov" viewBox="0 0 {w} {h}" aria-hidden="true" focusable="false">
				{#if roads && status === 'offline'}
					{#each roads as r, i (i)}
						<path class="net" d={path(r)} />
					{/each}
				{/if}
				{#each overlay?.rings ?? [] as r, i (i)}
					{@const [x, y] = toBox(r.at, f)}
					{@const rr = Math.max(18, r.radiusM / mpp(r.at[1]))}
					<circle class="ring-case" cx={x} cy={y} r={rr} />
					<circle class="ring" cx={x} cy={y} r={rr} />
				{/each}
				{#each overlay?.lines ?? [] as l, i (i)}
					{@const d = path(l.coords)}
					{#if d}
						<path class="case" d={d} stroke-width={WIDTH[l.style] + 5} />
						<path class={['ln', `ln-${l.style}`]} d={d} stroke-width={WIDTH[l.style]} />
					{/if}
				{/each}
				{#each overlay?.points ?? [] as p, i (i)}
					{@const [x, y] = at(p)}
					{#if p.small}
						<circle class="case-fill" cx={x} cy={y} r="6.5" />
						<circle class="read" cx={x} cy={y} r="4" />
					{:else}
						{@const r = markerR}
						{#if p.halo}
							<circle class={['halo', `t-${p.tone ?? 'brand'}`]} cx={x} cy={y} r={r * 2.4} opacity="0.16" />
							<circle class={['halo', `t-${p.tone ?? 'brand'}`]} cx={x} cy={y} r={r * 1.6} opacity="0.18" />
						{/if}
						<circle class="case-fill" cx={x} cy={y} r={r + 3} />
						<circle class={['mk', `mk-${p.tone ?? 'neutral'}`]} cx={x} cy={y} {r} />
						<g transform="translate({x - r * 0.72} {y - r * 0.72}) scale({(r * 1.44) / 24})">
							<path class="mk-glyph" d={glyphPath(p.glyph ?? 'pin')} />
						</g>
						{#if p.decide}
							<circle class="decide" cx={x + r * 0.78} cy={y - r * 0.78} r={Math.max(5, r * 0.4)} />
						{/if}
						{#if labels && p.label}
							{@const est = Math.max(p.label.length, (p.sub ?? '').length) * 8}
							{@const left = p.labelSide === 'l' || (x + r + 9 + est > w - 6 && x - r - 9 - est >= 6)}
							<text class="lbl" x={left ? x - r - 9 : x + r + 9} y={y + (p.sub ? -1 : 5)} text-anchor={left ? 'end' : 'start'}>{p.label}</text>
							{#if p.sub}<text class="lbl dim" x={left ? x - r - 9 : x + r + 9} y={y + 15} text-anchor={left ? 'end' : 'start'}>{p.sub}</text>{/if}
						{/if}
					{/if}
				{/each}
			</svg>
		{/if}
	</div>
	{@render children?.()}
	{#if shown === 'satellite' && creditText && creditRoom && creditInside}
		<span class="credit sat" data-testid="thumb-imagery-credit" title={imagery.full}>{creditText}</span>
	{:else if credit}
		<a class="credit" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">{creditLabel}</a>
	{/if}
	{#if status === 'offline' && !roads}
		<span class="off" aria-hidden="true"><Glyph name="map" size={22} /></span>
	{/if}
</div>

<style>
	.thumb {
		position: relative;
		overflow: hidden;
		background: var(--v3-map-bg);
	}

	.map {
		position: absolute;
		inset: 0;
	}

	.tiles {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		opacity: 0;
		transition: opacity var(--v3-dur-3) var(--v3-ease);
	}

	.tiles.shown {
		opacity: 1;
	}

	.ov {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		overflow: visible;
	}

	.net {
		fill: none;
		stroke: var(--v3-line-3);
		stroke-width: 2;
		stroke-linecap: round;
	}

	/* a dark casing under the dashed ring, so it reads on the brightest roof and the darkest park */
	.ring-case {
		fill: none;
		stroke: var(--v3-glass);
		stroke-width: 6.5;
		opacity: 0.9;
	}

	.ring {
		fill: var(--v3-t2);
		fill-opacity: 0.08;
		stroke: var(--v3-t2);
		stroke-width: 2.5;
		stroke-dasharray: 10 8;
	}

	.case {
		fill: none;
		stroke: var(--v3-glass);
		stroke-linecap: round;
		stroke-linejoin: round;
		opacity: 0.9;
	}

	.ln {
		fill: none;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.ln-route {
		stroke: var(--v3-route);
	}

	.ln-route-done {
		stroke: var(--v3-route-done);
	}

	.ln-trail {
		stroke: var(--v3-alert);
		stroke-dasharray: 2 8;
	}

	.ln-green {
		stroke: var(--v3-ok);
		stroke-dasharray: 12 8;
	}

	.ln-road {
		stroke: var(--v3-t1);
		stroke-opacity: 0.55;
	}

	.ln-water {
		stroke: var(--v3-brand);
		stroke-opacity: 0.75;
	}

	/* a road at waterlogging risk (the hydro nowcast): the map's water-hazard hue */
	.ln-flood {
		stroke: var(--v-map-water);
	}

	.ln-dashed {
		stroke: var(--v3-t1);
		stroke-opacity: 0.5;
		stroke-dasharray: 10 7;
	}

	.case-fill {
		fill: var(--v3-glass);
	}

	.read {
		fill: var(--v3-t1);
	}

	.halo.t-brand {
		fill: var(--v3-brand);
	}

	.halo.t-route {
		fill: var(--v3-route);
	}

	.halo.t-alert {
		fill: var(--v3-alert);
	}

	.halo.t-neutral {
		fill: var(--v3-t1);
	}

	.mk {
		fill: var(--v3-t1);
	}

	.mk-route {
		fill: var(--v3-route);
	}

	.mk-brand {
		fill: var(--v3-brand-text);
	}

	.mk-alert {
		fill: var(--v3-t1);
		stroke: var(--v3-alert);
		stroke-width: 3.5;
	}

	.mk-glyph {
		fill: none;
		stroke: var(--v3-primary-ink);
		stroke-width: 2.2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.decide {
		fill: var(--v3-decide);
		stroke: var(--v3-primary-ink);
		stroke-width: 2.5;
	}

	.lbl {
		fill: var(--v3-t1);
		font-family: var(--v-font-ui);
		font-size: 14px;
		font-weight: 600;
		paint-order: stroke;
		stroke: var(--v3-scrim-mid);
		stroke-width: 4px;
		stroke-linejoin: round;
	}

	.lbl.dim {
		fill: var(--v3-t2);
		font-size: 12px;
		font-weight: 550;
	}

	.credit {
		position: absolute;
		right: 8px;
		bottom: 6px;
		z-index: 3;
		padding: 1px 6px;
		border-radius: 6px;
		background: var(--v3-glass);
		color: var(--v3-t2);
		font-size: 11px;
		line-height: 16px;
		text-decoration: none;
	}

	/* natural-colour imagery: its copyright line is text on the glass, bottom right, never over the subject */
	.credit.sat {
		max-width: calc(100% - 16px);
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
		font-size: 10px;
		line-height: 14px;
		pointer-events: none;
	}

	/* on imagery the neutral lines and labels are drawn stronger: a bright roof or a dark park never swallows them */
	.thumb[data-style='satellite'] .ln-road,
	.thumb[data-style='satellite'] .ln-dashed {
		stroke-opacity: 0.95;
	}

	.thumb[data-style='satellite'] .ln-water {
		stroke-opacity: 1;
	}

	/* the casings go (almost) opaque: the red of an alert line keeps ≥ 3:1 against its edge on a white roof */
	.thumb[data-style='satellite'] .case,
	.thumb[data-style='satellite'] .ring-case {
		stroke: var(--v3-scrim);
		opacity: 1;
	}

	.thumb[data-style='satellite'] .case-fill {
		fill: var(--v3-scrim);
	}

	.thumb[data-style='satellite'] .lbl {
		stroke: var(--v3-glass);
		stroke-width: 5px;
	}

	.credit:hover {
		color: var(--v3-t1);
	}

	.credit:focus-visible {
		outline: 2px solid var(--v3-brand);
	}

	.off {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		color: var(--v3-t3);
	}

	@media (prefers-reduced-motion: reduce) {
		.tiles {
			transition: none;
		}
	}
</style>
