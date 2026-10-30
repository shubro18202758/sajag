<script lang="ts">
	/**
	 * One Inbox row (SPEC §5.3 Inbox; prototype .inbox-row): a 16 px lead
	 * glyph, the title (600 while unread) and a 12 px meta line, and the right
	 * column — "waiting / 1 h 40 min" or, for a time-boxed proposal,
	 * "expires in / 1:25" in the warning ink. A selected row (the J/K cursor)
	 * is `.is-selected` (the one active-state rule). The whole row is one
	 * button: it opens the unit's detail view (or, for an escort proposal,
	 * its home, the Movement tab — never a decision button here).
	 */
	import type { Snippet } from 'svelte';
	import type { IconName } from '$lib/design/icons';
	import { Icon } from '$lib/ui';

	let {
		icon,
		tone = 'neutral',
		title,
		meta = null,
		ageLabel = null,
		age = null,
		urgent = false,
		countdown = false,
		unread = false,
		selected = false,
		onopen,
		titleSnippet,
		...rest
	}: {
		icon: IconName;
		tone?: 'neutral' | 'warning' | 'danger' | 'ai';
		title: string;
		meta?: string | null;
		ageLabel?: string | null;
		age?: string | null;
		urgent?: boolean;
		countdown?: boolean;
		unread?: boolean;
		selected?: boolean;
		onopen: () => void;
		titleSnippet?: Snippet;
		[k: string]: unknown;
	} = $props();
</script>

<button
	type="button"
	class="row"
	class:unread
	class:is-selected={selected}
	data-unread={unread ? '1' : '0'}
	onclick={() => onopen()}
	{...rest}
>
	<span class="lead tone-{tone}"><Icon name={icon} size={16} /></span>
	<span class="mid">
		<span class="ttl">{#if titleSnippet}{@render titleSnippet()}{:else}{title}{/if}</span>
		{#if meta}<span class="m">{meta}</span>{/if}
	</span>
	{#if age}
		<span class="age">
			{#if ageLabel}<span class="al">{ageLabel}</span>{/if}
			<span class="av" class:due={countdown} class:urgent>{age}</span>
		</span>
	{/if}
</button>

<style>
	.row {
		display: grid;
		grid-template-columns: 16px minmax(0, 1fr) auto;
		gap: 12px;
		width: 100%;
		padding: 10px 12px 10px 16px;
		border: 0;
		border-bottom: 1px solid var(--v-line-1);
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		font-family: var(--v-font-ui);
		text-align: left;
		cursor: pointer;
	}

	.row:hover {
		background: var(--v-row-hover);
	}

	.row:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.row.is-selected {
		background: var(--v-primary-veil);
		box-shadow: inset 2px 0 0 var(--v-primary-text);
	}

	.lead {
		padding-top: 1px;
		color: var(--v-ink-2);
	}

	.tone-warning {
		color: var(--v-warning-text);
	}

	.tone-danger {
		color: var(--v-danger-text);
	}

	.tone-ai {
		color: var(--v-ai-text);
	}

	.mid {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	/* F-29: the title is the decision's VERB ("Authorise pursuit of …", "Reject e-challan for …"): it
	   wraps onto a second line on a narrow dock (1366) instead of being cut mid-verb; the mark keeps
	   its own unbroken box */
	.ttl {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		column-gap: 6px;
		row-gap: 2px;
		min-width: 0;
		font-size: var(--v-text-base);
		font-weight: 400;
		line-height: 18px;
		overflow-wrap: anywhere;
	}

	.row.unread .ttl {
		font-weight: 600;
	}

	.m {
		margin-top: 4px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.age {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
		white-space: nowrap;
	}

	.av {
		color: var(--v-ink-1);
		font-variant-numeric: tabular-nums;
	}

	.av.due {
		color: var(--v-warning-text);
		font-weight: 600;
	}

	.av.urgent {
		color: var(--v-danger-text);
	}
</style>
