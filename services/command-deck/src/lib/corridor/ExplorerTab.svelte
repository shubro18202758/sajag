<script lang="ts">
	/**
	 * The corridor workspace's Explorer tab (SPEC §6.1): the S2X Explorer
	 * with the corridor's Active events in its `activeEvents` snippet. The
	 * registry mounts tab components bare (no props), so the snippet needs
	 * this one-wrapper; S2X's Explorer stays untouched.
	 */
	import Explorer from '$lib/workspace/components/explorer/Explorer.svelte';
	import ActiveEvents from './ActiveEvents.svelte';
</script>

<Explorer>
	{#snippet activeEvents()}
		<ActiveEvents />
	{/snippet}
</Explorer>
