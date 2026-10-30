/**
 * Decide's rules (V3-SPEC §5.3, §6.2, §7.1) — the small, pure decisions the /decide screen makes about a
 * decision unit, kept out of the components so tests/decide.unit.mjs can hold them:
 *
 *   actionsOf       which verbs a unit offers NOW (the primary and the secondaries), the same reading the
 *                   v2 ProposalCard makes of decisions/writers.ts's ACTIONS (a stolen vehicle offers
 *                   Authorise, then Open the pursuit; an e-challan on a stolen vehicle and a refused one
 *                   offer no Approve); every verb runs through its EXISTING writer (writerKindOf);
 *   needsReason     the verbs whose writer refuses without the officer's reason (dismiss, reject, defer;
 *                   an escort's Reject needs none — the countdown is the constraint);
 *   keyIntent       the keyboard (§7.1): J / K next / previous, 1–4 choose an option, Enter focuses the
 *                   primary button, R opens the reason. NO key maps to approve, dispatch or unmask;
 *   escortPhase     an escort proposal is open, answered (locked: ops.escortAnswered) or expired (the
 *                   current plan is kept);
 *   coaFigure       the ONE figure a response option shows (time to the scene, or "no units");
 *   when            the queue's timer line ("0:47 left", "1 h 34 min left", "waiting 14 min").
 *
 * No runes and no DOM here; the store is read only through the arguments.
 */
import { UNIT_KINDS, echallanOf, escortOf, stolenOf, type Unit } from '$lib/decisions/units';
import { ACTIONS, writerFor, type WriterEntry } from '$lib/decisions/writers';
import { unitKey as homeUnitKey } from '$lib/decisions/homes';
import { parseUnitKey } from '$lib/decisions/homes';
import { waitingSince } from '$lib/decisions/cards/meta';
import type { DssCoa } from '$lib/ops/client';
import { fmtCountdown, fmtDuration } from '$lib/ui/format/format';

/** A unit's identity across polls (the same key Home uses). */
export const keyOf = (u: { kind: string; id: string }) => `${u.kind}:${u.id}`;

/** The deep link of a unit: /decide/<kind>:<id> (never a mark). */
export function decideHref(u: { kind: string; id: string }): string {
	const k = homeUnitKey(u.kind, u.id);
	return k ? `/decide/${encodeURIComponent(k)}` : '/decide';
}

/** The `[unit]` route parameter → {kind, id}, or null when it is hostile or unknown. */
export function parseDeepLink(param: string | null | undefined): { kind: string; id: string } | null {
	if (!param) return null;
	let v = param;
	try {
		v = decodeURIComponent(param);
	} catch {
		return null;
	}
	const p = parseUnitKey(v);
	return p && UNIT_KINDS[p.kind] ? p : null;
}

// ── the verbs a unit offers ─────────────────────────────────────────────

export interface UnitActions {
	/** The one primary verb (null: nothing to approve — e.g. an e-challan on a stolen vehicle). */
	primary: string | null;
	/** The secondary verbs, in button order. */
	secondary: string[];
}

/** The writer kind of a verb: Open pursuit is the pursuit writer, whatever the unit (ProposalCard's rule). */
export const writerKindOf = (u: Unit, action: string) => (action === 'open' ? 'pursuit' : u.kind);

/** The writer entry of a unit's verb (decisions/writers.ts — the one write path). */
export function writerOf(u: Unit, action: string | null): WriterEntry | null {
	return action ? writerFor(writerKindOf(u, action), action) : null;
}

export function actionsOf(u: Unit): UnitActions {
	switch (u.kind) {
		case 'stolen-sighting': {
			const d = stolenOf(u);
			const primary = d.refusal ? null : d.approved ? (d.step.state === 'open' ? null : 'open') : 'authorise';
			// once authorised, the earlier sightings are still dismissable under one reason
			return { primary, secondary: ['dismiss'] };
		}
		case 'echallan': {
			const d = echallanOf(u);
			return { primary: d.stolen || d.refusal ? null : 'approve', secondary: ['reject'] };
		}
		case 'dss':
			// X22: Reject is the footer's secondary, Defer sits beside it (same writer gate, same note rule)
			return { primary: 'approve', secondary: ['reject', 'defer'] };
		default: {
			const a = ACTIONS[u.kind];
			return { primary: a?.primary ?? null, secondary: a?.secondary ? [a.secondary] : [] };
		}
	}
}

/** True when the verb's writer refuses without the officer's reason. */
export function needsReason(u: Unit, action: string): boolean {
	if (action === 'dismiss' || action === 'defer') return true;
	if (action === 'reject') return u.kind !== 'escort-proposal';
	return false;
}

/** The outcome words key: dec_done_<action>_<group> (ProposalCard's grouping; a dss verb reads as the pursuit group's plain words). */
export function doneKey(u: Unit, action: string): string {
	const g = u.kind === 'escort-proposal' ? 'escort' : u.kind === 'corridor-request' ? 'corridor' : u.kind === 'echallan' ? 'echallan' : 'pursuit';
	return `dec_done_${action}_${g}`;
}

/** Which session tally a successful verb counts towards. */
export function tallyOf(action: string): 'approved' | 'rejected' | 'deferred' {
	if (action === 'reject' || action === 'dismiss') return 'rejected';
	if (action === 'defer') return 'deferred';
	return 'approved';
}

// ── the keyboard (V3-SPEC §7.1) ─────────────────────────────────────────

export type KeyIntent = { kind: 'next' } | { kind: 'prev' } | { kind: 'option'; index: number } | { kind: 'focus-primary' } | { kind: 'reason' } | null;

/**
 * A key → what Decide does with it. Never approve: Enter only FOCUSES the primary button; R opens the
 * reason field (a reject still needs the reason and a click). Keys with a modifier, keys while typing and
 * keys another handler took are ignored.
 */
export function keyIntent(e: { key: string; ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean; defaultPrevented?: boolean }, typing: boolean): KeyIntent {
	if (e.defaultPrevented || typing || e.ctrlKey || e.metaKey || e.altKey) return null;
	const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
	if (k === 'j' || k === 'ArrowDown') return { kind: 'next' };
	if (k === 'k' || k === 'ArrowUp') return { kind: 'prev' };
	if (k === '1' || k === '2' || k === '3' || k === '4') return { kind: 'option', index: Number(k) - 1 };
	if (k === 'Enter') return { kind: 'focus-primary' };
	if (k === 'r') return { kind: 'reason' };
	return null;
}

/** The unit `step` places after `current` in `units` (wraps; the first when none is current). */
export function stepKey(units: readonly { kind: string; id: string }[], current: string | null, step: 1 | -1): string | null {
	if (!units.length) return null;
	const i = current ? units.findIndex((u) => keyOf(u) === current) : -1;
	if (i < 0) return keyOf(units[step === 1 ? 0 : units.length - 1]);
	return keyOf(units[(i + step + units.length) % units.length]);
}

// ── escort proposals: open, answered, expired ───────────────────────────

export type EscortPhase = 'open' | 'answered' | 'expired';

/** An escort proposal's phase at `now`: answered here (final, locked) wins; past its deadline it expired (plan kept). */
export function escortPhase(u: Unit, now: number, answered: (approvalId: string) => boolean): EscortPhase {
	const p = escortOf(u).proposal;
	if (answered(p.approvalId)) return 'answered';
	if (u.deadline != null && u.deadline <= now) return 'expired';
	return 'open';
}

// ── the response options (DSS courses of action) ─────────────────────────

export interface Figure {
	value: string;
	/** A pack key for the line under the value. */
	labelKey: string;
}

/** The one figure an option shows (§7.6): time to the scene; else no units / no action. */
export function coaFigure(c: DssCoa): Figure {
	// watching is not an action: no clock for it, whatever the engine's time-to-effect says
	const monitor = c.actions.every((a) => a.verb === 'monitor');
	if (monitor) return { value: '—', labelKey: 'v3d_opt_no_action' };
	const sec = c.responseToSceneSec ?? c.etaToSceneSec;
	if (sec != null && Number.isFinite(sec) && sec > 0) return { value: fmtCountdown(sec), labelKey: 'v3d_opt_to_scene' };
	if (c.timeToEffectSec != null && Number.isFinite(c.timeToEffectSec) && c.timeToEffectSec > 0) return { value: fmtCountdown(c.timeToEffectSec), labelKey: 'v3d_opt_to_effect' };
	return { value: '—', labelKey: 'v3d_opt_no_units' };
}

/** The glyph of an option kind (the ride-type icon). */
export function coaGlyph(c: DssCoa): string {
	const verbs = new Set(c.actions.map((a) => a.verb));
	if (verbs.has('dispatch')) return 'ambulance';
	if (verbs.has('closure') || verbs.has('diversion')) return 'cone';
	if (verbs.has('request_cctv') || /verify/i.test(c.kind)) return 'search';
	if (verbs.has('advisory')) return 'megaphone';
	if (verbs.has('signal_hold')) return 'signal';
	return 'eye';
}

/** The V3 glyph of a sheet tag by what it names (a named map: the deck's glyph lint keeps kind names out of literals). */
export const TAG_GLYPH = { movement: 'route' } as const;

// ── the queue's timer line ──────────────────────────────────────────────

export interface When {
	text: string;
	/** The deadline is under a minute (or past): the line turns urgent. */
	urgent: boolean;
	/** A countdown (time-boxed or expiring), not a waiting time. */
	countdown: boolean;
}

/** "0:47 left" · "1 h 34 min left" · "waiting 14 min" (pack keys v3d_when_*). */
export function whenOf(u: Unit, now: number, lang: string, T: (key: string, ...a: unknown[]) => string): When {
	if (u.deadline != null && (UNIT_KINDS[u.kind]?.timeBoxed || u.kind === 'dss' || u.kind === 'corridor-request')) {
		const left = (u.deadline - now) / 1000;
		if (left <= 0) return { text: T('v3d_when_expired'), urgent: true, countdown: true };
		const v = left >= 3600 ? fmtDuration(left, lang) : fmtCountdown(left);
		return { text: T('v3d_when_left', v), urgent: left < 60, countdown: true };
	}
	const since = waitingSince(u);
	return { text: T('v3d_when_waiting', since != null ? fmtDuration((now - since) / 1000, lang) : '—'), urgent: false, countdown: false };
}

// ── the countdown ring ──────────────────────────────────────────────────

/** The ring's fill (1 → full, 0 → drained) for `leftSec` of a `totalSec` window. */
export function ringFraction(leftSec: number, totalSec: number | null | undefined): number {
	const total = totalSec && totalSec > 0 ? totalSec : 90;
	return Math.max(0, Math.min(1, leftSec / total));
}

/** The polite announcement thresholds (§7.7): once at 30 s and once at 10 s. */
export function announceAt(prevLeft: number | null, left: number): 30 | 10 | null {
	if (prevLeft == null) return null;
	if (prevLeft > 30 && left <= 30 && left > 10) return 30;
	if (prevLeft > 10 && left <= 10 && left > 0) return 10;
	return null;
}
