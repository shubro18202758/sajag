/**
 * The inspector's deferred modules (FIX-E-PERF2: the inspector loads with the
 * first selection, never on a cold load). The loaders are module-level, so
 * every mount passes LazyMount the SAME function: a dock tab switch or a
 * {#if} toggle that remounts the panel renders the already-loaded module in
 * the same frame (no spinner frame, no second fetch).
 *
 * `prefetchInspector` is the inspector tab's registered `prefetch`
 * (TabSpec.prefetch): the workspace frame calls it on the operator's FIRST
 * press (pointer or key), so the first selection finds the inspector loaded
 * — the omnibar's first-use rule. An interaction-free cold load fetches
 * neither module.
 */
export const loadInspectorTab = () => import('./InspectorTab.svelte');
export const loadObjectInspector = () => import('./ObjectInspector.svelte');
export const prefetchInspector = (): Promise<unknown> => Promise.all([loadInspectorTab(), loadObjectInspector()]);
