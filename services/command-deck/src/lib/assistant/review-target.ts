/**
 * Where a map proposal or a citation is reviewed (plan X9's one home, per
 * surface): the docked panel lives beside a canvas — '/' and '/gods-eye'
 * both have one — so the review happens on the CURRENT map and the panel
 * never navigates away; the workspace just shows a view where the map is
 * visible ('graph' keeps its split, 'table' becomes the map), the same rule
 * the decision homes use for the 'map' home. The /chat page has no canvas:
 * its review opens the map route.
 */
import type { View } from '$lib/workspace/types';

export interface ReviewTarget {
	/** The route to open (null: stay on this page). */
	goto: string | null;
	/** The workspace view that shows the map. */
	view: View;
}

export function reviewTarget(variant: 'dock' | 'page', view: View = 'map'): ReviewTarget {
	if (variant === 'page') return { goto: '/gods-eye', view: 'map' };
	return {
		goto: null,
		view: view === 'graph' ? 'split' : view === 'table' ? 'map' : view,
	};
}
