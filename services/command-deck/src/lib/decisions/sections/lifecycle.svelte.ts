/**
 * The event lifecycle action (SPEC §12.2 EventLifecycleVerbs row: "event
 * lifecycle action, registered into the inspector and row menu"; plan X6):
 * the C-F verbs the server's transition table allows from the event's RAW
 * status — Approve, Activate, Complete, Cancel — as ObjectActions for the
 * `event` kind (decisions/register.ts, id 'decisions.lifecycle', order 10;
 * other providers add their own `event` actions under other ids).
 *
 * Every verb is a city-writer commit under the named duty officer (the
 * store's transitionEvent → POST /api/v1/events/{id}/status), one POST at a
 * time (ops.eventBusy). Cancel keeps today's two-step confirmation: the
 * first run arms it ("Confirm cancel" for 8 s, then the label reverts),
 * the second sends it. The
 * outcome is a toast (outcomes only) and the board card's inline
 * `event-outcome` line. These are officer actions, not decisions: no
 * proposal waits on them.
 */
import { ops, eventVerbs } from '$lib/ops/store.svelte';
import { toasts } from '$lib/shell/toast.svelte';
import { tOps } from '$lib/i18n/strings.ops';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.decisions';
import { istClock } from '$lib/ops/format';
import type { IconName } from '$lib/design/icons';
import type { ObjectAction, ObjectRow } from '$lib/workspace/types';
import type { EventTransitionTarget } from '$lib/ops/types';

/**
 * The cancel verb armed for one event (the second run within ARM_MS sends
 * it). A timer disarms it after ARM_MS, so the "Confirm cancel" label goes
 * back to "Cancel this event" on screen — a click after that arms again,
 * and the label says so.
 */
export const lifecycleArm = $state<{ eventId: string | null; at: number }>({ eventId: null, at: 0 });
export const ARM_MS = 8000;
let disarmTimer: ReturnType<typeof setTimeout> | null = null;

function arm(eventId: string) {
	const at = Date.now();
	lifecycleArm.eventId = eventId;
	lifecycleArm.at = at;
	if (disarmTimer) clearTimeout(disarmTimer);
	disarmTimer = setTimeout(() => {
		disarmTimer = null;
		if (lifecycleArm.eventId === eventId && lifecycleArm.at === at) lifecycleArm.eventId = null;
	}, ARM_MS);
}

function disarm() {
	if (disarmTimer) clearTimeout(disarmTimer);
	disarmTimer = null;
	lifecycleArm.eventId = null;
}

const ICON: Record<EventTransitionTarget, IconName> = {
	approved: 'endorsed',
	active: 'play',
	completed: 'tick-circle',
	cancelled: 'ban-circle',
};

/** The outcome line of the store's last transition, in this console's language. */
export function outcomeText(lang: string): string | null {
	const o = ops.eventOutcome;
	if (!o) return null;
	const DONE: Record<EventTransitionTarget, string> = {
		approved: 'lifecycleApproved',
		active: 'lifecycleActivated',
		completed: 'lifecycleCompleted',
		cancelled: 'lifecycleCancelled',
	};
	if (o.ok) return tOps(lang, DONE[o.toStatus], o.actor ?? ops.dutyOfficer, istClock(o.at ?? o.when));
	return `${tOps(lang, 'lifecycleRefused', o.status || '—', ops.text(o.detail))}${o.allowed ? ` · ${tOps(lang, 'lifecycleAllowed', o.allowed.length ? o.allowed.join(' | ') : '—')}` : ''}`;
}

/** Run one verb (the cancel verb arms first unless `confirmed`). True when the POST succeeded. */
export async function runLifecycle(eventId: string, to: EventTransitionTarget, note = '', confirmed = false): Promise<boolean> {
	if (to === 'cancelled' && !confirmed) {
		const armed = lifecycleArm.eventId === eventId && Date.now() - lifecycleArm.at < ARM_MS;
		if (!armed) {
			arm(eventId);
			return false;
		}
	}
	disarm();
	const ok = await ops.transitionEvent(eventId, to, note);
	const text = outcomeText(ops.lang);
	if (text) toasts.push({ kind: ok ? 'act' : 'error', title: text });
	return ok;
}

/** The lifecycle actions of an event row (none for other kinds or for events without a C-F lifecycle). */
export function lifecycleActions(row: ObjectRow): readonly ObjectAction[] {
	if (row.kind !== 'event') return [];
	const ev = ops.eventById(row.id);
	const verbs = eventVerbs(ev);
	if (!ev || !verbs.length) return [];
	const lang = ops.lang;
	const busy = ops.eventBusy !== null;
	const armed = lifecycleArm.eventId === ev.eventId && Date.now() - lifecycleArm.at < ARM_MS;
	return verbs.map((to): ObjectAction => {
		const block = !ops.officerOn ? tOps(lang, 'lifecycleNeedsOfficer') : busy ? t(lang, 'dec_reason_busy') : null;
		return {
			id: `decisions.lifecycle.${to}`,
			label: to === 'cancelled' && armed ? tOps(lang, 'verbConfirmCancel') : t(lang, `dec_life_${to}`),
			icon: ICON[to],
			...(to === 'cancelled' ? { intent: 'danger' as const } : {}),
			disabled: !!block,
			...(block ? { disabledReason: block } : {}),
			run: () => void runLifecycle(ev.eventId, to, '', false),
		};
	});
}
