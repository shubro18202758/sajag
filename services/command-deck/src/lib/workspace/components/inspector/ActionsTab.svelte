<script lang="ts">
	/**
	 * Actions — what can be done with this object that is not a decision
	 * (the workspace's actions and every provider's, registerActions), and a
	 * LINK CARD to the home of every decision unit whose subject is this
	 * object. A decision is made in exactly one place per route (SPEC §5.4):
	 * this tab never carries a second Approve button. Each action's button
	 * says what it does ("Copy", "Show", "Explain"); a provider's action
	 * this tab has no verb for says "Run".
	 */
	import { kindIcon } from '$lib/design/icons';
	import { fmtCountdown, fmtDuration } from '$lib/ui/format/format';
	import { Button, Icon, NonIdealState, Reason } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.workspace';
	import type { DecisionUnitSummary, ObjectAction, TabRoute } from '../../types';

	let {
		actions,
		units,
		route,
		lang,
		now,
		onhome,
		mask,
	}: {
		actions: readonly ObjectAction[];
		units: readonly DecisionUnitSummary[];
		route: TabRoute;
		lang: string;
		now: number;
		onhome: (u: DecisionUnitSummary) => void;
		/** Provider text as this console may show it (the inspector's mask: raw only for a named duty officer). */
		mask: (s: string) => string;
	} = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	/** The button's verb for the workspace's own actions (actions.ts). */
	const VERB: Readonly<Record<string, string>> = {
		'ws.show-on-map': 'ws_verb_show',
		'ws.search-around': 'ws_verb_search',
		'ws.add-to-graph': 'ws_verb_add',
		'ws.explain': 'ws_verb_explain',
		'ws.copy-link': 'ws_verb_copy',
		'ws.copy-urn': 'ws_verb_copy',
		'ws.open-in-table': 'ws_verb_open',
	};
	const verb = (a: ObjectAction) => L(VERB[a.id] ?? 'ws_act_run');
	/** The button's accessible name: the action's label when it holds the verb ("Copy" → "Copy link"), else the verb alone. */
	const named = (a: ObjectAction) => (a.label.toLowerCase().includes(verb(a).toLowerCase()) ? mask(a.label) : undefined);
	const homeRoute = $derived(route === '/chat' ? '/' : route);
	const homeWord = (u: DecisionUnitSummary) => L(`ws_home_${u.homes[homeRoute] ?? 'inbox'}`);
	const due = (u: DecisionUnitSummary) =>
		u.deadline == null ? null : u.deadline - now < 3_600_000 ? L('ws_link_due', fmtCountdown((u.deadline - now) / 1000)) : L('ws_link_due', fmtDuration((u.deadline - now) / 1000, lang));
</script>

{#each units as u (`${u.kind}:${u.id}`)}
	<button type="button" class="linkcard" data-testid="decision-link" data-unit-kind={u.kind} data-unit-id={u.id} onclick={() => onhome(u)}>
		<Icon name={kindIcon('recommendation')} class="g" />
		<span class="body">
			<span class="title">{mask(u.title)}</span>
			<span class="sub">{L('ws_link_decided_in', homeWord(u))}{#if due(u)}{` · ${due(u)}`}{/if}</span>
		</span>
		<Icon name="arrow-right" class="g" />
	</button>
{/each}

{#if !actions.length && !units.length}
	<div class="empty"><NonIdealState icon="more" iconSize={32} title={L('ws_actions_none')} /></div>
{:else}
	<ul class="acts">
		{#each actions as a (a.id)}
			<li class="act" data-action-id={a.id}>
				<Icon name={a.icon} class="g" />
				<span class="body">
					<span class="title">{mask(a.label)}</span>
					{#if a.disabled && a.disabledReason}<Reason text={mask(a.disabledReason)} />{/if}
				</span>
				<Button small aria-label={named(a)} disabled={a.disabled} disabledReason={a.disabledReason ?? null} onclick={() => void a.run()}>{verb(a)}</Button>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.linkcard {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		margin: 12px 0 4px;
		padding: 8px 12px;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-2);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
		color: var(--v-ink-1);
		font: inherit;
		font-size: 12px;
		line-height: 16px;
		text-align: left;
		cursor: pointer;
	}

	.linkcard:hover {
		background: var(--v-surface-3);
	}

	.linkcard :global(.g),
	.act :global(.g) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.body {
		display: flex;
		flex-direction: column;
		gap: 4px;
		flex: 1 1 auto;
		min-width: 0;
	}

	.title {
		font-weight: 600;
	}

	.sub {
		color: var(--v-ink-2);
	}

	.empty {
		padding: 16px 0;
	}

	.acts {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.act {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 8px 0;
		border-bottom: 1px solid var(--v-line-1);
		font-size: 14px;
	}

	.act .title {
		font-weight: 400;
	}
</style>
