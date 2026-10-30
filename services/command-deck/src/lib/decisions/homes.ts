/**
 * Decision homes (SPEC §5.4, review B3; plan X9): each decision kind is
 * decided in exactly ONE place per route. Every other surface — the
 * inspector's Actions tab, the assistant, the map tile, the LiveStrip's
 * Review, the planner's proposal row — shows a link card that opens the
 * home; it never carries a second Approve.
 *
 *   inbox      the Inbox detail view (right dock) on / and /gods-eye
 *   decisions  the item in the /ops Decisions column
 *   movement   the Movement tab's ConvoyCard on / (escort proposals)
 *   map        the MapProposals card on the map (AI map proposals)
 *
 * `homeLink(kind, id, route)` is the link-card target a link-only surface
 * uses: an href that opens the home (a deep link the home reads) and the
 * label "Decided in …". tests/decisions.unit.mjs iterates HOMES (every kind
 * has exactly one home per route, and a home for every unit kind).
 *
 * The route keys are the LOGICAL routes: '/' is the Analyst workspace (the v2 page, served at `/analyst` since the
 * V3 root flip — homeLink's hrefs say so); '/gods-eye' and '/ops' are themselves. V3's own surfaces link a unit
 * straight to /decide/<unit> and an object to /o/<urn> (v3/home/view.ts); this table is the Analyst side of the rule.
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.decisions';
import { safePathId } from '$lib/ops/endpoints';
import { WORKSPACE_URL } from '$lib/shell/root-flip';

export type HomeRoute = '/' | '/gods-eye' | '/ops';
export type Home = 'inbox' | 'decisions' | 'movement' | 'map';

export const HOME_ROUTES: readonly HomeRoute[] = ['/', '/gods-eye', '/ops'];

/** One home per kind per route (plan X9, frozen shape). */
export const HOMES: Record<string, Record<HomeRoute, Home>> = {
	'stolen-sighting': { '/': 'inbox', '/gods-eye': 'inbox', '/ops': 'decisions' },
	pursuit: { '/': 'inbox', '/gods-eye': 'inbox', '/ops': 'decisions' },
	echallan: { '/': 'inbox', '/gods-eye': 'inbox', '/ops': 'decisions' },
	'corridor-request': { '/': 'inbox', '/gods-eye': 'inbox', '/ops': 'decisions' },
	// SPEC §5.4: the Movement tab's ConvoyCard on / and /gods-eye; the ConvoyCard at the top of the /ops Decisions column
	'escort-proposal': { '/': 'movement', '/gods-eye': 'movement', '/ops': 'decisions' },
	'map-proposal': { '/': 'map', '/gods-eye': 'map', '/ops': 'map' },
	// plan X22: the decision-support proposal is approved in the Inbox detail on / and /gods-eye,
	// as a Decisions column item on /ops — exactly one home per route
	dss: { '/': 'inbox', '/gods-eye': 'inbox', '/ops': 'decisions' },
};

/** The home of `kind` on `route` (/chat and unknown routes read as '/'); an unknown kind's home is the inbox. */
export function homeOf(kind: string, route: string): Home {
	const r: HomeRoute = route === '/gods-eye' || route === '/ops' ? route : '/';
	return HOMES[kind]?.[r] ?? (r === '/ops' ? 'decisions' : 'inbox');
}

/** The deep-link key a home reads (#unit=<kind>:<id> on /ops, #inbox=… / #movement=… on the workspace routes). */
export function unitKey(kind: string, id: string): string | null {
	const k = /^[a-z][a-z-]{0,31}$/.test(kind) ? kind : null;
	const i = safePathId(id);
	return k && i ? `${k}:${i}` : null;
}

/** Parse `<kind>:<id>` (a deep link's value) — null when either part is hostile. */
export function parseUnitKey(v: string | null | undefined): { kind: string; id: string } | null {
	if (typeof v !== 'string') return null;
	const at = v.indexOf(':');
	if (at <= 0) return null;
	const kind = v.slice(0, at);
	const id = v.slice(at + 1);
	return unitKey(kind, id) ? { kind, id } : null;
}

/**
 * The link-card target of a decision on `route`: an href that opens its home,
 * and the label ("Decided in the Inbox"). The href carries the unit's kind
 * and id only — never a mark.
 */
export function homeLink(kind: string, id: string, route: string, lang = 'en'): { href: string; label: string } {
	const home = homeOf(kind, route);
	const key = unitKey(kind, id);
	const enc = key ? encodeURIComponent(key) : '';
	const base = route === '/gods-eye' ? '/gods-eye' : route === '/ops' ? '/ops' : WORKSPACE_URL;
	const href =
		home === 'decisions'
			? `/ops${enc ? `#unit=${enc}` : ''}`
			: home === 'movement'
				? `${base}${enc ? `#movement=${enc}` : ''}`
				: home === 'map'
					? base
					: `${base}${enc ? `#inbox=${enc}` : ''}`;
	return { href, label: t(lang, `dec_home_${home}`) };
}
