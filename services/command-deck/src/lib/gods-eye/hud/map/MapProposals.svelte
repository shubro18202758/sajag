<script lang="ts">
	/**
	 * MapProposals — the HOME of map proposals (SPEC §5.3, §5.4): the AI's
	 * canvas directives wait here as compact cards at the top centre of the
	 * map, "Proposed on the map · <label>", with the proposer's tier, Dismiss
	 * and Apply (the one primary, Dismiss to its left). Applying runs the move
	 * on this canvas only; nothing moves until a person applies it. Every
	 * other surface (the assistant) links here.
	 *
	 * Test hooks (SPEC §12.2): the container is `agent-suggestions`, each card
	 * `agent-chip` (with data-directive-id and data-verb), its buttons
	 * `agent-apply` and `agent-dismiss`.
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.map';
	import '$lib/i18n/packs.agent';
	import { ACTOR_ICON } from '$lib/design/icons';
	import Button from '$lib/ui/Button.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import Tag from '$lib/ui/Tag.svelte';
	import type { CanvasDirective } from '../../directives';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		proposals: readonly CanvasDirective[];
		/** The card's label for a proposal: the localised verb and its subject, masked. */
		textOf: (d: CanvasDirective) => string;
		onapply: (d: CanvasDirective) => void;
		ondismiss: (d: CanvasDirective) => void;
		lang?: string;
		/** Cards shown at once; the rest wait behind "+n more". */
		max?: number;
	}

	let { proposals, textOf, onapply, ondismiss, lang = 'en', max = 3, class: cls = '', ...rest }: Props = $props();

	const shown = $derived(proposals.slice(0, max));
</script>

{#if proposals.length}
	<div class={['proposals', cls]} data-testid="agent-suggestions" aria-live="polite" {...rest}>
		{#each shown as d (d.id)}
			<div class="card" data-testid="agent-chip" data-directive-id={d.id} data-verb={d.verb} title={t(lang, 'agent_proposal')}>
				<span class="who"><Icon name={ACTOR_ICON.ai} size={16} /></span>
				<span class="text">{t(lang, 'map_proposal_head', textOf(d))}</span>
				{#if d.tier}<Tag class="tier">{t(lang, 'map_proposal_tier', d.tier)}</Tag>{/if}
				<span class="acts">
					<Button small data-testid="agent-dismiss" onclick={() => ondismiss(d)}>{t(lang, 'agent_dismiss')}</Button>
					<Button small intent="primary" data-testid="agent-apply" onclick={() => onapply(d)}>{t(lang, 'agent_apply')}</Button>
				</span>
			</div>
		{/each}
		{#if proposals.length > max}
			<span class="more">{t(lang, 'agent_more', proposals.length - max)}</span>
		{/if}
	</div>
{/if}

<style>
	.proposals {
		display: flex;
		flex-direction: column;
		align-items: stretch;
		gap: 6px;
		width: min(440px, calc(100% - 16px));
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
	}

	.card {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 44px;
		padding: 6px 8px 6px 12px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-2);
		box-shadow: var(--v-elev-3);
		color: var(--v-ink-1);
	}

	.who {
		display: inline-flex;
		flex: 0 0 auto;
		color: var(--v-ai-text);
	}

	.text {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.acts {
		display: inline-flex;
		gap: 6px;
		flex: 0 0 auto;
	}

	.more {
		align-self: center;
		padding: 2px 8px;
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-2);
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}
</style>
