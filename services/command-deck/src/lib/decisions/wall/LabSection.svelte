<script lang="ts">
	/**
	 * Lab and system (SPEC §6.3 col 3; plan X23), collapsed by default: the
	 * scenario emulator with the living city, the twin comparison and the
	 * degradation ledger. They are tools for a rehearsal or an audit, not the
	 * live picture, so they stay folded until asked for.
	 *
	 * Hooks (plan X23, consumed by UI-S7A's openIfCollapsed and UI-S7B):
	 *   [data-testid=lab-toggle]   the disclosure button, aria-expanded false|true
	 *   [data-testid=lab-section]  the root, data-open false|true
	 * While folded the panels are not mounted (their nodes are absent); once
	 * opened they mount, and the ops store polls the emulator and the ledger
	 * as it always does (the store's pollers never depended on the panels).
	 */
	import { tick } from 'svelte';
	import { Icon } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';

	interface Props {
		lang: string;
		open?: boolean;
	}

	let { lang, open = $bindable(false) }: Props = $props();

	const uid = $props.id();
	let root: HTMLElement | undefined = $state();

	/**
	 * Opening brings the panels into view: they mount below the fold of the
	 * right column, so the column (the nearest scrolling ancestor, and only
	 * it) scrolls the section to its top. Never scrollIntoView: that would
	 * also scroll the page's own overflow-hidden frames.
	 */
	async function toggle() {
		open = !open;
		if (!open || !root) return;
		await tick();
		let scroller = root.parentElement;
		while (scroller && !/(auto|scroll)/.test(getComputedStyle(scroller).overflowY)) scroller = scroller.parentElement;
		if (!scroller) return;
		const top = root.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop;
		scroller.scrollTo({ top, behavior: 'smooth' });
	}
</script>

<section class="lab" bind:this={root} data-testid="lab-section" data-open={open ? 'true' : 'false'} data-prim="panel" aria-labelledby="{uid}-title">
	<header class="head">
		<h2 class="hx">
			<button
				type="button"
				class="toggle"
				data-testid="lab-toggle"
				aria-expanded={open ? 'true' : 'false'}
				aria-controls="{uid}-body"
				onclick={() => void toggle()}
			>
				<Icon name={open ? 'chevron-down' : 'chevron-right'} size={16} />
				<Icon name="lab-test" size={16} />
				<span class="title" id="{uid}-title">{t(lang, 'wall_lab')}</span>
			</button>
		</h2>
		<span class="sub">{t(lang, 'wall_lab_sub')}</span>
	</header>
	{#if open}
		<div class="body" id="{uid}-body">
			<!-- the lab is closed at first paint: its panels load when it opens (FIX-E-PERF2) -->
			<LazyMount load={() => import('$lib/ops/components/EmulatorPanel.svelte')} />
			<LazyMount load={() => import('$lib/ops/components/TwinComparePanel.svelte')} />
			<LazyMount load={() => import('$lib/ops/components/DegradationLedger.svelte')} />
		</div>
	{/if}
</section>

<style>
	.lab {
		display: flex;
		flex-direction: column;
		min-width: 0;
		border-bottom: 1px solid var(--v-line-2);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 40px;
		padding: 0 16px 0 8px;
		min-width: 0;
	}

	.hx {
		display: flex;
		flex: 0 0 auto;
		min-width: 0;
		margin: 0;
		font-size: inherit;
		font-weight: inherit;
		line-height: inherit;
		align-self: stretch;
	}

	.toggle {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		margin: 0;
		padding: 0 8px;
		border: 0;
		border-radius: var(--v-radius-btn);
		background: transparent;
		color: inherit;
		font: inherit;
		cursor: pointer;
	}

	.toggle:hover {
		background: var(--v-minimal-hover);
	}

	.toggle:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.toggle :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.title {
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: calc(var(--v-text-base) + 2px);
		white-space: nowrap;
	}

	.sub {
		flex: 1 1 auto;
		min-width: 0;
		margin-left: 8px;
		text-align: right;
		overflow: hidden;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.body {
		display: flex;
		flex-direction: column;
		border-top: 1px solid var(--v-line-1);
	}
</style>
