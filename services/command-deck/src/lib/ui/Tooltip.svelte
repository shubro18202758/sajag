<script lang="ts">
	/**
	 * Tooltip — inverted (light on the dark theme, dark on daylight), 12 px,
	 * no arrow. Opens on hover after a short delay and on keyboard focus;
	 * closes on leave, blur, press or scroll. The bubble is portalled to
	 * <body> (no dock can clip it) and carries the declaring subtree's theme.
	 *
	 * The target is the children; the wrapper is `display: contents`, so the
	 * target keeps its own layout. Works on disabled buttons (Chrome
	 * dispatches pointer events on disabled controls). `...rest` goes on the
	 * wrapper; the bubble is [data-ui="tooltip"] with role="tooltip" and is
	 * named by aria-describedby on the target while open.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import { placeFloating, portal, targetOf } from './overlay';
	import type { Placement } from './types';

	interface Props extends Omit<HTMLAttributes<HTMLSpanElement>, 'content'> {
		/** Plain text, or a snippet for formatted content. Empty = no tooltip. */
		content: string | Snippet | null | undefined;
		placement?: Placement;
		disabled?: boolean;
		/** Hover delay before opening, ms. */
		openDelay?: number;
		children?: Snippet;
	}

	let {
		content,
		placement = 'top',
		disabled = false,
		openDelay = 150,
		children,
		...rest
	}: Props = $props();

	const uid = $props.id();
	const bubbleId = `${uid}-tip`;

	let wrapper: HTMLSpanElement | undefined = $state();
	let bubble: HTMLDivElement | undefined = $state();
	let open = $state(false);
	let pos = $state<{ top: number; left: number } | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;

	const hasContent = $derived(typeof content === 'function' || (typeof content === 'string' && content.trim() !== ''));

	function show(delay = openDelay) {
		if (disabled || !hasContent || open) return;
		clearTimeout(timer);
		timer = setTimeout(() => {
			pos = null;
			open = true;
		}, delay);
	}

	function hide() {
		clearTimeout(timer);
		open = false;
	}

	function onOut(e: PointerEvent) {
		const to = e.relatedTarget as Node | null;
		if (to && wrapper?.contains(to)) return;
		hide();
	}

	function onFocusIn(e: FocusEvent) {
		const el = e.target as Element | null;
		if (el?.matches?.(':focus-visible')) show(0);
	}

	$effect(() => {
		if (!open || !bubble || !wrapper) return;
		const target = targetOf(wrapper);
		if (!target) return;
		const r = target.getBoundingClientRect();
		const b = bubble.getBoundingClientRect();
		const p = placeFloating(r, { width: b.width, height: b.height }, placement, {
			width: window.innerWidth,
			height: window.innerHeight
		}, 6);
		pos = { top: p.top, left: p.left };
		target.setAttribute('aria-describedby', bubbleId);
		const onScroll = () => hide();
		window.addEventListener('scroll', onScroll, true);
		return () => {
			window.removeEventListener('scroll', onScroll, true);
			if (target.getAttribute('aria-describedby') === bubbleId) target.removeAttribute('aria-describedby');
		};
	});

	$effect(() => () => clearTimeout(timer));
</script>

<span
	class="tt"
	bind:this={wrapper}
	onpointerover={() => show()}
	onpointerout={onOut}
	onpointerdown={hide}
	onfocusin={onFocusIn}
	onfocusout={hide}
	{...rest}
>
	{@render children?.()}
</span>
{#if open}
	<div
		class="tooltip"
		role="tooltip"
		id={bubbleId}
		data-ui="tooltip"
		use:portal
		bind:this={bubble}
		style:top={pos ? `${pos.top}px` : '0px'}
		style:left={pos ? `${pos.left}px` : '0px'}
		style:visibility={pos ? 'visible' : 'hidden'}
	>
		{#if typeof content === 'function'}{@render content()}{:else}{content}{/if}
	</div>
{/if}

<style>
	.tt {
		display: contents;
	}

	.tooltip {
		position: fixed;
		z-index: var(--v-z-tooltip);
		max-width: 320px;
		padding: 4px 8px;
		border-radius: var(--v-radius-chip);
		background: var(--v-tooltip-bg);
		color: var(--v-tooltip-ink);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		font-weight: 400;
		white-space: normal;
		overflow-wrap: anywhere;
		pointer-events: none;
		box-shadow:
			0 2px 4px color-mix(in srgb, var(--v-backdrop) 55%, transparent),
			0 8px 24px color-mix(in srgb, var(--v-backdrop) 55%, transparent);
	}

	.tooltip :global(b),
	.tooltip :global(strong) {
		font-weight: 600;
	}
</style>
