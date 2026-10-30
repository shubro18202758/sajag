/**
 * The map chrome's shared state (chrome v2): what the LayerTree and the
 * legend show and the actions they send back to the canvas.
 *
 * The mounted GodsEyeCanvas (one per page: one WebGL context) attaches
 * itself as the controller and publishes its layer rows, the base-map
 * choice and the legend's state here on every stats refresh. A LayerTree
 * can therefore live inside the canvas (the Layers toolbar button's panel)
 * or in a page's dock (`onLayers`, SPEC §6.1 left dock) and read the same
 * rows; toggles go back through the controller, never around it.
 */

import type { LayerGroup } from '../../registry';

/** One LayerTree row. */
export interface LayerRow {
	id: string;
	label: string;
	group: LayerGroup;
	/** Objects drawn now (the layer's own count: decision units, coloured roads …). */
	count: number;
	/** The layer's hint (the row's tooltip; tests read it as the row's title). */
	hint: string;
	error: string | null;
	visible: boolean;
	/** Nothing to draw right now ("None now"). */
	empty: boolean;
	/** Its rows come from a simulated feed (the flow layer's compact provenance glyph). */
	simulated: boolean;
	/** Its rows come from the scenario emulator. */
	emulated: boolean;
	/** Stood down while a replay plays. */
	paused: boolean;
}

export type BasemapStyle = 'photoreal' | 'streets' | 'dark';

export interface MapChromeController {
	setLayer(id: string, on: boolean): void;
	setBasemap(style: BasemapStyle): void;
	toggleLegend(open?: boolean): void;
	/** chrome v3: a tool the V3 map page's own buttons drive (zoom ±1, north, follow, sensor <mode>, measure, 3d on|off, home: back to the city). */
	act?(tool: MapAct, arg?: unknown): void;
}

/** The tools chrome v3 drives through the canvas (the canvas implements them; the page only asks). */
export type MapAct = 'zoom' | 'north' | 'follow' | 'sensor' | 'measure' | '3d' | 'home';

/** What chrome v3's tool buttons show (the canvas publishes it while it is mounted with chrome="v3"). */
export interface MapToolState {
	heading: number;
	follow: { pressed: boolean; disabled: boolean; title: string };
	sensor: string;
	tool: string;
	/** The photoreal city's first tiles are in (3D shows the OSM night map until then). */
	photorealReady: boolean;
}

class MapChromeState {
	rows = $state<LayerRow[]>([]);
	basemap = $state<BasemapStyle>('dark');
	/** The photoreal base map: available on the ion key, else why not. */
	photoreal = $state<{ available: boolean; hint: string }>({ available: false, hint: '' });
	legendOpen = $state(false);
	lang = $state('en');
	/** A canvas is mounted and publishing. */
	attached = $state(false);
	/** chrome v3 only: the tool buttons' state (null under v2). */
	tools = $state<MapToolState | null>(null);
	#ctl: MapChromeController | null = null;

	/** The canvas attaches on mount; the returned function detaches it. */
	attach(ctl: MapChromeController): () => void {
		this.#ctl = ctl;
		this.attached = true;
		return () => {
			if (this.#ctl !== ctl) return;
			this.#ctl = null;
			this.attached = false;
			this.rows = [];
			this.legendOpen = false;
			this.tools = null;
		};
	}

	setLayer(id: string, on: boolean): void {
		this.#ctl?.setLayer(id, on);
	}

	setBasemap(style: BasemapStyle): void {
		this.#ctl?.setBasemap(style);
	}

	toggleLegend(open?: boolean): void {
		this.#ctl?.toggleLegend(open);
	}

	/** chrome v3: run a tool on the mounted canvas (nothing when none is mounted). */
	act(tool: MapAct, arg?: unknown): void {
		this.#ctl?.act?.(tool, arg);
	}
}

export const mapChrome = new MapChromeState();
