/**
 * The decision-support provider (plan X22, R27) — the section and the
 * promote action for the OSINT surfaces. `registerProviders()`
 * (workspace/providers.ts) calls `register()` once per page via Vite's
 * eager glob over each provider's register.ts; every call carries its id,
 * so a second call replaces its own entries and never another provider's
 * (OS-DECK-A adds `osint.map` for the same kind in this wave).
 *
 *   sections  'dss' for `osint_event` and `event` (order 20 — UI-S5A's
 *             Pursuit section stays at 10 on `event`): the "Decision
 *             support" link card to the proposal's ONE approval home.
 *             `ownsUnitKinds: ['dss']` keeps the inspector's Actions tab
 *             from adding its own link card, so an object carries exactly
 *             one link per DSS (this section's `dss-link`).
 *   actions   'dss.promote' for `osint_event` (order 20): the officer-gated
 *             Promote verb (the dialog lives in the section).
 */
import { registerActions, registerInspectorSection } from '$lib/workspace/registry';
import type { InspectorSectionProps } from '$lib/workspace/types';
import type { Component } from 'svelte';
import LazyDecisionSupportSection from './LazyDecisionSupportSection.svelte';
import { promoteActions } from './promote';

export function register(): void {
	const section = LazyDecisionSupportSection as unknown as Component<InspectorSectionProps>;
	registerInspectorSection('osint_event', section, { id: 'dss', order: 20, ownsUnitKinds: ['dss'] });
	registerInspectorSection('event', section, { id: 'dss', order: 20, ownsUnitKinds: ['dss'] });
	registerActions('osint_event', promoteActions, { id: 'dss.promote', order: 20 });
}
