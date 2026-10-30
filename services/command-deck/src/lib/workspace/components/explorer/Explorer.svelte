<script lang="ts">
	/**
	 * Explorer (SPEC §5.3, §6.1) — the left dock's first tab: what the city
	 * holds and the views an analyst keeps.
	 *
	 *   Active events   the `activeEvents` snippet (the page fills it with
	 *                   ActiveEvents, `active-events`); absent without one
	 *   Object types    every kind with count(kind) — THE registry count, the
	 *                   same figure as the layer tree and the vitals card —
	 *                   and one state word ("2 open", "6 pending", "on
	 *                   watchlist"); a kind the registry holds without an
	 *                   adapter (an open-source report, a place) appears too.
	 *                   A kind with nothing is dimmed. Picking a kind calls
	 *                   onSelectKind; without one, the table explores it (a
	 *                   kind filter and the table view; picking it again
	 *                   lifts the filter)
	 *   Saved views     SavedViews.svelte (masked, this browser)
	 *   Watches         Watches.svelte (titles only; "Decision needed" is
	 *                   decisionUnits())
	 *
	 * The dock's own header carries the title "Explorer".
	 */
	import type { Snippet } from 'svelte';
	import { kindIcon } from '$lib/design/icons';
	import { Section, Tag, Tree, provideUiLang, type TreeNode } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.views';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { kindOne } from '../../kinds/generic';
	import { liveWorld, selectors } from '../../world.svelte';
	import { workspace } from '../../workspace.svelte';
	import { explorerKinds, exploredKind } from './model';
	import SavedViews from './SavedViews.svelte';
	import Watches from './Watches.svelte';

	let { activeEvents, onSelectKind }: { activeEvents?: Snippet; onSelectKind?: (kind: string) => void } = $props();

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	let eventsOpen = $state(true);
	let typesOpen = $state(true);

	const kinds = $derived(explorerKinds(liveWorld.registry(), (k) => selectors.count(k), lang));
	const total = $derived(kinds.reduce((n, k) => n + k.n, 0));
	const explored = $derived(exploredKind(workspace.filters));
	const counts = $derived(new Map(kinds.map((k) => [k.kind, k.n])));

	const nodes = $derived<TreeNode[]>(
		kinds.map((k) => ({
			id: k.kind,
			label: k.label,
			icon: kindIcon(k.kind),
			secondaryLabel: k.word,
			dim: k.n === 0,
			selected: explored === k.kind,
			attrs: { 'data-kind': k.kind, 'data-count': String(k.n) },
		})),
	);

	/** Explore a kind in the table: one kind filter (replacing any other), the table view; again lifts it. */
	function exploreKind(kind: string) {
		const again = explored === kind;
		for (const f of workspace.filters) if (f.field === 'kind') workspace.removeFilter(f.id);
		if (again) return;
		workspace.addFilter({ field: 'kind', values: [kind], label: kindOne(kind, lang) });
		workspace.view = 'table';
	}

	function pick(node: TreeNode) {
		if (onSelectKind) onSelectKind(node.id);
		else exploreKind(node.id);
	}
</script>

{#snippet countEnd(node: TreeNode)}
	<Tag round data-testid="explorer-count">{counts.get(node.id) ?? 0}</Tag>
{/snippet}

<div class="explorer" data-testid="explorer">
	{#if activeEvents}
		<Section title={L('vw_ex_active_events')} collapsible bind:open={eventsOpen} data-explorer-section="active-events">
			<div class="slot">{@render activeEvents()}</div>
		</Section>
	{/if}
	<Section title={L('vw_ex_object_types')} sub={total} collapsible bind:open={typesOpen} data-explorer-section="object-types">
		<Tree class="types" {nodes} onnodeclick={pick} end={countEnd} label={L('vw_ex_object_types')} data-testid="explorer-kinds" />
		{#if total === 0}<p class="empty">{L('vw_ex_none')}</p>{/if}
	</Section>
	<SavedViews {lang} />
	<Watches {lang} />
</div>

<style>
	.explorer {
		display: flex;
		flex-direction: column;
		min-width: 0;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.slot {
		padding: 0 0 4px;
	}

	.explorer :global(.types) {
		padding: 0 0 4px;
	}

	/* leaf rows: the glyph lines up with the other lists' (16 px), not behind an empty 30 px caret box */
	.explorer :global(.types .caret.none) {
		width: 16px;
	}

	.empty {
		margin: 0;
		padding: 0 16px 12px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}
</style>
