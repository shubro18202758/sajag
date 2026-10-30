<script lang="ts">
	/**
	 * The inspector's Pursuit section (SPEC §5.3 ObjectInspector; plan X6:
	 * registered for `vehicle` and `event` by decisions/register.ts, id
	 * 'pursuit', order 10). A vehicle shows it while it has an open pursuit
	 * (ops.pursuitFor); a vehicle_pursuit event shows its own plan. Any other
	 * object renders nothing. Props are the registry's {row, dossier}.
	 */
	import type { InspectorSectionProps } from '$lib/workspace/types';
	import { ops } from '$lib/ops/store.svelte';
	import PursuitPlan from './PursuitPlan.svelte';

	let { row }: InspectorSectionProps = $props();

	const eventId = $derived(row.kind === 'event' && ops.eventById(row.id)?.eventKind === 'vehicle_pursuit' ? row.id : null);
	const vehicleId = $derived(row.kind === 'vehicle' ? row.id : null);
</script>

{#if eventId}
	<PursuitPlan {eventId} />
{:else if vehicleId && ops.pursuitFor(vehicleId)}
	<PursuitPlan {vehicleId} />
{/if}
