<script lang="ts">
	/**
	 * ProgressBar — an 8 px track with a meter: `value` 0..1 is
	 * determinate; null is indeterminate (moving stripes, static under
	 * reduced motion). Intent colours the meter (warning for an expiry bar).
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import type { Intent } from './types';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		value?: number | null;
		intent?: Intent;
		stripes?: boolean;
		label?: string;
	}

	let { value = null, intent = 'none', stripes = true, label, class: cls = '', ...rest }: Props = $props();

	const determinate = $derived(typeof value === 'number' && Number.isFinite(value));
	const pct = $derived(determinate ? Math.round(Math.min(1, Math.max(0, value as number)) * 1000) / 10 : 100);
</script>

<div
	data-ui="progress-bar"
	role="progressbar"
	aria-label={label}
	aria-valuemin={determinate ? 0 : undefined}
	aria-valuemax={determinate ? 100 : undefined}
	aria-valuenow={determinate ? pct : undefined}
	class={['pb', `i-${intent}`, !determinate && stripes && 'indeterminate', cls]}
	{...rest}
>
	<div class="meter" style:width="{pct}%"></div>
</div>

<style>
	.pb {
		position: relative;
		width: 100%;
		height: 8px;
		overflow: hidden;
		border-radius: var(--v-radius-pill);
		background: color-mix(in srgb, var(--v-surface-sink) 50%, transparent);
	}

	.meter {
		height: 100%;
		border-radius: var(--v-radius-pill);
		background: var(--v-ink-2);
		transition: width var(--v-dur-in) var(--v-ease);
	}

	.i-primary .meter {
		background: var(--v-primary);
	}

	.i-success .meter {
		background: var(--v-success);
	}

	.i-warning .meter {
		background: var(--v-warning-text);
	}

	.i-danger .meter {
		background: var(--v-danger);
	}

	.indeterminate .meter {
		background-image: linear-gradient(
			-45deg,
			color-mix(in srgb, var(--v-surface-sink) 30%, transparent) 25%,
			transparent 25%,
			transparent 50%,
			color-mix(in srgb, var(--v-surface-sink) 30%, transparent) 50%,
			color-mix(in srgb, var(--v-surface-sink) 30%, transparent) 75%,
			transparent 75%
		);
		background-size: 30px 30px;
		animation: stripes 300ms linear infinite reverse;
	}

	@keyframes stripes {
		from {
			background-position: 0 0;
		}
		to {
			background-position: 30px 0;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.indeterminate .meter {
			animation: none;
		}
	}
</style>
