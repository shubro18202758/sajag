/**
 * Shared pieces of the kind adapters (SPEC §7.2, plan X5): the base row a
 * city entity becomes, state intents, and the inspector's view model.
 *
 * An adapter turns one city entity (the registry, a dossier) into the ONE
 * ObjectRow every view renders, names the links its props imply (rows known
 * only from history carry no `links`), and describes the object for the
 * inspector as data (figures, grouped properties, at most one rule note,
 * raw system fields). Components render that data through the formatter;
 * nothing here builds markup, so the model is unit-tested as plain data.
 *
 * Masking (C6, SPEC §9.3): a row's label and sublabel are always masked
 * (mask.ts: any case, any spelling) — rows reach the omnibar, the search,
 * the table and CSV. The oracle sends some props with a RAW mark inside
 * free text (an e-challan's `recommendation`, a vehicle's `earmark_reason`,
 * a dispatch's `event_title`), so every server or officer text a view shows
 * goes through shownText(ctx, …), and a view built with no named duty
 * officer is masked whole (maskView; adapterFor applies it). A raw mark
 * appears only in a view built for a named officer (ctx.officer).
 */
import { kindIcon, eventKindIcon, type IconName } from '$lib/design/icons';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.workspace';
import type { CityEntity, Dossier } from '$lib/gods-eye/city-api';
import type { ObjectGraph, ObjectLink, ObjectRow, ObjectSource, StateIntent } from '../types';
import { displayTitle, titleParts } from '../display';
import { maskMarks } from '../mask';
import { isTestText } from '../vocabulary';

// ── values ────────────────────────────────────────────────────────────────

export function str(v: unknown): string | null {
	if (typeof v === 'string') return v.trim() ? v : null;
	if (typeof v === 'number' && Number.isFinite(v)) return String(v);
	return null;
}

export function num(v: unknown): number | null {
	return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** Epoch ms of an ISO string or a number; null otherwise. */
export function ms(v: unknown): number | null {
	if (typeof v === 'number' && Number.isFinite(v)) return v > 1e12 ? v : v * 1000;
	if (typeof v === 'string' && v.trim()) {
		const n = Date.parse(v);
		return Number.isFinite(n) ? n : null;
	}
	return null;
}

export function rec(v: unknown): Record<string, unknown> {
	return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

/** A `<kind>:<id>` URN from a prop value, or null when the value is empty. */
export function urnFrom(kind: string, v: unknown): string | null {
	const id = str(v);
	return id ? `${kind}:${id}` : null;
}

// ── states ────────────────────────────────────────────────────────────────

/**
 * The hue a state may take (SPEC §2.4 roles only): orange when a decision
 * waits, green when approved, red for the watchlist or stolen alert. Every
 * other state — Active, Planning, Completed — is neutral.
 */
const STATE_INTENT: Readonly<Record<string, StateIntent>> = {
	pending: 'warning',
	requested: 'warning',
	proposed: 'warning',
	approved: 'success',
	flagged: 'danger',
	stolen_vehicle: 'danger',
};

export function intentOf(state: string | null | undefined): StateIntent {
	return (state && STATE_INTENT[state]) || 'none';
}

// ── the base row ──────────────────────────────────────────────────────────

export interface RowCtx {
	/** The corridor summary says the ingest feed is simulated (segments and anomalies read 'simulated'). */
	simulatedFeed?: boolean;
}

/** The generic row of any city entity: kind glyph, masked label, provenance from source and verification. */
export function baseRow(e: CityEntity, ctx: RowCtx = {}): ObjectRow {
	const parts = titleParts(e.label || e.urn);
	let source: ObjectSource = e.source;
	// FIX-G-ORACLE (HON-11): an entity the oracle marks synthetic is SIMULATED whatever its kind —
	// the synthetic traffic generator's readings, served as live (or, since HON-11, as "emulated":
	// the oracle's nearest word) — the deck says SIMULATED FEED. The corridor summary's
	// simulated-feed flag still speaks for live segments and anomalies only.
	if ((source === 'live' || source === 'emulated') && e.props.data_quality === 'synthetic') {
		source = 'simulated';
	} else if (source === 'live' && (e.kind === 'segment' || e.kind === 'anomaly') && ctx.simulatedFeed) {
		source = 'simulated';
	}
	if (parts.emulated && source === 'live') source = 'emulated';
	return {
		urn: e.urn,
		kind: e.kind,
		id: e.id,
		label: maskMarks(parts.title || e.urn),
		sublabel: null,
		icon: iconOf(e.kind, str(e.props.event_kind)),
		state: e.state,
		stateIntent: intentOf(e.state),
		t: e.t,
		end: null,
		lon: e.lon,
		lat: e.lat,
		source,
		verification: e.verificationState,
		credibility: e.credibility,
		test: parts.test,
		masked: /•/.test(e.label),
		props: e.props,
	};
}

/**
 * A row with its label and sublabel masked (C6): rows reach the omnibar, the
 * search, the table and CSV whoever is on console, so they never hold a raw
 * mark. The same row object when there is nothing to mask.
 */
export function maskedRow(row: ObjectRow): ObjectRow {
	const label = typeof row.label === 'string' ? maskMarks(row.label) : row.label;
	const sublabel = typeof row.sublabel === 'string' ? maskMarks(row.sublabel) : row.sublabel;
	if (label === row.label && sublabel === row.sublabel) return row;
	return { ...row, label, sublabel, masked: row.masked || label !== row.label };
}

/** The glyph of an object: an event by its event kind, any other kind by kindIcon (unknown → dot). */
export function iconOf(kind: string, eventKind?: string | null): IconName {
	return kind === 'event' ? eventKindIcon(eventKind) : kindIcon(kind);
}

/** True when any of the given strings names a rehearsal or test. */
export function anyTest(...values: unknown[]): boolean {
	return values.some((v) => isTestText(v));
}

export { displayTitle, maskMarks };

// ── the inspector's view model ────────────────────────────────────────────

/** A run of inline content, rendered through the formatter. */
export type Run =
	| { text: string }
	| { id: string }
	| { time: number | null; seconds?: boolean }
	/** A window at one precision ("01:20–01:42", "23 Oct 23:52–00:04"): ONE run, never two stamps. */
	| { start: number; end: number | null }
	| { plate: string | null; masked: boolean };

/**
 * Two moments the formatter shows the same (it prints minutes, hh:mm): a
 * window inside one minute is one stamp, never "23:55–23:55". IST is a
 * whole number of minutes off UTC, so the minute is the same in both.
 */
export function sameMinute(a: number | null | undefined, b: number | null | undefined): boolean {
	return a != null && b != null && Math.floor(a / 60_000) === Math.floor(b / 60_000);
}

/** A moment, or a window when it has an end in another minute: the run a subtitle shows it in. */
export function timeRun(t: number, end?: number | null): Run {
	return end != null && !sameMinute(t, end) ? { start: t, end } : { time: t };
}

/** A property value. */
export type PropValue =
	| { t: 'text'; v: string; hint?: string | null }
	| { t: 'id'; v: string; hint?: string | null }
	| { t: 'plate'; mark: string | null; masked: boolean; hint?: string | null }
	| { t: 'time'; ms: number | null; seconds?: boolean; hint?: string | null }
	| { t: 'range'; a: number | null; b: number | null }
	| { t: 'object'; row: ObjectRow }
	| { t: 'tags'; tags: readonly ViewTag[] }
	| { t: 'source'; source: ObjectSource; verification?: string | null; text: string }
	| { t: 'coord'; lat: number; lon: number };

export interface PropRow {
	key: string;
	value: PropValue;
	/** data-testid of the value (pinned hooks such as dossier-phase-window). */
	testid?: string;
	attrs?: Record<string, string>;
}

export interface PropGroup {
	title: string;
	rows: readonly PropRow[];
}

/** A key figure: caption, value, unit (2 to 4 per object). */
export interface Figure {
	caption: string;
	value: string | number | null;
	unit?: string | null;
	/** A time figure (rendered hh:mm IST; a time off the anchor's day carries its day). */
	time?: number | null;
	/** Tooltip prose (the cell's title). */
	hint?: string | null;
	/** A short VISIBLE second line under the value (the way a time's day reads) — set only where the line must be seen,
	 *  e.g. the OSINT Sources figure's context note; long tooltip prose belongs in `hint`. */
	sub?: string | null;
}

/** True when a figure has something to say (a time, a number, a word; never a bare dash). */
function hasValue(f: Figure): boolean {
	if (f.time != null) return true;
	if (typeof f.value === 'number') return Number.isFinite(f.value);
	return typeof f.value === 'string' && f.value.trim() !== '' && f.value.trim() !== '—';
}

/**
 * The key figures a view shows (SPEC §5.3): figures with no value are
 * dropped (no "Class —", no "Decided —"), then two to four remain or none —
 * a lone figure only repeats the subtitle.
 */
export function keyFigures(list: ReadonlyArray<Figure | null | undefined | false>): Figure[] {
	const kept = list.filter((f): f is Figure => !!f && hasValue(f));
	return kept.length >= 2 ? kept.slice(0, 4) : [];
}

export interface ViewTag {
	text: string;
	intent: StateIntent;
	icon?: IconName;
	tooltip?: string | null;
	testid?: string;
}

/** The rule note (SPEC §5.1 Note): one neutral line, at most one per inspector. */
export interface RuleNote {
	icon: IconName;
	title: string | null;
	text: string;
}

export interface InspectorView {
	/** The title runs (a vehicle's is its Plate: the dossier-plate hook). */
	title: readonly Run[];
	/** The title shows the object's registration mark (dossier-plate). */
	plateTitle: boolean;
	/** Subtitle segments, joined by " · ". */
	subtitle: readonly (readonly Run[])[];
	/** A watchlisted or stolen vehicle: the glyph tile is ringed red. */
	alert: boolean;
	tags: readonly ViewTag[];
	figures: readonly Figure[];
	note: RuleNote | null;
	groups: readonly PropGroup[];
	/** Raw values (masked) behind "Show system fields". */
	system: readonly PropRow[];
	/** The registration mark the object carries, as the console may show it (dossier-plate), or null. */
	plate: { mark: string | null; masked: boolean } | null;
}

export interface ViewCtx {
	lang: string;
	now: number;
	/** A named duty officer is on console (ops.officerOn). */
	officer: boolean;
	/** The console's plate sink (ops.plate): raw only for a named officer. */
	plate: (raw: string | null | undefined) => string | null;
	graph: ObjectGraph;
	links: readonly ObjectLink[];
	dossier: Dossier | null;
	/** The ops board's phases for an event id (dossier-phase-window), when the board carries it. */
	phases?: (eventId: string) => readonly { label: string; window: string }[] | null;
	/** True when an event kind may reach citizens (advisories); false = operator-only. */
	publicKind?: (eventKind: string | null) => boolean;
}

/**
 * Server or officer free text as this console may show it (SPEC §9.3, as
 * main's plates.ts displayText): raw only for a named duty officer, else
 * every registration mark masked. Nothing but a mark is ever changed.
 */
export function shownText(ctx: Pick<ViewCtx, 'officer'>, text: string | null | undefined): string | null {
	if (text == null) return null;
	return ctx.officer ? text : maskMarks(text);
}

/** Mask every registration mark in a view's runs. */
function maskRuns(runs: readonly Run[]): Run[] {
	return runs.map((r) => {
		if ('text' in r) return { ...r, text: maskMarks(r.text) };
		if ('id' in r) return { ...r, id: maskMarks(r.id) };
		if ('plate' in r) return r.plate == null ? r : { ...r, plate: maskMarks(r.plate) };
		return r;
	});
}

const maskHint = (h: string | null | undefined) => (typeof h === 'string' ? maskMarks(h) : h);

/** Mask every registration mark in a property value (a linked object shows its masked row). */
function maskValue(v: PropValue): PropValue {
	switch (v.t) {
		case 'text':
		case 'id':
			return { ...v, v: maskMarks(v.v), hint: maskHint(v.hint) };
		case 'plate':
			return { ...v, mark: v.mark == null ? null : maskMarks(v.mark), hint: maskHint(v.hint) };
		case 'time':
			return { ...v, hint: maskHint(v.hint) };
		case 'object':
			return { ...v, row: maskedRow(v.row) };
		case 'tags':
			return { ...v, tags: v.tags.map(maskTag) };
		case 'source':
			return { ...v, text: maskMarks(v.text) };
		default:
			return v;
	}
}

function maskTag(tg: ViewTag): ViewTag {
	return { ...tg, text: maskMarks(tg.text), tooltip: maskHint(tg.tooltip) };
}

function maskPropRows(rows: readonly PropRow[]): PropRow[] {
	return rows.map((r) => ({ ...r, key: maskMarks(r.key), value: maskValue(r.value) }));
}

/**
 * A view with every registration mark masked in every string it shows —
 * title and subtitle runs, tags, key figures, the rule note, every property
 * (text, hints, linked objects) and the system fields (C6, SPEC §9.3). The
 * guard adapterFor applies to every view built with no named duty officer:
 * whatever text an adapter takes from the server, none reaches the page raw.
 */
export function maskView(v: InspectorView): InspectorView {
	return {
		...v,
		title: maskRuns(v.title),
		subtitle: v.subtitle.map(maskRuns),
		tags: v.tags.map(maskTag),
		figures: v.figures.map((f) => ({
			...f,
			caption: maskMarks(f.caption),
			value: typeof f.value === 'string' ? maskMarks(f.value) : f.value,
			unit: maskHint(f.unit),
			hint: maskHint(f.hint),
			sub: maskHint(f.sub),
		})),
		note: v.note ? { ...v.note, title: maskHint(v.note.title) ?? null, text: maskMarks(v.note.text) } : null,
		groups: v.groups.map((g) => ({ title: maskMarks(g.title), rows: maskPropRows(g.rows) })),
		system: maskPropRows(v.system),
		plate: v.plate ? { ...v.plate, mark: v.plate.mark == null ? null : maskMarks(v.plate.mark) } : null,
	};
}

/** The i18n helper of the adapters. */
export function L(ctx: Pick<ViewCtx, 'lang'>, key: string, ...args: unknown[]): string {
	return t(ctx.lang, key, ...args);
}

/** A text property, or nothing when the value is empty. */
export function textRow(key: string, v: unknown, hint?: string | null): PropRow | null {
	const s = typeof v === 'string' ? v : num(v) != null ? String(v) : null;
	return s && s.trim() ? { key, value: { t: 'text', v: s, hint: hint ?? null } } : null;
}

export function idRow(key: string, v: unknown): PropRow | null {
	const s = str(v);
	return s ? { key, value: { t: 'id', v: s } } : null;
}

export function timeRow(key: string, v: unknown, opts: { seconds?: boolean; hint?: string | null } = {}): PropRow | null {
	const m = ms(v);
	return m != null ? { key, value: { t: 'time', ms: m, seconds: opts.seconds, hint: opts.hint ?? null } } : null;
}

export function objectRow(key: string, row: ObjectRow | null | undefined): PropRow | null {
	return row ? { key, value: { t: 'object', row } } : null;
}

/** Drop empty rows and empty groups. */
export function groups(...list: Array<{ title: string; rows: Array<PropRow | null | undefined | false> }>): PropGroup[] {
	return list
		.map((g) => ({ title: g.title, rows: g.rows.filter((r): r is PropRow => !!r) }))
		.filter((g) => g.rows.length > 0);
}

/** The system fields: the URN, the raw label and the scalar props, every string masked (C6). */
export function systemRows(row: ObjectRow, extra: Record<string, unknown> = {}): PropRow[] {
	const out: PropRow[] = [{ key: 'urn', value: { t: 'id', v: row.urn } }];
	const add = (k: string, v: unknown) => {
		if (v == null || k === 'plate') return;
		if (typeof v === 'string') out.push({ key: k, value: { t: 'id', v: maskMarks(v) } });
		else if (typeof v === 'number' || typeof v === 'boolean') out.push({ key: k, value: { t: 'id', v: String(v) } });
	};
	for (const [k, v] of Object.entries(extra)) add(k, v);
	for (const [k, v] of Object.entries(row.props)) {
		if (k in extra) continue;
		add(k, v);
	}
	return out.slice(0, 40);
}

/** Linked rows of one relation (from the view's links). */
export function linkedBy(ctx: Pick<ViewCtx, 'links'>, relation: string): ObjectRow[] {
	return ctx.links.filter((l) => l.relation === relation).map((l) => l.row);
}

/** Compass words for a heading in degrees. */
export function compass(deg: number | null, lang: string): string {
	if (deg == null || !Number.isFinite(deg)) return '—';
	const i = Math.round((((deg % 360) + 360) % 360) / 45) % 8;
	return t(lang, `ws_dir_${i}`);
}

/** Whole days from now until `until` (null when unknown). */
export function daysLeft(until: number | null, now: number): number | null {
	return until == null ? null : Math.max(0, Math.round((until - now) / 86_400_000));
}
