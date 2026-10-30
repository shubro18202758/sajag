<script lang="ts">
	/**
	 * OperatorSignIn — the duty-officer sign-in of the opt-in operator gate
	 * (SAJAG_OPERATOR_PIN). Gate off: renders nothing.
	 *
	 * - `inline`: the sign-in form itself (`data-shell="operator-signin-form"`,
	 *   inputs `signin-officer` and `signin-pin`), shown only while the gate is
	 *   on and nobody is signed in. The navbar's duty-officer popover and the
	 *   /ops sign-in card embed it.
	 * - otherwise: a control (`data-shell="operator-signin"`) that opens the
	 *   form in a Dialog, or, signed in, who is on duty
	 *   (`data-shell="operator-session"`, `data-officer`) and Sign out.
	 *
	 * After a sign-in or sign-out the page reloads, so every panel re-reads its
	 * feeds under the new session (no stale 403s left on screen); the reload
	 * keeps the URL hash, so a shared view restores.
	 */
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import { INTENT_ICON } from '$lib/design/icons';
	import Button from '$lib/ui/Button.svelte';
	import Dialog from '$lib/ui/Dialog.svelte';
	import FormGroup from '$lib/ui/FormGroup.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import Input from '$lib/ui/Input.svelte';
	import { OFFICER_ICON } from './icons';
	import { operatorSession } from './session.svelte';

	let { lang, inline = false }: { lang: string; inline?: boolean } = $props();

	const uid = $props.id();
	let open = $state(false);
	let officer = $state('');
	let pin = $state('');

	onMount(() => {
		void operatorSession.refresh();
	});

	async function submit() {
		if (await operatorSession.signIn(officer.trim(), pin)) {
			pin = '';
			open = false;
			location.reload();
		}
	}

	async function signOut() {
		await operatorSession.signOut();
		location.reload();
	}
</script>

{#snippet signinForm(autofocus: boolean)}
	<form
		class="signin"
		data-shell="operator-signin-form"
		onsubmit={(e) => {
			e.preventDefault();
			void submit();
		}}
	>
		<p class="note">{t(lang, 'signin_note')}</p>
		<FormGroup label={t(lang, 'signin_officer')} labelFor="{uid}-officer">
			<Input
				id="{uid}-officer"
				fill
				bind:value={officer}
				autocomplete="name"
				minlength={2}
				maxlength={64}
				required
				data-testid="signin-officer"
				data-autofocus={autofocus ? '' : undefined}
				{lang}
			/>
		</FormGroup>
		<FormGroup label={t(lang, 'signin_pin')} labelFor="{uid}-pin">
			<Input
				id="{uid}-pin"
				fill
				type="password"
				bind:value={pin}
				autocomplete="current-password"
				inputmode="numeric"
				required
				data-testid="signin-pin"
				{lang}
			/>
		</FormGroup>
		{#if operatorSession.error}
			<p class="error" role="alert">
				<Icon name={INTENT_ICON.danger} size={16} />
				{operatorSession.error === 'throttled' ? t(lang, 'signin_throttled') : t(lang, 'signin_refused')}
			</p>
		{/if}
		<div class="actions">
			<Button type="submit" intent="primary" loading={operatorSession.busy} disabled={officer.trim().length < 2 || !pin}>
				{t(lang, 'signin_submit')}
			</Button>
		</div>
	</form>
{/snippet}

{#if inline}
	{#if operatorSession.gate && !operatorSession.officer}
		{@render signinForm(false)}
	{/if}
{:else}
	{#if operatorSession.gate}
		{#if operatorSession.officer}
			<span class="on-duty" data-shell="operator-session" data-officer={operatorSession.officer}>
				<Icon name={OFFICER_ICON} size={16} />
				<span class="who">{t(lang, 'signin_on_duty')}: {operatorSession.officer}</span>
				<Button small minimal onclick={() => void signOut()}>{t(lang, 'signin_signout')}</Button>
			</span>
		{:else}
			<Button small icon={OFFICER_ICON} data-shell="operator-signin" onclick={() => (open = true)}>
				{t(lang, 'signin_open')}
			</Button>
		{/if}
	{/if}

	<Dialog bind:open title={t(lang, 'signin_title')} icon={OFFICER_ICON} width={380} {lang}>
		{@render signinForm(true)}
	</Dialog>
{/if}

<style>
	.signin {
		display: flex;
		flex-direction: column;
		gap: 0;
		min-width: 0;
		font-family: var(--v-font-ui);
	}

	.note {
		margin: 0 0 12px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.error {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		margin: 0 0 12px;
		color: var(--v-ink-1);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.error :global([data-ui='icon']) {
		color: var(--v-ink-2);
		flex: 0 0 auto;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
	}

	.on-duty {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.on-duty :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.who {
		color: var(--v-ink-1);
		white-space: nowrap;
	}
</style>
