<script lang="ts">
	/**
	 * OfficerGate (V3-SPEC §5.3, §9.1) — "Who is deciding?" on every decision. AI or a rule proposes; a NAMED
	 * officer decides (ethics rule 6).
	 *
	 *   no officer   the field (`decision-officer`, as on the duty roster) + Continue, and the honest helper,
	 *                word for word: "Naming yourself shows full registration marks on this console and records
	 *                your name with the decision. Attribution, not sign-in." The sheet's buttons stay visible
	 *                but disabled, with the reason, until a name is given;
	 *   named        "Deciding as R. Mehta · Change · Recorded in the audit trail";
	 *   signed in    (operator gate on) the session's officer, locked: no Change.
	 *
	 * The name is the CONSOLE's duty officer (the top bar's control and this field are the same person): it is
	 * set on Continue / Enter, never per keystroke, so a half-typed name never unmasks anything.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { t } from '$lib/i18n/strings';
	import Glyph from '../Glyph.svelte';
	import './packs.decide';

	let { lang }: { lang: string } = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const uid = $props.id();

	const officer = $derived((commandBar.officer ? commandBar.officer.value : ops.dutyOfficer).trim());
	const fromSession = $derived(commandBar.officer ? commandBar.officer.fromSession : ops.dutyOfficerFromSession);
	const named = $derived(officer.length >= 2);

	let editing = $state(false);
	let draft = $state('');
	let field = $state<HTMLInputElement | null>(null);

	const ready = $derived(draft.trim().length >= 2);

	function apply() {
		const v = draft.trim();
		if (v.length < 2 || fromSession) return;
		if (commandBar.officer) commandBar.officer.set(v);
		else ops.setDutyOfficer(v);
		editing = false;
	}

	function change() {
		draft = officer;
		editing = true;
		queueMicrotask(() => field?.focus());
	}
</script>

{#if named && !editing}
	<div class="who" data-testid="v3-officer-named">
		<span class="av"><Glyph name="badge" size={16} /></span>
		<span class="txt">
			{fromSession ? L('v3d_signed_as') : L('v3d_deciding_as')} <b data-testid="v3-officer-name">{officer}</b>
			{#if !fromSession}
				<span class="dot" aria-hidden="true">·</span>
				<button type="button" class="link" onclick={change}>{L('v3d_change')}</button>
			{/if}
		</span>
		<span class="audit">{L('v3d_recorded')}</span>
	</div>
{:else}
	<div class="gate" data-testid="v3-officer-gate">
		<label class="lbl" for="v3d-who-{uid}">{L('v3d_who')}</label>
		<div class="row">
			<input
				bind:this={field}
				id="v3d-who-{uid}"
				class="field"
				data-testid="decision-officer"
				placeholder={L('v3d_who_placeholder')}
				autocomplete="off"
				spellcheck={false}
				maxlength={120}
				aria-describedby="v3d-who-help-{uid}"
				bind:value={draft}
				onkeydown={(e) => {
					if (e.key === 'Enter') {
						e.preventDefault();
						apply();
					} else if (e.key === 'Escape' && named) {
						e.preventDefault();
						editing = false;
					}
				}}
			/>
			<button type="button" class="btn secondary" data-testid="v3-officer-continue" aria-disabled={!ready} onclick={apply}>{L('v3d_continue')}</button>
		</div>
		<p class="help" id="v3d-who-help-{uid}"><Glyph name="info" size={16} />{L('v3d_officer_helper')}</p>
	</div>
{/if}

<style>
	.who {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 14px;
		line-height: 20px;
		color: var(--v3-t2);
	}

	.av {
		display: grid;
		place-items: center;
		flex: none;
		width: 30px;
		height: 30px;
		border-radius: 15px;
		background: var(--v3-brand-veil);
		color: var(--v3-brand-text);
	}

	.txt {
		min-width: 0;
	}

	.txt b {
		color: var(--v3-t1);
		font-weight: 650;
	}

	.dot {
		margin: 0 4px;
		color: var(--v3-t3);
	}

	.audit {
		margin-left: auto;
		font-size: var(--v3-text-micro);
		font-weight: 600;
		color: var(--v3-t3);
		text-align: right;
	}

	.link {
		padding: 0;
		border: 0;
		background: none;
		color: var(--v3-brand-text);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	.link:focus-visible,
	.field:focus-visible,
	.btn:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.gate {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.lbl {
		font-size: var(--v3-text-meta);
		font-weight: 600;
		color: var(--v3-t2);
	}

	.row {
		display: flex;
		gap: 10px;
	}

	.field {
		flex: 1;
		min-width: 0;
		height: var(--v3-ctl-lg);
		padding: 0 14px;
		border: 1px solid var(--v3-line-2);
		border-radius: 12px;
		background: var(--v3-s2);
		color: var(--v3-t1);
		font: inherit;
		font-size: 15px;
	}

	.field::placeholder {
		color: var(--v3-t3);
	}

	.btn {
		flex: none;
		height: var(--v3-ctl-lg);
		padding: 0 18px;
		border: 1px solid var(--v3-line-2);
		border-radius: 22px;
		background: var(--v3-s3);
		color: var(--v3-t1);
		font: inherit;
		font-size: 15px;
		font-weight: 650;
		cursor: pointer;
	}

	.btn[aria-disabled='true'] {
		color: var(--v3-t3);
		cursor: not-allowed;
	}

	.help {
		display: flex;
		gap: 8px;
		align-items: flex-start;
		margin: 0;
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		color: var(--v3-t2);
	}

	.help :global(svg) {
		margin-top: 1px;
	}
</style>
