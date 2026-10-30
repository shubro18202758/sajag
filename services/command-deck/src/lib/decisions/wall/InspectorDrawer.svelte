<script lang="ts">
	/**
	 * The wall's inspector drawer (SPEC §6.3): the workspace's ObjectInspector
	 * for the selected object, 400 px wide on the right. On a wall at least
	 * 1680 px wide it docks beside the three columns (the grid gives it a
	 * track, so nothing on the wall is covered); narrower, it slides over the
	 * right column and is non-modal (no backdrop: the wall stays usable).
	 * The inspector's own close (✕) closes the drawer, wherever the object
	 * it shows came from (a row the operator picked, or the wall's selected
	 * event).
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.workspace';
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';
	import { loadObjectInspector } from '$lib/workspace/components/inspector/load';

	interface Props {
		urn: string;
		/** Docked in the grid (≥ 1680 px) or over the right column. */
		docked: boolean;
		lang: string;
		onclose: () => void;
	}

	let { urn, docked, lang, onclose }: Props = $props();

	/** The inspector's ✕ (it clears the selection itself; the drawer must close too). */
	function onClickCapture(e: MouseEvent) {
		const btn = (e.target as Element | null)?.closest?.('button');
		if (btn && btn.getAttribute('aria-label') === t(lang, 'ws_insp_close')) onclose();
	}
</script>

<aside class="drawer" class:docked data-wall="inspector" data-docked={docked ? 'true' : 'false'} aria-label={t(lang, 'ws_tab_inspector')} onclickcapture={onClickCapture}>
	<LazyMount load={loadObjectInspector} {urn} />
</aside>

<style>
	.drawer {
		display: flex;
		flex-direction: column;
		width: 400px;
		min-width: 0;
		min-height: 0;
		overflow-x: hidden;
		overflow-y: auto;
		background: var(--v-surface-1);
		border-left: 1px solid var(--v-line-2);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		scrollbar-width: thin;
	}

	.drawer:not(.docked) {
		position: absolute;
		top: 0;
		right: 0;
		bottom: 0;
		z-index: 6;
		box-shadow: var(--v-elev-3);
	}

	.drawer > :global([data-testid='entity-dossier']) {
		flex: 1 0 auto;
	}
</style>
