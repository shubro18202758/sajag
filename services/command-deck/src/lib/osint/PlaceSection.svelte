<script lang="ts">
	/**
	 * The inspector's place section (OS-DECK-A; registered for `place` by
	 * osint/register.ts, id 'osint-place', order 10). A gazetteer place a
	 * surfaced situation is reported at: the canonical name, the feature
	 * type, the gazetteer's own surface forms (EN + MR), its road and
	 * junction, and the count of linked reported situations. A place is a
	 * PLACE: it carries no verification of its own and no person anywhere.
	 */
	import type { InspectorSectionProps } from '$lib/workspace/types';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.osint';
	import { shellClock, useShellClock } from '$lib/shell/clock.svelte';
	import PropertyGroups from '$lib/workspace/components/inspector/PropertyGroups.svelte';
	import { placeView, readPlace } from './model';

	let { row, dossier }: InspectorSectionProps = $props();

	useShellClock();
	const lang = $derived(ops.lang);
	const now = $derived(shellClock.now);
	const view = $derived(placeView(readPlace(row.props), dossier, (key, ...args) => t(lang, key, ...args)));

	function select(urn: string) {
		selection.select(urn, { source: 'dossier' });
	}
</script>

<section class="place" data-testid="osint-place" data-kind="place">
	{#if view.rows.length}
		<PropertyGroups groups={[{ title: view.title, rows: view.rows }]} {now} onselect={select} />
	{/if}
</section>

<style>
	/* the section renders INSIDE the inspector's Properties tab now (fix round 2, item 7):
	   the tab body already carries the console gutter, so the section pads vertically only */
	.place {
		display: flex;
		flex-direction: column;
		padding: 4px 0 8px;
		border-bottom: 1px solid var(--v-line-2);
	}
</style>
