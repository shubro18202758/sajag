/**
 * The OSINT provider (OS-DECK-A; plan R1, R27): registers the reported
 * situations and places into the redesigned workspace — never into
 * src/lib/ops/components/. `registerProviders()` (workspace/providers.ts)
 * calls `register()` once per page; every call carries its id, so a second
 * call replaces only its own entries (idempotent; HMR-safe).
 *
 *   sections  'osint-report' for `osint_event` (order 10): the report —
 *             situation, verification, location, sources, live state
 *             (model.ts, rendered through the inspector's PropertyGroups)
 *             'osint-place' for `place` (order 10): the gazetteer place
 *   actions   'osint.map' for `osint_event` (order 10): the three
 *             NON-decision actions (show on map, search around the place,
 *             open the source list). Promote and decision support are
 *             decisions: OS-DECK-B registers them for the same kind under
 *             its own id in this wave, and both appear (plan R27).
 *
 * The omnibar, table, histogram, graph and timeline already carry OSINT
 * objects through the generic adapter (UI-S2, X5) and the lane mapping
 * (UI-S4, X8); this provider adds only presentation. No new polled GET:
 * everything reads the city snapshot and the dossier the selection loads
 * anyway (plan X13).
 */
import { registerActions, registerInspectorSection } from '$lib/workspace/registry';
import type { Component } from 'svelte';
import type { InspectorSectionProps } from '$lib/workspace/types';
import { ops } from '$lib/ops/store.svelte';
import { osintActions } from './actions';
import LazyOsintReportSection from './LazyOsintReportSection.svelte';
import LazyPlaceSection from './LazyPlaceSection.svelte';
import '$lib/i18n/packs.osint';

const report = LazyOsintReportSection as unknown as Component<InspectorSectionProps>;
const place = LazyPlaceSection as unknown as Component<InspectorSectionProps>;

export function register(): void {
	registerInspectorSection('osint_event', report, { id: 'osint-report', order: 10 });
	registerInspectorSection('place', place, { id: 'osint-place', order: 10 });
	registerActions('osint_event', (row) => osintActions(row, ops.lang), { id: 'osint.map', order: 10 });
}
