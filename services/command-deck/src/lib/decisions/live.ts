/**
 * The LiveStrip feed (SPEC §5.3 LiveStrip, §7.3 interrupts; plan X21):
 * `liveStripFeed()` returns the S1B `LiveStripFeed` the pages copy into
 * `commandBar.live`, or null when nothing is live. The shell never imports a
 * store (R4): everything the strip shows is computed here, already masked.
 *
 *   movement    the active protected movement (its class, the convoy's
 *               speed from the city registry; next junction and ETA only
 *               when the feed reports them — never invented)
 *   pursuits    every open vehicle_pursuit: the pursued vehicle's MASKED
 *               mark, its last read's age and heading; selects the vehicle
 *   soonest     the decision unit with the soonest deadline (an escort
 *               proposal's expiry, a 108 request's golden hour) and its
 *               countdown; Review opens the unit's home on this route
 *   interrupts  while a movement is live: the band at RED or BLACK, and a
 *               feed that stopped answering (§7.3)
 *
 * The strip appears ONLY while a movement or a pursuit is live (null
 * otherwise). Watches add inbox rows but never mute an interrupt: nothing
 * here reads the watches. Interrupts never open a modal and make no sound.
 */
import type { LiveInterrupt, LiveMovement, LivePursuit, LiveSoonest, LiveStripFeed } from '$lib/shell/command-bar.svelte';
import { ops, isLivePursuit } from '$lib/ops/store.svelte';
import { maskPlate } from '$lib/ops/format';
import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
import { selection } from '$lib/gods-eye/entities/selection.svelte';
import { workspace } from '$lib/workspace/workspace.svelte';
import { compass } from '$lib/workspace/kinds/common';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.decisions';
import { decisionUnits, type DecisionState } from './units';
import { homeOf, unitKey, type HomeRoute } from './homes';
import { WORKSPACE_URL } from '$lib/shell/root-flip';
import type { CorridorEvent } from '$lib/ops/types';

export interface LiveFeedOptions {
	/** The route the strip is on (the Review target); defaults to the page's path. */
	route?: string;
	/** The clock (tests). */
	now?: number;
	/** The state (tests): the ops store by default. */
	state?: DecisionState;
	/**
	 * Client-side navigation (the page's goto). A canvas-less page (/chat,
	 * /comms) has no map to select on: the pursuit segment opens the vehicle
	 * on the workspace (`/analyst#sel=vehicle:<id>`) through it (F-06).
	 */
	navigate?: (url: string) => void;
}

/** The pages with no map of their own: a selection there means nothing (F-06). */
const CANVASLESS: ReadonlySet<string> = new Set(['/chat', '/comms']);

/** The workspace link that selects (and flies to) `urn` on `/analyst`. */
export function workspaceSelectLink(urn: string): string {
	return `${WORKSPACE_URL}#${new URLSearchParams({ sel: urn }).toString()}`;
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

function currentRoute(): HomeRoute {
	const p = typeof location !== 'undefined' ? location.pathname : '/';
	return p.startsWith('/ops') ? '/ops' : p.startsWith('/gods-eye') ? '/gods-eye' : '/';
}

/** The live protected movement: an active protected_movement on the board. */
export function liveMovementEvent(state: DecisionState = ops): CorridorEvent | null {
	return state.events.find((e) => e.source !== 'offline-fixture' && e.eventKind === 'protected_movement' && e.state === 'active') ?? null;
}

/**
 * Every pursuit under way on the board (F-05): ACTIVE only. A planned
 * (planning / approved) pursuit is not running — nobody authorised it to
 * start — so it never reads as live in the strip or the map's mode; a
 * closed one never does either.
 */
export function openPursuits(state: DecisionState = ops): CorridorEvent[] {
	return state.events.filter((e) => isLivePursuit(e) && e.state === 'active');
}

function movementSegment(ev: CorridorEvent, lang: string): LiveMovement {
	const convoy = cityRegistry.byKind('convoy').find((c) => !ev.movementId || c.props.movement_id === ev.movementId || c.id === ev.movementId) ?? null;
	const props = (convoy?.props ?? {}) as Record<string, unknown>;
	const etaSec = num(props.eta_sec);
	const nextName = typeof props.next_junction_name === 'string' ? props.next_junction_name : null;
	return {
		label: t(lang, 'dec_live_movement', ev.protectionClass && ev.protectionClass !== 'none' ? ev.protectionClass : '—'),
		speedKmh: num(props.speed_kmh),
		nextJunction: nextName,
		nextInSec: nextName ? num(props.next_junction_in_sec) : null,
		etaMs: etaSec != null ? Date.now() + etaSec * 1000 : null,
		onOpen() {
			workspace.rightTab = 'movement';
			workspace.setDock('right', true);
		},
	};
}

function pursuitSegment(state: DecisionState, ev: CorridorEvent, now: number, lang: string, navigate: ((url: string) => void) | null): LivePursuit {
	const vehicleId = ev.metadata?.vehicleId ?? null;
	const watch = vehicleId ? state.watchlist.find((w) => w.vehicleId === vehicleId) ?? null : null;
	const plan = state.interception && state.interception.eventId === ev.eventId ? state.interception : null;
	const readT = plan?.latestSighting?.t ?? watch?.lastSighting?.t ?? null;
	const readMs = readT ? Date.parse(readT) : NaN;
	const heading = plan?.latestSighting?.heading ?? watch?.lastSighting?.heading ?? null;
	return {
		// ALREADY masked (the strip never unmasks, whatever the officer state)
		plateMasked: maskPlate(watch?.plate ?? plan?.latestSighting?.plate ?? null) ?? t(lang, 'dec_live_vehicle'),
		lastReadAgoSec: Number.isFinite(readMs) ? Math.max(0, Math.round((now - readMs) / 1000)) : null,
		heading: heading != null ? compass(heading, lang) : null,
		onSelect() {
			const urn = vehicleId ? `vehicle:${vehicleId}` : `event:${ev.eventId}`;
			// a canvas-less page opens the workspace on the vehicle (F-06: a bare selection there did nothing)
			if (navigate) navigate(workspaceSelectLink(urn));
			else selection.select(urn, { fly: true, source: 'rail' });
		},
	};
}

/** Open a unit's home on `route` (the Review button). */
export function openHome(kind: string, id: string, subjectUrn: string, title: string, deadline: number | null, route: HomeRoute): void {
	const home = homeOf(kind, route);
	if (home === 'decisions') {
		const key = unitKey(kind, id);
		if (key && typeof location !== 'undefined') location.hash = `unit=${encodeURIComponent(key)}`;
		return;
	}
	workspace.openDecisionHome(
		{
			kind,
			id,
			subjectUrn,
			title,
			deadline,
			severity: 3,
			homes: { '/': homeOf(kind, '/'), '/gods-eye': homeOf(kind, '/gods-eye'), '/ops': homeOf(kind, '/ops') },
		},
		route,
	);
}

/** The soonest-deadline decision (null when no unit carries a deadline). */
function soonestSegment(state: DecisionState, route: HomeRoute, now: number): LiveSoonest | null {
	const next = decisionUnits(state).find((u) => u.deadline != null && u.deadline > now - 1000);
	if (!next || next.deadline == null) return null;
	return {
		title: next.title,
		deadlineMs: next.deadline,
		onReview: () => openHome(next.kind, next.id, next.subjectUrn, next.title, next.deadline, route),
	};
}

/** §7.3 interrupts while a movement is live: band RED/BLACK, a feed that stopped answering. */
export function interruptsOf(state: DecisionState, movementLive: boolean, lang: string): LiveInterrupt[] {
	if (!movementLive) return [];
	const out: LiveInterrupt[] = [];
	const band = state.cityBand?.band ?? state.band;
	if (band === 'RED' || band === 'BLACK') out.push({ kind: 'band', band, text: t(lang, 'dec_live_band', t(lang, `dec_band_${band.toLowerCase()}`)) });
	const lost: string[] = [];
	if (state.boardStatus === 'offline' && state.boardUpdated > 0) lost.push(t(lang, 'dec_feed_events'));
	if (state.cityBand?.stale) lost.push(t(lang, 'dec_feed_band'));
	if (state.escortsNote && state.escortsDeployed !== false) lost.push(t(lang, 'dec_feed_escorts'));
	if (state.trafficFeedNote) lost.push(t(lang, 'dec_feed_traffic'));
	for (const name of lost) out.push({ kind: 'feed-loss', text: t(lang, 'dec_live_feed_lost', name) });
	return out;
}

/** The LiveStrip feed (plan X21), or null when no movement and no pursuit is live. */
export function liveStripFeed(opts: LiveFeedOptions = {}): LiveStripFeed | null {
	const state = opts.state ?? ops;
	const now = opts.now ?? Date.now();
	const route: HomeRoute = opts.route === '/ops' || opts.route === '/gods-eye' || opts.route === '/' ? opts.route : currentRoute();
	const lang = state.lang;
	const mv = liveMovementEvent(state);
	const pursuits = openPursuits(state);
	if (!mv && !pursuits.length) return null;
	const canvasless = opts.route != null && CANVASLESS.has(opts.route);
	const navigate = canvasless ? (opts.navigate ?? ((url: string) => (typeof location !== 'undefined' ? location.assign(url) : undefined))) : null;
	return {
		movement: mv ? movementSegment(mv, lang) : null,
		pursuits: pursuits.map((p) => pursuitSegment(state, p, now, lang, navigate)),
		soonest: soonestSegment(state, route, now),
		interrupts: interruptsOf(state, !!mv, lang),
	};
}
