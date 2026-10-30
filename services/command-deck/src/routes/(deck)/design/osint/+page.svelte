<script lang="ts">
	/**
	 * /design/osint — the OS-DECK-A harness (plan R18, X16): the inspector's
	 * report and place sections, the OSINT actions and the map legend over
	 * FIXTURE data, offline. Not linked from navigation; UI-S7B deletes it.
	 *
	 * Data: tests/fixtures/osint/*.json — the SYNTHETIC wire shapes of the
	 * city snapshot (fictional *.example publishers plus the public-domain
	 * SACHET sample; every summary already redacted at parse). The real
	 * stores are seeded (cityRegistry, dossier); nothing is fetched.
	 *
	 *   ?sel=correlated|district|robbery|place   which object the inspector
	 *                                            opens (default: correlated)
	 *
	 * This page registers ONLY the osint provider (not registerProviders()):
	 * the harness never starts another provider's feeds.
	 */
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { ProvenanceTag, Tag, provideUiLang } from '$lib/ui';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { parseCitySnapshot, parseDossier, type CitySnapshot } from '$lib/gods-eye/city-api';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { dossier } from '$lib/gods-eye/entities/dossier.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import ObjectInspector from '$lib/workspace/components/inspector/ObjectInspector.svelte';
	import MapLegend from '$lib/gods-eye/hud/map/MapLegend.svelte';
	import { register } from '$lib/osint/register';
	import correlatedFixture from '../../../../../tests/fixtures/osint/correlated.json';
	import districtFixture from '../../../../../tests/fixtures/osint/district.json';
	import robberyFixture from '../../../../../tests/fixtures/osint/robbery.json';
	import placeFixture from '../../../../../tests/fixtures/osint/place.json';

	provideUiLang(() => commandBar.lang);

	// ── the fixture world (synthetic; see tests/fixtures/osint/README.md) ──
	const SEGMENT = {
		urn: 'segment:1045',
		kind: 'segment',
		id: '1045',
		label: 'BKC connector',
		lon: 72.7692,
		lat: 18.9932,
		state: null,
		band: null,
		source: 'live',
		verification_state: null,
		credibility: null,
		t: null,
		age_sec: null,
		links: [],
		props: { road_name: 'BKC connector', data_quality: 'synthetic' },
	};
	const JUNCTION = {
		urn: 'junction:11',
		kind: 'junction',
		id: '11',
		label: 'Girgaon Chowpatty',
		lon: 72.9352,
		lat: 19.0082,
		state: null,
		band: null,
		source: 'live',
		verification_state: null,
		credibility: null,
		t: null,
		age_sec: null,
		links: [],
		props: { junction_id: 11, name: 'Girgaon Chowpatty' },
	};
	const SNAPSHOT: CitySnapshot = parseCitySnapshot({
		as_of: '2026-10-25T01:39:01.433Z',
		entities: [correlatedFixture, districtFixture, robberyFixture, placeFixture, SEGMENT, JUNCTION],
		feeds: {
			osint_event: { count: 3, newest_t: '2026-10-20T13:59:00.000Z', age_sec: 387601.4, unlocated: 0, status: 'ok', error: null, held_social: 2 },
			place: { count: 1, newest_t: '2026-10-20T13:59:00.000Z', age_sec: 387601.4, unlocated: 0, status: 'ok', error: null },
		},
	});
	// the dossier carries the per-signal sources (R2): publisher, tier, the redacted title,
	// the fetch mode and a url on OFFICIAL tiers only — the notes beside them, keyed by signal.
	// ETHICS (item 12, fix round 2): the SACHET district warning is the correlated report's
	// CONTEXT member — it is never a corroborating source row — and the district fixture's
	// dossier carries the OFFICIAL reporting source that demos the official link.
	const SG_NEWS = '1a1b2c3d-0000-4c3c-8d4d-000000000001';
	const RB_NEWS_A = '1a1b2c3d-0000-4c3c-8d4d-000000000003';
	const RB_NEWS_C = '1a1b2c3d-0000-4c3c-8d4d-000000000004';
	const DI_OFFICIAL = '1a1b2c3d-0000-4c3c-8d4d-000000000005';
	const SG_SOURCES = {
		sources: [
			{ signal_id: SG_NEWS, source: 'google_news_rss', publisher: 'news-a.example', url: null, title: 'Car crashes into three vehicles near club; [AGE] rider hurt', fetch_mode: 'cached-sample', role: 'primary' },
		],
		source_notes: [{ signal_id: SG_NEWS, source_tier: 'aggregator', link_note: 'source link withheld — may name a person' }],
	};
	const ROBBERY_SOURCES = {
		sources: [
			{ signal_id: RB_NEWS_A, source: 'google_news_rss', publisher: 'news-a.example', url: null, title: 'Robbery reported near Babughat; [PERSON], [AGE] named in report', fetch_mode: 'cached-sample', role: 'primary' },
			{ signal_id: RB_NEWS_C, source: 'gdelt_doc', publisher: 'news-c.example', url: null, title: 'Commercial robbery on ring road', fetch_mode: 'cached-sample', role: 'corroborating' },
		],
		source_notes: [
			{ signal_id: RB_NEWS_A, source_tier: 'aggregator', link_note: 'source link withheld — may name a person' },
			{ signal_id: RB_NEWS_C, source_tier: 'aggregator', link_note: 'source link withheld — may name a person' },
		],
	};
	const DISTRICT_SOURCES = {
		sources: [
			{ signal_id: DI_OFFICIAL, source: 'sachet_cap', publisher: 'sachet.ndma.gov.in', url: 'https://sachet.ndma.gov.in/cap/sample-2026', title: 'Thunderstorm warning for Mumbai City district', fetch_mode: 'cached-sample', role: 'primary' },
		],
		source_notes: [{ signal_id: DI_OFFICIAL, source_tier: 'official', link_note: null }],
	};
	const DOSSIERS = [
		parseDossier(
			{
				entity: { ...correlatedFixture, props: { ...correlatedFixture.props, ...SG_SOURCES } },
				related: [
					{ relation: 'reported_at', entity: placeFixture },
					{ relation: 'on_road', entity: SEGMENT },
				],
				audit: [],
			},
			Date.parse('2026-10-25T01:39:01.433Z'),
		),
		parseDossier({ entity: { ...districtFixture, props: { ...districtFixture.props, ...DISTRICT_SOURCES } }, related: [], audit: [] }, Date.parse('2026-10-25T01:39:01.433Z')),
		parseDossier(
			{
				entity: { ...robberyFixture, props: { ...robberyFixture.props, ...ROBBERY_SOURCES } },
				related: [
					{ relation: 'at_junction', entity: JUNCTION },
					{ relation: 'on_road', entity: SEGMENT },
				],
				audit: [],
			},
			Date.parse('2026-10-25T01:39:01.433Z'),
		),
		parseDossier(
			{
				entity: placeFixture,
				related: [{ relation: 'reported_at', entity: correlatedFixture }],
				audit: [],
			},
			Date.parse('2026-10-25T01:39:01.433Z'),
		),
	].filter((d): d is NonNullable<typeof d> => !!d);

	/** ?sel names the fixture; the URN it selects. */
	const URNS: Record<string, string> = {
		correlated: correlatedFixture.urn,
		district: districtFixture.urn,
		robbery: robberyFixture.urn,
		place: placeFixture.urn,
	};

	let ready = $state(false);
	onMount(() => {
		register();
		// the OSINT surfaces read ops.lang (the section, the actions): a language switch on
		// the command bar reaches them the way it does on / and /gods-eye (fix round 2, item 11)
		commandBar.onLangChange = (l) => (ops.lang = l);
		cityRegistry.seed(SNAPSHOT, 'design harness: synthetic fixture data');
		dossier.seed(DOSSIERS);
		const params = $page.url.searchParams;
		const want = params.get('sel') ?? 'correlated';
		selection.select(URNS[want] ?? URNS.correlated, { source: 'map' });
		(window as unknown as Record<string, unknown>).__OSINT_HARNESS__ = {
			select: (name: string) => selection.select(URNS[name] ?? URNS.correlated, { source: 'map' }),
		};
		ready = true;
		return () => {
			selection.clear();
			dossier.unseed();
			cityRegistry.unseed();
		};
	});
</script>

<svelte:head><title>OSINT harness · Sajag</title></svelte:head>

<div class="harness" data-harness="osint" data-ready={ready}>
	<header class="hb">
		<strong>OSINT surfaces</strong>
		<span class="muted">Synthetic capture · Mumbai</span>
		<span class="grow"></span>
		<ProvenanceTag source="osint" lang={commandBar.lang} />
		<Tag icon="lab-test" tooltip="Design harness: the synthetic OSINT fixtures (fictional *.example publishers, the public-domain SACHET sample). Not linked from navigation.">Fixture data</Tag>
	</header>

	{#if !ready}
		<div class="wait"></div>
	{:else}
		<div class="grid">
			<section class="cell inspector" aria-label="Object inspector">
				<ObjectInspector urn={selection.current} />
			</section>

			<section class="cell side" aria-label="Selection and legend">
				<div class="cap">Fixture objects (synthetic) — click to inspect</div>
				<div class="picks">
					<button type="button" class="pick" data-testid="harness-sel-correlated" onclick={() => selection.select(URNS.correlated, { source: 'map' })}>
						<span class="dot" style="background: var(--v-map-decision)"></span>
						Road accident · BKC (Bandra Kurla Complex)
					</button>
					<button type="button" class="pick" data-testid="harness-sel-district" onclick={() => selection.select(URNS.district, { source: 'map' })}>
						<span class="dot area"></span>
						Weather hazard · Mumbai City district
					</button>
					<button type="button" class="pick" data-testid="harness-sel-robbery" onclick={() => selection.select(URNS.robbery, { source: 'map' })}>
						<span class="dot"></span>
						Reported crime · Girgaon Chowpatty
					</button>
					<button type="button" class="pick" data-testid="harness-sel-place" onclick={() => selection.select(URNS.place, { source: 'map' })}>
						<span class="dot place"></span>
						BKC (Bandra Kurla Complex)
					</button>
				</div>

				<div class="cap">Map legend preview</div>
				<MapLegend lang={commandBar.lang} />
				<div class="cap">The reported-situation marks (this work package)</div>
				<div class="rows">
					<div class="row">
						<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
							<circle cx="12" cy="12" r="7" fill="var(--v-map-marker-fill)" stroke="var(--v-map-marker)" stroke-width="1.5" />
							<circle cx="12" cy="12" r="2" fill="var(--v-map-label-ink)" />
						</svg>
						<span>Reported situation — neutral, its glyph on hover; the hover label names it</span>
					</div>
					<div class="row">
						<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
							<circle cx="12" cy="12" r="7" fill="var(--v-map-marker-fill)" stroke="var(--v-map-decision)" stroke-width="2.5" />
							<circle cx="12" cy="12" r="2" fill="var(--v-map-label-ink)" />
						</svg>
						<span>Awaiting a decision — the orange decision dot (one per waiting report, on selected and clustered markers too); the proposal is decided in its one home</span>
					</div>
					<div class="row">
						<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
							<circle cx="12" cy="12" r="10.5" fill="none" stroke="var(--v-map-marker)" stroke-width="1.5" stroke-dasharray="3 3" />
							<circle cx="12" cy="12" r="6" fill="var(--v-map-marker-fill)" stroke="var(--v-map-marker)" stroke-width="1.5" />
						</svg>
						<span>District-level report — the same glyph inside an area ring; not a precise pin</span>
					</div>
					<div class="row">
						<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
							<circle cx="12" cy="12" r="6" fill="var(--v-map-marker-fill)" stroke="var(--v-map-marker)" stroke-width="1.5" />
						</svg>
						<span>Reported-at place (the places layer, off by default)</span>
					</div>
				</div>
				<p class="note">Fixture data only: fictional *.example publishers and the public-domain SACHET sample. Sajag never identifies people.</p>
			</section>
		</div>
	{/if}
</div>

<style>
	.harness {
		position: fixed;
		inset: 0;
		z-index: 40;
		display: flex;
		flex-direction: column;
		background: var(--v-canvas);
		color: var(--v-ink-1);
		font-size: 14px;
	}

	.hb {
		display: flex;
		align-items: center;
		gap: 12px;
		flex: 0 0 auto;
		height: 40px;
		padding: 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
	}

	.muted {
		color: var(--v-ink-2);
	}

	.grow {
		flex: 1 1 auto;
	}

	.wait {
		flex: 1 1 auto;
	}

	.grid {
		flex: 1 1 auto;
		min-height: 0;
		display: grid;
		grid-template-columns: minmax(340px, 440px) minmax(0, 1fr);
	}

	.cell {
		min-height: 0;
		overflow: auto;
		background: var(--v-surface-1);
	}

	.inspector {
		border-right: 1px solid var(--v-line-2);
	}

	.side {
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.cap {
		color: var(--v-ink-2);
		font-size: 12px;
		line-height: 16px;
	}

	.picks {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.pick {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		padding: 8px 12px;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-2);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
		color: var(--v-ink-1);
		font: inherit;
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		text-align: left;
		cursor: pointer;
	}

	.pick:hover {
		background: var(--v-surface-3);
	}

	.pick:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.dot {
		flex: 0 0 auto;
		width: 14px;
		height: 14px;
		border-radius: 999px;
		background: var(--v-map-marker-fill);
		box-shadow: inset 0 0 0 1.5px var(--v-map-marker);
	}

	.dot.area {
		box-shadow: inset 0 0 0 1.5px var(--v-map-marker);
	}

	.dot.place {
		width: 11px;
		height: 11px;
	}

	.rows {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 10px;
		color: var(--v-ink-2);
		font-size: 12px;
		line-height: 16px;
	}

	.note {
		margin: 8px 0 0;
		color: var(--v-ink-2);
		font-size: 12px;
		line-height: 16px;
	}
</style>
