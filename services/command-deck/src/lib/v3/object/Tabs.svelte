<script lang="ts">
	/**
	 * The object page's tabs (V3-SPEC §5.4: Overview · Sources · Timeline · Nearby · Record, counts in pills).
	 * A real tablist: one tab stop (the selected tab), ←/→ move and select (wrapping), Home/End jump; each tab
	 * controls `obj-panel-<id>`. The selected tab is underlined (no fill: the global .is-selected veil is for data rows).
	 */
	import { t } from '$lib/i18n/strings';
	import './packs.object';
	import { tabStep, type TabId, type TabSpec } from './model';

	let { tabs, value = $bindable(), label, lang }: { tabs: readonly TabSpec[]; value: TabId; label: string; lang: string } = $props();

	let list = $state<HTMLDivElement | null>(null);

	function onkey(e: KeyboardEvent) {
		const next = tabStep(tabs, value, e.key);
		if (!next) return;
		e.preventDefault();
		value = next as TabId;
		list?.querySelector<HTMLButtonElement>(`[data-tab="${next}"]`)?.focus();
	}
</script>

<div class="tabs" role="tablist" aria-label={label} bind:this={list} tabindex="-1" onkeydown={onkey} data-testid="obj-tabs">
	{#each tabs as tab (tab.id)}
		<button
			type="button"
			role="tab"
			id={`obj-tab-${tab.id}`}
			class={['tab', tab.id === value && 'on']}
			aria-selected={tab.id === value}
			aria-controls={`obj-panel-${tab.id}`}
			tabindex={tab.id === value ? 0 : -1}
			data-tab={tab.id}
			onclick={() => (value = tab.id)}
		>
			{t(lang, tab.key)}
			{#if tab.count != null}<span class="n" aria-hidden="true">{tab.count}</span><span class="sr">({tab.count})</span>{/if}
		</button>
	{/each}
</div>

<style>
	.tabs {
		display: flex;
		gap: 6px;
		overflow-x: auto;
		border-bottom: 1px solid var(--v3-line-1);
		scrollbar-width: none;
	}

	.tabs:focus {
		outline: none;
	}

	.tab {
		display: inline-flex;
		flex: none;
		align-items: center;
		gap: 8px;
		height: var(--v3-ctl-lg);
		margin-bottom: -1px;
		padding: 0 14px;
		border: 0;
		border-bottom: 2px solid transparent;
		background: none;
		color: var(--v3-t2);
		font: inherit;
		font-size: var(--v3-text-body);
		font-weight: 600;
		cursor: pointer;
		transition: color var(--v3-dur-1) var(--v3-ease);
	}

	.tab:hover {
		color: var(--v3-t1);
	}

	.tab.on {
		border-bottom-color: var(--v3-t1);
		color: var(--v3-t1);
	}

	.tab:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: -2px;
		border-radius: 6px;
	}

	.n {
		padding: 1px 7px;
		border-radius: 10px;
		background: var(--v3-s3);
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-variant-numeric: tabular-nums;
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	@media (prefers-reduced-motion: reduce) {
		.tab {
			transition: none;
		}
	}
</style>
