/**
 * The OSINT provider's object actions (registered for `osint_event` under
 * the provider id `osint.map`, plan R27 — OS-DECK-B adds the decision
 * actions under its own id, and both appear). A reported situation is never
 * acted on from here: promote and decision support have their one home
 * (SPEC §5.4, ethics rule 6).
 *
 *   Show on map              the workspace's OWN core action (the header
 *                            renders it once) — this provider adds no
 *                            duplicate of it (item 7)
 *   Search around the place  the omnibar seeded with the report's toponym
 *                            (X25: the page's one omnibar opens, map
 *                            commands off where there is no map) — the
 *                            workspace's Search around has no toponym to
 *                            seed, so this one is additive, not a duplicate
 *   Open the source list     scroll the inspector to the osint-sources
 *                            section (a reading aid, never a fetch: the
 *                            sources are already rendered)
 */
import { ACTION_ICON } from '$lib/design/icons';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.osint';
import { workspace } from '$lib/workspace/workspace.svelte';
import type { ObjectAction, ObjectRow } from '$lib/workspace/types';

/** The actions for an osint_event row, in the order the inspector lists them. */
export function osintActions(row: ObjectRow, lang: string): ObjectAction[] {
	const L = (k: string) => t(lang, k);
	const actions: ObjectAction[] = [];
	const toponym = typeof row.props.toponym === 'string' ? row.props.toponym.trim() : '';
	if (toponym) {
		actions.push({
			id: 'osint.search-around',
			label: L('os_act_search_around'),
			icon: ACTION_ICON.search_around,
			run() {
				workspace.openOmnibar(toponym);
			},
		});
	}
	actions.push({
		id: 'osint.sources',
		label: L('os_act_sources'),
		icon: ACTION_ICON.osint,
		run() {
			if (typeof document === 'undefined') return;
			const el = document.querySelector<HTMLElement>('[data-testid="osint-sources"]');
			el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
		},
	});
	return actions;
}
