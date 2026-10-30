<script lang="ts">
	/**
	 * /chat — the Assistant page (SPEC §6.4; UI-S6B).
	 *
	 * Two columns at 1440 px and wider (the AssistantPanel's page variant):
	 * the conversation at a 760 px measure with the input docked at the
	 * bottom, and a context column with the selection, the citations and the
	 * link cards to proposals' homes. Below 1440 px the context column
	 * becomes a drawer. Every label reaches at least 4.5:1 (the token gate).
	 *
	 * The panel LINKS to decisions and never decides: a map proposal opens
	 * the map, a decision opens its one home — there is no Apply and no
	 * Approve anywhere on this page.
	 *
	 * The navbar carries what is page-owned (plan R10/X12) and the page's own
	 * interrupts (SPEC §7.3 — the audit's S2): the live strip and the inbox
	 * count stay (the inbox routes to the workspace's inbox deep link), and the
	 * city registry is polled while the page is open so the omnibar reads a
	 * live world. /chat has no canvas, so the map commands list disabled with
	 * their reason.
	 */
	import { onDestroy, onMount } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { registerProviders } from '$lib/workspace/providers';
	import { selectors, liveWorld } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import Omnibar from '$lib/workspace/components/omnibar/Omnibar.svelte';
	import AssistantPanel from '$lib/assistant/AssistantPanel.svelte';
	import { wireInterrupts, inboxFromUnits } from '$lib/assistant/page-interrupts';
	import { dataFeeds, feedRows, worstStatus } from '$lib/decisions/wall/feeds';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import SignInWall from '$lib/shell/SignInWall.svelte';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.assistant';

	registerProviders();

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	/** Decision units waiting — the navbar's inbox count (SPEC §7.3). */
	const units = $derived(selectors.decisionUnits());

	/** The labelled sample state (?sample=1): composed locally, no model called. */
	let sample = $state(false);

	onMount(() => {
		ops.start();
		liveWorld.graph(); // build the world once now — the omnibar reads it
		cityRegistry.start();
		sample = new URLSearchParams(location.search).get('sample') === '1';
	});

	onDestroy(() => {
		cityRegistry.stop();
		ops.stop();
	});

	// ── the navbar (plan R10/X12) ───────────────────────────────────────────
	$effect(() => {
		commandBar.lang = ops.lang;
		commandBar.onLangChange = (l: string) => (ops.lang = l);
		commandBar.onShare = null;
		commandBar.onSearch = (q?: string) => workspace.openOmnibar(q);
		wireInterrupts('/chat');
	});

	$effect(() => {
		inboxFromUnits(units);
	});

	$effect(() => {
		commandBar.officer = {
			value: ops.dutyOfficer,
			fromSession: ops.dutyOfficerFromSession,
			set: (v: string) => ops.setDutyOfficer(v),
		};
	});

	/** The Data popover's rows, from what this page actually reads (no canvas feeds). */
	const chatFeeds = $derived.by(() =>
		feedRows(
			{
				now: Date.now(),
				// F-04: this page reads no registry, city feed or cameras — "Not read here", never "waiting"
				registry: null,
				cityFeed: null,
				traffic: {
					label: ops.trafficFeed?.label ?? null,
					note: ops.trafficFeedNote,
					segments: ops.trafficFeed?.segments ?? null,
					dataAgeSec: ops.trafficFeed?.dataAgeSec ?? null,
				},
				cameras: null,
				board: { status: ops.boardStatus, updated: ops.boardUpdated, open: ops.events.length },
				model: {
					brain: ops.brain
						? { reachable: ops.brain.reachable, decider: { state: ops.brain.decider.state, p95Ms: ops.brain.decider.p95Ms }, checkedAt: ops.brain.checkedAt }
						: null,
					tier: ops.brain?.degradationTier ?? null,
				},
				emulator: { online: ops.emulator.online, lastChecked: ops.emulator.lastChecked, tapes: ops.emulatorLibrary.length },
			},
			lang,
		),
	);

	$effect(() => {
		const b = ops.brain;
		const latch = b?.decider.latch ?? null;
		commandBar.dataStatus = {
			decider: b ? (b.reachable ? b.decider.state : 'unreachable') : 'unknown',
			tier: b?.degradationTier ?? '',
			p95: b?.decider.p95Ms != null ? b.decider.p95Ms / 1000 : null,
			novelty: latch === 'armed' || latch === 'tripped',
			feeds: dataFeeds(chatFeeds, lang),
			worst: worstStatus(chatFeeds),
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

	/** The navbar's band: the city band when its engine answers, else the store's. */
	$effect(() => {
		const city = ops.cityBand;
		commandBar.band = city ? (city.stale ? null : city.band) : ops.bandSourceKind === 'city-band' ? ops.band : null;
		commandBar.bandSource = city ? (city.stale ? ops.bandSource : null) : commandBar.band ? ops.bandSource : null;
		const at = ops.cityBand?.evaluatedAt ?? (ops.cityBandUpdated || null);
		commandBar.bandAgeSec = at && commandBar.band ? Math.max(0, (Date.now() - at) / 1000) : null;
	});
</script>

<svelte:head>
	<title>{t(lang, 'asst_page_title')} · Sajag</title>
</svelte:head>

{#if ops.signInRequired}
	<!-- F-10: gate on, nobody signed in — one sign-in card, no panel of refused reads -->
	<SignInWall title={tOps(lang, 'opsSigninTitle')} body={tOps(lang, 'chatSigninBody')} {lang} testid="chat-signin-required" />
{:else}
	<div class="chat-page" data-screen="chat">
		<header class="head">
			<h1>{t(lang, 'asst_page_title')}</h1>
			<p>{t(lang, 'asst_page_sub')}</p>
		</header>
		<AssistantPanel variant="page" {sample} />
	</div>

	<Omnibar />
{/if}

<style>
	.chat-page {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: var(--v-gap-panel);
		padding: var(--v-pad-panel);
	}

	/* The header sits on the panel's one centred grid (≈760 + 360): the
	 * title and subtitle in the conversation's column, never off-centre.
	 * Below 1440 px the panel's grid collapses to one column — the header
	 * collapses with it, or the title sits at the old column's x while the
	 * conversation starts at the page edge (audit E, S3 at 1366). */
	.head {
		display: grid;
		grid-template-columns: minmax(0, 760px) 360px;
		justify-content: center;
		gap: var(--v-gap-panel);
		width: 100%;
	}

	.head h1 {
		grid-column: 1;
		margin: 0;
		font-size: var(--v-text-lg);
	}

	.head p {
		grid-column: 1;
		margin: var(--v-space-1) 0 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	@media (max-width: 1439px) {
		.head {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
