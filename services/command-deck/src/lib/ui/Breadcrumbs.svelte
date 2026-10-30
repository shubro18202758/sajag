<script lang="ts">
	/**
	 * Breadcrumbs — where an object sits ("Old City · stolen vehicle ›
	 * Vehicles › MH01XX•••7"): 12 px, ink-2, chevron separators, the current
	 * crumb in ink-1 and ellipsised. Crumbs with href or onclick are links.
	 * The current crumb may render custom content through `current`.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import Icon from './Icon.svelte';
	import { uiLang, ut } from './lang';
	import type { Crumb } from './types';

	interface Props extends HTMLAttributes<HTMLElement> {
		items: readonly Crumb[];
		current?: Snippet;
		lang?: string;
	}

	let { items, current, lang, class: cls = '', ...rest }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
</script>

<nav data-ui="breadcrumbs" aria-label={ut(L, 'ui_location')} class={['crumbs', cls]} {...rest}>
	<ol>
		{#each items as c, i (i)}
			{@const last = i === items.length - 1}
			<li class={['crumb', (c.current || last) && 'cur']}>
				{#if i > 0}<Icon name="chevron-right" size={12} class="sep" />{/if}
				{#if (c.current || last) && current}
					<span class="c" aria-current="page">{@render current()}</span>
				{:else if c.href && !(c.current || last)}
					<a class="c link" href={c.href}>{#if c.icon}<Icon name={c.icon} size={12} />{/if}{c.label}</a>
				{:else if c.onclick && !(c.current || last)}
					<button type="button" class="c link" onclick={c.onclick}
						>{#if c.icon}<Icon name={c.icon} size={12} />{/if}{c.label}</button
					>
				{:else}
					<span class="c" aria-current={c.current || last ? 'page' : undefined}
						>{#if c.icon}<Icon name={c.icon} size={12} />{/if}{c.label}</span
					>
				{/if}
			</li>
		{/each}
	</ol>
</nav>

<style>
	.crumbs {
		min-width: 0;
		color: var(--v-ink-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	ol {
		display: flex;
		align-items: center;
		gap: 2px;
		min-width: 0;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.crumb {
		display: inline-flex;
		flex: 0 1 auto;
		align-items: center;
		gap: 2px;
		min-width: 0;
		white-space: nowrap;
	}

	.crumb:not(.cur) {
		flex-shrink: 0;
	}

	.crumbs :global(.sep) {
		color: var(--v-ink-2);
	}

	.c {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.cur .c {
		color: var(--v-ink-1);
	}

	.link {
		margin: 0;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--v-ink-2);
		font: inherit;
		text-decoration: none;
		cursor: pointer;
	}

	.link:hover {
		color: var(--v-primary-text);
	}

	.link:focus-visible {
		outline: 2px solid var(--v-focus);
	}
</style>
