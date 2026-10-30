<script lang="ts">
	/**
	 * EventLifecycleVerbs — kept as a thin wrapper (UI-S5A) over the
	 * decisions provider's lifecycle rail (decisions/sections/LifecycleVerbs:
	 * the C-F verbs from the server's transition table, one POST per click
	 * under the named officer, Cancel with its inline confirmation, the
	 * `event-outcome` line). The same logic is registered as the `event`
	 * lifecycle action of the inspector (decisions/register.ts). Props are
	 * today's.
	 */
	import type { CorridorEvent } from '$lib/ops/types';
	import LifecycleVerbs from '$lib/decisions/sections/LifecycleVerbs.svelte';

	let { event, compact = false }: { event: CorridorEvent; compact?: boolean } = $props();
</script>

<LifecycleVerbs {event} {compact} />
