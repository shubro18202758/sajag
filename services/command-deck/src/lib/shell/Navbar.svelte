<script lang="ts">
	/**
	 * Navbar (SPEC §5.3, §3.7) — the 50 px Blueprint navbar of the operator
	 * shell (`data-shell="command-bar"`). Left to right: the product mark, the
	 * five module buttons (.is-pressed on the active one), the search box
	 * (`data-shell="command-search"`), then the right group: band tag,
	 * Exercise data, Data, Policies, legacy Share, Inbox, language switch, the
	 * duty officer, More.
	 *
	 * Every control a PAGE owns renders only when the page supplied its field
	 * (plan R10/X12): `officer` → `duty-officer`, `dataStatus` →
	 * `brain-posture`, `exercise` → `feed-provenance`, `onShare` → the legacy
	 * Share, `onInbox`/`inboxCount` → Inbox. Search calls the page's omnibar
	 * (`onSearch`); without one it is the navbar's own route search ('/'
	 * focuses it, Enter goes, Esc clears then leaves) and ⌘K stays with the
	 * page.
	 *
	 * Responsive in three steps: ≥ 1680 full; 1440–1679 icon-only modules,
	 * search 300, Policies icon-only; 1280–1439 search 240 without the key
	 * hint, Data, Policies and the language fold into More (still in the DOM,
	 * hidden), the city name hides and the officer input becomes an avatar
	 * whose popover holds the same input. The bar never widens the page.
	 *
	 * Fit (no control is ever clipped): what a step shows depends on the
	 * fields the page supplied, the operator gate and the language, so after
	 * every change that moves the bar's content the navbar measures itself.
	 * The search gives way first: from 1680 it shrinks from 380 toward 240
	 * before any label folds (the full step keeps its labels, §3.7); at
	 * 1440–1679 it holds its 300 (the step's width); below 1440 it is 240.
	 * While the right group would still pass the bar's edge, or the search
	 * would be narrower than that floor, the bar frees width one fold at a
	 * time, in this order (`fit-1` … `fit-5`), least information first:
	 *   1. the city name hides (the 1280–1439 step hides it anyway);
	 *   2. the 4 px spacers go; Share, Sign-in and the signed-in name become
	 *      icon-only (their text stays the accessible name; the tooltip says it);
	 *   3. the band tag's "Band" key becomes its glyph (the word stays for
	 *      screen readers; the band value and its swatch always show);
	 *   4. Policies becomes icon-only;
	 *   5. the module buttons become icon-only.
	 * Once the bar fits, every earlier fold the last one made unnecessary is
	 * given back (the latest first), so a big fold never leaves small ones
	 * standing for nothing. `data-fit` lists the folds in force ("0": none).
	 * The Exercise-data tag, the band value, the Data button, the Inbox, the
	 * language switch, the officer control and More never fold this way.
	 */
	import { onMount, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { SUPPORTED, t } from '$lib/i18n/strings';
	import Icon from '$lib/ui/Icon.svelte';
	import Kbd from '$lib/ui/Kbd.svelte';
	import Popover from '$lib/ui/Popover.svelte';
	import Tag from '$lib/ui/Tag.svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';
	import BandTag from './BandTag.svelte';
	import { commandBar } from './command-bar.svelte';
	import DataPanel, { dataSummary } from './DataPanel.svelte';
	import ExercisePanel from './ExercisePanel.svelte';
	import {
		DATA_ICON,
		EMULATED_ICON,
		INBOX_ICON,
		POLICIES_ICON,
		SEARCH_ICON,
		SHARE_ICON
	} from './icons';
	import MoreMenu from './MoreMenu.svelte';
	import { MODULES, NAV_INDEX, moduleActive } from './nav';
	import NavButton from './NavButton.svelte';
	import OfficerControl from './OfficerControl.svelte';
	import PoliciesPanel from './PoliciesPanel.svelte';
	import { operatorSession } from './session.svelte';

	interface Props {
		pathname: string;
		/** The operator picked a language (persisted by the shell). */
		onLangPick: (code: string) => void;
		/** Open the shortcuts dialog. */
		onShortcuts: () => void;
		/** The fallback search input (the shell focuses it on '/'). */
		searchEl?: HTMLInputElement | null;
	}

	let { pathname, onLangPick, onShortcuts, searchEl = $bindable(null) }: Props = $props();

	const lang = $derived(commandBar.lang);

	// SSR renders the full bar; the client knows its width (the officer avatar
	// below 1440 px is a different element, not a hidden one: one duty-officer)
	let width = $state(1920);
	const compact = $derived(width < 1440);

	// ── search ────────────────────────────────────────────────────────────
	const omni = $derived(commandBar.onSearch);
	let q = $state('');
	const matches = $derived.by(() => {
		const needle = q.trim().toLowerCase();
		if (!needle) return [];
		return NAV_INDEX.filter((n) => n.terms.includes(needle) || t(lang, n.key).toLowerCase().includes(needle));
	});

	function searchKeydown(e: KeyboardEvent) {
		if (omni) {
			// the page's omnibar takes the search: open it with what was typed
			if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
				e.preventDefault();
				omni(e.key);
			} else if (e.key === 'Enter' || e.key === 'ArrowDown') {
				e.preventDefault();
				omni('');
			}
			return;
		}
		if (e.key === 'Escape') {
			// Esc closes, then clears: never navigates
			e.preventDefault();
			e.stopPropagation();
			if (q) q = '';
			else searchEl?.blur();
		} else if (e.key === 'Enter' && matches.length > 0) {
			const href = matches[0].href;
			q = '';
			searchEl?.blur();
			void goto(href);
		}
	}

	// ── inbox ─────────────────────────────────────────────────────────────
	const inboxShown = $derived(!!commandBar.onInbox || commandBar.inboxCount > 0);
	const inboxTip = $derived(
		commandBar.inboxIntent === 'danger'
			? t(lang, 'shell_inbox_watchlist')
			: commandBar.inboxCount > 0
				? t(lang, 'shell_inbox_waiting', commandBar.inboxCount)
				: t(lang, 'shell_inbox_none')
	);

	// ── data ──────────────────────────────────────────────────────────────
	const summary = $derived(commandBar.dataStatus ? dataSummary(lang, commandBar.dataStatus) : '');

	// ── fit: fold, then give back, until nothing is clipped ───────────────
	const FIT_MAX = 5;
	/** The 1440–1679 step's search width (§3.7): held there while other things fold. */
	const SEARCH_FLOOR_MID = 300;
	/** The narrowest the search ever gets (the 1280–1439 width; the full step shrinks to it first). */
	const SEARCH_MIN = 240;
	let navEl = $state<HTMLElement | null>(null);
	let rightEl = $state<HTMLElement | null>(null);
	let searchBox = $state<HTMLElement | null>(null);
	/** The folds in force (1…FIT_MAX), ascending. */
	let folds = $state<number[]>([]);

	function applyFolds(nav: HTMLElement, on: Set<number>) {
		for (let i = 1; i <= FIT_MAX; i++) nav.classList.toggle(`fit-${i}`, on.has(i));
	}

	/**
	 * Measure synchronously (the browser paints only the final state): fold
	 * in order until the right group ends inside the bar's padding and the
	 * search is at least its floor, then give back each earlier fold that is
	 * no longer needed.
	 */
	function measureFit() {
		const nav = navEl;
		const right = rightEl;
		const box = searchBox;
		if (!nav || !right || !box) return;
		const vw = window.innerWidth;
		const floor = vw >= 1440 && vw < 1680 ? SEARCH_FLOOR_MID : SEARCH_MIN;
		const pad = parseFloat(getComputedStyle(nav).paddingRight) || 0;
		const tight = () =>
			right.getBoundingClientRect().right > nav.getBoundingClientRect().right - pad + 0.5 ||
			box.getBoundingClientRect().width < floor - 0.5;
		const on = new Set<number>();
		applyFolds(nav, on);
		let level = 0;
		while (level < FIT_MAX && tight()) {
			on.add(++level);
			applyFolds(nav, on);
		}
		for (let i = level - 1; i >= 1; i--) {
			on.delete(i);
			applyFolds(nav, on);
			if (tight()) {
				on.add(i);
				applyFolds(nav, on);
			}
		}
		folds = [...on].sort((a, b) => a - b);
	}

	/** Everything that moves the bar's content width (presence, not identity: a page re-assigning the same fields does not re-measure). */
	const fitKey = $derived(
		[
			width,
			lang,
			!!commandBar.officer,
			!!commandBar.dataStatus,
			!!commandBar.exercise,
			!!commandBar.onShare,
			!!commandBar.onSearch,
			inboxShown,
			commandBar.inboxCount,
			commandBar.inboxIntent,
			commandBar.band ?? '',
			commandBar.bandSource ?? '',
			operatorSession.gate === true,
			operatorSession.officer ?? ''
		].join('|')
	);

	$effect(() => {
		void fitKey;
		void navEl;
		void rightEl;
		void searchBox;
		untrack(measureFit);
	});

	onMount(() => {
		// web fonts (and the Devanagari / Marathi faces on a language switch)
		// change every label's width when they arrive
		const fonts = document.fonts;
		const again = () => measureFit();
		void fonts?.ready.then(again);
		fonts?.addEventListener?.('loadingdone', again);
		return () => fonts?.removeEventListener?.('loadingdone', again);
	});
</script>

<svelte:window bind:innerWidth={width} />

<header
	class={[
		'navbar',
		folds.includes(1) && 'fit-1',
		folds.includes(2) && 'fit-2',
		folds.includes(3) && 'fit-3',
		folds.includes(4) && 'fit-4',
		folds.includes(5) && 'fit-5'
	]}
	data-shell="command-bar"
	data-step={width >= 1680 ? 'full' : compact ? 'compact' : 'mid'}
	data-fit={folds.length ? folds.join(' ') : '0'}
	bind:this={navEl}
>
	<a class="brand" href="/" aria-label={t(lang, 'shell_home')}>
		<span class="mark" aria-hidden="true"><img src="/brand/sajag-mark-solid.svg" alt="" width="18" height="18" /></span>
		<span class="name">{t(lang, 'shell_mark')}</span>
		<span class="city">{t(lang, 'shell_city')}</span>
	</a>
	<span class="sep" aria-hidden="true"></span>

	<nav class="mods" aria-label={t(lang, 'shell_modules')}>
		{#each MODULES as m (m.id)}
			{@const active = moduleActive(m, pathname)}
			<Tooltip content={t(lang, 'shell_module_tip', t(lang, m.key), m.hotkey)} placement="bottom">
				<a
					class={['mod', active && 'is-pressed']}
					href={m.href}
					aria-label={t(lang, m.key)}
					aria-current={active ? 'page' : undefined}
					data-module={m.id}
				>
					<Icon name={m.icon} size={16} />
					<span class="lbl">{t(lang, m.key)}</span>
				</a>
			</Tooltip>
		{/each}
	</nav>

	<div class="search" role="search" bind:this={searchBox}>
		<Icon name={SEARCH_ICON} size={16} class="s-ic" />
		{#if omni}
			<input
				class="s-in"
				type="search"
				readonly
				bind:this={searchEl}
				placeholder={t(lang, 'shell_search_omni')}
				aria-label={t(lang, 'shell_search_omni')}
				aria-haspopup="dialog"
				data-shell="command-search"
				data-mode="omnibar"
				onclick={() => omni?.('')}
				onkeydown={searchKeydown}
			/>
			<span class="keys"><Kbd keys={['Ctrl', 'K']} /></span>
		{:else}
			<input
				class={['s-in', q.trim() && 'hinted']}
				type="search"
				bind:this={searchEl}
				bind:value={q}
				placeholder={t(lang, 'shell_search')}
				aria-label={t(lang, 'shell_search')}
				autocomplete="off"
				spellcheck="false"
				data-shell="command-search"
				data-mode="routes"
				onkeydown={searchKeydown}
			/>
			{#if q.trim()}
				<span class="keys hint">{matches.length ? t(lang, 'shell_search_go', t(lang, matches[0].key)) : t(lang, 'shell_search_none')}</span>
			{:else}
				<span class="keys"><Kbd keys={['/']} /></span>
			{/if}
		{/if}
	</div>

	<div class="right" bind:this={rightEl}>
		<BandTag band={commandBar.band} bandSource={commandBar.bandSource} bandAgeSec={commandBar.bandAgeSec} {lang} />

		{#if commandBar.exercise}
			{@const ex = commandBar.exercise}
			<Popover placement="bottom-end" aria-label={t(lang, 'shell_exercise')}>
				<button type="button" class="ex-tag" data-testid="feed-provenance" data-label={ex.label}>
					<Tooltip content={ex.text} placement="bottom">
						<span class="ex-in"><Icon name={EMULATED_ICON} size={12} />{t(lang, 'shell_exercise')}</span>
					</Tooltip>
				</button>
				{#snippet content()}<ExercisePanel exercise={ex} {lang} />{/snippet}
			</Popover>
		{/if}

		{#if commandBar.dataStatus}
			{@const ds = commandBar.dataStatus}
			<span class="fold">
				<Popover placement="bottom-end" aria-label={t(lang, 'shell_data')}>
					<NavButton
						icon={DATA_ICON}
						iconOnly
						tip={summary}
						class="data-btn"
						data-testid="brain-posture"
						data-decider={ds.decider}
						data-tier={ds.tier}
						data-worst={ds.worst}
					>
						<i class="dot s-{ds.worst}" aria-hidden="true"></i><span class="sr">{summary}</span>
					</NavButton>
					{#snippet content()}<DataPanel status={ds} {lang} />{/snippet}
				</Popover>
			</span>
		{/if}

		<span class="fold">
			<Popover placement="bottom-end" aria-label={t(lang, 'shell_policies')}>
				<NavButton icon={POLICIES_ICON} tip={t(lang, 'shell_policies_tip')} class="policies" aria-label={t(lang, 'shell_policies')}>
					<span class="pol-lbl">{t(lang, 'shell_policies')}</span>
				</NavButton>
				{#snippet content()}<PoliciesPanel {lang} />{/snippet}
			</Popover>
		</span>

		{#if commandBar.onShare}
			{@const share = commandBar.onShare}
			<NavButton icon={SHARE_ICON} tip={folds.includes(2) ? t(lang, 'shell_share') : null} class="share" data-share="" onclick={() => share()}>
				<span class="opt-lbl">{t(lang, 'shell_share')}</span>
			</NavButton>
		{/if}

		{#if inboxShown}
			{@const n = commandBar.inboxCount}
			<NavButton
				icon={INBOX_ICON}
				tip={inboxTip}
				aria-label={inboxTip}
				class={['inbox', commandBar.inboxIntent !== 'none' && `i-${commandBar.inboxIntent}`]}
				data-inbox-intent={commandBar.inboxIntent}
				data-count={n}
				disabled={!commandBar.onInbox}
				onclick={() => commandBar.onInbox?.()}
			>
				{#if n > 0}<Tag round intent={commandBar.inboxIntent === 'none' ? 'none' : commandBar.inboxIntent}>{n}</Tag>{:else if commandBar.inboxIntent === 'danger'}<i class="dot s-alert" aria-hidden="true"></i>{/if}
			</NavButton>
		{/if}

		<span class="sep fold" aria-hidden="true"></span>
		<div class="lang fold" role="group" aria-label={t(lang, 'shell_language')}>
			{#each SUPPORTED as s (s.code)}
				<button
					type="button"
					lang={s.code}
					class={[lang === s.code && 'is-pressed']}
					aria-pressed={lang === s.code}
					title={s.label}
					data-lang-code={s.code}
					onclick={() => onLangPick(s.code)}>{s.short}</button
				>
			{/each}
		</div>

		<OfficerControl officer={commandBar.officer} {compact} {lang} />

		<MoreMenu {lang} {compact} dataStatus={commandBar.dataStatus} onLang={onLangPick} {onShortcuts} />
	</div>
</header>

<style>
	.navbar {
		position: relative;
		z-index: var(--v-z-content);
		display: flex;
		align-items: center;
		gap: 2px;
		box-sizing: border-box;
		height: var(--v-ws-navbar);
		min-width: 0;
		padding: 0 8px 0 12px;
		overflow: hidden;
		background: var(--v-surface-1);
		box-shadow: var(--v-elev-1);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	/* ── brand ── */
	.brand {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 8px;
		margin-right: 4px;
		color: inherit;
		text-decoration: none;
		white-space: nowrap;
	}

	.brand:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 2px;
		border-radius: var(--v-radius-btn);
	}

	/* the Sajag mark (the solid S: the truss closes up at this size) on its black tile */
	.mark {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 24px;
		height: 24px;
		border-radius: var(--v-radius-btn);
		background: var(--v-canvas);
		box-shadow: inset 0 0 0 1px var(--v-line-2);
	}

	.mark img {
		display: block;
		width: 18px;
		height: 18px;
	}

	.name {
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: 20px;
	}

	.city {
		color: var(--v-ink-2);
	}

	.sep {
		flex: 0 0 auto;
		width: 1px;
		height: 20px;
		margin: 0 8px;
		background: var(--v-line-2);
	}

	/* ── modules ── */
	.mods {
		display: flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 2px;
	}

	.mod {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		box-sizing: border-box;
		height: var(--v-ctl-md);
		min-width: var(--v-ctl-md);
		padding: 0 8px;
		border-radius: var(--v-radius-btn);
		color: var(--v-ink-1);
		text-decoration: none;
		white-space: nowrap;
		transition: background-color var(--v-dur-out) var(--v-ease);
	}

	.mod:hover {
		background: var(--v-minimal-hover);
	}

	.mod:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 2px;
	}

	.mod :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.mod.is-pressed :global([data-ui='icon']) {
		color: var(--v-ink-1);
	}

	/* ── search ── */
	.search {
		position: relative;
		display: flex;
		flex: 0 1 auto;
		align-items: center;
		width: 380px;
		min-width: 240px;
		margin: 0 12px;
	}

	.search :global(.s-ic) {
		position: absolute;
		left: 8px;
		color: var(--v-ink-2);
		pointer-events: none;
	}

	.s-in {
		box-sizing: border-box;
		width: 100%;
		height: var(--v-ctl-md);
		margin: 0;
		/* the right padding is the key hint's room: Ctrl K (52 px at 5 px from the edge) for the omnibar, / for the route search */
		padding: 0 60px 0 32px;
		border: 0;
		border-radius: var(--v-radius-btn);
		outline: 0;
		background: color-mix(in srgb, var(--v-surface-sink) 30%, transparent);
		color: var(--v-ink-1);
		box-shadow:
			inset 0 0 0 1px var(--v-line-2),
			inset 0 -1px 1px 0 var(--v-line-strong);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		text-overflow: ellipsis;
	}

	.s-in[readonly] {
		cursor: text;
	}

	.s-in[data-mode='routes'] {
		padding-right: 32px;
	}

	.s-in[data-mode='routes'].hinted {
		padding-right: 100px;
	}

	.s-in::placeholder {
		color: var(--v-ink-2);
		opacity: 1;
	}

	.s-in:focus {
		box-shadow:
			inset 0 0 0 1px var(--v-focus),
			0 0 0 1px var(--v-focus);
	}

	.s-in::-webkit-search-cancel-button {
		display: none;
	}

	.keys {
		position: absolute;
		right: 5px;
		display: inline-flex;
		align-items: center;
		pointer-events: none;
	}

	.keys.hint {
		max-width: 92px;
		overflow: hidden;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* ── right group ── */
	.right {
		display: flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 2px;
		margin-left: auto;
	}

	.right > :global(*) {
		flex: 0 0 auto;
	}

	.fold {
		display: inline-flex;
		align-items: center;
	}

	.ex-tag {
		display: inline-flex;
		align-items: stretch;
		box-sizing: border-box;
		min-height: var(--v-ws-tag);
		margin: 0 4px;
		padding: 0;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		color: var(--v-ink-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		white-space: nowrap;
		cursor: pointer;
	}

	.ex-tag:hover {
		box-shadow: inset 0 0 0 999px var(--v-neutral-veil);
		color: var(--v-ink-1);
	}

	.ex-tag:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 1px;
	}

	.ex-in {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 6px;
	}

	.ex-tag :global([data-ui='icon']) {
		color: inherit;
	}

	.right :global(.data-btn) {
		margin-left: 4px;
	}

	.dot {
		position: absolute;
		top: 5px;
		right: 4px;
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--v-success-text);
		box-shadow: 0 0 0 2px var(--v-surface-1);
	}

	.dot.s-degraded {
		background: var(--v-surface-1);
		box-shadow:
			inset 0 0 0 2px var(--v-ink-1),
			0 0 0 2px var(--v-surface-1);
	}

	.dot.s-down {
		background: var(--v-ink-1);
	}

	/* an unread watchlist read: the alert role */
	.dot.s-alert {
		background: var(--v-danger-text);
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	.right :global(.inbox:disabled) {
		cursor: default;
		color: var(--v-ink-1);
	}

	.right :global(.inbox:disabled:hover) {
		background: transparent;
	}

	.lang {
		display: inline-flex;
		gap: 2px;
		margin: 0 4px;
		padding: 2px;
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-sink);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}

	.lang > button {
		min-height: 22px;
		min-width: 26px;
		margin: 0;
		padding: 0 6px;
		border: 0;
		border-radius: 3px;
		background: transparent;
		color: var(--v-ink-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: 16px;
		cursor: pointer;
	}

	.lang > button:hover {
		color: var(--v-ink-1);
	}

	.lang > button:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 1px;
	}

	/* ── fit levels (cumulative; set by measureFit, see the header) ── */
	.navbar.fit-1 .city {
		display: none;
	}

	.navbar.fit-2 .ex-tag {
		margin: 0;
	}

	.navbar.fit-2 :global(.data-btn) {
		margin-left: 0;
	}

	.navbar.fit-2 .lang {
		margin: 0 2px;
	}

	.navbar.fit-2 .right .sep {
		margin: 0 4px;
	}

	/* a folded label stays the control's accessible name, off screen */
	.navbar.fit-2 :global(.opt-lbl),
	.navbar.fit-3 :global(.band-tag .kt) {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	.navbar.fit-4 .pol-lbl {
		display: none;
	}

	.navbar.fit-5 .mod .lbl {
		display: none;
	}

	.navbar.fit-5 .mod {
		width: var(--v-ctl-md);
		padding: 0;
		justify-content: center;
	}

	/* ── 1440–1679: icon-only modules, search 300, Policies icon-only ── */
	@media (max-width: 1679px) {
		.mod .lbl {
			display: none;
		}

		.mod {
			width: var(--v-ctl-md);
			padding: 0;
			justify-content: center;
		}

		.search {
			width: 300px;
		}

		.pol-lbl {
			display: none;
		}
	}

	/* ── 1280–1439: search 240 without the key hint; Data, Policies and the language fold into More ── */
	@media (max-width: 1439px) {
		.search {
			width: 240px;
			margin: 0 8px;
		}

		.keys:not(.hint) {
			display: none;
		}

		/* no key hint at this step: the placeholder gets the room */
		.s-in,
		.s-in[data-mode='routes'] {
			padding-right: 4px;
		}

		.fold {
			display: none;
		}

		.city {
			display: none;
		}
	}
</style>
