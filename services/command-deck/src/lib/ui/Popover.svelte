<script lang="ts">
	/**
	 * Popover — floating content anchored to a target (menus, the Data and
	 * Policies panels, forms). Opens on click (or hover with
	 * interactionKind="hover"); closes on Escape (topmost overlay only), on a
	 * pointer outside, or through the `close` the content snippet receives.
	 * Portalled to <body> with the declaring subtree's theme, so no dock
	 * clips it; inside a Dialog or Drawer it takes the dialog layer.
	 *
	 * Nesting: a popover (or dialog) opened from inside this one sits above
	 * it in the overlay stack, and a pointer inside it is NOT outside this
	 * one, so the parent stays open while its child is used (the navbar's
	 * More popover holding Data and Policies).
	 *
	 * Focus (keyboard-first, SPEC §1.9): a click popover takes focus once it
	 * is placed and visible — a [data-autofocus] descendant, else the first
	 * [tabindex="0"] (a Menu's tab stop: its current choice, else its first
	 * item), else the panel itself — so Enter on the target then ArrowDown
	 * walks the menu. Tab past the last stop (or Shift+Tab before the first)
	 * closes it; closing with focus inside (a choice, Escape, Tab, a pointer
	 * outside) hands focus back to the target. `autofocus={false}` opts out;
	 * a hover popover never takes focus.
	 *
	 *   <Popover placement="bottom-end">
	 *     <Button icon="more" tooltip="More" />
	 *     {#snippet content({ close })}<Menu items={…} onselect={close} />{/snippet}
	 *   </Popover>
	 *
	 * `open` is bindable. The target gets aria-haspopup and aria-expanded.
	 * `...rest` goes on the floating panel ([data-ui="popover"]).
	 */
	import { tick, type Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import { insideOverlay, onOutsidePointer, placeFloating, portal, pushLayer, tabLeaves, targetOf } from './overlay';
	import type { Placement } from './types';

	interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'content'> {
		open?: boolean;
		placement?: Placement;
		interactionKind?: 'click' | 'hover';
		disabled?: boolean;
		matchTargetWidth?: boolean;
		/** The panel's role: 'dialog' (default) or 'menu' containers use their own roles inside. */
		role?: string;
		/** Move focus into the panel when a click opens it (default true; hover popovers never do). */
		autofocus?: boolean;
		onopenchange?: (open: boolean) => void;
		content: Snippet<[{ close: () => void }]>;
		children?: Snippet;
	}

	let {
		open = $bindable(false),
		placement = 'bottom-start',
		interactionKind = 'click',
		disabled = false,
		matchTargetWidth = false,
		role = 'dialog',
		autofocus = true,
		onopenchange,
		content,
		children,
		class: cls = '',
		...rest
	}: Props = $props();

	const uid = $props.id();
	let wrapper: HTMLSpanElement | undefined = $state();
	let panel: HTMLDivElement | undefined = $state();
	let pos = $state<{ top: number; left: number; width?: number } | null>(null);
	let layer = $state<'overlay' | 'dialog'>('overlay');
	let hoverTimer: ReturnType<typeof setTimeout> | undefined;

	function setOpen(v: boolean) {
		if (open === v) return;
		open = v;
		onopenchange?.(v);
	}

	/** Focus inside the panel goes back to the target (it would otherwise fall to <body> with the panel). */
	function returnFocus() {
		const active = document.activeElement;
		if (panel && active && panel.contains(active)) targetOf(wrapper)?.focus?.({ preventScroll: true });
	}

	function close() {
		returnFocus();
		setOpen(false);
	}

	const takesFocus = () => autofocus && interactionKind === 'click';

	/** Focus the panel's first stop: [data-autofocus], else [tabindex="0"], else the panel. */
	function focusInto(el: HTMLElement) {
		if (!el.isConnected || el.contains(document.activeElement)) return;
		const pick = el.querySelector<HTMLElement>('[data-autofocus]') ?? el.querySelector<HTMLElement>('[tabindex="0"]');
		pick?.focus();
		if (!el.contains(document.activeElement)) el.focus({ preventScroll: true });
	}

	/** Tab past either end leaves the popover: close it and go back to the target. */
	function onPanelKey(e: KeyboardEvent) {
		if (e.key !== 'Tab' || e.defaultPrevented || !panel || interactionKind !== 'click') return;
		if (!tabLeaves(panel, document.activeElement, e.shiftKey)) return;
		e.preventDefault();
		close();
	}

	function toggle() {
		if (disabled) return;
		setOpen(!open);
	}

	function place() {
		const target = targetOf(wrapper);
		if (!target || !panel) return;
		const r = target.getBoundingClientRect();
		if (matchTargetWidth) panel.style.minWidth = `${Math.round(r.width)}px`;
		const b = panel.getBoundingClientRect();
		const p = placeFloating(r, { width: b.width, height: b.height }, placement, {
			width: window.innerWidth,
			height: window.innerHeight
		});
		pos = { top: p.top, left: p.left };
	}

	// target ARIA
	$effect(() => {
		const target = targetOf(wrapper);
		if (!target) return;
		target.setAttribute('aria-haspopup', role === 'menu' ? 'menu' : 'dialog');
		target.setAttribute('aria-expanded', open ? 'true' : 'false');
		if (open) target.setAttribute('aria-controls', `${uid}-pop`);
		else target.removeAttribute('aria-controls');
	});

	// while open: position, focus, Escape, outside pointer, reposition on scroll/resize
	$effect(() => {
		if (!open || !panel) return;
		const el = panel;
		layer = insideOverlay(targetOf(wrapper)) ? 'dialog' : 'overlay';
		pos = null;
		let alive = true;
		// the panel stays visibility:hidden until placed, and a hidden element
		// cannot take focus: place it, let the DOM show it, then move focus in
		queueMicrotask(async () => {
			if (!alive) return;
			place();
			if (!takesFocus()) return;
			await tick();
			if (alive) focusInto(el);
		});
		// focus inside when the popover is closed from outside (bind:open) goes back too
		let focusWithin = false;
		const onFocusIn = () => (focusWithin = true);
		const onFocusOut = (e: FocusEvent) => {
			const to = e.relatedTarget as Node | null;
			if (to && !el.contains(to)) focusWithin = false;
		};
		el.addEventListener('focusin', onFocusIn);
		el.addEventListener('focusout', onFocusOut);
		const target = targetOf(wrapper);
		const popLayer = pushLayer(
			() => {
				close();
				target?.focus?.({ preventScroll: true });
			},
			() => true,
			() => panel
		);
		// inside = the target, this panel, and every overlay opened above this one
		const stopOutside = onOutsidePointer(() => [wrapper ? targetOf(wrapper) : null, panel, ...popLayer.above()], close);
		let raf = 0;
		const again = () => {
			cancelAnimationFrame(raf);
			raf = requestAnimationFrame(place);
		};
		window.addEventListener('resize', again);
		window.addEventListener('scroll', again, true);
		return () => {
			alive = false;
			popLayer();
			stopOutside();
			cancelAnimationFrame(raf);
			window.removeEventListener('resize', again);
			window.removeEventListener('scroll', again, true);
			el.removeEventListener('focusin', onFocusIn);
			el.removeEventListener('focusout', onFocusOut);
			const active = document.activeElement;
			if (focusWithin && (!active || active === document.body || el.contains(active))) target?.focus?.({ preventScroll: true });
		};
	});

	function hoverIn() {
		if (interactionKind !== 'hover' || disabled) return;
		clearTimeout(hoverTimer);
		hoverTimer = setTimeout(() => setOpen(true), 100);
	}

	function hoverOut(e: PointerEvent) {
		if (interactionKind !== 'hover') return;
		const to = e.relatedTarget as Node | null;
		if (to && (wrapper?.contains(to) || panel?.contains(to))) return;
		clearTimeout(hoverTimer);
		hoverTimer = setTimeout(() => setOpen(false), 150);
	}

	$effect(() => () => clearTimeout(hoverTimer));
</script>

<span
	class="target"
	bind:this={wrapper}
	onclick={interactionKind === 'click' ? toggle : undefined}
	onpointerover={hoverIn}
	onpointerout={hoverOut}
	role="presentation"
>
	{@render children?.()}
</span>
{#if open}
	<div
		id="{uid}-pop"
		data-ui="popover"
		role={role === 'menu' ? undefined : role}
		class={['popover', cls]}
		style:z-index={layer === 'dialog' ? 'var(--v-z-dialog)' : 'var(--v-z-overlay)'}
		style:top={pos ? `${pos.top}px` : '0px'}
		style:left={pos ? `${pos.left}px` : '0px'}
		style:visibility={pos ? 'visible' : 'hidden'}
		tabindex="-1"
		use:portal
		bind:this={panel}
		onpointerover={() => clearTimeout(hoverTimer)}
		onpointerout={hoverOut}
		onkeydown={onPanelKey}
		{...rest}
	>
		{@render content({ close })}
	</div>
{/if}

<style>
	.target {
		display: contents;
	}

	.popover {
		position: fixed;
		max-width: min(480px, calc(100vw - 8px));
		max-height: calc(100vh - 8px);
		overflow: auto;
		border-radius: var(--v-radius-modal);
		background: var(--v-surface-2);
		box-shadow:
			0 0 0 1px var(--v-popover-line),
			var(--v-elev-3);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	/* the panel holds focus only until Tab moves into its content */
	.popover:focus {
		outline: 0;
	}
</style>
