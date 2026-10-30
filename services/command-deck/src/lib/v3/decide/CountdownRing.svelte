<script lang="ts">
	/**
	 * CountdownRing (V3-SPEC §5.3, §7.5, §7.7) — 72 px, drains linearly, `m:ss` in the middle, decision orange
	 * (alert red under 10 s). `role="timer"`; the polite announcement speaks ONLY at 30 s and at 10 s (a timer
	 * that talks every second is noise). Past zero it reads "0:00" and the sheet says the plan is kept.
	 */
	import { t } from '$lib/i18n/strings';
	import { fmtCountdown } from '$lib/ui/format/format';
	import './packs.decide';
	import { announceAt, ringFraction } from './model';

	let { leftSec, totalSec = 90, lang, size = 72 }: { leftSec: number; totalSec?: number | null; lang: string; size?: number } = $props();

	const R = 15.5;
	const C = 2 * Math.PI * R;
	const frac = $derived(ringFraction(leftSec, totalSec));
	const text = $derived(fmtCountdown(Math.max(0, leftSec)));

	let said = $state('');
	let prev: number | null = null;
	$effect(() => {
		const at = announceAt(prev, leftSec);
		prev = leftSec;
		if (at) said = t(lang, 'v3d_ring_announce', at);
	});
</script>

<div class="ring" class:urgent={leftSec <= 10} style:width="{size}px" style:height="{size}px" data-v3="countdown">
	<svg viewBox="0 0 36 36" aria-hidden="true" focusable="false">
		<circle class="track" cx="18" cy="18" r={R} />
		<circle class="arc" cx="18" cy="18" r={R} stroke-dasharray={C} stroke-dashoffset={C * (1 - frac)} />
	</svg>
	<b role="timer" aria-label={t(lang, 'v3d_ring_label', text)}>{text}</b>
	<span class="sr" aria-live="polite">{said}</span>
</div>

<style>
	.ring {
		position: relative;
		flex: none;
	}

	svg {
		width: 100%;
		height: 100%;
		transform: rotate(-90deg);
	}

	circle {
		fill: none;
		stroke-width: 3;
	}

	.track {
		stroke: var(--v3-s4);
	}

	.arc {
		stroke: var(--v3-decide);
		stroke-linecap: round;
		transition: stroke-dashoffset 1s linear;
	}

	.urgent .arc {
		stroke: var(--v3-alert);
	}

	b {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		font-size: 17px;
		font-weight: 750;
		color: var(--v3-decide-text);
		font-variant-numeric: tabular-nums;
	}

	.urgent b {
		color: var(--v3-alert-text);
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	@media (prefers-reduced-motion: reduce) {
		.arc {
			transition: none;
		}
	}
</style>
