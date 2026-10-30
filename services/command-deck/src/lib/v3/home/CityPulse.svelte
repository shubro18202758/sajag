<script lang="ts">
	/**
	 * CityPulse (V3-SPEC §5.2, §6.1) — the city in one sentence and four numbers. The band sentence ("The
	 * city is steady", never green when the band is not known), when it was entered and when it was last
	 * read; four tiles that link to where each number is worked (decisions, live operations, reported
	 * events, watchlisted vehicles — plates hidden until an officer is named); and the systems line
	 * (cameras answering, the traffic feed's provenance) — or, when a feed is down, one neutral warning row
	 * that says which feed, since when, and that decisions still work.
	 *
	 * V3-P7: the card opens on the city itself — a wide illustrated scene of the city (the City Pack's, Mumbai) for the time of day (dawn, day,
	 * dusk, night), the greeting band; it fades into the card so the sentence below reads on the plain surface.
	 *
	 * Every count is a canonical selector's (cardFigures / selectors.decisionUnits(), SPEC v2 §7.4): the
	 * page passes them in; nothing here counts.
	 *
	 * Under the systems line: "Next 2 hours" ($lib/ai NextHours — the forecast crossings, waterlogging risk, the
	 * tide and the signal-timing proposals waiting, each with its honest label) and the 19 Aug 2025 replay; then the
	 * City row ($lib/cityfeeds CityChips: Air · Heat · Cyclone · River · Quake, each with its honest label).
	 */
	import { t } from '$lib/i18n/strings';
	import '../packs.v3';
	import Glyph from '../Glyph.svelte';
	import type { PulseStat } from './view';
	import { onMount, type Component } from 'svelte';

	let {
		band,
		sentence,
		meta,
		stats,
		systems,
		down = null,
		onRetry,
		lang,
		scene = null,
	}: {
		scene?: { src: string; alt: string } | null;
		band: string | null;
		sentence: string;
		meta: string;
		stats: PulseStat[];
		systems: { text: string; ok: boolean }[];
		down?: string | null;
		onRetry?: () => void;
		lang: string;
	} = $props();

	/** "Next 2 hours" ($lib/ai) loads after Home's first paint: its store, model and strings stay out of the route's eager graph. */
	let NextHours = $state<Component<{ lang: string }> | null>(null);
	/** The City row ($lib/cityfeeds: Air · Heat · Cyclone · River · Quake) loads the same way, after first paint. */
	let CityChips = $state<Component<{ lang: string; variant?: 'map' | 'home' }> | null>(null);
	onMount(() => {
		void import('$lib/ai/ui/NextHours.svelte').then((m) => (NextHours = m.default as unknown as Component<{ lang: string }>));
		void import('$lib/cityfeeds/CityChips.svelte').then((m) => (CityChips = m.default as unknown as Component<{ lang: string; variant?: 'map' | 'home' }>));
	});
</script>

<aside class={['pulse', scene && 'has-scene']} aria-label={t(lang, 'v3_pulse_aria')} data-testid="v3-pulse" data-band={band ?? 'unknown'}>
	{#if scene}
		<div class="scene" data-testid="v3-scene"><img src={scene.src} alt={scene.alt} width="960" height="320" loading="eager" decoding="async" /></div>
	{/if}
	<div class="head">
		<div class="state">
			<span class={['ring', `b-${(band ?? 'unknown').toLowerCase()}`]} role="img" aria-label={t(lang, 'v3_band_ring', band ? t(lang, `v3_band_${band.toLowerCase()}`) : '—')}>
				<Glyph name={band === 'GREEN' ? 'check' : band ? 'alert' : 'info'} size={28} />
			</span>
			<div class="st">
				<h2 class="h">{sentence}</h2>
				<!-- the heartbeat: a dot that breathes while the feeds answer (still and grey when one is down); each refresh
				     (a new "updated" time) restarts its ripple, so the console visibly lives -->
				<span class="meta">{#key meta}<span class={['beat', down && 'still']} aria-hidden="true" data-testid="v3-heartbeat"></span>{/key}{meta}</span>
			</div>
		</div>
		<a class="link" href="/map">{t(lang, 'v3_open_map')}<Glyph name="chevR" size={16} /></a>
	</div>
	<ul class="stats">
		{#each stats as s (s.id)}
			<li>
				<a class={['stat', s.decide && s.n > 0 && 'decide']} href={s.href} data-testid="v3-stat" data-stat={s.id} data-n={s.n}>
					<b>{s.n}</b>
					<span class="lbl">{s.label}</span>
					{#if s.sub}<span class="sub">{s.sub}</span>{/if}
				</a>
			</li>
		{/each}
	</ul>
	{#if down}
		<div class="down" role="status" data-testid="v3-feed-down">
			<img src="/illustrations/empty/offline.svg" alt="" width="64" height="40" />
			<span>{down}</span>
			{#if onRetry}<button type="button" class="link" onclick={onRetry}>{t(lang, 'v3_sys_retry')}</button>{/if}
		</div>
	{:else}
		<div class="systems" data-testid="v3-systems">
			{#each systems as s, i (i)}
				{#if i}<span aria-hidden="true">·</span>{/if}
				<span class={[s.ok && 'ok']}>{#if s.ok}<Glyph name="check" size={16} />{/if}{s.text}</span>
			{/each}
			<span aria-hidden="true">·</span>
			<a class="link" href="/ops">{t(lang, 'v3_sys_details')}</a>
		</div>
	{/if}
	{#if NextHours}<NextHours {lang} />{/if}
	{#if CityChips}<CityChips {lang} variant="home" />{/if}
</aside>

<style>
	.pulse {
		display: flex;
		flex-direction: column;
		gap: 18px;
		min-width: 0;
		padding: 24px 26px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
	}

	.scene {
		position: relative;
		height: 116px;
		margin: -24px -26px -6px;
		overflow: hidden;
		border-radius: var(--v3-radius-xl) var(--v3-radius-xl) 0 0;
	}

	.scene img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: 50% 62%;
	}

	.scene::after {
		content: '';
		position: absolute;
		inset: 0;
		background: linear-gradient(to bottom, transparent 30%, var(--v3-s1));
	}

	.head {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}

	.state {
		display: flex;
		align-items: center;
		gap: 14px;
		min-width: 0;
	}

	.ring {
		display: grid;
		place-items: center;
		flex: none;
		width: 54px;
		height: 54px;
		border-radius: 50%;
		background: var(--v3-s3);
		color: var(--v3-t2);
	}

	.ring.b-green {
		background: var(--v3-ok-veil);
		color: var(--v3-ok-text);
	}

	.ring.b-amber {
		background: var(--v3-decide-veil);
		color: var(--v3-decide-text);
	}

	.ring.b-red,
	.ring.b-black {
		background: var(--v3-alert-veil);
		color: var(--v3-alert-text);
	}

	.st {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.h {
		margin: 0;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 640;
	}

	.meta {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		font-weight: 500;
		font-variant-numeric: tabular-nums;
	}

	.beat {
		position: relative;
		display: inline-block;
		width: 7px;
		height: 7px;
		margin: 0 8px 1px 1px;
		border-radius: 50%;
		background: var(--v3-ok);
		vertical-align: middle;
		animation: v3-breathe 2.4s ease-in-out infinite;
	}

	.beat::after {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: 50%;
		box-shadow: 0 0 0 0 var(--v3-ok);
		animation: v3-ripple 1.2s var(--v3-ease) 1 both;
	}

	.beat.still {
		background: var(--v3-t3);
		animation: none;
	}

	.beat.still::after {
		animation: none;
	}

	@keyframes v3-breathe {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.45;
		}
	}

	@keyframes v3-ripple {
		from {
			opacity: 0.7;
			box-shadow: 0 0 0 0 var(--v3-ok);
		}
		to {
			opacity: 0;
			box-shadow: 0 0 0 7px var(--v3-ok);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.beat,
		.beat::after {
			animation: none;
		}
	}

	.link {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 0;
		border: 0;
		background: none;
		color: var(--v3-brand-text);
		font: inherit;
		font-weight: 600;
		text-decoration: none;
		white-space: nowrap;
		cursor: pointer;
	}

	.link:hover {
		text-decoration: underline;
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.stats li {
		display: flex;
		min-width: 0;
	}

	.stat {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
		padding: 14px 16px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		color: var(--v3-t1);
		text-decoration: none;
		transition: background var(--v3-dur-1);
	}

	.stat:hover {
		background: var(--v3-s3);
	}

	.stat b {
		font-size: var(--v3-text-stat);
		line-height: var(--v3-lh-stat);
		font-weight: 650;
		font-variant-numeric: tabular-nums;
	}

	.stat.decide b {
		color: var(--v3-decide-text);
	}

	.lbl {
		color: var(--v3-t2);
		font-size: 14px;
		line-height: 20px;
		font-weight: 500;
	}

	.sub {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.systems,
	.down {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
		padding-top: 14px;
		border-top: 1px solid var(--v3-line-1);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.systems .ok {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--v3-ok-text);
	}

	.down img {
		flex: none;
		width: 64px;
		height: auto;
	}

	.down span {
		flex: 1;
		min-width: 0;
	}

	.link:focus-visible,
	.stat:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	@media (max-width: 1500px) {
		.pulse {
			gap: 14px;
			padding: 20px;
		}

		.scene {
			height: 84px;
			margin: -20px -20px -4px;
		}

		.stat {
			padding: 12px 14px;
		}

		.sub {
			display: none;
		}

		.systems {
			font-size: 12px;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.stat {
			transition: none;
		}
	}
</style>
