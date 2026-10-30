<script lang="ts">
	/**
	 * /comms leaves the (deck) layout (`@` = reset to the root layout) and wears the V3 shell itself — see
	 * $lib/v3/comms/CommsFrame.svelte for why and for how this file goes away when the route joins the (v3) group.
	 */
	import CommsFrame from '$lib/v3/comms/CommsFrame.svelte';

	let { children } = $props();
</script>

<CommsFrame>
	{@render children?.()}
</CommsFrame>
