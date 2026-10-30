/**
 * The workspace's own object actions (SPEC §5.3 ObjectInspector): Show on
 * map, Search around, Add to graph, Explain, Copy link, Copy URN, Open in
 * table. None of them is a decision: decisions are made in exactly one home
 * per route (SPEC §5.4), and the inspector links there.
 *
 * Copy is ALWAYS masked (SPEC §7.5): a link carries URNs only (the
 * workspace keys plus `sel`), never a registration mark, whether or not an
 * officer is named; the copied text is checked before it is written.
 */
import { ACTION_ICON } from '$lib/design/icons';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.workspace';
import { selection } from '$lib/gods-eye/entities/selection.svelte';
import { toasts } from '$lib/shell/toast.svelte';
import { carriesRawMark } from './hash';
import type { ObjectAction, ObjectRow, View } from './types';
import { workspace } from './workspace.svelte';

export interface ActionContext {
	lang: string;
	/** The centre views the page composes (the graph and table actions need theirs). */
	views: readonly View[];
	/** Ask the inspector to explain the object (it streams the answer). */
	explain?: () => void;
}

/** Write `text` to the clipboard; false when the browser refuses. */
async function copy(text: string): Promise<boolean> {
	try {
		await navigator.clipboard.writeText(text);
		return true;
	} catch {
		return false;
	}
}

/** The masked link to `urn` on this page: the current hash (camera, layers) with the workspace keys and `sel`. */
export function linkTo(urn: string): string {
	const base = typeof location === 'undefined' ? '' : location.hash.replace(/^#/, '');
	const params = new URLSearchParams(base);
	params.set('sel', urn);
	const hash = workspace.toHash(params.toString());
	const origin = typeof location === 'undefined' ? '' : `${location.origin}${location.pathname}`;
	return `${origin}#${hash}`;
}

/** Choose a centre view that shows `want` (split keeps the map beside the graph). */
function viewFor(want: 'map' | 'graph' | 'table', views: readonly View[]): View | null {
	if (want === 'graph') return views.includes('split') ? 'split' : views.includes('graph') ? 'graph' : null;
	return views.includes(want) ? want : null;
}

/** The workspace actions for `row`, in the order the inspector lists them. */
export function workspaceActions(row: ObjectRow, ctx: ActionContext): ObjectAction[] {
	const L = (k: string, ...a: unknown[]) => t(ctx.lang, k, ...a);
	const graphView = viewFor('graph', ctx.views);
	const tableView = viewFor('table', ctx.views);
	const noGraph = L('ws_reason_no_graph');
	return [
		{
			id: 'ws.show-on-map',
			label: L('ws_act_show_on_map'),
			icon: ACTION_ICON.show_on_map,
			run() {
				selection.select(row.urn, { fly: true, source: 'dossier', mode: selection.has(row.urn) && selection.items.length > 1 ? 'add' : 'replace' });
				const v = viewFor('map', ctx.views);
				if (v && workspace.view !== 'split') workspace.view = v;
			},
		},
		{
			id: 'ws.search-around',
			label: L('ws_act_search_around'),
			icon: ACTION_ICON.search_around,
			disabled: !graphView,
			disabledReason: graphView ? undefined : noGraph,
			run() {
				if (graphView) workspace.view = graphView;
			},
		},
		{
			id: 'ws.add-to-graph',
			label: L('ws_act_add_to_graph'),
			icon: ACTION_ICON.add_to_graph,
			disabled: !graphView,
			disabledReason: graphView ? undefined : noGraph,
			run() {
				selection.select(row.urn, { source: 'graph', mode: 'add' });
				if (graphView) workspace.view = graphView;
			},
		},
		{
			id: 'ws.explain',
			label: L('ws_act_explain'),
			icon: ACTION_ICON.explain,
			disabled: !ctx.explain,
			run() {
				ctx.explain?.();
			},
		},
		{
			id: 'ws.copy-link',
			label: L('ws_act_copy_link'),
			icon: 'link',
			async run() {
				const link = linkTo(row.urn);
				// defence in depth: a link never carries a registration mark (C6) — and the operator is told nothing was copied
				if (carriesRawMark(link)) {
					toasts.push({ kind: 'error', title: L('ws_toast_link_refused') });
					return;
				}
				const ok = await copy(link);
				toasts.push({ kind: ok ? 'info' : 'error', title: L(ok ? 'ws_toast_link_copied' : 'ws_toast_copy_failed') });
			},
		},
		{
			id: 'ws.copy-urn',
			label: L('ws_act_copy_urn'),
			icon: 'duplicate',
			async run() {
				const ok = await copy(row.urn);
				toasts.push({ kind: ok ? 'info' : 'error', title: L(ok ? 'ws_toast_urn_copied' : 'ws_toast_copy_failed') });
			},
		},
		{
			id: 'ws.open-in-table',
			label: L('ws_act_open_in_table'),
			icon: 'th',
			disabled: !tableView,
			disabledReason: tableView ? undefined : L('ws_reason_no_table'),
			run() {
				selection.select(row.urn, { source: 'table' });
				if (tableView) workspace.view = tableView;
			},
		},
	];
}
