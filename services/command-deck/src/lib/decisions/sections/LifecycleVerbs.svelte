<script lang="ts">
	/**
	 * The C-F verb rail of one corridor event (the EventLifecycleVerbs logic,
	 * rebuilt on src/lib/ui): Approve / Activate / Complete / Cancel, offered
	 * strictly from the server's transition table for the event's RAW status.
	 * Every verb is a city-writer commit under the named duty officer; while
	 * one is in flight every verb is disabled, so a double click sends ONE
	 * POST. Cancel asks once more inline (`.cancel-row input`, a reason for the
	 * ledger). The outcome renders inline (`event-outcome`, data-ok):
	 * "activated by <officer> · hh:mm:ss IST", or the server's refusal with
	 * the moves it allows.
	 *
	 * Hooks kept: `event-verbs` (data-event-id, data-status), `[data-verb]`
	 * wrapping each button, `.cancel-row input`, `event-outcome[data-ok]`.
	 */
	import { ops, eventVerbs } from '$lib/ops/store.svelte';
	import { Button, Input } from '$lib/ui';
	import { tOps } from '$lib/i18n/strings.ops';
	import type { CorridorEvent, EventTransitionTarget } from '$lib/ops/types';
	import { outcomeText } from './lifecycle.svelte';

	let { event, compact = false }: { event: CorridorEvent; compact?: boolean } = $props();

	const lang = $derived(ops.lang);
	const verbs = $derived(eventVerbs(event));
	const busy = $derived(ops.eventBusy === event.eventId);
	const anyBusy = $derived(ops.eventBusy !== null);
	const outcome = $derived(ops.eventOutcome?.eventId === event.eventId ? ops.eventOutcome : null);
	const outcomeLine = $derived(outcome ? outcomeText(lang) : null);

	let confirmCancel = $state(false);
	let cancelNote = $state('');

	const VERB_KEY: Record<EventTransitionTarget, string> = {
		approved: 'verbApprove',
		active: 'verbActivate',
		completed: 'verbComplete',
		cancelled: 'verbCancel',
	};

	async function fire(to: EventTransitionTarget) {
		if (to === 'cancelled' && !confirmCancel) {
			confirmCancel = true;
			return;
		}
		const note = to === 'cancelled' ? cancelNote : '';
		const ok = await ops.transitionEvent(event.eventId, to, note);
		if (ok) {
			confirmCancel = false;
			cancelNote = '';
		}
	}

	const needOfficer = $derived(ops.officerOn ? null : tOps(lang, 'lifecycleNeedsOfficer'));
</script>

{#if verbs.length}
	<div class="verbs" class:compact data-testid="event-verbs" data-event-id={event.eventId} data-status={event.status ?? ''}>
		{#each verbs as verb, i (verb)}
			<span class="verb-wrap" data-verb={verb}>
				<Button
					small
					intent={verb !== 'cancelled' && i === 0 ? 'primary' : 'none'}
					outlined={verb === 'cancelled'}
					loading={busy}
					disabled={anyBusy || !ops.officerOn}
					disabledReason={needOfficer}
					onclick={() => void fire(verb)}
				>
					{verb === 'cancelled' && confirmCancel ? tOps(lang, 'verbConfirmCancel') : tOps(lang, VERB_KEY[verb])}
				</Button>
			</span>
		{/each}
	</div>
	{#if confirmCancel}
		<div class="cancel-row">
			<Input small fill placeholder={tOps(lang, 'verbCancelPlaceholder')} bind:value={cancelNote} maxlength={500} />
			<Button small minimal onclick={() => ((confirmCancel = false), (cancelNote = ''))}>{tOps(lang, 'verbKeep')}</Button>
		</div>
	{/if}
{/if}

{#if outcome}
	<p class="outcome" class:ok={outcome.ok} class:refused={!outcome.ok} data-testid="event-outcome" data-ok={outcome.ok}>{outcomeLine}</p>
{/if}

<style>
	.verbs {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}

	.verb-wrap {
		display: inline-flex;
	}

	.cancel-row {
		display: flex;
		gap: 8px;
		align-items: center;
		margin-top: 4px;
	}

	.outcome {
		margin: 4px 0 0;
		padding: 4px 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		overflow-wrap: anywhere;
		font-variant-numeric: tabular-nums;
	}

	.outcome.ok {
		color: var(--v-ink-1);
		background: var(--v-success-veil);
	}

	.outcome.refused {
		color: var(--v-ink-1);
		background: var(--v-danger-veil);
	}
</style>
