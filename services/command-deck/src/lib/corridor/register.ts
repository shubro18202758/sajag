/**
 * The corridor provider (SPEC §5.3, §6.1, §6.2; plan X6, R9, R27) — the
 * route pages' tabs for the corridor workspace and map mode.
 *
 *   left tabs (on /)    Explorer (S2X) · Layers (S3's LayerTree) ·
 *                       Histogram (S2X) · Plan (PlanPanel, this provider)
 *   left tab (map mode) Info (the full City vitals; the card variant is the
 *                       map's overlay, one variant mounted at a time)
 *   right tab           Movement (ConvoyCard) — the default while a movement
 *                       is live, and the home of escort proposals
 *
 * The bottom dock's tabs are the analysis provider's; the Inbox and the
 * inspector register their own right tabs. Idempotent: every registration
 * is keyed by id (plan R27), so a second registerProviders() replaces its
 * own entries and never another provider's.
 *
 * Every tab is a LAZY wrapper (corridor/lazy/*, plan R9's budget escape
 * hatch): the route's eager graph carries only this registry — each real
 * panel loads on its tab's first open.
 */
import { registerLeftTab, registerRightTab } from '$lib/workspace/registry';
import { KIND_ICON } from '$lib/design/icons';
import LazyExplorerTab from './lazy/LazyExplorerTab.svelte';
import LazyLayerTreeTab from './lazy/LazyLayerTreeTab.svelte';
import LazyHistogramTab from './lazy/LazyHistogramTab.svelte';
import LazyPlanTab from './lazy/LazyPlanTab.svelte';
import LazyInfoTab from './lazy/LazyInfoTab.svelte';
import LazyMovementTab from './lazy/LazyMovementTab.svelte';

export function register(): void {
	// the corridor workspace's left dock (SPEC §6.1); only on /
	registerLeftTab({ id: 'explorer', label: 'vw_tab_explorer', icon: 'diagram-tree', component: LazyExplorerTab, order: 10, when: (ctx) => ctx.route === '/' });
	registerLeftTab({ id: 'layers', label: 'cor_tab_layers', icon: 'layers', component: LazyLayerTreeTab, order: 20, when: (ctx) => ctx.route === '/' });
	registerLeftTab({ id: 'histogram', label: 'vw_tab_histogram', icon: 'horizontal-bar-chart', component: LazyHistogramTab, order: 30, when: (ctx) => ctx.route === '/' });
	registerLeftTab({ id: 'plan', label: 'cor_tab_plan', icon: KIND_ICON.convoy, component: LazyPlanTab, order: 40, when: (ctx) => ctx.route === '/' });
	// map mode's Info tab (the full vitals; SPEC §6.2)
	registerLeftTab({ id: 'info', label: 'vw_tab_info', icon: 'info-sign', component: LazyInfoTab, order: 50, when: (ctx) => ctx.route === '/gods-eye' });
	// the Movement tab: the default right dock tab while a movement is live
	registerRightTab({
		id: 'movement',
		label: 'cor_tab_movement',
		icon: KIND_ICON.convoy,
		component: LazyMovementTab,
		order: 10,
		when: (ctx) => ctx.live.movement,
	});
}
