<script lang="ts">
	/**
	 * GodsEyeCanvas — the Cesium God's-eye canvas.
	 *
	 * Keyless by default (re-graded dark OSM raster + ellipsoid terrain + our
	 * own entities — zero calls to cesium.com/ion); env-keyed ion upgrade via
	 * the server-side mode endpoint, built from the async ion factories and
	 * falling back to keyless when the token or ion fails. Sensor modes:
	 * COMMAND (the raw render — the default, because a luminance-mapped scene
	 * erases every colour the layers carry) and the opt-in FLIR looks
	 * (White-Hot / Black-Hot / Ironbow). A share-link camera URL, and the
	 * layer registry (gods-eye-view MIT pattern — see registry.ts).
	 *
	 * HUD modes: 'full' (SAJAG CITY COMMAND /gods-eye — EXIT chip + Esc back to
	 * the wall; the page hosts the entity dossier, the vitals and the fusion
	 * rail around this canvas) · 'mini' (compact chip row) · 'wall' (the
	 * cockpit '/' and the /ops situation wall):
	 *   - AUTO-ORBIT (wall only): 30 s after the last interaction the camera
	 *     orbits a ground pivot — the locked subject, else the screen-centre
	 *     ground point inside the city, else the city centre — inside an
	 *     east-north-up frame at that pivot (rotateRight about the LOCAL up
	 *     axis). Any interaction, flight, tour or follow hands the camera back
	 *     to the world frame, and an idle camera that leaves the city bbox
	 *     flies home. (The first orbit rotated about Earth's polar axis and
	 *     carried the city off-screen in ~40 s.)
	 *   - SUBJECT FOLLOW (/ops): selecting a live event flies to its spine
	 *     once and locks; the follow tracks the selection id only, so board
	 *     polls never re-fly, and RELEASE sticks (across views too — a
	 *     released subject is not re-locked until the selection moves).
	 *   - FOCUS BUS (focus.svelte.ts): board surfaces request a fly + lock;
	 *     LOCKED is shown only when the flight lands (a drag or wheel during
	 *     the flight cancels it), and a canvas serves only requests made
	 *     after it mounted — the next view never replays the last request.
	 *   - SELECTION (entities/selection.svelte.ts): every pick maps through its
	 *     layer to a C-C URN and selects that entity (event URNs also select
	 *     the event on the board); the selected entity wears a halo and its
	 *     primitives stay highlighted. A fly request (fusion-rail row, dossier
	 *     chip, tour) flies to the entity's fused position — the registry's,
	 *     else its dossier's — and reports landed / no-position.
	 *   - PICKING: on the wall views the layer's description opens a pick
	 *     card; on City Command the dossier replaces it (the pick text rides
	 *     into the dossier's MAP line). Hover highlights the entity.
	 *   - PURSUIT OVERLAY (head-first trace + comet + choke cascade + marching
	 *     future arc — pursuit.ts), redrawn only when the plan changes, with
	 *     the plan's stale / likely-passed / direction-of-travel facts.
	 *   - GUIDED TOUR: camera choreography over targets computed from the
	 *     LIVE city picture (posture, the pursuit, the busiest camera, the
	 *     units, the planned convoy, the signal network, the e-challan pins),
	 *     skipping what is empty; on City Command each stop opens its dossier.
	 *   - REPLAY (hud/replay.svelte.ts + replay.ts): an emulator tape on the
	 *     viewer clock — EVERY live layer stands down while it plays (a 'LIVE
	 *     paused' chip says so), so the replayed frames are what is on screen;
	 *     every replayed primitive is badged EMULATED.
	 *   - AGENTIC GOD'S-EYE (canvas-bus.svelte.ts, contract C-D2): the agent's
	 *     canvas directives queue as 'AI suggests: <verb> <label> [Apply]
	 *     [Dismiss]' chips. Apply runs the move LOCALLY (fly / select / halo /
	 *     a TTL note / sensor / layer) and acknowledges it to the brain once;
	 *     nothing is ever auto-applied. ⌘K / Ctrl+K opens the command palette
	 *     (hud full + wall). An 'Open on map' from the agent console is
	 *     served when City Command mounts.
	 *   - PICKING PRIORITY: a click drill-picks up to 8 primitives and takes
	 *     the operator's likely target by layer (unit > camera > vehicle mark
	 *     > signal > pursuit > event > segment); the halo and non-entity
	 *     picks (3D tile features of the photoreal layer, C-L) never win.
	 *     Draped lines share the road's pixels, so a pursuit LINE lying on
	 *     an event's spine ranks just after the event (its markers keep
	 *     their rank).
	 *   - 3D CITY (layers/draping.ts): on the ion key the overlays stand ON
	 *     Google's photoreal mesh — the selection halo is a draped ring, an
	 *     agent note a clamped label; City Command's home is a presentation-grade
	 *     oblique from the city pack (HOME_VIEW_3D: for Mumbai, from off Haji
	 *     Ali north along the Worli seaface to the Bandra–Worli Sea Link; the
	 *     live action framed at ACTION_VIEW_3D); the chip names what is on
	 *     screen (basemap.ts imageryChip — 'Photoreal 3D · Google') and the
	 *     data credits ride a glass plate in the region the host's panels
	 *     leave clear (City Command's fusion rail would cover them).
	 *
	 * Ethics rail (C6): every plate this canvas prints is masked unless a
	 * named duty officer is on console (plates.ts) — at the source (layer
	 * descriptions, tour labels, focus notes) AND again at every text sink
	 * (pick card, LOCKED chip, flash line, tour label, test snapshot), so a
	 * layer that forgets to mask a free-text prop still never shows a plate.
	 *
	 * Degradation contract: if WebGL or the prebuilt bundle is unavailable
	 * this panel degrades ALONE. If OSM tiles cannot load, the canvas switches
	 * to 'Offline schematic mode' (entities over a dark globe, labelled).
	 *
	 * CHROME (SPEC §5.3, plan X11): `chrome="legacy"` (the default) is the
	 * chip row above, unchanged — every page keeps it until its owner opts
	 * in. `chrome="v2"` is the redesign's map chrome: the toolbar (Select,
	 * Select within shape, Search around, Measure · Layers, Legend · Follow,
	 * Live/Replay, Guided tour, Thermal-style view, Exit map mode), zoom and
	 * north at the bottom right above Cesium's credits, the readout at the
	 * bottom left, the LayerTree, the legend, MapProposals and the replay
	 * banner (hud/map/*); and the symbology in which colour means only state
	 * (hud/map/symbols.ts): neutral glyph discs, clusters under 22 px with a
	 * count chip (a click spiderfies them), the offset vehicle pin, one
	 * decision dot per object, greedy labels (hud/map/labels.ts), the
	 * selection's hierarchy and the time window's fading with protected
	 * objects (hud/map/view.ts). The v2 pass (decorate) restyles markers in
	 * place on camera-move end and on data change, never per frame. The
	 * omnibar mount (CommandPalette, hud 'full' | 'wall') is the same under
	 * both chromes, and the __GODS_EYE__ contract is unchanged.
	 */
	import { onMount, onDestroy, untrack } from 'svelte';
	import { replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import { ops } from '$lib/ops/store.svelte';
	import { CITY_BBOX, CITY_CAMERAS, cityName } from '$lib/city';
	import { t } from '$lib/i18n/strings';
	import type { InterceptionPlan } from '$lib/ops/types';
	import { godsEye } from './store.svelte';
	import { focus } from './focus.svelte';
	import { GODS_EYE_LAYERS, GODS_EYE_LAYER_IDS } from './layers';
	import { eventCentroid, eventIdFromPick } from './layers/corridor-events';
	import { unitPhase } from './layers/agency';
	import {
		ION_READY_TIMEOUT_MS,
		OSM_CREDIT,
		createIonBasemap,
		createKeylessBasemap,
		imageryChip,
		imageryModeOf,
		osmScreenCredit,
		photorealReady,
		type Basemap,
	} from './layers/basemap';
	import { DRAPE_Z, clampedLabel, drapedPolyline, ground, groundPath, ringCoords } from './layers/draping';
	import type { PursuitOverlay } from './pursuit';
	import type { ReplayOverlay } from './replay';
	import { fetchVehicleTrace } from './data';
	import { FLIR_SHADER } from './shaders/flir';
	import { buildShareUrl, parseShareHash, type ShareViewState } from './share-link';
	import { cssColor, cssVar } from './theme';
	import { displayPlate, displayText } from './plates';
	import { parseUrn } from './city-api';
	import { ACTOR_ICON, kindIcon } from '$lib/design/icons';
	import { cityRegistry } from './entities/registry.svelte';
	import { selection } from './entities/selection.svelte';
	import { dossier } from './entities/dossier.svelte';
	import { replay } from './hud/replay.svelte';
	import { cityVitals } from './hud/vitals.svelte';
	import CommandPalette from './hud/CommandPalette.svelte';
	import { canvasBus } from './canvas-bus.svelte';
	import type { CanvasDirective, DirectiveWorld } from './directives';
	import '$lib/i18n/packs.agent';
	import '$lib/i18n/packs.map';
	import type { GodsEyeLayerInstance, LayerCoverageStats } from './registry';
	import { canvasFont } from './theme';
	import { DARK_REGRADE, STREETS_GRADE, applyGrade, createOsmImageryLayer } from './layers/basemap';
	import { stolenVehicles } from './layers/enforcement';
	import { cityDecisionUrns, markShowsDecision } from './layers/osint';
	import { MAP_OPACITY, emptyView, kindShown, kindsSignature, markerStyle, type MapView } from './hud/map/view';
	import { CLUSTER_RADIUS_PX, clusterAround, spiderOffsets } from './hud/map/cluster';
	import { discBox, placeLabels, type Box, type LabelItem } from './hud/map/labels';
	import {
		LABEL,
		MARKER,
		TRACK_ARROW,
		clearMapImages,
		ensureMapFonts,
		imageBillboard,
		imageFor,
		labelImage,
		labelText,
		mapInk,
		markerBillboard,
		markerMeta,
		tagMarker,
		trackArrows,
		trackMeta,
		type MapImage,
		type MarkerMeta,
		type TrackArrow,
	} from './hud/map/symbols';
	import { mapChrome, type BasemapStyle, type LayerRow, type MapAct } from './hud/map/map-state.svelte';
	import MapToolbar, { type MapTool, type ShapeMode } from './hud/map/MapToolbar.svelte';
	// the Layers and Legend panels are closed at first paint: they load on first open (V3-P4, the FIX-E-PERF2 pattern)
	const loadLayerTree = () => import('./hud/map/LayerTree.svelte');
	const loadLegend = () => import('./hud/map/MapLegend.svelte');
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';
	import ReplayBanner from './hud/map/ReplayBanner.svelte';
	import MapNav from './hud/map/MapNav.svelte';
	import MapReadout from './hud/map/MapReadout.svelte';
	import { shareHashExtras } from './share-link';

	type SensorMode = GodsEyeSensorMode;

	const NO_URNS: ReadonlySet<string> = new Set();
	/** chrome v3's night grade of the OSM raster (V3-SPEC §4.6: the map is ground, the objects are the figure). */
	const V3_NIGHT = { brightness: 0.3, contrast: 1.3, saturation: 0.32, gamma: 1.0 } as const;

	let {
		hud = 'full',
		onexit,
		pickCard = hud !== 'full',
		clearInsets = null,
		chrome: chromeProp = 'legacy',
		defaultLayers = null,
		timeWindow = null,
		protected: protectedUrns = NO_URNS,
		kindFilter = null,
		selectionItems = null,
		idleOrbit = false,
		onLayers,
		onTimeline,
		onlasso,
	}: {
		hud?: 'full' | 'mini' | 'wall';
		/** 'full' only: the EXIT chip and Esc (no tour running) call this. */
		onexit?: () => void;
		/**
		 * Show the canvas's own pick card. City Command ('full') hosts the
		 * entity dossier instead, so a pick there only selects.
		 */
		pickCard?: boolean;
		/**
		 * CSS px of the canvas the host's glass panels cover (City Command:
		 * vitals left, dossier right, fusion rail bottom). Every camera flight
		 * then lands its subject in the middle of the CLEAR region instead of
		 * the canvas centre, so a selected entity never lands under a panel.
		 */
		clearInsets?: { left: number; right: number; top: number; bottom: number } | null;
		/**
		 * 'legacy' (default): today's chips, exactly as before. 'v2': the
		 * redesign's map chrome and symbology (SPEC §5.3). 'v3': the v2
		 * symbology and tools with NO canvas-drawn toolbar, layer panel,
		 * legend, navigation or readout — the V3 map page (/map) draws its own
		 * around the canvas and drives the tools through mapChrome.act
		 * (map-state.svelte.ts). Read at mount.
		 */
		chrome?: 'legacy' | 'v2' | 'v3';
		/**
		 * The layers that start on when no share link names them (null: every
		 * layer's own defaultOn). Read at mount. The V3 map's clean default.
		 */
		defaultLayers?: readonly string[] | null;
		/** v2: the time window [from, to] (epoch ms); null when live. */
		timeWindow?: readonly [number, number] | null;
		/** v2: objects that never fade or dim (SPEC §7.3, computed by the page). */
		protected?: ReadonlySet<string>;
		/** v2: the kinds shown (null: every kind). */
		kindFilter?: ReadonlySet<string> | null;
		/** v2: the multi-selection (the primary is selection.current). */
		selectionItems?: readonly string[] | null;
		/** v2: orbit after 30 s idle, only while nothing is selected. */
		idleOrbit?: boolean;
		/** v2: the Layers button opens the page's own layer dock instead of the canvas's panel. */
		onLayers?: () => void;
		/** v2: the Live/Replay indicator opens the page's timeline. */
		onTimeline?: () => void;
		/** v2: a shape or Search around selected these URNs (the page calls selection.selectMany). */
		onlasso?: (urns: string[]) => void;
	} = $props();

	/** The page's chrome (read at mount): v3 draws with the v2 symbology; its tools live on the page. */
	const v3 = untrack(() => chromeProp) === 'v3';
	const chrome: 'legacy' | 'v2' = v3 ? 'v2' : untrack(() => chromeProp) === 'v2' ? 'v2' : 'legacy';

	let container: HTMLDivElement | null = $state(null);
	/** The HUD chip row — measured for the clear region (it wraps when a host panel narrows it). */
	let hudRowEl: HTMLDivElement | null = $state(null);

	let phase = $state<'loading' | 'ready' | 'unavailable'>('loading');
	let unavailableReason = $state<string | null>(null);
	let offlineDetected = $state(false);
	/** COMMAND (raw) by default on every route; FLIR looks are opt-in. */
	let sensorMode = $state<SensorMode>('raw');
	let activeLayers = $state<Set<string>>(new Set(untrack(() => defaultLayers) ?? GODS_EYE_LAYERS.map((l) => l.id)));
	let stats = $state<Record<string, LayerCoverageStats>>({});
	let picked = $state<{
		id: string;
		layer: string;
		label: string;
		text: string;
		eventId: string | null;
		/** The C-C entity the pick selected (null for preview fixtures / replay). */
		urn: string | null;
	} | null>(null);
	let shareFlash = $state<string | null>(null);
	let tourIndex = $state<number | null>(null);
	let tourTotal = $state(0);
	let tourLabel = $state<string>('');
	let legendOpen = $state(false);
	/** Reactive mirror of the pursuit overlay's entity count (HUD chip). */
	let pursuitCount = $state(0);
	/** Basemap actually rendering (the ion upgrade can fall back to keyless). */
	let basemapId = $state<'osm-keyless' | 'ion-photoreal'>('osm-keyless');
	let basemapNote = $state<string | null>(null);
	/** 1 Hz wall clock — the AMA chip age ticks between band polls. */
	let nowMs = $state(Date.now());

	// chrome v2: the map chrome's tools and panels (SPEC §5.3)
	let tool = $state<MapTool>('select');
	let shapeMode = $state<ShapeMode>('select');
	let layersOpen = $state(false);
	let followUrn = $state<string | null>(null);
	let basemapStyle = $state<BasemapStyle>('dark');
	let cursorAt = $state<{ lon: number; lat: number } | null>(null);
	let scaleBar = $state<{ px: number; label: string } | null>(null);
	let cameraHeadingDeg = $state(0);
	let hoverList = $state<{ x: number; y: number; title: string; items: string[] } | null>(null);
	let toolHint = $state<string | null>(null);
	/** v2: the credit bar's height (the navigation stacks above it, never over it). */
	let creditsH = $state(26);
	let creditsObserver: ResizeObserver | null = null;
	/** Bumped when the map's fonts land: every marker repaints once. */
	let imageEpoch = 0;

	// controller state (non-reactive)
	let viewer: CesiumViewer | null = null;
	/** The Cesium namespace this viewer was built with (the lazy overlays build with it). */
	let cesiumRef: CesiumGlobal | null = null;
	/** This canvas's own test hook (window.__GODS_EYE__ points at the newest canvas's). */
	let snapHook: NonNullable<Window['__GODS_EYE__']> | null = null;
	/**
	 * Set by onDestroy. The mount is async (bundle, mode endpoint, layer
	 * probes): a view left while the canvas is loading must not go on to
	 * build a viewer — a WebGL context with a live render loop — on a
	 * detached node.
	 */
	let destroyed = false;
	let instances = new Map<string, GodsEyeLayerInstance>();
	let pursuit: PursuitOverlay | null = null;
	let stage: { uniforms?: Record<string, number> } | null = null;
	let hashTimer: ReturnType<typeof setTimeout> | null = null;
	let hashLast = 0;
	let hudTimer: ReturnType<typeof setInterval> | null = null;
	let clockTimer: ReturnType<typeof setInterval> | null = null;
	let timeTimer: ReturnType<typeof setInterval> | null = null;
	let declutterTimer: ReturnType<typeof setInterval> | null = null;
	let tourTimer: ReturnType<typeof setTimeout> | null = null;
	let ionTimer: ReturnType<typeof setTimeout> | null = null;
	let hoverTimer: ReturnType<typeof setTimeout> | null = null;
	let handler: { destroy(): void } | null = null;
	let removeCameraListener: (() => void) | null = null;
	let removeTileError: (() => void) | null = null;
	let removeTileProgress: (() => void) | null = null;
	let removePreUpdate: (() => void) | null = null;
	let removeIonListeners: Array<() => void> = [];
	let tileErrors = 0;
	/** Set in onMount: a SPA navigation must not start orbiting at once. */
	let lastInteraction = 0;
	/** True while the orbit's east-north-up frame holds the camera. */
	let orbitFrameActive = false;
	let orbitLastTick = 0;
	/** performance.now() until which a camera flight owns the camera. */
	let flightUntil = 0;
	/** Where the current press started (null once it became a drag). */
	let pointerOrigin: { x: number; y: number } | null = null;
	/** A button is held on the canvas — hover picking pauses. */
	let pressing = false;
	let hoverAt: { x: number; y: number } | null = null;
	let hovered: { entity: CesiumEntity; restore: () => void } | null = null;
	/** Selection-follow memory: never re-fly the same (or a released) subject. */
	let lastFollowedId: string | null = null;
	/** Ground anchor of the locked subject (the wall orbit pivots on it). */
	let lockAnchor: { lon: number; lat: number } | null = null;
	/**
	 * The subject flight in progress: LOCKED is set only when it lands. The
	 * token drops callbacks of a flight that a newer one superseded.
	 */
	let lockFlight: { token: number; eventId: string; seq: number | null } | null = null;
	let lockFlightToken = 0;
	/**
	 * Focus requests this canvas has seen. Starts at the bus's current seq:
	 * the bus outlives SPA navigation, and a canvas must not replay a request
	 * made on another view (a released subject re-locked on /gods-eye, a
	 * stale 'no route geometry' flash on /ops). Requests made while this
	 * canvas is still loading are newer, so they are still served.
	 */
	const mountedFocusSeq = focus.seq;
	let lastFocusSeq = mountedFocusSeq;
	let detachFocus: (() => void) | null = null;
	let pendingFocus: { seq: number; eventId: string; deadline: number } | null = null;
	/** Pursuit request token: a stale async trace fetch never draws. */
	let pursuitToken = 0;
	let pursuitShownSig = '';
	/** Signature whose trace fetch is in flight (an identical re-poll waits for it). */
	let pursuitPendingSig = '';
	let preTourSensor: SensorMode = 'raw';
	/** REPLAY overlay (tape tracks on the viewer clock). */
	let replayOverlay: ReplayOverlay | null = null;
	/** Bumped when a lazily-built overlay lands, so the pursuit and replay effects re-run at once. */
	let overlaysLanded = $state(0);
	let pursuitFlight: Promise<void> | null = null;
	let replayFlight: Promise<void> | null = null;

	/**
	 * The pursuit and replay overlays load with their modules (FIX-E-PERF2):
	 * neither draws anything before its data exists — an open pursuit's plan,
	 * a replay tape — so each module loads when that data first arrives
	 * instead of on every cold load (a board with an open pursuit fetches it
	 * at once, and tests/route-coldload.mjs counts it). Every other use site
	 * is already null-safe. A failed fetch clears the flight: the next poll
	 * retries.
	 */
	function ensurePursuitOverlay(cesium: CesiumGlobal, viewer: CesiumViewer): void {
		if (pursuit || pursuitFlight) return;
		pursuitFlight = import('./pursuit')
			.then((m) => {
				if (destroyed) return;
				pursuit = m.createPursuitOverlay(cesium, viewer, { chrome });
				overlaysLanded++;
			})
			.catch(() => {
				pursuitFlight = null;
			});
	}

	function ensureReplayOverlay(cesium: CesiumGlobal, viewer: CesiumViewer): void {
		if (replayOverlay || replayFlight) return;
		replayFlight = import('./replay')
			.then((m) => {
				if (destroyed) return;
				replayOverlay = m.createReplayOverlay(cesium, viewer);
				overlaysLanded++;
			})
			.catch(() => {
				replayFlight = null;
			});
	}
	let replayShownSig = '';
	/** Layers stood down while a replay plays (restored on LIVE; the chips show them paused). */
	let replaySuspended = $state<string[]>([]);
	/** Selection halo + the highlight currently applied to the selection's primitives. */
	const HALO_ID = 'sel:halo';
	/** Radius (m) of the halo's draped ring around its subject. */
	const HALO_RADIUS_M = 95;
	/** A moving subject re-lays its ring once it has moved this far (m). */
	const HALO_RELAY_M = 20;
	let haloAt: { lon: number; lat: number } | null = null;
	/** The halo entity, and where its ring was last laid on the ground. */
	let haloEntity: (CesiumEntity & { show: boolean }) | null = null;
	let haloDrawnAt: { lon: number; lat: number } | null = null;
	let selectedHighlights: Array<{ entity: CesiumEntity; restore: () => void }> = [];
	let selectedHighlightSig = '';
	/** Fly requests this canvas has seen (starts at the bus's seq: no replay across views). */
	const mountedFlySeq = selection.flySeq;
	let lastFlySeq = mountedFlySeq;
	/** Agent notes (canvas_annotate) on the canvas: id → removal timer. */
	const AGENT_NOTE_PREFIX = 'agent:note:';
	const AGENT_NOTE_TTL_MS = 60_000;
	/** canvas_highlight emphasis lasts this long. */
	const AGENT_HIGHLIGHT_TTL_MS = 20_000;
	const agentNotes = new Map<string, ReturnType<typeof setTimeout>>();
	let agentHighlights: Array<() => void> = [];
	let agentHighlightTimer: ReturnType<typeof setTimeout> | null = null;
	/** AI-suggests chips shown at once (the rest wait behind '+N more'). */
	const AGENT_CHIPS_SHOWN = 3;

	/** The flat-map home's target: the city centre (City Pack, $lib/city CITY_CAMERAS.home2d). */
	const CAMERA_HOME = { lon: CITY_CAMERAS.home2d.lon, lat: CITY_CAMERAS.home2d.lat };

	/** Home framing: the city centre mid-screen, the central districts in view (City Pack). */
	const HOME_VIEW = {
		range: CITY_CAMERAS.home2d.range,
		headingDeg: CITY_CAMERAS.home2d.headingDeg,
		pitchDeg: CITY_CAMERAS.home2d.pitchDeg,
	} as const;

	/**
	 * City Command home: the live action framed (actionFrame). If the fused
	 * picture answers only after the canvas is ready, the camera settles onto
	 * the action once — within `settleMs` of the home and only if nobody has
	 * touched the camera since.
	 */
	const ACTION_VIEW = {
		minRange: 3500,
		maxRange: 16_000,
		/** Extra room around the outermost entity (fraction of the fit, then metres for markers/labels). */
		margin: 1.2,
		padM: 500,
		headingDeg: 0,
		pitchDeg: -52,
		flightSec: 1.6,
		settleMs: 12_000,
	} as const;
	/** performance.now() of the home that is still waiting for the fused picture (0 = none). */
	let actionHomeAt = 0;

	/**
	 * The presentation-grade home on the photoreal 3D city (City Command, ion key,
	 * nothing in action): the City Pack's oblique (CITY_CAMERAS.home3d). For
	 * Mumbai it looks north from off Haji Ali along the Worli seaface (its
	 * towers on the right) to the Bandra–Worli Sea Link — camera ≈2.5 km up
	 * (5.2 km at −30°) —
	 * where the real buildings AND the draped overlays read at 1920×1080. The
	 * 2D homes (the flat home, the action frame at −52°) look down onto a
	 * mesh that wants an oblique.
	 */
	const HOME_VIEW_3D = {
		lon: CITY_CAMERAS.home3d.lon,
		lat: CITY_CAMERAS.home3d.lat,
		range: CITY_CAMERAS.home3d.range,
		headingDeg: CITY_CAMERAS.home3d.headingDeg,
		pitchDeg: CITY_CAMERAS.home3d.pitchDeg,
	} as const;
	/**
	 * The live action on the photoreal city: the same frame, oblique, its
	 * camera kept 1.5–3 km up (range 3.5–4.4 km at −42°) — a wider action
	 * keeps its centre and lets the edges go rather than climbing to where
	 * the buildings flatten into a map.
	 */
	const ACTION_VIEW_3D = { pitchDeg: -42, maxRange: 4400 } as const;

	/** Orbit resumes 30 s after the last interaction (the wall's idle beat). */
	const ORBIT_RESUME_MS = 30_000;
	/** ~5 minutes per revolution — slow enough to read labels while it turns. */
	const ORBIT_DEG_PER_SEC = 1.2;
	/** An idle wall camera past the city bbox by this much (or this high) flies home. */
	const CITY_MARGIN_DEG = 0.04;
	const CITY_MAX_ALT_M = 40_000;

	/**
	 * Subject framing for follow/focus. The range is the distance at which
	 * the spine's bounding circle (+15 %) fits the canvas's NARROWER field
	 * of view (1.5–30 km), so a long corridor is framed whole on any aspect
	 * ratio; the pitch steepens from the -60° oblique as the range grows so
	 * the camera stays over the subject — the horizontal offset
	 * range·cos(pitch) never exceeds 1.8 km (≈0.016° of latitude). A short
	 * flight lands the lock well inside 3 s even on software WebGL.
	 */
	const SUBJECT_VIEW = {
		margin: 1.15,
		minRange: 1500,
		maxRange: 30_000,
		minPitchDeg: 60,
		maxPitchDeg: 89,
		maxOffsetM: 1800,
		flightSec: 1.2,
	} as const;

	/** Wheel-out ceiling (m): the region stays in view, never orbit-space. */
	const MAX_ZOOM_M = 120_000;

	/** Focus requests wait this long for geometry (segments / board) to land. */
	const FOCUS_WAIT_MS = 15_000;

	/** An AMA band whose newest READING is older than this renders STALE. */
	const AMA_STALE_SEC = 600;

	/** Share-hash writes at most once per second (cinematic route only). */
	const HASH_THROTTLE_MS = 1000;

	const SENSOR_ORDER: SensorMode[] = ['raw', 'flir-whot', 'flir-bhot', 'flir-iron'];
	// honest labels (fix round 2, item 9): the look is a VISUAL FILTER, never a sensor —
	// the internal ids keep their flir-* names, the chip copy reads thermal-style
	const SENSOR_LABEL: Record<SensorMode, string> = {
		raw: 'COMMAND',
		'flir-whot': 'Thermal-style·WHOT',
		'flir-bhot': 'Thermal-style·BHOT',
		'flir-iron': 'Thermal-style·IRON',
	};

	/**
	 * The guided tour — camera choreography over the LIVE city picture.
	 * Targets are computed when a step plays, from the fused registry and the
	 * board; a step whose layer is off or empty (or whose subject does not
	 * exist right now) is skipped, so the tour never narrates a layer that
	 * shows nothing. On City Command each stop also selects its subject, so
	 * the dossier narrates real rows while the camera moves.
	 */
	interface TourTarget {
		label: string;
		lon: number;
		lat: number;
		range: number;
		/** The entity the stop is about (selected on City Command). */
		urn?: string | null;
	}

	interface TourStep {
		id: string;
		/** Registry layer the step shows (skipped when off or count 0). */
		layer?: string;
		headingDeg: number;
		pitchDeg: number;
		/** Optional sensor beat; other steps play in the pre-tour sensor. */
		sensor?: SensorMode;
		target: () => TourTarget | null;
	}

	const TOUR: TourStep[] = [
		{
			id: 'city',
			headingDeg: HOME_VIEW.headingDeg,
			pitchDeg: HOME_VIEW.pitchDeg,
			target: () => ({
				label: `${cityName('en')} at ${ops.band ?? 'NO BAND'} — one fused picture (${cityRegistry.size} entities · band source ${ops.bandSource})`,
				lon: CAMERA_HOME.lon,
				lat: CAMERA_HOME.lat,
				range: HOME_VIEW.range,
			}),
		},
		{
			id: 'pursuit',
			headingDeg: 60,
			pitchDeg: -48,
			target: () => {
				const pursuitEv = cityRegistry
					.byKind('event')
					.find((e) => e.props.event_kind === 'vehicle_pursuit' && e.state !== 'completed' && e.state !== 'cancelled');
				const meta = (pursuitEv?.props.metadata ?? {}) as Record<string, unknown>;
				const vehicle = typeof meta.vehicle_id === 'string' ? cityRegistry.get(`vehicle:${meta.vehicle_id}`) : null;
				const plan = ops.interception;
				const s = plan?.latestSighting;
				const anchor =
					vehicle && vehicle.lon != null && vehicle.lat != null
						? ([vehicle.lon, vehicle.lat] as [number, number])
						: s
							? s.position
							: null;
				if (!anchor) return null;
				const pts: Array<[number, number]> = [anchor, ...(plan?.chokes ?? []).slice(0, 4).map((c) => c.position)];
				const f = frameOf(pts, 1100);
				const plate = displayPlate(
					typeof vehicle?.props.plate === 'string' ? vehicle.props.plate : (s?.plate ?? null),
					ops.officerOn,
				);
				return f && {
					...f,
					label: `pursuit — ${plate ?? 'vehicle'} (${vehicle?.source === 'emulated' || s?.source === 'emulated_anpr' ? 'EMULATED ANPR' : 'ANPR'}) · ${
						plan?.chokes.length ?? 0
					} ranked chokes · human-initiated`,
					urn: vehicle?.urn ?? pursuitEv?.urn ?? null,
				};
			},
		},
		{
			id: 'camera',
			layer: 'cameras',
			headingDeg: 200,
			pitchDeg: -50,
			target: () => {
				const cams = godsEye.cameras;
				if (!cams.length) return null;
				const busiest = [...cams].sort(
					(a, b) => b.hits15m * 1000 + b.reads15m - (a.hits15m * 1000 + a.reads15m) || (b.lastReadT ?? 0) - (a.lastReadT ?? 0),
				)[0];
				const name = busiest.label ?? busiest.cameraId;
				// A quiet window says so: the stop then shows the newest read, not a 'busiest' zero.
				const ago = busiest.lastReadT != null ? Math.max(0, Math.round((Date.now() - busiest.lastReadT) / 60_000)) : null;
				return {
					label:
						busiest.reads15m > 0
							? `busiest camera — ${name}: ${busiest.reads15m} reads, ${busiest.hits15m} watchlist hits in 15 min (locations + counts only)`
							: `latest ANPR read — ${name}${ago != null ? `, ${ago} min ago` : ''} · no reads in the last 15 min (locations + counts only)`,
					lon: busiest.lon,
					lat: busiest.lat,
					range: 1600,
					urn: `camera:${busiest.cameraId}`,
				};
			},
		},
		{
			id: 'units',
			layer: 'units',
			headingDeg: 150,
			pitchDeg: -42,
			target: () => {
				const units = godsEye.units;
				const pts = units.map((u) => [u.lon, u.lat] as [number, number]);
				const f = frameOf(pts, 1200);
				const moving = units.find((u) => unitPhase(u) === 'en_route') ?? units[0];
				return f && {
					...f,
					label: `units on the ground — ${pts.length} (EMULATED) · ${units.filter((u) => unitPhase(u) === 'en_route').length} en route · ${
						units.filter((u) => unitPhase(u) === 'on_scene').length
					} on scene`,
					urn: moving ? `unit:${moving.unitId}` : null,
				};
			},
		},
		{
			id: 'convoy',
			headingDeg: 0,
			pitchDeg: -55,
			target: () => {
				const convoy = cityRegistry.byKind('convoy')[0];
				if (convoy && convoy.lon != null && convoy.lat != null) {
					return {
						label: `convoy on GPS — ${convoy.label} (${convoy.source === 'emulated' ? 'EMULATED GPS' : 'GPS'})`,
						lon: convoy.lon,
						lat: convoy.lat,
						range: 2400,
						urn: convoy.urn,
					};
				}
				const segs = godsEye.segmentById;
				const planned = ops.events.find(
					(e) => e.source !== 'offline-fixture' && e.eventKind === 'protected_movement' && eventCentroid(e, segs),
				);
				const c = planned ? eventCentroid(planned, segs) : null;
				if (!planned || !c) return null;
				const { range } = subjectFraming(c.radiusM);
				return {
					label: `planned protected movement — ${displayText(planned.name, ops.officerOn)} · RECOMMENDED corridor + dashed alternates`,
					lon: c.lon,
					lat: c.lat,
					range: Math.min(9000, range),
					urn: `event:${planned.eventId}`,
				};
			},
		},
		{
			id: 'signals',
			layer: 'signals',
			headingDeg: 90,
			pitchDeg: -38,
			sensor: 'flir-iron',
			target: () => {
				const pts = godsEye.signals.map((s) => [s.lon, s.lat] as [number, number]);
				const f = frameOf(pts);
				return f && { ...f, label: `signal network — ${pts.length} junction programs at the phase clock — thermal-style view (visual filter)` };
			},
		},
		{
			id: 'enforcement',
			layer: 'enforcement',
			headingDeg: 300,
			pitchDeg: -50,
			target: () => {
				const recs = cityRegistry.byKind('recommendation').filter((r) => r.lon != null && r.lat != null);
				const pending = recs.filter((r) => r.state === 'pending');
				const pick = pending[0] ?? recs[0];
				if (!pick) return null;
				// sightings are evidence on file, never fines: the tour says which is which
				const sightings = recs.filter((r) => r.props.rule_id === 'R_STOLEN_SIGHTING').length;
				return {
					label: `enforcement — ${recs.length - sightings} e-challan recommendation(s) · ${sightings} stolen-vehicle sighting(s), evidence only · ${pending.length} pending a named officer (machine proposes, human disposes)`,
					lon: pick.lon as number,
					lat: pick.lat as number,
					range: 1800,
					urn: pick.urn,
				};
			},
		},
	];

	/** Bounding frame (centre + range) for a set of ground points. */
	function frameOf(
		pts: Array<[number, number]>,
		minRange = 1200,
	): { lon: number; lat: number; range: number } | null {
		if (!pts.length) return null;
		let minLon = Infinity;
		let maxLon = -Infinity;
		let minLat = Infinity;
		let maxLat = -Infinity;
		for (const [x, y] of pts) {
			minLon = Math.min(minLon, x);
			maxLon = Math.max(maxLon, x);
			minLat = Math.min(minLat, y);
			maxLat = Math.max(maxLat, y);
		}
		const lon = (minLon + maxLon) / 2;
		const lat = (minLat + maxLat) / 2;
		const halfW = ((maxLon - minLon) / 2) * 111_320 * Math.cos((lat * Math.PI) / 180);
		const halfH = ((maxLat - minLat) / 2) * 111_320;
		const radius = Math.hypot(halfW, halfH);
		return { lon, lat, range: Math.min(9000, Math.max(minRange, radius * 2.4)) };
	}

	function loadScript(src: string): Promise<void> {
		return new Promise((resolve, reject) => {
			const el = document.createElement('script');
			el.src = src;
			el.async = true;
			el.onload = () => resolve();
			el.onerror = () => reject(new Error(`failed to load ${src}`));
			document.head.appendChild(el);
		});
	}

	function webglAvailable(): boolean {
		try {
			const c = document.createElement('canvas');
			const gl = (c.getContext('webgl2') ?? c.getContext('webgl')) as WebGLRenderingContext | null;
			// Release the probe context at once — one fewer live context per mount.
			gl?.getExtension('WEBGL_lose_context')?.loseContext();
			return !!gl;
		} catch {
			return false;
		}
	}

	function fetchJson(path: string, signal?: AbortSignal): Promise<unknown> {
		return fetch(path, signal ? { signal } : undefined).then((res) => {
			if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
			return res.json();
		});
	}

	function makeReadyHook() {
		let resolveReady: (v: { ok: boolean; reason?: string }) => void;
		const ready = new Promise<{ ok: boolean; reason?: string }>((r) => {
			resolveReady = r;
		});
		const hook: NonNullable<Window['__GODS_EYE__']> = {
			phase: 'loading',
			imageryMode: 'keyless-osm',
			imageryNote: null,
			tilesLoaded: false,
			entityCount: 0,
			distinctLayerIds: [],
			stats: {},
			offlineDetected: false,
			sensorMode: 'raw',
			camera: null,
			orbiting: false,
			selectedEventId: null,
			subjectLockId: null,
			picked: null,
			amaAgeSec: null,
			pursuitEntities: 0,
			layerStats: {},
			selection: { urn: null, hover: null, fly: null, flyOutcome: null, flyMs: null, halo: null, highlighted: 0 },
			registry: { status: 'idle', entities: 0, kinds: {}, updatedAt: 0, convoys: [] },
			replay: null,
			vitals: null,
			locate,
			ready,
		};
		window.__GODS_EYE__ = snapHook = hook;
		return (ok: boolean, reason?: string) => {
			hook.phase = ok ? 'ready' : 'unavailable';
			resolveReady({ ok, reason });
		};
	}

	/**
	 * Publish the test snapshot. Reads run untracked: this is called from
	 * effects, and a snapshot must never become an effect dependency.
	 */
	function publishSnapshot() {
		untrack(() => {
			const snap = snapHook;
			if (!snap || !viewer) return;
			// What is on screen: the photoreal mesh once its tiles cover the view
			// (even over a stumbled imagery layer), else the imagery ladder.
			snap.imageryMode = imageryModeOf({ offline: offlineDetected, basemapId, photoreal: stats['photoreal-3d'] ?? null });
			snap.imageryNote = basemapNote;
			snap.tilesLoaded = viewer.scene.globe.tilesLoaded;
			snap.entityCount = viewer.entities.values.length;
			snap.distinctLayerIds = [...instances.keys()].filter((id) => activeLayers.has(id));
			snap.stats = Object.fromEntries(Object.entries(stats).map(([id, s]) => [id, s.count]));
			snap.offlineDetected = offlineDetected;
			snap.sensorMode = sensorMode;
			snap.camera = cameraState();
			snap.orbiting = orbitFrameActive;
			snap.selectedEventId = ops.selectedEventId;
			snap.subjectLockId = godsEye.subjectLockId;
			snap.picked = picked
				? { id: picked.id, layer: picked.layer, text: displayText(picked.text, ops.officerOn), eventId: picked.eventId }
				: null;
			snap.amaAgeSec = amaAgeSec;
			snap.pursuitEntities = pursuit?.count() ?? 0;
			pursuitCount = snap.pursuitEntities;
			snap.layerStats = Object.fromEntries(
				Object.entries(stats).map(([id, st]) => [id, { count: st.count, ...(st.detail ?? {}), ...(st.via ? { via: st.via } : {}) }]),
			);
			// The pursuit overlay is not a registry layer: its drape audit rides beside them (3D smoke).
			if (pursuit && snap.pursuitEntities > 0) snap.layerStats.pursuit = { count: snap.pursuitEntities, ...pursuit.audit() };
			snap.selection = {
				urn: selection.current,
				hover: selection.hover,
				fly: selection.flyUrn,
				flyOutcome: selection.flyOutcome,
				flyMs: selection.flyLandedMs,
				halo: haloAt ? { lon: haloAt.lon, lat: haloAt.lat } : null,
				highlighted: selectedHighlights.length,
			};
			const kinds: Record<string, number> = {};
			for (const k of ['event', 'vehicle', 'sighting', 'camera', 'junction', 'unit', 'convoy', 'dispatch', 'recommendation', 'anomaly'] as const) {
				kinds[k] = cityRegistry.byKind(k).length;
			}
			snap.registry = {
				status: cityRegistry.status,
				entities: cityRegistry.size,
				kinds,
				updatedAt: cityRegistry.updatedAt,
				convoys: cityRegistry
					.byKind('convoy')
					.filter((c) => c.lon != null && c.lat != null)
					.map((c) => ({ id: c.id, lon: c.lon as number, lat: c.lat as number, t: c.t, source: c.source })),
			};
			snap.vitals = cityVitals.shown;
			// AI suggestions (canvas bus) — a local cast: the snapshot typing lives in cesium.d.ts.
			(snap as unknown as Record<string, unknown>).agent = canvasBus.snapshot();
			snap.replay =
				replay.mode === 'replay'
					? {
							runId: replay.runId,
							status: replay.status,
							cursorSec: replay.cursorSec,
							durationSec: replay.tape?.durationSec ?? 0,
							tracks: replayOverlay?.count() ?? 0,
							markers: replayOverlay?.markers() ?? {},
						}
					: null;
		});
	}

	function refreshStats() {
		const next: Record<string, LayerCoverageStats> = {};
		for (const [id, inst] of instances) next[id] = inst.coverageStats();
		stats = next;
		if (chrome === 'v2') publishChrome();
		// chrome v3: the OSM night map stays under the 3D city until its first tiles are in
		if (v3 && basemapStyle === 'photoreal' && osmOverlay && photorealReady(next['photoreal-3d'])) applyBasemap('photoreal');
		publishSnapshot();
	}

	function radToDeg(rad: number): number {
		const C = window.Cesium;
		if (C?.Math?.toDegrees) return C.Math.toDegrees(rad);
		return (rad * 180) / Math.PI;
	}

	/**
	 * Camera ground position only (degrees / metres) — the per-frame city
	 * guard reads this; the heading/pitch getters each swap the camera
	 * transform, so the full pose stays on the 1 Hz snapshot.
	 */
	function cameraGround(): { lon: number; lat: number; alt: number } | null {
		if (!viewer) return null;
		try {
			const c = viewer.camera.positionCartographic;
			return { lon: radToDeg(c.longitude), lat: radToDeg(c.latitude), alt: c.height };
		} catch {
			return null; // camera mid-teardown
		}
	}

	/** World-frame camera pose (degrees / metres), null before the viewer. */
	function cameraState(): { lon: number; lat: number; alt: number; heading: number; pitch: number } | null {
		if (!viewer) return null;
		try {
			const cam = viewer.camera;
			const c = cam.positionCartographic;
			return {
				lon: radToDeg(c.longitude),
				lat: radToDeg(c.latitude),
				alt: c.height,
				heading: radToDeg(cam.heading),
				pitch: radToDeg(cam.pitch),
			};
		} catch {
			return null; // camera mid-teardown
		}
	}

	function currentViewState(): ShareViewState {
		const cam = viewer!.camera;
		const c = cam.positionCartographic;
		return {
			lon: radToDeg(c.longitude),
			lat: radToDeg(c.latitude),
			alt: c.height,
			heading: radToDeg(cam.heading),
			pitch: radToDeg(cam.pitch),
			roll: radToDeg(cam.roll),
			style: sensorMode === 'raw' ? 'raw' : 'flir',
			bhot: sensorMode === 'flir-bhot',
			palette: sensorMode === 'flir-iron' ? 'iron' : 'mono',
			layers: [...activeLayers],
			// City Command hands the selected entity over with the view.
			selected: hud === 'full' ? selection.current : null,
			// the workspace's keys (UI-S2) ride along unchanged (share-link pass-through, R24)
			extra: shareHashExtras(window.location.hash),
		};
	}

	/** The share URL for the current view (camera, sensor + palette, layers, selection). */
	function shareUrl(): string {
		return buildShareUrl(currentViewState(), GODS_EYE_LAYER_IDS);
	}

	/** Keep the location hash on the current view — cinematic route only, throttled. */
	function updateHash() {
		if (!viewer || hud !== 'full' || hashTimer) return;
		const wait = Math.max(0, HASH_THROTTLE_MS - (performance.now() - hashLast));
		hashTimer = setTimeout(() => {
			hashTimer = null;
			hashLast = performance.now();
			if (!viewer) return;
			try {
				replaceState(`#${shareUrl().split('#')[1] ?? ''}`, page.state);
			} catch {
				// router not ready / sandboxed iframe — SHARE VIEW still works
			}
		}, wait);
	}

	function readProp<T>(p: CesiumProperty<T> | T | undefined, time: unknown): T | undefined {
		if (p == null) return undefined;
		if (typeof p === 'object' && typeof (p as CesiumProperty<T>).getValue === 'function') {
			return (p as CesiumProperty<T>).getValue(time);
		}
		return p as T;
	}

	/** The human description every layer attaches to its entities. */
	function descriptionOf(entity: CesiumEntity): string | null {
		if (!viewer) return null;
		const d = readProp(entity.description, viewer.clock.currentTime);
		return typeof d === 'string' && d.trim() ? d : null;
	}

	/**
	 * Test hook: client coordinates of the entities whose id starts with
	 * `prefix`, on-screen only — on the canvas AND not under anything the
	 * host floats over it (City Command's vitals / dossier / rail, the HUD
	 * chips), so a reported spot is one an operator can actually click. A
	 * polyline reports the screen midpoint of its middle span (on the line,
	 * clear of the vertices where markers and neighbouring segments meet); a
	 * point reports its position.
	 */
	function locate(prefix: string): Array<{ id: string; x: number; y: number }> {
		const C = window.Cesium;
		const out: Array<{ id: string; x: number; y: number }> = [];
		if (!viewer || !C) return out;
		const v = viewer;
		const rect = v.scene.canvas.getBoundingClientRect();
		const time = v.clock.currentTime;
		const toWindow = (world: unknown) => {
			const win = world ? C.SceneTransforms.worldToWindowCoordinates(v.scene, world) : undefined;
			return win && Number.isFinite(win.x) && Number.isFinite(win.y) ? win : null;
		};
		for (const e of v.entities.values) {
			if (!e.id.startsWith(prefix)) continue;
			// chrome v2: a marker hidden in a cluster cannot be clicked; a pin is clicked at its head
			const v2meta = chrome === 'v2' ? markerMeta(e) : null;
			if (v2meta && readProp(e.billboard?.show, time) === false) continue;
			const positions = readProp(e.polyline?.positions, time);
			let win: { x: number; y: number } | null = null;
			if (Array.isArray(positions) && positions.length >= 2) {
				const i = Math.max(0, Math.floor(positions.length / 2) - 1);
				const a = toWindow(positions[i]);
				const b = toWindow(positions[i + 1]);
				win = a && b ? { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 } : null;
			} else {
				win = toWindow(readProp(e.position, time));
				if (win && v2meta?.click) win = { x: win.x + v2meta.click.x, y: win.y + v2meta.click.y };
			}
			if (!win || win.x < 0 || win.y < 0 || win.x > rect.width || win.y > rect.height) continue;
			const x = rect.left + win.x;
			const y = rect.top + win.y;
			const top = document.elementFromPoint(x, y);
			if (top && container && !container.contains(top)) continue; // covered by a panel or chip
			out.push({ id: e.id, x, y });
		}
		return out;
	}

	function enterOfflineSchematic(v: CesiumViewer) {
		if (offlineDetected) return;
		offlineDetected = true;
		try {
			v.scene.globe.show = false;
			v.scene.imageryLayers.removeAll?.();
		} catch {
			// older bundle edge — globe hidden is the meaningful part
		}
	}

	/**
	 * Offline detection: sustained tile errors on the base layer → schematic.
	 * Not while the photoreal tiles cover the view: the city on screen is
	 * Google's 3D mesh, not a flat dark globe, and the globe beneath it is
	 * the overlays' ground (layers/draping.ts) — hiding it would be false.
	 */
	function watchTileErrors(v: CesiumViewer) {
		removeTileError?.();
		removeTileError = null;
		tileErrors = 0;
		const baseProvider = (v.scene.imageryLayers.get(0) as unknown as {
			imageryProvider?: { errorEvent?: CesiumEvent<[unknown]> };
		})?.imageryProvider;
		if (baseProvider?.errorEvent) {
			removeTileError = baseProvider.errorEvent.addEventListener(() => {
				tileErrors++;
				if (tileErrors >= 5 && !offlineDetected && !photorealReady(stats['photoreal-3d'])) enterOfflineSchematic(v);
			});
		}
	}

	/**
	 * The ion upgrade reports failure asynchronously (bad token → 401,
	 * ion unreachable → no answer). Either way the canvas swaps in the
	 * keyless basemap and labels why — a bad token never takes the canvas
	 * down to 'unavailable'.
	 */
	function watchIonBasemap(cesium: CesiumGlobal, v: CesiumViewer, basemap: Basemap) {
		if (basemap.id !== 'ion-photoreal') return;
		let imageryReady = false;
		const why = (err: unknown) => (err instanceof Error ? err.message : String(err)).slice(0, 120);
		const imageryFallback = (reason: string) => {
			if (basemapId !== 'ion-photoreal' || viewer !== v) return;
			if (ionTimer) clearTimeout(ionTimer);
			ionTimer = null;
			try {
				if (basemap.imageryLayer) v.scene.imageryLayers.remove(basemap.imageryLayer, true);
				const keyless = createKeylessBasemap(cesium);
				v.scene.imageryLayers.add(keyless.baseLayer, 0);
				v.scene.globe.terrainProvider = keyless.terrainProvider;
				watchTileErrors(v);
			} catch {
				// a half-built ion layer is still removable on teardown
			}
			basemapId = 'osm-keyless';
			basemapNote = `ion upgrade unavailable (${reason}) — keyless OSM fallback`;
			publishSnapshot();
		};
		if (basemap.imageryLayer) {
			removeIonListeners.push(
				basemap.imageryLayer.readyEvent.addEventListener(() => {
					imageryReady = true;
					if (ionTimer) clearTimeout(ionTimer);
					ionTimer = null;
					// The ion provider exists only now: arm the offline-schematic
					// tile-error watch on it (the mount-time watch found none).
					if (viewer === v && basemapId === 'ion-photoreal') watchTileErrors(v);
				}),
				basemap.imageryLayer.errorEvent.addEventListener((err) => imageryFallback(why(err))),
			);
		}
		if (basemap.terrain) {
			removeIonListeners.push(
				basemap.terrain.errorEvent.addEventListener((err) => {
					if (viewer !== v) return;
					try {
						v.scene.globe.terrainProvider = new cesium.EllipsoidTerrainProvider();
					} catch {
						// keep whatever terrain the globe has
					}
					if (basemapId === 'ion-photoreal') basemapNote = `ion world terrain unavailable (${why(err)}) — ellipsoid terrain`;
					publishSnapshot();
				}),
			);
		}
		ionTimer = setTimeout(() => {
			if (!imageryReady) imageryFallback(`no answer in ${Math.round(ION_READY_TIMEOUT_MS / 1000)} s`);
		}, ION_READY_TIMEOUT_MS);
	}

	/** The star field is held off until the view's first tiles have landed. */
	let starsHeld = false;

	/**
	 * The canvas is a DARK MAP from its first frame, never 'space': the clear
	 * colour and the globe's base colour are the canvas token, and the star
	 * field stays off until the view's first tiles land (a slow tile fetch —
	 * OSM probes have taken 4.9 s — used to leave a fresh City Command on a
	 * black, starry sky with only the markers; the draped lines need the
	 * globe). The stars come back with the first loaded view (only a horizon
	 * view ever shows sky). And the OSM attribution rides the on-screen
	 * credit plate on both canvases — the keyless raster is OSM, and the keyed
	 * city still draws OSM-derived road geometry (basemap.ts osmScreenCredit).
	 */
	function prepareGround(cesium: CesiumGlobal, v: CesiumViewer) {
		const ink = cssColor(cesium, '--v-canvas', cesium.Color.BLACK);
		try {
			v.scene.backgroundColor = ink;
			v.scene.globe.baseColor = ink;
		} catch {
			// a stripped build keeps its defaults
		}
		if (v.scene.skyBox) {
			v.scene.skyBox.show = false;
			starsHeld = true;
		}
		const credit = osmScreenCredit(cesium);
		if (credit) {
			try {
				v.creditDisplay?.addStaticCredit(credit);
			} catch {
				// the lightbox still carries the raster's credit
			}
		}
	}

	/** The first loaded view: the star field may show again (horizon views only). */
	function releaseStars() {
		if (!starsHeld) return;
		starsHeld = false;
		try {
			if (viewer?.scene.skyBox) viewer.scene.skyBox.show = true;
		} catch {
			// viewer mid-teardown
		}
	}

	function applySensorStage(cesium: CesiumGlobal, v: CesiumViewer) {
		if (stage && v.scene.postProcessStages.contains(stage)) {
			v.scene.postProcessStages.remove(stage);
		}
		stage = null;
		if (sensorMode === 'raw') return;
		stage = new cesium.PostProcessStage({
			name: 'sajag-flir',
			fragmentShader: FLIR_SHADER.fragmentShader,
			uniforms: {
				intensity: FLIR_SHADER.uniforms.intensity.default,
				sensitivity: FLIR_SHADER.uniforms.sensitivity.default,
				bloom: FLIR_SHADER.uniforms.bloom.default,
				mode: sensorMode === 'flir-bhot' ? 1 : 0,
				pixelation: FLIR_SHADER.uniforms.pixelation.default,
				palette: sensorMode === 'flir-iron' ? 1 : 0,
				// Wall embeds keep the full frame; the optics mask is cinematic-only.
				lens: hud === 'full' ? FLIR_SHADER.uniforms.lens.default : 0,
				time: 0,
			},
		});
		v.scene.postProcessStages.add(stage);
	}

	function setSensor(mode: SensorMode) {
		sensorMode = mode;
		if (viewer && window.Cesium) applySensorStage(window.Cesium, viewer);
		publishSnapshot();
	}

	function cycleSensor() {
		const next = SENSOR_ORDER[(SENSOR_ORDER.indexOf(sensorMode) + 1) % SENSOR_ORDER.length];
		// The operator's choice outlives the tour (stop restores THIS sensor).
		if (tourIndex != null) preTourSensor = next;
		setSensor(next);
		updateHash();
	}

	function setLayerEnabled(id: string, on: boolean) {
		const inst = instances.get(id);
		if (!inst) return;
		if (on === activeLayers.has(id)) return;
		// A layer the replay stood down only changes its toggle now; LIVE
		// re-activates it (activate() is not idempotent — never twice).
		if (!replaySuspended.includes(id)) {
			if (on) inst.activate();
			else inst.deactivate();
		}
		activeLayers = new Set(on ? [...activeLayers, id] : [...activeLayers].filter((x) => x !== id));
		refreshStats();
		updateHash();
	}

	function toggleLayer(id: string) {
		setLayerEnabled(id, !activeLayers.has(id));
	}

	async function share() {
		if (!viewer) return;
		const url = shareUrl();
		try {
			await navigator.clipboard.writeText(url);
			shareFlash = 'view URL copied';
		} catch {
			shareFlash = url.slice(0, 160) + '…';
		}
		setTimeout(() => (shareFlash = null), 4000);
	}

	// ─── camera: frames, flights, home ─────────────────────────────────────────

	/** Hand the camera back to the world frame (orbit frame released). */
	function resetFrame() {
		const C = window.Cesium;
		if (!orbitFrameActive || !viewer || !C) return;
		try {
			viewer.camera.lookAtTransform(C.Matrix4.IDENTITY);
		} catch {
			// camera mid-teardown
		}
		orbitFrameActive = false;
	}

	/**
	 * Fly to frame a ground point from a heading/pitch/range offset. The
	 * orbit frame is released first (flyTo keeps a non-identity transform),
	 * and the orbit stays off while the flight owns the camera. `complete`
	 * runs when the flight lands; `cancel` when a newer flight (or the
	 * operator's gesture) supersedes it.
	 */
	function flyFrame(
		lon: number,
		lat: number,
		range: number,
		headingDeg: number,
		pitchDeg: number,
		duration: number,
		on: { complete?: () => void; cancel?: () => void } = {},
	) {
		const C = window.Cesium;
		if (!viewer || !C) return;
		resetFrame();
		flightUntil = performance.now() + duration * 1000 + 250;
		const at = clearRegionTarget(lon, lat, range, headingDeg, pitchDeg);
		viewer.camera.flyToBoundingSphere(new C.BoundingSphere(C.Cartesian3.fromDegrees(at.lon, at.lat, 0), 0), {
			offset: new C.HeadingPitchRange(C.Math.toRadians(headingDeg), C.Math.toRadians(pitchDeg), range),
			duration,
			...on,
		});
	}

	/**
	 * The look-at point that puts ground point `lon,lat` in the middle of the
	 * canvas region the host's panels leave clear (clearInsets), for a flight
	 * at `range`/`headingDeg`/`pitchDeg`. Without insets (the wall views) it
	 * is the point itself. Small-angle model around the screen centre: one
	 * CSS px covers 2·range·tan(vfov/2)/H metres across the view and that
	 * over sin(|pitch|) along the ground; the shift is capped at 35 % of the
	 * range so a panel layout can never push the subject off the canvas.
	 * The top edge is the lower of the host's inset and the chip row as it
	 * lays out right now: with the dossier open the row wraps to two lines,
	 * and a fixed one-row inset would land the subject under the second.
	 */
	function clearRegionTarget(
		lon: number,
		lat: number,
		range: number,
		headingDeg: number,
		pitchDeg: number,
	): { lon: number; lat: number } {
		const ins = clearInsets;
		const canvas = viewer?.scene.canvas;
		const w = canvas?.clientWidth ?? 0;
		const h = canvas?.clientHeight ?? 0;
		if (!ins || w < 200 || h < 200) return { lon, lat };
		const rowBottom =
			hudRowEl && canvas ? hudRowEl.getBoundingClientRect().bottom - canvas.getBoundingClientRect().top + 8 : 0;
		const top = Math.max(ins.top, rowBottom);
		const clearW = w - ins.left - ins.right;
		const clearH = h - top - ins.bottom;
		if (clearW < 160 || clearH < 120) return { lon, lat };
		const dxPx = ins.left + clearW / 2 - w / 2; // + = the clear centre is right of the canvas centre
		const dyPx = top + clearH / 2 - h / 2; // + = below
		const fov = viewer?.camera.frustum.fov;
		const aspect = w / h;
		const tanHalfV = Math.tan((fov && Number.isFinite(fov) ? fov : Math.PI / 3) / 2) / Math.max(1, aspect);
		const mPerPx = (2 * range * tanHalfV) / h;
		const along = Math.max(0.35, Math.sin(Math.abs((pitchDeg * Math.PI) / 180)));
		let rightM = dxPx * mPerPx;
		let upM = (-dyPx * mPerPx) / along;
		const cap = range * 0.35;
		const norm = Math.hypot(rightM, upM);
		if (norm > cap) {
			rightM *= cap / norm;
			upM *= cap / norm;
		}
		// The look-at moves opposite to where the subject must appear on screen.
		const hd = (headingDeg * Math.PI) / 180;
		const eastM = -rightM * Math.cos(hd) - upM * Math.sin(hd);
		const northM = rightM * Math.sin(hd) - upM * Math.cos(hd);
		return {
			lon: lon + eastM / (111_320 * Math.cos((lat * Math.PI) / 180)),
			lat: lat + northM / 110_540,
		};
	}

	/**
	 * Half-angle (rad) of the narrower field-of-view axis. Cesium's `fov` is
	 * the horizontal angle on a wide canvas and the vertical one on a tall
	 * canvas; the other axis is narrower by the aspect ratio.
	 */
	function narrowHalfFov(): number {
		const f = viewer?.camera.frustum;
		const canvas = viewer?.scene.canvas;
		const fov = f?.fov && Number.isFinite(f.fov) ? f.fov : Math.PI / 3;
		const aspect =
			f?.aspectRatio && Number.isFinite(f.aspectRatio)
				? f.aspectRatio
				: canvas && canvas.clientHeight > 0
					? canvas.clientWidth / canvas.clientHeight
					: 16 / 9;
		return Math.atan(Math.tan(fov / 2) * Math.min(aspect, 1 / aspect));
	}

	/** Range + pitch that frame a spine of `radiusM` whole, with the camera over its centroid. */
	function subjectFraming(radiusM: number): { range: number; pitchDeg: number } {
		const fit = (radiusM * SUBJECT_VIEW.margin) / Math.sin(narrowHalfFov());
		const range = Math.min(SUBJECT_VIEW.maxRange, Math.max(SUBJECT_VIEW.minRange, fit));
		const steepDeg = (Math.acos(Math.min(1, SUBJECT_VIEW.maxOffsetM / range)) * 180) / Math.PI;
		return { range, pitchDeg: -Math.min(SUBJECT_VIEW.maxPitchDeg, Math.max(SUBJECT_VIEW.minPitchDeg, steepDeg)) };
	}

	/**
	 * Home. On City Command the home is the LIVE ACTION — the fused
	 * picture's open events, earmarked vehicles, pending e-challans,
	 * dispatches, convoys and units in motion, framed together in the clear
	 * region — and the city centre only while the picture has none (or has
	 * not answered yet). On the photoreal 3D city both are oblique: the
	 * action at ACTION_VIEW_3D, else the City Pack's oblique over the
	 * centre (HOME_VIEW_3D). The wall views keep the fixed city-centre home.
	 */
	function flyHome(duration: number) {
		const action = hud === 'full' ? actionFrame() : null;
		if (action) {
			flyFrame(action.lon, action.lat, action.range, ACTION_VIEW.headingDeg, actionPitchDeg(), duration);
			return;
		}
		if (hud === 'full' && photoreal3d()) {
			const h = HOME_VIEW_3D;
			flyFrame(h.lon, h.lat, h.range, h.headingDeg, h.pitchDeg, duration);
			return;
		}
		flyFrame(CAMERA_HOME.lon, CAMERA_HOME.lat, HOME_VIEW.range, HOME_VIEW.headingDeg, HOME_VIEW.pitchDeg, duration);
	}

	/**
	 * The photoreal 3D city is (or is about to be) under the camera: the ion
	 * key with its 3D layer on. Read from the key, not the tiles — the home
	 * flight leaves before the first tile lands.
	 */
	function photoreal3d(): boolean {
		return godsEye.imageryMode === 'ion-photoreal' && !!godsEye.imageryToken && activeLayers.has('photoreal-3d');
	}

	/** The action frame's pitch: oblique over the 3D city, steeper over the flat map. */
	function actionPitchDeg(): number {
		return photoreal3d() ? ACTION_VIEW_3D.pitchDeg : ACTION_VIEW.pitchDeg;
	}

	/** The frame of what is happening in the city now (null: nothing open, or no answer yet). */
	function actionFrame(): { lon: number; lat: number; range: number } | null {
		if (cityRegistry.status !== 'ok') return null;
		const pts: Array<[number, number]> = [];
		const add = (e: { lon: number | null; lat: number | null }) => {
			if (e.lon != null && e.lat != null && inCity(e.lon, e.lat, 0)) pts.push([e.lon, e.lat]);
		};
		for (const e of cityRegistry.byKind('event')) if (e.state !== 'completed' && e.state !== 'cancelled') add(e);
		for (const e of cityRegistry.byKind('vehicle')) add(e);
		for (const e of cityRegistry.byKind('recommendation')) if (e.state === 'pending') add(e);
		for (const e of cityRegistry.byKind('dispatch')) add(e);
		for (const e of cityRegistry.byKind('convoy')) add(e);
		for (const e of cityRegistry.byKind('unit')) if (e.state === 'en_route' || e.state === 'on_scene') add(e);
		if (!pts.length) return null;
		let minLon = Infinity;
		let maxLon = -Infinity;
		let minLat = Infinity;
		let maxLat = -Infinity;
		for (const [x, y] of pts) {
			minLon = Math.min(minLon, x);
			maxLon = Math.max(maxLon, x);
			minLat = Math.min(minLat, y);
			maxLat = Math.max(maxLat, y);
		}
		const lat = (minLat + maxLat) / 2;
		const lon = (minLon + maxLon) / 2;
		// Fit the extent into the region the panels leave clear (the whole
		// canvas on a wall): one CSS px covers 2·range·tan(vfov/2)/H metres
		// across the view, that over sin(|pitch|) along the ground.
		const canvas = viewer?.scene.canvas;
		const w = canvas?.clientWidth || 1920;
		const h = canvas?.clientHeight || 1080;
		const ins = clearInsets;
		const clearW = Math.max(160, w - (ins?.left ?? 0) - (ins?.right ?? 0));
		const clearH = Math.max(120, h - (ins?.top ?? 0) - (ins?.bottom ?? 0));
		const fov = viewer?.camera.frustum.fov;
		const tanHalfV = Math.tan((fov && Number.isFinite(fov) ? fov : Math.PI / 3) / 2) / Math.max(1, w / h);
		const halfE = ((maxLon - minLon) / 2) * 111_320 * Math.cos((lat * Math.PI) / 180);
		const halfN = ((maxLat - minLat) / 2) * 110_540;
		const needE = (halfE * h) / (tanHalfV * clearW);
		const needN = (halfN * Math.sin(Math.abs((actionPitchDeg() * Math.PI) / 180)) * h) / (tanHalfV * clearH);
		const range = Math.min(
			photoreal3d() ? ACTION_VIEW_3D.maxRange : ACTION_VIEW.maxRange,
			Math.max(ACTION_VIEW.minRange, Math.max(needE, needN) * ACTION_VIEW.margin + ACTION_VIEW.padM),
		);
		return { lon, lat, range };
	}

	function inCity(lon: number, lat: number, marginDeg: number): boolean {
		return (
			lon >= CITY_BBOX.minLon - marginDeg &&
			lon <= CITY_BBOX.maxLon + marginDeg &&
			lat >= CITY_BBOX.minLat - marginDeg &&
			lat <= CITY_BBOX.maxLat + marginDeg
		);
	}

	function restoreFromHash(cesium: CesiumGlobal, v: CesiumViewer) {
		const parsed = parseShareHash(window.location.hash, GODS_EYE_LAYER_IDS);
		if (!parsed) {
			flyHome(0);
			// City Command before the fused picture answered: settle onto the action later.
			if (hud === 'full' && !actionFrame()) actionHomeAt = performance.now();
			return;
		}
		sensorMode =
			parsed.style === 'raw' ? 'raw' : parsed.bhot ? 'flir-bhot' : parsed.palette === 'iron' ? 'flir-iron' : 'flir-whot';
		applySensorStage(cesium, v);
		activeLayers = new Set(parsed.layers);
		// A handed-over selection opens the same dossier (the camera comes from the hash).
		if (hud === 'full' && parsed.selected && parseUrn(parsed.selected)) {
			selection.select(parsed.selected, { fly: false, source: 'share' });
		}
		v.camera.flyTo({
			destination: cesium.Cartesian3.fromDegrees(parsed.lon, parsed.lat, parsed.alt),
			orientation: {
				heading: cesium.Math.toRadians(parsed.heading),
				pitch: cesium.Math.toRadians(parsed.pitch),
				roll: cesium.Math.toRadians(parsed.roll),
			},
			duration: 0, // restore instantly — a handoff link must not cinematic-fly
		});
	}

	// ─── wall mode: auto-orbit, subject follow, focus, guided tour ────────────

	/** Pointer/wheel on the canvas: the operator has the camera now. */
	function markInteraction() {
		lastInteraction = performance.now();
		resetFrame();
		if (tourIndex != null) stopTour();
	}

	/**
	 * A camera gesture (drag or wheel) takes the camera: the held or incoming
	 * lock is released, so the LOCKED chip never claims a hold the operator
	 * just broke, and a flight in progress yields — Cesium does not cancel a
	 * flight on input, its tween would keep overriding the gesture.
	 */
	function takeCamera() {
		followUrn = null;
		if (godsEye.subjectLockId || lockFlight) releaseSubject({ why: 'the operator took the camera' });
		if (viewer && performance.now() < flightUntil) {
			try {
				viewer.camera.cancelFlight();
			} catch {
				// camera mid-teardown
			}
			flightUntil = 0;
		}
	}

	function onPointerDown(e: PointerEvent) {
		markInteraction();
		pressing = true;
		pointerOrigin = { x: e.clientX, y: e.clientY };
	}

	function onPointerMove(e: PointerEvent) {
		if (e.buttons === 0) return;
		lastInteraction = performance.now();
		// A drag (not a click) is a camera gesture.
		if (pointerOrigin && Math.hypot(e.clientX - pointerOrigin.x, e.clientY - pointerOrigin.y) > 6) {
			pointerOrigin = null;
			takeCamera();
		}
	}

	function onPointerUp() {
		pressing = false;
		pointerOrigin = null;
		lastInteraction = performance.now();
	}

	/** v2: the pointer left the map — the readout returns to the view's centre. */
	function onPointerLeave() {
		cursorAt = null;
		hoverList = null;
	}

	function onWheel() {
		markInteraction();
		takeCamera();
	}

	/** The ground point the orbit turns around. */
	function orbitPivot(C: CesiumGlobal): unknown {
		if (godsEye.subjectLockId && lockAnchor) {
			return C.Cartesian3.fromDegrees(lockAnchor.lon, lockAnchor.lat, 0);
		}
		const canvas = viewer!.scene.canvas;
		const hit = viewer!.camera.pickEllipsoid(new C.Cartesian2(canvas.clientWidth / 2, canvas.clientHeight / 2));
		const carto = hit ? C.Cartographic.fromCartesian(hit) : undefined;
		if (carto) {
			const lon = radToDeg(carto.longitude);
			const lat = radToDeg(carto.latitude);
			if (inCity(lon, lat, 0)) return C.Cartesian3.fromDegrees(lon, lat, 0);
		}
		return C.Cartesian3.fromDegrees(CAMERA_HOME.lon, CAMERA_HOME.lat, 0);
	}

	/**
	 * Per-frame orbit + city guard (scene.preUpdate). Wall mode only; time
	 * based, so the turn rate is the same on SwiftShader and on a GPU.
	 */
	function orbitTick() {
		const now = performance.now();
		const dt = orbitLastTick ? Math.min(0.25, (now - orbitLastTick) / 1000) : 0;
		orbitLastTick = now;
		const C = window.Cesium;
		if (!viewer || !C) return;
		if (chrome === 'v2') {
			// SPEC §6.1–6.2: idle orbit only where the page allows it, and never while anything is selected
			if (!idleOrbit || selection.current || (selectionItems?.length ?? 0) > 0 || followUrn) {
				resetFrame();
				return;
			}
		} else if (hud !== 'wall') return;
		const idle = now - lastInteraction >= ORBIT_RESUME_MS;
		if (!idle || tourIndex != null) {
			resetFrame();
			return;
		}
		if (now < flightUntil || document.hidden) return;
		try {
			const cam = cameraGround();
			if (cam && (!inCity(cam.lon, cam.lat, CITY_MARGIN_DEG) || cam.alt > CITY_MAX_ALT_M)) {
				// An idle wall camera off the city (or out in space) flies home.
				if (godsEye.subjectLockId) releaseSubject({ remember: false });
				flyHome(2.5);
				return;
			}
			if (!orbitFrameActive) {
				viewer.camera.lookAtTransform(C.Transforms.eastNorthUpToFixedFrame(orbitPivot(C)));
				orbitFrameActive = true;
			}
			viewer.camera.rotateRight(C.Math.toRadians(ORBIT_DEG_PER_SEC * dt));
			// an orbit never ends a move: the v2 pass keeps up at a slow cadence (coalesced)
			if (chrome === 'v2') scheduleDecorate(ORBIT_DECORATE_MS);
		} catch {
			// camera mid-teardown — the next frame retries
		}
	}

	/**
	 * Fly to an event's spine; the camera is held on it (the LOCKED chip)
	 * only when the flight LANDS. `seq` is the focus request being served
	 * (null for the /ops selection follow) — it settles 'locked' on landing,
	 * 'cancelled' when the flight is superseded or the operator takes over.
	 */
	function lockOn(eventId: string, c: { lon: number; lat: number; radiusM: number }, seq: number | null = null) {
		if (tourIndex != null) stopTour();
		// A different subject held now is let go at once (a hand-over, not an
		// operator release); the chip returns when this flight lands.
		if (godsEye.subjectLockId && godsEye.subjectLockId !== eventId) {
			godsEye.subjectLockId = null;
			lockAnchor = null;
		}
		const token = ++lockFlightToken;
		lockFlight = { token, eventId, seq };
		const { range, pitchDeg } = subjectFraming(c.radiusM);
		lastInteraction = performance.now();
		flyFrame(c.lon, c.lat, range, 0, pitchDeg, SUBJECT_VIEW.flightSec, {
			complete: () => {
				if (token !== lockFlightToken || !viewer) return;
				lockFlight = null;
				godsEye.subjectLockId = eventId;
				lockAnchor = { lon: c.lon, lat: c.lat };
				lastInteraction = performance.now();
				if (seq != null) focus.settle(seq, 'locked', eventLabel(eventId));
				publishSnapshot();
			},
			cancel: () => {
				if (token !== lockFlightToken) return;
				// superseded by a flight that is not a lock (tour step, fly-home)
				lockFlight = null;
				if (seq != null) focus.settle(seq, 'cancelled', 'another camera flight took over');
				publishSnapshot();
			},
		});
		publishSnapshot();
	}

	/** Selection follow (wall /ops): live events only, once per selection. */
	function followSubject(eventId: string) {
		if (!viewer || !window.Cesium) return;
		const ev = ops.events.find((e) => e.eventId === eventId);
		if (!ev || ev.source === 'offline-fixture') return;
		const c = eventCentroid(ev, godsEye.segmentById);
		if (!c) return;
		lastFollowedId = eventId;
		lockOn(eventId, c);
	}

	/**
	 * Let go of the subject — the held lock, or a lock flight still in the
	 * air (it will not lock when it lands). An operator release (RELEASE,
	 * drag, wheel, tour) is remembered on the focus bus, so no view's
	 * selection follow re-locks the subject until the selection moves to
	 * another event or a surface asks for it again; the idle city guard's
	 * release is not an operator decision and is not remembered.
	 */
	function releaseSubject({ why = 'released before the flight landed', remember = true } = {}) {
		const subject = godsEye.subjectLockId ?? lockFlight?.eventId ?? null;
		if (lockFlight) {
			if (lockFlight.seq != null) focus.settle(lockFlight.seq, 'cancelled', why);
			lockFlight = null;
			lockFlightToken++; // its complete/cancel callbacks are stale now
		}
		if (subject && remember) focus.released = subject;
		godsEye.subjectLockId = null;
		lockAnchor = null;
		lastInteraction = performance.now(); // orbit stays paused 30 s after release
		resetFrame();
		publishSnapshot();
	}

	/** Serve focus request `seq` (focus bus): fly + lock on landing, or say why not. */
	function runFocus(seq: number, eventId: string) {
		const ev = ops.events.find((e) => e.eventId === eventId);
		const c = ev ? eventCentroid(ev, godsEye.segmentById) : null;
		if (ev && c) {
			pendingFocus = null;
			focus.settle(seq, 'pending', `flying to ${eventLabel(eventId)}`);
			lockOn(eventId, c, seq);
			return;
		}
		const waiting = !ev || godsEye.segmentsFeed.status === 'empty';
		if (waiting && (!pendingFocus || pendingFocus.seq !== seq)) {
			pendingFocus = { seq, eventId, deadline: Date.now() + FOCUS_WAIT_MS };
			focus.settle(seq, 'pending', 'waiting for the board / segment geometry');
			return;
		}
		if (waiting && pendingFocus && Date.now() < pendingFocus.deadline) return;
		pendingFocus = null;
		focusFlash(`${eventLabel(eventId)}: no route geometry on the canvas — nothing to lock`);
		focus.settle(seq, 'no-geometry', 'event has no resolvable route spine');
	}

	/**
	 * A board event's name as this console may show it: a pursuit title
	 * carries the plate ('PURSUIT — stolen MH47EM9001 …'), so every focus
	 * note, flash and chip title goes through the C6 mask (the event id when
	 * the board does not carry the event).
	 */
	function eventLabel(eventId: string, officer: boolean = ops.officerOn): string {
		const name = ops.events.find((e) => e.eventId === eventId)?.name;
		return name ? displayText(name, officer) : eventId;
	}

	function focusFlash(text: string) {
		shareFlash = text;
		setTimeout(() => {
			if (shareFlash === text) shareFlash = null;
		}, 5000);
	}

	function tourTarget(step: TourStep) {
		if (step.layer && (!activeLayers.has(step.layer) || (stats[step.layer]?.count ?? 0) === 0)) return null;
		return step.target();
	}

	function tourStep(i: number) {
		const C = window.Cesium;
		if (!viewer || !C || tourIndex == null) return;
		const steps = TOUR.filter((s) => tourTarget(s) !== null);
		if (!steps.length) {
			stopTour();
			return;
		}
		const idx = i % steps.length;
		const step = steps[idx];
		const t = tourTarget(step)!;
		tourIndex = idx;
		tourTotal = steps.length;
		tourLabel = t.label;
		const want = step.sensor ?? preTourSensor;
		if (want !== sensorMode) setSensor(want);
		// City Command: the stop's subject opens in the dossier, so the tour
		// narrates real rows (selected first — the clear region then already
		// accounts for the dossier the selection opens).
		if (hud === 'full' && t.urn && parseUrn(t.urn) && selection.current !== t.urn) {
			selection.select(t.urn, { fly: false, source: 'tour' });
		}
		flyFrame(t.lon, t.lat, t.range, step.headingDeg, step.pitchDeg, 2);
		tourTimer = setTimeout(() => {
			if (tourIndex == null) return;
			tourStep(idx + 1);
		}, 6000);
	}

	function startTour() {
		if (!viewer) return;
		if (godsEye.subjectLockId || lockFlight) releaseSubject({ why: 'a guided tour took the camera' });
		preTourSensor = sensorMode;
		picked = null;
		legendOpen = false;
		tourIndex = 0;
		tourStep(0);
	}

	function stopTour(restoreSensor = true) {
		const wasRunning = tourIndex != null;
		tourIndex = null;
		tourTotal = 0;
		tourLabel = '';
		if (tourTimer) clearTimeout(tourTimer);
		tourTimer = null;
		if (wasRunning) lastInteraction = performance.now();
		if (wasRunning && restoreSensor && sensorMode !== preTourSensor) setSensor(preTourSensor);
	}

	// ─── picking + hover ───────────────────────────────────────────────────────

	function layerOf(id: string): { layer: string; label: string } {
		for (const [layerId, inst] of instances) {
			if (inst.handlePick(id)) {
				return { layer: layerId, label: GODS_EYE_LAYERS.find((l) => l.id === layerId)?.label ?? layerId };
			}
		}
		if (id.startsWith('pursuit:')) return { layer: 'pursuit', label: 'PURSUIT' };
		if (id.startsWith('rpl:')) return { layer: 'replay', label: 'REPLAY · EMULATED' };
		if (id === HALO_ID) return { layer: 'selection', label: 'SELECTED' };
		return { layer: 'other', label: 'ENTITY' };
	}

	/**
	 * The C-C URN a picked primitive draws: the owning layer's urnOf, the
	 * pursuit overlay's subjects (the pursued vehicle, a choke junction, an
	 * onward segment), the halo (the selection itself). Replay primitives are
	 * tape records, not city entities — they have none.
	 */
	function urnOfPick(id: string): string | null {
		for (const inst of instances.values()) {
			if (inst.handlePick(id)) return inst.urnOf?.(id) ?? null;
		}
		if (id === HALO_ID || id === V2_SEL) return selection.current;
		if (id.startsWith('pursuit:')) {
			const choke = /^pursuit:choke-(\d+)$/.exec(id);
			if (choke) return `junction:${choke[1]}`;
			const onward = /^pursuit:onward-(\d+)$/.exec(id);
			if (onward) return `segment:${onward[1]}`;
			const plan = ops.interception;
			return plan?.vehicleId ? `vehicle:${plan.vehicleId}` : plan ? `event:${plan.eventId}` : null;
		}
		return null;
	}

	/**
	 * Pick priority by layer — the operator's likely target first: unit >
	 * camera > vehicle mark > signal > pursuit > event > segment (lower
	 * wins). A small marker drawn over a road must win the click over the
	 * road's spine and the signal ring at the same spot.
	 */
	const PICK_RANK: Record<string, number> = {
		units: 0,
		dispatch: 0.5,
		cameras: 1,
		traces: 2,
		convoy: 2,
		replay: 2,
		enforcement: 2.5,
		signals: 3,
		pursuit: 4,
		anomalies: 4.5,
		events: 5,
		flow: 6,
	};

	/** Marker centres within this many px of the nearest one are 'at the click'. */
	const PICK_NEAR_PX = 3;

	/**
	 * Lines of EQUAL rank under the click (two events' spines sharing a
	 * segment) are not left to drill-pick order: the selected event wins,
	 * then a live (active) one over a planned one, then a pursuit, then the
	 * most recent window — and the id, last, so a click at the same pixel
	 * always picks the same entity. Lower is preferred.
	 */
	function lineTieBreak(e: CesiumEntity): [number, number, number, number, string] {
		const eventId = eventIdFromPick(e.id);
		const ev = eventId ? ops.eventById(eventId) : null;
		if (!ev) return [1, 1, 1, 0, e.id];
		const start = ev.windowStart ? Date.parse(ev.windowStart) : Number.NaN;
		return [
			ev.eventId === ops.selectedEventId ? 0 : 1,
			ev.state === 'active' ? 0 : 1,
			ev.eventKind === 'vehicle_pursuit' ? 0 : 1,
			Number.isFinite(start) ? -start : 0,
			e.id,
		];
	}

	function compareTieBreak(a: [number, number, number, number, string], b: [number, number, number, number, string]): number {
		for (let i = 0; i < 4; i++) if (a[i] !== b[i]) return (a[i] as number) - (b[i] as number);
		return a[4] < b[4] ? -1 : a[4] > b[4] ? 1 : 0;
	}

	/**
	 * The entity under a screen point: up to `limit` primitives drill-picked
	 * front to back. A MARKER (an entity with a position) beats a line; among
	 * markers the one whose centre is nearest the click wins, and markers
	 * about as near (within PICK_NEAR_PX) go by PICK_RANK — unit > camera >
	 * vehicle mark > signal > pursuit > event; lines (spines, segments) go
	 * by PICK_RANK alone. Only Cesium ENTITIES count — the selection halo,
	 * the agent's notes and anything that is not an entity (a 3D-tile
	 * feature of the photoreal layer, C-L) are see-through to the pointer.
	 */
	function pickedEntity(position: { x: number; y: number }, limit = 8): CesiumEntity | null {
		const C = window.Cesium;
		if (!viewer || !C) return null;
		const v = viewer;
		const asEntity = (hit: { id?: CesiumEntity | string } | undefined) => {
			const e = hit && typeof hit.id === 'object' ? hit.id : null;
			return e && typeof e.id === 'string' ? e : null;
		};
		let hits: Array<{ id?: CesiumEntity | string }> = [];
		try {
			hits = v.scene.drillPick(position, limit);
		} catch {
			return null; // scene mid-teardown
		}
		const time = v.clock.currentTime;
		const markers: Array<{ e: CesiumEntity; rank: number; d: number }> = [];
		const lines: Array<{ e: CesiumEntity; rank: number }> = [];
		for (const hit of hits) {
			const e = asEntity(hit);
			if (!e || e.id === HALO_ID || e.id.startsWith(AGENT_NOTE_PREFIX) || e.id.startsWith(V2_PREFIX)) continue;
			const layer = layerOf(e.id).layer;
			// Draped lines share the road's pixels: a pursuit LINE (trace,
			// onward fan, arc, rim) lies on the very road an event's spine
			// drapes, so a click there means the event — the pursued vehicle
			// and its chokes are markers of their own and keep their rank.
			const rank = layer === 'pursuit' && e.polyline ? PICK_RANK.events + 0.25 : (PICK_RANK[layer] ?? 7);
			const world = e.polyline ? undefined : readProp(e.position, time);
			const win = world ? C.SceneTransforms.worldToWindowCoordinates(v.scene, world) : undefined;
			if (win && Number.isFinite(win.x) && Number.isFinite(win.y)) {
				markers.push({ e, rank, d: Math.hypot(win.x - position.x, win.y - position.y) });
			} else {
				lines.push({ e, rank });
			}
		}
		if (markers.length) {
			const nearest = Math.min(...markers.map((m) => m.d));
			const at = markers.filter((m) => m.d <= nearest + PICK_NEAR_PX);
			at.sort((a, b) => a.rank - b.rank || a.d - b.d);
			return at[0].e;
		}
		lines.sort((a, b) => a.rank - b.rank || compareTieBreak(lineTieBreak(a.e), lineTieBreak(b.e)));
		return lines[0]?.e ?? null;
	}

	// ─── label declutter (screen space) ───────────────────────────────────────

	/**
	 * Overlay labels of nearby markers would overprint each other (a Jan
	 * Rakshak unit's label over 'PURSUIT · MH02TS•••2', an e-challan pin's
	 * rule over the pursuit event's name). Every DECLUTTER_MS the labels of
	 * these layers are placed in priority order — the pursued vehicle, the
	 * corridor events' names and tags, units, the pursuit's choke
	 * annotations, dispatch waypoints (a unit that arrived stands ON its
	 * waypoint junction), the convoy, e-challan pins, cameras, vehicle traces
	 * (a vehicle's own mark before its numbered camera hops), anomaly rings —
	 * each as the SCREEN BOX it draws (its anchor + pixelOffset, its origin,
	 * its lines of monospace text), and one whose box meets a placed one hides
	 * until they part. The e-challan / sighting PINS themselves (glyphs, not
	 * labels) are obstacles too: a unit's, camera's, hop's or anomaly's label
	 * that would print over a pin gives way to it — the pin's site label names
	 * the place (a hop 'n EM-CAM-04' under the ₹ pin at EM-CAM-04 read as
	 * noise). A label the operator hovers or selects (emphasis) always shows;
	 * a label already outside its distance condition takes no room.
	 */
	const DECLUTTER_RANK: Record<string, number> = {
		pursuit: 0,
		events: 0.75,
		units: 1,
		dispatch: 1.4,
		convoy: 1.5,
		enforcement: 2,
		cameras: 3,
		traces: 3.25,
		anomalies: 3.5,
	};
	/** A numbered camera hop gives way to its vehicle's own mark label. */
	const HOP_RANK = 3.3;
	/**
	 * Labels that give way to an enforcement pin (glyph) they would cover:
	 * units, cameras, anomalies and the numbered camera hops — never the
	 * earmarked vehicle's own mark label, an event's name or the pursuit's.
	 */
	const YIELD_TO_PINS = new Set(['units', 'cameras', 'anomalies']);
	const yieldsToPins = (layer: string, id: string) => YIELD_TO_PINS.has(layer) || id.startsWith('veh:hop-');
	/** Glyph metrics of the canvas's 12–13 px monospace labels (box estimate). */
	const LABEL_CHAR_PX = 7.4;
	const LABEL_LINE_PX = 16;
	const LABEL_PAD_PX = 4;
	const DECLUTTER_MS = 500;
	/** Hidden labels → the show value they had (restored when they part). */
	const declutterHidden = new Map<CesiumEntity, unknown>();

	type LabelBits = {
		show?: unknown;
		distanceDisplayCondition?: unknown;
		text?: unknown;
		pixelOffset?: unknown;
		verticalOrigin?: unknown;
		horizontalOrigin?: unknown;
	};
	type ScreenBox = { l: number; t: number; r: number; b: number };

	/** Metres between two world (Cartesian3) positions. */
	function cartesianDistance(a: unknown, b: unknown): number {
		const p = a as { x?: number; y?: number; z?: number } | null;
		const q = b as { x?: number; y?: number; z?: number } | null;
		if (!p || !q) return Number.POSITIVE_INFINITY;
		return Math.hypot((p.x ?? 0) - (q.x ?? 0), (p.y ?? 0) - (q.y ?? 0), (p.z ?? 0) - (q.z ?? 0));
	}

	function labelVisibleAt(label: LabelBits, distanceM: number, time: unknown): boolean {
		if (readProp(label.show as CesiumProperty<boolean> | boolean | undefined, time) === false) return false;
		const ddc = readProp(label.distanceDisplayCondition as CesiumProperty<unknown> | undefined, time) as
			| { near?: number; far?: number }
			| undefined;
		if (!ddc) return true;
		return distanceM >= (ddc.near ?? 0) && distanceM <= (ddc.far ?? Number.POSITIVE_INFINITY);
	}

	/**
	 * The screen box a label draws: its anchor moved by its pixelOffset,
	 * placed by its origins (Cesium VerticalOrigin CENTER 0 / BOTTOM 1 /
	 * BASELINE 2 / TOP -1; HorizontalOrigin CENTER 0 / LEFT 1 / RIGHT -1),
	 * sized by its lines of text.
	 */
	function labelBox(label: LabelBits, win: { x: number; y: number }, time: unknown): ScreenBox {
		const text = String(readProp(label.text as CesiumProperty<string> | string | undefined, time) ?? '');
		const lines = text.split('\n');
		const w = Math.max(1, ...lines.map((l) => l.length)) * LABEL_CHAR_PX + LABEL_PAD_PX * 2;
		const h = lines.length * LABEL_LINE_PX + LABEL_PAD_PX;
		const off = readProp(label.pixelOffset as CesiumProperty<{ x?: number; y?: number }> | undefined, time);
		const x = win.x + (off?.x ?? 0);
		const y = win.y + (off?.y ?? 0);
		const vo = Number(readProp(label.verticalOrigin as CesiumProperty<number> | number | undefined, time) ?? 0);
		const ho = Number(readProp(label.horizontalOrigin as CesiumProperty<number> | number | undefined, time) ?? 0);
		const t = vo === -1 ? y : vo === 0 ? y - h / 2 : y - h;
		const l = ho === 1 ? x : ho === -1 ? x - w : x - w / 2;
		return { l, t, r: l + w, b: t + h };
	}

	const boxesMeet = (a: ScreenBox, b: ScreenBox) => a.l < b.r && b.l < a.r && a.t < b.b && b.t < a.b;

	type BillboardBits = {
		show?: unknown;
		width?: unknown;
		height?: unknown;
		scale?: unknown;
		pixelOffset?: unknown;
		verticalOrigin?: unknown;
		horizontalOrigin?: unknown;
	};

	/** The screen box a billboard (a pin glyph) draws — same origin rules as labelBox. */
	function billboardBox(bb: BillboardBits, win: { x: number; y: number }, time: unknown): ScreenBox | null {
		if (readProp(bb.show as CesiumProperty<boolean> | boolean | undefined, time) === false) return null;
		const scale = Number(readProp(bb.scale as CesiumProperty<number> | number | undefined, time) ?? 1) || 1;
		const w = Number(readProp(bb.width as CesiumProperty<number> | number | undefined, time) ?? 0) * scale;
		const h = Number(readProp(bb.height as CesiumProperty<number> | number | undefined, time) ?? 0) * scale;
		if (!(w > 0 && h > 0)) return null;
		const off = readProp(bb.pixelOffset as CesiumProperty<{ x?: number; y?: number }> | undefined, time);
		const x = win.x + (off?.x ?? 0);
		const y = win.y + (off?.y ?? 0);
		const vo = Number(readProp(bb.verticalOrigin as CesiumProperty<number> | number | undefined, time) ?? 0);
		const ho = Number(readProp(bb.horizontalOrigin as CesiumProperty<number> | number | undefined, time) ?? 0);
		const t = vo === -1 ? y : vo === 0 ? y - h / 2 : y - h;
		const l = ho === 1 ? x : ho === -1 ? x - w : x - w / 2;
		return { l, t, r: l + w, b: t + h };
	}

	function declutterLabels() {
		const C = window.Cesium;
		const v = viewer;
		if (!v || !C || phase !== 'ready' || chrome === 'v2') return;
		const time = v.clock.currentTime;
		const eye = v.camera.positionWC;
		const placed: ScreenBox[] = [];
		/** Enforcement pin glyphs on screen (obstacles for the labels that yield to them). */
		const pins: ScreenBox[] = [];
		const candidates: Array<{ e: CesiumEntity; label: LabelBits; rank: number; box: ScreenBox; yieldsToPins: boolean }> = [];
		for (const e of v.entities.values) {
			if (typeof e.id !== 'string') continue;
			const label = e.label as LabelBits | undefined;
			const layer = label || e.billboard ? layerOf(e.id).layer : null;
			if (layer === 'enforcement' && e.billboard) {
				const world = readProp(e.position, time);
				const win = world ? C.SceneTransforms.worldToWindowCoordinates(v.scene, world) : null;
				const box = win && Number.isFinite(win.x) && Number.isFinite(win.y) ? billboardBox(e.billboard as BillboardBits, win, time) : null;
				if (box) pins.push(box);
			}
			if (!label || layer == null) continue;
			// the pursued vehicle's own label outranks everything; its choke
			// annotations rank after the units sent to them; a camera hop after
			// its vehicle's mark
			const rank = e.id.startsWith('pursuit:choke-')
				? 1.25
				: e.id.startsWith('veh:hop-')
					? HOP_RANK
					: DECLUTTER_RANK[layer];
			if (rank == null) continue;
			const world = readProp(e.position, time);
			if (!world) continue;
			// check its OWN visibility (the show we forced off does not count)
			const own: LabelBits = declutterHidden.has(e) ? { distanceDisplayCondition: label.distanceDisplayCondition } : label;
			const distance = cartesianDistance(eye, world);
			if (!emphasis.has(e) && !labelVisibleAt(own, distance, time)) continue;
			const win = C.SceneTransforms.worldToWindowCoordinates(v.scene, world);
			if (!win || !Number.isFinite(win.x) || !Number.isFinite(win.y)) continue;
			candidates.push({ e, label, rank, box: labelBox(label, win, time), yieldsToPins: yieldsToPins(layer, e.id) });
		}
		candidates.sort((a, b) => Number(emphasis.has(b.e)) - Number(emphasis.has(a.e)) || a.rank - b.rank || a.box.t - b.box.t);
		for (const c of candidates) {
			const clash = placed.some((p) => boxesMeet(p, c.box)) || (c.yieldsToPins && pins.some((p) => boxesMeet(p, c.box)));
			if (!clash || emphasis.has(c.e)) {
				placed.push(c.box);
				if (declutterHidden.has(c.e)) {
					c.label.show = declutterHidden.get(c.e) ?? true;
					declutterHidden.delete(c.e);
				}
			} else if (!declutterHidden.has(c.e)) {
				declutterHidden.set(c.e, c.label.show);
				c.label.show = false;
			}
		}
		// entities a layer removed are forgotten
		for (const e of [...declutterHidden.keys()]) if (v.entities.getById(e.id) !== e) declutterHidden.delete(e);
	}

	/**
	 * Left click: the picked primitive's URN becomes the selection (the
	 * dossier on City Command; event URNs also select the event on the
	 * board); the wall views show the layer's pick card as well.
	 */
	function onPick(position: { x: number; y: number }) {
		if (chrome === 'v2' && toolClick(position)) return;
		const entity = pickedEntity(position);
		if (chrome === 'v2') {
			// a cluster's first click spreads it out; the next click picks a member
			const cluster = entity ? clusterOf.get(entity.id) : undefined;
			if (cluster && spider?.lead !== cluster.lead) {
				spider = cluster;
				hoverList = null;
				scheduleDecorate(0);
				return;
			}
			if (spider && (!entity || clusterMember.get(entity.id) !== spider.lead)) {
				spider = null;
				scheduleDecorate(0);
			}
		}
		if (!entity) {
			picked = null;
			publishSnapshot();
			return;
		}
		const { layer, label } = layerOf(entity.id);
		const eventId = eventIdFromPick(entity.id);
		const text = descriptionOf(entity) ?? entity.id;
		const urn = entity.id === HALO_ID ? null : urnOfPick(entity.id);
		if (urn && parseUrn(urn)) {
			selection.select(urn, { fly: false, source: 'map', pick: { pickId: entity.id, layer, text } });
		} else if (eventId && eventId !== ops.selectedEventId && ops.events.some((e) => e.eventId === eventId)) {
			// A PREVIEW fixture (slug id — no C-C URN) still selects on the board.
			// selectEvent resets the band and the audit tail, so never re-select.
			ops.selectEvent(eventId);
		}
		picked = { id: entity.id, layer, label, text, eventId, urn };
		legendOpen = false;
		applySelectionHighlight();
		publishSnapshot();
	}

	/**
	 * Emphasis held per entity. Hover, the selection and an applied agent
	 * highlight may overlap on one entity; each enlarge captures the size it
	 * found, so undos run out of order would leave it enlarged. The count
	 * keeps one enlargement per entity, undone when the LAST holder releases.
	 */
	const emphasis = new Map<CesiumEntity, { holders: number; undo: () => void }>();

	/** Emphasise one entity (hover, selection, agent highlight); returns its release. */
	function highlight(entity: CesiumEntity): () => void {
		const held = emphasis.get(entity);
		if (held) held.holders += 1;
		else emphasis.set(entity, { holders: 1, undo: enlarge(entity) });
		let released = false;
		return () => {
			if (released) return;
			released = true;
			const h = emphasis.get(entity);
			if (!h) return;
			h.holders -= 1;
			if (h.holders <= 0) {
				emphasis.delete(entity);
				h.undo();
			}
		};
	}

	/**
	 * Enlarge one entity: a polyline widens, a point grows, a pin (billboard)
	 * scales up, and a label hidden by distance shows at any range — the
	 * decluttered overview never hides the text of what the operator is
	 * looking at. Returns the undo.
	 */
	function enlarge(entity: CesiumEntity): () => void {
		const time = viewer?.clock.currentTime;
		const undo: Array<() => void> = [];
		const line = entity.polyline;
		if (line) {
			const w = Number(readProp(line.width, time) ?? 2);
			line.width = w + 3;
			undo.push(() => {
				line.width = w;
			});
		}
		const pt = entity.point;
		if (pt) {
			const size = Number(readProp(pt.pixelSize, time) ?? 8);
			const outline = Number(readProp(pt.outlineWidth, time) ?? 1);
			pt.pixelSize = size + 6;
			pt.outlineWidth = outline + 1;
			undo.push(() => {
				pt.pixelSize = size;
				pt.outlineWidth = outline;
			});
		}
		const pin = entity.billboard;
		if (pin) {
			// Restore the PROPERTY, not its value: a hot camera's dot pulses
			// through a time-varying scale (layers/cameras.ts, clamped dots).
			const held = pin.scale;
			const scale = Number(readProp(held, time) ?? 1);
			pin.scale = scale * 1.35;
			undo.push(() => {
				pin.scale = held;
			});
		}
		const text = entity.label;
		if (text && text.distanceDisplayCondition) {
			const ddc = text.distanceDisplayCondition;
			text.distanceDisplayCondition = undefined;
			undo.push(() => {
				text.distanceDisplayCondition = ddc;
			});
		}
		return () => {
			for (const u of undo) u();
		};
	}

	function applyHover() {
		hoverTimer = null;
		if (!viewer || !container || !hoverAt || pressing) return;
		const entity = pickedEntity(hoverAt, 4); // hover: a lighter drill (≤12 picks/s)
		if (chrome === 'v2') hoverV2(hoverAt, entity);
		if (entity === (hovered?.entity ?? null)) return;
		hovered?.restore();
		hovered = null;
		const urn = entity ? urnOfPick(entity.id) : null;
		selection.hover = urn;
		// Only entities still in the collection (layers redraw on data change);
		// the selection's own primitives already wear the selection highlight.
		if (entity && viewer.entities.getById(entity.id) === entity) {
			const selected = selectedHighlights.some((h) => h.entity === entity);
			// a v2 marker shows its hover ring through the v2 pass instead of growing
			const ringed = chrome === 'v2' && !!markerMeta(entity);
			hovered = { entity, restore: selected || ringed ? () => {} : highlight(entity) };
		}
		container.style.cursor = chrome === 'v2' && tool !== 'select' ? 'crosshair' : hovered ? 'pointer' : '';
	}

	function onHover(position: { x: number; y: number }) {
		hoverAt = position;
		if (!hoverTimer) hoverTimer = setTimeout(applyHover, 80); // ≤12 picks/s
	}

	// ─── selection: halo, highlight, fly-to ────────────────────────────────────

	/** Camera framing for a single entity fly-to (offset ≈ 0.007° — well inside 0.02°). */
	const ENTITY_VIEW = { range: 1700, pitchDeg: -62, flightSec: 0.9, maxOffsetM: 900 } as const;
	/**
	 * An applied AI suggestion lands steeper and closer: the camera stands
	 * almost over the subject (offset ≈ 460 m ≈ 0.004°), so 'the agent showed
	 * me the vehicle' reads as the vehicle mid-screen, not a street away.
	 */
	const AGENT_VIEW = { range: 1500, pitchDeg: -72 } as const;
	/** An applied canvas_fly_to's own range_m for its URN (the next agent fly-to reads it once). */
	let agentFlyRange: { urn: string; range: number } | null = null;

	/**
	 * Where an entity is on the ground: the fused registry first; an event's
	 * spine (with its radius, for framing) from the board; a segment or a
	 * junction from the canvas's own geometry; the open dossier last.
	 */
	function knownPosition(urn: string): { lon: number; lat: number; radiusM?: number } | null {
		const parsed = parseUrn(urn);
		const e = cityRegistry.get(urn);
		if (parsed?.kind === 'event') {
			const ev = ops.events.find((x) => x.eventId === parsed.id);
			const c = ev ? eventCentroid(ev, godsEye.segmentById) : null;
			if (e && e.lon != null && e.lat != null) return { lon: e.lon, lat: e.lat, radiusM: c?.radiusM };
			if (c) return c;
		}
		if (e && e.lon != null && e.lat != null) return { lon: e.lon, lat: e.lat };
		if (parsed?.kind === 'segment') {
			const seg = godsEye.segmentById.get(Number(parsed.id));
			const mid = seg?.coordinates[Math.floor((seg?.coordinates.length ?? 0) / 2)];
			if (mid) return { lon: mid[0], lat: mid[1] };
		}
		if (parsed?.kind === 'junction') {
			const j = godsEye.signals.find((s) => s.junctionId === parsed.id);
			if (j) return { lon: j.lon, lat: j.lat };
		}
		const d = dossier.data;
		if (d && d.entity.urn === urn && d.entity.lon != null && d.entity.lat != null) {
			return { lon: d.entity.lon, lat: d.entity.lat };
		}
		return null;
	}

	/** The selection's primitives stay highlighted (re-applied when a layer redraws them). */
	function applySelectionHighlight() {
		if (!viewer) return;
		const urn = selection.current;
		const matches: CesiumEntity[] = [];
		if (urn) {
			for (const e of viewer.entities.values) {
				if (e.id === HALO_ID || e.id.startsWith('rpl:') || e.id.startsWith(V2_PREFIX)) continue;
				if (urnOfPick(e.id) === urn) matches.push(e);
			}
		}
		// v2: a selection no layer draws (a decided row, a sighting on file —
		// the v2 map shows waiting decisions only) still reads as selected:
		// the canvas wears it with the neutral marker + selection ring, and it
		// counts as the selection's own primitive.
		const selMarker = applySelectionMarker(urn, chrome === 'v2' && matches.length === 0);
		const sig = `${urn ?? ''}|${matches.map((e) => e.id).join('|')}`;
		const v = viewer;
		if (sig === selectedHighlightSig && selectedHighlights.every((h) => v.entities.getById(h.entity.id) === h.entity)) return;
		for (const h of selectedHighlights) h.restore();
		selectedHighlights = matches.map((e) => {
			if (hovered?.entity === e) {
				// already enlarged by the hover: let the hover's restore hand it back
				hovered.restore();
				hovered = { entity: e, restore: () => {} };
			}
			return { entity: e, restore: chrome === 'v2' && markerMeta(e) ? () => {} : highlight(e) };
		});
		if (selMarker) selectedHighlights.push({ entity: selMarker, restore: () => {} });
		selectedHighlightSig = sig;
	}

	/**
	 * The canvas's own v2 selection marker (`map2:sel`): a selection no layer
	 * primitive carries — the neutral marker of its kind wearing the
	 * selection ring, at the subject's position (SPEC §7: one selection
	 * drives every view, so a rail, inspector, table, graph or omnibar pick
	 * marks the entity on the map even when the v2 symbology gives it no
	 * marker of its own). Removed when a layer draws the selection or it
	 * clears; the 1 Hz tick re-runs this, so a moving subject is followed.
	 */
	function applySelectionMarker(urn: string | null, needed: boolean): CesiumEntity | null {
		const C = window.Cesium;
		if (chrome !== 'v2' || !C || !viewer || !urn || !needed || !parseUrn(urn)) {
			dropSelectionMarker();
			return null;
		}
		const at = knownPosition(urn);
		if (!at) {
			dropSelectionMarker();
			return null;
		}
		const kind = cityRegistry.get(urn)?.kind ?? parseUrn(urn)?.kind ?? 'marker';
		const meta: MarkerMeta = { urn, kind, glyph: kindIcon(kind), shape: 'disc', cluster: false };
		const existing = viewer.entities.getById(V2_SEL);
		if (!existing) {
			const entity = viewer.entities.add({
				id: V2_SEL,
				position: ground(C, at.lon, at.lat),
				billboard: markerBillboard(C, meta, { selected: true }),
				description: 'the selected entity',
			});
			tagMarker(entity, meta);
			scheduleDecorate(0);
			return entity;
		}
		// the selection moved on: the marker follows its subject and wears the
		// new kind's glyph (the pass drops its stale applied state)
		tagMarker(existing, meta);
		appliedMark.delete(existing);
		(existing as { position?: unknown }).position = ground(C, at.lon, at.lat);
		const bb = existing.billboard;
		const img = imageFor(meta, { selected: true });
		if (bb && img) {
			bb.image = img.url;
			bb.width = img.w;
			bb.height = img.h;
			bb.pixelOffset = new C.Cartesian2(img.offset.x, img.offset.y);
		}
		return existing;
	}

	/** The canvas's v2 selection marker, when it is up. */
	function dropSelectionMarker() {
		if (viewer && viewer.entities.getById(V2_SEL)) viewer.entities.removeById(V2_SEL);
	}

	/** Move the halo onto the selection (or hide it). */
	function placeHalo() {
		const urn = selection.current;
		haloAt = urn ? knownPosition(urn) : null;
		drawHalo();
	}

	/**
	 * Lay the halo's ring on the ground at haloAt — only once the subject
	 * moved HALO_RELAY_M: a draped ring is a GroundPolylinePrimitive that
	 * Cesium rebuilds in a worker, so it is never re-laid per frame, and a
	 * moving subject (a convoy, a pursued vehicle) re-lays it in steps.
	 */
	function drawHalo() {
		const C = window.Cesium;
		const halo = haloEntity;
		if (!C || !halo) return;
		const at = haloAt;
		if (!at || (chrome === 'v2' && selectionIsMarker())) {
			halo.show = false;
			return;
		}
		const kx = 111_320 * Math.cos((at.lat * Math.PI) / 180);
		const moved = !haloDrawnAt || Math.hypot((at.lon - haloDrawnAt.lon) * kx, (at.lat - haloDrawnAt.lat) * 110_540) > HALO_RELAY_M;
		if (moved && halo.polyline) {
			(halo.polyline as { positions?: unknown }).positions = groundPath(C, ringCoords(at.lon, at.lat, HALO_RADIUS_M));
			haloDrawnAt = { lon: at.lon, lat: at.lat };
		}
		halo.show = true;
	}

	/**
	 * The selection halo: a glowing RING around its subject, DRAPED on the
	 * ground (terrain and the photoreal tiles — a ring at a fixed height ran
	 * inside the 3D city) above every other draped line; never a filled
	 * disc (the old 16 %-alpha disc read as an opaque plate over the very
	 * marker it was meant to point at). It breathes through its glow colour
	 * — a material uniform, so the ring itself is re-laid only when its
	 * subject moves (drawHalo); reduced motion holds it steady.
	 */
	function addHalo(cesium: CesiumGlobal, v: CesiumViewer) {
		if (chrome === 'v2') {
			// v2: a thin selection-blue ring on the ground, no glow (SPEC §1.1, §2.4)
			const blue = cssColor(cesium, '--v-map-select', cesium.Color.CYAN) as { withAlpha?: (a: number) => unknown };
			haloEntity = v.entities.add({
				id: HALO_ID,
				show: false,
				polyline: drapedPolyline(cesium, {
					positions: [],
					width: 2,
					material: new cesium.ColorMaterialProperty(blue.withAlpha?.(0.85) ?? blue),
					z: DRAPE_Z.pursuit + 1,
				}),
				description: 'the selected entity',
			}) as CesiumEntity & { show: boolean };
			haloDrawnAt = null;
			drawHalo();
			return;
		}
		const ring = cssColor(cesium, '--v-data', cesium.Color.CYAN) as { withAlpha?: (a: number) => unknown };
		const t0 = performance.now();
		const glow = () => {
			if (reducedMotionPref()) return ring.withAlpha?.(0.9) ?? ring;
			const p = ((performance.now() - t0) % 1800) / 1800;
			return ring.withAlpha?.(0.5 + 0.45 * (0.5 - 0.5 * Math.cos(p * 2 * Math.PI))) ?? ring;
		};
		haloEntity = v.entities.add({
			id: HALO_ID,
			show: false,
			polyline: drapedPolyline(cesium, {
				positions: [],
				width: 6,
				material: new cesium.PolylineGlowMaterialProperty({ color: new cesium.CallbackProperty(glow, false), glowPower: 0.28 }),
				z: DRAPE_Z.pursuit + 1,
			}),
			description: 'the selected entity',
		}) as CesiumEntity & { show: boolean };
		haloDrawnAt = null;
		drawHalo();
	}

	/** v2: the selection is drawn as a marker (its own selected ring marks it). */
	function selectionIsMarker(): boolean {
		const urn = selection.current;
		if (!urn || !viewer) return false;
		for (const e of viewer.entities.values) {
			const meta = markerMeta(e);
			if (meta?.urn === urn && meta.shape !== 'dot') return true;
		}
		return false;
	}

	function reducedMotionPref(): boolean {
		return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
	}

	/** Serve fly request `seq`: bring `urn` into view (or say why not). */
	async function flyToUrn(seq: number, urn: string) {
		let at = knownPosition(urn);
		if (!at) {
			selection.settleFly(seq, 'pending', 'resolving the entity position');
			const d = await dossier.peek(urn);
			if (seq !== selection.flySeq || !viewer || destroyed) return;
			if (d && d.entity.lon != null && d.entity.lat != null) at = { lon: d.entity.lon, lat: d.entity.lat };
		}
		if (!at) {
			selection.settleFly(seq, 'no-position', 'the entity has no known position');
			focusFlash(`${urn}: no position in the city picture — nothing to fly to`);
			return;
		}
		if (tourIndex != null) stopTour();
		if (godsEye.subjectLockId || lockFlight) releaseSubject({ why: 'a fly-to took the camera', remember: false });
		const agent = selection.source === 'agent' && selection.flyUrn === urn;
		const asked = agent && agentFlyRange?.urn === urn ? agentFlyRange.range : null;
		agentFlyRange = null;
		let range: number = agent ? (asked ?? AGENT_VIEW.range) : ENTITY_VIEW.range;
		let pitchDeg: number = agent ? AGENT_VIEW.pitchDeg : ENTITY_VIEW.pitchDeg;
		if (asked != null && asked > AGENT_VIEW.range) {
			// A wider ask still stands over the subject: the pitch steepens so
			// the camera never sits further off it than the agent view's own
			// offset (≈ 460 m) — the entity stays mid-screen, only smaller.
			const maxOffsetM = AGENT_VIEW.range * Math.cos((AGENT_VIEW.pitchDeg * Math.PI) / 180);
			pitchDeg = -Math.max(-AGENT_VIEW.pitchDeg, (Math.acos(Math.min(1, maxOffsetM / range)) * 180) / Math.PI);
		}
		if (at.radiusM != null && at.radiusM > 400) {
			// An area (an event's spines): frame it whole, camera kept over it.
			range = subjectFraming(at.radiusM).range;
			pitchDeg = -Math.max(62, (Math.acos(Math.min(1, ENTITY_VIEW.maxOffsetM / range)) * 180) / Math.PI);
		}
		haloAt = { lon: at.lon, lat: at.lat };
		drawHalo();
		lastInteraction = performance.now();
		selection.settleFly(seq, 'flying');
		flyFrame(at.lon, at.lat, range, 0, pitchDeg, ENTITY_VIEW.flightSec, {
			complete: () => {
				selection.settleFly(seq, 'landed');
				lastInteraction = performance.now();
				publishSnapshot();
			},
			cancel: () => selection.settleFly(seq, 'cancelled', 'another camera flight took over'),
		});
		publishSnapshot();
	}

	// ─── REPLAY: every live layer stands down while a tape plays ──────────────

	/**
	 * Every live layer pauses while a tape plays — the roads' live colours,
	 * the board's events, signals and cameras included — so the replayed
	 * frames are the only data on the canvas (the viewer saw live layers
	 * drawing over the replay). Basemap-like layers (3D tiles) stay.
	 */
	const REPLAY_KEEPS = new Set(['photoreal-3d']);

	function suspendLiveLayers() {
		if (replaySuspended.length) return;
		const paused: string[] = [];
		for (const id of GODS_EYE_LAYER_IDS.filter((l) => !REPLAY_KEEPS.has(l))) {
			if (activeLayers.has(id)) {
				instances.get(id)?.deactivate();
				paused.push(id);
			}
		}
		replaySuspended = paused;
		pursuitToken++;
		pursuitShownSig = pursuitPendingSig = '';
		pursuit?.clear();
		refreshStats();
	}

	function resumeLiveLayers() {
		for (const id of replaySuspended) if (activeLayers.has(id)) instances.get(id)?.activate();
		replaySuspended = [];
		pursuitShownSig = '';
		refreshStats();
	}

	// ─── AGENTIC GOD'S-EYE: AI-suggested directives a human applies ──────────

	/** What this canvas can resolve right now (the fused registry + its own network). */
	function directiveWorld(): DirectiveWorld {
		const segments = godsEye.segmentById;
		return {
			hasUrn: (urn) => cityRegistry.get(urn) != null,
			hasSegment: (id) => segments.has(id),
			hasJunction: (id) =>
				cityRegistry.get(`junction:${id}`) != null || godsEye.signals.some((s) => String(s.junctionId) === String(id)),
			layerIds: [...instances.keys()],
		};
	}

	/** The world is worth re-checking queued URNs against (registry answered, network loaded). */
	function worldReady(): boolean {
		return phase === 'ready' && cityRegistry.status === 'ok' && godsEye.segments.length > 0;
	}

	/** The named duty officer (the ack's claimed officer; the deck proxy adds the verified one). */
	function ackOfficer(): string | null {
		return ops.officerOn ? ops.dutyOfficer.trim() : null;
	}

	function clearAgentHighlights() {
		if (agentHighlightTimer) clearTimeout(agentHighlightTimer);
		agentHighlightTimer = null;
		for (const undo of agentHighlights) undo();
		agentHighlights = [];
	}

	/** Emphasise every primitive of `urns` for AGENT_HIGHLIGHT_TTL_MS and frame them. */
	function highlightUrns(urns: string[]) {
		if (!viewer) return;
		clearAgentHighlights();
		const wanted = new Set(urns);
		const pts: Array<[number, number]> = [];
		for (const e of viewer.entities.values) {
			if (e.id === HALO_ID || e.id.startsWith('rpl:') || e.id.startsWith(AGENT_NOTE_PREFIX)) continue;
			const urn = urnOfPick(e.id);
			if (urn && wanted.has(urn)) agentHighlights.push(highlight(e));
		}
		for (const urn of urns) {
			const at = knownPosition(urn);
			if (at) pts.push([at.lon, at.lat]);
		}
		agentHighlightTimer = setTimeout(clearAgentHighlights, AGENT_HIGHLIGHT_TTL_MS);
		const f = frameOf(pts, 1200);
		if (f) flyFrame(f.lon, f.lat, f.range, 0, -55, 1.2);
		publishSnapshot();
	}

	/** A short-lived note pinned to an entity (canvas_annotate), masked at the sink. */
	function addAgentNote(d: CanvasDirective) {
		const C = window.Cesium;
		if (!viewer || !C || d.args.verb !== 'canvas_annotate') return;
		const at = knownPosition(d.args.urn);
		if (!at) return;
		const id = `${AGENT_NOTE_PREFIX}${d.id}`;
		viewer.entities.removeById(id);
		const tone =
			chrome === 'v2'
				? d.args.severity === 'critical'
					? '--v-map-alert'
					: '--v-ai-text'
				: d.args.severity === 'critical'
					? '--v-band-red'
					: d.args.severity === 'warn'
						? '--v-band-amber'
						: '--v-tool';
		viewer.entities.add({
			id,
			// On the ground beside its entity (a fixed 30 m sat inside the 3D city), never hidden by a building.
			position: ground(C, at.lon, at.lat),
			label: clampedLabel(C, {
				text: `${t(ops.lang, 'agent_note_label')} · ${displayText(d.args.text, ops.officerOn)}`,
				font: canvasFont('600 13px var(--v-font-ui)'),
				fillColor: cssColor(C, tone, C.Color.WHITE),
				outlineColor: cssColor(C, '--v-canvas', C.Color.BLACK),
				outlineWidth: 4,
				style: 2, // FILL_AND_OUTLINE
				verticalOrigin: 1, // BOTTOM
				pixelOffset: new C.Cartesian2(0, -18),
			}),
			description: `AI note (proposal applied by the operator) · ${d.args.text}`,
		});
		const old = agentNotes.get(id);
		if (old) clearTimeout(old);
		agentNotes.set(
			id,
			setTimeout(() => {
				agentNotes.delete(id);
				viewer?.entities.removeById(id);
			}, AGENT_NOTE_TTL_MS),
		);
	}

	/**
	 * Apply one AI suggestion — a HUMAN pressed Apply. Local only (camera,
	 * selection, halo, a TTL note, sensor, layer); the brain gets one ack.
	 */
	function applyDirective(d: CanvasDirective) {
		if (!canvasBus.get(d.id)) return; // already settled (double press)
		const a = d.args;
		switch (a.verb) {
			case 'canvas_fly_to':
				if (a.urn) {
					// the proposal's own range frames the entity (else AGENT_VIEW)
					agentFlyRange = a.rangeM != null ? { urn: a.urn, range: a.rangeM } : null;
					selection.select(a.urn, { fly: true, source: 'agent' });
				} else if (a.lon != null && a.lat != null) {
					if (tourIndex != null) stopTour();
					lastInteraction = performance.now();
					flyFrame(a.lon, a.lat, a.rangeM ?? AGENT_VIEW.range, 0, AGENT_VIEW.pitchDeg, ENTITY_VIEW.flightSec);
				}
				break;
			case 'canvas_track_entity':
				agentFlyRange = null;
				selection.select(a.urn, { fly: true, source: 'agent' });
				break;
			case 'canvas_highlight':
				highlightUrns(a.urns);
				break;
			case 'canvas_annotate':
				addAgentNote(d);
				break;
			case 'canvas_set_sensor':
				setSensor(a.mode);
				updateHash();
				break;
			case 'canvas_toggle_layer':
				setLayerEnabled(a.layerId, a.on);
				break;
		}
		canvasBus.settle(d.id, 'applied', ackOfficer());
		publishSnapshot();
	}

	function dismissDirective(d: CanvasDirective) {
		canvasBus.settle(d.id, 'dismissed', ackOfficer());
		publishSnapshot();
	}

	/** 'fly to <road>' / units: a point flight from the palette. */
	function paletteFly(lon: number, lat: number, rangeM: number) {
		if (tourIndex != null) stopTour();
		if (godsEye.subjectLockId || lockFlight) releaseSubject({ why: 'the command palette took the camera', remember: false });
		lastInteraction = performance.now();
		flyFrame(lon, lat, rangeM, 0, -55, 1.2);
	}

	/** The brain's English verb lead ('track …', 'fly to …') — replaced by the localised verb. */
	const EN_VERB_LEAD = /^(track|fly to|highlight|note on|sensor|layer)\s+/i;

	/** '<verb> <label>' for a chip: the localised verb, the label masked at the sink. */
	function chipText(d: CanvasDirective): string {
		const verb = t(ops.lang, `agent_verb_${d.verb}`);
		return `${verb} ${displayText(d.label, ops.officerOn).replace(EN_VERB_LEAD, '')}`;
	}

	/**
	 * A modal dialog is open on screen. Only a VISIBLE one counts: Cesium
	 * keeps its credit lightbox (role=dialog, aria-modal) in the DOM with
	 * display:none for the life of the viewer.
	 */
	function modalOpen(): boolean {
		return Array.from(document.querySelectorAll('[aria-modal="true"]')).some((el) => el.getClientRects().length > 0);
	}

	/**
	 * Layered Esc: tour → legend → pick card → exit (/gods-eye). An Esc that
	 * another surface already handled, typed in a field (the command
	 * search) or pressed under an open modal belongs to that surface.
	 */
	function onKey(e: KeyboardEvent) {
		if (e.key !== 'Escape' || e.defaultPrevented) return;
		const t = e.target as HTMLElement | null;
		const typing = !!t && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName));
		if (typing || modalOpen()) return;
		if (chrome === 'v2') {
			if (tourIndex != null) stopTour();
			else if (tool !== 'select') setTool('select');
			else if (spider) {
				spider = null;
				scheduleDecorate(0);
			} else if (legendOpen) {
				legendOpen = false;
				publishChrome();
			} else if (layersOpen) layersOpen = false;
			else if (hud === 'full' && selection.current) {
				selection.clear();
				picked = null;
				publishSnapshot();
			} else return; // SPEC §6.2: Esc never navigates
			e.preventDefault();
			return;
		}
		if (tourIndex != null) {
			stopTour();
		} else if (legendOpen) {
			legendOpen = false;
		} else if (picked && showPickCard) {
			picked = null;
			publishSnapshot();
		} else if (hud === 'full' && selection.current) {
			// City Command: Esc closes the dossier before it leaves the view.
			selection.clear();
			picked = null;
			publishSnapshot();
		} else if (hud === 'full' && onexit) {
			onexit();
		} else {
			return;
		}
		e.preventDefault(); // consumed: later listeners see defaultPrevented
	}

	/** 1 Hz: AMA clock, camera snapshot, queued focus retries, the selection's halo + highlight, the AI queue. */
	function tick() {
		nowMs = Date.now();
		if (pendingFocus && phase === 'ready') runFocus(pendingFocus.seq, pendingFocus.eventId);
		if (phase === 'ready') {
			placeHalo();
			applySelectionHighlight();
			// Proposals made off-canvas (the agent console) are resolved here;
			// expired ones leave the queue on their own.
			if (worldReady()) canvasBus.resolve(directiveWorld());
			else canvasBus.expire();
			serveSelectionRequest();
			if (chrome === 'v2') followTick();
		}
		publishSnapshot();
	}

	/** A cited entity opened from the agent console: City Command selects + flies once it can. */
	function serveSelectionRequest() {
		if (hud !== 'full' || !canvasBus.selectionRequest || cityRegistry.status !== 'ok') return;
		const req = canvasBus.takeSelection();
		if (req && parseUrn(req.urn)) selection.select(req.urn, { fly: true, source: req.source });
	}

	// ─── CHROME V2: the view, the decoration pass, the tools ──────────────────

	/** Entities the v2 pass owns (labels, arrows, measure and shape drawings): never picked. */
	const V2_PREFIX = 'map2:';
	/** The canvas's own v2 selection marker (no layer primitive wears the selection). */
	const V2_SEL = `${V2_PREFIX}sel`;
	const V2_LABEL = `${V2_PREFIX}label:`;
	const V2_ARROW = `${V2_PREFIX}arrow:`;
	const V2_MEASURE = `${V2_PREFIX}measure:`;
	const V2_SHAPE = `${V2_PREFIX}shape:`;
	/** The pursuit overlay's choke squares: the pass makes them cluster anchors. */
	const CHOKE_PREFIX = 'pursuit:choke-';
	/** The pass's cadence while the idle orbit turns the camera (an orbit never ends a move). */
	const ORBIT_DECORATE_MS = 1000;
	/** Search around: objects within this of the selection (m). */
	const SEARCH_AROUND_M = 450;
	/** A followed object re-centres once it has moved this far (m). */
	const FOLLOW_RELAY_M = 40;

	/** The view the layers and the pass read (ctx.view()); rebuilt when its inputs change. */
	// chrome v3 draws a district-level report as a chip on the page, never a ring on the map (V3-SPEC §5.6)
	let mapView: MapView = { ...emptyView('v2'), noAreas: v3, focus: v3 };
	let mapViewSig = '';
	let mapViewVersion = 0;
	let decorateTimer: ReturnType<typeof setTimeout> | null = null;
	let decorateDue = 0;
	/** The marker under the pointer (v2 repaints it with the hover ring). */
	let hoverMarkId: string | null = null;
	/** Cluster bookkeeping from the last pass: lead → members, member → lead. */
	let clusterOf = new Map<string, { lead: string; members: string[] }>();
	let clusterMember = new Map<string, string>();
	/** The cluster a click spread out (its members fanned around the lead). */
	let spider: { lead: string; members: string[] } | null = null;
	/** What the pass last applied per marker (skip unchanged markers). */
	const appliedMark = new WeakMap<object, string>();
	const v2Labels = new Map<string, string>();
	const v2Arrows = new Set<string>();
	/** Measure and shape drawing state (lon/lat vertices). */
	let measurePts: Array<[number, number]> = [];
	let shapePts: Array<[number, number]> = [];
	/** Filter to shape: markers outside this polygon are hidden until cleared. */
	let shapeFilter = $state<Array<[number, number]> | null>(null);
	/** The OSM imagery layer laid over the ion aerial for Streets / Dark (keyed canvas). */
	let osmOverlay: unknown = null;
	let followAt: { lon: number; lat: number } | null = null;
	let removeMoveEnd: (() => void) | null = null;
	let removeCollection: (() => void) | null = null;
	let detachChrome: (() => void) | null = null;

	/** URNs linked to `urn` on the canvas: its registry links, a sighting's camera, a pursuit's chokes. */
	function relatedUrns(urn: string): Set<string> {
		const out = new Set<string>();
		const own = cityRegistry.get(urn);
		for (const l of own?.links ?? []) out.add(l);
		for (const e of cityRegistry.related(urn)) {
			out.add(e.urn);
			if (e.kind === 'sighting' || e.kind === 'recommendation') for (const l of e.links) out.add(l);
		}
		const plan = ops.interception;
		if (plan && (urn === `vehicle:${plan.vehicleId}` || urn === `event:${plan.eventId}`)) {
			for (const c of plan.chokes) out.add(`junction:${c.junctionId}`);
			out.add(`event:${plan.eventId}`);
			if (plan.vehicleId) out.add(`vehicle:${plan.vehicleId}`);
		}
		out.delete(urn);
		return out;
	}

	/** The objects that wear a decision dot (SPEC §5.4 units; one per object). A reported
	 * situation whose decision-support proposal is proposed AND unexpired waits too (R3):
	 * the set is the layers' PURE builder (layers/osint.ts cityDecisionUrns) over the live
	 * registry — the unit test asserts the waiting OSINT URN rides the view.decisions it
	 * feeds, which is what keeps the dot on a selected or clustered marker. */
	function decisionSet(enforcementOn: boolean): Set<string> {
		return cityDecisionUrns({
			recommendations: cityRegistry.byKind('recommendation'),
			stolen: stolenVehicles(),
			dispatches: cityRegistry.byKind('dispatch'),
			osint: cityRegistry.byKind('osint_event'),
			enforcementOn,
			now: Date.now(),
		});
	}

	/** Rebuild the view from its inputs; true when it changed (layers restyle, the pass reruns). */
	function rebuildView(input: {
		primary: string | null;
		items: readonly string[] | null;
		window: readonly [number, number] | null;
		protectedSet: ReadonlySet<string>;
		kinds: ReadonlySet<string> | null;
		enforcementOn: boolean;
	}): boolean {
		const items = input.items?.length ? [...input.items] : input.primary ? [input.primary] : [];
		const related = new Set<string>();
		for (const urn of items) for (const r of relatedUrns(urn)) related.add(r);
		for (const urn of items) related.delete(urn);
		const decisions = decisionSet(input.enforcementOn);
		const window = input.window && Number.isFinite(input.window[0]) && Number.isFinite(input.window[1]) ? ([input.window[0], input.window[1]] as const) : null;
		const sig = JSON.stringify([
			input.primary,
			items,
			[...related].sort(),
			window,
			[...input.protectedSet].sort(),
			input.kinds ? [...input.kinds].sort() : null,
			[...decisions].sort(),
		]);
		if (sig === mapViewSig) return false;
		mapViewSig = sig;
		mapView = {
			chrome: 'v2',
			noAreas: v3,
			focus: v3,
			selection: input.primary ?? items[0] ?? null,
			items,
			related,
			window,
			protected: input.protectedSet,
			kinds: input.kinds,
			decisions,
			version: ++mapViewVersion,
		};
		return true;
	}

	/** Run the decoration pass soon (coalesced). */
	function scheduleDecorate(delay = 60) {
		if (chrome !== 'v2' || destroyed) return;
		const due = performance.now() + delay;
		if (decorateTimer && due >= decorateDue) return;
		if (decorateTimer) clearTimeout(decorateTimer);
		decorateDue = due;
		decorateTimer = setTimeout(() => {
			decorateTimer = null;
			decorate();
		}, delay);
	}

	/** Ray-cast a canvas point onto the ground (lon/lat), or null (sky). */
	function groundAt(x: number, y: number): { lon: number; lat: number } | null {
		const C = window.Cesium;
		if (!viewer || !C) return null;
		try {
			const hit = viewer.camera.pickEllipsoid(new C.Cartesian2(x, y));
			const c = hit ? C.Cartographic.fromCartesian(hit) : undefined;
			return c ? { lon: radToDeg(c.longitude), lat: radToDeg(c.latitude) } : null;
		} catch {
			return null;
		}
	}

	function metresBetween(a: { lon: number; lat: number }, b: { lon: number; lat: number }): number {
		const k = Math.cos((((a.lat + b.lat) / 2) * Math.PI) / 180);
		return Math.hypot((b.lon - a.lon) * 111_320 * k, (b.lat - a.lat) * 110_540);
	}

	/** The scale bar: a round distance that spans ≤ 110 px at the bottom of the view. */
	function updateScale() {
		const canvas = viewer?.scene.canvas;
		if (!canvas) return;
		const w = canvas.clientWidth;
		const h = canvas.clientHeight;
		const y = Math.max(0, h - 48);
		const a = groundAt(w / 2 - 50, y);
		const b = groundAt(w / 2 + 50, y);
		if (!a || !b) {
			scaleBar = null;
			return;
		}
		const mPerPx = metresBetween(a, b) / 100;
		if (!(mPerPx > 0)) {
			scaleBar = null;
			return;
		}
		const nice = [5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10_000, 20_000, 50_000, 100_000];
		const d = [...nice].reverse().find((m) => m / mPerPx <= 110) ?? nice[0];
		scaleBar = { px: d / mPerPx, label: d >= 1000 ? `${d / 1000} km` : `${d} m` };
		try {
			cameraHeadingDeg = radToDeg(viewer!.camera.heading);
		} catch {
			// camera mid-teardown
		}
		if (!cursorAt) cursorCentre();
	}

	/** The readout's position when the pointer is off the map: the view's centre. */
	function cursorCentre() {
		const canvas = viewer?.scene.canvas;
		if (!canvas) return;
		const c = groundAt(canvas.clientWidth / 2, canvas.clientHeight / 2);
		centreAt = c;
	}
	let centreAt = $state<{ lon: number; lat: number } | null>(null);

	/** Point-in-polygon over lon/lat (ray casting). */
	function insidePolygon(p: readonly [number, number], poly: ReadonlyArray<readonly [number, number]>): boolean {
		let inside = false;
		for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
			const [xi, yi] = poly[i];
			const [xj, yj] = poly[j];
			if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) inside = !inside;
		}
		return inside;
	}

	/** An entity's ground lon/lat now (markers), or null. */
	function lonLatOf(e: CesiumEntity): [number, number] | null {
		const C = window.Cesium;
		if (!C || !viewer) return null;
		const world = readProp(e.position, viewer.clock.currentTime);
		const c = world ? C.Cartographic.fromCartesian(world) : undefined;
		return c ? [radToDeg(c.longitude), radToDeg(c.latitude)] : null;
	}

	/**
	 * Restyle one v2 marker in place: visibility, image (selected, decision
	 * dot, count chip, hover ring), tint alpha and the spider offset — only
	 * when something changed since the last pass.
	 */
	function applyMark(
		e: CesiumEntity,
		meta: MarkerMeta,
		s: { show: boolean; selected: boolean; decision: boolean; count: number; hover: boolean; alpha: number; spread: { x: number; y: number } | null },
	) {
		const C = window.Cesium;
		const bb = e.billboard;
		if (!C || !bb) return;
		const key = `${imageEpoch}|${s.show ? 1 : 0}|${s.selected ? 1 : 0}|${s.decision ? 1 : 0}|${s.count}|${s.hover ? 1 : 0}|${s.alpha.toFixed(2)}|${s.spread ? `${s.spread.x},${s.spread.y}` : ''}`;
		if (appliedMark.get(e) === key) return;
		appliedMark.set(e, key);
		bb.show = s.show;
		if (!s.show) return;
		const img = imageFor(meta, { selected: s.selected, decision: s.decision, count: s.count, hover: s.hover });
		if (img) {
			bb.image = img.url;
			bb.width = img.w;
			bb.height = img.h;
			bb.pixelOffset = new C.Cartesian2(img.offset.x + (s.spread?.x ?? 0), img.offset.y + (s.spread?.y ?? 0));
		}
		const white = C.Color.WHITE as { withAlpha?: (a: number) => unknown } | undefined;
		if (white?.withAlpha) bb.color = white.withAlpha(Math.max(0.05, Math.min(1, s.alpha)));
	}

	type V2Mark = {
		e: CesiumEntity;
		meta: MarkerMeta;
		st: ReturnType<typeof markerStyle>;
		/** The projected ground position, and where the mark is drawn (pin head, spider). */
		win: { x: number; y: number } | null;
		at: { x: number; y: number } | null;
		shown: boolean;
		alpha: number;
	};

	/**
	 * THE V2 PASS — on camera-move end, data change, view change and hover,
	 * never per frame (SPEC §13.5): reads every tagged marker, fades and dims
	 * it by the view, clusters the 21 px discs closer than 22 px (the lead
	 * wears the count chip; a spread cluster fans its members out), marks the
	 * selection and the waiting decisions, places the labels greedily against
	 * the drawn discs, and lays direction arrows on the selected track's spans
	 * longer than 60 px.
	 */
	function decorate() {
		const C = window.Cesium;
		const v = viewer;
		if (!C || !v || chrome !== 'v2' || phase !== 'ready') return;
		const time = v.clock.currentTime;
		const W = v.scene.canvas.clientWidth;
		const H = v.scene.canvas.clientHeight;
		const view = mapView;
		const toWin = (world: unknown) => {
			const w = world ? C.SceneTransforms.worldToWindowCoordinates(v.scene, world) : undefined;
			return w && Number.isFinite(w.x) && Number.isFinite(w.y) ? { x: w.x, y: w.y } : null;
		};
		const onScreen = (p: { x: number; y: number } | null) => !!p && p.x >= -24 && p.y >= -24 && p.x <= W + 24 && p.y <= H + 24;
		const marks: V2Mark[] = [];
		const chokes = new Set<string>();
		for (const e of v.entities.values) {
			const meta = markerMeta(e);
			if (meta?.urn && e.id.startsWith(CHOKE_PREFIX)) chokes.add(meta.urn);
		}
		for (const e of v.entities.values) {
			const meta = markerMeta(e);
			if (!meta) continue;
			const st = markerStyle({ urn: meta.urn, kind: meta.kind, t: meta.t ?? null }, view);
			// a junction dot under a choke square steps aside; filter to shape hides the outside
			if (meta.shape === 'dot' && meta.kind === 'junction' && meta.urn && chokes.has(meta.urn)) st.show = false;
			if (shapeFilter && st.show) {
				const at = lonLatOf(e);
				if (at && !insidePolygon(at, shapeFilter)) st.show = false;
			}
			const win = toWin(readProp(e.position, time));
			const at = win && meta.click ? { x: win.x + meta.click.x, y: win.y + meta.click.y } : win;
			marks.push({ e, meta, st, win, at, shown: false, alpha: st.alpha * (meta.passed ? MAP_OPACITY.passed : 1) });
		}

		// clusters: the 21 px discs closer than 22 px merge (the selection's own lead);
		// a pursuit's choke square leads whatever plain marker sits at its junction
		// (a camera there wears the square's count chip and spreads out on a click),
		// so the square is never drawn under it
		const isChoke = (m: V2Mark) => m.e.id.startsWith(CHOKE_PREFIX);
		const anchors = marks.filter((m) => isChoke(m) && m.st.show && onScreen(m.at)).map((m) => ({ id: m.e.id, x: m.at!.x, y: m.at!.y }));
		const pts = marks
			.filter((m) => m.meta.cluster && !isChoke(m) && m.st.show && onScreen(m.at))
			.map((m) => ({ id: m.e.id, x: m.at!.x, y: m.at!.y, lead: m.st.selected || m.st.related, weight: (m.st.decision ? 2 : 0) + (m.meta.kind === 'camera' ? 0 : 1) }));
		clusterOf = new Map();
		clusterMember = new Map();
		for (const c of clusterAround(anchors, pts, CLUSTER_RADIUS_PX, (p) => !!p.lead || (p.weight ?? 0) >= 2)) {
			if (c.members.length < 2) continue;
			clusterOf.set(c.lead, { lead: c.lead, members: c.members });
			for (const id of c.members) clusterMember.set(id, c.lead);
		}
		if (spider && !clusterOf.has(spider.lead)) spider = null;
		const spread = spider ? spiderOffsets(spider.members.length - 1) : [];
		// a waiting member absorbed under another lead keeps its dot: the LEAD carries the
		// decision mark when any of its members waits (fix round 2, review note on the
		// clustering) — the members' URNs ride the view's decision set
		const urnById = new Map(marks.map((m) => [m.e.id, m.meta.urn] as const));
		const memberWaits = (id: string) => view.decisions.has(urnById.get(id) ?? '');

		const occupied: Box[] = [];
		for (const m of marks) {
			const lead = clusterMember.get(m.e.id);
			const spreadOut = !!spider && lead === spider.lead;
			const isLead = lead === m.e.id;
			let show = m.st.show;
			let count = 0;
			let off: { x: number; y: number } | null = null;
			if (lead && !isLead && !spreadOut) show = false;
			if (lead && isLead && !spreadOut) count = clusterOf.get(m.e.id)?.members.length ?? 0;
			if (spreadOut && !isLead) off = spread[spider!.members.indexOf(m.e.id) - 1] ?? null;
			applyMark(m.e, m.meta, {
				show,
				selected: m.st.selected,
				decision: markShowsDecision(m.st.decision, isLead, spreadOut, clusterOf.get(m.e.id)?.members, memberWaits),
				count,
				hover: hoverMarkId === m.e.id,
				alpha: m.alpha,
				spread: off,
			});
			m.shown = show;
			if (show && m.at && onScreen(m.at)) {
				if (off) m.at = { x: m.at.x + off.x, y: m.at.y + off.y };
				const r = m.meta.radius ?? (m.meta.shape === 'dot' ? (m.meta.r ?? 4.5) + 2 : MARKER.radius);
				occupied.push(discBox(m.at.x, m.at.y, r));
			}
		}
		occupied.push(...chromeBoxes());
		placeV2Labels(marks, occupied, W, H, view);
		placeV2Arrows(W, H);
	}

	/** The chrome floating over the map (toolbar, panels, readout, navigation, credits) as keep-out boxes. */
	function chromeBoxes(): Box[] {
		const canvas = viewer?.scene.canvas;
		const wrap = container?.parentElement;
		if (!canvas || !wrap) return [];
		const origin = canvas.getBoundingClientRect();
		const out: Box[] = [];
		const els = [...wrap.querySelectorAll('.ge-hud.v2 .toolbar, .ge-hud.v2 .flash, .ge-hud.v2 .tool-hint, .v2-top > *, .v2-panel, .v2-legend, .v2-nav, .v2-readout, .cesium-viewer-bottom')];
		// chrome v3: the page's own panels over the canvas (the Now panel, the chips, the card, the tools)
		if (v3) els.push(...document.querySelectorAll('[data-ge-keepout]'));
		for (const el of els) {
			const r = el.getBoundingClientRect();
			if (r.width > 0 && r.height > 0) out.push({ x: r.left - origin.left - 4, y: r.top - origin.top - 4, w: r.width + 8, h: r.height + 8 });
		}
		return out;
	}

	/** Labels: what the policy shows, placed greedily; a hovered label always shows. */
	function placeV2Labels(marks: V2Mark[], occupied: Box[], W: number, H: number, view: MapView) {
		const C = window.Cesium;
		const v = viewer;
		if (!C || !v) return;
		const items: LabelItem[] = [];
		const byId = new Map<string, { m: V2Mark; img: MapImage | null }>();
		for (const m of marks) {
			const parts = m.meta.label;
			if (!m.shown || !m.at || !parts?.length) continue;
			const hovered = hoverMarkId === m.e.id;
			const when = m.meta.labelWhen ?? 'hover';
			const want =
				hovered ||
				when === 'always' ||
				(when === 'selected' && (m.st.selected || (!!m.meta.labelWith && view.items.includes(m.meta.labelWith))));
			if (!want) continue;
			const img = labelImage(parts, { lock: m.meta.labelLock });
			if (!img) continue;
			items.push({
				id: m.e.id,
				x: m.at.x,
				y: m.at.y,
				w: img.w,
				h: img.h,
				r: m.meta.radius ?? MARKER.radius,
				prefer: m.meta.labelPrefer,
				priority: hovered ? 1000 : (m.meta.labelPriority ?? 0),
			});
			byId.set(m.e.id, { m, img });
		}
		const { placed, dropped } = placeLabels(items, occupied, { width: W, height: H });
		// a hovered label that fits nowhere still shows (to its right): the pointer asked for it
		if (hoverMarkId && dropped.includes(hoverMarkId)) {
			const it = items.find((i) => i.id === hoverMarkId);
			if (it) placed.set(it.id, { id: it.id, pos: 'r', box: { x: it.x + (it.r ?? 0) + 4, y: it.y - it.h / 2, w: it.w, h: it.h } });
		}
		const keep = new Set<string>();
		for (const [id, p] of placed) {
			const hit = byId.get(id);
			if (!hit?.img || !hit.m.win) continue;
			const { m, img } = hit;
			const labelId = `${V2_LABEL}${id}`;
			keep.add(id);
			const offset = new C.Cartesian2(p.box.x + p.box.w / 2 - m.win!.x, p.box.y + p.box.h / 2 - m.win!.y);
			const white = C.Color.WHITE as { withAlpha?: (a: number) => unknown } | undefined;
			const tint = white?.withAlpha ? white.withAlpha(Math.max(0.3, m.alpha)) : undefined;
			const existing = v.entities.getById(labelId) as (CesiumEntity & { position?: unknown }) | undefined;
			if (existing?.billboard) {
				// a layer's redraw replaces its marker entity: the label follows the new one's position
				if (existing.position !== m.e.position) existing.position = m.e.position;
				existing.billboard.image = img.url;
				existing.billboard.width = img.w;
				existing.billboard.height = img.h;
				existing.billboard.pixelOffset = offset;
				if (tint) existing.billboard.color = tint;
				existing.billboard.show = true;
			} else {
				v.entities.add({
					id: labelId,
					position: m.e.position,
					billboard: imageBillboard(C, img, { w: img.w, h: img.h }, { pixelOffset: offset, ...(tint ? { color: tint } : {}) }),
				});
			}
			v2Labels.set(id, labelId);
		}
		for (const [id, labelId] of [...v2Labels]) {
			if (keep.has(id)) continue;
			v.entities.removeById(labelId);
			v2Labels.delete(id);
		}
	}

	/**
	 * Direction arrows on the selected track's spans drawn longer than 60 px
	 * (SPEC §5.3); none while a kind filter leaves vehicles out. Each arrow
	 * is a chevron DRAPED on the surface the track drapes on (terrain or the
	 * 3D tiles), so it sits on the line at every pitch, and is keyed by its
	 * span's geometry and scale (trackArrows): when the reads change (a read
	 * in, a read out of the 30-min pass, another window) or a zoom re-sizes
	 * it, the arrow of a span no longer drawn goes and the new span gets its
	 * own — none is ever left on a span the track no longer has.
	 */
	function placeV2Arrows(W: number, H: number) {
		const C = window.Cesium;
		const v = viewer;
		if (!C || !v) return;
		const want = new Map<string, TrackArrow>();
		const project = (lon: number, lat: number) => C.SceneTransforms.worldToWindowCoordinates(v.scene, C.Cartesian3.fromDegrees(lon, lat, 0));
		for (const e of kindShown(mapView, 'vehicle') ? v.entities.values : []) {
			const track = trackMeta(e);
			if (!track) continue;
			for (const a of trackArrows(track.coords, project, { width: W, height: H })) want.set(`${V2_ARROW}${e.id}:${a.id}`, a);
		}
		for (const id of [...v2Arrows]) {
			if (want.has(id)) continue;
			v.entities.removeById(id);
			v2Arrows.delete(id);
		}
		if (![...want.keys()].some((id) => !v2Arrows.has(id))) return;
		const material = C.PolylineOutlineMaterialProperty
			? new C.PolylineOutlineMaterialProperty({
					color: C.Color.fromCssColorString(mapInk('alert')),
					outlineColor: C.Color.fromCssColorString(mapInk('casing')),
					// Cesium's outline takes both edges together: the core = width − outlineWidth
					outlineWidth: TRACK_ARROW.width - TRACK_ARROW.core,
				})
			: C.Color.fromCssColorString(mapInk('alert'));
		for (const [id, a] of want) {
			if (v2Arrows.has(id)) continue;
			v.entities.add({
				id,
				polyline: drapedPolyline(C, {
					positions: groundPath(C, a.chevron),
					width: C.PolylineOutlineMaterialProperty ? TRACK_ARROW.width : TRACK_ARROW.core,
					material,
					// above the track (and the measure sketch); its own ground batch, so a new arrow never rebuilds the track
					z: DRAPE_Z.pursuit + 2,
				}),
			});
			v2Arrows.add(id);
		}
	}

	// ── v2 tools: measure, shape (select within / filter to), search around ──

	function setTool(next: MapTool, mode?: ShapeMode) {
		tool = next;
		if (mode) shapeMode = mode;
		measurePts = [];
		shapePts = [];
		redrawToolSketch();
		toolHint = next === 'measure' ? t(ops.lang, 'map_tool_measure_hint') : next === 'shape' ? t(ops.lang, 'map_tool_shape_hint') : null;
		if (container) container.style.cursor = next === 'select' ? '' : 'crosshair';
	}

	/** The measure line or the shape outline being drawn, on the ground. */
	function redrawToolSketch() {
		const C = window.Cesium;
		const v = viewer;
		if (!C || !v) return;
		for (const e of [...v.entities.values]) {
			if (e.id.startsWith(V2_MEASURE) || (e.id.startsWith(V2_SHAPE) && !(shapeFilter && e.id === `${V2_SHAPE}filter`))) v.entities.removeById(e.id);
		}
		const sketch = (prefix: string, pts: Array<[number, number]>, closed: boolean, dashed: boolean, inkRole: 'label-ink' | 'select') => {
			if (pts.length < 2) return;
			const path = closed ? [...pts, pts[0]] : pts;
			const color = C.Color.fromCssColorString(mapInk(inkRole));
			v.entities.add({
				id: `${prefix}line`,
				polyline: drapedPolyline(C, {
					positions: groundPath(C, path),
					width: 2,
					material: dashed ? new C.PolylineDashMaterialProperty({ color, dashLength: 10 }) : color,
					z: DRAPE_Z.pursuit + 1,
				}),
			});
		};
		if (tool === 'measure' && measurePts.length) {
			sketch(V2_MEASURE, measurePts, false, false, 'label-ink');
			let total = 0;
			for (let i = 1; i < measurePts.length; i++) {
				total += metresBetween({ lon: measurePts[i - 1][0], lat: measurePts[i - 1][1] }, { lon: measurePts[i][0], lat: measurePts[i][1] });
			}
			const last = measurePts[measurePts.length - 1];
			const text = t(ops.lang, 'map_measure_total', total >= 1000 ? `${(total / 1000).toFixed(2)} km` : `${Math.round(total)} m`);
			const img = labelImage([{ text }]);
			if (img && measurePts.length > 1) {
				v.entities.add({
					id: `${V2_MEASURE}label`,
					position: ground(C, last[0], last[1]),
					billboard: imageBillboard(C, img, { w: img.w, h: img.h }, { pixelOffset: new C.Cartesian2(img.w / 2 + 8, 0) }),
				});
			}
		}
		if (tool === 'shape' && shapePts.length) sketch(V2_SHAPE, shapePts, shapePts.length > 2, true, 'select');
	}

	/** Every tagged marker URN inside the polygon (deduplicated, at most 50). */
	function urnsInside(poly: ReadonlyArray<readonly [number, number]>): string[] {
		if (!viewer) return [];
		const out: string[] = [];
		for (const e of viewer.entities.values) {
			const meta = markerMeta(e);
			if (!meta?.urn || out.includes(meta.urn)) continue;
			const at = lonLatOf(e);
			if (at && insidePolygon(at, poly)) out.push(meta.urn);
			if (out.length >= 50) break;
		}
		return out;
	}

	/** Hand a multi-selection to the page (onlasso); without one, emphasise them on the canvas. */
	function selectUrns(urns: string[]) {
		if (!urns.length) return;
		if (onlasso) onlasso(urns);
		else highlightUrns(urns);
	}

	function closeShape() {
		const poly = shapePts.length >= 3 ? [...shapePts] : null;
		shapePts = [];
		if (!poly) {
			redrawToolSketch();
			return;
		}
		if (shapeMode === 'filter') {
			shapeFilter = poly;
			const C = window.Cesium;
			if (C && viewer) {
				viewer.entities.removeById(`${V2_SHAPE}filter`);
				viewer.entities.add({
					id: `${V2_SHAPE}filter`,
					polyline: drapedPolyline(C, {
						positions: groundPath(C, [...poly, poly[0]]),
						width: 2,
						material: new C.PolylineDashMaterialProperty({ color: C.Color.fromCssColorString(mapInk('select')), dashLength: 10 }),
						z: DRAPE_Z.pursuit + 1,
					}),
				});
			}
			focusFlash(t(ops.lang, 'map_shape_filtered', urnsInside(poly).length));
		} else {
			const urns = urnsInside(poly);
			selectUrns(urns);
			focusFlash(t(ops.lang, 'map_shape_selected', urns.length));
		}
		setTool('select');
		scheduleDecorate(0);
	}

	function clearShapeFilter() {
		shapeFilter = null;
		viewer?.entities.removeById(`${V2_SHAPE}filter`);
		scheduleDecorate(0);
	}

	/** Search around: the objects within SEARCH_AROUND_M of the selection join it. */
	function searchAround() {
		const urn = selection.current;
		const at = urn ? knownPosition(urn) : null;
		if (!urn || !at || !viewer) return;
		const out = [urn];
		for (const e of viewer.entities.values) {
			const meta = markerMeta(e);
			if (!meta?.urn || out.includes(meta.urn)) continue;
			const p = lonLatOf(e);
			if (p && metresBetween(at, { lon: p[0], lat: p[1] }) <= SEARCH_AROUND_M) out.push(meta.urn);
			if (out.length >= 50) break;
		}
		selectUrns(out);
	}

	/** A click while a tool is active (true: the tool took it). */
	function toolClick(position: { x: number; y: number }): boolean {
		if (tool === 'select') return false;
		const at = groundAt(position.x, position.y);
		if (!at) return true;
		if (tool === 'measure') measurePts = [...measurePts, [at.lon, at.lat]];
		else shapePts = [...shapePts, [at.lon, at.lat]];
		redrawToolSketch();
		return true;
	}

	function toolDoubleClick() {
		if (tool === 'shape') closeShape();
		else if (tool === 'measure') {
			// the measured line stays until the tool is left
			toolHint = null;
		}
	}

	// ── v2 follow, base map, the chrome state for the LayerTree ─────────────

	/** Follow: hold the camera on the selection (an event's spine locks; anything else is followed as it moves). */
	function toggleFollow() {
		if (godsEye.subjectLockId || lockFlight || followUrn) {
			followUrn = null;
			followAt = null;
			releaseSubject({ why: 'the operator released the follow' });
			return;
		}
		const urn = selection.current;
		if (!urn) return;
		const parsed = parseUrn(urn);
		if (parsed?.kind === 'event') {
			const ev = ops.events.find((e) => e.eventId === parsed.id);
			const c = ev ? eventCentroid(ev, godsEye.segmentById) : null;
			if (ev && c) {
				lockOn(ev.eventId, c);
				return;
			}
		}
		const at = knownPosition(urn);
		if (!at) {
			focusFlash(t(ops.lang, 'map_follow_no_position', objectName(urn)));
			return;
		}
		followUrn = urn;
		followAt = { lon: at.lon, lat: at.lat };
		if (tourIndex != null) stopTour();
		lastInteraction = performance.now();
		flyFrame(at.lon, at.lat, ENTITY_VIEW.range, 0, ENTITY_VIEW.pitchDeg, ENTITY_VIEW.flightSec);
	}

	/** An object's name in operator copy: its registry label (marks masked), else null (never a raw URN). */
	function objectName(urn: string): string | null {
		const label = cityRegistry.get(urn)?.label;
		return label ? displayText(label, ops.officerOn) : null;
	}

	/** 1 Hz: a followed object that moved is re-centred (never per frame). */
	function followTick() {
		if (!followUrn) return;
		if (selection.current !== followUrn) {
			followUrn = null;
			followAt = null;
			return;
		}
		const at = knownPosition(followUrn);
		if (!at || !followAt || performance.now() < flightUntil) return;
		if (metresBetween(at, followAt) < FOLLOW_RELAY_M) return;
		followAt = { lon: at.lon, lat: at.lat };
		const cam = cameraState();
		flyFrame(at.lon, at.lat, ENTITY_VIEW.range, cam?.heading ?? 0, ENTITY_VIEW.pitchDeg, 0.8);
	}

	/** The photoreal base map can be shown (the ion key and its layer). */
	function photorealAvailable(): boolean {
		return godsEye.imageryMode === 'ion-photoreal' && !!godsEye.imageryToken && instances.has('photoreal-3d');
	}

	/**
	 * Base map (v2 LayerTree): Photoreal = the photoreal-3d layer; Streets and
	 * Dark = the OSM raster, plain or re-graded — the keyless base layer
	 * itself, or an OSM layer over the ion aerial on the keyed canvas.
	 */
	function applyBasemap(style: BasemapStyle) {
		const C = window.Cesium;
		const v = viewer;
		if (!C || !v || chrome !== 'v2') return;
		const next: BasemapStyle = style === 'photoreal' && !photorealAvailable() ? 'dark' : style;
		setLayerEnabled('photoreal-3d', next === 'photoreal');
		// chrome v3: the night city map (deeper and quieter than the Analyst map's dark re-grade)
		const grade = next === 'streets' ? STREETS_GRADE : v3 ? V3_NIGHT : DARK_REGRADE;
		try {
			if (basemapId === 'osm-keyless') {
				applyGrade(v.scene.imageryLayers.get(0), grade);
			} else if (next === 'photoreal') {
				// chrome v3 keeps the OSM night map showing until the photoreal city's first tiles land (never a blank map)
				if (osmOverlay && !(v3 && !photorealReady(stats['photoreal-3d']))) {
					v.scene.imageryLayers.remove(osmOverlay, true);
					osmOverlay = null;
				}
			} else if (osmOverlay) {
				applyGrade(osmOverlay, grade);
			} else {
				osmOverlay = createOsmImageryLayer(C, grade);
				v.scene.imageryLayers.add(osmOverlay);
			}
		} catch {
			// a stumbling imagery layer keeps what it had; the choice still shows
		}
		basemapStyle = next;
		publishChrome();
	}

	/** chrome v3: the V3 map page's tool buttons (mapChrome.act) run the canvas's own tools. */
	function v3Act(what: MapAct, arg?: unknown) {
		if (what === 'zoom') zoomBy(arg === -1 ? -1 : 1);
		else if (what === 'north') resetNorth();
		else if (what === 'home') flyHome(1.2);
		else if (what === 'follow') toggleFollow();
		else if (what === 'measure') setTool(tool === 'measure' ? 'select' : 'measure');
		else if (what === 'sensor' && SENSOR_ORDER.includes(arg as SensorMode)) {
			setSensor(arg as SensorMode);
			updateHash();
		} else if (what === '3d') {
			// the photoreal city, seen at an angle; back to the city map from above (the same ground point)
			applyBasemap(arg === true ? 'photoreal' : 'dark');
			const canvas = viewer?.scene.canvas;
			const cam = cameraState();
			if (!canvas || !cam) return;
			const at = groundAt(canvas.clientWidth / 2, canvas.clientHeight / 2) ?? cam;
			markInteraction();
			takeCamera();
			if (basemapStyle === 'photoreal') flyFrame(at.lon, at.lat, HOME_VIEW_3D.range, cam.heading, HOME_VIEW_3D.pitchDeg, 1.2);
			else flyFrame(at.lon, at.lat, Math.max(2500, Math.min(HOME_VIEW.range, cam.alt * 1.4)), 0, -60, 1);
		}
	}

	/** Publish the LayerTree's rows and the base map (map-state.svelte.ts). */
	function publishChrome() {
		if (chrome !== 'v2') return;
		const lang = ops.lang;
		const rows: LayerRow[] = GODS_EYE_LAYERS.filter((l) => !l.basemap && instances.has(l.id)).map((l) => {
			const st = stats[l.id];
			const key = `map_layer_${l.id}`;
			const label = t(lang, key);
			const count = st?.count ?? 0;
			const detail = st?.detail ?? {};
			return {
				id: l.id,
				label: label === key ? l.name : label,
				group: l.group,
				count,
				hint: st?.hint ?? l.name,
				error: st?.error ?? null,
				visible: activeLayers.has(l.id),
				empty: count === 0 && !st?.loading,
				simulated: (detail.simulated ?? 0) > 0,
				emulated: (detail.emulated ?? 0) > 0,
				paused: replaySuspended.includes(l.id),
			};
		});
		mapChrome.rows = rows;
		mapChrome.basemap = basemapStyle;
		mapChrome.lang = lang;
		mapChrome.photoreal = {
			available: photorealAvailable(),
			hint: stats['photoreal-3d']?.hint ?? t(lang, 'map_basemap_needs_key'),
		};
		mapChrome.legendOpen = legendOpen;
	}

	/** The v2 hover: repaint the marker, list a cluster's members, follow the readout. */
	function hoverV2(position: { x: number; y: number }, entity: CesiumEntity | null) {
		const meta = entity ? markerMeta(entity) : null;
		const id = meta && entity ? entity.id : null;
		if (id !== hoverMarkId) {
			hoverMarkId = id;
			scheduleDecorate(0);
		}
		const cluster = id ? clusterOf.get(id) : null;
		if (cluster && cluster.members.length > 1 && spider?.lead !== id && viewer) {
			const names = cluster.members.map((mid) => {
				const e = viewer!.entities.getById(mid);
				const m = e ? markerMeta(e) : null;
				return m?.label?.length ? labelText(m.label) : (m?.urn ?? mid);
			});
			hoverList = { x: position.x, y: position.y, title: t(ops.lang, 'map_cluster_list', names.length), items: names.slice(0, 12) };
		} else if (hoverList) {
			hoverList = null;
		}
		cursorAt = groundAt(position.x, position.y);
	}

	onMount(() => {
		const settle = makeReadyHook();
		detachFocus = focus.attach();
		lastInteraction = performance.now();
		ops.start(); // events + band feed the events layer / AMA chip
		godsEye.start();
		clockTimer = setInterval(tick, 1000);

		(async () => {
			if (!container) return;
			if (!webglAvailable()) {
				unavailableReason = 'WebGL is unavailable in this browser';
				phase = 'unavailable';
				settle(false, unavailableReason);
				return;
			}
			if (!window.Cesium) {
				try {
					const link = document.createElement('link');
					link.rel = 'stylesheet';
					link.href = '/cesium/Widgets/widgets.css';
					document.head.appendChild(link);
					await loadScript('/cesium/Cesium.js');
					if (destroyed) return;
				} catch (err) {
					unavailableReason = `Cesium bundle not served (${
						err instanceof Error ? err.message : String(err)
					}) — dev servers need static/cesium (see infra/docker/Dockerfile.command-deck)`;
					phase = 'unavailable';
					settle(false, unavailableReason);
					return;
				}
			}
			const cesium = window.Cesium!;
			cesiumRef = cesium;
			try {
				await godsEye.pollImageryMode();
				if (destroyed) return;
				const viewerOpts = {
					baseLayerPicker: false,
					geocoder: false,
					homeButton: false,
					sceneModePicker: false,
					navigationHelpButton: false,
					animation: false,
					timeline: false,
					fullscreenButton: false,
					infoBox: false,
					selectionIndicator: false,
					requestRenderMode: false,
					contextOptions: { webgl: { preserveDrawingBuffer: true } },
				};
				const viewerWith = (b: Basemap) =>
					new cesium.Viewer(container!, {
						...viewerOpts,
						baseLayer: b.baseLayer,
						...(b.terrain ? { terrain: b.terrain } : { terrainProvider: b.terrainProvider }),
					});

				// The ion upgrade, when keyed — any synchronous failure (API drift,
				// constructor errors) lands on the keyless basemap instead of
				// taking the canvas down; async failures are watched below.
				let basemap: Basemap | null = null;
				if (godsEye.imageryMode === 'ion-photoreal' && godsEye.imageryToken) {
					try {
						// chrome v3: the natural aerial imagery, ungraded (V3-P4C: no tint on the satellite picture)
						const ion = createIonBasemap(cesium, godsEye.imageryToken, v3 ? STREETS_GRADE : undefined);
						viewer = viewerWith(ion);
						basemap = ion;
					} catch (err) {
						basemapNote = `ion upgrade failed (${
							err instanceof Error ? err.message : String(err)
						}) — keyless OSM fallback`;
						viewer = null;
						container.replaceChildren(); // drop a half-built widget
					}
				}
				if (!viewer || !basemap) {
					basemap = createKeylessBasemap(cesium);
					viewer = viewerWith(basemap);
				}
				basemapId = basemap.id;
				prepareGround(cesium, viewer);
				watchIonBasemap(cesium, viewer, basemap);
				watchTileErrors(viewer);

				// Real-time tilesLoaded publishing: the queue-depth event fires
				// as imagery loads, so the test snapshot (and any observer) sees
				// the moment the globe settles instead of waiting for the next
				// layer-refresh publish.
				const globeEvents = viewer.scene.globe as unknown as {
					tileLoadProgressEvent?: CesiumEvent<[number]>;
				};
				if (globeEvents.tileLoadProgressEvent) {
					removeTileProgress = globeEvents.tileLoadProgressEvent.addEventListener((remaining) => {
						if (snapHook) snapHook.tilesLoaded = remaining === 0;
						if (remaining === 0) releaseStars();
					});
				}

				applySensorStage(cesium, viewer);
				restoreFromHash(cesium, viewer);

				// Registry lifecycle.
				instances = new Map();
				for (const layer of GODS_EYE_LAYERS) {
					const ctx = { cesium, viewer, fetchJson, notify: refreshStats, chrome, view: () => mapView };
					const inst = layer.create(ctx);
					await inst.status();
					if (destroyed) return; // onDestroy already tore down the viewer + the layers so far
					inst.init(ctx);
					instances.set(layer.id, inst);
				}
				for (const layer of GODS_EYE_LAYERS) {
					if (activeLayers.has(layer.id)) instances.get(layer.id)?.activate();
				}

				// The pursuit and replay overlays build on first use instead (see
				// ensurePursuitOverlay/ensureReplayOverlay); the halo is first paint.
				addHalo(cesium, viewer);

				// Picking (pick card + board selection) and hover highlight.
				const hh = new cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
				hh.setInputAction((movement) => {
					if (movement.position) onPick(movement.position);
				}, cesium.ScreenSpaceEventType.LEFT_CLICK);
				hh.setInputAction((movement) => {
					if (movement.endPosition) onHover(movement.endPosition);
				}, cesium.ScreenSpaceEventType.MOUSE_MOVE);
				const dbl = cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK;
				if (chrome === 'v2' && dbl != null) {
					// v2: a double-click closes a shape (Cesium's own double-click would track the entity)
					viewer.cesiumWidget?.screenSpaceEventHandler?.removeInputAction(dbl);
					hh.setInputAction(() => toolDoubleClick(), dbl);
				}
				handler = hh;

				// Interaction hands the camera back from the orbit/tour (capture:
				// before Cesium's own handlers see the gesture).
				container.addEventListener('pointerdown', onPointerDown, { passive: true, capture: true });
				container.addEventListener('pointermove', onPointerMove, { passive: true, capture: true });
				container.addEventListener('pointerup', onPointerUp, { passive: true, capture: true });
				container.addEventListener('wheel', onWheel, { passive: true, capture: true });

				// Wheel-out ceiling: an unbounded zoom once parked the camera
				// 2.8e13 m out until the idle guard flew it home.
				viewer.scene.screenSpaceCameraController.maximumZoomDistance = MAX_ZOOM_M;
				viewer.camera.percentageChanged = 0.05;
				// the v2 pass runs on camera-move END (below), never per camera change
				// (SPEC §13.5); a continuous motion with no end (the idle orbit)
				// reruns it at ORBIT_DECORATE_MS from orbitTick
				removeCameraListener = viewer.camera.changed.addEventListener(() => updateHash());
				removePreUpdate = viewer.scene.preUpdate.addEventListener(orbitTick);
				if (chrome === 'v2') {
					// the v2 pass: camera-move end, a layer's redraw (its own drawings excepted)
					removeMoveEnd =
						viewer.camera.moveEnd?.addEventListener(() => {
							spider = null;
							updateScale();
							scheduleDecorate(0);
						}) ?? null;
					removeCollection =
						viewer.entities.collectionChanged?.addEventListener((_c, added, removed) => {
							if ([...added, ...removed].some((e) => !e.id.startsWith(V2_PREFIX))) scheduleDecorate();
						}) ?? null;
					container.addEventListener('pointerleave', onPointerLeave, { passive: true });
					const bar = container.querySelector('.cesium-viewer-bottom');
					if (bar && typeof ResizeObserver === 'function') {
						creditsObserver = new ResizeObserver(() => {
							creditsH = Math.max(18, Math.round(bar.getBoundingClientRect().height));
						});
						creditsObserver.observe(bar);
					}
					detachChrome = mapChrome.attach({
						setLayer: (id, on) => setLayerEnabled(id, on),
						setBasemap: (style) => applyBasemap(style),
						toggleLegend: (open) => {
							legendOpen = open ?? !legendOpen;
							publishChrome();
						},
						act: v3 ? v3Act : undefined,
					});
					void ensureMapFonts().then((ok) => {
						if (!ok || destroyed) return;
						clearMapImages();
						imageEpoch++;
						scheduleDecorate(0);
					});
					basemapStyle = activeLayers.has('photoreal-3d') && photorealAvailable() ? 'photoreal' : 'dark';
					applyBasemap(basemapStyle);
				}

				hudTimer = setInterval(refreshStats, 2000);
				declutterTimer = setInterval(declutterLabels, DECLUTTER_MS);
				// FLIR coherent-noise clock.
				timeTimer = setInterval(() => {
					if (stage?.uniforms) stage.uniforms['time'] = performance.now() / 1000;
				}, 100);

				refreshStats();
				phase = 'ready';
				settle(true);
				if (chrome === 'v2') {
					updateScale();
					scheduleDecorate(0);
				}
			} catch (err) {
				if (destroyed) return;
				unavailableReason = `viewer failed: ${err instanceof Error ? err.message : String(err)}`;
				phase = 'unavailable';
				settle(false, unavailableReason);
			}
		})();
	});

	// Selection follow (wall /ops): tracks the selection id (+ readiness and
	// whether its spine geometry exists) — never the 5 s events array — and
	// flies once per selected id. A released subject is not re-flown, here
	// or on the next view's canvas (focus.released), until the selection
	// moves to another event.
	let selectedHasSpine = $derived.by(() => {
		const id = ops.selectedEventId;
		const ev = id ? ops.events.find((e) => e.eventId === id) : undefined;
		return ev ? eventCentroid(ev, godsEye.segmentById) !== null : false;
	});

	$effect(() => {
		const id = ops.selectedEventId;
		const ready = phase === 'ready' && selectedHasSpine;
		untrack(() => {
			// A new selection forgets an older RELEASE: re-selecting that
			// subject later follows it again (a transient null selection
			// while the board reloads does not count as a new one).
			if (id && focus.released && focus.released !== id) focus.released = null;
			if (!ready || !id || !godsEye.followSelection || id === lastFollowedId || id === focus.released) return;
			followSubject(id);
		});
	});

	// City Command home, late: the fused picture answered after the canvas
	// opened on the city centre — settle onto the live action once, unless
	// the operator (or a selection, tour or focus) has the camera already.
	$effect(() => {
		void cityRegistry.version;
		const ready = phase === 'ready';
		untrack(() => {
			if (!actionHomeAt || !ready) return;
			const since = actionHomeAt;
			const untouched = lastInteraction <= since && !selection.current && tourIndex == null && !lockFlight;
			if (!untouched || performance.now() - since > ACTION_VIEW.settleMs) {
				actionHomeAt = 0;
				return;
			}
			const action = actionFrame();
			if (!action) return;
			actionHomeAt = 0;
			flyFrame(action.lon, action.lat, action.range, ACTION_VIEW.headingDeg, actionPitchDeg(), ACTION_VIEW.flightSec);
		});
	});

	// Focus bus: each request made since this canvas mounted flies + locks
	// on landing (or reports why it could not). lastFocusSeq starts at the
	// bus's seq at mount, so the previous view's request is never replayed.
	$effect(() => {
		const seq = focus.seq;
		const current = phase;
		if (seq === 0 || seq === lastFocusSeq || current === 'loading') return;
		lastFocusSeq = seq;
		untrack(() => {
			if (current === 'unavailable') {
				focus.settle(seq, 'no-canvas', unavailableReason);
				return;
			}
			if (focus.eventId) runFocus(seq, focus.eventId);
		});
	});

	// CHROME V2: the view the layers and the pass read — the selection (one or
	// many), the time window, the protected objects, the kind filter and the
	// waiting decisions. A change restyles the layers (no fetch) and reruns
	// the pass; an unchanged rebuild (a registry poll) costs a signature.
	$effect(() => {
		if (chrome !== 'v2') return;
		const input = {
			primary: selection.current,
			items: selectionItems,
			window: timeWindow,
			protectedSet: protectedUrns ?? NO_URNS,
			kinds: kindFilter,
			enforcementOn: activeLayers.has('enforcement'),
		};
		void cityRegistry.version;
		void ops.interception;
		void ops.watchlist;
		const ready = phase === 'ready';
		untrack(() => {
			if (!rebuildView(input) || !ready) return;
			for (const inst of instances.values()) inst.restyle?.();
			scheduleDecorate(0);
		});
	});

	function pursuitSignature(plan: InterceptionPlan, officer: boolean, kinds: ReadonlySet<string> | null): string {
		const s = plan.latestSighting;
		return JSON.stringify([
			plan.eventId,
			plan.vehicleId,
			s?.sightingId,
			s?.t,
			s?.position,
			plan.chokes.map((c) => [c.junctionId, c.rank]),
			officer,
			kindsSignature({ kinds }),
		]);
	}

	// The pursuit overlay rides the interception plan (both wall + full). A
	// re-polled identical plan keeps the drawn overlay (no replayed cinema)
	// and never restarts its own reads (a 6 s re-poll against a slow trace
	// endpoint would otherwise starve the overlay); the request token drops
	// reads that a newer plan (or a clear) superseded, so a stale show() can
	// never land after clear(). Each new plan also re-reads the plan's
	// honesty fields (stale / likely passed / direction) for the overlay and
	// the dossier. A replay owns the canvas while it plays.
	$effect(() => {
		const plan = ops.interception;
		const officer = ops.officerOn;
		// v2: the kind filter hides the heading arrow (legacy draws no filter)
		const kinds = chrome === 'v2' ? (kindFilter ?? null) : null;
		const replaying = replay.mode === 'replay';
		if (phase !== 'ready') return;
		void overlaysLanded;
		if (plan?.latestSighting && plan.vehicleId && !replaying && !pursuit) {
			// the overlay module loads with the first pursuit plan (FIX-E-PERF2);
			// the bump above re-runs this effect once it has landed
			ensurePursuitOverlay(cesiumRef!, viewer!);
		}
		if (!pursuit) return;
		if (!plan?.latestSighting || !plan.vehicleId || replaying) {
			pursuitToken++;
			pursuitShownSig = pursuitPendingSig = '';
			pursuit.clear();
			if (!plan) void godsEye.loadInterception(null);
			publishSnapshot();
			return;
		}
		const sig = pursuitSignature(plan, officer, kinds);
		if (sig === pursuitShownSig || sig === pursuitPendingSig) return;
		const token = ++pursuitToken;
		pursuitPendingSig = sig;
		const vehicleId: string = plan.vehicleId;
		void (async () => {
			let trace: Array<[number, number]> = [];
			const [t, detail] = await Promise.all([
				fetchVehicleTrace(vehicleId, 900, AbortSignal.timeout(6000)).catch(() => null),
				godsEye.loadInterception(plan.eventId),
			]);
			// trace endpoint absent — the sighting + chokes still draw
			if (t) trace = t.coordinates;
			if (token !== pursuitToken || !pursuit) return;
			pursuitPendingSig = '';
			pursuit.show({ plan, trace, detail: detail ?? godsEye.interception, segments: godsEye.segmentById, officer, kinds });
			pursuitShownSig = sig;
			publishSnapshot();
		})();
	});

	// Fly bus (selection): each request made since this canvas mounted flies
	// to the entity's fused position and reports landed / no-position.
	$effect(() => {
		const seq = selection.flySeq;
		const current = phase;
		const urn = selection.flyUrn;
		if (seq === 0 || seq === lastFlySeq || current === 'loading') return;
		lastFlySeq = seq;
		untrack(() => {
			if (current === 'unavailable') {
				selection.settleFly(seq, 'no-canvas', unavailableReason);
				return;
			}
			if (urn) void flyToUrn(seq, urn);
		});
	});

	// The selection moved: halo, highlight and (City Command) the share hash follow.
	$effect(() => {
		const urn = selection.current;
		const ready = phase === 'ready';
		untrack(() => {
			if (!ready) return;
			placeHalo();
			applySelectionHighlight();
			if (!urn && picked?.urn) picked = null;
			updateHash();
			publishSnapshot();
		});
	});

	// REPLAY: the tape on the clock; live dynamic layers stand down meanwhile.
	$effect(() => {
		const mode = replay.mode;
		const tape = replay.tape;
		const cursor = replay.cursorSec;
		const officer = ops.officerOn;
		if (phase !== 'ready') return;
		void overlaysLanded;
		if (mode === 'replay' && tape && !replayOverlay) {
			// the overlay module loads on the first replay (FIX-E-PERF2); the
			// bump above re-runs this effect once it has landed
			ensureReplayOverlay(cesiumRef!, viewer!);
		}
		if (!replayOverlay) return;
		untrack(() => {
			if (mode !== 'replay' || !tape) {
				if (replayShownSig) {
					replayOverlay?.clear();
					replayShownSig = '';
				}
				if (replaySuspended.length) resumeLiveLayers();
				publishSnapshot();
				return;
			}
			const sig = `${tape.runId}|${officer}`;
			if (sig !== replayShownSig) {
				suspendLiveLayers();
				replayOverlay?.show(tape, officer);
				replayShownSig = sig;
			}
			replayOverlay?.setTime(cursor);
			publishSnapshot();
		});
	});

	onDestroy(() => {
		destroyed = true;
		stopTour(false);
		// A request this canvas took on but never finished (queued for
		// geometry, mid-flight, or still loading) is answered, so no surface
		// waits on 'locating…' for a canvas that is gone; the next canvas
		// does not replay it.
		lockFlightToken++;
		lockFlight = null;
		pendingFocus = null;
		if (focus.seq > mountedFocusSeq && focus.outcome === 'pending') {
			focus.settle(focus.seq, 'cancelled', 'the canvas closed before the request was served');
		}
		detachFocus?.();
		detachFocus = null;
		if (hudTimer) clearInterval(hudTimer);
		if (clockTimer) clearInterval(clockTimer);
		if (timeTimer) clearInterval(timeTimer);
		if (declutterTimer) clearInterval(declutterTimer);
		declutterTimer = null;
		declutterHidden.clear();
		if (hashTimer) clearTimeout(hashTimer);
		if (ionTimer) clearTimeout(ionTimer);
		if (hoverTimer) clearTimeout(hoverTimer);
		if (decorateTimer) clearTimeout(decorateTimer);
		decorateTimer = null;
		removeMoveEnd?.();
		removeMoveEnd = null;
		removeCollection?.();
		removeCollection = null;
		detachChrome?.();
		detachChrome = null;
		creditsObserver?.disconnect();
		creditsObserver = null;
		osmOverlay = null;
		spider = null;
		hudTimer = clockTimer = timeTimer = null;
		hashTimer = ionTimer = hoverTimer = null;
		pursuitToken++;
		handler?.destroy();
		handler = null;
		if (container) {
			container.removeEventListener('pointerdown', onPointerDown, { capture: true });
			container.removeEventListener('pointermove', onPointerMove, { capture: true });
			container.removeEventListener('pointerup', onPointerUp, { capture: true });
			container.removeEventListener('wheel', onWheel, { capture: true });
			container.removeEventListener('pointerleave', onPointerLeave);
		}
		removeCameraListener?.();
		removeCameraListener = null;
		removePreUpdate?.();
		removePreUpdate = null;
		removeTileError?.();
		removeTileError = null;
		removeTileProgress?.();
		removeTileProgress = null;
		for (const off of removeIonListeners) off();
		removeIonListeners = [];
		hovered = null;
		selectedHighlights = [];
		haloAt = null;
		haloEntity = null;
		haloDrawnAt = null;
		clearAgentHighlights();
		for (const timer of agentNotes.values()) clearTimeout(timer);
		agentNotes.clear();
		pursuit?.destroy();
		pursuit = null;
		replayOverlay?.destroy();
		replayOverlay = null;
		for (const inst of instances.values()) inst.destroy();
		instances = new Map();
		try {
			viewer?.destroy();
		} catch {
			// viewer already torn down by navigation
		}
		viewer = null;
		if (godsEye.subjectLockId) godsEye.subjectLockId = null;
		godsEye.stop();
		ops.stop();
	});

	/** Compact age: 42s · 4m07s · 3h12m · 2d05h. */
	function fmtAge(sec: number): string {
		if (sec < 120) return `${sec}s`;
		if (sec < 7200) return `${Math.floor(sec / 60)}m${String(sec % 60).padStart(2, '0')}s`;
		if (sec < 172_800) return `${Math.floor(sec / 3600)}h${String(Math.floor((sec % 3600) / 60)).padStart(2, '0')}m`;
		return `${Math.floor(sec / 86_400)}d${String(Math.floor((sec % 86_400) / 3600)).padStart(2, '0')}h`;
	}

	// AMA chip (R9): band + age of the newest band READING (now −
	// ops.bandUpdated: the event's newest situation_log row, or the city
	// band's latest engine evaluation — every rung reports the same 'newest
	// reading', never the band's entry time) on a 1 s clock; the source label
	// prints as the store reports it. STALE keys on that reading too, so a
	// band that has HELD for hours but is still being read is never STALE —
	// only one whose engine stopped reading it (a failing city-band poll
	// already reads UNKNOWN in the store).
	let amaBand = $derived(ops.band ?? '—');
	let amaAgeSec = $derived(ops.bandUpdated ? Math.max(0, Math.floor((nowMs - ops.bandUpdated) / 1000)) : null);
	let amaStale = $derived(amaAgeSec != null && amaAgeSec > AMA_STALE_SEC);
	let feedWarnings = $derived(GODS_EYE_LAYERS.filter((l) => !!stats[l.id]?.error));
	/** The layer's own pick card: wall views always; City Command only for picks with no entity URN. */
	let showPickCard = $derived(pickCard || (picked != null && !picked.urn));
	let replaying = $derived(replay.mode === 'replay');
	/**
	 * The replay's own provenance (SPEC §9: honest labels, read from the
	 * replay state — never guessed): the tape is an emulated recording when
	 * every ANPR read it carries wears the emulator's EM series marker
	 * (event-emulator tape.py `is_emulated_plate`); a capture of live reads
	 * is never labelled so. A tape with no reads to contradict it keeps the
	 * ledger's own provenance — parseTape loads emulator runs only.
	 */
	let replayEmulated = $derived(tapeIsEmulated(replay.tape));

	/** Pure: `MH47EM9001` → true (the EM series after the RTO code); a live capture's marks are not. */
	function tapeIsEmulated(tape: { anpr: ReadonlyArray<{ plate: string }> } | null): boolean {
		if (!tape) return false;
		const plates = tape.anpr.map((r) => r.plate);
		if (!plates.length) return true;
		return plates.every((p) => p.length > 6 && p.slice(4, 6).toUpperCase() === 'EM');
	}
	/** The locked subject's name as this console may show it (C6: masked unless an officer is named). */
	let lockedEventName = $derived(godsEye.subjectLockId ? eventLabel(godsEye.subjectLockId, ops.officerOn) : null);
	// Chip text only (basemap.ts imageryChip, EN/HI/MR) — the snapshot's
	// imageryMode stays 'keyless-osm' / 'ion-photoreal' / 'offline-schematic'
	// (tests and share links read it). Once the photoreal tiles cover the
	// view the chip names Google's 3D city, whatever the imagery under it did.
	let photoreal = $derived(stats['photoreal-3d'] ?? null);
	let photorealOn = $derived(photorealReady(photoreal));
	let modeLabel = $derived(
		t(ops.lang, imageryChip({ offline: offlineDetected, basemapId, fallbackNote: basemapNote, photoreal })),
	);
	let modeTitle = $derived(
		photorealOn
			? `Google Photorealistic 3D Tiles via Cesium ion — every overlay draped on the 3D city${basemapNote ? ` · ${basemapNote}` : ''}`
			: (basemapNote ?? 'Basemap mode (dark re-grade applied to the keyless raster)'),
	);
	/** The data credits ride the clear region's bottom-left corner (City Command's rail covers the canvas's own). */
	let creditStyle = $derived(
		clearInsets
			? `--ge-credit-left:${Math.max(0, Math.round(clearInsets.left))}px;--ge-credit-bottom:${Math.max(0, Math.round(clearInsets.bottom))}px`
			: undefined,
	);
	/** AI suggestions waiting on a human (the chips) — the bus's queue. */
	let agentPending = $derived(canvasBus.pending);

	// ─── chrome v2: template state ─────────────────────────────────────────
	let isV2 = $derived(chrome === 'v2');
	/** What Follow holds, in operator copy: the locked event's name, the followed object's label (marks masked), never a raw URN. */
	let followName = $derived.by(() => {
		if (godsEye.subjectLockId) return lockedEventName;
		return followUrn ? objectName(followUrn) : null;
	});
	let followState = $derived({
		pressed: !!godsEye.subjectLockId || !!followUrn,
		disabled: !selection.current,
		// a followed object the registry cannot name reads "Following the selection"
		title:
			godsEye.subjectLockId || followUrn
				? t(ops.lang, 'map_tool_following', followName)
				: selection.current
				? t(ops.lang, 'map_tool_follow')
				: t(ops.lang, 'map_tool_follow_none'),
	});
	let modeState = $derived<{ kind: 'live' | 'window' | 'replay'; runId?: number | string | null }>(
		replaying ? { kind: 'replay', runId: replay.runId } : timeWindow ? { kind: 'window' } : { kind: 'live' },
	);
	let readoutAt = $derived(cursorAt ?? centreAt);
	let flowSimulated = $derived((stats['flow']?.detail?.simulated ?? 0) > 0);

	// chrome v3: the page's tool buttons read what the canvas's tools hold
	$effect(() => {
		if (!v3 || phase !== 'ready') return;
		mapChrome.tools = { heading: cameraHeadingDeg, follow: followState, sensor: sensorMode, tool, photorealReady: photorealOn };
	});

	/** v2 zoom buttons: a step toward or away from the ground (a camera gesture). */
	function zoomBy(sign: 1 | -1) {
		if (!viewer) return;
		markInteraction();
		takeCamera();
		const h = Math.max(60, cameraGround()?.alt ?? 1000);
		try {
			if (sign > 0) viewer.camera.zoomIn?.(h * 0.4);
			else viewer.camera.zoomOut?.(h * 0.6);
		} catch {
			// camera mid-teardown
		}
		scheduleDecorate(200);
	}

	/** v2 compass: the same ground point under the centre, north up. */
	function resetNorth() {
		const canvas = viewer?.scene.canvas;
		const cam = cameraState();
		if (!viewer || !canvas || !cam) return;
		const centre = groundAt(canvas.clientWidth / 2, canvas.clientHeight / 2);
		if (!centre) return;
		markInteraction();
		takeCamera();
		const pitch = Math.min(-10, cam.pitch);
		const range = cam.alt / Math.max(0.2, Math.sin(Math.abs((pitch * Math.PI) / 180)));
		flyFrame(centre.lon, centre.lat, range, 0, pitch, 0.8);
	}
</script>

<svelte:window onkeydown={onKey} />

<div class="ge-wrap" class:mini={hud === 'mini'} data-hud={hud} data-chrome={chrome}>
	{#if phase === 'loading'}
		<div class="ge-status"><span class="pulse"></span> initialising God's-eye canvas…</div>
	{/if}

	{#if phase === 'unavailable'}
		<div class="ge-degrade">
			<h3>3D God's-eye canvas unavailable</h3>
			<p>{unavailableReason}</p>
			<p class="dim">
				This panel degrades alone — the board keeps working on the situation wall at
				<a href="/ops">/ops</a>. A WebGL-capable browser (or the served build with
				static/cesium) renders the Cesium canvas.
			</p>
		</div>
	{/if}

	<div class="ge-canvas" bind:this={container} style={creditStyle}></div>

	{#if phase === 'ready'}
		{#if isV2}
			<!-- chrome v2 (SPEC §5.3): toolbar top left, proposals and the replay banner top centre,
			     navigation bottom right above Cesium's credits, readout bottom left -->
			<div class="ge-hud v2" class:v3>
				{#if !v3}
				<MapToolbar
					lang={ops.lang}
					{tool}
					{shapeMode}
					shapeFiltered={!!shapeFilter}
					canSearchAround={!!selection.current}
					layersOpen={onLayers ? false : layersOpen}
					{legendOpen}
					layersRail={!onLayers}
					follow={followState}
					mode={modeState}
					imagery={{ label: modeLabel, title: `${modeTitle} · ${t(ops.lang, 'map_imagery_not_live')}` }}
					showExit={hud === 'full' && !!onexit}
					touring={tourIndex != null}
					sensor={sensorMode}
					ontool={(next, mode) => setTool(next, mode)}
					onclearshape={clearShapeFilter}
					onsearcharound={searchAround}
					onlayers={() => (onLayers ? onLayers() : (layersOpen = !layersOpen))}
					onlegend={() => {
						legendOpen = !legendOpen;
						publishChrome();
					}}
					onfollow={toggleFollow}
					onmode={() => onTimeline?.()}
					onexit={() => onexit?.()}
					ontour={() => (tourIndex == null ? startTour() : stopTour())}
					onsensor={(mode) => {
						setSensor(mode);
						updateHash();
					}}
				/>
				{/if}
				{#if shareFlash}<span class="flash">{displayText(shareFlash, ops.officerOn)}</span>{/if}
				{#if tourIndex != null && tourLabel}
					<span class="tour-label">{displayText(tourLabel, ops.officerOn)}</span>
				{/if}
				{#if toolHint}<span class="tool-hint">{toolHint}</span>{/if}
			</div>
			<div class="v2-top">
				{#if replaying}<ReplayBanner runId={replay.runId} emulated={replayEmulated} lang={ops.lang} />{/if}
				{#if agentPending.length}
					<!-- the proposal cards load with the first canvas directive (FIX-E-PERF2):
					     with none pending they render nothing, so nothing loads at first paint -->
					<LazyMount
						load={() => import('./hud/map/MapProposals.svelte')}
						spinner={false}
						glyphs={[ACTOR_ICON.ai]}
						proposals={agentPending}
						textOf={chipText}
						onapply={applyDirective}
						ondismiss={dismissDirective}
						lang={ops.lang}
						max={AGENT_CHIPS_SHOWN}
					/>
				{/if}
			</div>
			{#if !v3}
			{#if layersOpen && !onLayers}
				<div class="v2-panel"><LazyMount load={loadLayerTree} spinner={false} lang={ops.lang} onclose={() => (layersOpen = false)} /></div>
			{/if}
			{#if legendOpen}
				<!-- beside the canvas's own LayerTree panel when it is open (never over its rows or its base-map control) -->
				<div class="v2-legend" class:beside={layersOpen && !onLayers}>
					<LazyMount
						load={loadLegend}
						spinner={false}
						lang={ops.lang}
						simulated={flowSimulated}
						onclose={() => {
							legendOpen = false;
							publishChrome();
						}}
					/>
				</div>
			{/if}
			<div class="v2-nav" style:bottom={`${creditsH + 16}px`}>
				<MapNav lang={ops.lang} heading={cameraHeadingDeg} onzoomin={() => zoomBy(1)} onzoomout={() => zoomBy(-1)} onnorth={resetNorth} />
			</div>
			<div class="v2-readout">
				<MapReadout lang={ops.lang} lat={readoutAt?.lat ?? null} lon={readoutAt?.lon ?? null} scale={scaleBar} />
			</div>
			{/if}
			{#if hoverList}
				<div class="v2-hover" style:left={`${hoverList.x + 16}px`} style:top={`${hoverList.y + 12}px`} role="tooltip">
					<div class="v2-hover-title">{hoverList.title}</div>
					{#each hoverList.items as item, i (i)}<div class="v2-hover-item">{item}</div>{/each}
					<div class="v2-hover-hint">{t(ops.lang, 'map_cluster_spread')}</div>
				</div>
			{/if}
		{:else}
		<div class="ge-hud" class:mini={hud === 'mini'}>
			{#if hud === 'full' || hud === 'wall'}
				<!-- one wrapping chip row: controls · layers · AMA · basemap · legend -->
				<div class="hud-row" bind:this={hudRowEl}>
					{#if hud === 'full' && onexit}
						<button class="chip exit" onclick={onexit} title="Leave the cinematic view — back to the situation wall (Esc)">
							⤡ EXIT
						</button>
					{/if}
					<button
						class="chip sensor"
						class:flir={sensorMode !== 'raw'}
						onclick={cycleSensor}
						title="Visual filter: COMMAND (true colours, default) → thermal-style White-Hot → Black-Hot → Ironbow"
					>
						▙ {SENSOR_LABEL[sensorMode]}
					</button>
					<button class="chip share" onclick={share} title="Copy this exact view for a civic volunteer unit / police control room">
						⇪ SHARE
					</button>
					<button
						class="chip tour"
						onclick={() => (tourIndex == null ? startTour() : stopTour())}
						title="Guided tour over the live city — empty layers are skipped (Esc stops)"
					>
						{tourIndex == null ? '▶ TOUR' : `■ ${tourIndex + 1}/${tourTotal}`}
					</button>
					{#if godsEye.subjectLockId}
						<button
							class="chip lock"
							onclick={() => releaseSubject()}
							title={`camera held on ${lockedEventName ?? godsEye.subjectLockId} — click to release`}
						>
							⊕ LOCKED · RELEASE
						</button>
					{/if}
					{#each GODS_EYE_LAYERS as layer (layer.id)}
						<button
							class="chip layer"
							class:off={!activeLayers.has(layer.id)}
							class:paused={replaying && replaySuspended.includes(layer.id)}
							class:warn={!!stats[layer.id]?.error}
							title={replaying && replaySuspended.includes(layer.id)
								? `${layer.name} — paused while the replay owns the canvas`
								: (stats[layer.id]?.hint ?? layer.name)}
							data-layer={layer.id}
							onclick={() => toggleLayer(layer.id)}
						>
							{layer.label}
							<span class="n">{stats[layer.id]?.count ?? 0}</span>
							{#if (stats[layer.id]?.detail?.simulated ?? 0) > 0}
								<!-- provenance, never 'live': the integrated ingest feed is synthetic -->
								<span class="sim" data-testid="chip-simulated" title={t(ops.lang, 'cc_simulated_feed')}>SIM</span>
							{/if}
						</button>
					{/each}
					{#if replaying}
						<span class="chip replay" data-testid="replay-pill" title="A recorded emulator tape is playing on the canvas clock — every replayed primitive is EMULATED">
							◐ REPLAY{replay.runId != null ? ` · run ${replay.runId}` : ''} · EMULATED
						</span>
						<span class="chip live-paused" data-testid="live-paused" title={t(ops.lang, 'canvas_live_paused_hint')}>
							❚❚ {t(ops.lang, 'canvas_live_paused')}
						</span>
					{/if}
					<span
						class="chip ama"
						class:stale={amaStale}
						data-age-sec={amaAgeSec ?? ''}
						title={t(ops.lang, 'canvas_ama_title')}
					>
						AMA {amaBand}
						{#if amaAgeSec != null}<span class="n">·{fmtAge(amaAgeSec)}</span>{/if}
						<span class="n dim">[{ops.bandSource}]</span>
						{#if amaStale}<span class="stale-tag">STALE</span>{/if}
					</span>
					<span class="chip mode" class:photoreal={photorealOn} title={modeTitle}>
						{modeLabel}
					</span>
					{#if pursuitCount > 0}
						<span class="chip pursuit" title="pursuit overlay — trace + ranked chokes + future arc">
							PURSUIT <span class="n">{pursuitCount}</span>
						</span>
					{/if}
					<button
						class="chip legend"
						class:warn={feedWarnings.length > 0}
						onclick={() => (legendOpen = !legendOpen)}
						aria-expanded={legendOpen}
						title="Legend — layer feeds, colour key and credits"
					>
						ⓘ © OSM{#if feedWarnings.length}<span class="warn-n">⚠ {feedWarnings.length}</span>{/if}
					</button>
					{#if shareFlash}<span class="flash">{displayText(shareFlash, ops.officerOn)}</span>{/if}
				</div>
				{#if tourIndex != null && tourLabel}
					<span class="tour-label">{displayText(tourLabel, ops.officerOn)}</span>
				{/if}
				{#if agentPending.length}
					<div class="agent-chips" data-testid="agent-suggestions" aria-live="polite">
						{#each agentPending.slice(0, AGENT_CHIPS_SHOWN) as d (d.id)}
							<div class="agent-chip" data-testid="agent-chip" data-directive-id={d.id} data-verb={d.verb} title={t(ops.lang, 'agent_proposal')}>
								<span class="agent-kicker">✦ {t(ops.lang, 'agent_suggests')}</span>
								<span class="agent-text">{chipText(d)}</span>
								{#if d.tier}<span class="agent-tier" title={t(ops.lang, 'agent_from', d.tier)}>{d.tier}</span>{/if}
								<button class="agent-apply" data-testid="agent-apply" onclick={() => applyDirective(d)}>{t(ops.lang, 'agent_apply')}</button>
								<button class="agent-dismiss" data-testid="agent-dismiss" onclick={() => dismissDirective(d)}>{t(ops.lang, 'agent_dismiss')}</button>
							</div>
						{/each}
						{#if agentPending.length > AGENT_CHIPS_SHOWN}
							<span class="agent-more">{t(ops.lang, 'agent_more', agentPending.length - AGENT_CHIPS_SHOWN)}</span>
						{/if}
					</div>
				{/if}
				{#if legendOpen}
					<div class="ge-legend" role="dialog" aria-label="God's-eye legend">
						<ul class="lg-layers">
							{#each GODS_EYE_LAYERS as layer (layer.id)}
								<li>
									<b>{layer.label}</b>
									<span class="n">{stats[layer.id]?.count ?? 0}</span>
									<span class="lg-hint">{stats[layer.id]?.hint ?? layer.name}</span>
									{#if stats[layer.id]?.error}<span class="feed-warn">{stats[layer.id].error}</span>{/if}
								</li>
							{/each}
						</ul>
						<p class="lg-key">
							<i class="sw sw-data"></i> planned · <i class="sw sw-act"></i> active / flagged / pending a human ·
							<i class="sw sw-dim"></i> closed · glow = RECOMMENDED corridor · dashes = alternates ·
							·PREVIEW = offline fixture · ·EMULATED = emulator source
						</p>
						<p class="lg-key">
							flow (draped on the ground): <i class="sw sw-green"></i> free → <i class="sw sw-red"></i> severe, hairline = NO DATA,
							dashed = schematic chord (not the road's true shape) ·
							signals: arc = green share, <i class="sw sw-amber"></i> amber, <i class="sw sw-red"></i> all-red ·
							₹ pins = e-challan recommendations (a named officer decides) · eye pins = stolen-vehicle sightings (evidence, never a fine) ·
							plates masked until a duty officer is named
						</p>
						{#if basemapNote}<p class="lg-note">{basemapNote}</p>{/if}
						<p class="credit">
							{OSM_CREDIT} · canvas patterns from
							<a href="https://github.com/bilawalsidhu/gods-eye-view" target="_blank" rel="noreferrer">gods-eye-view (MIT)</a>
						</p>
					</div>
				{/if}
				{#if picked && showPickCard}
					<div class="ge-pick" data-pick-layer={picked.layer} role="status">
						<header>
							<span class="pick-layer">{picked.label}</span>
							{#if picked.eventId && ops.selectedEventId === picked.eventId}<span class="pick-sel">SELECTED</span>{/if}
							<button class="pick-x" onclick={() => (picked = null)} aria-label="dismiss pick card">✕</button>
						</header>
						<p class="pick-text">{displayText(picked.text, ops.officerOn)}</p>
						{#if picked.eventId}
							<div class="pick-actions">
								<button class="chip lock" onclick={() => focus.request(picked!.eventId!)} title="fly to this event and hold the camera on it">
									⊕ FOCUS
								</button>
							</div>
						{/if}
					</div>
				{/if}
			{:else}
				<span class="chip mode" title={modeTitle}>
					{photorealOn ? '3D · GOOGLE' : offlineDetected ? 'OFFLINE SCHEMATIC' : basemapId === 'ion-photoreal' ? 'ION' : 'OSM·DARK'}
				</span>
				<span
					class="chip ama"
					class:stale={amaStale}
					style={`border-color:${ops.band ? (cssVar(`--v-band-${ops.band.toLowerCase()}`) ?? 'var(--v-line-2)') : 'var(--v-line-2)'}`}
				>
					AMA {amaBand}{amaAgeSec != null ? ` ·${fmtAge(amaAgeSec)}` : ''}
				</span>
				<a class="chip layer" href="/gods-eye">FULLSCREEN ⤢</a>
			{/if}
		</div>
		{/if}
		{#if hud === 'full' || hud === 'wall'}
			<CommandPalette
				layerIds={GODS_EYE_LAYER_IDS}
				world={directiveWorld}
				onfly={paletteFly}
				onhighlight={highlightUrns}
				onlayer={(id, on) => setLayerEnabled(id, on)}
				onsensor={(mode) => {
					setSensor(mode);
					updateHash();
				}}
			/>
		{/if}
	{/if}
</div>

<style>
	.ge-wrap {
		position: relative;
		width: 100%;
		height: 100%;
		min-height: 240px;
		background: var(--v-canvas);
		overflow: hidden;
		border-radius: var(--v-radius-panel);
	}

	.ge-canvas {
		position: absolute;
		inset: 0;
	}

	.ge-canvas :global(.cesium-viewer) {
		width: 100%;
		height: 100%;
	}

	/*
	 * The data credits (Google, Cesium ion, OSM — Google's terms want them
	 * legible) on a glass plate, lifted into the corner the host's panels
	 * leave clear (--ge-credit-left / --ge-credit-bottom from clearInsets:
	 * City Command's fusion rail covers the canvas's own bottom-left).
	 * A transform, because Cesium writes the bar's left/bottom inline on
	 * every resize. A host that floats an instrument along the bottom edge
	 * (the cockpit's tool dock) caps the bar's width (--ge-credit-max-w):
	 * the credits wrap onto another line instead of running under it.
	 */
	.ge-wrap:not([data-chrome='v2']) .ge-canvas :global(.cesium-viewer-bottom) {
		transform: translate(var(--ge-credit-left, 0px), calc(-1 * var(--ge-credit-bottom, 0px)));
		width: fit-content;
		max-width: var(--ge-credit-max-w, none);
		padding: 2px 6px;
		border-radius: var(--v-radius-chip);
		background: var(--v-glass-bg);
	}

	.ge-status {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: var(--v-space-3);
		color: var(--v-ink-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		z-index: 3;
	}

	.pulse {
		width: 8px;
		height: 8px;
		border-radius: var(--v-radius-pill);
		background: var(--v-data);
		animation: gepulse 1.2s ease-in-out infinite;
	}

	@keyframes gepulse {
		50% {
			opacity: 0.2;
		}
	}

	.ge-degrade {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--v-space-2);
		padding: var(--v-space-5);
		text-align: center;
		color: var(--v-ink-2);
		background: var(--v-surface-sink);
		z-index: 3;
	}

	.ge-degrade h3 {
		margin: 0;
		font-size: var(--v-text-base);
		letter-spacing: 0;
		color: var(--v-ink-1);
	}

	.ge-degrade p {
		margin: 0;
		font-size: var(--v-text-xs);
		max-width: 46ch;
	}

	.ge-degrade .dim {
		color: var(--v-ink-3);
	}

	.ge-degrade a {
		color: var(--v-data);
	}

	/* The HUD column. Hosts that float chrome over the canvas (the cockpit's
	 * rails and stats pill) inset it with --ge-hud-left/right/top. */
	.ge-hud {
		position: absolute;
		left: var(--ge-hud-left, var(--v-space-3));
		right: var(--ge-hud-right, var(--v-space-3));
		top: var(--ge-hud-top, var(--v-space-3));
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--v-space-1);
		z-index: 4;
		pointer-events: none;
	}

	.ge-hud .hud-row,
	.ge-hud .chip,
	.ge-hud .ge-pick,
	.ge-hud .ge-legend,
	.ge-hud .flash,
	.ge-hud .tour-label {
		pointer-events: auto;
	}

	.hud-row {
		display: flex;
		flex-wrap: wrap;
		gap: var(--v-space-1);
		align-items: center;
	}

	.chip {
		font-family: var(--v-font-ui);
		font-variant-numeric: tabular-nums;
		font-size: var(--v-text-2xs);
		letter-spacing: 0;
		color: var(--v-ink-1);
		background: color-mix(in srgb, var(--v-canvas) 82%, transparent);
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-chip);
		padding: 2px var(--v-space-2);
		cursor: default;
		text-decoration: none;
		display: inline-flex;
		align-items: center;
		gap: var(--v-space-1);
		white-space: nowrap;
	}

	button.chip {
		cursor: pointer;
	}

	button.chip:hover {
		border-color: var(--v-line-select);
	}

	button.chip:focus-visible {
		outline: 1px solid var(--v-act-focus);
		outline-offset: 1px;
	}

	.chip.exit {
		border-color: var(--v-ink-2);
		color: var(--v-ink-1);
	}

	.chip.sensor {
		border-color: var(--v-data);
		color: var(--v-data);
	}

	.chip.sensor.flir {
		border-color: var(--v-band-amber);
		color: var(--v-band-amber);
	}

	.chip.share {
		border-color: var(--v-band-green);
		color: var(--v-band-green);
	}

	.chip.tour {
		border-color: var(--v-act);
		color: var(--v-act-text);
	}

	.chip.lock {
		border-color: var(--v-data);
		color: var(--v-data);
	}

	.chip.pursuit {
		border-color: var(--v-act);
		color: var(--v-act-text);
	}

	.chip.mode.photoreal {
		border-color: var(--v-data);
		color: var(--v-data);
	}

	.chip.layer.off {
		opacity: 0.45;
	}

	.chip.layer.paused {
		opacity: 0.35;
		border-style: dotted;
	}

	.chip.replay {
		border-color: var(--v-tool);
		color: var(--v-tool);
		border-style: dashed;
		letter-spacing: 0;
	}

	.chip.layer.warn {
		border-style: dashed;
	}

	.chip .n {
		color: var(--v-data);
	}

	/* SIMULATED FEED provenance tag (synthetic ingest rows) — the tool accent, dashed, never a band colour. */
	.chip .sim {
		margin-left: 2px;
		padding: 0 4px;
		font-size: 9px;
		letter-spacing: 0;
		color: var(--v-tool);
		border: 1px dashed var(--v-tool);
		border-radius: var(--v-radius-pill);
	}

	.chip .dim {
		color: var(--v-ink-3);
	}

	.chip.ama {
		border-color: var(--v-data);
		color: var(--v-data);
	}

	.chip.ama.stale {
		border-style: dashed;
		border-color: var(--v-line-2);
		color: var(--v-ink-3);
	}

	.chip.ama.stale .n {
		color: var(--v-ink-3);
	}

	.stale-tag {
		color: var(--v-band-amber);
		letter-spacing: 0;
	}

	.chip.legend.warn {
		border-color: var(--v-band-red);
	}

	.warn-n {
		color: var(--v-band-red);
		margin-left: var(--v-space-1);
	}

	.tour-label {
		font-size: var(--v-text-2xs);
		color: var(--v-ink-2);
		background: color-mix(in srgb, var(--v-canvas) 82%, transparent);
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-chip);
		padding: 2px var(--v-space-2);
		max-width: min(64ch, 100%);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.flash {
		font-family: var(--v-font-ui);
		font-size: var(--v-text-2xs);
		color: var(--v-band-green);
		background: color-mix(in srgb, var(--v-canvas) 85%, transparent);
		border-radius: var(--v-radius-chip);
		padding: 2px var(--v-space-2);
		max-width: 48ch;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.ge-legend,
	.ge-pick {
		font-family: var(--v-font-ui);
		font-size: var(--v-text-2xs);
		color: var(--v-ink-2);
		background: color-mix(in srgb, var(--v-canvas) 90%, transparent);
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-chip);
		padding: var(--v-space-2);
		max-width: min(58ch, 100%);
	}

	.lg-layers {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.lg-layers b {
		color: var(--v-ink-1);
		font-weight: 600;
	}

	.lg-layers .n {
		color: var(--v-data);
		margin: 0 var(--v-space-1);
	}

	.lg-hint {
		color: var(--v-ink-3);
	}

	.lg-key,
	.lg-note,
	.credit {
		margin: var(--v-space-2) 0 0;
	}

	.lg-note {
		color: var(--v-band-amber);
	}

	.sw {
		display: inline-block;
		width: 10px;
		height: 3px;
		vertical-align: middle;
		border-radius: 1px;
	}

	.sw-data {
		background: var(--v-data);
	}

	.sw-act {
		background: var(--v-act);
	}

	.sw-dim {
		background: var(--v-ink-4);
	}

	.sw-green {
		background: var(--v-band-green);
	}

	.sw-amber {
		background: var(--v-band-amber);
	}

	.sw-red {
		background: var(--v-band-red);
	}

	.credit {
		color: var(--v-ink-3);
	}

	.credit a {
		color: var(--v-ink-2);
	}

	.feed-warn {
		display: block;
		font-family: var(--v-font-ui);
		font-size: var(--v-text-2xs);
		color: var(--v-band-red);
	}

	.ge-pick {
		border-color: var(--v-data);
	}

	.ge-pick header {
		display: flex;
		align-items: center;
		gap: var(--v-space-2);
		margin-bottom: var(--v-space-1);
	}

	.pick-layer {
		color: var(--v-data);
		letter-spacing: 0;
	}

	.pick-sel {
		color: var(--v-act-text);
		letter-spacing: 0;
	}

	.pick-x {
		margin-left: auto;
		background: transparent;
		border: none;
		color: var(--v-ink-3);
		cursor: pointer;
		font: inherit;
	}

	.pick-x:hover {
		color: var(--v-ink-1);
	}

	.pick-text {
		margin: 0;
		color: var(--v-ink-1);
		white-space: pre-line;
		line-height: 1.45;
	}

	.pick-actions {
		margin-top: var(--v-space-2);
		display: flex;
		gap: var(--v-space-1);
	}

	.ge-hud.mini {
		flex-direction: row;
		gap: var(--v-space-1);
		align-items: flex-start;
	}

	/* 'LIVE paused' — the live layers stand down while a replay owns the canvas */
	.chip.live-paused {
		border-color: var(--v-band-amber);
		color: var(--v-band-amber);
		border-style: dashed;
	}

	/* AI suggestions: the machine proposes (tool accent), a human presses Apply */
	.agent-chips {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--v-space-1);
		pointer-events: auto;
		max-width: min(64ch, 100%);
	}

	.agent-chip {
		display: flex;
		align-items: center;
		gap: var(--v-space-2);
		padding: 3px var(--v-space-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		color: var(--v-ink-1);
		background: color-mix(in srgb, var(--v-canvas) 88%, transparent);
		border: 1px solid var(--v-tool);
		border-left: 3px solid var(--v-tool);
		border-radius: var(--v-radius-chip);
		box-shadow: 0 0 18px color-mix(in srgb, var(--v-tool) 25%, transparent);
		max-width: 100%;
	}

	.agent-kicker {
		color: var(--v-tool);
		letter-spacing: 0;
		white-space: nowrap;
	}

	.agent-text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.agent-tier {
		font-size: 9px;
		letter-spacing: 0;
		color: var(--v-ink-3);
		border: 1px dashed var(--v-line-2);
		border-radius: var(--v-radius-pill);
		padding: 0 5px;
		white-space: nowrap;
	}

	.agent-chip button {
		font: inherit;
		font-size: var(--v-text-2xs);
		padding: 1px var(--v-space-2);
		border-radius: var(--v-radius-btn);
		cursor: pointer;
		white-space: nowrap;
	}

	.agent-apply {
		color: var(--v-act-text);
		background: var(--v-act-veil);
		border: 1px solid var(--v-act);
	}

	.agent-apply:hover {
		background: color-mix(in srgb, var(--v-act) 30%, transparent);
	}

	.agent-dismiss {
		color: var(--v-ink-2);
		background: transparent;
		border: 1px solid var(--v-line-2);
	}

	.agent-dismiss:hover {
		color: var(--v-ink-1);
		border-color: var(--v-line-select);
	}

	.agent-chip button:focus-visible {
		outline: 1px solid var(--v-act-focus);
		outline-offset: 1px;
	}

	.agent-more {
		font-family: var(--v-font-ui);
		font-size: var(--v-text-2xs);
		color: var(--v-ink-3);
	}


	/* ── chrome v2 (SPEC §5.3) ─────────────────────────────────────────── */

	/*
	 * Cesium's own credits (Google's logo, Cesium ion, '© OpenStreetMap
	 * contributors', the per-tile copyrights) restyled as a quiet plate at
	 * the BOTTOM RIGHT of the map pane, never covered: the navigation sits
	 * above it and the readout stays at the bottom left, clear of it.
	 * !important: Cesium writes the bar's left/bottom inline on every resize.
	 */
	.ge-wrap[data-chrome='v2'] .ge-canvas :global(.cesium-viewer-bottom) {
		left: auto !important;
		right: 8px !important;
		bottom: 8px !important;
		max-width: calc(46% - 16px);
		padding: 2px 6px;
		border-radius: var(--v-radius-chip);
		background: var(--v-map-label-bg);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: 18px;
		color: var(--v-ink-2);
		z-index: 4;
	}

	.ge-wrap[data-chrome='v2'] .ge-canvas :global(.cesium-widget-credits) {
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
		text-shadow: none;
	}

	.ge-wrap[data-chrome='v2'] .ge-canvas :global(.cesium-credit-expand-link),
	.ge-wrap[data-chrome='v2'] .ge-canvas :global(.cesium-widget-credits a) {
		color: var(--v-ink-2);
	}

	.ge-hud.v2 {
		left: var(--ge-hud-left, 8px);
		top: var(--ge-hud-top, 8px);
		gap: 6px;
	}

	.ge-hud.v2 .flash,
	.ge-hud.v2 .tour-label,
	.ge-hud.v2 .tool-hint {
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: 16px;
		padding: 3px 8px;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: var(--v-map-label-bg);
		box-shadow: var(--v-elev-1);
		max-width: min(64ch, 100%);
		pointer-events: auto;
	}

	.ge-hud.v2 .flash {
		color: var(--v-ink-1);
	}

	.ge-hud.v2 .tour-label,
	.ge-hud.v2 .tool-hint {
		color: var(--v-ink-2);
	}

	.v2-top {
		position: absolute;
		top: 8px;
		left: 50%;
		transform: translateX(-50%);
		width: min(440px, calc(100% - 16px));
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		z-index: 5;
		pointer-events: none;
	}

	.v2-top > :global(*) {
		pointer-events: auto;
	}

	.v2-panel {
		position: absolute;
		top: 48px;
		left: var(--ge-hud-left, 8px);
		width: 300px;
		max-height: calc(100% - 104px);
		display: flex;
		flex-direction: column;
		border-radius: var(--v-radius-panel);
		overflow: hidden;
		box-shadow: var(--v-elev-2);
		z-index: 5;
	}

	.v2-panel > :global(*) {
		min-height: 0;
		flex: 1 1 auto;
	}

	.v2-legend {
		position: absolute;
		left: var(--ge-hud-left, 8px);
		bottom: 38px;
		z-index: 5;
	}

	/* the LayerTree panel is 300 px wide at the same left edge: the legend stands to its right */
	.v2-legend.beside {
		left: calc(var(--ge-hud-left, 8px) + 308px);
	}

	.v2-nav {
		position: absolute;
		right: 8px;
		bottom: 44px;
		z-index: 4;
	}

	.v2-readout {
		position: absolute;
		left: 8px;
		bottom: 8px;
		max-width: calc(54% - 16px);
		z-index: 4;
	}

	.v2-hover {
		position: absolute;
		z-index: 6;
		max-width: 280px;
		padding: 6px 8px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-2);
		box-shadow: var(--v-elev-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: 18px;
		color: var(--v-ink-1);
		pointer-events: none;
	}

	.v2-hover-title {
		font-weight: 600;
	}

	.v2-hover-item {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.v2-hover-hint {
		margin-top: 2px;
		color: var(--v-ink-2);
	}

	@media (prefers-reduced-motion: reduce) {
		.pulse {
			animation: none;
			opacity: 0.5;
		}
	}
</style>
