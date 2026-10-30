<script lang="ts">
	/**
	 * "Waterlogging on your road" (PLAN §2.4 B, public): the hydro nowcast for the next two hours in plain words, for the
	 * road the reader picks (remembered in this browser only) or the whole city; the sea tide and the rain the same
	 * way; and a Listen button that reads it aloud in the page's language. Everything is labelled MODELLED (the tide model
	 * is approximate, the rain a model nowcast, the pumps emulated). Reads only the three public hydro answers
	 * (GET /api/hydro/nowcast | tide | rain); no operator code, no location is asked for or sent.
	 */
	import { onMount } from 'svelte';
	import { localizeNumber, t } from '$lib/i18n/strings';
	import { clockAtMs } from '$lib/citizen/holds';
	import '$lib/v3/field/packs.field';
	import { atRisk, leadFor, rainWord, spokenClock, type Nowcast, type RainNow, type SegmentWater, type TideNow } from '$lib/v3/field/model';
	import { nowcast, rain as readRain, tide as readTide } from '$lib/v3/field/reads';
	import Glyph from '../Glyph.svelte';
	import PublicTag from './PublicTag.svelte';
	import ListenButton from './ListenButton.svelte';

	let { lang }: { lang: string } = $props();

	/** Every public string in the reader's digits (mr and hi ०–९), through the formatter. */
	const P = (key: string, ...args: unknown[]) => localizeNumber(t(lang, key, ...args), lang);
	const num = (v: number, digits = 1) => localizeNumber(Number(v.toFixed(digits)).toString(), lang);

	const STORE = 'sajag_my_road';
	let n = $state<Nowcast | null>(null);
	let tideNow = $state<TideNow | null>(null);
	let rainNow = $state<RainNow | null>(null);
	let status = $state<'loading' | 'ready' | 'down'>('loading');
	let pick = $state<number | null>(null);

	function load() {
		void nowcast()
			.then((x) => {
				n = x;
				status = 'ready';
			})
			.catch(() => {
				if (!n) status = 'down';
			});
		void readTide()
			.then((x) => (tideNow = x))
			.catch(() => undefined);
		void readRain()
			.then((x) => (rainNow = x))
			.catch(() => undefined);
	}

	onMount(() => {
		try {
			const v = Number(localStorage.getItem(STORE));
			if (Number.isInteger(v) && v > 0) pick = v;
		} catch {
			/* storage blocked: the city view */
		}
		load();
		const id = setInterval(load, 5 * 60_000);
		return () => clearInterval(id);
	});

	function choose(v: string) {
		pick = v ? Number(v) : null;
		try {
			if (pick) localStorage.setItem(STORE, String(pick));
			else localStorage.removeItem(STORE);
		} catch {
			/* storage blocked: the choice lasts this page view */
		}
	}

	const roadLabel = (s: SegmentWater) => {
		const place = lang === 'mr' ? (s.placeMr ?? s.place) : s.place;
		return place ? `${s.roadName} · ${place}` : s.roadName;
	};
	const roads = $derived(n ? [...n.segments].sort((a, b) => a.roadName.localeCompare(b.roadName) || (a.place ?? '').localeCompare(b.place ?? '')) : []);
	const mine = $derived(n && pick ? (n.segments.find((s) => s.segmentId === pick) ?? null) : null);
	const watch = $derived(n ? atRisk(n, 1).slice(0, 5) : []);

	function roadSentence(s: SegmentWater): string {
		if (s.elevated && s.risk === 0) return P('fld_pub_elevated');
		if (s.risk === 0) return P('fld_pub_road_0');
		const m = leadFor(s);
		const when = m === null ? t(lang, 'fld_pub_when_now') : t(lang, 'fld_pub_when_in', m);
		const sentence = P(`fld_pub_road_${s.risk}`, when);
		return sentence.charAt(0).toLocaleUpperCase(lang) + sentence.slice(1);
	}

	const headline = $derived.by(() => {
		if (!n) return '';
		if (mine) return roadSentence(mine);
		const k = n.flagged.length + n.counts[1];
		return k === 0 ? P('fld_pub_city_dry') : k === 1 ? P('fld_pub_city_one') : P('fld_pub_city_some', k);
	});
	const level = $derived(mine ? mine.risk : n ? (n.counts[3] ? 3 : n.counts[2] ? 2 : n.counts[1] ? 1 : 0) : 0);

	const tideLines = $derived.by(() => {
		if (!tideNow || tideNow.levelM === null) return [] as string[];
		const out = [P(tideNow.rising ? 'fld_pub_tide_rising' : 'fld_pub_tide_falling', num(tideNow.levelM))];
		out.push(P(tideNow.gateClosed ? 'fld_pub_gates_shut' : 'fld_pub_gates_open'));
		if (tideNow.nextHighAt !== null) out.push(P('fld_pub_next_high', clockAtMs(tideNow.nextHighAt, lang)));
		return out;
	});
	const rainLine = $derived.by(() => {
		if (!rainNow) return '';
		if (rainNow.nowMmH >= 0.5) return P('fld_pub_rain_now', num(rainNow.nowMmH));
		const w = rainWord(rainNow);
		return w === 'none' ? P('fld_pub_rain_none') : P(w === 'heavy' ? 'fld_pub_rain_heavy' : 'fld_pub_rain_light', num(rainNow.next2hMm));
	});
	/*
	 * What Listen reads: the same facts, written for the ear — the synthetic voice reads "3.6" and "03:22" badly in
	 * Marathi, so a decimal is said in words ("३ दशांश ६") and a clock as the time of day ("रात्री ३ वाजून २२ मिनिटांनी").
	 */
	const say = (v: number) => {
		const r = Math.round(v * 10) / 10;
		const whole = Math.trunc(r);
		const tenth = Math.round(Math.abs(r - whole) * 10);
		return tenth ? t(lang, 'fld_say_decimal', whole, tenth) : String(whole);
	};
	const spoken = $derived.by(() => {
		const parts = [headline];
		if (tideNow && tideNow.levelM !== null) {
			parts.push(P(tideNow.rising ? 'fld_pub_tide_rising' : 'fld_pub_tide_falling', say(tideNow.levelM)));
			parts.push(P(tideNow.gateClosed ? 'fld_pub_gates_shut' : 'fld_pub_gates_open'));
			if (tideNow.nextHighAt !== null) {
				const c = spokenClock(tideNow.nextHighAt);
				const at = c.minute ? t(lang, 'fld_say_clock', t(lang, `fld_say_${c.part}`), c.hour, c.minute) : t(lang, 'fld_say_clock_hour', t(lang, `fld_say_${c.part}`), c.hour);
				parts.push(P('fld_pub_next_high_say', c.tomorrow ? `${t(lang, 'fld_say_tomorrow')} ${at}` : at));
			}
		}
		if (rainNow) {
			const w = rainWord(rainNow);
			if (rainNow.nowMmH >= 0.5) parts.push(P('fld_pub_rain_now', say(rainNow.nowMmH)));
			else parts.push(w === 'none' ? P('fld_pub_rain_none') : P(w === 'heavy' ? 'fld_pub_rain_heavy' : 'fld_pub_rain_light', say(rainNow.next2hMm)));
		}
		return parts.filter(Boolean).join(' ');
	});

	/** The tide's next 12 hours as a sparkline (x: time, y: level), with the gate-closing level and "now". */
	const spark = $derived.by(() => {
		if (!tideNow || tideNow.series.length < 4) return null;
		const t0 = Date.now() - 15 * 60_000;
		const pts = tideNow.series.filter((p) => p.t >= t0 && p.t <= t0 + 12.25 * 3600_000);
		if (pts.length < 4) return null;
		const w = 260, h = 64, lo = Math.min(...pts.map((p) => p.m), tideNow.gateCloseM ?? 9) - 0.3, hi = Math.max(...pts.map((p) => p.m), tideNow.gateCloseM ?? 0) + 0.3;
		const x = (tt: number) => ((tt - pts[0].t) / (pts[pts.length - 1].t - pts[0].t)) * w;
		const y = (m: number) => h - ((m - lo) / (hi - lo)) * h;
		const line = pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)} ${y(p.m).toFixed(1)}`).join(' ');
		const area = `${line} L${w} ${h} L0 ${h} Z`;
		return { w, h, line, area, gate: tideNow.gateCloseM !== null ? y(tideNow.gateCloseM) : null, nowX: x(Date.now()), nowY: tideNow.levelM !== null ? y(tideNow.levelM) : null };
	});
</script>

<section class="water" aria-labelledby="wl-title" data-testid="water-card" data-status={status} data-level={level} lang={lang}>
	<header class="wh">
		<span class="wi"><Glyph name="wave" size={22} /></span>
		<div class="wt">
			<h2 id="wl-title">{t(lang, 'fld_pub_title')}</h2>
			<p class="lead">{P('fld_pub_lead')}</p>
		</div>
		<span class="tagbox" data-label="MODELLED"><PublicTag tone="dashed" glyph="graph" label={t(lang, 'fld_tag_modelled')} /></span>
	</header>

	{#if status === 'down'}
		<p class="quiet">{t(lang, 'fld_pub_down')}</p>
	{:else}
		<label class="pickl" for="wl-road">{t(lang, 'fld_pub_pick')}</label>
		<select id="wl-road" value={pick ? String(pick) : ''} onchange={(e) => choose(e.currentTarget.value)} disabled={!n} data-testid="water-road">
			<option value="">{t(lang, 'fld_pub_all')}</option>
			{#each roads as r (r.segmentId)}<option value={String(r.segmentId)}>{roadLabel(r)}</option>{/each}
		</select>

		<div class={['verdict', `l${level}`]} aria-live="polite">
			<span class="meter" aria-hidden="true">{#each [1, 2, 3] as i (i)}<i class={[level >= i && 'lit']}></i>{/each}</span>
			{#if status === 'loading'}
				<p class="big quiet">{t(lang, 'fld_pub_loading')}</p>
			{:else}
				<div class="vt">
					{#if mine || level > 0}<b class="cls">{t(lang, `fld_risk_${level}`)}</b>{/if}
					<p class="big" data-testid="water-headline">{headline}</p>
				</div>
			{/if}
		</div>
		{#if status === 'ready'}<ListenButton text={spoken} {lang} />{/if}

		{#if !mine && watch.length}
			<div class="watch">
				<h3>{t(lang, 'fld_pub_roads_at_risk')}</h3>
				<ul>
					{#each watch as w (w.segmentId)}
						<li><button type="button" onclick={() => choose(String(w.segmentId))}><span class={['dot', `l${w.risk}`]} aria-hidden="true"></span><span class="rn">{roadLabel(w)}</span><span class="rk">{t(lang, `fld_risk_${w.risk}`)}</span></button></li>
					{/each}
				</ul>
			</div>
		{/if}

		<div class="cols">
			<div class="mini" data-testid="water-tide">
				<h3><Glyph name="timeline" size={18} />{t(lang, 'fld_pub_tide_h')}</h3>
				{#if spark}
					<svg class="spark" viewBox={`0 0 ${spark.w} ${spark.h}`} aria-hidden="true" preserveAspectRatio="none">
						<path class="ar" d={spark.area} />
						<path class="ln" d={spark.line} />
						{#if spark.gate !== null}<line class="gate" x1="0" x2={spark.w} y1={spark.gate} y2={spark.gate} />{/if}
						{#if spark.nowY !== null}<circle class="now" cx={spark.nowX} cy={spark.nowY} r="4" />{/if}
					</svg>
					<p class="key"><span>{t(lang, 'fld_pub_now')}</span><span class="gk">{P('fld_pub_gate_line')}</span><span>{P('fld_pub_12h')}</span></p>
				{/if}
				{#each tideLines as line, i (i)}<p>{line}</p>{/each}
				{#if !tideLines.length}<p class="quiet">{t(lang, 'fld_pub_loading')}</p>{/if}
			</div>
			<div class="mini" data-testid="water-rain">
				<h3><Glyph name="wave" size={18} />{t(lang, 'fld_pub_rain_h')}</h3>
				<p>{rainLine || t(lang, 'fld_pub_loading')}</p>
			</div>
		</div>
	{/if}
	<p class="src">{P('fld_pub_src')}</p>
</section>

<style>
	.water {
		display: flex;
		flex-direction: column;
		gap: 14px;
		padding: 22px 20px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
		box-shadow: var(--v3-elev-1);
	}

	.wh {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 12px;
		align-items: start;
	}

	.wi {
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		border-radius: 50%;
		background: var(--v3-brand-veil);
		color: var(--v3-brand-text);
	}

	h2 {
		margin: 0;
		font-size: 22px;
		line-height: 30px;
		font-weight: 700;
	}

	.lead {
		margin: 2px 0 0;
		color: var(--v3-t2);
		font-size: 15px;
		line-height: 22px;
	}

	.tagbox {
		grid-column: 2;
	}

	.pickl {
		color: var(--v3-t2);
		font-size: 14px;
		font-weight: 650;
		margin-bottom: -8px;
	}

	select {
		width: 100%;
		height: 48px;
		padding: 0 14px;
		border: 1px solid var(--v3-line-3);
		border-radius: var(--v3-radius-m);
		background: var(--v3-bg);
		color: var(--v3-t1);
		font: inherit;
		font-size: 16px;
	}

	select:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.verdict {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 16px;
		border-radius: var(--v3-radius-l);
		background: var(--v3-bg);
	}

	.meter {
		display: flex;
		align-items: flex-end;
		gap: 4px;
		flex: none;
		height: 48px;
	}

	.meter i {
		display: block;
		width: 10px;
		border-radius: 3px;
		background: var(--v3-s3);
	}

	.meter i:nth-child(1) {
		height: 18px;
	}

	.meter i:nth-child(2) {
		height: 32px;
	}

	.meter i:nth-child(3) {
		height: 46px;
	}

	.meter i.lit {
		background: var(--v3-brand);
	}

	.l0 .meter i:nth-child(1) {
		background: var(--v3-ok);
	}

	.cls {
		display: block;
		color: var(--v3-brand-text);
		font-size: 16px;
		font-weight: 700;
	}

	.big {
		margin: 0;
		font-size: 20px;
		line-height: 28px;
		font-weight: 650;
	}

	.quiet {
		margin: 0;
		color: var(--v3-t2);
	}

	.watch h3,
	.mini h3 {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0 0 6px;
		font-size: 16px;
		font-weight: 700;
	}

	.watch ul {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.watch button {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		min-height: 44px;
		padding: 0 12px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-m);
		background: var(--v3-bg);
		color: var(--v3-t1);
		font: inherit;
		font-size: 15px;
		text-align: left;
		cursor: pointer;
	}

	.dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--v3-brand-veil);
	}

	.dot.l2,
	.dot.l3 {
		background: var(--v3-brand);
	}

	.rn {
		flex: 1;
		min-width: 0;
	}

	.rk {
		color: var(--v3-t2);
		font-size: 14px;
	}

	.cols {
		display: grid;
		grid-template-columns: 1.3fr 1fr;
		gap: 12px;
	}

	.mini {
		padding: 14px 16px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-bg);
	}

	.mini h3 :global(.v3-glyph) {
		color: var(--v3-brand-text);
	}

	.mini p {
		margin: 4px 0 0;
		font-size: 15px;
		line-height: 22px;
	}

	.spark {
		display: block;
		width: 100%;
		height: 56px;
		margin: 4px 0 8px;
	}

	.ar {
		fill: var(--v3-brand-veil);
	}

	.ln {
		fill: none;
		stroke: var(--v3-brand);
		stroke-width: 2;
		vector-effect: non-scaling-stroke;
	}

	.gate {
		stroke: var(--v3-t3);
		stroke-width: 1;
		stroke-dasharray: 4 4;
		vector-effect: non-scaling-stroke;
	}

	.now {
		fill: var(--v3-t1);
		stroke: var(--v3-s1);
		stroke-width: 2;
		vector-effect: non-scaling-stroke;
	}

	.key {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		margin: -4px 0 6px;
		color: var(--v3-t3);
		font-size: 12px;
		line-height: 16px;
	}

	.mini .key {
		margin: -4px 0 6px;
		font-size: 12px;
		line-height: 16px;
	}

	.gk {
		text-align: center;
	}

	.src {
		margin: 0;
		color: var(--v3-t3);
		font-size: 13px;
		line-height: 19px;
	}

	@media (max-width: 520px) {
		.cols {
			grid-template-columns: minmax(0, 1fr);
		}

		.water {
			padding: 18px 16px;
		}
	}
</style>
