/**
 * What a mounted WorkspaceFrame tells the components inside it (the
 * inspector's actions need to know which centre views the page composes and
 * which route it is on). A component outside any frame gets the defaults.
 */
import { getContext, setContext } from 'svelte';
import type { TabRoute, View } from '../../types';

export interface FrameContext {
	views: () => readonly View[];
	route: () => TabRoute;
	mode: () => 'workspace' | 'map';
}

const KEY = Symbol.for('sajag.workspace.frame');

export function provideFrame(ctx: FrameContext): void {
	setContext(KEY, ctx);
}

/** The enclosing frame's context, or null outside a frame (the legacy City Command drawer). */
export function frameContext(): FrameContext | null {
	return getContext<FrameContext | undefined>(KEY) ?? null;
}
