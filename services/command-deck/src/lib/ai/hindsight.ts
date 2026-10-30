/**
 * The map's hindsight view (plain TypeScript: the waterlogging canvas layer reads it without runes).
 *
 * Off by default: the layer draws the LIVE nowcast. When the officer opens "19 Aug 2025 (hindsight)" on the map,
 * the page puts the replay's per-road first-reached times here with the moment to show; the layer then draws each
 * road's MODELLED class at that moment from IMD's OBSERVED rain, and every pick text and the chip say so. The
 * version counter tells the layer to redraw.
 */
import type { ReplaySegment } from './types';

export interface HindsightView {
	on: boolean;
	/** The moment shown (epoch ms). */
	at: number | null;
	segments: ReadonlyMap<number, ReplaySegment>;
	version: number;
}

export const hindsight: HindsightView = { on: false, at: null, segments: new Map(), version: 0 };

export function showHindsight(segments: readonly ReplaySegment[], at: number): void {
	hindsight.on = true;
	hindsight.at = at;
	hindsight.segments = new Map(segments.map((s) => [s.segment_id, s]));
	hindsight.version++;
}

export function hideHindsight(): void {
	if (!hindsight.on) return;
	hindsight.on = false;
	hindsight.at = null;
	hindsight.segments = new Map();
	hindsight.version++;
}
