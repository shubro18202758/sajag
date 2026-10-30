<script lang="ts">
	/**
	 * City vitals (SPEC §6.2, §12.1.2, §12.2) — the city in a glance, in one
	 * of two variants, ONE mounted at a time:
	 *
	 *   card   map mode's floating card (top right, `city-vitals`): open
	 *          events, decisions waiting (units), watchlisted vehicles (the
	 *          registry count — the Explorer's figure), cameras answering,
	 *          feed anomalies, reported events when there are any, and the
	 *          traffic feed's provenance (`vitals-feeds .sim`). No band: the
	 *          band is in the navbar.
	 *   info   the left dock's Info tab (and today's /gods-eye rail, the
	 *          default): posture, events by kind, decisions waiting, units and
	 *          ANPR, the ethics rails, signals, AI tiers and feeds, with every
	 *          `vitals-*` id the smokes read.
	 *
	 * Both derive from the same stores here and publish the same figures to
	 * the canvas test snapshot (window.__GODS_EYE__.vitals, through
	 * cityVitals.shown) — unchanged in shape. Vitals are never time-travelled:
	 * during a replay they keep showing live data and say so (§7.3).
	 *
	 * POSTURE is the highest band over ACTIVE events (registry); with no
	 * active banded event, the CITY band the signal writer acts on. Either is
	 * aged from its newest READING and is STALE only past 10 min; how long it
	 * has HELD is a line of its own; a stale city band reads Unknown, never
	 * Green. Every number is a count of fused rows or a server health field;
	 * a rung that cannot answer says so in neutral ink. Clicking a figure
	 * selects (and flies to) the object behind it.
	 *
	 * Props: `variant` (default 'info': today's /gods-eye page mounts it
	 * without props) and `poll` (default true; false — or a seeded vitals
	 * store — starts no poller: the /design harnesses read their fixtures).
	 *
	 * One variant at a time (§12.1.2: no duplicate `city-vitals`): a second
	 * mounted instance warns in dev; the snapshot is cleared only when the
	 * last instance unmounts, so one leaving never blanks another's.
	 */
	import { onDestroy, onMount } from 'svelte';
	import { dev } from '$app/environment';
	import { provideUiLang } from '$lib/ui';
	import { ops } from '$lib/ops/store.svelte';
	import { isSignInRequired } from '$lib/ops/client';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.views';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { corridor } from '$lib/ops/components/template/corridor.svelte';
	import { registrySize } from '$lib/workspace/registry';
	import { liveWorld, selectors } from '$lib/workspace/world.svelte';
	import { cardFigures, isEvidenceRec, registryUnits } from '$lib/workspace/components/vitals/figures';
	import { displayTitle } from '$lib/workspace/display';
	import VitalsCard from '$lib/workspace/components/vitals/VitalsCard.svelte';
	import VitalsInfo from '$lib/workspace/components/vitals/VitalsInfo.svelte';
	import type { PostureView, VitalsView } from '$lib/workspace/components/vitals/types';
	import { cityRegistry } from '../entities/registry.svelte';
	import { selection } from '../entities/selection.svelte';
	import { godsEye } from '../store.svelte';
	import { cityVitals } from './vitals.svelte';
	import { fusionFeed } from './feed.svelte';
	import { replay } from './replay.svelte';
	import { ageOf } from './format';
	import { isAmber } from '../layers/signal-network';
	import { unitPhase } from '../layers/agency';
	import type { BandCode } from '../city-api';

	let { variant = 'info', poll = true }: { variant?: 'card' | 'info'; poll?: boolean } = $props();

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);

	const BAND_RANK: Record<BandCode, number> = { GREEN: 0, AMBER: 1, RED: 2, BLACK: 3 };
	/** A posture older than this renders stale (the AMA chip's threshold). */
	const POSTURE_STALE_SEC = 600;

	let now = $state(Date.now());
	let clock: ReturnType<typeof setInterval> | null = null;
	/** Pollers this mount started (none in a harness: poll=false or a seeded store). */
	let polling = false;
	const instance = Symbol('city-vitals');

	onMount(() => {
		const mounted = cityVitals.attach(instance);
		if (dev && mounted > 1) console.warn(`City vitals: ${mounted} variants are mounted at once; mount one at a time (SPEC §12.1.2: no duplicate city-vitals)`);
		polling = poll && !cityVitals.seeded;
		if (polling) {
			cityRegistry.start();
			cityVitals.start();
			fusionFeed.start();
			corridor.start();
		}
		clock = setInterval(() => (now = Date.now()), 1000);
	});

	onDestroy(() => {
		if (clock) clearInterval(clock);
		if (polling) {
			corridor.stop();
			fusionFeed.stop();
			cityVitals.stop();
			cityRegistry.stop();
		}
		// the snapshot goes only with the last variant (another still mounted keeps publishing it)
		cityVitals.detach(instance);
	});

	/** A feed note in the console's words (the gate's refusal reads as such). */
	function noteText(note: string | null | undefined): string | null {
		if (!note) return null;
		return isSignInRequired(note) ? t(lang, 'vw_i_signin') : note;
	}

	function epoch(v: unknown): number | null {
		if (typeof v !== 'string') return null;
		const ms = Date.parse(v);
		return Number.isFinite(ms) ? ms : null;
	}

	// ─── posture ───────────────────────────────────────────────────────────────

	const postureBase = $derived.by(() => {
		const active = cityRegistry.byKind('event').filter((e) => e.state === 'active' && e.band);
		if (active.length) {
			const top = [...active].sort((a, b) => BAND_RANK[b.band as BandCode] - BAND_RANK[a.band as BandCode] || (b.t ?? 0) - (a.t ?? 0))[0];
			const transition = fusionFeed.rows.find(
				(r) => r.kind === 'ama' && r.id.startsWith('situation_log:') && r.urns.includes(top.urn) && r.props.situation_class === top.band,
			);
			// aged from the subject's newest reading (band_t); its transition row is when the band was entered
			const readingAt = epoch(top.props.band_t);
			return {
				band: top.band as BandCode | null,
				urn: top.urn as string | null,
				label: displayTitle(top.label, lang),
				events: active.length,
				at: readingAt ?? transition?.t ?? null,
				basis: readingAt != null ? ('reading' as const) : ('transition' as const),
				source: 'events' as const,
				simulated: top.props.simulated_feed === true,
				emulated: top.source === 'emulated',
				heldSince: transition?.t ?? null,
				engineStale: false,
				staleSince: null as number | null,
			};
		}
		// no active event carries a band: the city band (never empty while it answers)
		const cb = ops.cityBand;
		if (cb && (cb.band || cb.stale)) {
			return {
				band: cb.stale ? null : cb.band,
				urn: null,
				label: t(lang, 'vw_i_posture_city'),
				events: 0,
				// aged from its NEWEST READING (the engine's last evaluation, else this console's last
				// read) — never from the moment it was entered: that is how long it has HELD
				at: cb.stale ? null : (cb.evaluatedAt ?? (ops.cityBandUpdated || null)),
				basis: cb.stale ? ('none' as const) : ('reading' as const),
				source: 'city-band' as const,
				simulated: cb.simulatedFeed === true,
				emulated: false,
				heldSince: cb.stale ? null : cb.since,
				engineStale: cb.stale,
				staleSince: cb.stale ? cb.staleSince : null,
			};
		}
		if (ops.band && ops.bandSourceKind === 'city-band') {
			return {
				band: ops.band as BandCode | null,
				urn: null,
				label: t(lang, 'vw_i_posture_city'),
				events: 0,
				at: ops.bandUpdated || null,
				basis: ops.bandUpdated ? ('reading' as const) : ('none' as const),
				source: 'city-band' as const,
				simulated: ops.bandSimulated === true,
				emulated: false,
				heldSince: ops.bandCommittedAt,
				engineStale: false,
				staleSince: null as number | null,
			};
		}
		return null;
	});

	const posture = $derived.by((): PostureView | null => {
		const p = postureBase;
		if (!p) return null;
		const age = p.at != null ? ageOf(p.at, now) : null;
		const held = p.heldSince != null ? ageOf(p.heldSince, now) : null;
		return { ...p, ageSec: age != null ? Math.round(age) : null, stale: age != null && age > POSTURE_STALE_SEC, heldSec: held != null ? Math.round(held) : null };
	});

	// ─── events / decisions / units / ANPR ─────────────────────────────────────

	const eventKinds = $derived.by(() => {
		const m = new Map<string, { kind: string; total: number; active: number; emulated: number; urn: string }>();
		for (const e of cityRegistry.byKind('event')) {
			const kind = typeof e.props.event_kind === 'string' ? e.props.event_kind : 'unknown';
			const row = m.get(kind) ?? { kind, total: 0, active: 0, emulated: 0, urn: e.urn };
			row.total++;
			if (e.state === 'active') row.active++;
			if (e.source === 'emulated') row.emulated++;
			m.set(kind, row);
		}
		return [...m.values()].sort((a, b) => b.active - a.active || b.total - a.total);
	});

	const pendingRecs = $derived(cityRegistry.byKind('recommendation').filter((r) => r.state === 'pending'));
	/** Penal e-challans an officer can approve — never a stolen vehicle's (C-N). */
	const echallans = $derived(pendingRecs.filter((r) => !isEvidenceRec(r.props) && r.props.approvable !== false));
	/** Evidence-only stolen-vehicle sightings (R_STOLEN_SIGHTING): a pursuit authorisation, no fine. */
	const stolenSightings = $derived(pendingRecs.filter((r) => isEvidenceRec(r.props)));
	/** Penal rows withheld for a vehicle reported stolen: an officer can only reject them. */
	const withheld = $derived(pendingRecs.filter((r) => !isEvidenceRec(r.props) && r.props.approvable === false));
	const requested = $derived(cityRegistry.byKind('dispatch').filter((d) => d.state === 'requested'));
	const ambulance = $derived(requested.filter((d) => d.props.agency === 'ambulance'));
	/** The escorts' open proposals (an officer approves every switch). */
	const escortProposals = $derived(ops.escortProposals);
	const decisionsTotal = $derived(pendingRecs.length + requested.length + escortProposals.length);
	/**
	 * Decisions waiting as UNITS (SPEC §7.4, the Inbox's count): decisionUnits()
	 * once a decision provider registers its source, else the same rule on the
	 * registry. The snapshot keeps its row count (decisions.total) unchanged.
	 */
	const unitSources = $derived(registrySize().units);
	const unitsWaiting = $derived(
		unitSources > 0 ? selectors.decisionUnits().length : registryUnits([...pendingRecs, ...requested], escortProposals.length),
	);
	/** The road network as the canvas draws it: OSM-traced ('osm' / 'osm_display') vs schematic. */
	const roadsTraced = $derived(godsEye.segments.filter((s) => s.geometryBasis !== 'schematic').length);
	const roadsSchematic = $derived(godsEye.segments.length - roadsTraced);

	const units = $derived(godsEye.units);
	// one partition (agency.ts unitPhase): an arrived unit is on scene, never also en route
	const unitsEnRoute = $derived(units.filter((u) => unitPhase(u) === 'en_route'));
	const unitsOnScene = $derived(units.filter((u) => unitPhase(u) === 'on_scene'));

	const cams = $derived(godsEye.cameras);
	const hits15 = $derived(cams.reduce((n, c) => n + c.hits15m, 0));
	const reads15 = $derived(cams.reduce((n, c) => n + c.reads15m, 0));
	const reporting = $derived(cams.filter((c) => c.reads15m > 0).length);
	const busiestCam = $derived([...cams].sort((a, b) => b.hits15m * 1000 + b.reads15m - (a.hits15m * 1000 + a.reads15m))[0] ?? null);

	// ─── signals ───────────────────────────────────────────────────────────────

	const plans = $derived(ops.signalPlans);
	const programs = $derived(godsEye.signals);
	const programsAmber = $derived(programs.filter((s) => isAmber(s)).length);
	const programsRed = $derived(programs.filter((s) => !isAmber(s) && s.phaseLost === true).length);

	// ─── feeds ─────────────────────────────────────────────────────────────────

	const ingest = $derived(cityVitals.ingest);
	const brain = $derived(cityVitals.brain);
	const retention = $derived(cityVitals.retention);
	const latestRun = $derived(cityVitals.runs.value?.[0] ?? null);
	const living = $derived(cityVitals.livingCity);
	const registryAge = $derived(cityRegistry.updatedAt ? ageOf(cityRegistry.updatedAt, now) : null);
	const sightingsT = $derived(cityRegistry.feed('sighting')?.newestT ?? cityRegistry.feed('vehicle')?.newestT ?? null);

	// ─── ethics ────────────────────────────────────────────────────────────────

	const lawful = $derived.by(() => {
		const m = new Map<string, number>();
		for (const v of cityRegistry.byKind('vehicle')) {
			const basis = typeof v.props.lawful_basis === 'string' ? v.props.lawful_basis : 'none';
			m.set(basis, (m.get(basis) ?? 0) + 1);
		}
		return [...m.entries()].sort((a, b) => b[1] - a[1]);
	});

	// ─── the traffic feed's provenance; the card's figures (one selector per quantity, SPEC §7.4) ──

	/** Simulated when the corridor summary says so or a road's observation is synthetic. */
	const trafficSimulated = $derived(corridor.simulated || cityRegistry.byKind('segment').some((s) => s.props.data_quality === 'synthetic'));

	// only the card reads the object model (the info rail on today's /gods-eye never builds it)
	const card = $derived(
		variant === 'card'
			? cardFigures({
					selectors,
					registry: liveWorld.registry(),
					unitSources,
					escortProposals: escortProposals.length,
					corridorSimulated: trafficSimulated,
				})
			: null,
	);

	const link = (list: { urn: string; id: string }[]) => ({ n: list.length, urn: list[0]?.urn ?? null, id: list[0]?.id ?? null });

	const view = $derived<VitalsView>({
		now,
		replay: replay.mode === 'replay',
		registry: { size: cityRegistry.size, ageSec: registryAge != null ? Math.round(registryAge) : null, status: cityRegistry.status, note: noteText(cityRegistry.note), tookMs: cityRegistry.tookMs ?? null },
		card,
		posture,
		events: { total: cityRegistry.byKind('event').length, kinds: eventKinds },
		decisions: {
			total: decisionsTotal,
			units: unitsWaiting,
			fromUnits: unitSources > 0,
			escortProposals: escortProposals.length,
			echallans: link(echallans),
			stolen: link(stolenSightings),
			withheld: link(withheld),
			requested: link(requested),
			ambulance: link(ambulance),
		},
		units: {
			out: units.length,
			enRoute: unitsEnRoute.length,
			onScene: unitsOnScene.length,
			urn: unitsEnRoute[0] ? `unit:${unitsEnRoute[0].unitId}` : units[0] ? `unit:${units[0].unitId}` : null,
		},
		anpr: { hits: hits15, reads: reads15, reporting, cameras: cams.length, urn: busiestCam ? `camera:${busiestCam.cameraId}` : null },
		ethics: { retention: { ...retention, note: noteText(retention.note) }, lawful, officer: ops.officerOn ? ops.dutyOfficer.trim() : null },
		signals: {
			plans,
			note: noteText(ops.signalPlansNote),
			programs: programs.length,
			green: programs.length - programsAmber - programsRed,
			amber: programsAmber,
			red: programsRed,
		},
		brain: { ...brain, note: noteText(brain.note) },
		feeds: {
			ingest: { ...ingest, note: noteText(ingest.note) },
			trafficSimulated: card?.trafficSimulated ?? trafficSimulated,
			roads: { traced: roadsTraced, schematic: roadsSchematic, known: godsEye.segments.length > 0 },
			sightingAgeSec: sightingsT != null ? Math.round(ageOf(sightingsT, now) ?? 0) : null,
			runs: { ...cityVitals.runs, note: noteText(cityVitals.runs.note) },
			living: { ...living, note: noteText(living.note) },
		},
	});

	function go(urn: string | null | undefined) {
		if (urn) selection.select(urn, { fly: true, source: 'vitals' });
	}

	// What this variant shows, published for the canvas test snapshot (window.__GODS_EYE__.vitals);
	// the same shape whichever variant is mounted.
	$effect(() => {
		const kinds: Record<string, number> = {};
		let activeEvents = 0;
		let emulatedEvents = 0;
		for (const k of eventKinds) {
			kinds[k.kind] = k.total;
			activeEvents += k.active;
			emulatedEvents += k.emulated;
		}
		// built apart so the snapshot's additive keys (stolen sightings, withheld rows,
		// escort proposals, the roads' basis) ride along
		const decisionsShown = {
			total: decisionsTotal,
			echallans: echallans.length,
			stolenSightings: stolenSightings.length,
			withheld: withheld.length,
			escortProposals: escortProposals.length,
			dispatchRequests: requested.length,
			ambulance: ambulance.length,
		};
		const feedsShown = {
			ingestPerMin: ingest.value?.msgsPerMin ?? null,
			ingestAgeSec: ingest.value?.lastMsgAgeSec ?? null,
			simulated: corridor.simulated,
			registryEntities: cityRegistry.size,
			registryAgeSec: registryAge != null ? Math.round(registryAge) : null,
			sightingAgeSec: sightingsT != null ? Math.round(ageOf(sightingsT, now) ?? 0) : null,
			emulatorRun: latestRun?.runId ?? null,
			livingCity: living.value ? (living.value.status ?? (living.value.enabled ? 'on' : 'off')) : living.state,
			roads: { traced: roadsTraced, schematic: roadsSchematic },
		};
		cityVitals.shown = {
			posture: posture
				? {
						band: posture.band,
						ageSec: posture.ageSec,
						heldSec: posture.heldSec,
						basis: posture.basis,
						stale: posture.stale || posture.engineStale,
						source: posture.source,
						urn: posture.urn,
						simulated: posture.simulated,
					}
				: null,
			events: { total: cityRegistry.byKind('event').length, active: activeEvents, emulated: emulatedEvents, kinds },
			decisions: decisionsShown,
			units: { out: units.length, enRoute: unitsEnRoute.length, onScene: unitsOnScene.length },
			anpr: { hits15m: hits15, reads15m: reads15, reporting, cameras: cams.length },
			signals: {
				writerOn: plans ? plans.writerEnabled : null,
				twinInFlight: plans ? (plans.gate.twinInFlight ?? 0) : null,
				programs: programs.length,
				green: programs.length - programsAmber - programsRed,
				amber: programsAmber,
				red: programsRed,
			},
			feeds: feedsShown,
			ai: brain.value
				? {
						decider: brain.value.decider,
						p95Ms: brain.value.p95Ms,
						gemma: brain.value.gemma,
						degraded: brain.value.deciderDegraded,
					}
				: null,
			ethics: {
				reaper: retention.value ? (retention.value.healthy === false ? 'failing' : 'healthy') : retention.state,
				consecutiveFailures: retention.value?.consecutiveFailures ?? null,
				lawfulBasis: Object.fromEntries(lawful),
				platesMasked: !ops.officerOn,
			},
		};
	});
</script>

{#if variant === 'card'}
	<VitalsCard {view} {lang} />
{:else}
	<VitalsInfo {view} {lang} onpick={go} />
{/if}
