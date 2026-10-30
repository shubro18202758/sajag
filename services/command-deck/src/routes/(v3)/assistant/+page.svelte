<script lang="ts">
	/**
	 * /assistant — the V3 Assistant (V3-SPEC §5.7; V3-P4). The page is $lib/v3/assistant/AssistantPage.svelte: the
	 * shared assistant session ($lib/assistant/session.svelte.ts) in the V3 conversation layout. /chat stays the v2
	 * assistant page, unchanged.
	 */
	import AssistantPage from '$lib/v3/assistant/AssistantPage.svelte';
</script>

<AssistantPage />
