/**
 * Shell navigation — the routes of the deck (SPEC §5.3, §6). The shell owns
 * the route topology; this list is the single source of nav truth (no link
 * ever 404s). Labels are i18n keys (packs.ts registers en/hi/mr); glyphs are
 * Blueprint icon names from the frozen MODULE_ICON map (no Unicode glyphs).
 */
import { MODULE_ICON, type IconName } from '$lib/design/icons';
import { WORKSPACE_URL } from './root-flip';

export interface NavModule {
	id: keyof typeof MODULE_ICON;
	href: string;
	/** i18n key of the module's name. */
	key: string;
	icon: IconName;
	/** Alt+n jumps here. */
	hotkey: string;
}

/**
 * The five operator modules, left to right (SPEC §5.3): City, Corridor,
 * Situation, Advisories, Assistant. Corridor is the Analyst workspace at
 * `/analyst` (V3 P5: `/` is Home, which the brand mark opens); `/ops` is the
 * "Situation wall" (the existing `nav_ops` label — a nav label only, V3-SPEC §3.2).
 */
export const MODULES: readonly NavModule[] = [
	{ id: 'city', href: '/gods-eye', key: 'nav_module_city', icon: MODULE_ICON.city, hotkey: '1' },
	{ id: 'corridor', href: WORKSPACE_URL, key: 'nav_module_corridor', icon: MODULE_ICON.corridor, hotkey: '2' },
	{ id: 'situation', href: '/ops', key: 'nav_ops', icon: MODULE_ICON.situation, hotkey: '3' },
	{ id: 'advisories', href: '/comms', key: 'nav_module_advisories', icon: MODULE_ICON.advisories, hotkey: '4' },
	{ id: 'assistant', href: '/chat', key: 'nav_module_assistant', icon: MODULE_ICON.assistant, hotkey: '5' }
];

/** True when `pathname` is the module's route (the active one is .is-pressed). */
export function moduleActive(m: NavModule, pathname: string): boolean {
	return pathname === m.href || pathname.startsWith(`${m.href}/`);
}

export interface NavItem {
	href: string;
	/** i18n key for the label. */
	key: string;
}

/** Citizen and driver surfaces (daylight theme): the navbar's More menu and the public bar. */
export const PUBLIC_NAV: readonly NavItem[] = [
	{ href: '/citizen', key: 'nav_citizen' },
	{ href: '/driver', key: 'nav_driver' }
];

/**
 * The design sheet is a developer page: its More entry shows only under the
 * vite dev server (the route itself stays: the smokes use it).
 */
export const DEV_BUILD: boolean = import.meta.env?.DEV === true;

/** Search index for the navbar's own search (pages without an omnibar): the routes only. */
export const NAV_INDEX: readonly { href: string; key: string; terms: string }[] = [
	...MODULES.map((m) => ({ href: m.href, key: m.key, terms: `${m.href} ${m.id} ${m.key}` })),
	...PUBLIC_NAV.map((n) => ({ href: n.href, key: n.key, terms: `${n.href} ${n.key}` })),
	...(DEV_BUILD ? [{ href: '/design', key: 'nav_design', terms: '/design design nav_design' }] : [])
].map((n) => ({ ...n, terms: n.terms.toLowerCase() }));
