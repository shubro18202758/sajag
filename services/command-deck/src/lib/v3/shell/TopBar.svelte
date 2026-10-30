<script lang="ts">
	/**
	 * TopBar (V3-SPEC §3.1, §5.1; slimmed by the colleague review, V3-P4B) — ONE line, the same on every V3 page:
	 *
	 *   the screen title   one line, never a second line of status (that moved into the menu)
	 *   SEARCH             the prominent element, centred: "Search a place, road, event or vehicle mark"; it opens the
	 *                      page's own Omnibar (commandBar.onSearch — unchanged grammar; ⌘K and `/` stay the Omnibar's)
	 *   the menu           HeaderMenu: the page's status line, the language switch (sajag_lang through the shell's
	 *                      onLangPick), the Exercise data statement (v2 ExercisePanel) and the data status (v2
	 *                      DataPanel) — one compact control; it carries the exercise flask while closed (honest labels)
	 *   report by voice    FieldReportEntry (lib/v3/field): the one entry point to the voice field report sheet
	 *   alerts             AlertsButton, unchanged
	 *   the duty officer   the pill that opens the v2 OfficerControl (the `duty-officer` input, its `.officer-input`
	 *                      class, the operator gate's sign-in and sign-out, the honest helper) — test ids and the gate's
	 *                      behaviour unchanged
	 *
	 * Below 1500 px the bar is 60 px and the search loses its key hint.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import '../packs.v3';
	import Popover from '$lib/ui/Popover.svelte';
	import OfficerControl from '$lib/shell/OfficerControl.svelte';
	import { operatorSession } from '$lib/shell/session.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import Glyph from '../Glyph.svelte';
	import AlertsButton from './AlertsButton.svelte';
	import HeaderMenu from './HeaderMenu.svelte';
	import FieldReportEntry from '../field/FieldReportEntry.svelte';

	let {
		title,
		sub,
		lang,
		onLangPick,
	}: { title: string; sub: string | null; lang: string; onLangPick: (code: string) => void } = $props();

	const officer = $derived(commandBar.officer);
	const sessionName = $derived(operatorSession.officer);
	const name = $derived((officer?.value ?? sessionName ?? '').trim());
	const named = $derived(name.length >= 2);
	const fromSession = $derived(!!officer?.fromSession || (operatorSession.gate === true && !!sessionName));
	const search = $derived(commandBar.onSearch);

	let officerOpen = $state(false);

	/** Opening the officer panel puts the cursor in its first field (the name, or the sign-in form's), as the v2 navbar's popover did. */
	function focusFirstField(node: HTMLElement) {
		node.querySelector<HTMLElement>('input:not([type="hidden"]), textarea')?.setAttribute('data-autofocus', '');
	}
</script>

<header class="top" data-v3="top-bar">
	<div class="title">
		<h1 class="t" data-v3="screen-title">{title}</h1>
	</div>

	<button
		type="button"
		class="search"
		disabled={!search}
		aria-label={t(lang, 'v3_search_open')}
		aria-haspopup="dialog"
		data-shell="command-search"
		data-mode="omnibar"
		onclick={() => search?.('')}
	>
		<Glyph name="search" size={20} />
		<span class="ph">{t(lang, 'v3_search')}</span>
		<kbd class="kbd" aria-hidden="true">Ctrl K</kbd>
	</button>

	<div class="right">
		<HeaderMenu {lang} status={sub} exercise={commandBar.exercise} dataStatus={commandBar.dataStatus} {onLangPick} />

		<FieldReportEntry {lang} officer={named ? name : null} />

		<AlertsButton {lang} />

		<Popover placement="bottom-end" class="v3-pop" bind:open={officerOpen} aria-label={t(lang, 'shell_officer')}>
			<button
				type="button"
				class={['officer', named && 'named']}
				data-testid="v3-officer"
				data-named={named ? 'true' : 'false'}
				title={named ? t(lang, 'shell_officer_helper') : t(lang, 'v3_officer_tip_none')}
			>
				<span class="av"><Glyph name={named ? 'badge' : 'lock'} size={18} /></span>
				<span class="who">
					<b>{named ? name : t(lang, 'v3_officer_none')}</b>
					<small>{named ? t(lang, fromSession ? 'v3_officer_signed' : 'v3_officer_on') : t(lang, 'v3_officer_plates')}</small>
				</span>
			</button>
			{#snippet content({ close })}
				<div class="officer-pop" data-v3="officer-panel" use:focusFirstField>
					<div class="op-head">{t(lang, 'v3_officer_title')}</div>
					<OfficerControl officer={commandBar.officer} compact={false} {lang} />
					<p class="op-help">{t(lang, 'shell_officer_helper')}</p>
					<div class="op-end"><button type="button" class="op-done" onclick={close}>{t(lang, 'shell_officer_done')}</button></div>
				</div>
			{/snippet}
		</Popover>
	</div>
</header>

<style>
	/* three columns: the title, the search centred, the cluster — the search is the bar's one prominent element */
	.top {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(280px, 680px) minmax(max-content, 1fr);
		align-items: center;
		gap: 20px;
		min-width: 0;
		height: var(--v3-top);
		padding: 0 var(--v3-gut);
		border-bottom: 1px solid var(--v3-line-1);
		background: var(--v3-bg);
		color: var(--v3-t1);
	}

	/* the title takes what is left and truncates: the search and every control sit at the SAME pixels on every V3 page
	   (the three columns do not depend on the title; the cluster's controls have fixed widths per officer state) */
	.title {
		min-width: 0;
	}

	.t {
		margin: 0;
		font-size: 18px;
		line-height: 24px;
		font-weight: 650;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.search {
		display: flex;
		align-items: center;
		gap: 12px;
		width: 100%;
		min-width: 0;
		height: 46px;
		padding: 0 10px 0 18px;
		border: 1px solid var(--v3-line-3);
		border-radius: 23px;
		background: var(--v3-s2);
		box-shadow: var(--v3-elev-1);
		color: var(--v3-t2);
		font: inherit;
		font-size: var(--v3-text-body);
		text-align: left;
		cursor: text;
		transition: border-color var(--v3-dur-1) var(--v3-ease), background var(--v3-dur-1) var(--v3-ease);
	}

	.search :global(.v3-glyph) {
		color: var(--v3-brand-text);
	}

	.search:hover:not(:disabled) {
		border-color: var(--v3-brand);
		background: var(--v3-s3);
	}

	.search .ph {
		flex: 1;
		min-width: 0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.kbd {
		padding: 0 6px;
		border: 1px solid var(--v3-line-2);
		border-bottom-width: 2px;
		border-radius: 6px;
		background: var(--v3-s2);
		color: var(--v3-t2);
		font: 600 12px/18px var(--v-font-ui);
	}

	.right {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 10px;
		min-width: max-content;
	}

	.officer {
		display: flex;
		align-items: center;
		gap: 10px;
		height: var(--v3-ctl-lg);
		max-width: 260px;
		padding: 0 16px 0 6px;
		border: 1px solid var(--v3-line-2);
		border-radius: 22px;
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		text-align: left;
		white-space: nowrap;
		cursor: pointer;
	}

	.officer:hover {
		border-color: var(--v3-line-3);
	}

	.av {
		display: grid;
		place-items: center;
		flex: none;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		background: var(--v3-s3);
		color: var(--v3-t2);
	}

	.officer.named .av {
		background: var(--v3-brand-veil);
		color: var(--v3-brand-text);
	}

	.who {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.who b {
		overflow: hidden;
		text-overflow: ellipsis;
		font-size: 14px;
		line-height: 17px;
		font-weight: 640;
	}

	.who small {
		color: var(--v3-t3);
		font-size: 12px;
		line-height: 14px;
		font-weight: 600;
	}

	.officer-pop {
		display: flex;
		flex-direction: column;
		gap: 12px;
		width: 340px;
		padding: 18px;
	}

	.op-head {
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 620;
	}

	.officer-pop :global(.inline) {
		width: 100%;
		margin: 0;
	}

	.op-help {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 19px;
	}

	.op-end {
		display: flex;
		justify-content: flex-end;
	}

	.op-done {
		height: var(--v3-ctl);
		padding: 0 16px;
		border: 0;
		border-radius: 18px;
		background: var(--v3-s3);
		color: var(--v3-t1);
		font: inherit;
		font-size: 14px;
		font-weight: 650;
		cursor: pointer;
	}

	.op-done:hover {
		background: var(--v3-s4);
	}

	.search:focus-visible,
	.officer:focus-visible,
	.op-done:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	:global(div.popover.v3-pop) {
		border-radius: var(--v3-radius-l);
		background: var(--v3-s2);
		box-shadow:
			0 0 0 1px var(--v3-line-2),
			var(--v3-elev-2);
		color: var(--v3-t1);
	}

	:global(:lang(hi)) .who b,
	:global(:lang(mr)) .who b {
		font-size: 15px;
		line-height: 1.4;
	}

	@media (max-width: 1500px) {
		.top {
			gap: 14px;
		}

		.kbd {
			display: none;
		}

		.top {
			grid-template-columns: minmax(0, 1fr) minmax(240px, 560px) minmax(max-content, 1fr);
		}

		.search {
			height: 44px;
		}
	}

	/* a phone: no screen title (the tab bar names the page), the search takes what is left, the officer is its badge */
	@media (max-width: 720px) {
		.top {
			grid-column: 1;
			grid-template-columns: minmax(0, 1fr) auto;
			gap: 8px;
			padding: 0 12px;
		}

		.title {
			display: none;
		}

		.search {
			height: 40px;
			gap: 8px;
			padding: 0 12px;
		}

		.right {
			gap: 6px;
		}

		.officer {
			height: 40px;
			padding: 0 3px;
			border-radius: 20px;
		}

		.who {
			display: none;
		}

		.officer-pop {
			width: min(340px, calc(100vw - 32px));
		}
	}
</style>
