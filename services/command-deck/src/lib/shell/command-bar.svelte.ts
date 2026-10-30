/**
 * CommandBar state — the R3 shell↔page contract (SPEC §5.3, §14.2; plan X12).
 *
 * The shell OWNS this module; every (deck)/(public) page assigns the fields it
 * owns inside an $effect. Import direction is one-way: pages → $lib/shell/**.
 * The shell never imports $lib/ops/** or $lib/gods-eye/** (R4, linted): what
 * a page knows (the band, the officer, the brain's posture, the live
 * operations) reaches the navbar and the LiveStrip only through these fields.
 *
 * The rule (plan R10/X12): a navbar control and its test id render ONLY when
 * the page supplied its field. `officer` → the duty-officer input
 * (`duty-officer`), `dataStatus` → the Data button (`brain-posture`),
 * `exercise` → the Exercise-data tag (`feed-provenance`), `live` with content
 * → the LiveStrip (`live-strip`). A page that assigns nothing renders calm
 * chrome: band:null shows the hollow "Band —" tag (data-band="pending"), so a
 * hollow state cannot hide.
 *
 * The shells call resetCommandBar() whenever the ROUTE changes (before the
 * incoming page mounts), so one page's band, officer, live feed or Share
 * handler never leaks onto the next.
 */
import type { Band } from '$lib/design/tokens';

/** Citizen-facing posture (the public bar never shows a band code). */
export type PublicTier = 'calm' | 'watch' | 'hold' | 'severe';

/** The health of one data feed or service in the Data popover. */
/** 'none': the page does not read this feed (F-04: said, never a guessed "waiting · degraded"). */
export type FeedStatus = 'ok' | 'degraded' | 'down' | 'none';

/** One row of the Data popover: a feed or service, its status and a short state word. */
export interface DataFeed {
	name: string;
	status: FeedStatus;
	/** Short state word shown beside the status ("38 of 49 roads", "by policy"). */
	label: string;
}

/**
 * The Data button (`brain-posture`): the decision model's posture and the
 * feeds behind the console. Its visually hidden summary (also its tooltip)
 * reads e.g. "Decision model loaded, p95 2.3 s, novelty check on; all feeds
 * answering" (ops-wall-smoke reads "p95 <n> s" and "novelty check on|off").
 */
export interface DataStatus {
	/** The decider's state, e.g. 'loaded' | 'loading' | 'unreachable' (data-decider). */
	decider: string;
	/** The brain's degradation tier, e.g. 'FULL' (data-tier). */
	tier: string;
	/** The decider's p95 decide latency in SECONDS (2.3), or null when unknown. */
	p95: number | null;
	/** Whether the novelty check is on. */
	novelty: boolean;
	feeds: DataFeed[];
	/** The worst feed status (the button's dot). */
	worst: FeedStatus;
}

/** The console-wide exercise-data statement (`feed-provenance`, data-label = label). */
export interface ExerciseInfo {
	/** The feed's provenance word, e.g. 'simulated' (data-label). */
	label: string;
	/** One line for the tag's tooltip and the popover's lead. */
	text: string;
}

/**
 * The duty-officer control (plan R10). `value` is the name on console;
 * `fromSession` is true when the operator gate signed the officer in (the
 * navbar then shows the name locked); `set(v)` names (or clears) the officer.
 */
export interface OfficerControl {
	value: string;
	fromSession: boolean;
	set(v: string): void;
}

/** The live movement segment of the LiveStrip. */
export interface LiveMovement {
	/** e.g. "Protected movement · Z". */
	label: string;
	speedKmh: number | null;
	nextJunction: string | null;
	nextInSec: number | null;
	/** Epoch ms of the arrival estimate. */
	etaMs: number | null;
	/** Opens the Movement tab. */
	onOpen(): void;
}

/** One open pursuit segment of the LiveStrip. */
export interface LivePursuit {
	/** The registration mark, ALREADY masked by the page (MH47EM•••1). */
	plateMasked: string;
	lastReadAgoSec: number | null;
	heading: string | null;
	/** Selects the pursued vehicle. */
	onSelect(): void;
}

/** The soonest-expiring decision: countdown on an orange veil, and Review. */
export interface LiveSoonest {
	title: string;
	/** Epoch ms when the decision expires. */
	deadlineMs: number;
	/** Opens the decision's home. */
	onReview(): void;
}

/** An interrupt (SPEC §7.3): band RED/BLACK during a movement, or feed loss. */
export interface LiveInterrupt {
	kind: 'band' | 'feed-loss';
	text: string;
	band?: 'RED' | 'BLACK';
	onOpen?(): void;
}

/** What pages put in commandBar.live (UI-S5A's liveStripFeed(), plan X21). */
export interface LiveStripFeed {
	movement: LiveMovement | null;
	pursuits: LivePursuit[];
	soonest: LiveSoonest | null;
	interrupts: LiveInterrupt[];
}

export interface CommandBarState {
	/** City situation band, or null when not yet known (the hollow "Band —" tag). */
	band: Band | null;
	/** Where the band came from, e.g. 'situation_log' (tooltip only). */
	bandSource: string | null;
	/** Seconds since the band's newest reading; the tag ticks from it (data-age-sec). */
	bandAgeSec: number | null;
	/** UI language ('en' | 'hi' | 'mr'); drives the shell's language switch. */
	lang: string;
	/** Called when the operator flips the language switch (or null). */
	onLangChange: ((lang: string) => void) | null;
	/**
	 * Legacy: a page that still supplies a Share handler gets a Share control in
	 * the navbar's right group (`.share`, `data-share`) until its owner moves
	 * Share into the view header (SPEC §5.3: no Share in the navbar).
	 */
	onShare: (() => void) | null;
	/** Public pages only: plain-language posture for the citizen bar. */
	tier: PublicTier | null;
	/** Opens the page's omnibar (the page mounts it). Null: the navbar's own nav search. */
	onSearch: ((q?: string) => void) | null;
	/** Opens the page's Inbox. */
	onInbox: (() => void) | null;
	/** Decision units waiting (the Inbox count). */
	inboxCount: number;
	/** warning: a decision waits; danger: an unread watchlist read. */
	inboxIntent: 'none' | 'warning' | 'danger';
	/** The Data button's posture (null: no Data button). */
	dataStatus: DataStatus | null;
	/** The console-wide exercise-data statement (null: no Exercise-data tag). */
	exercise: ExerciseInfo | null;
	/** The duty-officer control (null: no navbar officer input). */
	officer: OfficerControl | null;
	/** The LiveStrip feed (null or empty: no strip). */
	live: LiveStripFeed | null;
}

export const commandBar = $state<CommandBarState>({
	band: null,
	bandSource: null,
	bandAgeSec: null,
	lang: 'en',
	onLangChange: null,
	onShare: null,
	tier: null,
	onSearch: null,
	onInbox: null,
	inboxCount: 0,
	inboxIntent: 'none',
	dataStatus: null,
	exercise: null,
	officer: null,
	live: null
});

/** True when a LiveStrip feed has anything to show. */
export function liveHasContent(live: LiveStripFeed | null | undefined): boolean {
	if (!live) return false;
	return !!live.movement || (live.pursuits?.length ?? 0) > 0 || !!live.soonest || (live.interrupts?.length ?? 0) > 0;
}

/**
 * Clear every page-owned field (language stays: it is the user's choice, not
 * page state). Called by the shells on route change.
 */
export function resetCommandBar(): void {
	commandBar.band = null;
	commandBar.bandSource = null;
	commandBar.bandAgeSec = null;
	commandBar.onLangChange = null;
	commandBar.onShare = null;
	commandBar.tier = null;
	commandBar.onSearch = null;
	commandBar.onInbox = null;
	commandBar.inboxCount = 0;
	commandBar.inboxIntent = 'none';
	commandBar.dataStatus = null;
	commandBar.exercise = null;
	commandBar.officer = null;
	commandBar.live = null;
}
