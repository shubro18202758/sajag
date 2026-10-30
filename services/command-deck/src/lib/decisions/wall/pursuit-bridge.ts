/**
 * The wall's bridge to the Pursuit section (wave C; see
 * WallPursuitSection.svelte). UI-S5A registers PursuitSection for `event`
 * (and `vehicle`) under id 'pursuit' through registerProviders(); call this
 * AFTER registerProviders(): it registers the bridge for `event` only when
 * no pursuit section is there, under the same id, so a later registration
 * of the real section replaces it (registry R27: same id, one entry).
 */
import { inspectorSectionsFor, registerInspectorSection } from '$lib/workspace/registry';
import WallPursuitSection from './WallPursuitSection.svelte';

export const PURSUIT_SECTION_ID = 'pursuit';

/** True when a section that speaks for pursuits is registered for `kind`. */
export function hasPursuitSection(kind: string): boolean {
	return inspectorSectionsFor(kind).some((s) => s.id === PURSUIT_SECTION_ID || /pursuit/i.test(s.id));
}

/** Register the bridge for events when (and only when) no pursuit section exists. */
export function ensurePursuitSection(): boolean {
	if (hasPursuitSection('event')) return false;
	registerInspectorSection('event', WallPursuitSection, { id: PURSUIT_SECTION_ID, order: 10 });
	return true;
}
