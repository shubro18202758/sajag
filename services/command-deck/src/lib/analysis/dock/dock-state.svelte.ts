/**
 * What the analysis dock remembers between its tabs (the frame mounts one
 * tab at a time; FusionRail mounts all three): the range, the audit scope
 * and filters, and the cursor the operator put down while not live. The
 * time WINDOW is not here: it is the workspace store's (null ⇔ live).
 *
 * `clockOverride` pins "now" (the /design harness shows a captured fixture
 * at its capture time); nothing on a route sets it.
 */
import { DEFAULT_RANGE, type RangeId } from '../timeline/bins';
import type { AuditFilter, AuditScope } from '../audit/rows';

class DockState {
	/** A preset, or 'fit' (fitRange holds the span). */
	range = $state<RangeId | 'fit'>(DEFAULT_RANGE);
	fitSpan = $state.raw<[number, number] | null>(null);
	auditScope = $state<AuditScope>('city');
	auditFilter = $state<AuditFilter>('all');
	aiFilter = $state<AuditFilter>('all');
	/** The cursor the operator put down while not live (null: the window's end). */
	cursor = $state<number | null>(null);
	/** Standalone dock (FusionRail): its own size; 'auto' = full when the seven lanes fit at full size, else compact. */
	size = $state<'auto' | 'compact' | 'full'>('auto');
	/** A fixed "now" (the design harness only). */
	clockOverride = $state<number | null>(null);
	/** Playing the window forward (live mode's play). */
	playing = $state(false);
	/**
	 * The frame's bottom dock was raised to full by an analysis tab (Audit or
	 * AI trace opened it from compact). Remembered across the tabs — the frame
	 * mounts one tab at a time — so Audit → AI trace → Timeline still gives
	 * the timeline its compact size back.
	 */
	raisedBottom = $state(false);
}

export const dockState = new DockState();
