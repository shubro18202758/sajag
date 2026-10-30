<script lang="ts">
	/**
	 * Omnibar (SPEC §5.3, §8.1) — search over every object type and the
	 * command line, ⌘K / Ctrl+K (and `/` outside a field) on every operator
	 * route. 600 px wide, 14vh from the top.
	 *
	 * - Results are grouped by type with counts; each row shows its type
	 *   glyph, its label through the formatter with exactly the matched span
	 *   marked, a subtitle (place or state), and its time on the right (one
	 *   format per group). "Explore all N results in a table" is the last row.
	 * - Enter selects (and flies there when the page has a map); Shift+Enter
	 *   adds to the selection; Ctrl+Enter pins as an inspector tab.
	 * - `kind:`, `state:` and `source:` tokens filter; `>` lists commands,
	 *   including the legacy grammar (fly to, show units near, layer on|off,
	 *   sensor, ask), which also works without the `>`.
	 * - Registration marks: a full mark (or a 6+ character prefix) is matched
	 *   only against watchlisted vehicles, shown masked, with the honest
	 *   empty state of §8.1. With a duty officer NAMED, a complete mark
	 *   additionally offers the officer-only, audited vehicle lookup
	 *   (vehicle-lookup.ts — every lookup is recorded; reads leave only
	 *   through C6) whose result block under the list is an S3 key/value
	 *   block: the unmasked mark, the basis in words, dated reads,
	 *   "Open vehicle" / "Show trail", and the quiet "Lookup recorded ·
	 *   <officer> · <time>" line. The block retires the moment the officer
	 *   signs off — an officer-only result never outlives its officer.
	 *   There is no person search. What the operator
	 *   typed is never echoed raw: a command row that quotes it (ask, units
	 *   near, layer) goes through the mask in any case and spelling
	 *   (mask.ts), the lookup offer and lookup itself run on the canonical
	 *   mark (normMark), and the Explore filter's label never quotes a typed
	 *   mark (search.exploreLabel), since a filter reaches share links and
	 *   saved views.
	 *
	 * ONE omnibar per page (plan R30/X25): the open state is the workspace
	 * store's (`workspace.omnibar`), and only the first mounted instance
	 * installs the ⌘K handler. On canvas routes the canvas mounts it (through
	 * hud/CommandPalette.svelte) with the map callbacks; pages without a map
	 * mount it directly, and the map commands are listed disabled with the
	 * reason "No map on this page".
	 *
	 * Nothing here decides anything: a fly is a camera move, an ask is a
	 * question whose proposals a human applies on the map.
	 */
	import { onMount, tick } from 'svelte';
	import { ACTION_ICON, ACTOR_ICON, eventKindIcon, kindIcon, type IconName } from '$lib/design/icons';
	import { Icon, Kbd, NonIdealState, ProvenanceTag, provideUiLang } from '$lib/ui';
	import { colStamp } from '$lib/ui/format/format';
	import Id from '$lib/ui/format/Id.svelte';
	import Plate from '$lib/ui/format/Plate.svelte';
	import { portal, pushLayer, trapFocus } from '$lib/ui/overlay';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.workspace';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.map';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { streamChat } from '$lib/api/client';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { canvasBus } from '$lib/gods-eye/canvas-bus.svelte';
	import { godsEye } from '$lib/gods-eye/store.svelte';
	import { SENSOR_MODES, resolveUrn, type DirectiveWorld } from '$lib/gods-eye/directives';
	import { parseUrn } from '$lib/gods-eye/city-api';
	import { cityView, landmarkName } from '$lib/city';
	import { PLACE_MARKS, placeMarkName } from '$lib/city/places';
	import { workspace } from '../../workspace.svelte';
	import { liveWorld } from '../../world.svelte';
	import { kindMany, shortStateWord, stateWord } from '../../kinds/generic';
	import { ruleWords } from '../../kinds/recommendation';
	import { localTitle } from '../../display';
	import { COMMAND_EXAMPLES, exploreLabel, isMarkQuery, lookupOfferActive, markEmptyState, matchMark, normMark, parseCommand, search, type Command } from '../../search';
	import { lookupVehicle, lookupView, type LookupOutcome, type LookupView } from '../../vehicle-lookup';
	import { maskMarks } from '../../mask';
	import type { ObjectRow } from '../../types';
	import { claimHotkey, releaseHotkey, typingIn } from './hotkey';
	import HighlightText from './HighlightText.svelte';

	type SensorMode = (typeof SENSOR_MODES)[number];

	let {
		layerIds = [],
		world,
		onfly,
		onhighlight,
		onlayer,
		onsensor,
		/** Render-test seed (audit E round 2): the outcome the result block shows
		 *  without running the lookup. Always null in the app — the tests' only write. */
		seedOutcome = null,
	}: {
		layerIds?: readonly string[];
		/** What the canvas can resolve right now (streamed directives, URN lookups). */
		world?: () => DirectiveWorld;
		/** A point flight (a road's extent, a group of units). */
		onfly?: (lon: number, lat: number, rangeM: number) => void;
		onhighlight?: (urns: string[]) => void;
		onlayer?: (id: string, on: boolean) => void;
		onsensor?: (mode: SensorMode) => void;
		seedOutcome?: LookupOutcome | null;
	} = $props();

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	/** Text this page may show: raw only for a named duty officer, else every mark masked, in any case and spelling. */
	const shown = (s: string) => (ops.officerOn ? s : maskMarks(s));

	/** The map commands need the canvas's callbacks. */
	const hasMap = $derived(!!onfly);
	const noMap = $derived(L('ws_reason_no_map'));

	// ── one ⌘K handler per page ────────────────────────────────────────────

	const slot = Symbol('omnibar');
	/** This instance holds the page's slot: only the holder renders (one command-palette in the DOM, SPEC §12.1.2). */
	let holding = $state(false);
	onMount(() => {
		if (!claimHotkey(slot)) {
			if (import.meta.env.DEV) console.warn('[omnibar] a second Omnibar is mounted on this page: it registers no ⌘K handler and renders nothing (plan R30)');
			return;
		}
		holding = true;
		const onKey = (e: KeyboardEvent) => {
			if ((e.metaKey || e.ctrlKey) && !e.altKey && (e.key === 'k' || e.key === 'K')) {
				e.preventDefault();
				if (workspace.omnibar.open) workspace.closeOmnibar();
				else workspace.openOmnibar();
				return;
			}
			if (e.key === '/' && !e.metaKey && !e.ctrlKey && !e.altKey && !e.defaultPrevented && !typingIn(e) && !workspace.omnibar.open) {
				e.preventDefault();
				workspace.openOmnibar();
			}
		};
		window.addEventListener('keydown', onKey);
		return () => {
			window.removeEventListener('keydown', onKey);
			releaseHotkey(slot);
			holding = false;
		};
	});

	// ── state ──────────────────────────────────────────────────────────────

	const open = $derived(workspace.omnibar.open && holding);
	let panel: HTMLDivElement | undefined = $state();
	let list: HTMLDivElement | undefined = $state();
	let active = $state(0);
	let note = $state<string | null>(null);
	let answer = $state('');
	let asking = $state(false);
	/** The last ask never reached the assistant (the answer block says so). */
	let answerFailed = $state(false);
	let session: string | null = null;
	let controller: AbortController | null = null;

	function close() {
		workspace.closeOmnibar();
	}

	// Esc: the topmost overlay owns it (it never reaches the page, and never navigates)
	$effect(() => {
		if (!open) return;
		return pushLayer(close, () => true, () => panel);
	});

	$effect(() => {
		void workspace.omnibar.query;
		active = 0;
	});

	// ── items ──────────────────────────────────────────────────────────────

	type Mods = { add: boolean; pin: boolean };
	type Item =
		| { type: 'object'; key: string; row: ObjectRow; time: string }
		| { type: 'road'; key: string; road: string; count: number; points: Array<[number, number]> }
		| { type: 'explore'; key: string; total: number; urns: string[] }
		| { type: 'command'; key: string; icon: IconName; label: string; detail?: string | null; reason?: string | null; run: (m: Mods) => void };
	type Prov = { source: 'emulated' | 'simulated' | 'osint'; verification: ReturnType<typeof verifOf> };
	/**
	 * A group of results. `prov` is the one provenance every row shares, said
	 * once in the header (SPEC §9.2: a uniform list's rows carry none); `mixed`
	 * marks the non-live rows of a mixed group with the compact glyph.
	 */
	type Section = { key: string; title: string | null; count: number | null; items: Item[]; prov?: Prov | null; mixed?: boolean };

	const now = $derived.by(() => {
		void liveWorld.tick;
		return Date.now();
	});
	const rows = $derived(open ? liveWorld.graph().all() : []);
	const query = $derived(workspace.omnibar.query);
	const result = $derived(open ? search(rows, query) : null);
	const legacy = $derived(open ? parseCommand(query) : null);

	// ── the officer-only full-mark lookup (FIX-C-PLATESEARCH) ─────────────

	/** True when a named duty officer typed a COMPLETE registration mark (search.lookupOfferActive). */
	const lookupOffer = $derived(lookupOfferActive(result, query, ops.officerOn));
	/** The offer sentence split around the mark, so HI/MR keep their word order (the mark renders as a Plate between). */
	const offerParts = $derived(L('ws_lookup_offer', '\u0000').split('\u0000'));

	let lookupBusy = $state(false);
	// svelte-ignore state_referenced_locally — a SEED on purpose: only the
	// render test writes it; runLookup and the reset effect own every other write
	let lookupOutcome: LookupOutcome | null = $state(seedOutcome);
	let lookupSeq = 0;

	/** A new query retires the block: a result belongs to the query that asked for it.
	 *  FIX-E-LOOKUP: a sign-off retires it too — an officer-only result never outlives
	 *  its officer (the block's own {#if ops.officerOn} guard is defence in depth). */
	$effect(() => {
		void workspace.omnibar.query;
		void ops.officerOn;
		lookupBusy = false;
		lookupOutcome = null;
	});

	const lookupLines = $derived(lookupOutcome ? lookupView(lookupOutcome, lang, now) : null);

	/** The offer's run(): the panel STAYS OPEN — the result block under the list is the answer. */
	async function runLookup(mark: string) {
		const seq = ++lookupSeq;
		lookupBusy = true;
		lookupOutcome = null;
		const outcome = await lookupVehicle(mark);
		if (seq !== lookupSeq || normMark(workspace.omnibar.query) !== mark) return;
		lookupOutcome = outcome;
		lookupBusy = false;
	}

	/** "Open vehicle" (FIX-E-LOOKUP): the looked-up vehicle becomes the selection
	 *  (a map page flies there); the panel closes — the inspector takes over. */
	function openVehicle(lines: LookupView | null) {
		if (!lines?.vehicleUrn) return;
		selection.select(lines.vehicleUrn, { fly: hasMap, source: 'omnibar' });
		close();
	}

	/** "Show trail" (FIX-E-LOOKUP): highlight the lawful reads on the canvas —
	 *  and CLOSE the panel, so it does not sit over the very area it frames
	 *  (audit E round 2, nice-to-have). */
	function showTrail(lines: LookupView | null) {
		if (lines?.readUrns.length) {
			onhighlight?.(lines.readUrns);
			close();
		}
	}

	function distM(a: [number, number], b: [number, number]): number {
		const kx = 111_320 * Math.cos((a[1] * Math.PI) / 180);
		return Math.hypot((a[0] - b[0]) * kx, (a[1] - b[1]) * 110_540);
	}

	function frame(points: Array<[number, number]>) {
		if (!points.length || !onfly) return;
		const lons = points.map((p) => p[0]);
		const lats = points.map((p) => p[1]);
		const lon = (Math.min(...lons) + Math.max(...lons)) / 2;
		const lat = (Math.min(...lats) + Math.max(...lats)) / 2;
		const span = Math.max(distM([Math.min(...lons), lat], [Math.max(...lons), lat]), distM([lon, Math.min(...lats)], [lon, Math.max(...lats)]));
		onfly(lon, lat, Math.min(16_000, Math.max(1600, span * 1.8)));
	}

	function roadsMatching(text: string) {
		const q = text.trim().toLowerCase();
		if (q.length < 3) return [];
		const byRoad = new Map<string, typeof godsEye.segments>();
		for (const s of godsEye.segments) {
			const name = s.roadName ?? '';
			if (!name.toLowerCase().includes(q)) continue;
			byRoad.set(name, [...(byRoad.get(name) ?? []), s]);
		}
		return [...byRoad.entries()].map(([road, segs]) => ({ road, segs }));
	}

	function selectRow(row: ObjectRow, m: Mods) {
		if (m.pin) workspace.pin(row.urn);
		selection.select(row.urn, { fly: hasMap && !m.add, source: 'omnibar', mode: m.add ? 'add' : 'replace' });
		if (!m.add) close();
	}

	const AGENCIES: Record<string, string> = {
		'civic volunteers': 'jan_rakshak',
		'civic volunteer': 'jan_rakshak',
		jan_rakshak: 'jan_rakshak',
		police: 'police',
		traffic: 'traffic',
		ambulance: 'ambulance',
		'108': 'ambulance',
		fire: 'fire',
	};
	const NEAR_M = 1500;

	/** fly to <plate | URN | junction | road>: the targets the canvas can fly to (vehicles by watchlist mark only). */
	function flyTargets(text: string): Item[] {
		const out: Item[] = [];
		const q = text.trim();
		if (!q) return out;
		const g = liveWorld.graph();
		const push = (row: ObjectRow) => {
			if (out.some((i) => i.key === row.urn)) return;
			out.push({
				type: 'command',
				key: row.urn,
				icon: row.icon,
				label: `${L('ws_cmd_fly')} ${row.label}`,
				detail: [kindMany(row.kind, lang), stateWord(row.state, lang)].filter(Boolean).join(' · '),
				reason: hasMap ? null : noMap,
				run: () => selectRow(row, { add: false, pin: false }),
			});
		};
		// a named view of the city (city pack `views`: "sea link", "marine drive", "BKC", "dadar", "andheri" …), then
		// the pack's labelled places by name (landmarks, areas): reference geography, flown to, never selected
		const view = cityView(q);
		if (view) {
			out.push({
				type: 'command',
				key: `view:${view.id}`,
				icon: kindIcon('place'),
				label: `${L('ws_cmd_fly')} ${landmarkName(view.id, lang)}`,
				detail: null,
				reason: hasMap ? null : noMap,
				run: () => {
					onfly?.(view.lon, view.lat, view.range);
					close();
				},
			});
		}
		if (q.length >= 3) {
			const fq = q.toLowerCase();
			for (const p of PLACE_MARKS) {
				if (p.tier > 2 || out.length > 6 || (view && p.id === `lm_${view.id}`)) continue;
				const name = placeMarkName(p, lang);
				if (!(name.toLowerCase().includes(fq) || p.en.toLowerCase().includes(fq))) continue;
				out.push({
					type: 'command',
					key: `placemark:${p.id}`,
					icon: kindIcon('place'),
					label: `${L('ws_cmd_fly')} ${name}`,
					detail: null,
					reason: hasMap ? null : noMap,
					run: () => {
						onfly?.(p.lon, p.lat, p.tier === 1 ? 2600 : 4000);
						close();
					},
				});
			}
		}
		const asUrn = world ? resolveUrn(q, world()) : null;
		const urn = asUrn?.urn && asUrn.resolved ? asUrn.urn : parseUrn(q) ? q : null;
		if (urn) {
			const row = g.get(urn);
			if (row) push(row);
		}
		// a plate: the registry's watchlisted vehicles only (§8.1, the search's own rule), never echoed
		for (const v of matchMark(g.byKind('vehicle'), q)) push(v);
		const jNum = /^(?:j|junction\s*)(\d{1,6})$/i.exec(q);
		for (const j of g.byKind('junction')) {
			if ((jNum && j.id === jNum[1]) || (q.length >= 3 && j.label.toLowerCase().includes(q.toLowerCase()))) push(j);
		}
		for (const { road, segs } of roadsMatching(q)) {
			out.push({
				type: 'command',
				key: `road:${road}`,
				icon: kindIcon('road'),
				label: `${L('ws_cmd_fly')} ${road}`,
				detail: L('ws_cmd_segments', segs.length),
				reason: hasMap ? null : noMap,
				run: () => {
					frame(segs.flatMap((s) => s.coordinates as Array<[number, number]>));
					close();
				},
			});
		}
		if (q.length >= 3) {
			for (const kind of ['camera', 'unit', 'event', 'convoy', 'osint_event', 'place']) {
				for (const e of g.byKind(kind)) {
					if (e.label.toLowerCase().includes(q.toLowerCase()) || e.id.toLowerCase() === q.toLowerCase()) push(e);
				}
			}
		}
		return out.slice(0, 8);
	}

	function unitsNear(agencyWord: string | null, road: string): Item[] {
		const agency = agencyWord ? (AGENCIES[agencyWord.trim().toLowerCase()] ?? null) : null;
		const segs = godsEye.segments.filter((s) => (s.roadName ?? '').toLowerCase().includes(road.trim().toLowerCase()));
		if (!segs.length) {
			return [{ type: 'command', key: 'units:none', icon: kindIcon('unit'), label: L('ws_cmd_unknown_road'), detail: shown(road), reason: hasMap ? null : noMap, run: () => (note = L('ws_cmd_unknown_road')) }];
		}
		const pts = segs.flatMap((s) => s.coordinates as Array<[number, number]>);
		const units = godsEye.units.filter((u) => (!agency || u.agency === agency) && pts.some((p) => distM([u.lon, u.lat], p) <= NEAR_M));
		const roadName = shown(segs[0].roadName ?? road);
		const label = units.length ? L('ws_cmd_units_near', units.length, roadName) : L('ws_cmd_none_near', roadName);
		return [
			{
				type: 'command',
				key: `units:${agency ?? 'all'}:${roadName}`,
				icon: kindIcon('unit'),
				label,
				detail: L('ws_cmd_units_detail'),
				reason: onhighlight && hasMap ? null : noMap,
				run: () => {
					onhighlight?.(units.map((u) => `unit:${u.unitId}`));
					frame([...pts, ...units.map((u) => [u.lon, u.lat] as [number, number])]);
					note = label;
					close();
				},
			},
		];
	}

	function ask(question: string) {
		controller?.abort();
		const ctrl = new AbortController();
		controller = ctrl;
		answer = '';
		asking = true;
		answerFailed = false;
		// F-01: nothing is claimed before the assistant answers — "Asking…" until the
		// first token (or the done line) proves the question arrived
		note = null;
		const arrived = () => {
			if (controller === ctrl && note === null) note = L('ws_cmd_sent');
		};
		/** The assistant never answered: say so as the answer, and claim nothing was sent. */
		const unreachable = () => {
			if (ctrl.signal.aborted || controller !== ctrl) return;
			answer = L('ws_cmd_unreachable');
			answerFailed = true;
			note = null;
			asking = false;
		};
		void streamChat(
			question,
			null,
			null,
			{
				onToken: (tok) => {
					answer += tok;
					arrived();
				},
				onThought: () => {},
				onToolCall: () => {},
				onToolResult: () => {},
				// a proposal queues on the map as "AI suggests"; a human applies it
				onDirective: (d) => canvasBus.offer(d, world ? world() : null),
				onDone: (d) => {
					if (d.sessionId) session = d.sessionId;
					arrived();
					asking = false;
				},
				onError: () => unreachable(),
			},
			{ sessionId: session, signal: ctrl.signal, eventId: ops.selectedEventId },
		).catch(() => unreachable());
	}

	/** The catalogue label of a template (the row the officer picked). */
	const TEMPLATE_LABEL: Record<string, string> = {
		fly: 'ws_cmd_tpl_fly',
		units: 'ws_cmd_tpl_units',
		layer: 'ws_cmd_tpl_layer',
		sensor: 'ws_cmd_tpl_sensor',
		ask: 'ws_cmd_tpl_ask',
	};

	const TEMPLATE_ICON: Record<string, IconName> = {
		fly: ACTION_ICON.show_on_map,
		units: kindIcon('unit'),
		layer: 'layers',
		sensor: 'eye-open',
		ask: ACTOR_ICON.ai,
	};

	function legacyItems(c: Command): Item[] {
		switch (c.type) {
			case 'incomplete':
				// F-20: the template's head alone — say what to type next (a row that cannot run, with its reason)
				return [
					{
						type: 'command',
						key: `incomplete:${c.template}`,
						icon: TEMPLATE_ICON[c.template],
						label: L(TEMPLATE_LABEL[c.template]),
						reason: L('ws_cmd_incomplete', COMMAND_EXAMPLES[c.template]),
						run: () => {},
					},
				];
			case 'fly':
				return flyTargets(c.target);
			case 'units':
				return unitsNear(c.agency, c.road);
			case 'layer': {
				const known = layerIds.includes(c.id);
				return [
					{
						type: 'command',
						key: `layer:${c.id}`,
						icon: c.on ? ACTION_ICON.layer_visible : ACTION_ICON.layer_hidden,
						label: L(c.on ? 'ws_cmd_layer_on' : 'ws_cmd_layer_off', shown(c.id)),
						reason: !onlayer ? noMap : known ? null : L('ws_reason_no_layer'),
						run: () => {
							onlayer?.(c.id, c.on);
							close();
						},
					},
				];
			}
			case 'sensor': {
				const known = (SENSOR_MODES as readonly string[]).includes(c.mode);
				return [
					{
						type: 'command',
						key: `sensor:${c.mode}`,
						icon: 'eye-open',
						// FIX-E-LOOKUP: the palette in words (map_pal_*), never the raw
						// flir-* id and never a "sensor" — the view is a visual filter.
						// Audit E round 2: an UNKNOWN mode never quotes the typed word
						// inside a localised sentence (the refusal is the whole row).
						label: known ? L('ws_cmd_sensor', paletteWord(c.mode)) : L('map_tool_thermal'),
						detail: L('ws_cmd_sensor_detail'),
						reason: !onsensor ? noMap : known ? null : L('ws_reason_no_sensor'),
						run: () => {
							onsensor?.(c.mode as SensorMode);
							close();
						},
					},
				];
			}
			case 'ask':
				return [
					{
						type: 'command',
						key: 'ask',
						icon: ACTOR_ICON.ai,
						label: `${L('ws_cmd_ask')}: ${shown(c.question)}`,
						detail: L('ws_cmd_ask_detail'),
						run: () => ask(c.question),
					},
				];
		}
	}

	/** A thermal mode in words (the map pack's short palette names, FIX-E-LOOKUP):
	 *  the raw flir-* ids are grammar, never console copy. */
	function paletteWord(mode: string): string {
		if (mode === 'raw') return L('map_pal_raw');
		if (mode === 'flir-whot') return L('map_pal_whot');
		if (mode === 'flir-bhot') return L('map_pal_bhot');
		if (mode === 'flir-iron') return L('map_pal_iron');
		return shown(mode);
	}

	/** The command catalogue (`>`): templates of the legacy grammar, then workspace commands that apply now. */
	function catalogue(): Item[] {
		const tpl = (key: string, icon: IconName, label: string, fill: string, map: boolean, detail: string | null = null): Item => ({
			type: 'command',
			key,
			icon,
			label,
			detail,
			reason: map && !hasMap ? noMap : null,
			run: () => {
				workspace.omnibar.query = fill;
			},
		});
		const out: Item[] = [
			tpl('tpl:fly', ACTION_ICON.show_on_map, L('ws_cmd_tpl_fly'), 'fly to ', true, L('ws_cmd_tpl_fly_detail')),
			tpl('tpl:units', kindIcon('unit'), L('ws_cmd_tpl_units'), 'show police units near ', true),
			tpl('tpl:layer', 'layers', L('ws_cmd_tpl_layer'), 'layer ', true, layerIds.length ? layerIds.slice(0, 6).join(', ') : null),
			tpl('tpl:sensor', 'eye-open', L('ws_cmd_tpl_sensor'), 'sensor ', true, SENSOR_MODES.map(paletteWord).join(', ')),
			tpl('tpl:ask', ACTOR_ICON.ai, L('ws_cmd_tpl_ask'), 'ask ', false),
		];
		if (!workspace.live) {
			out.push({ type: 'command', key: 'cmd:live', icon: ACTION_ICON.return_to_live, label: L('ws_return_to_live'), run: () => (workspace.returnToLive(), close()) });
		}
		if (workspace.filters.length) {
			out.push({ type: 'command', key: 'cmd:filters', icon: 'filter-remove', label: L('ws_clear_filters'), run: () => (workspace.clearFilters(), close()) });
		}
		if (selection.current) {
			out.push({ type: 'command', key: 'cmd:clear', icon: 'cross', label: L('ws_cmd_clear_selection'), run: () => (selection.clear(), close()) });
		}
		return out;
	}

	/** The provenance a group states once (every row the same, not live), and whether its rows differ. */
	function groupProv(list: readonly ObjectRow[]): { prov: Prov | null; mixed: boolean } {
		const keys = new Set(list.map((r) => `${r.source}|${r.source === 'osint' ? (verifOf(r) ?? '') : ''}`));
		if (keys.size !== 1) return { prov: null, mixed: true };
		const p = list.length ? provOf(list[0]) : null;
		return { prov: p ? { source: p, verification: p === 'osint' ? verifOf(list[0]) : null } : null, mixed: false };
	}

	const sections = $derived.by((): Section[] => {
		if (!open) return [];
		const q = query.trim();
		if (legacy) {
			const items = legacyItems(legacy);
			// nothing to fly to: an honest empty state below, never an empty "Commands" header
			return items.length ? [{ key: 'legacy', title: L('ws_omni_commands'), count: null, items }] : [];
		}
		if (q.startsWith('>')) {
			const cq = q.slice(1).trim().toLowerCase();
			const items = catalogue().filter((c) => c.type === 'command' && (!cq || c.label.toLowerCase().includes(cq)));
			return [{ key: 'commands', title: L('ws_omni_commands'), count: null, items }];
		}
		if (!q || !result) return [{ key: 'commands', title: L('ws_omni_commands'), count: null, items: catalogue() }];
		const out: Section[] = [];
		if (lookupOffer) {
			// the officer-only, audited full-mark lookup: FIRST, so Enter runs it (the
			// mark-empty guard below lets the sections render for a mark nothing watches).
			// FIX-E-LOOKUP: the label and the lookup run on the CANONICAL mark
			// (normMark), never on the raw typed query.
			out.push({
				key: 'lookup',
				title: null,
				count: null,
			items: [
				{
					type: 'command',
					key: 'vehicle-lookup',
					icon: kindIcon('vehicle'),
					label: L('ws_lookup_offer', normMark(q)),
					detail: L('ws_lookup_offer_detail'),
					run: () => void runLookup(normMark(q)),
				},
			],
			});
		}
		for (const g of result.groups.slice(0, 6)) {
			const times = colStamp(
				g.items.map((r) => r.t),
				now,
			);
			out.push({
				key: `g:${g.kind}`,
				title: kindMany(g.kind, lang),
				count: g.total,
				items: g.items.map((row, i) => ({ type: 'object', key: row.urn, row, time: row.t != null ? times[i] : '' })),
				...groupProv(g.items),
			});
		}
		if (!result.mark && hasMap) {
			const roads = roadsMatching(q).slice(0, 3);
			if (roads.length) {
				out.push({
					key: 'g:road',
					title: kindMany('segment', lang),
					count: roads.length,
					items: roads.map(({ road, segs }) => ({ type: 'road', key: `road:${road}`, road, count: segs.length, points: segs.flatMap((s) => s.coordinates as Array<[number, number]>) })),
				});
			}
		}
		if (result.total > 0) out.push({ key: 'explore', title: null, count: null, items: [{ type: 'explore', key: 'explore', total: result.total, urns: result.urns }] });
		if (!result.mark) {
			const lq = q.toLowerCase();
			const cmds = catalogue()
				.filter((c) => c.type === 'command' && c.label.toLowerCase().includes(lq))
				.slice(0, 3);
			if (cmds.length) out.push({ key: 'commands', title: L('ws_omni_commands'), count: null, items: cmds });
		}
		return out;
	});

	const flat = $derived(sections.flatMap((s) => s.items));
	/**
	 * `fly to <target>` that resolves to nothing: a registration mark gets the
	 * §8.1 empty state (the watchlist only), anything else an explicit "Nothing
	 * to fly to" — never an empty section.
	 */
	const flyEmpty = $derived.by((): 'mark' | 'none' | null => {
		if (!legacy || legacy.type !== 'fly' || sections.length) return null;
		return isMarkQuery(legacy.target) ? 'mark' : 'none';
	});
	const markEmpty = $derived((!!result?.mark && result.total === 0) || flyEmpty === 'mark');
	const noMatch = $derived(!!result && !result.mark && !legacy && !lookupOffer && result.total === 0 && query.trim().length > 0 && !query.trim().startsWith('>'));
	const mark = $derived(markEmptyState(lang));

	function run(item: Item | undefined, m: Mods) {
		if (!item) return;
		if (item.type === 'object') selectRow(item.row, m);
		else if (item.type === 'road') {
			if (!hasMap) return;
			frame(item.points);
			close();
		} else if (item.type === 'explore') {
			// the label never quotes a typed mark (the filter reaches share links and saved views)
			workspace.addFilter({ field: 'urns', values: item.urns, label: result ? exploreLabel(result, lang) : L('ws_filter_results', '') });
			workspace.view = 'table';
			close();
		} else if (!item.reason) item.run(m);
	}

	function onInputKey(e: KeyboardEvent) {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			active = Math.min(flat.length - 1, active + 1);
			void scrollActive();
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			active = Math.max(0, active - 1);
			void scrollActive();
		} else if (e.key === 'Enter') {
			e.preventDefault();
			run(flat[active], { add: e.shiftKey, pin: e.ctrlKey || e.metaKey });
		}
	}

	async function scrollActive() {
		await tick();
		list?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' });
	}

	const indexOf = (item: Item) => flat.indexOf(item);

	function rowIcon(row: ObjectRow): IconName {
		return row.kind === 'event' ? eventKindIcon(typeof row.props.event_kind === 'string' ? row.props.event_kind : null) : kindIcon(row.kind);
	}

	/** The main text of an object row, and whether it is an identifier (the formatter's mono face). */
	function mainOf(row: ObjectRow): { text: string; mono: boolean; lead?: string } {
		if (row.kind === 'vehicle' || row.kind === 'camera' || row.kind === 'sighting' || row.kind === 'unit') return { text: row.label, mono: true };
		if (row.kind === 'recommendation') {
			// the rule in the omnibar's language, then the camera id (the label's EN words are the search's)
			const i = row.label.lastIndexOf(' · ');
			if (i > 0) return { lead: `${ruleWords(row.props.rule_id, lang)} · `, text: row.label.slice(i + 3), mono: true };
			return { text: ruleWords(row.props.rule_id, lang), mono: false };
		}
		return { text: localTitle(row.label, lang), mono: false };
	}

	/** The provenance a row shows (live rows are unmarked, SPEC §9.2). */
	function provOf(row: ObjectRow): 'emulated' | 'simulated' | 'osint' | null {
		return row.source === 'emulated' || row.source === 'simulated' || row.source === 'osint' ? row.source : null;
	}

	/** An OSINT row's verification label, when it is one ProvenanceTag knows. */
	function verifOf(row: ObjectRow): 'UNVERIFIED-OSINT' | 'NEWS-REPORTED' | 'OFFICIAL-VERIFIED' | 'CONFIRMED' | null {
		const v = row.verification;
		return v === 'UNVERIFIED-OSINT' || v === 'NEWS-REPORTED' || v === 'OFFICIAL-VERIFIED' || v === 'CONFIRMED' ? v : null;
	}

	/** The subtitle of an object row: a place, a state, a list. */
	function subOf(row: ObjectRow): string | null {
		if (row.kind === 'vehicle') return row.props.lawful_basis === 'stolen_vehicle_fir' ? L('ws_omni_sub_stolen') : L('ws_tag_watchlist');
		if (row.kind === 'sighting') {
			const cam = typeof row.props.camera_id === 'string' ? liveWorld.graph().get(`camera:${row.props.camera_id}`) : null;
			return [row.sublabel, cam?.sublabel].filter(Boolean).join(' · ') || null;
		}
		// a list row says a state in one short word ("Pending"), as the Links tab does
		if (row.kind === 'recommendation') return [shortStateWord(row.state, lang), row.sublabel].filter(Boolean).join(' · ');
		if (row.kind === 'event') return stateWord(row.state, lang);
		return row.sublabel;
	}
</script>

{#if open}
	<div class="omni-root" use:portal>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="backdrop" onclick={close}></div>
		<div
			class="omnibar"
			role="dialog"
			aria-modal="true"
			aria-label={L('ws_omni_label')}
			data-testid="command-palette"
			data-ui-overlay="modal"
			bind:this={panel}
			use:trapFocus
		>
			<div class="oi">
				<Icon name="search" size={20} class="oi-glyph" />
				<input
					bind:value={workspace.omnibar.query}
					onkeydown={onInputKey}
					placeholder={L('ws_omni_placeholder')}
					aria-label={L('ws_omni_label')}
					aria-controls="omni-results"
					data-testid="palette-input"
					data-autofocus
					autocomplete="off"
					spellcheck="false"
				/>
				<span class="hint"><Kbd>kind:</Kbd><Kbd>state:</Kbd><Kbd>&gt;</Kbd><span>{L('ws_omni_hint_commands')}</span></span>
			</div>

			<div class="res" id="omni-results" role="listbox" aria-label={L('ws_omni_label')} bind:this={list}>
				{#if markEmpty && !lookupOffer}
					<div class="empty" data-testid="omni-mark-empty">
						<NonIdealState icon={ACTION_ICON.masked} iconSize={20} title={mark.title} description={mark.body} />
					</div>
				{:else if flyEmpty === 'none'}
					<div class="empty" data-testid="omni-fly-empty">
						<NonIdealState icon={ACTION_ICON.show_on_map} iconSize={20} title={L('ws_omni_fly_none')} description={L('ws_omni_fly_none_hint')} />
					</div>
				{:else if noMatch}
					<div class="empty">
						<NonIdealState icon="search" iconSize={20} title={L('ws_omni_none')} description={L('ws_omni_none_hint')} />
					</div>
				{:else}
					{#each sections as s (s.key)}
						{#if s.title}
							<div class="menu-head" role="presentation">
								<span>{s.title}</span>{#if s.count != null}<span class="n">{s.count}</span>{/if}{#if s.prov}<ProvenanceTag
										source={s.prov.source}
										verification={s.prov.verification}
										class="head-prov"
									/>{/if}
							</div>
						{:else if s.key === 'explore'}
							<div class="menu-div" role="presentation"></div>
						{/if}
						{#each s.items as item (item.key)}
							{@const i = indexOf(item)}
							{@const on = i === active}
							{#if item.type === 'object'}
								{@const m = mainOf(item.row)}
								{@const sub = subOf(item.row)}
								{@const prov = provOf(item.row)}
								<div
									class="item"
									class:is-selected={on}
									role="option"
									tabindex="-1"
									aria-selected={on}
									data-active={on}
									data-urn={item.row.urn}
									data-kind={item.row.kind}
									onmouseenter={() => (active = i)}
									onclick={(e) => run(item, { add: e.shiftKey, pin: e.ctrlKey || e.metaKey })}
									onkeydown={() => {}}
								>
									<Icon name={rowIcon(item.row)} class="glyph" />
									<span class="main">
										<span class="lblw"
											><span class="lbl"
												>{#if m.lead}<HighlightText text={m.lead} words={result?.words ?? []} />{/if}<HighlightText
													text={m.text}
													words={result?.words ?? []}
													mono={m.mono}
												/></span
											>{#if item.row.kind === 'vehicle'}<Icon name={ACTION_ICON.masked} size={12} class="lock" title={L('ws_v_masked')} />{/if}</span
										>
										{#if sub}<span class="sub"><HighlightText text={sub} words={result?.words ?? []} /></span>{/if}
									</span>
									{#if selection.has(item.row.urn)}<Icon name="tick" size={16} class="picked" title={L('ws_omni_in_selection')} />{/if}
									{#if item.row.test}<ProvenanceTag source="test" />{/if}
									{#if prov && s.mixed}<ProvenanceTag source={prov} verification={verifOf(item.row)} compact />{/if}
									<span class="when">{item.time}</span>
								</div>
							{:else if item.type === 'road'}
								<div
									class="item"
									class:is-selected={on}
									role="option"
									tabindex="-1"
									aria-selected={on}
									data-active={on}
									onmouseenter={() => (active = i)}
									onclick={() => run(item, { add: false, pin: false })}
									onkeydown={() => {}}
								>
									<Icon name={kindIcon('road')} class="glyph" />
									<span class="main"
										><span class="lbl"><HighlightText text={item.road} words={result?.words ?? []} /></span><span class="sub"
											>{L('ws_cmd_segments', item.count)}</span
										></span
									>
								</div>
							{:else if item.type === 'explore'}
								<div
									class="item explore"
									class:is-selected={on}
									role="option"
									tabindex="-1"
									aria-selected={on}
									data-active={on}
									data-testid="omni-explore"
									onmouseenter={() => (active = i)}
									onclick={() => run(item, { add: false, pin: false })}
									onkeydown={() => {}}
								>
									<Icon name="th" class="glyph" />
									<span class="main"><span class="lbl">{L('ws_omni_explore', item.total)}</span></span>
									<span class="when"><Kbd>↵</Kbd></span>
								</div>
							{:else}
								<div
									class="item cmd"
									class:is-selected={on}
									class:disabled={!!item.reason}
									role="option"
									tabindex="-1"
									aria-selected={on}
									aria-disabled={!!item.reason}
									data-active={on}
									data-key={item.key}
									title={item.reason ?? undefined}
									onmouseenter={() => (active = i)}
									onclick={(e) => run(item, { add: e.shiftKey, pin: e.ctrlKey || e.metaKey })}
									onkeydown={() => {}}
								>
									<Icon name={item.icon} class="glyph" />
									<span class="main">
										<!-- FIX-E-LOOKUP audit E: the lookup offer's echoed mark in
										     the mono id voice — the format dir's Plate, as the block
										     renders it (the row is officer-gated, so unmasked) -->
										{#if item.type === 'command' && item.key === 'vehicle-lookup'}
											<span class="lbl">{offerParts[0]}<Plate mark={normMark(query)} masked={false} />{offerParts[1]}</span>
										{:else}
											<span class="lbl">{item.label}</span>
										{/if}
										{#if item.reason}<span class="sub reason">{item.reason}</span>{:else if item.detail}<span class="sub">{item.detail}</span>{/if}
									</span>
								</div>
							{/if}
						{/each}
					{/each}
				{/if}
			</div>

			{#if asking || answer}
				<p class="answer" data-testid="palette-answer" data-status={asking ? 'streaming' : answerFailed ? 'error' : 'done'}>
					<Icon name={ACTOR_ICON.ai} size={16} class="ai" />
					<span>{answer ? shown(answer) : L('ws_cmd_asking')}</span>
				</p>
			{/if}
			{#if note}<p class="note">{shown(note)}</p>{/if}

			{#if lookupBusy}
				<p class="note" data-testid="omni-lookup" data-status="running">{L('ws_lookup_running')}</p>
			{:else if lookupLines && ops.officerOn}
				<!-- FIX-E-LOOKUP: the S3 result block — a section header, key/value
				     pairs with human labels, dated reads, actions, the audit line.
				     Officer-gated twice: the reset effect retires the outcome on
				     sign-off, and this guard would hide a stale block regardless. -->
				<div class="lookup" data-testid="omni-lookup" data-status={lookupLines.state}>
					<p class="lk-head">{L('ws_lookup_heading')}</p>
					{#if lookupLines.state === 'found'}
						<div class="lk-grid">
							{#if lookupLines.mark}
								<span class="k">{L('ws_lookup_k_mark')}</span>
								<span class="v"><Plate mark={shown(lookupLines.mark)} masked={!ops.officerOn} /></span>
							{/if}
							<span class="k">{L('ws_lookup_k_status')}</span>
							<span class="v">{lookupLines.heading}</span>
							{#if lookupLines.recommendations != null}
								<span class="k">{L('ws_lookup_recommendations')}</span>
								<span class="v num">{lookupLines.recommendations}</span>
							{/if}
							{#if lookupLines.pursuits != null}
								<span class="k">{L('ws_lookup_pursuits')}</span>
								<span class="v num">{lookupLines.pursuits}</span>
							{/if}
						</div>
						{#if lookupLines.readRows.length}
							<!-- FIX-E-LOOKUP audit E: the reads are their OWN group under
							     "Lawful camera reads" (with the count), not rows hanging
							     under "Open pursuits"; the camera id in the mono id voice -->
							<div class="lk-reads">
								<p class="lk-subhead">{L('ws_lookup_reads')}{lookupLines.reads != null ? ` · ${lookupLines.reads}` : ''}</p>
								{#each lookupLines.readRows as row}
									{@const c = row.indexOf(' · ')}
									<p class="lk-sub">{#if c > 0}<Id value={row.slice(0, c)} />{row.slice(c)}{:else}{row}{/if}</p>
								{/each}
								{#if lookupLines.moreReads}<p class="lk-sub">{L('ws_lookup_more_reads', lookupLines.moreReads)}</p>{/if}
							</div>
						{/if}
						{#if lookupLines.note}<p class="lk-note">{lookupLines.note}</p>{/if}
						{#if lookupLines.vehicleUrn || (hasMap && lookupLines.readUrns.length)}
							<div class="lk-actions">
								{#if lookupLines.vehicleUrn}
									<button type="button" class="lk-btn" data-testid="omni-lookup-open" onclick={() => openVehicle(lookupLines)}>
										<Icon name={kindIcon('vehicle')} size={12} />{L('ws_lookup_open_vehicle')}
									</button>
								{/if}
								{#if hasMap && lookupLines.readUrns.length}
									<button type="button" class="lk-btn" data-testid="omni-lookup-trail" onclick={() => showTrail(lookupLines)}>
										<Icon name={ACTION_ICON.show_on_map} size={12} />{L('ws_lookup_show_trail')}
									</button>
								{/if}
							</div>
						{/if}
					{:else}
						{#if lookupLines.mark}
							<div class="lk-grid">
								<span class="k">{L('ws_lookup_k_mark')}</span>
								<span class="v"><Plate mark={shown(lookupLines.mark)} masked={!ops.officerOn} /></span>
							</div>
						{/if}
						<p class="lk-note">{lookupLines.heading}</p>
						{#if lookupLines.detail}<p class="lk-note">{lookupLines.detail}</p>{/if}
					{/if}
					{#if lookupLines.recorded}<p class="lk-stamp">{lookupLines.recorded}</p>{/if}
				</div>
			{/if}

			<footer class="ofoot">
				<span><Kbd keys={['↑', '↓']} />{L('ws_omni_move')}</span>
				<span><Kbd>↵</Kbd>{L('ws_omni_open')}</span>
				<span><Kbd keys={['Shift', '↵']} />{L('ws_omni_add')}</span>
				<span><Kbd keys={['Ctrl', '↵']} />{L('ws_omni_pin')}</span>
				<span><Kbd>Esc</Kbd>{L('ws_omni_close')}</span>
				<span class="rail"><Icon name={ACTION_ICON.policies} size={12} />{L('ws_omni_vehicles_only')}</span>
			</footer>
		</div>
	</div>
{/if}

<style>
	/* above every page layer (the legacy City Command overlay sits at 40), under tooltips */
	.omni-root {
		position: fixed;
		inset: 0;
		z-index: calc(var(--v-z-tooltip) - 1);
	}

	.backdrop {
		position: absolute;
		inset: 0;
		background: color-mix(in srgb, var(--v-canvas) 45%, transparent);
	}

	.omnibar {
		position: absolute;
		top: 14vh;
		left: 50%;
		transform: translateX(-50%);
		width: min(600px, calc(100vw - 32px));
		display: flex;
		flex-direction: column;
		background: var(--v-surface-2);
		color: var(--v-ink-1);
		border-radius: var(--v-radius-panel);
		box-shadow: var(--v-elev-4);
		overflow: hidden;
		font-size: 14px;
		line-height: 18px;
	}

	.oi {
		position: relative;
		display: flex;
		align-items: center;
		height: 44px;
		border-bottom: 1px solid var(--v-line-1);
	}

	.oi :global(.oi-glyph) {
		position: absolute;
		left: 12px;
		color: var(--v-ink-2);
	}

	.oi input {
		width: 100%;
		height: 44px;
		padding: 0 176px 0 44px;
		border: 0;
		outline: 0;
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		font-size: 16px;
	}

	.oi input::placeholder {
		color: var(--v-ink-2);
	}

	.hint {
		position: absolute;
		right: 12px;
		display: inline-flex;
		align-items: center;
		gap: 4px;
		font-size: 12px;
		color: var(--v-ink-2);
		white-space: nowrap;
		pointer-events: none;
	}

	.res {
		max-height: 56vh;
		overflow-y: auto;
		padding: 4px;
	}

	.menu-head {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 8px 4px;
		font-size: 12px;
		font-weight: 600;
		color: var(--v-ink-2);
	}

	.menu-head .n {
		font-weight: 400;
		font-variant-numeric: tabular-nums;
	}

	/* a uniform group says its provenance once, at the header's end (above the time column) */
	.menu-head :global(.head-prov) {
		margin-left: auto;
		font-weight: 400;
	}

	.menu-div {
		height: 1px;
		margin: 4px 0;
		background: var(--v-line-1);
	}

	.item {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 32px;
		padding: 4px 8px;
		border-radius: var(--v-radius-chip);
		cursor: pointer;
		white-space: nowrap;
	}

	.item :global(.glyph) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.item:hover {
		background: var(--v-hover);
	}

	.item.is-selected {
		background: var(--v-primary-veil);
	}

	.item.is-selected :global(.glyph) {
		color: var(--v-primary-text);
	}

	.item.disabled {
		cursor: default;
		color: var(--v-ink-disabled);
	}

	.main {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		flex: 1 1 auto;
		overflow: hidden;
	}

	/* the label and a vehicle's lock: a centred pair, the lock 4 px after the mark (as the formatter's Plate) */
	.lblw {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		flex: 0 1 auto;
		min-width: 0;
	}

	/* text flow (not flex): the runs of a highlighted label keep their spaces */
	.lbl {
		display: block;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.lblw :global(.lock) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	/* the label keeps its width; the subtitle takes what is left and ellipsises */
	.sub {
		flex: 1 1 0;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 12px;
		color: var(--v-ink-2);
	}

	.sub.reason {
		color: var(--v-ink-2);
	}

	.item :global(.picked) {
		color: var(--v-primary-text);
	}

	.when {
		margin-left: auto;
		padding-left: 16px;
		display: inline-flex;
		align-items: center;
		font-size: 12px;
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
	}

	.empty {
		padding: 16px 24px;
	}

	.answer {
		display: flex;
		gap: 8px;
		margin: 0;
		padding: 8px 12px;
		max-height: 8rem;
		overflow-y: auto;
		border-top: 1px solid var(--v-line-1);
		font-size: 14px;
		line-height: 21px;
		white-space: pre-wrap;
	}

	.answer :global(.ai) {
		flex: 0 0 auto;
		margin-top: 2px;
		color: var(--v-ai-text);
	}

	.note {
		margin: 0;
		padding: 4px 12px 8px;
		font-size: 12px;
		color: var(--v-ink-2);
	}

	/* the officer-only lookup's result block (a sibling of .answer/.note, same
	   voice; FIX-E-LOOKUP: a section header, key/value pairs, actions) */
	.lookup {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 8px 12px;
		max-height: 16rem;
		overflow-y: auto;
		border-top: 1px solid var(--v-line-1);
	}

	.lookup p {
		margin: 0;
		font-size: 12px;
		line-height: 17px;
		color: var(--v-ink-2);
	}

	/* the section header (the menu-head voice) */
	.lk-head {
		font-size: 12px;
		font-weight: 600;
		color: var(--v-ink-2);
	}

	/* key/value: the label column, then the value — the inspector's PropertyTable voice
	   (audit E round 2: the keys take the muted key voice, 12 px, ink-3) */
	.lk-grid {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 2px 16px;
		align-items: baseline;
	}

	.lk-grid .k {
		color: var(--v-ink-3);
		font-size: 12px;
	}

	.lk-grid .v {
		color: var(--v-ink-1);
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.lk-grid .v.num {
		font-variant-numeric: tabular-nums;
	}

	/* the reads' own group: the sub-head speaks the "Lawful camera reads" key */
	.lk-subhead {
		margin: 4px 0 0;
		font-size: 12px;
		font-weight: 600;
		color: var(--v-ink-2);
	}

	.lk-sub,
	.lk-stamp {
		font-variant-numeric: tabular-nums;
	}

	/* a read row's camera id takes the format dir's Id chip; the row keeps its
	   room around it (audit E round 2) */
	.lk-sub :global([data-ui='id']) {
		margin-right: 1px;
	}

	.lk-actions {
		display: flex;
		gap: 6px;
		padding-top: 2px;
	}

	.lk-btn {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 8px;
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-1);
		color: var(--v-ink-1);
		font: inherit;
		font-size: 12px;
		line-height: 16px;
		cursor: pointer;
	}

	.lk-btn:hover {
		background: var(--v-hover);
	}

	.ofoot {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 8px 12px;
		border-top: 1px solid var(--v-line-1);
		background: var(--v-surface-1);
		font-size: 12px;
		color: var(--v-ink-2);
		white-space: nowrap;
		overflow: hidden;
	}

	.ofoot > span {
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}

	.ofoot .rail {
		margin-left: auto;
	}
</style>
