<script lang="ts">
	/**
	 * PursuitPanel — kept as a thin wrapper (UI-S5A) so today's pages keep
	 * working (EventDossierDrawer mounts it for a selected pursuit). It
	 * renders the decisions provider's pursuit plan (decisions/sections/
	 * PursuitPlan: the ranked chokes, `pursuit-sighting[data-stale]`,
	 * `pursuit-choke`, "Request unit") for the selected pursuit event — or,
	 * while a selected vehicle's open pursuit is followed, for that pursuit.
	 * The rebuilt pages show the same plan as the inspector's Pursuit section.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { NonIdealState } from '$lib/ui';
	import { eventKindIcon } from '$lib/design/icons';
	import { tOps } from '$lib/i18n/strings.ops';
	import PursuitPlan from '$lib/decisions/sections/PursuitPlan.svelte';

	const lang = $derived(ops.lang);
	const ev = $derived.by(() => {
		const sel = ops.selectedEvent;
		if (sel?.eventKind === 'vehicle_pursuit') return sel;
		const planEvent = ops.interception ? ops.eventById(ops.interception.eventId) : null;
		return planEvent ?? (ops.planEventId ? ops.eventById(ops.planEventId) : null);
	});
</script>

<div class="pursuit-panel" data-prim="panel">
	{#if ev}
		<PursuitPlan eventId={ev.eventId} {lang} />
	{:else}
		<NonIdealState icon={eventKindIcon('vehicle_pursuit')} iconSize={32} title={ops.interceptionNote ?? tOps(lang, 'pursuitNoneForEvent')} />
	{/if}
</div>

<style>
	.pursuit-panel {
		min-width: 0;
		background: var(--v-surface-1);
		border-radius: var(--v-radius-panel);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}
</style>
