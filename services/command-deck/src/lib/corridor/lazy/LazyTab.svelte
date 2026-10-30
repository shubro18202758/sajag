<script lang="ts">
	/**
	 * LazyTab — a registered tab's lazy loader (plan R9's budget escape
	 * hatch): the registry mounts this wrapper; the real component loads on
	 * first mount of the tab (through LazyMount, which also lands the tab's
	 * glyphs beside it). Nothing heavy rides the route's eager graph. The
	 * failure line is the corridor pack's copy (audit C S3), in the console's
	 * language.
	 */
	import type { Component } from 'svelte';
	import { provideUiLang } from '$lib/ui';
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.corridor';

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);

	let { load }: { load: () => Promise<{ default: Component<any> }> } = $props();
</script>

<LazyMount {load}>
	{#snippet failure()}
		<div class="lazy-failed" role="alert" data-testid="lazy-failed">{t(lang, 'cor_tab_failed')}</div>
	{/snippet}
</LazyMount>

<style>
	.lazy-failed {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 24px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}
</style>
