/**
 * Watches (SPEC §7.3, §8.8): "tell me when this object or this filtered set
 * changes". The logic only — the Explorer's list (UI-S2X) reads
 * workspace.watches, and the inbox's Updates read matchesWatch().
 *
 * A watch adds rows to the inbox's Updates; it NEVER mutes an interrupt
 * (an escort proposal, a watchlist read, a band change during a movement,
 * a feed loss): there is no mute field here, by design.
 *
 * Stored masked in this browser's localStorage (a title with marks masked,
 * the subject as a URN, filters through hash.ts's guards); every access is
 * wrapped, and the workspace works without storage.
 */
import { parseUrn } from '$lib/gods-eye/city-api';
import { cleanFilters, safeText } from './hash';
import type { Filter, ObjectRow, Watch } from './types';

export const WATCHES_KEY = 'sajag.workspace.watches.v1';
export const WATCHES_MAX = 50;

/** A watch as it may be stored (masked title, a valid URN or null, clean filters); null when unusable. */
export function cleanWatch(w: Partial<Watch> & { id: string }): Watch | null {
	const title = safeText(w.title, 80);
	if (!title) return null;
	const subjectUrn = typeof w.subjectUrn === 'string' && parseUrn(w.subjectUrn) ? w.subjectUrn : null;
	const filters = cleanFilters(Array.isArray(w.filters) ? w.filters : [], (i) => `${w.id}-f${i + 1}`);
	if (!subjectUrn && !filters.length) return null;
	return { id: w.id.slice(0, 40), title, subjectUrn, filters };
}

export function loadWatches(storage: Storage | null): Watch[] {
	if (!storage) return [];
	try {
		const raw = storage.getItem(WATCHES_KEY);
		if (!raw) return [];
		const list: unknown = JSON.parse(raw);
		if (!Array.isArray(list)) return [];
		const out: Watch[] = [];
		for (const v of list) {
			if (!v || typeof v !== 'object' || typeof (v as Watch).id !== 'string') continue;
			const w = cleanWatch(v as Watch);
			if (w) out.push(w);
			if (out.length >= WATCHES_MAX) break;
		}
		return out;
	} catch {
		return [];
	}
}

export function storeWatches(storage: Storage | null, watches: readonly Watch[]): boolean {
	if (!storage) return false;
	try {
		storage.setItem(WATCHES_KEY, JSON.stringify(watches.slice(0, WATCHES_MAX)));
		return true;
	} catch {
		return false;
	}
}

let seq = 0;

/** A new watch id. */
export function newWatchId(now: number): string {
	seq += 1;
	return `w${now.toString(36)}${seq.toString(36)}`;
}

/** True when a row passes one filter (values OR-ed). */
export function passesFilter(row: ObjectRow, f: Filter, hourOf: (t: number) => string): boolean {
	const values = f.values;
	switch (f.field) {
		case 'kind':
			return values.includes(row.kind);
		case 'state':
			return row.state != null && values.includes(row.state);
		case 'source':
			return values.includes(row.source) || (row.test && values.includes('test'));
		case 'hour':
			return row.t != null && values.includes(hourOf(row.t));
		case 'road': {
			const p = row.props;
			const ev = (p.evidence ?? {}) as Record<string, unknown>;
			const road = [p.road_name, ev.road_name, row.kind === 'segment' ? row.label : null].find((r) => typeof r === 'string');
			return typeof road === 'string' && values.includes(road);
		}
		case 'camera': {
			const p = row.props;
			const ev = (p.evidence ?? {}) as Record<string, unknown>;
			const cam = row.kind === 'camera' ? row.id : [p.camera_id, ev.camera_id, p.last_camera_id].find((c) => typeof c === 'string');
			return typeof cam === 'string' && values.includes(cam);
		}
		case 'urns':
			return values.includes(row.urn);
		default:
			return false;
	}
}

/** True when a row passes every filter (fields AND-ed). */
export function passesFilters(row: ObjectRow, filters: readonly Filter[], hourOf: (t: number) => string): boolean {
	for (const f of filters) if (!passesFilter(row, f, hourOf)) return false;
	return true;
}

/** True when a row is what a watch watches: its subject, or a row its filters pass. */
export function matchesWatch(w: Watch, row: ObjectRow, hourOf: (t: number) => string): boolean {
	if (w.subjectUrn && row.urn === w.subjectUrn) return true;
	return w.filters.length > 0 && passesFilters(row, w.filters, hourOf);
}
