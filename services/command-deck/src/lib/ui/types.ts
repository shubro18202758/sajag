/**
 * Shared types of the src/lib/ui primitives (SPEC §5.1).
 *
 * Intent names follow Blueprint; what each hue may mean is SPEC §2.4's
 * frozen colour roles, and nothing else:
 *   none     neutral: everything that is not one of the roles below,
 *            including Reject, Dismiss and Cancel buttons and data states
 *   primary  blue: selection, focus, the one primary action of a surface,
 *            links. Never a data category.
 *   warning  orange: a decision waits ("Needs decision", the inbox count,
 *            the expiry bar)
 *   danger   red: the alert role, a watchlisted or stolen vehicle
 *            ("Watchlist", "Reported stolen", an unread watchlist read).
 *            Never "destructive": a decision verb is never red.
 *   success  green: approved, healthy ("Approved", "Answering")
 */
import type { IconName } from '$lib/design/icons';
import type { Moment } from './format/format';

export type Intent = 'none' | 'primary' | 'success' | 'warning' | 'danger';

/** Tag intents add `ai` (indigo): AI attribution only, nothing else. */
export type TagIntent = Intent | 'ai';

/**
 * Floating placement relative to the target (Popover, Tooltip): a side,
 * then how the box aligns along it. `right-start` is a submenu: its top on
 * the target's top.
 */
export type Placement =
	| 'top'
	| 'top-start'
	| 'top-end'
	| 'bottom'
	| 'bottom-start'
	| 'bottom-end'
	| 'left'
	| 'left-start'
	| 'left-end'
	| 'right'
	| 'right-start'
	| 'right-end';

/** Provenance sources and OSINT verification states (plan contract X2). */
export type ProvenanceSource = 'emulated' | 'simulated' | 'test' | 'osint';
export type VerificationState =
	| 'UNVERIFIED-OSINT'
	| 'NEWS-REPORTED'
	| 'OFFICIAL-VERIFIED'
	| 'CONFIRMED';

/** A Tree row (and its children). */
export interface TreeNode {
	id: string;
	label: string;
	icon?: IconName;
	secondaryLabel?: string | null;
	childNodes?: readonly TreeNode[];
	expanded?: boolean;
	selected?: boolean;
	disabled?: boolean;
	dim?: boolean;
	/** Extra attributes for the row (data-* hooks). */
	attrs?: Record<string, string>;
}

/** A Menu entry: an item, a divider or a header. */
export interface MenuItemSpec {
	id: string;
	kind?: 'item' | 'divider' | 'header';
	label?: string;
	icon?: IconName;
	/** Right-aligned hint: a shortcut, a count, a state. */
	rightLabel?: string | null;
	intent?: 'none' | 'primary' | 'danger';
	disabled?: boolean;
	disabledReason?: string | null;
	/** A choice: true renders the current one with .is-selected and aria-checked. */
	selected?: boolean;
	href?: string;
	onclick?: (e: MouseEvent) => void;
	attrs?: Record<string, string>;
}

/** A Breadcrumbs entry. */
export interface Crumb {
	label: string;
	href?: string;
	onclick?: () => void;
	icon?: IconName;
	current?: boolean;
}

/** A PropertyTable group of key/value rows. */
export interface PropertyGroup {
	title?: string | null;
	rows: readonly PropertyRow[];
}

export interface PropertyRow {
	key: string;
	value?: string | number | null;
	/** Muted text after the value ("30 days left"). */
	hint?: string | null;
	/** Custom value content (a Plate, an ObjectTag, tags) — wins over `value`. */
	render?: import('svelte').Snippet;
	attrs?: Record<string, string>;
}

/** A toast handed to the Toaster primitive (it owns no store). */
export interface ToastSpec {
	id: string | number;
	message: string;
	intent?: Intent;
	icon?: IconName;
	/** Auto-dismiss after ms (0 = until dismissed); paused while hovered. */
	timeout?: number;
	action?: { label: string; onclick: () => void } | null;
}

/** A group of shortcuts for HotkeysDialog. */
export interface HotkeyGroup {
	title: string;
	keys: readonly { combo: readonly string[]; label: string }[];
	/** An optional rule line under the group. */
	note?: string;
}

/** A DataTable column. */
export interface DataColumn<R> {
	key: string;
	/** Header text ('' for the icon column). */
	title?: string;
	/**
	 * px number or a CSS width; the icon column is always 32 px. A px width
	 * is fixed; a column without one shares the room that is left.
	 */
	width?: number | string;
	/**
	 * The narrowest a column without a px width may get, in px (default 64).
	 * The table never crushes a column below it: past the sum of the fixed
	 * widths and these minimums the table scrolls sideways instead (a 344 px
	 * dock, a 1366 px screen). The header cell carries it as data-min-width.
	 */
	minWidth?: number;
	align?: 'left' | 'right' | 'center';
	/** Figures: tabular, right-aligned. */
	num?: boolean;
	/** The fixed 32 px glyph column (overflow visible, never ellipsised). */
	icon?: boolean;
	sortable?: boolean;
	/** Cell value and sort key (default: row[key]). */
	value?: (row: R) => unknown;
	/**
	 * A time column: the values are moments (epoch ms, ISO 8601, Date). Cells
	 * render through colStamp — IST, ONE format for the whole column (hh:mm,
	 * or "23 Oct 23:52" on every row once the days differ) — and sort by the
	 * instant. `anchor` is the day that reads as today (default now).
	 */
	time?: boolean | { anchor?: Moment; seconds?: boolean };
	/** Text of a default cell (no `render`): the caller's formatter for the value. */
	format?: (value: unknown, row: R) => string;
	/** Custom cell content (inside the .c flex row). */
	render?: import('svelte').Snippet<[R]>;
	/** Two-line rows: the second line's text, or a snippet. */
	line2?: (row: R) => string | null | undefined;
	render2?: import('svelte').Snippet<[R]>;
	/** Header tooltip. */
	hint?: string;
}

export interface SortState {
	key: string;
	dir: 'asc' | 'desc';
}
