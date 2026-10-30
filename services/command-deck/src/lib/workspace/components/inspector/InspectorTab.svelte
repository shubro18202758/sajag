<script lang="ts">
	/**
	 * The right dock's Inspector tab: the ObjectInspector for the primary
	 * selection, or an empty state that says what to do. The inspector's
	 * module loads with the first selection (FIX-E-PERF2): a cold `/` shows
	 * this tab's empty state for a moment before the Inbox takes the dock,
	 * and that moment no longer downloads the whole inspector. The operator's
	 * first press prefetches it (TabSpec.prefetch), so the first pick does
	 * not wait on it.
	 */
	import { NonIdealState } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.workspace';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import LazyMount from '../lazy/LazyMount.svelte';
	import { loadObjectInspector } from './load';

	const lang = $derived(commandBar.lang);
</script>

{#if selection.current}
	<LazyMount load={loadObjectInspector} />
{:else}
	<div class="none">
		<NonIdealState icon="select" iconSize={48} title={t(lang, 'ws_insp_none')} description={t(lang, 'ws_insp_none_hint')} />
	</div>
{/if}

<style>
	.none {
		padding: 80px 24px 24px;
	}
</style>
