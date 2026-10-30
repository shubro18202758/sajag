/**
 * The decisions provider (SPEC §5.3, §5.4, §14.2 S5; plan X6, R9, R27).
 * `registerProviders()` (workspace/providers.ts) calls `register()` once per
 * page; every call carries its id, so a second call replaces its own entries
 * and never another provider's (OS-DECK-B adds `event` and `osint_event`
 * sections and actions under its own ids in wave D).
 *
 *   right tab   'inbox' — the Inbox, on / and /gods-eye (on /ops the
 *               decisions' home is the Decisions column)
 *   sections    'pursuit' for `vehicle` and `event` (order 10): the Pursuit
 *               section, shown for a vehicle with an open pursuit and for
 *               the pursuit event
 *               'decisions.links' for recommendation, vehicle, event,
 *               dispatch and junction (order 20): a link card to the home
 *               of each unit whose decision touches the object while its
 *               subject is another (a stolen vehicle's pending sighting,
 *               opened on its own) — never a verb
 *   actions     'decisions.lifecycle' for `event` (order 10): the C-F verbs
 *   units       'decisions': every decision unit as a DecisionUnitSummary,
 *               so selectors.decisionUnits() counts units everywhere — the
 *               navbar, the Inbox tab, the /ops metric, Watches, the strip.
 *               Recommendations, dispatches and vehicles get their link card
 *               to the home through the unit's subject URN (the inspector's
 *               Actions tab), never a second Approve.
 *
 * In the browser it also starts the follow sync (sections/follow): a
 * selected vehicle's open pursuit plan loads and polls.
 */
import { registerActions, registerDecisionUnits, registerInspectorSection, registerRightTab } from '$lib/workspace/registry';
import type { DecisionUnitSummary, InspectorSectionProps } from '$lib/workspace/types';
import type { Component } from 'svelte';
import { ACTION_ICON } from '$lib/design/icons';
import { decisionUnits } from './units';
import { homeOf } from './homes';
import LazyInbox from './LazyInbox.svelte';
import LazyPursuitSection from './sections/LazyPursuitSection.svelte';
import LazyDecisionLinks from './sections/LazyDecisionLinks.svelte';
import { LINK_KINDS } from './sections/links';
import { lifecycleActions } from './sections/lifecycle.svelte';
import { startFollow } from './sections/follow.svelte';

/** Every decision unit as the registry's summary (masked titles; one home per route). */
export function decisionUnitSummaries(): DecisionUnitSummary[] {
	return decisionUnits().map((u) => ({
		kind: u.kind,
		id: u.id,
		subjectUrn: u.subjectUrn,
		title: u.title,
		deadline: u.deadline,
		severity: u.severity,
		homes: { '/': homeOf(u.kind, '/'), '/gods-eye': homeOf(u.kind, '/gods-eye'), '/ops': homeOf(u.kind, '/ops') },
	}));
}

export function register(): void {
	registerRightTab({
		id: 'inbox',
		label: 'dec_tab_inbox',
		icon: ACTION_ICON.inbox,
		component: LazyInbox,
		order: 30,
		when: (ctx) => ctx.route === '/' || ctx.route === '/gods-eye',
	});
	const section = LazyPursuitSection as unknown as Component<InspectorSectionProps>;
	registerInspectorSection('vehicle', section, { id: 'pursuit', order: 10 });
	registerInspectorSection('event', section, { id: 'pursuit', order: 10 });
	const links = LazyDecisionLinks as unknown as Component<InspectorSectionProps>;
	for (const kind of LINK_KINDS) registerInspectorSection(kind, links, { id: 'decisions.links', order: 20 });
	registerActions('event', lifecycleActions, { id: 'decisions.lifecycle', order: 10 });
	registerDecisionUnits(decisionUnitSummaries, { id: 'decisions' });
	startFollow();
}
