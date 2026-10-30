<script lang="ts">
	/**
	 * OpsBand (V3-P6B; V3-SPEC §3.1, §6.9, §7.3) — the operator pages' own band under the V3 top bar. The rail and the
	 * top bar are the SAME pixels on every page; what only the operator pages need sits here, in the V3 language,
	 * so nothing has to be added to (or moved around in) the top bar:
	 *
	 *   the Analyst views   Workspace · Situation wall · City map · Assistant (the Analyst family's sub-nav, §6.9)
	 *   the band tag        the city's situation band (`band-tag`, data-band, the ticking data-age-sec; hollow
	 *                       "Band —" until a page reports one)
	 *   the Inbox           decisions waiting (`data-inbox-intent`, `data-count`); opens the page's inbox
	 *   the Data button     `brain-posture` (data-decider, data-tier, data-worst) + the v2 Data and services panel
	 *   Policies            the v2 Policies panel (what this console will never do)
	 *   More                shortcuts, the public views, the design sheet (dev builds only)
	 *
	 * The live strip is not here: V3Shell draws it (LiveBand) directly under the top bar, in the same place on every page
	 * that has something live ("live operations are never hidden", §7.3), /comms included.
	 *
	 * Like the shells it owns no data and imports no store (R4): every fact arrives through the v2 shell↔page
	 * contract, `commandBar`. The language, the Exercise data statement, the search and the duty officer are the top
	 * bar's (HeaderMenu, Search, the officer pill) and stay there.
	 *
	 * Keys: `?` opens the shortcuts sheet, which lists only keys that work here (Ctrl K while the page supplied its
	 * omnibar, `/`, `?`, Esc, and G then H / M / D / P / A / V). No single key approves, unmasks, dispatches or publishes.
	 */
	import { page } from '$app/stores';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import '../packs.v3';
	import './packs.shell';
	import HotkeysDialog from '$lib/ui/HotkeysDialog.svelte';
	import Menu from '$lib/ui/Menu.svelte';
	import Popover from '$lib/ui/Popover.svelte';
	import { ut } from '$lib/ui/lang';
	import type { HotkeyGroup, MenuItemSpec } from '$lib/ui/types';
	import BandTag from '$lib/shell/BandTag.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import DataPanel, { dataSummary } from '$lib/shell/DataPanel.svelte';
	import PoliciesPanel from '$lib/shell/PoliciesPanel.svelte';
	import { DESIGN_ICON, PUBLIC_ICON, SHORTCUTS_ICON } from '$lib/shell/icons';
	import { DEV_BUILD, PUBLIC_NAV } from '$lib/shell/nav';
	import Glyph from '../Glyph.svelte';
	import { ANALYST_TABS, V3_NAV, surfaceOf } from './nav';

	const lang = $derived(commandBar.lang);
	const pathname = $derived($page.url.pathname);
	const surface = $derived(surfaceOf(pathname));

	// ── inbox ──
	const inboxShown = $derived(!!commandBar.onInbox || commandBar.inboxCount > 0);
	const inboxTip = $derived(
		commandBar.inboxIntent === 'danger'
			? t(lang, 'shell_inbox_watchlist')
			: commandBar.inboxCount > 0
				? t(lang, 'shell_inbox_waiting', commandBar.inboxCount)
				: t(lang, 'shell_inbox_none'),
	);

	// ── data ──
	const summary = $derived(commandBar.dataStatus ? dataSummary(lang, commandBar.dataStatus) : '');

	// ── More + shortcuts ──
	let moreOpen = $state(false);
	let hotkeysOpen = $state(false);
	const moreItems = $derived<MenuItemSpec[]>([
		{
			id: 'shortcuts',
			label: t(lang, 'shell_shortcuts'),
			icon: SHORTCUTS_ICON,
			rightLabel: '?',
			onclick: () => {
				moreOpen = false;
				hotkeysOpen = true;
			},
		},
		{ id: 'public-head', kind: 'header', label: t(lang, 'shell_public_views') },
		...PUBLIC_NAV.map((n) => ({ id: `pub-${n.href}`, label: t(lang, n.key), icon: PUBLIC_ICON, href: n.href })),
		...(DEV_BUILD ? ([{ id: 'div-dev', kind: 'divider' }, { id: 'design', label: t(lang, 'nav_design'), icon: DESIGN_ICON, href: '/design' }] as MenuItemSpec[]) : []),
	]);

	function typing(target: EventTarget | null): boolean {
		const el = target as HTMLElement | null;
		return el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement || !!el?.isContentEditable;
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.defaultPrevented || typing(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
		if (e.key === '?') {
			e.preventDefault();
			hotkeysOpen = !hotkeysOpen;
		}
	}

	/** Only keys the shell can vouch for on this page: Ctrl K while the page supplied its omnibar, the rest are the shell's own. */
	const hotkeyGroups = $derived<HotkeyGroup[]>([
		{
			title: ut(lang, 'ui_hk_global'),
			keys: [
				...(commandBar.onSearch ? [{ combo: ['Ctrl', 'K'], label: ut(lang, 'ui_hk_omnibar') }] : []),
				{ combo: ['/'], label: ut(lang, 'ui_hk_search') },
				{ combo: ['?'], label: ut(lang, 'ui_hk_help') },
				{ combo: ['Esc'], label: ut(lang, 'ui_hk_escape') },
			],
			note: ut(lang, 'ui_hk_rule'),
		},
		{
			title: t(lang, 'shell_hk_modules'),
			keys: V3_NAV.filter((n) => n.chord).map((n) => ({ combo: ['G', (n.chord ?? '').toUpperCase()], label: t(lang, 'shell_hk_module', t(lang, n.key)) })),
		},
	]);
</script>

<svelte:window onkeydown={onKeydown} />

<div class="ops" data-v3="ops-band">
	<div class="bar" data-shell="command-bar" data-surface={surface?.href ?? 'other'}>
		{#if surface?.analyst}
			<nav class="tabs" aria-label={t(lang, 'v3s_analyst_nav')} data-v3="analyst-tabs">
				{#each ANALYST_TABS as tab (tab.id)}
					{@const on = pathname === tab.href || pathname.startsWith(`${tab.href}/`)}
					<a class={['tab', on && 'is-pressed']} href={tab.href} aria-current={on ? 'page' : undefined} data-v3-tab={tab.id}>
						<Glyph name={tab.glyph} size={18} />
						<span>{t(lang, tab.key)}</span>
					</a>
				{/each}
			</nav>
		{/if}

		<span class="grow"></span>

		<div class="band">
			<BandTag band={commandBar.band} bandSource={commandBar.bandSource} bandAgeSec={commandBar.bandAgeSec} {lang} />
		</div>

		{#if inboxShown}
			<button
				type="button"
				class={['chip', 'inbox', commandBar.inboxIntent !== 'none' && `i-${commandBar.inboxIntent}`]}
				aria-label={inboxTip}
				title={inboxTip}
				data-inbox-intent={commandBar.inboxIntent}
				data-count={commandBar.inboxCount}
				disabled={!commandBar.onInbox}
				onclick={() => commandBar.onInbox?.()}
			>
				<Glyph name="decide" size={18} />
				{#if commandBar.inboxCount > 0}<span class="n">{commandBar.inboxCount}</span>{:else if commandBar.inboxIntent === 'danger'}<i class="dot" aria-hidden="true"></i>{/if}
			</button>
		{/if}

		{#if commandBar.dataStatus}
			{@const ds = commandBar.dataStatus}
			<Popover placement="bottom-end" class="v3-pop" aria-label={t(lang, 'shell_data')}>
				<button
					type="button"
					class="chip data"
					title={summary}
					data-testid="brain-posture"
					data-decider={ds.decider}
					data-tier={ds.tier}
					data-worst={ds.worst}
				>
					<Glyph name="wave" size={18} />
					<i class={['dot', `s-${ds.worst}`]} aria-hidden="true"></i>
					<span class="sr">{summary}</span>
				</button>
				{#snippet content()}<DataPanel status={ds} {lang} />{/snippet}
			</Popover>
		{/if}

		<Popover placement="bottom-end" class="v3-pop" aria-label={t(lang, 'shell_policies')}>
			<button type="button" class="chip policies" title={t(lang, 'shell_policies_tip')} aria-label={t(lang, 'shell_policies')}>
				<Glyph name="shield" size={18} />
				<span class="lbl">{t(lang, 'shell_policies')}</span>
			</button>
			{#snippet content()}<PoliciesPanel {lang} />{/snippet}
		</Popover>

		<Popover placement="bottom-end" class="v3-pop" bind:open={moreOpen} aria-label={ut(lang, 'ui_more')}>
			<button type="button" class="chip more" title={ut(lang, 'ui_more')} aria-label={ut(lang, 'ui_more')} data-menu="more">
				<Glyph name="more" size={18} />
			</button>
			{#snippet content({ close })}
				<div class="more-menu" data-shell="more-menu"><Menu items={moreItems} label={ut(lang, 'ui_more')} onselect={close} autofocus /></div>
			{/snippet}
		</Popover>
	</div>
</div>

<HotkeysDialog bind:open={hotkeysOpen} groups={hotkeyGroups} {lang} data-shell="hotkeys" />

<style>
	.ops {
		flex: none;
		min-width: 0;
		background: var(--v3-bg);
		color: var(--v3-t1);
		font-family: var(--v-font-ui);
	}

	.bar {
		display: flex;
		align-items: center;
		gap: 8px;
		box-sizing: border-box;
		height: 52px;
		min-width: 0;
		padding: 0 var(--v3-gut);
		border-bottom: 1px solid var(--v3-line-1);
		font-size: var(--v3-text-body);
	}

	.tabs {
		display: flex;
		align-items: center;
		gap: 4px;
		min-width: 0;
	}

	.tab {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 36px;
		padding: 0 14px 0 12px;
		border-radius: 18px;
		color: var(--v3-t2);
		font-size: 14px;
		line-height: 20px;
		font-weight: 600;
		text-decoration: none;
		white-space: nowrap;
		transition:
			background var(--v3-dur-1) var(--v3-ease),
			color var(--v3-dur-1);
	}

	.tab:hover {
		background: var(--v3-s2);
		color: var(--v3-t1);
	}

	.tab.is-pressed {
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.grow {
		flex: 1 1 0;
		min-width: 0;
	}

	/* the v2 band tag, drawn with the V3 tokens */
	.band {
		display: inline-flex;
		align-items: center;
		--v-neutral-veil: var(--v3-s3);
		--v-ink-1: var(--v3-t1);
		--v-ink-2: var(--v3-t2);
		--v-line-2: var(--v3-line-2);
		--v-text-xs: var(--v3-text-meta);
		--v-ws-tag: 30px;
		--v-radius-chip: 15px;
	}

	.chip {
		position: relative;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		height: 36px;
		min-width: 36px;
		padding: 0 12px;
		border: 1px solid var(--v3-line-2);
		border-radius: 18px;
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		font-size: 14px;
		font-weight: 600;
		white-space: nowrap;
		cursor: pointer;
		transition:
			border-color var(--v3-dur-1) var(--v3-ease),
			background var(--v3-dur-1) var(--v3-ease);
	}

	.chip:hover:not(:disabled) {
		border-color: var(--v3-line-3);
		background: var(--v3-s2);
	}

	.chip:disabled {
		cursor: default;
		color: var(--v3-t3);
	}

	.chip.more {
		padding: 0;
		width: 36px;
	}

	.inbox.i-warning {
		border-color: var(--v3-decide-line);
		background: var(--v3-decide-veil);
		color: var(--v3-decide-text);
	}

	.inbox.i-danger {
		border-color: var(--v3-alert);
		background: var(--v3-alert-veil);
		color: var(--v3-alert-text);
	}

	.n {
		font-variant-numeric: tabular-nums;
	}

	.dot {
		display: inline-block;
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: var(--v3-ok);
	}

	.inbox .dot {
		background: var(--v3-alert);
	}

	.dot.s-degraded {
		background: transparent;
		box-shadow: inset 0 0 0 2px var(--v3-t1);
	}

	.dot.s-down {
		background: var(--v3-t1);
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}

	.chip:focus-visible,
	.tab:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.more-menu {
		min-width: 240px;
	}

	:global(:lang(hi)) .tab,
	:global(:lang(mr)) .tab {
		line-height: 1.5;
	}

	@media (max-width: 1500px) {
		.bar {
			height: 46px;
		}

		.tab {
			padding: 0 12px 0 10px;
		}
	}

	/* a phone: the tabs and the status chips in one row that scrolls sideways (they never draw over each other) */
	@media (max-width: 720px) {
		.bar {
			gap: 6px;
			padding: 0 12px;
			overflow-x: auto;
			overflow-y: hidden;
			scrollbar-width: none;
		}

		.tabs,
		.band {
			flex: none;
		}

		.grow {
			flex: 0 0 8px;
		}
	}
</style>
