/**
 * The ObjectTable's model (SPEC §5.3, §7.3, §9.2): what each cell says, the
 * header's words, which rows fade and where the rows come from. Pure — the
 * component and the unit test read the same functions.
 *
 *   rows      (selection ∪ linked) ∩ filters — the store's objectSet — or an
 *             Explorer kind (kindRows), or the omnibar's results (a `urns`
 *             filter on the objectSet)
 *   columns   icon · Object · Type · State · Time (IST) · Place · Speed ·
 *             Links, and Source only when the rows are MIXED; a uniform
 *             list states its provenance once in the header (§9.2)
 *   fading    a row outside the time window fades — never a protected
 *             object (a live movement, an open pursuit, a waiting decision,
 *             a recent watchlist read), never infrastructure (selectors
 *             .inWindow, §7.3)
 *
 * Every text a cell shows comes from the row's MASKED label and props; no
 * cell renders a raw registration mark (SPEC §7.2, §9.3).
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.views';
import { maskMarks } from '../../mask';
import { passesFilters } from '../../watches';
import { hourOf } from '../../workspace.svelte';
import type { Run } from '../../kinds/common';
import type { Filter, FilterField, ObjectGraph, ObjectRow, ObjectSource } from '../../types';

const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null);
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const rec = (v: unknown): Record<string, unknown> => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {});

type Lookup = (urn: string) => ObjectRow | null;

/** Where an object is, in words (a road, a camera's place, a junction), masked; null when it has no place. */
export function placeOf(row: ObjectRow, get: Lookup = () => null): string | null {
	const p = row.props;
	const ev = rec(p.evidence);
	const camPlace = (id: unknown) => {
		const cam = str(id);
		if (!cam) return null;
		return get(`camera:${cam}`)?.sublabel ?? cam;
	};
	let place: string | null;
	switch (row.kind) {
		case 'camera':
			place = row.sublabel;
			break;
		case 'sighting':
			place = str(p.road_name) ?? camPlace(p.camera_id);
			break;
		case 'vehicle':
			place = camPlace(p.last_camera_id);
			break;
		case 'recommendation':
			place = str(ev.road_name) ?? row.sublabel;
			break;
		case 'segment':
		case 'junction':
			place = row.label;
			break;
		case 'anomaly':
			place = str(p.road_name);
			break;
		case 'dispatch': {
			const j = num(p.waypoint_junction);
			place = (j != null ? get(`junction:${j}`)?.label : null) ?? null;
			break;
		}
		case 'osint_event':
			place = str(p.toponym) ?? row.sublabel;
			break;
		case 'place':
			place = str(p.canonical_name) ?? row.label;
			break;
		default:
			place = str(p.road_name) ?? str(ev.road_name);
	}
	return place ? maskMarks(place) : null;
}

/** A speed the row records (km/h), or null. */
export function speedOf(row: ObjectRow): number | null {
	const p = row.props;
	return num(p.speed_kmh) ?? num(rec(p.evidence).speed_kmh) ?? num(p.last_speed_kmh);
}

/** A masked registration mark as the oracle writes it ("MH47EM•••1", "MH 01 AB •••7"). */
const MASKED_MARK = /[A-Z]{2}[\s.\-/_]{0,3}\d{1,2}[\s.\-/_]{0,3}(?:[A-Z]{1,3}[\s.\-/_]{0,3})?•••\d/g;
/** An identifier: upper-case parts joined by dashes, with a digit ("EM-CAM-03", "EM-J01B", "PCR-12"). */
const ID = /\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b/g;

/**
 * A label as formatter runs: masked marks as a Plate, identifiers in the
 * identifier face, the rest as text (SPEC §3.3: mono for identifiers only).
 */
export function labelRuns(label: string): Run[] {
	const text = maskMarks(label);
	const marks: { at: number; end: number; run: Run }[] = [];
	for (const m of text.matchAll(MASKED_MARK)) marks.push({ at: m.index ?? 0, end: (m.index ?? 0) + m[0].length, run: { plate: m[0], masked: true } });
	for (const m of text.matchAll(ID)) {
		const at = m.index ?? 0;
		const end = at + m[0].length;
		if (!/\d/.test(m[0]) || marks.some((x) => at < x.end && end > x.at)) continue;
		marks.push({ at, end, run: { id: m[0] } });
	}
	marks.sort((a, b) => a.at - b.at);
	const out: Run[] = [];
	let i = 0;
	for (const m of marks) {
		if (m.at > i) out.push({ text: text.slice(i, m.at) });
		out.push(m.run);
		i = m.end;
	}
	if (i < text.length) out.push({ text: text.slice(i) });
	return out.length ? out : [{ text }];
}

/** The one provenance every row shares, or null when they are mixed (or there are none). */
export function uniformSource(rows: readonly ObjectRow[]): ObjectSource | null {
	let s: ObjectSource | null = null;
	for (const r of rows) {
		if (s == null) s = r.source;
		else if (r.source !== s) return null;
	}
	return s;
}

/** True when the rows are of more than one provenance: the Source column is shown (§9.2). */
export function isMixed(rows: readonly ObjectRow[]): boolean {
	return rows.length > 0 && uniformSource(rows) == null;
}

/** The one kind every row shares, or null when they are of several kinds (or there are none). */
export function uniformKind(rows: readonly ObjectRow[]): string | null {
	let k: string | null = null;
	for (const r of rows) {
		if (k == null) k = r.kind;
		else if (r.kind !== k) return null;
	}
	return k;
}

/**
 * The header's title for the table's rows (the subject part is drawn by the
 * component: "<label> and its 51 linked objects").
 *
 *   subject   only when the rows ARE the selection's scope (the table's
 *             default rows, or the store's objectSet); rows the page passed
 *             otherwise never borrow the selection's name
 *   header    the page's own title, when it gave one
 *   results   the omnibar's results explored (a `urns` filter)
 *   kind      the kind explored (one kind filter with one value), or the
 *             one kind of every passed row
 *   objects   any other passed set; "Every object" for the default scope
 *             with no selection
 */
export type TitleKind = { kind: 'subject' } | { kind: 'header'; text: string } | { kind: 'results' } | { kind: 'kind'; of: string } | { kind: 'objects' } | { kind: 'every' };

export function tableTitle(input: {
	header: string | null | undefined;
	/** True when the rows are the selection's scope (default rows, or the store's objectSet). */
	selectionScope: boolean;
	/** The scope's primary object exists. */
	hasSubject: boolean;
	exploring: boolean;
	exploredKind: string | null;
	/** True when the page passed the rows. */
	passed: boolean;
	rows: readonly ObjectRow[];
}): TitleKind {
	if (input.header) return { kind: 'header', text: input.header };
	if (input.exploring) return { kind: 'results' };
	if (input.selectionScope && input.hasSubject) return { kind: 'subject' };
	const kind = input.exploredKind ?? (input.passed ? uniformKind(input.rows) : null);
	if (kind) return { kind: 'kind', of: kind };
	return input.passed ? { kind: 'objects' } : { kind: 'every' };
}

/** The open-source verification states the provenance tag names (plan X2). */
export type TagVerification = 'UNVERIFIED-OSINT' | 'NEWS-REPORTED' | 'OFFICIAL-VERIFIED' | 'CONFIRMED';
const TAG_VERIFICATIONS: ReadonlySet<string> = new Set(['UNVERIFIED-OSINT', 'NEWS-REPORTED', 'OFFICIAL-VERIFIED', 'CONFIRMED']);

/** An open-source row's verification as the provenance tag takes it (null for any other row or state). */
export function tagVerification(source: string, v: string | null | undefined): TagVerification | null {
	return source === 'osint' && typeof v === 'string' && TAG_VERIFICATIONS.has(v) ? (v as TagVerification) : null;
}

/** Columns the user (or a narrow pane) may set aside; the rest always show. */
export const OPTIONAL_COLUMNS = ['place', 'speed', 'links'] as const;
export type OptionalColumn = (typeof OPTIONAL_COLUMNS)[number];

/**
 * The table's columns, in order: glyph · Object · Type · State · Time ·
 * Place · Speed · Source · Links — Source ONLY when the rows are mixed (a
 * uniform list states its provenance once, in the header: SPEC §9.2).
 */
export function columnKeys(rows: readonly ObjectRow[], visible: (c: OptionalColumn) => boolean = () => true): string[] {
	const out = ['icon', 'label', 'kind', 'state', 't'];
	if (visible('place')) out.push('place');
	if (visible('speed')) out.push('speed');
	if (isMixed(rows)) out.push('source');
	if (visible('links')) out.push('links');
	return out;
}

/** The one verification state a uniform open-source list shares, or null. */
export function uniformVerification(rows: readonly ObjectRow[]): string | null {
	let v: string | null | undefined;
	for (const r of rows) {
		if (v === undefined) v = r.verification ?? null;
		else if ((r.verification ?? null) !== v) return null;
	}
	return v ?? null;
}

/**
 * The verification state a row must show itself (ethics rule 7, SPEC §9.2):
 * an open-source row's own state whenever the header does not state it once
 * for every row (`headerVerification` null: the states differ, or the rows
 * are of several sources and the Source glyph alone would hide it). Null for
 * any other row, a row without a known state, or a list whose header states
 * the one state they all share.
 */
export function rowVerification(row: ObjectRow, headerVerification: string | null): TagVerification | null {
	if (headerVerification) return null;
	return tagVerification(row.source, row.verification);
}

/** The words the header adds for each kind of filter in force ("kind filter"). */
export function filterWords(filters: readonly Filter[], lang = 'en'): string[] {
	const fields = new Set<FilterField>(filters.map((f) => f.field));
	const order: FilterField[] = ['urns', 'kind', 'state', 'source', 'hour', 'road', 'camera'];
	return order.filter((f) => fields.has(f)).map((f) => t(lang, `vw_t_filter_${f}`));
}

/** "50 rows", "1 row" */
export function rowsLabel(n: number, lang = 'en'): string {
	return t(lang, 'vw_t_rows', n);
}

/** The header's meta line after the title: "50 rows · kind filter" (one data separator between parts). */
export function headerMeta(n: number, filters: readonly Filter[], lang = 'en'): string[] {
	return [rowsLabel(n, lang), ...filterWords(filters, lang)];
}

/**
 * Every object of a kind (an Explorer kind), with the filters in force —
 * the table's rows when the Explorer's kind is explored rather than the
 * selection's links.
 */
export function kindRows(graph: ObjectGraph, kind: string, filters: readonly Filter[] = [], max = 500): ObjectRow[] {
	const out: ObjectRow[] = [];
	for (const r of graph.byKind(kind)) {
		if (!passesFilters(r, filters, hourOf)) continue;
		out.push(r);
		if (out.length >= max) break;
	}
	return out;
}

/**
 * (selection ∪ linked) ∩ filters — the store's objectSet rule (SPEC §7.4),
 * stated here for the table's own check: the selection first, then its
 * one-hop links, each once.
 */
export function selectionRows(
	graph: ObjectGraph,
	linked: (urn: string) => readonly ObjectRow[],
	primary: string,
	items: readonly string[],
	filters: readonly Filter[],
	max = 500,
): ObjectRow[] {
	const seen = new Set<string>();
	const base: ObjectRow[] = [];
	for (const u of [primary, ...items]) {
		const r = graph.get(u);
		if (r && !seen.has(r.urn)) {
			seen.add(r.urn);
			base.push(r);
		}
	}
	for (const r of linked(primary)) {
		if (seen.has(r.urn)) continue;
		seen.add(r.urn);
		base.push(r);
	}
	const out: ObjectRow[] = [];
	for (const r of base) {
		if (passesFilters(r, filters, hourOf)) out.push(r);
		if (out.length >= max) break;
	}
	return out;
}

/** The table's scope: the selection another view made (its primary and items). */
export interface TableScopeState {
	primary: string;
	items: readonly string[];
}

/**
 * The table's rows for a scope: (scope ∪ linked) ∩ filters; every object ∩
 * filters with no scope or while the omnibar's results are explored (a
 * `urns` filter) — the store's objectSet rule over a scope the table's own
 * clicks never move (scope.svelte.ts).
 */
export function scopedRows(
	graph: ObjectGraph,
	linked: (urn: string) => readonly ObjectRow[],
	scope: TableScopeState | null,
	filters: readonly Filter[],
	max = 500,
): ObjectRow[] {
	const exploring = filters.some((f) => f.field === 'urns');
	if (scope && !exploring) return selectionRows(graph, linked, scope.primary, scope.items, filters, max);
	const out: ObjectRow[] = [];
	for (const r of graph.all()) {
		if (passesFilters(r, filters, hourOf)) out.push(r);
		if (out.length >= max) break;
	}
	return out;
}

/** A row fades when a window is set and it is outside it (inWindow keeps protected objects and infrastructure). */
export function fades(row: ObjectRow, window: readonly [number, number] | null, inWindow: (o: ObjectRow, w: readonly [number, number]) => boolean): boolean {
	return !!window && !inWindow(row, window);
}

/**
 * The empty table explains itself: an Explorer kind explored while a
 * selection scopes the table can be empty only because none of the
 * selection's links is of that kind — never "nothing here".
 */
export function emptyReason(input: { rows: number; exploredKind: string | null; subject: boolean }): 'kind-not-linked' | 'none' | null {
	if (input.rows > 0) return null;
	return input.exploredKind && input.subject ? 'kind-not-linked' : 'none';
}

/** The selection mode a table click asks for: Ctrl/Cmd toggles, Shift adds, a plain click replaces. */
export function clickMode(e: { ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean; type?: string } | null | undefined): 'replace' | 'add' | 'toggle' {
	if (!e || e.type === 'keydown') return 'replace';
	if (e.ctrlKey || e.metaKey) return 'toggle';
	if (e.shiftKey) return 'add';
	return 'replace';
}
