<script lang="ts">
	/**
	 * CitizenAdvisory — "Your road, next 2 hours" (Daylight, trilingual).
	 *
	 * Fed ONLY by the public feed (public-feed.svelte.ts → the deck's
	 * server-side projection): public-kind events, signage road names, the
	 * hold length with its provenance, a road-graph alternate and a
	 * plain-language tier. No operator store, no band codes, no pursuit or
	 * crime events, no titles. One card per event with tabular localized
	 * windows; the hold's provenance as the oracle labels it (closure plan,
	 * live adaptation, or the standard baseline — never a baseline passed
	 * off as live); an honest "not published" when a hold length is unknown,
	 * "no signed alternate" when the graph offers none, and "unavailable
	 * right now" when the read failed. Only an active event holds "now";
	 * a planned one reads "next" only inside the 2 h horizon, and events
	 * further out sit in a dated Later list. Every clock is IST, prefixed
	 * with its day when that is not today. An event the emulator opened is
	 * badged SIMULATED FEED · EMULATED (never LIVE), its routes are drawn
	 * non-live and it never moves the strip. The labelled offline preview
	 * stands in only while the feed is unreachable. Subscribe flow (10-digit
	 * validation, honest demo note, preview in the chosen alert language —
	 * the page's language until the citizen picks another) and the
	 * emergency card → /driver. The waterlogging card (v3/public/WaterOnYourRoad:
	 * the hydro nowcast, tide and rain in plain words, MODELLED) sits above the
	 * cards, and every advisory has a Listen button (v3/public/ListenButton: the
	 * on-premises synthetic voice, in the page language).
	 */
	import { SUPPORTED, kindLabel, localizeNumber, t } from '$lib/i18n/strings';
	import { citizenT, consequenceLabel, phaseLabelText } from '$lib/i18n/strings.citizen';
	import { ensureLang } from '$lib/i18n/load';
	import { composeAdvisory, factsFromPublicEvent, holdSourceKey } from '$lib/comms/advisory';
	import { clockAtMs, holdAnchorMs, stretchHolds, type StripTier } from './holds';
	import { publicFeed } from './public-feed.svelte';
	import type { PublicCorridorEvent, PublicLaterEvent } from './public-model';
	import '$lib/v3/public/packs.pub3';
	import { artFor } from '$lib/v3/home/model';
	import Glyph from '$lib/v3/Glyph.svelte';
	import PublicTag from '$lib/v3/public/PublicTag.svelte';
	import HoldMap from '$lib/v3/public/HoldMap.svelte';
	import ListenButton from '$lib/v3/public/LazyListen.svelte';
	import WaterOnYourRoad from '$lib/v3/public/LazyWater.svelte';
	import LightCorridorMap from './LightCorridorMap.svelte';
	import VehicleShot from '$lib/v3/media/VehicleShot.svelte';
	import AgencyMark from '$lib/v3/media/AgencyMark.svelte';
	import '$lib/v3/media/packs.media';

	let { lang }: { lang: string } = $props();

	let phone = $state('');
	/** The citizen's own pick; until then alerts follow the page language. */
	let alertLangPicked = $state<string | null>(null);
	const alertLang = $derived(alertLangPicked ?? lang);
	// The alert language can differ from the page's (an EN page previewing a
	// Hindi alert): its strings load on choice (FIX-E-PERF2 round 2) — the
	// preview re-renders in the language once they land (t()'s EN fallback
	// holds for the moment in between; a raw key never shows).
	$effect(() => {
		void ensureLang(alertLang);
	});
	let subscribed = $state(false);
	let timelineOpen = $state(false);
	let explainerOpen = $state(false);

	const events = $derived<PublicCorridorEvent[]>(publicFeed.events);
	const later = $derived<PublicLaterEvent[]>(publicFeed.later);
	const preview = $derived(publicFeed.preview);
	const live = $derived(publicFeed.status === 'live' || publicFeed.status === 'stale');
	/** Live (requestable) corridor events: the driver page offers only these. */
	const liveCount = $derived(live ? events.filter((e) => e.source === 'live' && e.stretches.length > 0).length : 0);
	const tier = $derived<StripTier | null>(live ? publicFeed.tier : null);
	/** Emulated rows on the page (cards or Later): they get the explicit note. */
	const anyEmulated = $derived(events.some((e) => e.source === 'emulated') || later.some((e) => e.source === 'emulated'));
	/** The emulated HOLD rows listed below — the banner counts the same cards. */
	const emulatedHoldCount = $derived(
		events.filter((e) => e.source === 'emulated').reduce((n, e) => n + stretchHolds(e.stretches, e.hold.minutes, holdAnchorMs(e), lang, e.state === 'active').length, 0),
	);
	/** The hero never reads LIVE when every event it would vouch for is emulated. */
	const heroEmulated = $derived(live && events.length > 0 && events.every((e) => e.source === 'emulated'));

	/** When the advisory feed last answered (IST) — no claim about live traffic. */
	const updatedLabel = $derived(
		publicFeed.updatedAt && !preview ? `${t(lang, 'updated')} · ${clockAtMs(publicFeed.updatedAt, lang)}` : '',
	);

	function stripKey(tr: StripTier | null): string {
		if (tr === null) return publicFeed.status === 'connecting' ? 'citizen_feed_connecting' : 'citizen_feed_offline';
		return tr === 'calm' ? 'strip_calm' : tr === 'watch' ? 'strip_watch' : tr === 'hold' ? 'strip_hold' : 'strip_severe';
	}

	/** A stretch by its signage name, else its place on the route (F-24: never a raw segment id). */
	function stretchName(roadName: string | null, index: number): string {
		return roadName ?? citizenT(lang, 'driver_stretch_unnamed', localizeNumber(index + 1, lang));
	}

	function validPhone(p: string): boolean {
		return /^[0-9]{10}$/.test(p.replace(/\s+/g, ''));
	}

	function subscribe() {
		if (validPhone(phone)) subscribed = true;
	}

	/** The exact citizen draft the comms desk would write, in the alert language. */
	const previewText = $derived.by(() => {
		const ev = events[0];
		if (!ev) return citizenT(alertLang, 'citizen_preview_none');
		return composeAdvisory(factsFromPublicEvent(ev), 'citizens', alertLang).text;
	});
</script>

<div class="citizen" data-screen="citizen" data-feed={publicFeed.status}>
	<header class="hero">
		<div class="hero-row">
			<span class="brand">{t(lang, 'brand')}</span>
			{#if !live}
				<span class="source-badge" data-source-badge="fixture"><PublicTag tone="dashed" glyph="flask" label={t(lang, 'opsSourceOffline')} /></span>
			{:else if heroEmulated}
				<span class="source-badge" data-source-badge="emulated"><PublicTag tone="dashed" glyph="flask" label={citizenT(lang, 'citizen_emulated_badge')} /></span>
			{:else}
				<span class="source-badge" data-source-badge="live"><PublicTag tone="live" glyph="check" label={t(lang, 'opsSourceLive')} /></span>
			{/if}
		</div>
		<h1 class="kicker">{citizenT(lang, 'citizen_kicker')}</h1>
		{#if updatedLabel}
			<p class="updated fig" data-testid="citizen-updated">{updatedLabel}</p>
		{/if}
	</header>

	<!-- Plain-language strip: never the internal band code. The one sentence a citizen needs, in big type. -->
	<section class="strip tier-{tier ?? 'unknown'}" data-strip={tier ?? 'unknown'} aria-live="polite">
		<span class="strip-dot" aria-hidden="true"></span>
		<p>{citizenT(lang, stripKey(tier))}</p>
	</section>

	{#if publicFeed.status === 'stale'}
		<p class="feed-note" data-feed-note="stale"><Glyph name="info" size={18} /><span class="note-text">{citizenT(lang, 'citizen_feed_stale')}</span></p>
	{:else if preview}
		<p class="feed-note" data-feed-note="preview">
			<PublicTag tone="dashed" glyph="flask" label={t(lang, 'opsSourceOffline')} />
			<span class="note-text">{citizenT(lang, 'citizen_feed_offline')}</span>
		</p>
	{/if}
	{#if anyEmulated && !preview}
		<!-- calm on the surface: the honest label as one quiet line; what it means one tap down (never hidden: the cards
		     below carry the same label) -->
		<details class="feed-note" data-feed-note="emulated">
			<summary><Glyph name="flask" size={16} /><span class="note-label">{citizenT(lang, 'citizen_emulated_badge')}</span><Glyph name="chevD" size={14} /></summary>
			<span class="note-text">
				{citizenT(lang, 'citizen_emulated_note')}
				<!-- the banner counts the very holds listed below (same derivation) -->
				{#if emulatedHoldCount > 0}{emulatedHoldCount === 1 ? t(lang, 'asst_citizen_hold_one') : t(lang, 'asst_citizen_hold_many', emulatedHoldCount)}{/if}
			</span>
		</details>
	{/if}

	<!-- Waterlogging on your road (the hydro nowcast in plain words, MODELLED) with its Listen button. -->
	<WaterOnYourRoad {lang} />

	{#if events.length === 0}
		<div class="empty" data-testid="citizen-empty" data-prim="empty-state">
			<img class="empty-scene" src="/artwork/scenes/day.svg" alt={t(lang, 'v3i_scene_day')} width="960" height="320" decoding="async" />
			<p class="empty-t">{publicFeed.status === 'connecting' ? citizenT(lang, 'citizen_feed_connecting') : citizenT(lang, 'citizen_none_now')}</p>
			<p class="empty-h">{t(lang, 'statusClearSub')}</p>
		</div>
	{:else}
		<!-- One card per public corridor event. -->
		{#each events as ev (ev.eventId)}
			{@const holds = stretchHolds(ev.stretches, ev.hold.minutes, holdAnchorMs(ev), lang, ev.state === 'active')}
			{@const demo = ev.source === 'offline-fixture'}
			{@const emulated = ev.source === 'emulated'}
			{@const unverified = ev.source === 'unverified'}
			<article class="event-card" class:emulated={emulated || unverified} data-event={ev.eventId} data-kind={ev.eventKind} data-source={ev.source}>
				{#if holds.length}
					<!-- the day-graded map of the stretch: solid for a live event, dashed for anything that is not -->
					<HoldMap ids={ev.stretches.map((s) => s.segmentId)} live={ev.source === 'live'} alt={t(lang, 'v3p_hold_map_alt')} />
				{/if}
				<div class="card-body">
					<header class="card-head">
						<div class="ttl">
							<img class="art" src={artFor(ev.eventKind)} alt="" width="44" height="44" />
							<h2>{kindLabel(lang, ev.eventKind)}</h2>
						</div>
						{#if emulated}
							<span class="source-badge" data-source-badge="emulated"><PublicTag tone="dashed" glyph="flask" label={citizenT(lang, 'citizen_emulated_badge')} /></span>
						{:else if unverified}
							<!-- F-CONN-03: the position source could not be read — never vouched for as live -->
							<span class="source-badge" data-source-badge="unverified"><PublicTag tone="dashed" glyph="unverified" label={citizenT(lang, 'citizen_unverified_badge')} /></span>
						{:else}
							<span class="source-badge" data-source-badge={demo ? 'fixture' : 'live'}>
								<PublicTag tone={demo ? 'dashed' : 'live'} glyph={demo ? 'flask' : 'check'} label={demo ? t(lang, 'opsSourceOffline') : t(lang, 'opsSourceLive')} />
							</span>
						{/if}
					</header>
					<p class="consequence">{consequenceLabel(lang, ev.eventKind, ev.state !== 'active')}</p>
					<!-- ऐका / Listen: the citizen advisory the comms desk would write, read aloud in the page language -->
					<div class="listen-row"><ListenButton compact text={composeAdvisory(factsFromPublicEvent(ev), 'citizens', lang).text} {lang} /></div>
					{#if holds.length}
						<ul class="holds">
							{#each holds as h (h.segmentId)}
								<li class="hold" data-hold-state={h.state}>
									<span class="seg">{stretchName(h.roadName, ev.stretches.findIndex((s) => s.segmentId === h.segmentId))}</span>
									<!-- an emulated hold is a demonstration: never 'Holding now' on a real road -->
									<span class="state">
										{h.state === 'now'
											? citizenT(lang, emulated ? 'card_sim_now' : unverified ? 'card_unv_now' : 'card_now')
											: h.state === 'next'
												? citizenT(lang, emulated ? 'card_sim_soon' : unverified ? 'card_unv_soon' : 'card_soon')
												: '→'}
									</span>
									<span class="window fig">
										{t(lang, 'freezeMinutes', localizeNumber(h.minutes, lang))}
										· {citizenT(lang, 'card_window_at', h.clock)}
									</span>
								</li>
							{/each}
						</ul>
						<p class="provenance" data-hold-source={ev.hold.source}>
							{citizenT(lang, holdSourceKey(ev.hold.source))}
						</p>
					{:else if ev.unavailable.hold}
						<p class="hold-unknown" data-hold-state="unavailable">{citizenT(lang, 'card_hold_unavailable')}</p>
					{:else}
						<p class="hold-unknown" data-hold-state="unpublished">{citizenT(lang, 'card_hold_unknown')}</p>
					{/if}
					{#if ev.alternate}
						<p class="alternate" data-alternate="graph">
							<Glyph name="route" size={18} />
							<span>
								{t(lang, 'alternate')}: <span class="alt">{ev.alternate.roadNames.join(' / ')}</span>
								<span class="provenance">· {citizenT(lang, 'card_alt_from_graph')}</span>
							</span>
						</p>
					{:else if ev.unavailable.alternate}
						<p class="alternate" data-alternate="unavailable">{citizenT(lang, 'card_alt_unavailable')}</p>
					{:else}
						<p class="alternate" data-alternate="none">{citizenT(lang, 'card_alt_none')}</p>
					{/if}
				</div>
			</article>
		{/each}

		<!-- Today's timeline accordion. -->
		<section class="accordion">
			<button class="acc-head" aria-expanded={timelineOpen} onclick={() => (timelineOpen = !timelineOpen)}>
				<span>{citizenT(lang, 'timeline_title')}</span>
				<span class="chev" aria-hidden="true"><Glyph name={timelineOpen ? 'up' : 'down'} size={20} /></span>
			</button>
			{#if timelineOpen}
				<ul class="timeline">
					{#each events as ev (ev.eventId)}
						{#each ev.phases as ph, i (ev.eventId + ':' + i)}
							{@const ended = ph.endTime != null && Date.parse(ph.endTime) < Date.now()}
							<li class="tl-row" data-phase={ended ? 'completed' : 'planned'}>
								<span class="tl-state">
									{ended ? citizenT(lang, 'timeline_lifted') : citizenT(lang, 'timeline_planned')}
								</span>
								<span class="tl-label" data-phase-label={ph.label}>{kindLabel(lang, ev.eventKind)} · {phaseLabelText(lang, ph.label, i + 1)}</span>
								{#if ph.startTime}
									<span class="tl-clock fig" data-ts={ph.startTime}>{clockAtMs(Date.parse(ph.startTime), lang)}</span>
								{/if}
							</li>
						{/each}
					{/each}
					{#if events.every((e) => e.phases.length === 0)}
						<li class="tl-row"><span class="tl-state">{citizenT(lang, 'timeline_empty')}</span></li>
					{/if}
				</ul>
			{/if}
		</section>
	{/if}

	{#if later.length}
		<!-- Beyond the 2 h horizon: dated heads-up rows only (no hold plan yet). -->
		<section class="later" data-testid="citizen-later">
			<h3>{citizenT(lang, 'citizen_later_title')}</h3>
			<ul>
				{#each later as ev (ev.eventId)}
					<li class="later-row" data-event={ev.eventId} data-kind={ev.eventKind} data-source={ev.source} data-starts={ev.startsAt ?? ''}>
						<span class="later-when fig">
							{ev.startsAt != null ? clockAtMs(ev.startsAt, lang) : citizenT(lang, 'citizen_later_unscheduled')}
						</span>
						<span class="later-what">
							<strong>{kindLabel(lang, ev.eventKind)}</strong>
							{#if ev.roadsWithheld}
								<span class="later-roads" data-roads-withheld="true"> · {citizenT(lang, 'citizen_later_roads_withheld')}</span>
							{:else if ev.roadNames.length}
								<span class="later-roads"> · {ev.roadNames.join(' / ')}</span>
							{/if}
						</span>
						{#if ev.source === 'emulated'}
							<span class="source-badge" data-source-badge="emulated"><PublicTag tone="dashed" glyph="flask" label={citizenT(lang, 'citizen_emulated_badge')} /></span>
						{/if}
					</li>
				{/each}
			</ul>
			<p class="provenance">{citizenT(lang, 'citizen_later_note')}</p>
		</section>
	{/if}

	<!-- Light corridor map (always mounted: an empty city is information too). -->
	<section class="map-card" aria-label={t(lang, 'v3p_map_title')}>
		<LightCorridorMap
			{lang}
			compact
			routes={events.flatMap((ev) => ev.stretches.map((s) => ({ segmentId: s.segmentId, live: ev.source === 'live' })))}
		/>
	</section>

	<!-- Why roads hold (explainer accordion). -->
	<section class="accordion">
		<button class="acc-head" aria-expanded={explainerOpen} onclick={() => (explainerOpen = !explainerOpen)}>
			<span>{citizenT(lang, 'citizen_explainer_link')}</span>
			<span class="chev" aria-hidden="true"><Glyph name={explainerOpen ? 'up' : 'down'} size={20} /></span>
		</button>
		{#if explainerOpen}
			<div class="explainer">
				<h3>{t(lang, 'why')}</h3>
				<p>{t(lang, 'whyBody')}</p>
			</div>
		{/if}
	</section>

	<!-- Subscribe (10-digit validation, honest demo note). -->
	<section class="subscribe">
		<h3>{t(lang, 'subscribeTitle')}</h3>
		<p>{t(lang, 'subscribeSub')}</p>
		<form onsubmit={(e) => { e.preventDefault(); subscribe(); }}>
			<input
				type="tel"
				inputmode="numeric"
				maxlength="10"
				placeholder={t(lang, 'phonePlaceholder')}
				aria-label={t(lang, 'phoneLabel')}
				bind:value={phone}
				data-testid="subscribe-phone"
			/>
			<select
				value={alertLang}
				onchange={(e) => (alertLangPicked = e.currentTarget.value)}
				aria-label={t(lang, 'languageLabel')}
				data-testid="subscribe-lang"
			>
				{#each SUPPORTED as s (s.code)}
					<option value={s.code}>{s.label}</option>
				{/each}
			</select>
			<button type="submit" class="pbtn" disabled={!validPhone(phone)}>
				{t(lang, 'subscribeBtn')}
			</button>
		</form>
		{#if subscribed}
			<p class="subscribed">{t(lang, 'subscribed')}</p>
			<div class="preview" data-testid="subscribe-preview" lang={alertLang}>
				<PublicTag tone="dashed" glyph="flask" label={t(lang, 'demoBadge')} />
				<strong>{t(lang, 'previewTitle')}</strong>
				<p>{previewText}</p>
			</div>
		{/if}
		<p class="demo-note">{citizenT(lang, 'subscribe_demo_note')}</p>
	</section>

	<!-- Emergency → /driver. -->
	<section class="emergency">
		<span class="em-pic">
			<VehicleShot cls="ambulance" {lang} width={150} />
			<span class="em-mark"><AgencyMark role="108" {lang} size={22} /></span>
		</span>
		<div class="em-body">
			<h3>{t(lang, 'emergencyTitle')}</h3>
			<!-- F-09: a request needs a live corridor event; with none, say so (never "the active event") -->
			<p data-testid="emergency-body" data-live-events={liveCount}>{t(lang, liveCount > 0 ? 'emergencyBody' : 'emergencyBodyNone')}</p>
			<a class="cta" href="/driver" data-testid="driver-link">{t(lang, 'emergencyCta')} →</a>
		</div>
	</section>

	<footer>
		{#if preview}
			<p class="demo-note">{t(lang, 'demoNote')}</p>
		{/if}
		<p class="privacy">{citizenT(lang, 'footer_privacy')}</p>
		<p>{t(lang, 'footerNote')}</p>
	</footer>
</div>

<style>
	.citizen {
		box-sizing: border-box;
		display: flex;
		flex-direction: column;
		gap: 16px;
		width: 100%;
		max-width: 592px;
		margin: 0 auto;
		padding: 20px 16px 40px;
		color: var(--v3-t1);
		font-size: 17px;
		line-height: 26px;
	}

	.fig {
		font-variant-numeric: tabular-nums;
	}

	/* ── the hero: the page's one question ─────────────────────────────── */
	.hero {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 4px 4px 0;
	}

	/* the source badge drops under the brand on a phone — it never squeezes the brand into three lines */
	.hero-row {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 6px 10px;
	}

	.brand {
		flex: 1 1 12rem;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 600;
		line-height: var(--v3-lh-meta);
	}

	.kicker {
		margin: 0;
		font-size: 32px;
		font-weight: 680;
		line-height: 40px;
	}

	.updated {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.source-badge {
		display: inline-flex;
		max-width: 100%;
	}

	/* ── the posture sentence: calm is green; every other posture is the brand blue (red and orange keep their meanings) ── */
	.strip {
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 18px 20px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
		box-shadow: var(--v3-elev-1);
	}

	.strip p {
		margin: 0;
		font-size: 22px;
		font-weight: 640;
		line-height: 30px;
	}

	.strip-dot {
		flex: none;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: var(--v3-t3);
	}

	.strip.tier-calm .strip-dot {
		background: var(--v3-ok);
		box-shadow: 0 0 0 5px var(--v3-ok-veil);
	}

	.strip.tier-watch .strip-dot,
	.strip.tier-hold .strip-dot,
	.strip.tier-severe .strip-dot {
		background: var(--v3-brand-strong);
		box-shadow: 0 0 0 5px var(--v3-brand-veil);
	}

	.strip.tier-unknown {
		border-style: dashed;
		box-shadow: none;
	}

	/* ── notes ─────────────────────────────────────────────────────────── */
	.feed-note {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 10px;
		margin: 0;
		padding: 12px 14px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s2);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 20px;
	}

	.note-text {
		flex: 1 1 14rem;
		min-width: 0;
	}

	/* the emulated feed: one quiet dashed line (the honest label); what it means one tap down */
	details.feed-note {
		display: block;
		padding: 10px 14px;
		border-style: dashed;
		border-color: var(--v3-dashed);
		background: transparent;
	}

	details.feed-note summary {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 28px;
		color: var(--v3-t2);
		font-weight: 600;
		list-style: none;
		cursor: pointer;
	}

	details.feed-note summary::-webkit-details-marker {
		display: none;
	}

	details.feed-note summary :global(.v3-glyph:last-child) {
		margin-left: auto;
		transition: transform var(--v3-dur-2) var(--v3-ease);
	}

	details.feed-note[open] summary :global(.v3-glyph:last-child) {
		transform: rotate(180deg);
	}

	details.feed-note summary:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
		border-radius: 6px;
	}

	details.feed-note .note-text {
		display: block;
		margin-top: 6px;
	}

	@media (prefers-reduced-motion: reduce) {
		details.feed-note summary :global(.v3-glyph:last-child) {
			transition: none;
		}
	}

	/* ── event cards ───────────────────────────────────────────────────── */
	.event-card,
	.subscribe,
	.emergency,
	.later,
	.accordion {
		overflow: hidden;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
		box-shadow: var(--v3-elev-1);
	}

	/* an emulated or unverified card is outlined, never solid: it is not a live road hold */
	.event-card.emulated {
		border-style: dashed;
		border-color: var(--v3-dashed);
	}

	.card-body {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 18px 20px 20px;
	}

	.card-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 8px 12px;
	}

	.ttl {
		display: flex;
		align-items: center;
		gap: 12px;
		min-width: 0;
	}

	.art {
		flex: none;
		width: 44px;
		height: 44px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s3);
	}

	.card-head h2 {
		margin: 0;
		font-size: 22px;
		font-weight: 660;
		line-height: 28px;
	}

	.listen-row {
		margin: -2px 0 2px;
	}

	.consequence {
		margin: 0;
		color: var(--v3-t2);
	}

	/* a hold: the road, how it stands, then its window — wrapping, never overlapping */
	.holds {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.hold {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: start;
		gap: 2px 12px;
		padding: 12px 14px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.seg {
		min-width: 0;
		font-weight: 650;
		overflow-wrap: anywhere;
	}

	.state {
		justify-self: end;
		max-width: 100%;
		padding: 0 10px;
		border-radius: 13px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 650;
		line-height: 26px;
		text-align: right;
	}

	/* holding now: the one filled state (white on the brand blue, 5.3:1) */
	.hold[data-hold-state='now'] .state {
		background: var(--v3-brand-strong);
		color: var(--v3-on-brand);
	}

	.hold[data-hold-state='next'] .state {
		box-shadow: inset 0 0 0 1.5px var(--v3-brand-strong);
		color: var(--v3-brand-text);
	}

	.window {
		grid-column: 1 / -1;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 20px;
	}

	.alternate {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		margin: 0;
		font-size: 16px;
		line-height: 24px;
	}

	.alternate :global(.v3-glyph) {
		flex: none;
		margin-top: 3px;
		color: var(--v3-route-text);
	}

	.alt {
		font-weight: 650;
	}

	.provenance {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 20px;
	}

	.hold-unknown {
		margin: 0;
		padding: 12px 14px;
		border: 1px dashed var(--v3-line-3);
		border-radius: var(--v3-radius-m);
		color: var(--v3-t2);
	}

	/* ── accordions ────────────────────────────────────────────────────── */
	.acc-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		width: 100%;
		min-height: 56px;
		padding: 0 20px;
		border: 0;
		background: transparent;
		color: var(--v3-t1);
		font: inherit;
		font-size: 17px;
		font-weight: 640;
		text-align: left;
		cursor: pointer;
	}

	.chev {
		display: grid;
		flex: none;
		place-items: center;
		color: var(--v3-t2);
	}

	.timeline {
		display: flex;
		flex-direction: column;
		margin: 0;
		padding: 0 20px 8px;
		list-style: none;
	}

	.tl-row {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: baseline;
		gap: 4px 12px;
		padding: 12px 0;
		border-top: 1px solid var(--v3-line-1);
		font-size: 16px;
		line-height: 24px;
	}

	.tl-state {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 600;
	}

	.tl-label {
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.tl-clock {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.explainer {
		padding: 0 20px 18px;
	}

	.explainer h3 {
		margin: 0 0 6px;
		font-size: 17px;
	}

	.explainer p {
		margin: 0;
		color: var(--v3-t2);
		font-size: 16px;
		line-height: 24px;
	}

	/* ── later ─────────────────────────────────────────────────────────── */
	.later {
		padding: 18px 20px 16px;
	}

	.later h3,
	.subscribe h3,
	.emergency h3 {
		margin: 0 0 6px;
		font-size: 19px;
		font-weight: 650;
		line-height: 26px;
	}

	.later ul {
		display: flex;
		flex-direction: column;
		margin: 0 0 8px;
		padding: 0;
		list-style: none;
	}

	.later-row {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 12px;
		padding: 10px 0;
		border-top: 1px solid var(--v3-line-1);
	}

	.later-when {
		min-width: 7.5rem;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 600;
	}

	.later-what {
		flex: 1 1 12rem;
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.later-roads {
		color: var(--v3-t2);
	}

	.map-card {
		overflow: hidden;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-xl);
		box-shadow: var(--v3-elev-1);
	}

	/* the corridor map inside it draws its own frame: no second border */
	.map-card :global(.light-map) {
		border: 0;
		border-radius: 0;
	}

	/* ── subscribe ─────────────────────────────────────────────────────── */
	.subscribe,
	.emergency {
		padding: 20px;
	}

	.subscribe p,
	.emergency p {
		margin: 0 0 12px;
		color: var(--v3-t2);
		font-size: 16px;
		line-height: 24px;
	}

	form {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
	}

	form input,
	form select {
		box-sizing: border-box;
		min-width: 0;
		height: 52px;
		padding: 0 14px;
		border: 1px solid var(--v3-line-3);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		font-size: 17px;
	}

	form input {
		flex: 1 1 11rem;
	}

	form select {
		flex: 0 1 9rem;
	}

	form input:focus-visible,
	form select:focus-visible,
	.acc-head:focus-visible,
	.cta:focus-visible,
	.pbtn:focus-visible {
		outline: 2px solid var(--v3-brand-strong);
		outline-offset: 2px;
	}

	.pbtn {
		min-height: 52px;
		padding: 0 22px;
		border: 1px solid var(--v3-line-3);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		font-size: 17px;
		font-weight: 650;
		cursor: pointer;
	}

	.pbtn:hover:not(:disabled) {
		background: var(--v3-s2);
	}

	.pbtn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.subscribed {
		margin: 12px 0 0 !important;
		color: var(--v3-ok-text) !important;
		font-weight: 650;
	}

	.preview {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 6px;
		margin-top: 10px;
		padding: 14px;
		border: 1px dashed var(--v3-line-3);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.preview p {
		margin: 0;
		color: var(--v3-t1);
	}

	.demo-note {
		margin: 12px 0 0 !important;
		color: var(--v3-t2) !important;
		font-size: var(--v3-text-meta) !important;
		line-height: 20px !important;
	}

	/* ── the emergency card → /driver ──────────────────────────────────── */
	.emergency {
		display: flex;
		align-items: flex-start;
		gap: 16px;
	}

	.em-pic {
		position: relative;
		flex: none;
		width: 150px;
	}

	.em-pic :global(.shot) {
		width: 150px;
		height: auto;
	}

	.em-mark {
		position: absolute;
		left: 0;
		bottom: 0;
	}

	.em-body {
		min-width: 0;
	}

	.cta {
		display: inline-flex;
		align-items: center;
		min-height: 52px;
		padding: 0 22px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-brand-strong);
		color: var(--v3-on-brand);
		font-size: 17px;
		font-weight: 650;
		text-decoration: none;
	}

	.cta:hover {
		background: var(--v3-brand-text);
	}

	/* ── empty and footer ──────────────────────────────────────────────── */
	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		padding: 24px 16px 8px;
		text-align: center;
	}

	.empty-scene {
		display: block;
		width: 100%;
		height: 170px;
		margin-bottom: 8px;
		object-fit: cover;
		border-radius: var(--v3-radius-l);
	}

	.empty-t {
		margin: 0;
		font-size: 19px;
		font-weight: 650;
		line-height: 26px;
	}

	.empty-h {
		margin: 0;
		color: var(--v3-t2);
		font-size: 16px;
		line-height: 24px;
	}

	footer {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 20px;
		text-align: center;
	}

	footer p {
		margin: 4px 0;
	}

	@media (max-width: 420px) {
		.kicker {
			font-size: 28px;
			line-height: 36px;
		}

		.strip p {
			font-size: 20px;
			line-height: 28px;
		}

		.emergency {
			flex-direction: column;
		}
	}
</style>
