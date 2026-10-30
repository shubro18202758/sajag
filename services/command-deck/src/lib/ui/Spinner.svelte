<script lang="ts">
	/**
	 * Spinner — loading indicator (Blueprint geometry). Indeterminate by
	 * default (a quarter arc turning); `value` 0..1 makes it determinate.
	 * role="progressbar" with an accessible name ("Loading" by default).
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { uiLang, ut } from './lang';
	import type { Intent } from './types';

	interface Props extends HTMLAttributes<HTMLSpanElement> {
		size?: number;
		intent?: Intent;
		value?: number | null;
		label?: string;
		lang?: string;
	}

	let { size = 20, intent = 'none', value = null, label, lang, class: cls = '', ...rest }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	const R = 45;
	const LEN = 280;
	const stroke = $derived(Math.min(16, (4 * 100) / Math.max(1, size)));
	const determinate = $derived(typeof value === 'number' && Number.isFinite(value));
	const frac = $derived(determinate ? Math.min(1, Math.max(0, value as number)) : 0.25);
	const offset = $derived(LEN - LEN * frac);
</script>

<span
	data-ui="spinner"
	class={['spinner', `i-${intent}`, !determinate && 'turning', cls]}
	role="progressbar"
	aria-label={label ?? ut(L, 'ui_loading')}
	aria-valuemin={determinate ? 0 : undefined}
	aria-valuemax={determinate ? 100 : undefined}
	aria-valuenow={determinate ? Math.round(frac * 100) : undefined}
	style:width="{size}px"
	style:height="{size}px"
	{...rest}
>
	<svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
		<path
			class="track"
			d="M 50,50 m 0,-{R} a {R},{R} 0 1 1 0,{2 * R} a {R},{R} 0 1 1 0,-{2 * R}"
			stroke-width={stroke}
		/>
		<path
			class="head"
			d="M 50,50 m 0,-{R} a {R},{R} 0 1 1 0,{2 * R} a {R},{R} 0 1 1 0,-{2 * R}"
			pathLength={LEN}
			stroke-dasharray="{LEN} {LEN}"
			stroke-dashoffset={offset}
			stroke-width={stroke}
		/>
	</svg>
</span>

<style>
	.spinner {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		justify-content: center;
		vertical-align: middle;
		color: var(--v-ink-2);
	}

	.spinner svg {
		display: block;
		overflow: visible;
	}

	.track {
		fill: none;
		stroke: var(--v-line-2);
	}

	.head {
		fill: none;
		stroke: currentColor;
		stroke-linecap: round;
		transform-origin: center;
		transition: stroke-dashoffset var(--v-dur-in) var(--v-ease);
	}

	.turning svg {
		animation: turn 600ms linear infinite;
	}

	.i-primary {
		color: var(--v-primary-text);
	}

	.i-success {
		color: var(--v-success-text);
	}

	.i-warning {
		color: var(--v-warning-text);
	}

	.i-danger {
		color: var(--v-danger-text);
	}

	@keyframes turn {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(360deg);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.turning svg {
			animation-duration: 1800ms;
		}
	}
</style>
