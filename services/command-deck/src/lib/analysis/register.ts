/**
 * The analysis provider (SPEC §5.3, plan X6): registers into the workspace
 * frame — never imported by it.
 *
 *   bottom tabs   Timeline · Audit · AI trace (the analysis dock's tab
 *                 variant: the frame draws the tabs and owns the size)
 *   activity      the inspector's activity strip (the object's rows over the
 *                 last 6 h, "Show in the timeline")
 *   object source the event history (GET /events?limit=200, once a minute):
 *                 events known only from history — a closed pursuit, a
 *                 completed movement — are objects of the graph, the table
 *                 and the inspector
 *
 * The Graph VIEW is composed by the route (UI-S6A), which imports LinkGraph.
 * Every tab and the activity strip is a LAZY wrapper (plan R9's budget
 * escape hatch): the route's eager graph carries only this registry — each
 * real panel loads on its first mount, and on /ops (no frame) never loads
 * at all. Idempotent: every registration is keyed by id (plan R27).
 */
import { registerActivityRenderer, registerBottomTab, registerObjectSource } from '$lib/workspace/registry';
import { eventRow } from '$lib/workspace/kinds';
import type { InspectorSectionProps, ObjectRow } from '$lib/workspace/types';
import type { Component } from 'svelte';
// the tab labels render before any panel mounts (t() is not reactive to a
// late pack), so this pack rides registration while the panels stay lazy
import '$lib/i18n/packs.analysis';
import LazyActivityStrip from './dock/LazyActivityStrip.svelte';
import LazyTimelineTab from './dock/LazyTimelineTab.svelte';
import LazyAuditTab from './dock/LazyAuditTab.svelte';
import LazyAiTraceTab from './dock/LazyAiTraceTab.svelte';
import { eventHistory } from './history.svelte';

/** The event history as object rows (masked at parse; the adapter masks the title again). */
export function historyRows(): readonly ObjectRow[] {
	const out: ObjectRow[] = [];
	for (const r of eventHistory.rows) {
		const row = eventRow(r.raw);
		if (row) out.push(row);
	}
	return out;
}

export function register(): void {
	registerBottomTab({ id: 'timeline', label: 'an_tab_timeline', icon: 'timeline-bar-chart', component: LazyTimelineTab, order: 10 });
	registerBottomTab({ id: 'audit', label: 'an_tab_audit', icon: 'history', component: LazyAuditTab, order: 20 });
	registerBottomTab({ id: 'ai', label: 'an_tab_ai', icon: 'predictive-analysis', component: LazyAiTraceTab, order: 30 });
	registerActivityRenderer(LazyActivityStrip as unknown as Component<InspectorSectionProps>, { id: 'analysis:activity-strip', order: 10 });
	registerObjectSource(historyRows, { id: 'analysis:event-history' });
}
