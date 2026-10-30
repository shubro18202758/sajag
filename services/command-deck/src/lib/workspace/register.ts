/**
 * The workspace's own provider: the Inspector, the right dock's tab for the
 * selected object (SPEC §6.1). Registered like every other provider, so a
 * frame with no provider registered at all shows its non-ideal state.
 */
import { registerRightTab } from './registry';
import LazyInspectorTab from './components/inspector/LazyInspectorTab.svelte';
import { prefetchInspector } from './components/inspector/load';

export function register(): void {
	registerRightTab({ id: 'inspector', label: 'ws_tab_inspector', icon: 'properties', component: LazyInspectorTab, order: 20, prefetch: prefetchInspector });
}
