/**
 * The Histogram's model (SPEC §5.3, §8.9): the rows in the table, counted
 * by value in six groups — Kind, State, Source, Hour (IST), Road, Camera —
 * and turned into workspace filters.
 *
 * Every value is read EXACTLY as the store's filter reads it
 * (watches.ts passesFilter), so "Filter to" a value keeps exactly the rows
 * its bar counted:
 *
 *   kind     row.kind
 *   state    row.state (rows without one are counted apart, never filtered)
 *   source   row.source — ONE bar per source; the open-source bar
 *            ("Open-source", the source glyph) carries a breakdown of its
 *            rows by verification state (News-reported 1 · Unverified
 *            OSINT 1 · No verification state 1) that is read, never picked:
 *            the store has no verification field, so the source filter
 *            keeps every open-source row, whatever its state
 *   hour     hourOf(row.t) in IST — an hour of the day, as the store's
 *            hour filter reads it; the bars are sorted BY TIME on the
 *            24-hour cycle that ends at the newest row's hour, so they read
 *            22:00, 23:00, 00:00, 01:00 across midnight (an hour seen on an
 *            older day too keeps its place in the cycle)
 *   road     the road a row names (props.road_name, evidence.road_name, a
 *            road's own label)
 *   camera   the camera a row names (a camera's id, props.camera_id,
 *            evidence.camera_id, a vehicle's last camera)
 *
 * Pure: no store is read here (the unit test runs it on fixtures).
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.views';
import { kindOne, shortStateWord, verificationWord } from '../../kinds/generic';
import { hourOf } from '../../workspace.svelte';
import type { Filter, FilterField, ObjectRow } from '../../types';

/** The Histogram's groups, in display order. */
export const HIST_FIELDS = ['kind', 'state', 'source', 'hour', 'road', 'camera'] as const;
export type HistField = (typeof HIST_FIELDS)[number];

/** How many values a group shows before "Show n more" (Hour shows every hour). */
export const TOP_VALUES = 8;

export interface HistBin {
	/** Unique within the group: the bar's filter value (one bar per value). */
	key: string;
	/** The filter value this bar selects; a filter on it keeps exactly the bar's `n` rows. */
	value: string;
	label: string;
	n: number;
	/**
	 * The open-source bar only: its rows by verification state, strongest
	 * first (a breakdown to read, never a value to pick); null on every
	 * other bar.
	 */
	parts: HistPart[] | null;
	/** Hour bins: the newest moment counted. */
	t: number | null;
	/** Hour bins: the place in the 24-hour cycle ending at the newest row (0 = oldest hour). */
	cycle: number | null;
}

/** One verification state's share of the open-source bar. */
export interface HistPart {
	/** The raw state (UNVERIFIED-OSINT, NEWS-REPORTED, …), or null for rows without one. */
	verification: string | null;
	label: string;
	n: number;
}

export interface HistGroup {
	field: HistField;
	title: string;
	bins: HistBin[];
	/** Rows in scope that carry no value for this field (counted apart, never filterable). */
	missing: number;
	/** The largest bin (bars scale to it). */
	max: number;
}

const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null);
const rec = (v: unknown): Record<string, unknown> => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {});

/** The road a row names — the same read as the store's road filter. */
export function roadOf(row: ObjectRow): string | null {
	const p = row.props;
	const ev = rec(p.evidence);
	const road = [p.road_name, ev.road_name, row.kind === 'segment' ? row.label : null].find((r) => typeof r === 'string');
	return typeof road === 'string' ? road : null;
}

/** The camera a row names — the same read as the store's camera filter. */
export function cameraOf(row: ObjectRow): string | null {
	const p = row.props;
	const ev = rec(p.evidence);
	const cam = row.kind === 'camera' ? row.id : [p.camera_id, ev.camera_id, p.last_camera_id].find((c) => typeof c === 'string');
	return typeof cam === 'string' ? cam : null;
}

/** A source in words ("Emulated", "Open-source"). */
export function sourceWord(source: string, lang: string): string {
	const key = `vw_src_${source}`;
	const v = t(lang, key);
	return v === key ? source : v;
}

/** The filter value of a row for a field, or null when the row has none. */
export function valueOf(row: ObjectRow, field: HistField): string | null {
	switch (field) {
		case 'kind':
			return row.kind;
		case 'state':
			return str(row.state);
		case 'source':
			return row.source;
		case 'hour':
			return row.t != null && Number.isFinite(row.t) ? hourOf(row.t) : null;
		case 'road':
			return roadOf(row);
		case 'camera':
			return cameraOf(row);
	}
}

/** A filter value in words, as a bar and a filter label show it. */
export function valueLabel(field: HistField, value: string, lang: string): string {
	switch (field) {
		case 'kind':
			return kindOne(value, lang);
		case 'state':
			return shortStateWord(value, lang) ?? value;
		case 'source':
			return sourceWord(value, lang);
		default:
			return value;
	}
}

const istHourNum = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', hourCycle: 'h23' });
/** The IST hour of a moment, 0–23. */
const hourNum = (t: number) => Number(istHourNum.format(t)) % 24;

const TITLE_KEY: Record<HistField, string> = {
	kind: 'vw_h_kind',
	state: 'vw_h_state',
	source: 'vw_h_source',
	hour: 'vw_h_hour',
	road: 'vw_h_road',
	camera: 'vw_h_camera',
};

/** Verification states, strongest first (the open-source breakdown's order; unknown states follow, then none). */
export const VERIFICATION_ORDER: readonly string[] = ['CONFIRMED', 'OFFICIAL-VERIFIED', 'NEWS-REPORTED', 'UNVERIFIED-OSINT'];

/** The open-source bar's rows by verification state, strongest first (rows without a state last). */
export function verificationParts(rows: readonly ObjectRow[], lang = 'en'): HistPart[] {
	const counts = new Map<string | null, number>();
	for (const r of rows) {
		const v = typeof r.verification === 'string' && r.verification.trim() ? r.verification : null;
		counts.set(v, (counts.get(v) ?? 0) + 1);
	}
	const rank = (v: string | null) => (v == null ? Infinity : VERIFICATION_ORDER.includes(v) ? VERIFICATION_ORDER.indexOf(v) : VERIFICATION_ORDER.length);
	return [...counts.entries()]
		.sort(([a], [b]) => rank(a) - rank(b) || String(a).localeCompare(String(b)))
		.map(([verification, n]) => ({
			verification,
			label: verification ? (verificationWord(verification, lang) ?? verification) : t(lang, 'vw_h_no_state'),
			n,
		}));
}

/** Count the rows in scope into the six groups (pure; ≤ 500 rows in well under a millisecond). */
export function histogram(rows: readonly ObjectRow[], lang = 'en'): HistGroup[] {
	return HIST_FIELDS.map((field) => {
		const bins = new Map<string, HistBin>();
		/** The open-source rows (the source group's breakdown). */
		const osint: ObjectRow[] = [];
		let missing = 0;
		for (const row of rows) {
			const value = valueOf(row, field);
			if (value == null) {
				missing++;
				continue;
			}
			let bin = bins.get(value);
			if (!bin) {
				bin = { key: value, value, label: valueLabel(field, value, lang), n: 0, parts: null, t: null, cycle: null };
				bins.set(value, bin);
			}
			bin.n++;
			if (field === 'hour' && row.t != null && (bin.t == null || row.t > bin.t)) bin.t = row.t;
			if (field === 'source' && value === 'osint') osint.push(row);
		}
		const open = bins.get('osint');
		if (field === 'source' && open) open.parts = verificationParts(osint, lang);
		const list = [...bins.values()];
		if (field === 'hour') {
			const newest = list.reduce((m, b) => Math.max(m, b.t ?? -Infinity), -Infinity);
			const last = Number.isFinite(newest) ? hourNum(newest) : 23;
			for (const b of list) b.cycle = (Number(b.value.slice(0, 2)) - last - 1 + 48) % 24;
			list.sort((a, b) => (a.cycle ?? 0) - (b.cycle ?? 0));
		} else list.sort((a, b) => b.n - a.n || a.label.localeCompare(b.label, undefined, { numeric: true }));
		return { field, title: t(lang, TITLE_KEY[field]), bins: list, missing, max: list.reduce((m, b) => Math.max(m, b.n), 0) };
	});
}

/** "1 value", "4 values" (never "1 values"): the filter values a group offers, one per bar. */
export function valuesLabel(n: number, lang = 'en'): string {
	return t(lang, 'vw_h_values', n);
}

/** The values selected per field (filter values, not bin keys). */
export type HistSelection = ReadonlyMap<HistField, ReadonlySet<string>>;

/** The filter values a group offers, in bar order (one bar per value). */
export function groupValues(g: HistGroup): string[] {
	return g.bins.map((b) => b.value);
}

/** The store keeps a filter label of at most 80 characters (a longer one falls back to the field name). */
const LABEL_ROOM = 64;

/** Words joined with ", " within the label's room, then "+n" for the rest ("Vehicle, Sighting +3"). */
export function joinWords(words: readonly string[], lang = 'en'): string {
	let out = '';
	for (let i = 0; i < words.length; i++) {
		const next = out ? `${out}, ${words[i]}` : words[i];
		if (next.length > LABEL_ROOM && out) return `${out} ${t(lang, 'vw_h_label_more', words.length - i)}`;
		out = next.length > LABEL_ROOM ? `${next.slice(0, LABEL_ROOM - 1)}…` : next;
	}
	return out;
}

/** A filter's label: the values in words ("Vehicle, Sighting"; "Not Camera"). */
function labelFor(field: HistField, values: readonly string[], lang: string, negate: readonly string[] | null): string {
	const words = joinWords(
		(negate ?? values).map((v) => valueLabel(field, v, lang)),
		lang,
	);
	return negate ? t(lang, 'vw_h_label_not', words) : words;
}

/**
 * The picks that still name a bar. When the table's rows change under a
 * pick (another view moves the scope, a filter is lifted), a value that is
 * no longer a bar drops out, so "Filter to" never stays primary over nothing.
 */
export function livePicks(groups: readonly HistGroup[], picked: Partial<Record<HistField, readonly string[]>>): Map<HistField, Set<string>> {
	const out = new Map<HistField, Set<string>>();
	for (const f of HIST_FIELDS) {
		const g = groups.find((x) => x.field === f);
		const values = new Set(g ? groupValues(g) : []);
		out.set(f, new Set((picked[f] ?? []).filter((v) => values.has(v))));
	}
	return out;
}

/** True when a live pick names at least one bar. */
export function hasPicks(sel: HistSelection): boolean {
	for (const v of sel.values()) if (v.size) return true;
	return false;
}

/**
 * "Filter to": one filter per group with a selected value (values OR-ed
 * within a group, groups AND-ed — the store's own rule).
 */
export function filtersTo(groups: readonly HistGroup[], sel: HistSelection, lang = 'en'): Omit<Filter, 'id'>[] {
	const out: Omit<Filter, 'id'>[] = [];
	for (const g of groups) {
		const chosen = sel.get(g.field);
		if (!chosen?.size) continue;
		const values = groupValues(g).filter((v) => chosen.has(v));
		if (!values.length) continue;
		out.push({ field: g.field as FilterField, values, label: labelFor(g.field, values, lang, null) });
	}
	return out;
}

/**
 * True when "Filter out" can be said exactly for this group: every row in
 * scope carries a value, and something is left once the selection is out.
 */
export function canFilterOut(g: HistGroup, chosen: ReadonlySet<string> | undefined): boolean {
	if (!chosen?.size || g.missing > 0) return false;
	return groupValues(g).some((v) => !chosen.has(v));
}

/**
 * "Filter out": the store keeps values (it has no exclusion), so filtering a
 * value out is filtering to the OTHER values the table holds now. Only for
 * groups where that is exact (canFilterOut); null when any selected group
 * cannot be said exactly.
 */
export function filtersOut(groups: readonly HistGroup[], sel: HistSelection, lang = 'en'): Omit<Filter, 'id'>[] | null {
	const out: Omit<Filter, 'id'>[] = [];
	for (const g of groups) {
		const chosen = sel.get(g.field);
		if (!chosen?.size) continue;
		if (!canFilterOut(g, chosen)) return null;
		const values = groupValues(g).filter((v) => !chosen.has(v));
		const dropped = groupValues(g).filter((v) => chosen.has(v));
		out.push({ field: g.field as FilterField, values, label: labelFor(g.field, values, lang, dropped) });
	}
	return out.length ? out : null;
}
