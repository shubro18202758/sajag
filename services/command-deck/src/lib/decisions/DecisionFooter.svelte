<script lang="ts" module>
	import type { IconName } from '$lib/design/icons';

	/** One footer button: its label, glyph, whether it can act now and, when not, why. */
	export interface FooterAct {
		label: string;
		icon?: IconName;
		disabled: boolean;
		/** The inline Reason (and tooltip) while disabled. */
		reason: string | null;
		run: () => void;
		testid?: string;
	}
</script>

<script lang="ts">
	/**
	 * DecisionFooter (SPEC §5.3 ProposalCard, §9.1) — the officer, the reason
	 * and the buttons of every decision card:
	 *
	 *   - the duty-officer field (`decision-officer`, an <input>), pre-filled
	 *     from the navbar's officer (commandBar.officer, else the ops store's)
	 *     with the honest helper, verbatim: "Shows full registration marks on
	 *     this console and records the name with your decision. Attribution,
	 *     not sign-in." Typing a name here names the console's officer (it is
	 *     the same one); with the operator gate on, the signed-in officer is
	 *     shown locked;
	 *   - Reason (`decision-reason`; the stolen-vehicle card keeps
	 *     `stolen-dismiss-reason`), required to Dismiss or Reject and sent as
	 *     the oracle note;
	 *   - `.ap-actions`: view evidence (icon), then Dismiss / Reject / Defer
	 *     (default), then the ONE primary — disabled with a Reason until an
	 *     officer is named. No single key ever approves.
	 *
	 * Sticky to the bottom of its scroll container when the viewport is at
	 * least 900 px tall; static below (SPEC §3.7). An outcome row (officer,
	 * time) replaces nothing: it sits above the buttons that still apply.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { ACTION_ICON } from '$lib/design/icons';
	import { Button, FormGroup, Icon, Input, Reason } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.decisions';

	let {
		lang = ops.lang,
		reasonMode = 'none',
		reasonTestId = 'decision-reason',
		reasonHint = null,
		reasonPlaceholder = null,
		reason = $bindable(''),
		primary = null,
		secondary = null,
		onevidence,
		busy = false,
		sticky = true,
		outcome = null,
		officerTestId = 'decision-officer',
		idPrefix = 'dec',
	}: {
		lang?: string;
		reasonMode?: 'none' | 'required' | 'optional';
		reasonTestId?: string;
		reasonHint?: string | null;
		/** The reason field's example, per kind (a 108 deferral is not a duplicate read). */
		reasonPlaceholder?: string | null;
		reason?: string;
		primary?: FooterAct | null;
		secondary?: FooterAct | null;
		onevidence?: () => void;
		busy?: boolean;
		sticky?: boolean;
		outcome?: string | null;
		officerTestId?: string;
		idPrefix?: string;
	} = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const uid = $props.id();

	/** The console's officer: the page's navbar control when it supplies one, else the ops store's. */
	const officerValue = $derived(commandBar.officer ? commandBar.officer.value : ops.dutyOfficer);
	const fromSession = $derived(commandBar.officer ? commandBar.officer.fromSession : ops.dutyOfficerFromSession);

	let draft = $state('');
	let editing = $state(false);
	$effect(() => {
		// follow the console's officer unless the operator is typing here
		const v = officerValue;
		if (!editing) draft = v;
	});

	function setOfficer(v: string) {
		if (fromSession) return;
		if (commandBar.officer) commandBar.officer.set(v);
		else ops.setDutyOfficer(v);
	}

	const lineReason = $derived(
		primary?.disabled && primary.reason ? primary.reason : !primary && secondary?.disabled && secondary.reason ? secondary.reason : null,
	);
</script>

<div class="foot" class:sticky data-part="decision-footer">
	{#if outcome}
		<p class="outcome" data-testid="decision-outcome"><Icon name="tick-circle" size={16} /><span>{outcome}</span></p>
	{/if}
	<FormGroup label={L('dec_officer_label')} labelFor="{idPrefix}-officer-{uid}" helperText={L('dec_officer_helper')} class="fg">
		<Input
			id="{idPrefix}-officer-{uid}"
			data-testid={officerTestId}
			fill
			readonly={fromSession}
			placeholder={L('dec_officer_placeholder')}
			autocomplete="off"
			spellcheck={false}
			maxlength={120}
			bind:value={draft}
			onfocus={() => (editing = true)}
			onblur={() => (editing = false)}
			oninput={() => setOfficer(draft)}
		/>
	</FormGroup>
	{#if reasonMode !== 'none'}
		<FormGroup
			label={L('dec_reason_label')}
			labelInfo={reasonHint ?? (reasonMode === 'required' ? L('dec_reason_info_required') : L('dec_reason_info_optional'))}
			labelFor="{idPrefix}-reason-{uid}"
			class="fg"
		>
			<Input
				id="{idPrefix}-reason-{uid}"
				data-testid={reasonTestId}
				fill
				maxlength={500}
				placeholder={reasonPlaceholder ?? L('dec_reason_placeholder')}
				bind:value={reason}
			/>
		</FormGroup>
	{/if}
	<div class="ap-actions">
		{#if onevidence}
			<Button minimal icon={ACTION_ICON.show_on_map} tooltip={L('dec_view_evidence')} aria-label={L('dec_view_evidence')} onclick={() => onevidence?.()} />
		{/if}
		<span class="grow"></span>
		{#if secondary}
			<Button
				data-testid={secondary.testid}
				icon={secondary.icon}
				disabled={secondary.disabled || busy}
				disabledReason={secondary.disabled ? secondary.reason : null}
				onclick={() => secondary?.run()}
			>
				{secondary.label}
			</Button>
		{/if}
		{#if primary}
			<Button
				intent="primary"
				data-testid={primary.testid}
				icon={primary.icon}
				loading={busy}
				disabled={primary.disabled || busy}
				disabledReason={primary.disabled ? primary.reason : null}
				onclick={() => primary?.run()}
			>
				{primary.label}
			</Button>
		{/if}
	</div>
	{#if lineReason}
		<Reason class="why-not" text={lineReason} />
	{/if}
</div>

<style>
	.foot {
		display: flex;
		flex-direction: column;
		gap: 0;
		padding: 12px 16px;
		border-top: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
	}

	.foot.sticky {
		position: sticky;
		bottom: 0;
		z-index: 1;
		box-shadow: 0 -8px 16px -8px var(--v-backdrop);
	}

	/* SPEC §3.7: below 900 px tall the decision footer is not sticky (and its helper folds) */
	@media (max-height: 899px) {
		.foot.sticky {
			position: static;
			box-shadow: none;
		}
	}

	.foot :global(.fg) {
		margin: 0 0 12px;
	}

	.outcome {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0 0 12px;
		padding: 6px 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
		background: var(--v-success-veil);
		border-radius: var(--v-radius-chip);
	}

	.outcome :global(svg) {
		color: var(--v-success-text);
		flex: 0 0 auto;
	}

	.ap-actions {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.grow {
		flex: 1 1 auto;
	}

	.foot :global(.why-not) {
		margin-top: 8px;
	}
</style>
