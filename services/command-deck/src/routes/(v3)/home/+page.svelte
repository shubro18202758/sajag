<script lang="ts">
	/**
	 * `/` — V3 Home (V3-SPEC §6.1; since the P5 root flip it is served at `/`, `/home` keeps answering, and the
	 * v2 workspace it used to share the root with is `/analyst`). It answers "what needs me, what is
	 * happening, what is coming" in three seconds:
	 *
	 *   hero     FeatureHero — the decision unit with the soonest deadline (pickFeatured: deadline first,
	 *            15 s hysteresis), over the real map of its place; CityPulse beside it
	 *   rails    Needs your decision (every unit, soonest first) · Live operations · Reported in the city
	 *            (about places, never people) · Coming up (next 72 hours)
	 *   footer   the rules in words; Policies; the OSM credit
	 *
	 * Composed ONLY from the deck's existing stores and selectors — no new endpoint: decisionUnits()
	 * (decisions/units.ts) for the units and deadlines, selectors.decisionUnits() / cardFigures() for every
	 * count (SPEC v2 §7.4 — the hook below exposes both so the smoke can hold the page to them), the ops
	 * store (board events, escorts, dispatches, band, traffic feed, the officer), the city registry (OSINT
	 * reports, convoys, sightings, cameras) and ops.segmentLines (the road geometry the store already
	 * loads). Every mark goes through ops.plate (masked until a duty officer is named); every card links
	 * to the one home of what it shows (decisions: the /ops Decisions column until /decide lands).
	 *
	 * Operator gate on and nobody signed in: one sign-in card, no pollers fire.
	 */
	import { onDestroy, onMount, untrack } from 'svelte';
	import { afterNavigate, goto } from '$app/navigation';
	import type { Component } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { cityName } from '$lib/city';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import OperatorSignIn from '$lib/shell/OperatorSignIn.svelte';
	import PoliciesPanel from '$lib/shell/PoliciesPanel.svelte';
	import Popover from '$lib/ui/Popover.svelte';
	import { registerProviders } from '$lib/workspace/providers';
	import { registrySize } from '$lib/workspace/registry';
	import { liveWorld, selectors } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { cardFigures } from '$lib/workspace/components/vitals/figures';
	import { decisionUnits, type Unit } from '$lib/decisions/units';
	import { tOps } from '$lib/i18n/strings.ops';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.wall';
	import { provideUiLang } from '$lib/ui';
	import { fmtDuration, fmtTime } from '$lib/ui/format/format';
	import '$lib/v3/packs.v3';
	import Glyph from '$lib/v3/Glyph.svelte';
	import { v3Bar } from '$lib/v3/shell/v3-bar.svelte';
	import { V3_NAV } from '$lib/v3/shell/nav';
	/** "Plan a movement" on the Coming-up rail opens the planner (Plan), not the analyst workspace. */
	const V3_PLAN = V3_NAV.find((n) => n.id === 'plan') ?? { href: '/plan' };
	import { earlyHandOverTag, workspaceHandOver } from '$lib/shell/root-flip';
	import FeatureHero from '$lib/v3/home/FeatureHero.svelte';
	import CityPulse from '$lib/v3/home/CityPulse.svelte';
	import Rail from '$lib/v3/home/Rail.svelte';
	import DecisionCard from '$lib/v3/home/DecisionCard.svelte';
	import OperationCard from '$lib/v3/home/OperationCard.svelte';
	import ReportCard from '$lib/v3/home/ReportCard.svelte';
	import PlannedCard from '$lib/v3/home/PlannedCard.svelte';
	import { bandSentenceKey, countdownText, greetingKey, liveOpsOf, pickFeatured, plannedOf, railOrder, reportTally, unitKey } from '$lib/v3/home/model';
	import { decisionVM, opVM, plannedVM, reportVM, roadLines, type PulseStat } from '$lib/v3/home/view';
	import { sceneFor, sceneSrc } from '$lib/v3/media/art';
	import '$lib/v3/media/packs.media';

	provideUiLang(() => ops.lang);
	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	/** The operator gate's state is known (or the read gave up). */
	let sessionWaitOver = $state(false);

	// ── clocks: 1 s for countdowns, 15 s for everything else that ages ─────
	let now = $state(Date.now());
	let slow = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => {
			now = Date.now();
			if (now - slow >= 15_000) slow = now;
		}, 1000);
		return () => clearInterval(id);
	});

	// ── the decisions (canonical: decisionUnits(), the units every surface counts) ──
	const units = $derived.by((): Unit[] => {
		void cityRegistry.version;
		return decisionUnits(ops);
	});
	let featuredKey = $state<string | null>(null);
	const featured = $derived(pickFeatured(units, featuredKey, now));
	$effect(() => {
		const k = featured ? unitKey(featured) : null;
		if (k !== untrack(() => featuredKey)) featuredKey = k;
	});
	const ordered = $derived(railOrder(units, featured));

	const roads = $derived(roadLines());
	const decisionVMs = $derived(ordered.map((u) => decisionVM(u, lang, slow)));
	const heroVM = $derived(featured ? (decisionVMs.find((v) => v.key === unitKey(featured)) ?? null) : null);

	// ── live operations, reports, coming up ────────────────────────────────
	const liveEvents = $derived(liveOpsOf(ops.events));
	const opVMs = $derived(liveEvents.map((ev) => opVM(ev, lang, slow, units)));
	const reports = $derived.by(() => {
		void cityRegistry.version;
		const dssSubjects = new Set(units.filter((u) => u.kind === 'dss').map((u) => u.subjectUrn));
		return [...cityRegistry.byKind('osint_event')].sort(
			(a, b) => Number(dssSubjects.has(b.urn)) - Number(dssSubjects.has(a.urn)) || (b.t ?? 0) - (a.t ?? 0),
		);
	});
	const reportVMs = $derived(reports.map((e) => reportVM(e, lang, slow, units)));
	const planned = $derived(plannedOf(ops.events, slow));
	const plannedVMs = $derived(planned.map((ev) => plannedVM(ev, lang, slow)));

	// ── the pulse: every count a canonical selector's ──────────────────────
	const figures = $derived.by(() => {
		void cityRegistry.version;
		return cardFigures({
			selectors,
			registry: liveWorld.registry(),
			unitSources: registrySize().units,
			escortProposals: ops.escortProposals.length,
			corridorSimulated: ops.trafficFeed?.label === 'simulated' || ops.trafficFeed?.label === 'mixed',
		});
	});
	const tally = $derived(reportTally(reports));
	const band = $derived.by(() => {
		const city = ops.cityBand;
		return city ? (city.stale ? null : city.band) : ops.bandSourceKind === 'city-band' ? ops.band : null;
	});
	const pulseMeta = $derived.by(() => {
		const city = ops.cityBand;
		if (city?.stale) return L('v3_band_stale');
		const since = city?.since ?? ops.bandCommittedAt ?? null;
		const read = city?.evaluatedAt ?? (ops.cityBandUpdated || null);
		return [
			band && since ? L('v3_band_since', L(`v3_band_${band.toLowerCase()}`), fmtTime(since)) : null,
			read ? L('v3_updated', fmtTime(read, { seconds: true })) : null,
		]
			.filter(Boolean)
			.join(' · ');
	});
	const soonest = $derived(units.find((u) => u.deadline != null && u.deadline > now) ?? null);
	const oldestWaiting = $derived.by(() => {
		const since = decisionVMs.map((v) => v.since).filter((s): s is number => s != null);
		return since.length ? Math.min(...since) : null;
	});
	const stats = $derived<PulseStat[]>([
		{
			id: 'decisions',
			n: units.length,
			label: L('v3_stat_decisions', units.length),
			sub: soonest?.deadline
				? L('v3_stat_soonest', countdownText(soonest.deadline - now, lang))
				: oldestWaiting != null
					? L('v3_stat_oldest', fmtDuration((now - oldestWaiting) / 1000, lang))
					: L('v3_stat_none_waiting'),
			href: '/decide',
			decide: true,
		},
		{
			id: 'live',
			n: liveEvents.length,
			label: L('v3_stat_live', liveEvents.length),
			sub: liveEvents.length
				? [
						liveEvents.filter((e) => e.eventKind === 'protected_movement').length
							? L('v3_stat_live_movements', liveEvents.filter((e) => e.eventKind === 'protected_movement').length)
							: null,
						liveEvents.filter((e) => e.eventKind === 'vehicle_pursuit').length
							? L('v3_stat_live_pursuits', liveEvents.filter((e) => e.eventKind === 'vehicle_pursuit').length)
							: null,
					]
						.filter(Boolean)
						.join(' · ')
				: L('v3_stat_live_none'),
			href: '#v3-live',
		},
		{
			id: 'reported',
			n: figures.reported,
			label: L('v3_stat_reported', figures.reported),
			sub: figures.reported
				? [
						tally.official ? L('v3_stat_rep_official', tally.official) : null,
						tally.news ? L('v3_stat_rep_news', tally.news) : null,
						tally.unverified ? L('v3_stat_rep_unverified', tally.unverified) : null,
					]
						.filter(Boolean)
						.join(' · ')
				: L('v3_stat_rep_none'),
			href: '#v3-reported',
		},
		{
			id: 'watchlisted',
			n: figures.watchlisted,
			label: L('v3_stat_watch', figures.watchlisted),
			sub: ops.officerOn ? L('v3_stat_watch_named', ops.dutyOfficer.trim()) : L('v3_stat_watch_masked'),
			href: '/ops',
		},
	]);
	const systems = $derived.by(() => {
		const out: { text: string; ok: boolean }[] = [];
		const c = figures.cameras;
		out.push(c.total ? { text: L('v3_sys_cameras', c.answering, c.total), ok: c.answering === c.total } : { text: L('v3_sys_cameras_none'), ok: false });
		const f = ops.trafficFeed;
		if (f?.label === 'simulated') out.push({ text: L('v3_sys_sim', f.segments), ok: false });
		else if (f?.label === 'mixed') out.push({ text: L('v3_sys_mixed', Math.round((100 * f.synthetic) / Math.max(1, f.real + f.synthetic))), ok: false });
		else if (f?.label === 'live') out.push({ text: L('v3_sys_live'), ok: true });
		return out;
	});
	const down = $derived.by(() => {
		const lost: string[] = [];
		if (cityRegistry.status === 'down')
			lost.push(cityRegistry.updatedAt ? L('v3_sys_down', L('v3_feed_city'), fmtTime(cityRegistry.updatedAt)) : L('v3_sys_down_now', L('v3_feed_city')));
		if (ops.boardStatus === 'offline' && ops.boardUpdated > 0) lost.push(L('v3_sys_down', L('v3_feed_events'), fmtTime(ops.boardUpdated)));
		return lost.length ? `${lost.join(' · ')} · ${L('v3_sys_still')}` : null;
	});

	function retry() {
		void cityRegistry.refresh();
		void ops.pollBoard(true);
	}

	// ── first run: the dismissible onboarding strip (never a modal) ───────
	const ONBOARD_KEY = 'sajag.v3.onboarded';
	let onboard = $state(false);
	function dismissOnboard() {
		onboard = false;
		try {
			localStorage.setItem(ONBOARD_KEY, '1');
		} catch {
			// storage unavailable: dismissed for this visit
		}
	}

	// ── the Omnibar: the page's one (plan R30), loaded after first paint ──
	let Omnibar = $state<Component | null>(null);

	// ── lifecycle ───────────────────────────────────────────────────────────
	onMount(() => {
		// a workspace link that lands here (an old `/#v=2…` bookmark, a share link, an Inbox / Movement deep
		// link, a selection) belongs to Analyst: hand it over with its hash, never drop it. A page load never gets
		// this far — the <head> script below leaves before first paint; this is the hand-over for a CLIENT-SIDE
		// arrival (a link in the app still spelling `/#…`), done as a client navigation so the app keeps its state
		const handOver = workspaceHandOver(location.hash);
		if (handOver) {
			void goto(handOver, { replaceState: true, noScroll: true });
			return;
		}
		window.addEventListener('hashchange', handOverNow);
		registerProviders();
		ops.start();
		cityRegistry.start();
		const wait = setTimeout(() => (sessionWaitOver = true), 2500);
		try {
			onboard = localStorage.getItem(ONBOARD_KEY) !== '1';
		} catch {
			onboard = false;
		}
		void import('$lib/workspace/components/omnibar/Omnibar.svelte').then((m) => (Omnibar = m.default as unknown as Component));
		return () => {
			clearTimeout(wait);
			window.removeEventListener('hashchange', handOverNow);
		};
	});

	// a hash-only navigation while Home is open (`/#sel=…` clicked on Home) never remounts the page: hand it over too
	// (the browser's own hashchange for a native anchor jump, afterNavigate for the router's)
	function handOverNow() {
		const handOver = workspaceHandOver(location.hash);
		if (handOver) void goto(handOver, { replaceState: true, noScroll: true });
	}
	afterNavigate((nav) => {
		if (nav.type !== 'enter') handOverNow();
	});

	onDestroy(() => {
		cityRegistry.stop();
		ops.stop();
		if (typeof window !== 'undefined') delete (window as unknown as Record<string, unknown>).__V3_HOME__;
	});

	// ── the shell (the v2 contract + the V3 bar) ───────────────────────────
	$effect(() => {
		commandBar.lang = ops.lang;
		commandBar.onLangChange = (l: string) => (ops.lang = l);
		commandBar.onShare = null;
		commandBar.onSearch = (q?: string) => workspace.openOmnibar(q);
		commandBar.onInbox = null;
	});

	$effect(() => {
		commandBar.officer = {
			value: ops.dutyOfficer,
			fromSession: ops.dutyOfficerFromSession,
			set: (v: string) => ops.setDutyOfficer(v),
		};
	});

	$effect(() => {
		const f = ops.trafficFeed;
		commandBar.exercise =
			f && (f.label === 'simulated' || f.label === 'mixed')
				? {
						label: f.label,
						text:
							f.label === 'simulated'
								? L('wall_exercise_simulated', f.segments)
								: L('wall_exercise_mixed', Math.round((100 * f.synthetic) / Math.max(1, f.real + f.synthetic))),
					}
				: null;
	});

	$effect(() => {
		commandBar.inboxCount = units.length;
		commandBar.inboxIntent = units.length ? 'warning' : 'none';
	});

	const dateLine = $derived.by(() => {
		const locale = lang === 'hi' ? 'hi-IN' : lang === 'mr' ? 'mr-IN' : 'en-GB';
		const day = new Intl.DateTimeFormat(locale, { weekday: 'long', day: 'numeric', month: 'short', timeZone: 'Asia/Kolkata', numberingSystem: 'latn' }).format(slow);
		return [cityName(lang), day, `${fmtTime(now)} IST`].join(' · ');
	});
	const istHour = $derived(Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Asia/Kolkata' }).format(slow)));

	const scene = $derived({ src: sceneSrc(sceneFor(istHour)), alt: L(`v3i_scene_${sceneFor(istHour)}`) });

	$effect(() => {
		v3Bar.title = L(greetingKey(istHour));
		v3Bar.sub = dateLine;
		v3Bar.active = 'home';
	});

	// the alert list primes on the first full answer (the units already waiting never alert); a feed
	// that never answers stops holding it back after 10 s
	const mountedAt = Date.now();
	const firstRound = $derived(
		(ops.boardUpdated > 0 && ops.recommendationsUpdated > 0 && ops.dispatchesUpdated > 0 && ops.escortsDeployed !== null && cityRegistry.status !== 'idle') ||
			now - mountedAt > 10_000,
	);
	$effect(() => {
		v3Bar.decisions = firstRound ? decisionVMs.map((v) => ({ key: v.key, title: v.maskedTitle, href: v.href, emulated: v.emulated })) : null;
	});

	// ── the test hook (the smoke holds the page to the canonical selectors) ─
	$effect(() => {
		if (typeof window === 'undefined') return;
		(window as unknown as Record<string, unknown>).__V3_HOME__ = {
			canonical: {
				decisions: selectors.decisionUnits().length,
				reported: figures.reported,
				watchlisted: figures.watchlisted,
				cameras: figures.cameras,
			},
			shown: { decisions: units.length, live: liveEvents.length, planned: planned.length, reports: reports.length },
			featured: featuredKey,
			order: ordered.map((u) => unitKey(u)),
			officerOn: ops.officerOn,
		};
	});
</script>

<svelte:head>
	<title>{L('v3_nav_home')} · Sajag</title>
	<!-- an old `/#v=2…` bookmark leaves for /analyst#… before Home paints (the fragment never reaches the server) -->
	{@html earlyHandOverTag()}
</svelte:head>

{#if ops.signInRequired}
	<div class="signin" data-testid="cockpit-signin-required">
		<div class="signin-card">
			<h2>{tOps(lang, 'opsSigninTitle')}</h2>
			<p>{tOps(lang, 'cockpitSigninBody')}</p>
			<OperatorSignIn lang={ops.lang} inline />
		</div>
	</div>
{:else}
	<div class="home" data-v3="home" data-ready={sessionWaitOver || ops.boardUpdated > 0 ? 'true' : 'false'}>
		<section class="hero" aria-label={L('v3_hero_now')}>
			<FeatureHero
				vm={heroVM}
				index={1}
				total={units.length}
				next={plannedVMs[0] ?? null}
				{now}
				{lang}
				{roads}
			/>
			<CityPulse
				{band}
				sentence={L(bandSentenceKey(band))}
				meta={pulseMeta}
				{stats}
				{systems}
				{down}
				onRetry={retry}
				{lang}
				{scene}
			/>
		</section>

		<Rail
			id="v3-decide"
			title={L('v3_rail_decide')}
			count={units.length}
			decide
			sub={L('v3_rail_decide_sub')}
			more={{ href: '/decide', text: L('v3_rail_decide_more') }}
			empty={units.length ? null : L('v3_rail_empty_decide')}
			{lang}
		>
			{#each decisionVMs as vm (vm.key)}
				<li><DecisionCard {vm} {now} {lang} {roads} /></li>
			{/each}
		</Rail>

		{#if onboard}
			<section class="onboard" aria-label={L('v3_onb_title')} data-testid="v3-onboarding">
				{#each [1, 2, 3] as i (i)}
					<div class="ob">
						<img src={`/illustrations/onboarding/${i === 1 ? '1-glance' : i === 2 ? '2-decide' : '3-you-decide'}.svg`} alt="" width="120" height="75" />
						<p>{L(`v3_onb_${i}`)}</p>
					</div>
				{/each}
				<button type="button" class="ob-x" onclick={dismissOnboard}>{L('v3_onb_dismiss')}</button>
			</section>
		{/if}

		{#if opVMs.length}
			<div id="v3-live">
				<Rail id="v3-live-rail" title={L('v3_rail_live')} count={opVMs.length} more={{ href: '/map', text: L('v3_rail_live_more') }} {lang}>
					{#each opVMs as vm (vm.key)}
						<li><OperationCard {vm} {lang} {roads} /></li>
					{/each}
				</Rail>
			</div>
		{/if}

		<div id="v3-reported">
			<Rail
				id="v3-reported-rail"
				title={L('v3_rail_reported')}
				count={reportVMs.length}
				sub={L('v3_rail_reported_sub')}
				more={{ href: '/map', text: L('v3_rail_reported_more') }}
				empty={reportVMs.length ? null : L('v3_rail_empty_reported')}
				{lang}
			>
				{#each reportVMs as vm (vm.key)}
					<li><ReportCard {vm} {lang} {roads} /></li>
				{/each}
			</Rail>
		</div>

		<Rail
			id="v3-planned"
			title={L('v3_rail_planned')}
			count={plannedVMs.length}
			sub={L('v3_rail_planned_sub')}
			more={{ href: V3_PLAN.href, text: L('v3_rail_planned_more'), glyph: 'plus' }}
			empty={plannedVMs.length ? null : L('v3_rail_empty_planned')}
			{lang}
		>
			{#each plannedVMs as vm (vm.key)}
				<li><PlannedCard {vm} {lang} {roads} /></li>
			{/each}
		</Rail>

		<footer class="foot-note">
			<span><Glyph name="shield" size={16} />{L('v3_rule_vehicles')}</span>
			<span><Glyph name="spark" size={16} />{L('v3_rule_ai')}</span>
			<Popover placement="top-start" class="v3-pop" aria-label={L('v3_policies')}>
				<button type="button" class="link">{L('v3_policies')}</button>
				{#snippet content()}<PoliciesPanel {lang} />{/snippet}
			</Popover>
			<span class="credit">{L('v3_maps_credit')}: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a></span>
			<span class="credit" data-testid="v3-media-credit">{L('v3i_art_credit')} <a href="/photos/NOTICE.md" target="_blank" rel="noopener">{L('v3i_photos_link')}</a> · {L('v3i_marks_credit')}</span>
		</footer>
	</div>
{/if}

{#if Omnibar}<Omnibar />{/if}

<style>
	.home {
		display: flex;
		flex-direction: column;
		gap: 34px;
		max-width: 2200px;
		padding: 28px var(--v3-gut) 40px;
	}

	.hero {
		display: grid;
		grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
		gap: 24px;
		min-height: 340px;
	}

	.onboard {
		display: flex;
		align-items: center;
		gap: 20px;
		padding: 14px 18px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}

	.ob {
		display: flex;
		flex: 1;
		align-items: center;
		gap: 14px;
		min-width: 0;
	}

	.ob img {
		flex: none;
		width: 120px;
		height: auto;
		border-radius: var(--v3-radius-m);
	}

	.ob p {
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
		line-height: 20px;
	}

	.ob-x {
		flex: none;
		height: var(--v3-ctl);
		padding: 0 16px;
		border: 0;
		border-radius: 18px;
		background: var(--v3-s3);
		color: var(--v3-t1);
		font: inherit;
		font-size: 14px;
		font-weight: 650;
		cursor: pointer;
	}

	.ob-x:hover {
		background: var(--v3-s4);
	}

	.foot-note {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px 22px;
		padding: 4px 2px 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
	}

	.foot-note span {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.link {
		padding: 0;
		border: 0;
		background: none;
		color: var(--v3-brand-text);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	.credit {
		margin-left: auto;
	}

	.credit a {
		color: var(--v3-t2);
	}

	.link:focus-visible,
	.ob-x:focus-visible,
	.credit a:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.signin {
		display: grid;
		place-items: center;
		min-height: 60vh;
		padding: 32px;
	}

	.signin-card {
		max-width: 420px;
		padding: 24px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}

	@media (max-width: 1500px) {
		.hero {
			grid-template-columns: minmax(0, 1.75fr) minmax(330px, 1fr);
			min-height: 300px;
		}
	}

	/* a phone: the hero over the city's pulse, one column */
	@media (max-width: 720px) {
		.home {
			gap: 24px;
			padding: 16px var(--v3-gut) 28px;
		}

		.hero {
			grid-template-columns: minmax(0, 1fr);
			min-height: 0;
		}
	}
</style>
