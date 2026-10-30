<script lang="ts">
	/**
	 * The navbar's duty-officer control (SPEC §5.3, §9.1; plan R10).
	 *
	 * - The page supplies `officer` ({value, fromSession, set}); without it the
	 *   navbar renders no `duty-officer` (the page still shows its own).
	 * - ≥ 1440 px: an inline INPUT (`data-testid="duty-officer"` on the
	 *   <input>, the group carries `.officer-input`) that stays an input when a
	 *   name is set, with a clear button and the honest helper as its tooltip.
	 * - < 1440 px: an avatar button whose popover holds the same input
	 *   (`data-autofocus`, so a click lands in it).
	 * - Operator gate on (SAJAG_OPERATOR_PIN): the input shows the signed-in
	 *   officer and is locked; sign-in (`operator-signin`, the form's
	 *   `signin-officer` / `signin-pin`) and sign-out live in the same popover.
	 *   Gate on and no page officer: the session control alone.
	 */
	import { t } from '$lib/i18n/strings';
	import Button from '$lib/ui/Button.svelte';
	import FormGroup from '$lib/ui/FormGroup.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import Input from '$lib/ui/Input.svelte';
	import Popover from '$lib/ui/Popover.svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';
	import type { OfficerControl } from './command-bar.svelte';
	import { CLEAR_ICON, MASKED_ICON, OFFICER_ICON } from './icons';
	import NavButton from './NavButton.svelte';
	import OperatorSignIn from './OperatorSignIn.svelte';
	import { operatorSession } from './session.svelte';

	interface Props {
		officer: OfficerControl | null;
		compact: boolean;
		lang: string;
	}

	let { officer, compact, lang }: Props = $props();

	const uid = $props.id();
	const gateOn = $derived(operatorSession.gate === true);
	const sessionName = $derived(operatorSession.officer);
	/** Gate on (or a session-sourced name): the field shows the signed-in officer, locked. */
	const locked = $derived(gateOn || !!officer?.fromSession);
	const shownName = $derived(officer ? officer.value : (sessionName ?? ''));
	const named = $derived(!!shownName.trim());

	// The field's text: the page's value, followed when it changes from outside
	// (a session adopted, another surface naming the officer).
	let draft = $state('');
	$effect.pre(() => {
		draft = officer?.value ?? '';
	});

	let open = $state(false);

	function onInput(e: Event) {
		const v = (e.currentTarget as HTMLInputElement).value;
		draft = v;
		officer?.set(v);
	}

	function clear() {
		draft = '';
		officer?.set('');
	}

	async function signOut() {
		await operatorSession.signOut();
		location.reload();
	}

	const helper = $derived(t(lang, 'shell_officer_helper'));
	const lockTip = $derived(sessionName ? `${t(lang, 'shell_officer_signed', sessionName)}. ${t(lang, 'shell_officer_session')}` : t(lang, 'signin_note'));
	const avatarTip = $derived(named ? t(lang, 'shell_officer_named', shownName) : t(lang, 'shell_officer_none'));
</script>

{#snippet field(autofocus: boolean, fillWidth: boolean)}
	<Input
		id={fillWidth ? `${uid}-pop` : undefined}
		class="officer-input"
		fill={fillWidth}
		leftIcon={OFFICER_ICON}
		value={locked ? shownName : draft}
		readonly={locked}
		placeholder={locked && !named ? t(lang, 'shell_officer_signed_out') : t(lang, 'shell_officer')}
		aria-label={t(lang, 'shell_officer')}
		aria-describedby={fillWidth ? `${uid}-help` : `${uid}-tip`}
		autocomplete="off"
		spellcheck="false"
		maxlength={64}
		oninput={onInput}
		data-testid="duty-officer"
		data-locked={locked ? 'true' : undefined}
		data-autofocus={autofocus && !locked ? '' : undefined}
		{lang}
	>
		{#snippet rightElement()}
			{#if locked}
				<span class="lock" title={t(lang, 'shell_officer_session')}><Icon name={MASKED_ICON} size={12} /></span>
			{:else if draft}
				<button type="button" class="clear" aria-label={t(lang, 'shell_officer_clear')} onclick={clear}>
					<Icon name={CLEAR_ICON} size={16} />
				</button>
			{/if}
		{/snippet}
	</Input>
{/snippet}

{#snippet sessionBlock()}
	{#if gateOn}
		{#if sessionName}
			<div class="session">
				<div class="who"><Icon name={OFFICER_ICON} size={16} />{t(lang, 'shell_officer_signed', sessionName)}</div>
				{#if !officer}<p class="help">{t(lang, 'shell_officer_session')}</p>{/if}
				<div class="row-end">
					<!-- text only: the glyph set has no sign-out glyph, and a lock would say the opposite -->
					<Button small onclick={() => void signOut()}>{t(lang, 'signin_signout')}</Button>
				</div>
			</div>
		{:else}
			<OperatorSignIn {lang} inline />
		{/if}
	{/if}
{/snippet}

{#snippet panel(close: () => void)}
	<div class="panel" class:wide={gateOn && !sessionName}>
		<div class="head">{gateOn && !sessionName ? t(lang, 'signin_title') : t(lang, 'shell_officer')}</div>
		{#if officer}
			<FormGroup label={t(lang, 'shell_officer_roster')} labelFor="{uid}-pop">
				{@render field(true, true)}
				<!-- honest in every state: the gate's line only once it has signed someone in -->
				<p class="help" id="{uid}-help">{!locked ? helper : sessionName ? t(lang, 'shell_officer_session') : t(lang, 'shell_officer_signin_below')}</p>
			</FormGroup>
		{/if}
		{@render sessionBlock()}
		{#if officer && !locked}
			<div class="row-end"><Button small onclick={close}>{t(lang, 'shell_officer_done')}</Button></div>
		{/if}
	</div>
{/snippet}

{#if compact}
	{#if officer || gateOn}
		<Popover placement="bottom-end" bind:open aria-label={t(lang, 'shell_officer')}>
			<NavButton
				icon={OFFICER_ICON}
				iconOnly
				tip={avatarTip}
				aria-label={avatarTip}
				class={['officer-avatar', named && 'named']}
				data-shell={gateOn ? (sessionName ? 'operator-session' : 'operator-signin') : undefined}
			/>
			{#snippet content({ close })}{@render panel(close)}{/snippet}
		</Popover>
	{/if}
{:else}
	{#if officer}
		<span class="inline">
			<Tooltip content={locked ? lockTip : helper} placement="bottom">{@render field(false, false)}</Tooltip>
			<!-- the tooltip's text for screen readers too (the input's aria-describedby) -->
			<span class="sr" id="{uid}-tip">{locked ? lockTip : helper}</span>
		</span>
	{/if}
	{#if gateOn}
		<Popover placement="bottom-end" bind:open aria-label={t(lang, 'signin_title')}>
			{#if sessionName}
				<NavButton
					icon={OFFICER_ICON}
					iconOnly={!!officer}
					tip={t(lang, 'shell_officer_signed', sessionName)}
					data-shell="operator-session"
					data-officer={sessionName}>{#if !officer}<span class="name opt-lbl">{sessionName}</span>{/if}</NavButton
				>
			{:else}
				<NavButton icon={OFFICER_ICON} tip={t(lang, 'signin_note')} data-shell="operator-signin"
					><span class="opt-lbl">{officer ? t(lang, 'signin_submit') : t(lang, 'signin_open')}</span></NavButton
				>
			{/if}
			{#snippet content({ close })}
				<div class="panel" class:wide={!sessionName}>
					<div class="head">{sessionName ? t(lang, 'shell_officer') : t(lang, 'signin_title')}</div>
					{@render sessionBlock()}
					{#if sessionName}<div class="row-end"><Button small onclick={close}>{t(lang, 'shell_officer_done')}</Button></div>{/if}
				</div>
			{/snippet}
		</Popover>
	{/if}
{/if}

<style>
	.inline {
		display: inline-flex;
		flex: 0 0 auto;
		width: 168px;
		margin: 0 2px;
	}

	.inline :global(.officer-input) {
		width: 100%;
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	.lock {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		color: var(--v-ink-2);
	}

	.clear {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		padding: 0;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: transparent;
		color: var(--v-ink-2);
		cursor: pointer;
	}

	.clear:hover {
		background: var(--v-minimal-hover);
		color: var(--v-ink-1);
	}

	.clear:focus-visible {
		outline: 2px solid var(--v-focus);
	}

	.panel {
		display: flex;
		flex-direction: column;
		gap: 12px;
		box-sizing: border-box;
		width: 320px;
		padding: 16px;
	}

	.panel.wide {
		width: 340px;
	}

	.head {
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: calc(var(--v-text-base) + 2px);
	}

	.help {
		margin: 4px 0 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.session {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.who {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: var(--v-text-base);
	}

	.who :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.row-end {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
	}

	.name {
		max-width: 140px;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	:global(.officer-avatar.named) :global([data-ui='icon']) {
		color: var(--v-ink-1);
	}
</style>
