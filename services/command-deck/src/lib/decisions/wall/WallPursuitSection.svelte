<script lang="ts">
	/**
	 * Bridge section (UI-S5B, wave C): until UI-S5A's PursuitSection is
	 * registered for events (decisions/register.ts, id 'pursuit'), the wall's
	 * inspector shows the selected pursuit's interception plan through
	 * today's PursuitPanel — the plan `pursuit-sighting` lives in, which the
	 * retired EventDossierDrawer used to mount on /ops. pursuit-bridge.ts
	 * registers this only when no 'pursuit' section exists, under the same id,
	 * so UI-S5A's section replaces it and the two never render together.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import PursuitPanel from '$lib/ops/components/PursuitPanel.svelte';
	import type { InspectorSectionProps } from '$lib/workspace/types';

	let { row }: InspectorSectionProps = $props();

	/** The plan the store follows is the selected event's: show it only on that event, and only for a pursuit. */
	const shown = $derived(
		row.kind === 'event' &&
			row.urn === `event:${ops.selectedEventId ?? ''}` &&
			ops.selectedEvent?.eventKind === 'vehicle_pursuit',
	);
</script>

{#if shown}
	<div class="bridge"><PursuitPanel /></div>
{/if}

<style>
	.bridge {
		padding: 8px 16px 12px;
		border-bottom: 1px solid var(--v-line-2);
	}
</style>
