/**
 * The event-history client (SPEC §8.4, §13.3): GET /api/v1/events?limit=200
 * — every corridor event the oracle keeps, closed ones included, newest first
 * by `updated_at` (contract C-F; UI-S7A's fixture
 * tests/contract/fixtures/events_history.sandbox.json shows the shape). The
 * timeline draws each event's span in the Events lane, and the analysis
 * provider registers the rows as an object source, so an event known only
 * from history (a closed pursuit, a completed movement) still has an object
 * in the graph, the table and the inspector.
 *
 * Read once a minute while a view needs it (history.svelte.ts); never
 * written. The parse is tolerant: `{events: […]}` or a bare array, a row
 * without an id or a time is dropped, an unknown status is kept as sent,
 * and every string a row carries is MASKED in any case and spelling
 * (workspace/mask.ts: a registration mark in a title or metadata never
 * reaches the client model — the oracle masks its feed, not this endpoint). No person field is read or kept: the deck reads only
 * the event's own fields.
 */
import { ORACLE_V1 } from '$lib/ops/endpoints';
import { getJson } from '$lib/gods-eye/data';
import { maskMarks } from '$lib/workspace/mask';

export const EVENT_HISTORY_API = `${ORACLE_V1}/events`;
/** The newest rows read (the oracle's own cap for this listing). */
export const EVENT_HISTORY_LIMIT = 200;
/** Once a minute (SPEC §13.3: a new read, no faster). */
export const EVENT_HISTORY_POLL_MS = 60_000;

export type EventHistorySource = 'live' | 'emulated' | 'osint';

/** One event of the history, as the views read it. */
export interface EventHistoryRow {
	eventId: string;
	urn: string;
	/** The corridor event kind (`protected_movement`, `vehicle_pursuit`, …), or null. */
	kind: string | null;
	/** The title, masked. */
	title: string;
	/** The raw status (`planning`, `active`, `completed`, `cancelled`, …), or null. */
	status: string | null;
	/** Epoch ms the span starts: actual start, else planned start, else the last update. */
	start: number;
	/** Epoch ms the span ends: actual end, else planned end; null while open. */
	end: number | null;
	/** Epoch ms of the row's last update. */
	updatedAt: number | null;
	/**
	 * The span the timeline draws: the actual run ([actual start, actual end —
	 * or open while the event runs]), else a still-planned window; null for an
	 * event that never ran (cancelled before its start, or no time at all).
	 */
	span: [number, number | null] | null;
	source: EventHistorySource;
	/** The row as sent, every string masked (the object adapter reads it). */
	raw: Record<string, unknown>;
}

const OPEN_STATES = new Set(['planning', 'planned', 'approved', 'active', 'live', 'open']);

function rec(v: unknown): Record<string, unknown> {
	return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

function str(v: unknown): string | null {
	return typeof v === 'string' && v.trim() ? v : null;
}

function ms(v: unknown): number | null {
	if (typeof v === 'number' && Number.isFinite(v)) return v;
	if (typeof v === 'string' && v.trim()) {
		const t = Date.parse(v);
		return Number.isFinite(t) ? t : null;
	}
	return null;
}

/** Every string at any depth through the mark mask (ethics rule 5: a raw mark never enters the model). */
export function maskDeep(v: unknown, depth = 0): unknown {
	if (depth > 8) return null;
	if (typeof v === 'string') return maskMarks(v);
	if (Array.isArray(v)) return v.map((x) => maskDeep(x, depth + 1));
	if (v && typeof v === 'object') {
		const out: Record<string, unknown> = {};
		for (const [k, x] of Object.entries(v as Record<string, unknown>)) out[k] = maskDeep(x, depth + 1);
		return out;
	}
	return v;
}

/** One wire row → history row; null when it has no id or no time at all. */
export function parseEventHistoryRow(raw: unknown): EventHistoryRow | null {
	const r = rec(maskDeep(raw));
	const id = str(r.event_id) ?? str(r.id);
	if (!id || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$/.test(id)) return null;
	const md = rec(r.metadata);
	const updatedAt = ms(r.updated_at);
	const start = ms(r.actual_start) ?? ms(r.planned_start) ?? updatedAt;
	if (start == null) return null;
	const endRaw = ms(r.actual_end) ?? ms(r.planned_end);
	const status = str(r.status);
	const open = status != null && OPEN_STATES.has(status);
	// a closed event's span ends at its end (or its last update); an open one runs to now
	const end = endRaw != null && endRaw >= start ? endRaw : open ? null : (updatedAt != null && updatedAt >= start ? updatedAt : start);
	const actualStart = ms(r.actual_start);
	const plannedStart = ms(r.planned_start);
	const settled = status === 'completed' || status === 'cancelled';
	let span: [number, number | null] | null = null;
	if (actualStart != null) {
		const ae = ms(r.actual_end);
		span = [actualStart, ae != null && ae >= actualStart ? ae : open ? null : (updatedAt != null && updatedAt >= actualStart ? updatedAt : actualStart)];
	} else if (plannedStart != null && !settled) {
		const pe = ms(r.planned_end);
		span = [plannedStart, pe != null && pe >= plannedStart ? pe : null];
	}
	const sourceKind = str(r.source_kind);
	const title = str(r.title) ?? str(r.name) ?? id;
	const source: EventHistorySource =
		sourceKind === 'osint' ? 'osint' : md.source === 'event-emulator' || sourceKind === 'emulator' || /\(emulated\)/i.test(title) ? 'emulated' : 'live';
	return {
		eventId: id,
		urn: `event:${id}`,
		kind: str(r.event_kind),
		title,
		status,
		start,
		end,
		updatedAt,
		span,
		source,
		raw: r,
	};
}

/** GET /events body → rows, newest first by update (tolerant: junk rows are dropped). */
export function parseEventHistory(resp: unknown): EventHistoryRow[] {
	const body = rec(resp);
	const list = Array.isArray(body.events) ? body.events : Array.isArray(resp) ? (resp as unknown[]) : [];
	const out: EventHistoryRow[] = [];
	const seen = new Set<string>();
	for (const raw of list.slice(0, EVENT_HISTORY_LIMIT * 2)) {
		const row = parseEventHistoryRow(raw);
		if (!row || seen.has(row.eventId)) continue;
		seen.add(row.eventId);
		out.push(row);
	}
	return out.sort((a, b) => (b.updatedAt ?? b.start) - (a.updatedAt ?? a.start)).slice(0, EVENT_HISTORY_LIMIT);
}

/** GET /api/v1/events?limit=200 — the event history (throws NotDeployed on 404, Down otherwise). */
export async function fetchEventHistory(signal?: AbortSignal): Promise<EventHistoryRow[]> {
	return parseEventHistory(await getJson<unknown>(`${EVENT_HISTORY_API}?limit=${EVENT_HISTORY_LIMIT}`, 10_000, signal));
}
