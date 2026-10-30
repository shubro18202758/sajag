/**
 * The board entry of a field or camera report — the platform's own ingestion path for a reported situation on the
 * officers' board: POST /api/v1/events (EVENTS_API, a fixed path), created by the named officer who presses Send, in
 * the oracle's `planning` state, labelled unverified (model.ts boardDraftFrom*). Operator pages only; the public pages
 * never import this module.
 */
import { EVENTS_API } from '$lib/ops/endpoints';
import { FieldApiError, call, fail } from './api';
import type { BoardDraft } from './model';

/**
 * The board entry — CITY WRITER (POST /api/v1/events, the fixed EVENTS_API path): one POST per press, by the named
 * officer the draft carries (the deck's verified session adds the officer header upstream). The oracle creates it in
 * `planning`; an officer confirms, edits or dismisses it on the board. Never retried.
 */
export async function writeBoardEntry(draft: BoardDraft): Promise<{ eventId: string }> {
	if (!draft.officer || draft.officer.length < 2) throw new FieldApiError('bad', 0, 'a named officer');
	const body: Record<string, unknown> = { ...draft };
	if (!draft.geotag) delete body.geotag;
	const res = await call(EVENTS_API, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }, 15_000);
	if (!res.ok) await fail(res);
	const out = (await res.json()) as { event_id?: unknown };
	if (typeof out?.event_id !== 'string') throw new FieldApiError('bad', res.status, 'no event id');
	return { eventId: out.event_id };
}
