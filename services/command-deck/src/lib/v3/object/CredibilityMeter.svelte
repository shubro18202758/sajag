<script lang="ts">
	/**
	 * CredibilityMeter (V3-SPEC §5.4, §6.3, "How sure are we") — the oracle's credibility as a gauge (two
	 * decimals, never more), four plain checks (model.ts credibilityChecks: independent publishers, the place
	 * match, an official source by TIER, another kind of source), the verification ladder, and the honest
	 * line: credibility says how far the sources agree, not that the report is true. A district alert in effect
	 * is context and never one of these checks.
	 */
	import { t } from '$lib/i18n/strings';
	import './packs.object';
	import Glyph from '../Glyph.svelte';
	import VerificationLadder from './VerificationLadder.svelte';
	import type { Check } from './model';

	let { credibility, checks, verification, lang }: { credibility: number | null; checks: readonly Check[]; verification: string | null; lang: string } = $props();

	const C = 2 * Math.PI * 15;
	const value = $derived(credibility != null ? Math.max(0, Math.min(1, credibility)) : null);
	const shownValue = $derived(value != null ? value.toFixed(2) : '—');
</script>

<div class="meter" data-testid="obj-credibility" data-credibility={shownValue}>
	<div class="gauge" role="img" aria-label={t(lang, 'obj_gauge_aria', shownValue)}>
		<svg viewBox="0 0 36 36" aria-hidden="true">
			<circle class="track" cx="18" cy="18" r="15" />
			{#if value != null}<circle class="fill" cx="18" cy="18" r="15" stroke-dasharray={C} stroke-dashoffset={C * (1 - value)} />{/if}
		</svg>
		<b aria-hidden="true">{shownValue}</b>
	</div>
	<ul class="checks">
		{#each checks as c (c.id)}
			<li class={c.ok ? 'y' : 'n'} data-check={c.id} data-ok={c.ok ? 'true' : 'false'}>
				<Glyph name={c.ok ? 'check' : 'close'} size={18} />
				<span>{t(lang, c.key, ...c.args)}</span>
			</li>
		{/each}
	</ul>
</div>
<VerificationLadder {verification} {lang} />
<p class="note"><Glyph name="info" size={17} />{t(lang, 'obj_cred_note')}</p>

<style>
	.meter {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 22px;
		align-items: center;
	}

	.gauge {
		position: relative;
		width: 110px;
		height: 110px;
	}

	.gauge svg {
		width: 110px;
		height: 110px;
		transform: rotate(-90deg);
	}

	.track,
	.fill {
		fill: none;
		stroke-width: 3.2;
	}

	.track {
		stroke: var(--v3-s4);
	}

	.fill {
		stroke: var(--v3-t1);
		stroke-linecap: round;
	}

	.gauge b {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		color: var(--v3-t1);
		font-size: 26px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.checks {
		display: flex;
		flex-direction: column;
		gap: 9px;
		margin: 0;
		padding: 0;
		font-size: 14px;
		line-height: 20px;
		list-style: none;
	}

	.checks li {
		display: flex;
		align-items: flex-start;
		gap: 10px;
	}

	.checks li :global(.v3-glyph) {
		margin-top: 1px;
	}

	.y {
		color: var(--v3-ok-text);
	}

	.y span {
		color: var(--v3-t1);
	}

	.n {
		color: var(--v3-t3);
	}

	.n span {
		color: var(--v3-t2);
	}

	.note {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 19px;
	}

	.note :global(.v3-glyph) {
		margin-top: 1px;
		color: var(--v3-t3);
	}
</style>
