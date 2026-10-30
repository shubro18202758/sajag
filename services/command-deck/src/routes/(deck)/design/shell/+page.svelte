<script lang="ts">
	/**
	 * /design/shell — the UI-S1B harness (plan R18, X16): a dev-only page, not
	 * linked anywhere, that supplies EVERY commandBar field with fictional
	 * data, so the full navbar and the LiveStrip can be seen and screenshotted
	 * before the pages that own those fields are rebuilt (UI-S5B /ops, UI-S6A
	 * / and /gods-eye, UI-S6B /chat and /comms). UI-S7B deletes it.
	 *
	 * Fictional data only: the mark is a masked placeholder (MH01XX•••7), the
	 * officer is whatever you type, the posture and the feeds are made up, and
	 * the soonest decision's countdown is held at 0:47 unless "Run the clock"
	 * is on. Nothing here reads or writes a backend.
	 *
	 * URL switches (for screenshots and the smokes): `?share=1` supplies the
	 * legacy Share as well, `?interrupts=1` turns the interrupts on, and
	 * `?squeeze=1` adds the rebuilt primitives in squeezed hosts (a fixed-height
	 * rail of two panels, like the cockpit's left rail, and a fixed-height
	 * audit scroller, like the trace console): nothing may spill over its
	 * neighbour or be squeezed under its own text (design-smoke §13c). Ctrl K
	 * opens the harness's stand-in omnibar, as the page's own omnibar would.
	 */
	import { onMount } from 'svelte';
	import type { Band } from '$lib/design/tokens';
	import FeedItem from '$lib/primitives/FeedItem.svelte';
	import Panel from '$lib/primitives/Panel.svelte';
	import { commandBar, type DataStatus, type FeedStatus, type LiveStripFeed } from '$lib/shell/command-bar.svelte';
	import { operatorSession } from '$lib/shell/session.svelte';
	import { toasts } from '$lib/shell/toast.svelte';
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import Dialog from '$lib/ui/Dialog.svelte';
	import Section from '$lib/ui/Section.svelte';
	import SegmentedControl from '$lib/ui/SegmentedControl.svelte';
	import Switch from '$lib/ui/Switch.svelte';
	import Kbd from '$lib/ui/Kbd.svelte';

	// ── what the harness supplies ────────────────────────────────────────
	let lang = $state('en');
	let officerName = $state('');
	let band = $state<Band | 'none'>('GREEN');
	let worst = $state<FeedStatus>('ok');
	let supply = $state({ officer: true, data: true, exercise: true, live: true, inbox: true, share: false, search: true });
	let runClock = $state(false);
	let interrupts = $state(false);
	let omnibarOpen = $state(false);
	let lastAction = $state<string | null>(null);
	let squeeze = $state(false);

	onMount(() => {
		const p = new URL(location.href).searchParams;
		if (p.get('share') === '1') supply.share = true;
		if (p.get('interrupts') === '1') interrupts = true;
		if (p.get('squeeze') === '1') squeeze = true;
	});

	/** Ctrl K / ⌘K: the stand-in omnibar, as the page's own omnibar binds it (the shell binds none). */
	function onKey(e: KeyboardEvent) {
		if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'k' && supply.search) {
			e.preventDefault();
			omnibarOpen = true;
		}
	}

	const T0 = Date.now();
	let tick = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (tick = Date.now()), 1000);
		return () => clearInterval(id);
	});

	/** The soonest decision expires 47 s from now, held there unless the clock runs. */
	const deadline = $derived(runClock ? T0 + 47_000 : tick + 47_000);

	const dataStatus = $derived<DataStatus>({
		decider: worst === 'down' ? 'unreachable' : 'loaded',
		tier: worst === 'ok' ? 'FULL' : 'TACTICAL_FALLBACK',
		p95: 2.3,
		novelty: true,
		feeds: [
			{ name: 'Traffic feed', status: 'ok', label: '38 of 49 roads, simulated' },
			{ name: 'Cameras', status: worst === 'degraded' ? 'degraded' : 'ok', label: '28 emulated' },
			{ name: 'Corridor events', status: 'ok', label: '3 open' },
			{ name: 'Scenario emulator', status: worst === 'down' ? 'down' : 'ok', label: 'living city' },
			{ name: 'Signal-plan writer', status: 'ok', label: 'off by policy' }
		],
		worst
	});

	const live = $derived<LiveStripFeed>({
		movement: {
			label: 'VVIP movement · Z',
			speedKmh: 38,
			nextJunction: 'Hindmata',
			nextInSec: 95,
			etaMs: T0 + 11 * 60_000,
			onOpen: () => (lastAction = 'Movement card requested')
		},
		pursuits: [
			{
				plateMasked: 'MH01XX•••7',
				lastReadAgoSec: 120 + Math.floor((tick - T0) / 1000),
				heading: 'north-east',
				onSelect: () => (lastAction = 'Pursued vehicle selected')
			}
		],
		soonest: {
			title: 'Escort proposal: hold the convoy short of Hindmata',
			deadlineMs: deadline,
			onReview: () => (lastAction = 'Escort proposal review requested')
		},
		interrupts: interrupts
			? [
					{ kind: 'band', band: 'RED', text: 'Band red during the movement', onOpen: () => (lastAction = 'Band history requested') },
					{ kind: 'feed-loss', text: 'Camera feed lost' }
				]
			: []
	});

	$effect(() => {
		commandBar.lang = lang;
		commandBar.onLangChange = (l: string) => (lang = l);
		commandBar.band = band === 'none' ? null : band;
		commandBar.bandSource = band === 'none' ? null : 'city band · SIMULATED FEED';
		commandBar.bandAgeSec = band === 'none' ? null : 12;
		// as a page adopts the session: with the operator gate on, the officer is
		// the signed-in one (locked); off, whatever is typed
		commandBar.officer = !supply.officer
			? null
			: operatorSession.gate === true
				? { value: operatorSession.officer ?? '', fromSession: !!operatorSession.officer, set: () => {} }
				: { value: officerName, fromSession: false, set: (v: string) => (officerName = v) };
		commandBar.dataStatus = supply.data ? dataStatus : null;
		commandBar.exercise = supply.exercise
			? {
					label: 'simulated',
					text: 'Cameras, sightings and decisions come from the scenario emulator; traffic is a simulated feed.'
				}
			: null;
		commandBar.live = supply.live ? live : null;
		commandBar.onInbox = supply.inbox ? () => (lastAction = 'Inbox requested') : null;
		commandBar.inboxCount = supply.inbox ? 2 : 0;
		commandBar.inboxIntent = supply.inbox ? 'warning' : 'none';
		commandBar.onShare = supply.share ? () => toasts.push({ kind: 'act', title: 'Link copied', body: 'marks stay masked' }) : null;
		commandBar.onSearch = supply.search ? () => (omnibarOpen = true) : null;
	});

	/** Fictional audit rows for the squeezed scroller: long enough to wrap to two or three lines. */
	const SQUEEZE_ROWS = [
		{ actor: 'Insp. Fixture (fictional)', kind: 'human', level: 'decision', text: 'Approved the escort hold short of Hindmata for the fictional movement; the convoy waits 90 s before the junction clears' },
		{ actor: 'Rules engine', kind: 'machine', level: 'decision', text: 'Recommended a review for MH01XX•••7 at a fictional camera; evidence only, no fine is ever filed for a reported-stolen vehicle' },
		{ actor: 'Sajag AI', kind: 'machine', level: 'model', text: 'Proposed a hold at the next junction because the band turned amber on the fictional corridor; an officer decides' },
		{ actor: 'Scenario emulator', kind: 'system', level: 'info', text: 'Closed the fictional event after its walk ended; the emulator injects causes only and never decides' },
		{ actor: 'Insp. Fixture (fictional)', kind: 'human', level: 'decision', text: 'Deferred the corridor request for the fictional ambulance window until the convoy has passed the junction' },
		{ actor: 'Rules engine', kind: 'machine', level: 'band', text: 'Band changed from green to amber on the fictional corridor after three slow readings in a row on the approach' }
	] as const;
	const FORM_ROWS = Array.from({ length: 12 }, (_, i) => i + 1);
	const RUNGS = Array.from({ length: 6 }, (_, i) => i + 1);

	const FIELDS = [
		['officer', 'Duty officer (officer)'],
		['data', 'Data and services (dataStatus)'],
		['exercise', 'Exercise data (exercise)'],
		['live', 'Live operations (live)'],
		['inbox', 'Inbox (onInbox, inboxCount 2, warning)'],
		['search', 'Omnibar (onSearch)'],
		['share', 'Legacy Share (onShare)']
	] as const;
</script>

<svelte:head><title>Shell harness · Sajag</title></svelte:head>
<svelte:window onkeydown={onKey} />

<div class="page" data-design="shell-harness">
	<header class="head">
		<div>
			<h1>Application shell</h1>
			<p class="sub">Every commandBar field supplied with fictional data</p>
		</div>
		<span class="hint">Shortcuts <Kbd keys={['?']} /></span>
	</header>

	<div class="grid">
		<Section title="Fields the page supplies" variant="card">
			<div class="pad">
				{#each FIELDS as [key, label] (key)}
					<Switch bind:checked={supply[key]} label={label} data-field={key} />
				{/each}
			</div>
		</Section>

		<Section title="State" variant="card">
			<div class="pad">
				<div class="field">
					<span class="cap">Band</span>
					<SegmentedControl
						small
						bind:value={band}
						options={[
							{ value: 'none', label: 'None' },
							{ value: 'GREEN', label: 'Green' },
							{ value: 'AMBER', label: 'Amber' },
							{ value: 'RED', label: 'Red' },
							{ value: 'BLACK', label: 'Black' }
						]}
					/>
				</div>
				<div class="field">
					<span class="cap">Worst feed</span>
					<SegmentedControl
						small
						bind:value={worst}
						options={[
							{ value: 'ok', label: 'Answering' },
							{ value: 'degraded', label: 'Degraded' },
							{ value: 'down', label: 'Down' }
						]}
					/>
				</div>
				<Switch bind:checked={interrupts} label="Interrupts: band red, feed lost" />
				<Switch bind:checked={runClock} label="Run the countdown" />
				<div class="row">
					<Button small onclick={() => toasts.push({ kind: 'act', title: 'Decision approved', body: 'fictional' })}>Outcome toast</Button>
					<Button small onclick={() => toasts.push({ kind: 'info', title: 'Draft copied' })}>Info toast</Button>
				</div>
			</div>
		</Section>

		<Section title="Last action" variant="card">
			<div class="pad">
				<p class="last" data-design="last-action">{lastAction ?? 'Nothing yet: use the strip, the Inbox or Review'}</p>
				<p class="muted">Named officer: <b data-design="officer-value">{officerName || 'none'}</b></p>
			</div>
		</Section>
	</div>

	{#if squeeze}
		<Section title="Primitives in squeezed hosts" variant="card" data-design="squeeze">
			<div class="pad sq-wrap">
				<!-- a fixed-height flex column of two panels, like the cockpit's left rail -->
				<div class="sq-rail" data-design="squeeze-rail">
					<Panel variant="glass" title="Scrolling panel" sub="A tall form: its body scrolls inside the panel" scroll>
						{#each FORM_ROWS as n (n)}<p class="sq-line">Fictional form row {n}</p>{/each}
						<Button small>Plan corridor</Button>
					</Panel>
					<Panel variant="glass" title="Clipped panel">
						{#each RUNGS as n (n)}<p class="sq-line">Fictional rung {n}</p>{/each}
					</Panel>
				</div>
				<!-- a fixed-height flex-column scroller, like the trace console and the dossier narrative -->
				<div class="sq-feed" data-design="squeeze-feed">
					{#each SQUEEZE_ROWS as r, i (i)}
						<FeedItem ts={T0 - i * 60_000} actor={r.actor} actorKind={r.kind} level={r.level} text={r.text} />
					{/each}
				</div>
			</div>
		</Section>
	{/if}

	<Callout icon="lab-test" title="Fictional data">
		The mark MH01XX•••7, the officer, the posture and the feeds are made up for this page; nothing reads or writes a
		backend.
	</Callout>

	<Dialog bind:open={omnibarOpen} title="Omnibar" icon="search" width={600}>
		<p class="muted">The page's omnibar opens here (UI-S2 mounts it; this harness only shows the call).</p>
	</Dialog>
</div>

<style>
	.page {
		display: flex;
		flex-direction: column;
		gap: 16px;
		max-width: 1200px;
		padding: 24px;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
		padding-bottom: 12px;
		border-bottom: 1px solid var(--v-line-2);
	}

	h1 {
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: 20px;
	}

	.hint {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.sub {
		margin: 4px 0 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
		gap: 16px;
	}

	.pad {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 12px 16px 16px;
	}

	.field {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.cap {
		width: 80px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.row {
		display: flex;
		gap: 8px;
	}

	.last {
		margin: 0;
		font-size: var(--v-text-base);
	}

	.muted {
		margin: 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.sq-wrap {
		flex-direction: row;
		flex-wrap: wrap;
		align-items: flex-start;
		gap: 16px;
	}

	/* the cockpit's left rail: a fixed height, the panels shrink into it */
	.sq-rail {
		display: flex;
		flex-direction: column;
		gap: 8px;
		width: 300px;
		height: 300px;
		overflow-y: auto;
	}

	/* the trace console's scroller: a fixed height, the rows never shrink */
	.sq-feed {
		display: flex;
		flex-direction: column;
		gap: 4px;
		width: 340px;
		max-height: 180px;
		overflow-y: auto;
	}

	.sq-line {
		margin: 0;
		line-height: 24px;
	}
</style>
