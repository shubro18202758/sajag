<script lang="ts">
	/**
	 * Splitter — the 1 px divider between two panes, draggable. `size` (px,
	 * bindable) is the size of the pane BEFORE the splitter (`reverse`: the
	 * pane after it); the parent lays the panes out with it. Pointer drag
	 * with capture; arrow keys step by `step` px (Shift ×4); Home/End jump
	 * to min/max. role="separator" with aria-valuenow.
	 *
	 * `orientation="vertical"` is a vertical bar between left and right
	 * panes (it resizes widths); "horizontal" sits between top and bottom.
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { uiLang, ut } from './lang';

	interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'onresize'> {
		size?: number;
		min?: number;
		max?: number;
		step?: number;
		orientation?: 'vertical' | 'horizontal';
		reverse?: boolean;
		onresize?: (size: number) => void;
		label?: string;
		lang?: string;
	}

	let {
		size = $bindable(300),
		min = 120,
		max = 2000,
		step = 16,
		orientation = 'vertical',
		reverse = false,
		onresize,
		label,
		lang,
		class: cls = '',
		...rest
	}: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	let dragging = $state(false);
	let start = { pos: 0, size: 0 };

	function clamp(v: number) {
		return Math.round(Math.min(max, Math.max(min, v)));
	}

	function set(v: number) {
		const next = clamp(v);
		if (next === size) return;
		size = next;
		onresize?.(next);
	}

	function down(e: PointerEvent) {
		if (e.button !== 0) return;
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
		dragging = true;
		start = { pos: orientation === 'vertical' ? e.clientX : e.clientY, size };
		e.preventDefault();
	}

	function move(e: PointerEvent) {
		if (!dragging) return;
		const pos = orientation === 'vertical' ? e.clientX : e.clientY;
		const delta = (pos - start.pos) * (reverse ? -1 : 1);
		set(start.size + delta);
	}

	function up(e: PointerEvent) {
		if (!dragging) return;
		dragging = false;
		(e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId);
	}

	function key(e: KeyboardEvent) {
		const inc = (e.shiftKey ? 4 : 1) * step;
		const grow = orientation === 'vertical' ? ['ArrowRight'] : ['ArrowDown'];
		const shrink = orientation === 'vertical' ? ['ArrowLeft'] : ['ArrowUp'];
		if (grow.includes(e.key)) set(size + (reverse ? -inc : inc));
		else if (shrink.includes(e.key)) set(size - (reverse ? -inc : inc));
		else if (e.key === 'Home') set(min);
		else if (e.key === 'End') set(max);
		else return;
		e.preventDefault();
	}
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex (a focusable separator is a widget: WAI-ARIA window splitter) -->
<div
	data-ui="splitter"
	role="separator"
	tabindex="0"
	aria-orientation={orientation}
	aria-label={label ?? ut(L, 'ui_resize')}
	aria-valuenow={size}
	aria-valuemin={min}
	aria-valuemax={max}
	class={['split', orientation, dragging && 'dragging', cls]}
	onpointerdown={down}
	onpointermove={move}
	onpointerup={up}
	onpointercancel={up}
	onkeydown={key}
	{...rest}
>
	<span class="line"></span>
</div>

<style>
	.split {
		position: relative;
		flex: 0 0 auto;
		z-index: 2;
		outline: 0;
		touch-action: none;
	}

	.vertical {
		width: 1px;
		align-self: stretch;
		cursor: col-resize;
	}

	.horizontal {
		height: 1px;
		width: 100%;
		cursor: row-resize;
	}

	/* a 9 px hit area around the 1 px line */
	.split::before {
		content: '';
		position: absolute;
	}

	.vertical::before {
		top: 0;
		bottom: 0;
		left: -4px;
		right: -4px;
	}

	.horizontal::before {
		left: 0;
		right: 0;
		top: -4px;
		bottom: -4px;
	}

	.line {
		position: absolute;
		inset: 0;
		background: var(--v-line-2);
		transition: background-color var(--v-dur-out) var(--v-ease);
	}

	.split:hover .line,
	.dragging .line,
	.split:focus-visible .line {
		background: var(--v-primary-text);
	}

	.vertical:hover .line,
	.vertical.dragging .line,
	.vertical:focus-visible .line {
		left: -1px;
		right: -1px;
	}

	.horizontal:hover .line,
	.horizontal.dragging .line,
	.horizontal:focus-visible .line {
		top: -1px;
		bottom: -1px;
	}
</style>
