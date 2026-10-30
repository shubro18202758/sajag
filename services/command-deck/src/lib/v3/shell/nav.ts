/**
 * The V3 rail (V3-SPEC §3.1): the officer's five jobs in order, then Analyst at the bottom, separated.
 * Labels are pack keys (packs.v3), glyphs are V3 glyph names. Decide carries the only badge (decision
 * units waiting, orange).
 *
 * Decide is /decide (P2); Map is /map and Assistant is /assistant (P4: the V3 map around the same God's-eye canvas, and
 * the V3 conversation over the same assistant session as the Analyst dock). /gods-eye stays the Analyst city map and /chat
 * the v2 assistant page. Until Advisories lands (P6) its item opens the screen that does that job today. The root flip (P5):
 * Home is `/` (`/home` keeps answering) and Analyst is the v2 workspace at `/analyst` (user decision: visible to every officer).
 */
export interface V3NavItem {
	id: 'home' | 'map' | 'decide' | 'plan' | 'assistant' | 'advisories' | 'analyst';
	href: string;
	key: string;
	glyph: string;
	/** G then this key goes here (§7.1). */
	chord: string | null;
}

export const V3_NAV: readonly V3NavItem[] = [
	{ id: 'home', href: '/', key: 'v3_nav_home', glyph: 'home', chord: 'h' },
	{ id: 'map', href: '/map', key: 'v3_nav_map', glyph: 'map', chord: 'm' },
	{ id: 'decide', href: '/decide', key: 'v3_nav_decide', glyph: 'decide', chord: 'd' },
	// Plan a movement (V3-P4B): the convoy / corridor planner on its own page, the "Where to?" flow
	{ id: 'plan', href: '/plan', key: 'v3_nav_plan', glyph: 'compass', chord: 'p' },
	{ id: 'assistant', href: '/assistant', key: 'v3_nav_assistant', glyph: 'spark', chord: 'a' },
	{ id: 'advisories', href: '/comms', key: 'v3_nav_advisories', glyph: 'megaphone', chord: 'v' },
];

export const V3_ANALYST: V3NavItem = { id: 'analyst', href: '/analyst', key: 'v3_nav_analyst', glyph: 'analyst', chord: null };

/** The rail item a pathname belongs to (null when none). */
export function navActive(pathname: string): V3NavItem['id'] | null {
	// Home answers at `/` and, as an alias, `/home`; the workspace at `/analyst`
	if (pathname === '/' || pathname === '/home' || pathname.startsWith('/home/')) return 'home';
	if (pathname === V3_ANALYST.href || pathname.startsWith(`${V3_ANALYST.href}/`)) return 'analyst';
	for (const n of V3_NAV) if (n.href !== '/' && (pathname === n.href || pathname.startsWith(`${n.href}/`))) return n.id;
	return null;
}

/**
 * The operator surfaces that are not V3 screens of their own (P6B): the v2 pages (route group `(deck)`)
 * drawn inside the same rail and top bar. Each one names the rail item it lights, its title (an i18n key)
 * and whether it belongs to the Analyst family, whose pages share a sub-nav (Workspace · Situation wall ·
 * City map · Assistant, V3-SPEC §6.9). `navActive()` is unchanged (tests pin it); the shell asks `surfaceOf`.
 *
 *   /analyst   the workspace            rail Analyst   title "Analyst"
 *   /ops       the Situation wall       rail Analyst   title "Situation wall" (the existing nav_ops string)
 *   /gods-eye  the Analyst city map     rail Analyst   title "City map"
 *   /chat      the assistant page       rail Analyst   title "Assistant"
 *   /comms     the advisory desk (P6A)  rail Advisories
 *   /design/*  the dev galleries        no rail item
 */
export interface DeckSurface {
	href: string;
	/** The rail item it lights (null: none). */
	rail: V3NavItem['id'] | null;
	/** i18n key of the top bar's title. */
	title: string;
	/** Part of the Analyst sub-nav. */
	analyst: boolean;
}

export const ANALYST_TABS: readonly { id: string; href: string; key: string; glyph: string }[] = [
	{ id: 'workspace', href: V3_ANALYST.href, key: 'v3s_tab_workspace', glyph: 'analyst' },
	{ id: 'wall', href: '/ops', key: 'v3s_tab_wall', glyph: 'list' },
	{ id: 'city', href: '/gods-eye', key: 'v3s_tab_city', glyph: 'globe' },
	{ id: 'assistant', href: '/chat', key: 'v3s_tab_assistant', glyph: 'spark' },
];

const DECK_SURFACES: readonly DeckSurface[] = [
	{ href: V3_ANALYST.href, rail: 'analyst', title: 'v3_nav_analyst', analyst: true },
	{ href: '/ops', rail: 'analyst', title: 'v3s_tab_wall', analyst: true },
	{ href: '/gods-eye', rail: 'analyst', title: 'v3s_tab_city', analyst: true },
	{ href: '/chat', rail: 'analyst', title: 'v3s_tab_assistant', analyst: true },
	{ href: '/comms', rail: 'advisories', title: 'v3_nav_advisories', analyst: false },
];

/** The deck surface a pathname belongs to; null for a pathname that is none of them (a /design page, an unknown one). */
export function surfaceOf(pathname: string): DeckSurface | null {
	return DECK_SURFACES.find((s) => pathname === s.href || pathname.startsWith(`${s.href}/`)) ?? null;
}
