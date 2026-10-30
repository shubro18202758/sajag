<script lang="ts">
	/**
	 * "Who is launching?" (V3-SPEC §9.1) — the planner's officer gate. AI or a rule proposes; a NAMED officer starts
	 * the escort. The name is the CONSOLE's duty officer (the top bar's control and this field are one person: the
	 * page's commandBar.officer, i.e. ops.setDutyOfficer); it is set on Continue or Enter, never per keystroke, so a
	 * half-typed name never unmasks a mark nor unlocks the launch. The helper is §9.1's sentence, word for word.
	 * With the operator gate on, the signed-in officer is shown, locked.
	 */
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { t } from '$lib/i18n/strings';
	import Glyph from '../Glyph.svelte';
	import './packs.plan';

	/** launch: "Who is launching?" · live: "Who is on duty?" (the escort's Stop). */
	let { lang, context = 'launch' }: { lang: string; context?: 'launch' | 'live' } = $props();

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
	<div class="who" data-testid="v3-plan-officer-named">
		<span class="av"><Glyph name="badge" size={18} /></span>
		<span class="txt">
			<span class="k">{fromSession ? L('v3p_signed_as') : context === 'live' ? L('v3p_as_live') : L('v3p_as')}</span>
			<b data-testid="v3-plan-officer-name">{officer}</b>
		</span>
		{#if !fromSession}<button type="button" class="link" onclick={change}>{L('v3p_change')}</button>{/if}
		<span class="audit">{L('v3p_recorded')}</span>
	</div>
{:else}
	<div class="gate" data-testid="v3-plan-officer-gate">
		<label class="lbl" for="v3p-who-{uid}">{context === 'live' ? L('v3p_who_live') : L('v3p_who')}</label>
		<div class="row">
			<input
				bind:this={field}
				id="v3p-who-{uid}"
				class="inp"
				data-testid="v3-plan-officer"
				placeholder={L('v3p_who_ph')}
				autocomplete="off"
				spellcheck={false}
				maxlength={64}
				aria-describedby="v3p-who-help-{uid}"
				bind:value={draft}
				onkeydown={(e) => {
					if (e.key === 'Enter') {
						e.preventDefault();
						apply();
					}
				}}
			/>
			<button type="button" class="go" data-testid="v3-plan-officer-continue" disabled={!ready} onclick={apply}>{L('v3p_who_go')}</button>
		</div>
		<p class="help" id="v3p-who-help-{uid}">{L('v3p_who_help')}</p>
	</div>
{/if}

<style>
	.who {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: center;
		column-gap: 12px;
		padding: 12px 14px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.av {
		display: grid;
		place-items: center;
		width: 36px;
		height: 36px;
		border-radius: 50%;
		background: var(--v3-brand-veil);
		color: var(--v3-brand-text);
	}

	.txt {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.k {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 650;
	}

	.txt b {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 650;
	}

	.audit {
		grid-column: 2 / span 2;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.link {
		padding: 4px 6px;
		border: 0;
		background: none;
		color: var(--v3-brand-text);
		font: inherit;
		font-size: var(--v3-text-meta);
		font-weight: 650;
		cursor: pointer;
	}

	.gate {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 14px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		box-shadow: inset 0 0 0 1px var(--v3-decide-line);
	}

	.lbl {
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
		font-weight: 650;
	}

	.row {
		display: flex;
		gap: 8px;
	}

	.inp {
		flex: 1;
		min-width: 0;
		height: var(--v3-ctl-lg);
		padding: 0 14px;
		border: 1px solid var(--v3-line-3);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		font-size: var(--v3-text-body);
	}

	.inp::placeholder {
		color: var(--v3-t3);
	}

	.go {
		height: var(--v3-ctl-lg);
		padding: 0 18px;
		border: 0;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s4);
		color: var(--v3-t1);
		font: inherit;
		font-size: var(--v3-text-body);
		font-weight: 650;
		cursor: pointer;
	}

	.go:disabled {
		color: var(--v3-t3);
		cursor: not-allowed;
	}

	.help {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.inp:focus-visible,
	.go:focus-visible,
	.link:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}
</style>
