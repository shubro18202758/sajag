/**
 * Overlay plumbing shared by Popover, Tooltip, Dialog, Alert, Drawer and
 * HotkeysDialog: a portal that keeps the theme, one Escape stack, a focus
 * trap, outside-pointer detection and the floating-placement math.
 *
 * Every floating thing is portalled to <body> so no dock's stacking context
 * or overflow can clip it; the portal copies the nearest data-theme of the
 * place it was declared, so a daylight subtree's popover is still daylight.
 * Svelte context (the UI language) is unaffected by the DOM move.
 *
 * Usage contract for portal(): the element carrying use:portal must be the
 * ONLY root node of its {#if} block (Svelte removes a block's nodes by
 * walking siblings from its first node).
 */

// ── portal ──────────────────────────────────────────────────────────────────

/** Move a node under <body>, carrying the declaring subtree's theme. */
export function portal(node: HTMLElement, _opts?: unknown): { destroy(): void } {
	const host = node.parentElement?.closest('[data-theme]');
	const theme =
		host?.getAttribute('data-theme') ?? document.documentElement.getAttribute('data-theme') ?? 'command';
	node.setAttribute('data-theme', theme);
	document.body.appendChild(node);
	return {
		destroy() {
			if (node.isConnected) node.remove();
		}
	};
}

// ── Escape: one stack, topmost layer only ────────────────────────────────────

interface Layer {
	id: number;
	close: () => void;
	escape: () => boolean;
	/** The overlay's own element (its panel or container), for outside-pointer checks. */
	el: () => Element | null | undefined;
}

/** What pushLayer returns: call it to unregister; `above()` lists the overlays opened after this one. */
export interface LayerHandle {
	(): void;
	/**
	 * The elements of the overlays still open above this one (a popover
	 * opened from inside it, a dialog opened from its menu). A pointer inside
	 * them is not "outside" this overlay: they are its descendants in the
	 * stack, as in Blueprint's overlay stack.
	 */
	above(): Element[];
}

const layers: Layer[] = [];
let seq = 0;
let listening = false;

function onKeydown(e: KeyboardEvent): void {
	if (e.key !== 'Escape' || layers.length === 0) return;
	const top = layers[layers.length - 1];
	// The topmost overlay owns Escape: nothing underneath (another overlay,
	// the page, the shell's "Esc clears") sees this press.
	e.stopPropagation();
	e.preventDefault();
	if (top.escape()) top.close();
}

/**
 * Register an open overlay. Escape closes the topmost one only, and never
 * reaches the page while any overlay is open. `el` returns the overlay's own
 * element, so the overlays beneath it treat a pointer inside it as inside
 * themselves. Returns the unregister function (with `above()`).
 */
export function pushLayer(
	close: () => void,
	escape: () => boolean = () => true,
	el: () => Element | null | undefined = () => null
): LayerHandle {
	const id = ++seq;
	layers.push({ id, close, escape, el });
	if (!listening && typeof window !== 'undefined') {
		window.addEventListener('keydown', onKeydown, true);
		listening = true;
	}
	const off = () => {
		const i = layers.findIndex((l) => l.id === id);
		if (i >= 0) layers.splice(i, 1);
		if (layers.length === 0 && listening) {
			window.removeEventListener('keydown', onKeydown, true);
			listening = false;
		}
	};
	return Object.assign(off, {
		above(): Element[] {
			const i = layers.findIndex((l) => l.id === id);
			if (i < 0) return [];
			return layers
				.slice(i + 1)
				.map((l) => l.el())
				.filter((e): e is Element => !!e);
		}
	});
}

/** The number of open overlays (the gallery and tests read it). */
export function openLayerCount(): number {
	return layers.length;
}

// ── focus ───────────────────────────────────────────────────────────────────

const FOCUSABLE =
	'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), ' +
	'textarea:not([disabled]), [tabindex]:not([tabindex="-1"]), [contenteditable="true"]';

/** Focusable descendants in DOM order (rendered ones only), tabindex="-1" included. */
export function focusables(root: HTMLElement): HTMLElement[] {
	return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
		(el) => el.getClientRects().length > 0 || el === document.activeElement
	);
}

/**
 * The Tab stops among them: a roving widget's other items (a Menu's, a
 * Tree's, a DataTable's rows, carets and chevrons at tabindex -1) are
 * focusable but never reached with Tab, so they are never a trap's ends.
 */
export function tabbables(root: HTMLElement): HTMLElement[] {
	return focusables(root).filter((el) => el.tabIndex >= 0);
}

/**
 * True when Tab (or Shift+Tab, `back`) from `active` would leave `root`:
 * no Tab stop of `root` follows (or precedes) it in DOM order. A Tab stop
 * that contains `active` precedes it (Shift+Tab from a row's button lands
 * on the row), and one inside it follows it.
 */
export function tabLeaves(root: HTMLElement, active: Element | null, back: boolean): boolean {
	if (!active || !root.contains(active)) return true;
	const flag = back ? Node.DOCUMENT_POSITION_PRECEDING : Node.DOCUMENT_POSITION_FOLLOWING;
	return !tabbables(root).some((el) => el !== active && (active.compareDocumentPosition(el) & flag) !== 0);
}

/**
 * Keep Tab inside `node` while it is mounted; on mount focus a
 * [data-autofocus] descendant, else the node itself when it carries
 * data-focus-self, else the first Tab stop; give focus back to the opener
 * on destroy. `{ trap: false }` (a non-modal panel) keeps the initial and
 * returned focus but lets Tab leave.
 */
export function trapFocus(node: HTMLElement, opts?: { trap?: boolean } | null): { destroy(): void } {
	const trap = opts?.trap !== false;
	const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
	queueMicrotask(() => {
		if (!node.isConnected) return;
		// a [data-autofocus] descendant wins; a node marked data-focus-self takes focus
		// itself (a dialog's panel, so Enter cannot hit an action by accident)
		const preferred =
			node.querySelector<HTMLElement>('[data-autofocus]') ?? (node.hasAttribute('data-focus-self') ? node : null);
		const first = preferred ?? tabbables(node)[0] ?? node;
		if (first === node && !node.hasAttribute('tabindex')) node.setAttribute('tabindex', '-1');
		first.focus({ preventScroll: true });
	});
	function onKey(e: KeyboardEvent) {
		if (e.key !== 'Tab' || !trap) return;
		const list = tabbables(node);
		if (list.length === 0) {
			e.preventDefault();
			return;
		}
		// wrap at either end (measured from the focused element, so a roving
		// item at tabindex -1 cannot let Tab out of the trap)
		if (!tabLeaves(node, document.activeElement, e.shiftKey)) return;
		e.preventDefault();
		(e.shiftKey ? list[list.length - 1] : list[0]).focus();
	}
	node.addEventListener('keydown', onKey);
	return {
		destroy() {
			node.removeEventListener('keydown', onKey);
			if (opener && opener.isConnected) opener.focus({ preventScroll: true });
		}
	};
}

// ── outside pointer ─────────────────────────────────────────────────────────

/**
 * Call `handler` on a pointerdown outside every element `inside()` returns.
 * Returns the unsubscribe function.
 */
export function onOutsidePointer(inside: () => (Element | null | undefined)[], handler: () => void): () => void {
	function listener(e: PointerEvent) {
		const t = e.target as Node | null;
		if (!t) return;
		for (const el of inside()) if (el && el.contains(t)) return;
		handler();
	}
	document.addEventListener('pointerdown', listener, true);
	return () => document.removeEventListener('pointerdown', listener, true);
}

// ── placement ───────────────────────────────────────────────────────────────

export interface Rect {
	top: number;
	left: number;
	width: number;
	height: number;
}

export type Side = 'top' | 'bottom' | 'left' | 'right';
export type Align = 'start' | 'center' | 'end';

/**
 * Where a floating box of `size` goes against `anchor` inside a `viewport`:
 * the requested side, flipped to the opposite side when it does not fit and
 * the opposite does, then clamped `margin` px inside the viewport. Pure.
 */
export function placeFloating(
	anchor: Rect,
	size: { width: number; height: number },
	placement: string,
	viewport: { width: number; height: number },
	gap = 4,
	margin = 4
): { top: number; left: number; side: Side } {
	const [sideRaw, alignRaw] = placement.split('-') as [string, string | undefined];
	let side: Side = sideRaw === 'top' || sideRaw === 'left' || sideRaw === 'right' ? sideRaw : 'bottom';
	const align: Align = alignRaw === 'start' || alignRaw === 'end' ? alignRaw : 'center';

	const room = {
		top: anchor.top - gap - margin,
		bottom: viewport.height - (anchor.top + anchor.height) - gap - margin,
		left: anchor.left - gap - margin,
		right: viewport.width - (anchor.left + anchor.width) - gap - margin
	};
	const need = side === 'top' || side === 'bottom' ? size.height : size.width;
	const opposite: Record<Side, Side> = { top: 'bottom', bottom: 'top', left: 'right', right: 'left' };
	if (room[side] < need && room[opposite[side]] > room[side]) side = opposite[side];

	let top: number;
	let left: number;
	if (side === 'top' || side === 'bottom') {
		top = side === 'top' ? anchor.top - gap - size.height : anchor.top + anchor.height + gap;
		left =
			align === 'start'
				? anchor.left
				: align === 'end'
					? anchor.left + anchor.width - size.width
					: anchor.left + anchor.width / 2 - size.width / 2;
	} else {
		left = side === 'left' ? anchor.left - gap - size.width : anchor.left + anchor.width + gap;
		top =
			align === 'start'
				? anchor.top
				: align === 'end'
					? anchor.top + anchor.height - size.height
					: anchor.top + anchor.height / 2 - size.height / 2;
	}
	left = Math.max(margin, Math.min(viewport.width - size.width - margin, left));
	top = Math.max(margin, Math.min(viewport.height - size.height - margin, top));
	return { top: Math.round(top), left: Math.round(left), side };
}

/** The first element child of a `display: contents` wrapper (the real target box). */
export function targetOf(wrapper: HTMLElement | null | undefined): HTMLElement | null {
	if (!wrapper) return null;
	let el = (wrapper.firstElementChild as HTMLElement | null) ?? wrapper;
	// A `display: contents` wrapper (Tooltip around a Button) has no box, so placement would read an all-zero rect
	// and clamp the panel to the viewport corner: anchor on its first descendant that has a box.
	if (typeof getComputedStyle === 'function') {
		while (el !== wrapper && el.firstElementChild && getComputedStyle(el).display === 'contents') {
			el = el.firstElementChild as HTMLElement;
		}
	}
	return el;
}

/** True when the node sits inside a modal overlay (Dialog, Alert, a Drawer with a backdrop). */
export function insideModal(node: Element | null | undefined): boolean {
	return !!node?.closest('[data-ui-overlay="modal"]');
}

/**
 * True when the node sits inside any overlay on the dialog layer: a modal,
 * or a non-modal panel (a Drawer without a backdrop, [data-ui-overlay=
 * "panel"]). Popovers opened there take the dialog layer so they draw above it.
 */
export function insideOverlay(node: Element | null | undefined): boolean {
	return !!node?.closest('[data-ui-overlay]');
}
