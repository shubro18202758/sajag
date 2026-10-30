<script lang="ts" module>
	export type DecisionKind = 'echallan' | 'corridor-request' | 'dispatch' | 'pursuit' | 'stolen-sighting';

	export interface DecisionAction {
		id: string;
		label: string;
		kind: 'commit' | 'reject' | 'defer' | 'ghost';
	}
</script>

<script lang="ts">
	/**
	 * DecisionCard — one item the machine proposed and a named officer must
	 * dispose of, rebuilt in the ProposalCard anatomy (SPEC §5.2, §5.3) on
	 * src/lib/ui: a header (the kind tag, the title, the deadline tag), the
	 * meta line, the body, the evidence, then the decision footer — the
	 * officer (or why the commit is refused), and the buttons with the ONE
	 * primary (the commit) on the right and Reject or Defer to its left.
	 *
	 * The commit cannot enable without a named officer (Button's gate); while
	 * `busy` the commit shows its spinner and every action is disabled, so a
	 * double click sends one decision. `blocked` names why the commit cannot
	 * go out even with an officer on console; it replaces the officer hint.
	 * `data-prim="decision-card"`, `data-kind` and `card-deadline` stay.
	 */
	import { ACTOR_ICON, INTENT_ICON } from '$lib/design/icons';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import Icon from '$lib/ui/Icon.svelte';
	import Tag from '$lib/ui/Tag.svelte';
	import Badge from './Badge.svelte';
	import Button from './Button.svelte';

	interface Props {
		kind: DecisionKind;
		title: string;
		/** A countdown or a window (retention, golden hour, expiry). */
		deadline?: string | null;
		/** Hover explanation of the deadline (what the countdown means). */
		deadlineTitle?: string | null;
		/** The kind tag's text (defaults to the raw kind). */
		badgeLabel?: string | null;
		actions?: DecisionAction[];
		/** Named officer identity; without it the commit renders locked. */
		namedActor?: string | null;
		/** A decision for this item is in flight: commit shows busy, all actions disable. */
		busy?: boolean;
		/** Why the commit is refused regardless of the officer (rendered in the footer). */
		blocked?: string | null;
		onaction?: (id: string) => void;
		lang?: string;
		evidence?: import('svelte').Snippet;
		meta?: import('svelte').Snippet;
		children?: import('svelte').Snippet;
	}

	let {
		kind,
		title,
		deadline = null,
		deadlineTitle = null,
		badgeLabel = null,
		actions = [],
		namedActor = null,
		busy = false,
		blocked = null,
		onaction,
		lang = 'en',
		evidence,
		meta,
		children
	}: Props = $props();

	const variantFor = (a: DecisionAction) => (a.kind === 'commit' ? 'primary' : a.kind === 'ghost' ? 'ghost' : 'secondary');

	const hasCommit = $derived(actions.some((a) => a.kind === 'commit'));
	/** The one primary sits on the right; Reject, Defer and the rest to its left (SPEC §1.7). */
	const ordered = $derived([...actions.filter((a) => a.kind !== 'commit'), ...actions.filter((a) => a.kind === 'commit')]);
</script>

<article class="card k-{kind}" class:busy data-prim="decision-card" data-kind={kind} aria-busy={busy || undefined}>
	<header class="head">
		<div class="tags">
			<Badge variant="neutral" label={badgeLabel ?? kind} {lang} />
			{#if deadline}
				<span data-testid="card-deadline" class="deadline">
					<Tag intent="warning" tooltip={deadlineTitle}>{deadline}</Tag>
				</span>
			{/if}
		</div>
		<h3 class="title">{title}</h3>
	</header>

	{#if meta}
		<div class="meta">
			{@render meta()}
		</div>
	{/if}

	<div class="body">
		{@render children?.()}
	</div>

	{#if evidence}
		<div class="evidence">
			{@render evidence()}
		</div>
	{/if}

	<footer class="foot">
		{#if blocked}
			<span class="reason" data-blocked><Icon name={INTENT_ICON.none} size={16} />{blocked}</span>
		{:else if namedActor}
			<span class="actor" title={namedActor}><Icon name={ACTOR_ICON.officer} size={16} />{namedActor}</span>
		{:else if hasCommit}
			<span class="reason"><Icon name={INTENT_ICON.none} size={16} />{t(lang, 'officer_hint')}</span>
		{/if}
		<span class="actions">
			{#each ordered as action (action.id)}
				<Button
					variant={variantFor(action)}
					size="sm"
					{lang}
					actor={action.kind === 'commit' ? namedActor : (namedActor ?? 'ui')}
					busy={busy && action.kind === 'commit'}
					disabled={busy || (!!blocked && action.kind === 'commit')}
					onclick={() => {
						if (!busy && !(blocked && action.kind === 'commit')) onaction?.(action.id);
					}}
				>
					{action.label}
				</Button>
			{/each}
		</span>
	</footer>
</article>

<style>
	.card {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 12px 16px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
		box-shadow: var(--v-elev-0);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.head {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
	}

	.deadline {
		display: inline-flex;
	}

	/* the title gets the line: it wraps, never squeezed by a tag */
	.title {
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: 20px;
		overflow-wrap: anywhere;
	}

	.meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.body {
		color: var(--v-ink-1);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) * 1.5);
	}

	.body:empty {
		display: none;
	}

	.evidence {
		padding: 8px 12px;
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-sink);
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.foot {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		padding-top: 8px;
		border-top: 1px solid var(--v-line-1);
	}

	.reason,
	.actor {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.actor {
		color: var(--v-ink-1);
	}

	.reason :global([data-ui='icon']),
	.actor :global([data-ui='icon']) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.actions {
		display: flex;
		gap: 8px;
		margin-left: auto;
	}
</style>
