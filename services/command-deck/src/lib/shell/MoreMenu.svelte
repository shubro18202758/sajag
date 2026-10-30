<script lang="ts">
	/**
	 * The navbar's More menu (SPEC §5.3, §3.7): keyboard shortcuts, the public
	 * views (Citizen, Driver), Lab and system — and, below 1440 px, the items
	 * the navbar folds into it: Data and services and Policies (each opens its
	 * own popover beside the menu, which stays open) and the language.
	 *
	 * The control is `aria-label="More"` (`data-menu="more"`). Its popover is
	 * a dialog named "More" that holds menus, each a whole `[role=menu]` with
	 * its own name: below 1440 px the folded "Data and policies" and the
	 * "Language" menu, then the More menu itself, whose links are the
	 * `[role=menu] a[href]` the smokes' shellLink finds. Headings and the
	 * separator sit between the menus, never inside one. The design sheet is
	 * listed only under the vite dev server.
	 */
	import { t, SUPPORTED } from '$lib/i18n/strings';
	import Icon from '$lib/ui/Icon.svelte';
	import Menu from '$lib/ui/Menu.svelte';
	import Popover from '$lib/ui/Popover.svelte';
	import { ut } from '$lib/ui/lang';
	import type { MenuItemSpec } from '$lib/ui/types';
	import type { DataStatus } from './command-bar.svelte';
	import DataPanel from './DataPanel.svelte';
	import {
		DATA_ICON,
		DESIGN_ICON,
		LANGUAGE_ICON,
		MORE_ICON,
		POLICIES_ICON,
		PUBLIC_ICON,
		SHORTCUTS_ICON,
		SYSTEM_ICON
	} from './icons';
	import { DEV_BUILD, PUBLIC_NAV } from './nav';
	import NavButton from './NavButton.svelte';
	import PoliciesPanel from './PoliciesPanel.svelte';

	interface Props {
		lang: string;
		compact: boolean;
		dataStatus: DataStatus | null;
		onLang: (code: string) => void;
		onShortcuts: () => void;
	}

	let { lang, compact, dataStatus, onLang, onShortcuts }: Props = $props();

	let open = $state(false);

	const items = $derived<MenuItemSpec[]>([
		{
			id: 'shortcuts',
			label: t(lang, 'shell_shortcuts'),
			icon: SHORTCUTS_ICON,
			rightLabel: '?',
			onclick: () => {
				open = false;
				onShortcuts();
			}
		},
		{ id: 'public-head', kind: 'header', label: t(lang, 'shell_public_views') },
		...PUBLIC_NAV.map((n) => ({ id: `pub-${n.href}`, label: t(lang, n.key), icon: PUBLIC_ICON, href: n.href })),
		{ id: 'div-lab', kind: 'divider' },
		{ id: 'lab', label: t(lang, 'shell_lab'), icon: SYSTEM_ICON, href: '/ops', rightLabel: t(lang, 'nav_module_situation') },
		...(DEV_BUILD ? [{ id: 'design', label: t(lang, 'nav_design'), icon: DESIGN_ICON, href: '/design' } as MenuItemSpec] : [])
	]);

	const langItems = $derived<MenuItemSpec[]>(
		SUPPORTED.map((s) => ({
			id: `lang-${s.code}`,
			label: s.label,
			icon: LANGUAGE_ICON,
			selected: lang === s.code,
			attrs: { lang: s.code },
			onclick: () => onLang(s.code)
		}))
	);
</script>

<Popover placement="bottom-end" bind:open aria-label={ut(lang, 'ui_more')}>
	<NavButton icon={MORE_ICON} iconOnly tip={ut(lang, 'ui_more')} aria-label={ut(lang, 'ui_more')} data-menu="more" />
	{#snippet content({ close })}
		<div class="more" data-shell="more-menu">
			{#if compact}
				<ul class="fold" role="menu" aria-label={t(lang, 'shell_more_folded')}>
					{#if dataStatus}
						<li role="none">
							<Popover placement="left-start">
								<button type="button" class="mi" role="menuitem">
									<Icon name={DATA_ICON} size={16} />
									<span class="l">{t(lang, 'shell_data')}</span>
									<i class="dot s-{dataStatus.worst}" aria-hidden="true"></i>
								</button>
								{#snippet content()}<DataPanel status={dataStatus} {lang} />{/snippet}
							</Popover>
						</li>
					{/if}
					<li role="none">
						<Popover placement="left-start">
							<button type="button" class="mi" role="menuitem">
								<Icon name={POLICIES_ICON} size={16} />
								<span class="l">{t(lang, 'shell_policies')}</span>
							</button>
							{#snippet content()}<PoliciesPanel {lang} />{/snippet}
						</Popover>
					</li>
				</ul>
				<div class="head" aria-hidden="true">{t(lang, 'shell_language')}</div>
				<Menu items={langItems} label={t(lang, 'shell_language')} onselect={close} />
				<div class="div" aria-hidden="true"></div>
			{/if}
			<Menu {items} label={ut(lang, 'ui_more')} onselect={close} autofocus={!compact} />
		</div>
	{/snippet}
</Popover>

<style>
	.more {
		box-sizing: border-box;
		min-width: 260px;
		padding: 0;
	}

	.fold {
		margin: 0;
		padding: 4px 4px 0;
		list-style: none;
	}

	.mi {
		display: flex;
		align-items: center;
		gap: 8px;
		box-sizing: border-box;
		width: 100%;
		min-height: 30px;
		margin: 0;
		padding: 4px 8px;
		border: 0;
		border-radius: var(--v-radius-btn);
		background: transparent;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		text-align: left;
		cursor: pointer;
	}

	.mi:hover,
	.mi:focus-visible {
		background: var(--v-hover);
		outline: 0;
	}

	.mi :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.l {
		flex: 1 1 auto;
	}

	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--v-success-text);
	}

	.dot.s-degraded {
		background: transparent;
		box-shadow: inset 0 0 0 2px var(--v-ink-1);
	}

	.dot.s-down {
		background: var(--v-ink-1);
	}

	.head {
		padding: 8px 12px 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 600;
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.div {
		height: 1px;
		margin: 0;
		background: var(--v-line-2);
	}
</style>
