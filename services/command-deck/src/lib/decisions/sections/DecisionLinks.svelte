<script lang="ts">
	/**
	 * Decision link cards in the inspector (sections/links.ts; registered for
	 * recommendation, vehicle, event, dispatch and junction by
	 * decisions/register.ts, id 'decisions.links', order 20): one card per
	 * unit whose decision touches this object while its subject is another
	 * (the Actions tab links the units ABOUT this object). The card opens the
	 * unit's one home on this route; it never carries a decision verb.
	 */
	import type { InspectorSectionProps } from '$lib/workspace/types';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { frameContext } from '$lib/workspace/components/frame/context';
	import { ops } from '$lib/ops/store.svelte';
	import { kindIcon } from '$lib/design/icons';
	import { Icon } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.decisions';
	import { homeOf } from '../homes';
	import { summaryOf, unitsReferencing } from './links';

	let { row }: InspectorSectionProps = $props();

	const frame = frameContext();
	const route = $derived.by((): '/' | '/gods-eye' | '/ops' => {
		const r = frame?.route();
		return r === '/gods-eye' || r === '/ops' ? r : '/';
	});
	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const units = $derived(unitsReferencing(row.urn));
</script>

{#if units.length}
	<div class="links" data-testid="decision-links">
		{#each units as u (`${u.kind}:${u.id}`)}
			<button
				type="button"
				class="linkcard"
				data-testid="decision-ref-link"
				data-unit-kind={u.kind}
				data-unit-id={u.id}
				onclick={() => workspace.openDecisionHome(summaryOf(u), route)}
			>
				<Icon name={kindIcon('recommendation')} size={16} class="g" />
				<span class="body">
					<span class="title">{u.title}</span>
					<span class="sub">{L(`dec_home_${homeOf(u.kind, route)}`)}</span>
				</span>
				<Icon name="arrow-right" size={16} class="g" />
			</button>
		{/each}
	</div>
{/if}

<style>
	.links {
		padding: 8px 16px;
	}

	.linkcard {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		margin: 0 0 4px;
		padding: 8px 12px;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-2);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
		color: var(--v-ink-1);
		font: inherit;
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: 16px;
		text-align: left;
		cursor: pointer;
	}

	.linkcard:hover {
		background: var(--v-surface-3);
	}

	.linkcard:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.linkcard :global(.g) {
		flex: 0 0 auto;
		color: var(--v-warning-text);
	}

	.body {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-width: 0;
	}

	.title {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 600;
	}

	.sub {
		color: var(--v-ink-2);
	}
</style>
