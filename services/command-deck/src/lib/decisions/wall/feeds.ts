/**
 * Feeds and services (SPEC §6.3 col 3, §8.10): every feed and service behind
 * the situation wall, with one honest status each. The same rows fill the
 * navbar's Data popover (commandBar.dataStatus.feeds), so the two never
 * disagree.
 *
 * Status mapping (tests/wall.unit.mjs pins it):
 *   waiting    the source has not answered yet (never "down" before a first try)
 *   ok         answering, real data
 *   simulated  answering, the readings are synthetic (the traffic generator)
 *   emulated   answering, the rows come from the scenario emulator
 *   degraded   answering in part (a blip held on last-good, a kind not served,
 *              the decision model loading, a tactical fallback tier)
 *   down       not answering (or not deployed)
 *   not_read   this page does not read the source at all (F-04: /chat and
 *              /comms read no registry, city feed or cameras — said so,
 *              never a made-up "waiting")
 * In the Data popover's three-step scale, ok / simulated / emulated are
 * 'ok' (provenance is a fact, not a fault), waiting and degraded are
 * 'degraded', down is 'down'.
 */
import type { DataFeed, FeedStatus } from '$lib/shell/command-bar.svelte';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.wall';

export type WallFeedStatus = 'waiting' | 'ok' | 'simulated' | 'emulated' | 'degraded' | 'down' | 'not_read';

export interface WallFeedRow {
	id: string;
	name: string;
	/** Volume in words ("312 objects"), or null. */
	volume: string | null;
	status: WallFeedStatus;
	/** Seconds since the newest answer (or reading), or null. */
	ageSec: number | null;
	/** The note behind a degraded or down state, verbatim from the store. */
	note: string | null;
}

/** The city registry's status (idle | ok | not-deployed | down) and its blip note. */
export function registryStatus(status: string, note: string | null, emulatedShare = 0): WallFeedStatus {
	if (status === 'idle') return 'waiting';
	if (status === 'down' || status === 'not-deployed') return 'down';
	if (status === 'ok' && note) return 'degraded';
	if (status === 'ok') return emulatedShare >= 0.5 ? 'emulated' : 'ok';
	return 'degraded';
}

/** The city feed's status (idle | ok | not-deployed | down). */
export function cityFeedStatus(status: string, note: string | null): WallFeedStatus {
	if (status === 'idle') return 'waiting';
	if (status === 'ok') return note ? 'degraded' : 'ok';
	return 'down';
}

/** The traffic feed's provenance label (corridor summary quality mix). */
export function trafficStatus(label: string | null | undefined, note: string | null): WallFeedStatus {
	if (label == null) return note ? 'down' : 'waiting';
	if (label === 'simulated') return 'simulated';
	if (label === 'mixed') return 'degraded';
	if (label === 'live') return 'ok';
	return 'down'; // 'none': nothing fresh
}

/** A per-kind feed of the city snapshot (status ok | unavailable | error). */
export function kindFeedStatus(feed: { status: string; count: number } | null, source: string | null): WallFeedStatus {
	if (!feed) return 'waiting';
	if (feed.status !== 'ok') return 'down';
	return source === 'emulated' ? 'emulated' : 'ok';
}

/** The decision model: reachable, loaded, loading; the degradation tier. */
export function modelStatus(brain: { reachable: boolean; decider: { state: string } } | null, tier: string | null): WallFeedStatus {
	if (!brain) return 'waiting';
	if (!brain.reachable || brain.decider.state === 'unreachable') return 'down';
	if (brain.decider.state === 'loading') return 'degraded';
	if (tier && tier.toUpperCase() !== 'FULL') return 'degraded';
	return 'ok';
}

/** The scenario emulator: online after a probe; nothing before the first probe. */
export function emulatorStatus(online: boolean, lastChecked: number): WallFeedStatus {
	if (!lastChecked) return 'waiting';
	return online ? 'emulated' : 'down';
}

/** The corridor-event board: live | mixed (fixtures beside it) | offline. */
export function boardStatus(status: string, updated: number): WallFeedStatus {
	if (!updated) return 'waiting';
	if (status === 'live') return 'ok';
	if (status === 'mixed') return 'degraded';
	return 'down';
}

/** A wall status on the Data popover's three-step scale. */
export function toFeedStatus(s: WallFeedStatus): FeedStatus {
	if (s === 'not_read') return 'none';
	if (s === 'down') return 'down';
	if (s === 'waiting' || s === 'degraded') return 'degraded';
	return 'ok';
}

const RANK: Record<FeedStatus, number> = { none: -1, ok: 0, degraded: 1, down: 2 };

/** The worst status of a set of rows (the Data button's dot). */
export function worstStatus(rows: readonly WallFeedRow[]): FeedStatus {
	let worst: FeedStatus = 'ok';
	for (const r of rows) {
		const s = toFeedStatus(r.status);
		if (RANK[s] > RANK[worst]) worst = s;
	}
	return worst;
}

/** The word a status reads as (the Feeds section's tag and the Data popover's label). */
export function statusWord(lang: string, s: WallFeedStatus): string {
	return t(lang, `wall_feed_status_${s}`);
}

/**
 * The rows for the navbar's Data popover. The decision model is NOT one of
 * them (F-21): the popover's own model block states it (decider, p95, tier),
 * and a second "Decision model" row graded on the tier read "Degraded" beside
 * "Loaded". The model still counts towards the Data button's dot (worstStatus
 * reads every row).
 */
export function dataFeeds(rows: readonly WallFeedRow[], lang: string): DataFeed[] {
	return rows.filter((r) => r.id !== 'model').map((r) => ({
		name: r.name,
		status: toFeedStatus(r.status),
		// a feed the page does not read has nothing to add beside its state ("Not read here")
		label: r.status === 'not_read' ? '' : r.volume ? `${r.volume}, ${statusWord(lang, r.status).toLowerCase()}` : statusWord(lang, r.status).toLowerCase(),
	}));
}

/** What the wall knows about each source (the page reads the stores into this). */
export interface FeedInputs {
	now: number;
	/** null: this page does not read the registry (F-04). */
	registry: { status: string; note: string | null; size: number; updatedAt: number; emulatedShare: number } | null;
	/** null: this page does not read the city feed. */
	cityFeed: { status: string; note: string | null; rows: number; updatedAt: number } | null;
	traffic: { label: string | null; note: string | null; segments: number | null; dataAgeSec: number | null };
	/** null: this page does not read the camera feed. */
	cameras: { feed: { status: string; count: number; ageSec: number | null } | null; source: string | null } | null;
	board: { status: string; updated: number; open: number };
	model: { brain: { reachable: boolean; decider: { state: string; p95Ms: number | null }; checkedAt: number } | null; tier: string | null };
	emulator: { online: boolean; lastChecked: number; tapes: number };
}

const ageOf = (now: number, at: number | null | undefined) => (at ? Math.max(0, Math.round((now - at) / 1000)) : null);

/** The rows of the Feeds section (and of the navbar's Data popover), in a fixed order. */
export function feedRows(i: FeedInputs, lang: string): WallFeedRow[] {
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const notRead = (id: string, name: string): WallFeedRow => ({ id, name, volume: null, status: 'not_read', ageSec: null, note: null });
	return [
		i.registry
			? {
					id: 'registry',
					name: L('wall_feed_registry'),
					volume: i.registry.updatedAt ? L('wall_feed_objects', i.registry.size) : null,
					status: registryStatus(i.registry.status, i.registry.note, i.registry.emulatedShare),
					ageSec: ageOf(i.now, i.registry.updatedAt),
					note: i.registry.note,
				}
			: notRead('registry', L('wall_feed_registry')),
		i.cityFeed
			? {
					id: 'city-feed',
					name: L('wall_feed_city_feed'),
					volume: i.cityFeed.updatedAt ? L('wall_feed_rows', i.cityFeed.rows) : null,
					status: cityFeedStatus(i.cityFeed.status, i.cityFeed.note),
					ageSec: ageOf(i.now, i.cityFeed.updatedAt),
					note: i.cityFeed.note,
				}
			: notRead('city-feed', L('wall_feed_city_feed')),
		{
			id: 'traffic',
			name: L('wall_feed_traffic'),
			volume: i.traffic.segments != null ? L('wall_feed_roads', i.traffic.segments) : null,
			status: trafficStatus(i.traffic.label, i.traffic.note),
			ageSec: i.traffic.dataAgeSec != null ? Math.round(i.traffic.dataAgeSec) : null,
			note: i.traffic.note,
		},
		i.cameras
			? {
					id: 'cameras',
					name: L('wall_feed_cameras'),
					volume: i.cameras.feed ? L('wall_feed_cameras_n', i.cameras.feed.count) : null,
					status: kindFeedStatus(i.cameras.feed, i.cameras.source),
					ageSec: i.cameras.feed?.ageSec != null ? Math.round(i.cameras.feed.ageSec) : null,
					note: null,
				}
			: notRead('cameras', L('wall_feed_cameras')),
		{
			id: 'events',
			name: L('wall_feed_events'),
			volume: i.board.updated ? L('wall_feed_open', i.board.open) : null,
			status: boardStatus(i.board.status, i.board.updated),
			ageSec: ageOf(i.now, i.board.updated),
			note: null,
		},
		{
			id: 'model',
			name: L('wall_feed_model'),
			volume: i.model.brain?.decider.p95Ms != null ? L('wall_feed_p95', (i.model.brain.decider.p95Ms / 1000).toFixed(1)) : null,
			status: modelStatus(i.model.brain, i.model.tier),
			ageSec: ageOf(i.now, i.model.brain?.checkedAt),
			note: null,
		},
		{
			id: 'emulator',
			name: L('wall_feed_emulator'),
			volume: i.emulator.lastChecked ? L('wall_feed_tapes', i.emulator.tapes) : null,
			status: emulatorStatus(i.emulator.online, i.emulator.lastChecked),
			ageSec: ageOf(i.now, i.emulator.lastChecked),
			note: null,
		},
	];
}
