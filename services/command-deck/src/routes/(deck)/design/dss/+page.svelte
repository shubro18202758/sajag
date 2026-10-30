<script lang="ts">
	/**
	 * /design/dss — the OS-DECK-B harness (plan R18, X16): a dev-only page,
	 * not linked anywhere, that seeds the city registry, the ops store and
	 * the dss state with a SYNTHETIC decision-support proposal (fixtures
	 * `tests/fixtures/dss/*.json`; fictional publishers news-a.example /
	 * news-b.example / sachet.ndma.gov.in; the fictional "Sandbox Officer";
	 * no person or plate field anywhere) and shows every decision-support
	 * surface offline:
	 *
	 *   - the /ops Decisions column (DecisionQueue) with the seeded dss item;
	 *   - the Inbox with the unit's detail view — the proposal's ONE home on
	 *     this route (`?open=1` opens it directly);
	 *   - the inspector's Decision support section in its two states
	 *     (`?section=1` scrolls to it): a proposed DSS with its link card to
	 *     the home, and no proposal with Generate (disabled on a closed
	 *     event);
	 *   - the Promote dialog (the registered action only opens it; confirm
	 *     would fire against whatever backend serves the page).
	 *
	 * The harness bar (fix round 2, for tests/dss-card-smoke.mjs): the duty
	 * officer toggle (`harness-officer`) and the fixture switch
	 * (`harness-fixture`, road accident / weather hazard). Both fixtures
	 * re-seed IMPERATIVELY — the seed never runs inside a reactive effect
	 * (seeding the global registry from one wedged the hydration loop on
	 * this Svelte build; the old harness seeded in onMount and so does this
	 * one, and the toggle calls the same seed function directly).
	 * A dss link card's click (workspace.openDecisionHome) switches this
	 * dock back to the Inbox, as the real workspace's dock would.
	 *
	 * Nothing is polled: the ops store is never started and the C-U object
	 * comes from the fixture (no GET).
	 *
	 * UI-S7B deletes it.
	 */
	import { onMount } from 'svelte';
	import { untrack } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { provideUiLang, Callout, Tag } from '$lib/ui';
	import DecisionQueue from '$lib/ops/components/DecisionQueue.svelte';
	import Inbox from '$lib/decisions/Inbox.svelte';
	import DecisionSupportSection from '$lib/dss/DecisionSupportSection.svelte';
	import { decisionUnits } from '$lib/decisions/units';
	import { parseDecisionSupport } from '$lib/ops/client';
	import type { VerificationState } from '$lib/ops/types';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { resetDssState, seedDssObject } from '$lib/dss/dss-store.svelte';
	import roadFixture from '../../../../../tests/fixtures/dss/dss_road_accident.json';
	import hazardFixture from '../../../../../tests/fixtures/dss/dss_weather_hazard.json';

	provideUiLang(() => commandBar.lang);

	const NOW = Date.now();
	const OFFICER = 'Sandbox Officer';

	/** The two fixtures and the synthetic subject each one is shown on. */
	const FIXTURE_META = {
		road_accident: {
			fixture: roadFixture,
			tab: 'Road accident',
			osintId: 'd5a1e555-0000-4000-8000-00000000e001',
			label: 'Road accident · BKC (Bandra Kurla Complex)',
			summary: 'Car crashes into three vehicles near BKC; [AGE] scooter rider among 3 injured',
			eventClass: 'road_accident',
			verificationState: 'NEWS-REPORTED' as VerificationState,
			credibility: 0.65,
			lon: 72.7652,
			lat: 18.9922,
			segmentId: 1045,
		},
		weather_hazard: {
			fixture: hazardFixture,
			tab: 'Weather hazard',
			osintId: 'd5a1e555-0000-4000-8000-00000000e002',
			label: 'Weather hazard · Mumbai City district',
			summary: 'Light rain likely at isolated places over the district in the next six hours',
			eventClass: 'weather_hazard',
			verificationState: 'OFFICIAL-VERIFIED' as VerificationState,
			credibility: 0.95,
			lon: 72.8322,
			lat: 19.0032,
			segmentId: null,
		},
	} as const;

	type FixtureId = keyof typeof FIXTURE_META;

	let fixtureId = $state<FixtureId>('road_accident');
	const meta = $derived(FIXTURE_META[fixtureId]);
	const DSS = $derived.by(() => {
		const d = parseDecisionSupport(meta.fixture);
		if (!d) throw new Error('dss harness: the fixture did not parse');
		return d;
	});

	const summary = $derived({
		dss_id: DSS.dssId,
		state: 'proposed',
		top_coa_id: DSS.recommendation.topCoaId,
		top_coa_label: DSS.coaSet.find((c) => c.coaId === DSS.recommendation.topCoaId)?.label ?? null,
		generated_at: new Date(NOW - 25 * 60_000).toISOString(),
		horizon_min: 120,
		expires_at: new Date(NOW + 95 * 60_000).toISOString(),
	});

	/** The subject as the city snapshot carries it (kind osint_event, source osint, masked label). */
	const SUBJECT = $derived({
		urn: `osint_event:${meta.osintId}`,
		kind: 'osint_event' as const,
		id: meta.osintId,
		label: meta.label,
		lon: meta.lon,
		lat: meta.lat,
		state: null,
		band: null,
		source: 'osint' as const,
		verificationState: meta.verificationState,
		credibility: meta.credibility,
		t: NOW - 30 * 60_000,
		ageSec: 1800,
		links: [],
		props: {
			label: meta.label,
			summary: meta.summary,
			event_class: meta.eventClass,
			sajag_event_kind: meta.eventClass,
			verification_state: meta.verificationState,
			credibility: meta.credibility,
			second_order: [],
			promoted_event_id: null,
			segment_id: meta.segmentId,
			junction_id: null,
			dss: summary,
		},
	});

	/** A second object with NO proposal on a CLOSED event: the Generate state, disabled with its reason. */
	const CLOSED_EVENT = {
		urn: 'event:d5a1e555-0000-4000-8000-0000000009f2',
		kind: 'event' as const,
		id: 'd5a1e555-0000-4000-8000-0000000009f2',
		label: 'Procession (completed)',
		lon: 72.8473,
		lat: 19.0090,
		state: 'completed',
		band: null,
		source: 'live' as const,
		verificationState: null,
		credibility: null,
		t: NOW - 4 * 3_600_000,
		ageSec: 4 * 3600,
		links: [],
		props: { label: 'Procession (completed)', second_order: [] },
	};

	type HarnessEntity = {
		urn: string;
		kind: 'osint_event' | 'event';
		id: string;
		label: string;
		lon: number;
		lat: number;
		state: string | null;
		verificationState: VerificationState | null;
		credibility: number | null;
		t: number;
		props: Record<string, unknown>;
	};

	const sectionRow = (entity: HarnessEntity) => ({
		urn: entity.urn,
		kind: entity.kind,
		id: entity.id,
		label: entity.label,
		sublabel: null,
		icon: entity.kind === 'osint_event' ? ('geosearch' as const) : ('timeline-events' as const),
		state: entity.state,
		stateIntent: 'none' as const,
		t: entity.t,
		end: null,
		lon: entity.lon,
		lat: entity.lat,
		source: 'osint' as const,
		verification: entity.verificationState,
		credibility: entity.credibility,
		test: false,
		masked: false,
		props: entity.props,
	});

	let ready = $state(false);
	let rightTab = $state<'inbox' | 'sections'>('inbox');
	let inboxOpen = $state<string | null>(null);

	/**
	 * Seed (or re-seed, on a fixture switch) the registry and the dss store
	 * with the current fixture — IMPERATIVE, never from a reactive effect
	 * (see the header note). An open card follows the new proposal's id.
	 */
	function seedFixture() {
		const obj = DSS;
		untrack(() => {
			cityRegistry.seed({ asOf: NOW, entities: [SUBJECT, CLOSED_EVENT], feeds: {}, tookMs: 1 });
			resetDssState();
			seedDssObject(obj);
			if (inboxOpen) inboxOpen = `dss:${obj.dssId}`;
		});
	}

	onMount(() => {
		const params = new URLSearchParams(window.location.search);
		const savedOfficer = ops.dutyOfficer;
		// the ops store never starts here (nothing is polled), so nobody adopts the
		// persisted sajag_lang choice — the harness renders in the console's language
		ops.adoptLangCookie();
		if (params.get('officer') === '1') ops.setDutyOfficer(OFFICER);
		if (params.get('open') === '1') {
			inboxOpen = `dss:${DSS.dssId}`;
			rightTab = 'inbox';
		}
		if (params.get('section') === '1') rightTab = 'sections';
		seedFixture();
		ready = true;
		return () => {
			cityRegistry.unseed();
			resetDssState();
			ops.setDutyOfficer(savedOfficer);
			commandBar.officer = null;
		};
	});

	// the navbar's officer control, as a rebuilt page supplies it
	$effect(() => {
		if (!ready) return;
		commandBar.officer = { value: ops.dutyOfficer, fromSession: ops.dutyOfficerFromSession, set: (v: string) => ops.setDutyOfficer(v) };
	});

	// a decision link card's click (workspace.openDecisionHome) opens the Inbox here too
	let seenFocus = 0;
	$effect(() => {
		const f = workspace.focusDecision;
		if (!f || f.seq === seenFocus) return;
		seenFocus = f.seq;
		rightTab = 'inbox';
	});

	// ── the harness bar ──────────────────────────────────────────────────

	const officerOn = $derived(!!ops.dutyOfficer);
	function toggleOfficer() {
		ops.setDutyOfficer(officerOn ? '' : OFFICER);
	}

	function switchFixture(id: FixtureId) {
		if (id === fixtureId) return;
		fixtureId = id;
		seedFixture();
	}

	const units = $derived(ready ? decisionUnits() : []);
</script>

<svelte:head><title>DSS harness · Sajag</title></svelte:head>

<div class="harness" data-testid="dss-harness">
	<section class="col queue">
		<header class="col-head"><h2>Decisions</h2><span class="sub">/ops column · the seeded dss item</span></header>
		<div class="scroll">
			{#if ready}<DecisionQueue />{/if}
		</div>
	</section>

	<section class="col dock">
		<div class="dock-tabs">
			<button type="button" class="dt" class:is-selected={rightTab === 'inbox'} onclick={() => (rightTab = 'inbox')}>Inbox{#if units.length}<Tag intent="warning">{units.length}</Tag>{/if}</button>
			<button type="button" class="dt" class:is-selected={rightTab === 'sections'} onclick={() => (rightTab = 'sections')}>Inspector sections</button>
			<span class="bar">
				<button type="button" class="hb" data-testid="harness-officer" data-on={officerOn ? '1' : '0'} onclick={toggleOfficer} title="Toggle the duty officer (re-seeds nothing; the card's gates follow)">
					{officerOn ? `Officer: ${ops.dutyOfficer}` : 'Officer: none'}
				</button>
				{#each Object.entries(FIXTURE_META) as [id, m] (id)}
					<button
						type="button"
						class="hb"
						data-testid="harness-fixture"
						data-fixture={id}
						class:is-selected={fixtureId === id}
						onclick={() => switchFixture(id as FixtureId)}
						title="Switch the seeded fixture"
					>
						{m.tab}
					</button>
				{/each}
			</span>
		</div>
		<div class="scroll" data-right-panel={rightTab}>
			{#if !ready}
				<span></span>
			{:else if rightTab === 'inbox'}
				<Inbox route="/" bind:open={inboxOpen} />
			{:else}
				<div class="sections" id="dss-sections">
					<Callout icon="info-sign">Fictional fixture data (publishers news-a.example, news-b.example, sachet.ndma.gov.in). Nothing is polled; the proposal comes from the fixture, not a GET.</Callout>
					<div class="sec-block">
						<h3>Proposed — the link card to its one home</h3>
						<div class="sec-frame">
							<div class="sec-head"><span class="ttl">{meta.label}</span><span class="sub">OSINT report · {meta.verificationState} · credibility {meta.credibility}</span></div>
							<DecisionSupportSection row={sectionRow(SUBJECT)} dossier={null} />
						</div>
					</div>
					<div class="sec-block">
						<h3>No proposal on a closed event — Generate disabled with its reason</h3>
						<div class="sec-frame">
							<div class="sec-head"><span class="ttl">Procession (completed)</span><span class="sub">Event · completed</span></div>
							<DecisionSupportSection row={sectionRow(CLOSED_EVENT)} dossier={null} />
						</div>
					</div>
					<div class="sec-block">
						<h3>Promote</h3>
						<p class="hint">The Promote verb lives in the object's Actions tab; its confirmation dialog is hosted here (the section). Name an officer with the toggle above to try it — a confirm POSTs to whatever backend serves this page.</p>
					</div>
				</div>
			{/if}
		</div>
	</section>
</div>

<style>
	.harness {
		display: grid;
		grid-template-columns: minmax(400px, 432px) minmax(0, 1fr);
		height: 100%;
		min-height: 0;
		background: var(--v-canvas);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.col {
		display: flex;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
		border-right: 1px solid var(--v-line-1);
	}

	.col-head {
		display: flex;
		align-items: baseline;
		gap: 8px;
		padding: 10px 16px;
		border-bottom: 1px solid var(--v-line-1);
	}

	.col-head h2 {
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
	}

	.col-head .sub {
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.scroll {
		flex: 1 1 auto;
		min-height: 0;
		overflow: auto;
	}

	.dock-tabs {
		display: flex;
		align-items: center;
		gap: 2px;
		padding: 4px 8px 0;
		border-bottom: 1px solid var(--v-line-1);
	}

	.dt {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 8px 12px;
		border: 0;
		border-bottom: 2px solid transparent;
		background: none;
		font: inherit;
		font-size: var(--v-text-sm);
		color: var(--v-ink-2);
		cursor: pointer;
	}

	.dt.is-selected {
		color: var(--v-ink-1);
		border-bottom-color: var(--v-primary-text);
	}

	.bar {
		display: inline-flex;
		gap: 4px;
		margin-left: auto;
		padding-bottom: 4px;
	}

	.hb {
		padding: 3px 8px;
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-chip);
		background: none;
		font: inherit;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
		cursor: pointer;
		white-space: nowrap;
	}

	.hb.is-selected,
	.hb[data-on='1'] {
		color: var(--v-ink-1);
		border-color: var(--v-line-2);
		background: var(--v-surface-2);
	}

	.sections {
		display: flex;
		flex-direction: column;
		gap: 20px;
		padding: 16px;
	}

	.sec-block h3 {
		margin: 0 0 8px;
		font-size: var(--v-text-sm);
		font-weight: 600;
	}

	.sec-frame {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 12px 16px;
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-1);
	}

	.sec-head {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding-bottom: 8px;
		border-bottom: 1px solid var(--v-line-1);
	}

	.sec-head .ttl {
		font-size: var(--v-text-md);
		font-weight: 600;
	}

	.sec-head .sub {
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.hint {
		margin: 0;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}
</style>
