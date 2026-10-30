<script lang="ts">
	/**
	 * AppRail (V3-SPEC §3.1, §5.1) — the left rail: the mark, the five jobs (icon + label, never
	 * icon-only), then Analyst at the bottom, separated. 88 px wide, 76 px below 1500 px. Decide carries
	 * the only badge: the decision units waiting (the page's commandBar.inboxCount — the canonical
	 * `decisionUnits()` count), orange, with its count in words for screen readers.
	 */
	import { t } from '$lib/i18n/strings';
	import '../packs.v3';
	import Glyph from '../Glyph.svelte';
	import { V3_ANALYST, V3_NAV, type V3NavItem } from './nav';

	let { active, lang, badge = 0 }: { active: string | null; lang: string; badge?: number } = $props();
</script>

{#snippet item(n: V3NavItem, count: number)}
	{@const on = active === n.id}
	<a
		class={['nav', on && 'is-pressed']}
		href={n.href}
		aria-current={on ? 'page' : undefined}
		title={n.id === 'analyst' ? t(lang, 'v3_nav_analyst_tip') : undefined}
		data-v3-nav={n.id}
	>
		<Glyph name={n.glyph} size={24} />
		<span class="lbl">{t(lang, n.key)}</span>
		{#if count > 0}
			<span class="badge" data-testid="v3-decide-badge" data-count={count}
				><span aria-hidden="true">{count > 99 ? '99+' : count}</span><span class="sr">{t(lang, 'v3_nav_badge', count)}</span></span
			>
		{/if}
	</a>
{/snippet}

<nav class="rail" aria-label={t(lang, 'v3_nav_main')} data-v3="rail">
	<a class="logo" href={V3_NAV[0].href} aria-label={t(lang, 'v3_home_link')}><img src="/brand/sajag-mark.svg" alt="" width="40" height="40" /></a>
	{#each V3_NAV as n (n.id)}
		{@render item(n, n.id === 'decide' ? badge : 0)}
	{/each}
	<span class="grow"></span>
	<span class="sep" aria-hidden="true"></span>
	{@render item(V3_ANALYST, 0)}
</nav>

<style>
	.rail {
		grid-row: 1 / -1;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		width: var(--v3-rail);
		min-height: 0;
		padding: 14px 0 16px;
		background: var(--v3-bg);
		border-right: 1px solid var(--v3-line-1);
	}

	.logo {
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		margin-bottom: 14px;
		border-radius: var(--v3-radius-m);
	}

	.logo img {
		display: block;
		width: 40px;
		height: 40px;
	}

	.nav {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 5px;
		width: calc(var(--v3-rail) - 16px);
		padding: 10px 0 9px;
		border-radius: 14px;
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: 14px;
		font-weight: 600;
		text-align: center;
		text-decoration: none;
		transition:
			background var(--v3-dur-1) var(--v3-ease),
			color var(--v3-dur-1);
	}

	.nav:hover {
		background: var(--v3-s2);
		color: var(--v3-t1);
	}

	.nav.is-pressed {
		background: var(--v3-s3) !important;
		box-shadow: none !important;
		color: var(--v3-t1) !important;
	}

	.nav.is-pressed::before {
		content: '';
		position: absolute;
		left: -8px;
		top: 14px;
		bottom: 14px;
		width: 3px;
		border-radius: 0 3px 3px 0;
		background: var(--v3-t1);
	}

	.lbl {
		max-width: calc(100% + 8px);
		overflow-wrap: normal;
		word-break: keep-all;
	}

	.nav:lang(hi) .lbl,
	.nav:lang(mr) .lbl {
		font-size: 13px;
		line-height: 1.35;
	}

	.badge {
		position: absolute;
		top: 4px;
		right: 12px;
		min-width: 20px;
		height: 20px;
		padding: 0 6px;
		border-radius: 10px;
		background: var(--v3-decide);
		color: var(--v3-on-decide);
		font-size: 12px;
		line-height: 20px;
		font-weight: 700;
		text-align: center;
		box-shadow: 0 0 0 3px var(--v3-bg);
	}

	.grow {
		flex: 1;
	}

	.sep {
		width: 36px;
		height: 1px;
		margin: 6px 0;
		background: var(--v3-line-2);
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	.nav:focus-visible,
	.logo:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	@media (prefers-reduced-motion: reduce) {
		.nav {
			transition: none;
		}
	}

	/* a phone: the five jobs and Analyst as a tab bar along the bottom (icon + label, never icon-only) */
	@media (max-width: 720px) {
		.rail {
			grid-row: 4;
			grid-column: 1;
			flex-direction: row;
			align-items: stretch;
			justify-content: space-between;
			gap: 0;
			width: auto;
			padding: 4px 4px calc(4px + env(safe-area-inset-bottom, 0px));
			border-right: 0;
			border-top: 1px solid var(--v3-line-1);
		}

		.logo,
		.grow,
		.sep {
			display: none;
		}

		.nav {
			flex: 1 1 0;
			min-width: 0;
			width: auto;
			gap: 3px;
			padding: 7px 0 6px;
			border-radius: 12px;
			font-size: 11px;
			line-height: 13px;
		}

		.nav:lang(hi) .lbl,
		.nav:lang(mr) .lbl {
			font-size: 11px;
			line-height: 1.3;
		}

		.lbl {
			max-width: 100%;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}

		.nav.is-pressed::before {
			left: 30%;
			right: 30%;
			top: -4px;
			bottom: auto;
			width: auto;
			height: 3px;
			border-radius: 0 0 3px 3px;
		}

		.badge {
			top: 1px;
			right: calc(50% - 30px);
			min-width: 18px;
			height: 18px;
			padding: 0 5px;
			font-size: 11px;
			line-height: 18px;
		}
	}
</style>
