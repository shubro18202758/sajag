/**
 * The audit table's rows (SPEC §5.3 "AuditTable and AI trace [S4]"), pure:
 * one item per audit row, from either source the deck has —
 *
 *   itemFromFeed   a city feed row (GET /city/feed, the dossier's audit):
 *                  the fusion dock and the workspace's Audit tab
 *   itemFromEntry  a row of the ops ledger (ops.audit: the selected event's
 *                  server rows or the city's, plus this console's local rows
 *                  — refusals before the wire, probe steps, echoes): /ops
 *
 * Every item keeps what the oracle recorded — the stable row id, the actor
 * KIND (an oracle, twin or model reply is never shown as human), the URNs,
 * the source (emulated, osint) — and shows it humanised: the actor through
 * displayActor ("traffic-oracle" → "Rules engine"), the text through
 * displayText with identifiers left as sent. The full server sentence,
 * officer's note included byte for byte, stays in the row's tooltip
 * (`full`). Registration marks are masked unless a named duty officer is on
 * console (the caller says; a raw mark only from the row's own props.plate),
 * and the mask is the workspace's (mask.ts): any case and spelling —
 * mh47em9001, MH.01.XX.0007, MH_47_EM_9001 — never only the upper-case
 * form the oracle writes (SPEC §9.3: no raw mark in DOM text without a named
 * officer; an officer's typed note can carry one in any spelling).
 *
 * Provenance marks NON-LIVE rows only: emulated, simulated, and open-source
 * with its verification label (ethics rule 7). The AI trace is the same
 * table filtered to model rows, with phase, tier and confidence, and no
 * officer row (no dismissals).
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.analysis';
import type { FeedRow } from '$lib/gods-eye/city-api';
import { maskMarks } from '$lib/workspace/mask';
import type { IconName } from '$lib/design/icons';
import type { AuditEntry, VerificationState } from '$lib/ops/types';
import { actorName, actorParts, displayRowText, displayText, displayTool, human } from '$lib/workspace/display';
import { actorGlyph } from '$lib/workspace/components/inspector/model';
import { laneOf } from '../timeline/lanes';
import { osintLabel } from '../timeline/tip';

export type AuditFilter = 'all' | 'officers' | 'machine' | 'system';
export type AuditScope = 'city' | 'event';
export type AuditMode = 'audit' | 'ai';

export type ProvSource = 'emulated' | 'simulated' | 'osint';
export type ProvVerification = 'UNVERIFIED-OSINT' | 'NEWS-REPORTED' | 'OFFICIAL-VERIFIED' | 'CONFIRMED';

export interface AuditItem {
	/** A stable key for the row. */
	id: string;
	/** `data-feed-id`: the server row id, or this console's own id for a local row. */
	feedId: string;
	/** `data-row-id`: server rows only (tests and deep links read it). */
	rowId: string | null;
	/** The row's primary object (its first URN), or null. */
	urn: string | null;
	urns: readonly string[];
	t: number;
	/** The feed kind (lane) or, for a local row, its level. */
	kind: string;
	kindLabel: string;
	actorKind: 'human' | 'machine' | 'system';
	/** The actor as shown ("Rules engine", "Sajag AI", an officer's name). */
	actor: string;
	/** The actor as recorded (tooltip). */
	actorRaw: string;
	actorTest: boolean;
	glyph: IconName;
	/** The glyph is the AI's (indigo). */
	ai: boolean;
	/** What happened, humanised (ids and masked marks left as sent). */
	text: string;
	/** The whole sentence as recorded (masked): the tooltip, the CSV. */
	full: string;
	/** `data-level`. */
	level: string;
	source: 'live' | 'emulated' | 'osint';
	/** The compact provenance mark, non-live rows only. */
	prov: { source: ProvSource; verification: ProvVerification | null } | null;
	/** A second mark: the row's numbers came from a SIMULATED feed. */
	simulated: boolean;
	severity: 'info' | 'warn' | 'critical';
	/** Written by this console (no server row). */
	local: boolean;
	phase: string | null;
	tier: string | null;
	confidence: number | null;
	/** The evidence payload (a dialog), or undefined. */
	detail?: unknown;
}

const VERIFS: ReadonlySet<string> = new Set(['UNVERIFIED-OSINT', 'NEWS-REPORTED', 'OFFICIAL-VERIFIED', 'CONFIRMED']);

function verifOf(v: VerificationState | string | null | undefined): ProvVerification | null {
	return typeof v === 'string' && VERIFS.has(v) ? (v as ProvVerification) : null;
}

function str(v: unknown): string | null {
	return typeof v === 'string' && v.trim() ? v : null;
}

function num(v: unknown): number | null {
	return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function rec(v: unknown): Record<string, unknown> {
	return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

/** The kind of a row in words ("Enforcement", "ANPR read", "Open-source"). */
export function kindWord(kind: string, lang = 'en'): string {
	const key = `an_kind_${kind}`;
	const v = t(lang, key);
	if (v !== key) return v;
	const lv = t(lang, `an_level_${kind}`);
	return lv !== `an_level_${kind}` ? lv : human(kind);
}

/** "decider_checkpoint" → "Decider checkpoint". */
function phaseWord(raw: string | null): string | null {
	if (!raw) return null;
	const w = raw.replace(/_/g, ' ').trim();
	return w ? w.charAt(0).toUpperCase() + w.slice(1) : null;
}

/** The text as this console may show it: masked unless an officer is named; a raw mark only from props.plate. */
function shownText(text: string, props: Readonly<Record<string, unknown>>, officer: boolean): string {
	const plate = str(props.plate);
	const masked = str(props.plate_masked);
	if (officer && plate && masked) return text.split(masked).join(plate);
	return officer ? text : maskMarks(text);
}

export interface ItemOpts {
	/** A named duty officer is on console (raw marks through props.plate only). */
	officer?: boolean;
	lang?: string;
}

/** A city feed row → an audit item. */
export function itemFromFeed(row: FeedRow, opts: ItemOpts = {}): AuditItem {
	const lang = opts.lang ?? 'en';
	const officer = opts.officer === true;
	const p = row.props ?? {};
	const parts = row.actor ? actorParts(row.actor) : null;
	const g = actorGlyph(row.actorKind, row.actor);
	const wire = row.feedKind ?? row.kind;
	const lane = laneOf(row) ?? row.kind;
	const raw = shownText(row.text ?? '', p, officer);
	const humanised = displayRowText({ kind: row.kind, text: raw, actorKind: row.actorKind, props: p });
	const verification = row.source === 'osint' ? verifOf(row.verificationState) : null;
	const simulated = p.simulated_feed === true || p.data_quality === 'synthetic' || p.data_quality === 'simulated';
	const prov: AuditItem['prov'] = row.source === 'osint' ? { source: 'osint', verification } : row.source === 'emulated' ? { source: 'emulated', verification: null } : null;
	return {
		id: row.id,
		feedId: row.id,
		rowId: row.id,
		urn: row.urns[0] ?? null,
		urns: row.urns,
		t: row.t,
		kind: wire === 'osint' ? 'osint' : lane,
		kindLabel: kindWord(wire === 'osint' ? 'osint' : lane, lang),
		actorKind: row.actorKind,
		// the shown name is DOM text too: masked in every spelling unless a named officer is on console (as itemFromEntry)
		actor: masked(parts ? actorName(parts, lang) : t(lang, `an_au_${row.actorKind === 'human' ? 'officers' : row.actorKind}`), officer),
		actorRaw: officer ? (row.actor ?? row.actorKind) : maskMarks(row.actor ?? row.actorKind),
		actorTest: parts?.test ?? false,
		glyph: g.glyph,
		ai: g.ai,
		text: humanised || raw,
		full: raw,
		level: row.severity === 'critical' ? 'decision' : lane === 'brain' ? 'model' : 'info',
		source: row.source,
		prov,
		simulated,
		severity: row.severity,
		local: false,
		phase: phaseWord(str(p.phase)),
		tier: str(p.tier),
		confidence: num(p.confidence),
	};
}

/** A row of the ops ledger (ops.audit — already masked under the plate rule) → an audit item. */
export function itemFromEntry(e: AuditEntry, opts: ItemOpts = {}): AuditItem {
	const lang = opts.lang ?? 'en';
	const officer = opts.officer === true;
	const server = !!e.serverId;
	// the ledger is published masked; the mask runs again here in every spelling (defence in depth)
	const raw = officer ? e.text : maskMarks(e.text);
	const actorKind = e.actorKind ?? 'machine';
	const tool = e.actor.startsWith('mcp:') ? e.actor.slice(4) : null;
	const parts = tool ? null : actorParts(e.actor);
	const actor = tool ? displayTool(tool) : parts ? actorName(parts, lang) : e.actor;
	const g = actorGlyph(actorKind, tool ? 'assistant' : e.actor);
	const ai = g.ai || (actorKind === 'machine' && (e.level === 'model' || e.level === 'tool'));
	const kind = server ? (e.kind ?? 'event') : e.level;
	const detail = rec(e.detail);
	const props = rec(detail.props);
	const urns = e.urns ?? [];
	const prov: AuditItem['prov'] = e.emulated ? { source: 'emulated', verification: null } : null;
	return {
		id: `ledger:${e.id}`,
		feedId: e.serverId ?? `local:${e.id}`,
		rowId: e.serverId ?? null,
		urn: urns[0] ?? null,
		urns,
		t: e.ts,
		kind,
		kindLabel: server ? kindWord(e.kind ?? 'event', lang) : kindWord(e.level, lang),
		actorKind,
		actor: officer ? actor : maskMarks(actor),
		actorRaw: officer ? e.actor : maskMarks(e.actor),
		actorTest: parts?.test ?? false,
		glyph: g.glyph,
		ai,
		// local rows are this console's own words: shown as written (masked)
		text: server ? displayText(raw) || raw : raw,
		full: raw,
		level: e.level,
		source: e.emulated ? 'emulated' : 'live',
		prov,
		simulated: e.simulated === true,
		severity: e.severity === 'critical' || e.severity === 'warn' ? e.severity : 'info',
		local: !server,
		phase: phaseWord(str(props.phase) ?? str(detail.phase)),
		tier: str(props.tier) ?? str(detail.tier),
		confidence: num(props.confidence) ?? num(detail.confidence),
		detail: e.detail,
	};
}

/** Rows a filter keeps. */
export function filterItems(items: readonly AuditItem[], filter: AuditFilter): AuditItem[] {
	if (filter === 'all') return [...items];
	const want = filter === 'officers' ? 'human' : filter;
	return items.filter((i) => i.actorKind === want);
}

/** Per-filter counts. */
export function filterCounts(items: readonly AuditItem[]): Record<AuditFilter, number> {
	const out: Record<AuditFilter, number> = { all: items.length, officers: 0, machine: 0, system: 0 };
	for (const i of items) {
		if (i.actorKind === 'human') out.officers++;
		else out[i.actorKind]++;
	}
	return out;
}

/**
 * The AI trace: model rows only — the city feed's AI decisions (kind
 * `brain`), and in the ops ledger the model's answers, tool calls and
 * decisions. Never an officer's row: dismissals are not the AI's.
 */
export function aiTrace(items: readonly AuditItem[]): AuditItem[] {
	return items.filter((i) => {
		if (i.actorKind === 'human') return false;
		if (i.kind === 'brain') return true;
		if (!i.local) return false;
		return i.level === 'model' || i.level === 'tool' || (i.level === 'decision' && i.ai) || (i.level === 'band' && i.ai);
	});
}

/**
 * One item per id, the first kept. Two sources merged into one list (a
 * harness's seeded rows and a poll, an overlap read) can repeat a row; a
 * keyed table must never see the same key twice.
 */
export function uniqueById<T extends { id: string }>(items: readonly T[]): T[] {
	const seen = new Set<string>();
	const out: T[] = [];
	for (const i of items) {
		if (seen.has(i.id)) continue;
		seen.add(i.id);
		out.push(i);
	}
	return out;
}

/**
 * SPEC §9.2 provenance display: the one provenance EVERY item shares
 * ("uniform list": the header states it once, the rows carry none but a
 * visually hidden word), or null for a mixed list (non-live rows carry the
 * compact glyph) and for an all-live list (nothing to state).
 */
export function uniformProv(items: readonly AuditItem[]): AuditItem['prov'] {
	if (!items.length) return null;
	const first = items[0].prov;
	if (!first) return null;
	for (const i of items) if (i.prov?.source !== first.source || i.prov?.verification !== first.verification) return null;
	return first;
}

/** Newest first. */
export function newestFirst(items: readonly AuditItem[]): AuditItem[] {
	return [...items].sort((a, b) => b.t - a.t || (a.id < b.id ? 1 : -1));
}

/** The CSV of the rows in view (SPEC §7.5: masked marks, with a provenance column). */
export function toCsv(items: readonly AuditItem[], lang = 'en'): string {
	const esc = (v: unknown) => {
		const s = maskMarks(String(v ?? ''));
		return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
	};
	const head = [t(lang, 'an_au_time'), t(lang, 'an_au_kind'), t(lang, 'an_au_actor'), t(lang, 'an_au_what'), t(lang, 'an_au_object'), t(lang, 'an_au_source')];
	const lines = [head.map(esc).join(',')];
	for (const i of items) {
		const prov = i.prov ? (i.prov.verification ? `${i.prov.source} (${i.prov.verification})` : i.prov.source) : 'live';
		lines.push([new Date(i.t).toISOString(), i.kindLabel, i.actor, i.full || i.text, i.urn ?? '', prov].map(esc).join(','));
	}
	return lines.join('\n');
}

/** A text as this console may print it: raw only to a named duty officer, else masked in every spelling. */
export function masked(text: string | null | undefined, officer: boolean): string {
	const s = text ?? '';
	return officer ? s : maskMarks(s);
}

/** A provenance in words (the uniform list's hidden per-row word): "Emulated", "Simulated", or the open-source X2 label. */
export function provWord(p: NonNullable<AuditItem['prov']>, lang = 'en'): string {
	if (p.source === 'osint') return osintLabel(p.verification, lang);
	return t(lang, p.source === 'emulated' ? 'ui_prov_emulated' : 'ui_prov_simulated');
}
