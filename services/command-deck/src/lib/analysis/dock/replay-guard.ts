/**
 * Replay is blocked on `/` while a movement or a pursuit is live (SPEC §7.3):
 * the reason, or null. On `/gods-eye` replay is allowed (live layers stand
 * down; the LiveStrip and the inbox stay live).
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.analysis';
import type { ObjectGraph } from '$lib/workspace/types';

const OPEN = new Set(['active', 'live', 'open', 'approved', 'planned', 'planning']);

export function replayBlockReason(route: string | null, graph: Pick<ObjectGraph, 'byKind'>, lang = 'en'): string | null {
	if (route !== '/') return null;
	let movement = false;
	let pursuit = false;
	for (const ev of graph.byKind('event')) {
		if (ev.state && !OPEN.has(ev.state)) continue;
		const kind = ev.props.event_kind;
		if (kind === 'protected_movement' && (ev.state === 'active' || ev.state === 'live')) movement = true;
		if (kind === 'vehicle_pursuit') pursuit = true;
	}
	if (movement) return t(lang, 'an_replay_blocked_movement');
	if (pursuit) return t(lang, 'an_replay_blocked_pursuit');
	return null;
}
