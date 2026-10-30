<script lang="ts">
	/**
	 * CitizenBar — the public bar (`data-shell="citizen-bar"`, SPEC §6.6):
	 * the brand, the plain-language posture (`data-tier`; citizens see
	 * "Planned holds on", never a band code), the two public views — inline
	 * tabs, or a Menu below 480 px — and the language switch, always in reach
	 * (`.lang button[lang]`). Deliberately nothing operator-side: no band code,
	 * no operator search, no Share, no link into the operator deck. Daylight
	 * theme; touch-sized controls; it wraps rather than scrolls sideways.
	 */
	import { SUPPORTED, t } from '$lib/i18n/strings';
	import Menu from '$lib/ui/Menu.svelte';
	import Popover from '$lib/ui/Popover.svelte';
	import type { MenuItemSpec } from '$lib/ui/types';
	import type { PublicTier } from './command-bar.svelte';
	import { MENU_ICON, PUBLIC_ICON } from './icons';
	import NavButton from './NavButton.svelte';
	import { PUBLIC_NAV } from './nav';

	interface Props {
		lang: string;
		tier: PublicTier | null;
		pathname: string;
		onLangChange?: ((lang: string) => void) | null;
	}

	let { lang, tier, pathname, onLangChange = null }: Props = $props();

	const active = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

	const menuItems = $derived<MenuItemSpec[]>(
		PUBLIC_NAV.map((n) => ({
			id: n.href,
			label: t(lang, n.key),
			icon: PUBLIC_ICON,
			href: n.href,
			selected: active(n.href),
			attrs: (active(n.href) ? { 'aria-current': 'page' } : {}) as Record<string, string>
		}))
	);
</script>

<header class="bar" data-shell="citizen-bar">
	<span class="brand">{t(lang, 'brand')}</span>

	<span class="tier tier-{tier ?? 'unknown'}" data-tier={tier ?? 'unknown'} aria-live="polite">
		<span class="dot" aria-hidden="true"></span>
		{t(lang, tier ? `tier_${tier}` : 'tier_unknown')}
	</span>

	<nav class="views" aria-label={t(lang, 'shell_public_views')}>
		{#each PUBLIC_NAV as n (n.href)}
			<a href={n.href} class="view" aria-current={active(n.href) ? 'page' : undefined}>{t(lang, n.key)}</a>
		{/each}
	</nav>

	<span class="views-menu">
		<Popover placement="bottom-start" role="menu" aria-label={t(lang, 'shell_menu')}>
			<NavButton icon={MENU_ICON} tip={t(lang, 'shell_public_views')} data-menu="public">{t(lang, 'shell_menu')}</NavButton>
			{#snippet content({ close })}
				<Menu items={menuItems} label={t(lang, 'shell_public_views')} onselect={close} />
			{/snippet}
		</Popover>
	</span>

	<div class="lang" role="group" aria-label={t(lang, 'shell_language')}>
		{#each SUPPORTED as s (s.code)}
			<button
				type="button"
				lang={s.code}
				class={[lang === s.code && 'is-pressed']}
				aria-pressed={lang === s.code}
				onclick={() => onLangChange?.(s.code)}
			>
				{s.label}
			</button>
		{/each}
	</div>
</header>

<style>
	.bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 12px;
		box-sizing: border-box;
		min-height: 56px;
		min-width: 0;
		padding: 8px 16px;
		background: var(--v-surface-1);
		border-bottom: 1px solid var(--v-line-1);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		flex-shrink: 0;
	}

	.brand {
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: calc(var(--v-text-md) + 4px);
	}

	.tier {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 28px;
		padding: 2px 12px;
		border-radius: var(--v-radius-pill);
		background: var(--v-neutral-veil);
		color: var(--v-ink-1);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex: 0 0 auto;
		background: var(--v-ink-4);
	}

	.tier-calm .dot {
		background: var(--v-band-green);
	}

	.tier-watch .dot {
		background: var(--v-band-amber);
	}

	.tier-hold .dot {
		background: var(--v-band-red);
	}

	.tier-severe .dot {
		background: var(--v-act);
	}

	.tier-unknown {
		background: transparent;
		box-shadow: inset 0 0 0 1px var(--v-line-2);
		color: var(--v-ink-2);
	}

	.views {
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}

	.view {
		display: inline-flex;
		align-items: center;
		box-sizing: border-box;
		min-height: var(--v-ctl-touch);
		padding: 0 12px;
		border-radius: var(--v-radius-btn);
		color: var(--v-ink-2);
		font-size: var(--v-text-sm);
		text-decoration: none;
		white-space: nowrap;
	}

	.view:hover {
		background: var(--v-minimal-hover);
		color: var(--v-ink-1);
	}

	/* the current view: the tab underline (SPEC §5.1: tabs use the underline) */
	.view[aria-current='page'] {
		color: var(--v-ink-1);
		box-shadow: inset 0 -3px 0 var(--v-primary-text);
	}

	.view:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 2px;
	}

	.views-menu {
		display: none;
	}

	.lang {
		display: inline-flex;
		gap: 2px;
		margin-left: auto;
		padding: 2px;
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-sink);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}

	.lang > button {
		min-height: var(--v-ctl-lg);
		margin: 0;
		padding: 0 12px;
		border: 0;
		border-radius: 3px;
		background: transparent;
		color: var(--v-ink-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-sm);
		cursor: pointer;
	}

	.lang > button:hover {
		color: var(--v-ink-1);
	}

	.lang > button:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	/* phones: the two views become a menu beside the brand; the posture and
	   the language share the second row, the language always in reach */
	@media (max-width: 479px) {
		.bar {
			padding: 8px 12px;
		}

		.views {
			display: none;
		}

		.views-menu {
			display: inline-flex;
			order: 1;
			margin-left: auto;
		}

		.tier {
			order: 2;
		}

		.lang {
			order: 3;
		}

		.lang > button {
			min-height: var(--v-ctl-touch);
			padding: 0 8px;
		}
	}
</style>
