<script lang="ts">
	/**
	 * /decide/<kind>:<id> — the deep link to one decision unit (V3-SPEC §3.2, §6.2). The key is the unit's
	 * kind and id only (decisions/homes.ts unitKey — never a mark); a hostile or unknown key opens the
	 * soonest deadline instead. Selecting another unit swaps the URL in place without remounting.
	 */
	import { page } from '$app/stores';
	import DecidePage from '$lib/v3/decide/DecidePage.svelte';
</script>

<DecidePage param={$page.params.unit ?? null} />
