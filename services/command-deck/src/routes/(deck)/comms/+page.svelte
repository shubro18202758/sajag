<script lang="ts">
	/**
	 * /comms — Advisories (V3-SPEC §6.7; V3-P6A). The desk that drafts one fact for every audience in every language,
	 * recomposed under the V3 shell (rail + slim top bar, via the route's `+layout@.svelte` → CommsFrame):
	 *
	 *   EVENTS  (left)   the events an advisory can be written for, as cards (art, kind, title); the selected one is
	 *                    framed on the real map of its place at the head of the desk. Templates by kind sit below,
	 *                    folded.
	 *   DESK    (centre) the audience (Citizens · Zone officers · 108 control · Municipal), Regenerate — the ONE
	 *                    primary — and the three drafts side by side (EN · हिन्दी · मराठी), each with its own Copy;
	 *                    the facts the drafts were written from, folded under them.
	 *   SHEET   (right)  opened from the desk: this tab's draft log and the dispatch threads — moved off the desk by
	 *                    the colleague review. No audit or analysis tables live on this page.
	 *
	 * BEHAVIOUR IS UNCHANGED from the v2 desk; only markup and layout are new:
	 *
	 *   - "Drafted — not delivered" is stated ONCE, as the desk's status tag. Nothing is sent from here.
	 *   - The exercise marker stays in the DRAFT STRING and in what Copy puts on the clipboard: `advisory.ts` begins
	 *     every emulated draft with the exercise prefix, so a copied draft can never pass for a real road hold. On
	 *     screen the column renders that prefix as a quiet tag at the start of the text.
	 *   - Regenerate is the one primary button. A citizen draft for an operator-only kind is WITHHELD (never composed,
	 *     all-clear disabled): tactical police operations are not broadcast. An OSINT-sourced event is withheld from
	 *     citizens and 108 control the same way, fail-closed. The withholding is stated ONCE, on the selected event
	 *     (`comms-withheld-badge`); a withheld column keeps its node, never a draft, never an enabled Copy.
	 *   - Facts come from comms/facts.ts — the same derivation /citizen's public projection runs (closure plan, else
	 *     the adaptive advance closure with the oracle's own provenance). Dispatch threads cover every agency
	 *     including civic volunteers, read live from GET /api/v1/dispatches (read only).
	 *
	 * The shell carries what is page-owned through the same contract every operator page uses (commandBar: language,
	 * search, officer, exercise statement, inbox count; v3Bar: title, status line, the decisions the alerts list), and
	 * the page's own interrupts (SPEC §7.3): the inbox count stays (the inbox routes to the workspace's inbox deep
	 * link), and the city registry is polled while the page is open so the omnibar reads a live world. The page
	 * mounts its one Omnibar — /comms has no canvas, so an omnibar PICK opens on the workspace, where the Inspector
	 * and the map can show it.
	 */
	import { onDestroy, onMount, tick } from 'svelte';
	import type { Component } from 'svelte';
	import { goto } from '$app/navigation';
	import { ops } from '$lib/ops/store.svelte';
	import { SUPPORTED, kindLabel, localizeNumber, t } from '$lib/i18n/strings';
	import { citizenT } from '$lib/i18n/strings.citizen';
	import { tOps } from '$lib/i18n/strings.ops';
	import OperatorSignIn from '$lib/shell/OperatorSignIn.svelte';
	import { ensureLang } from '$lib/i18n/load';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { toasts } from '$lib/shell/toast.svelte';
	import { WORKSPACE_URL } from '$lib/shell/root-flip';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { registerProviders } from '$lib/workspace/providers';
	import { selectors, liveWorld } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { decisionUnits, unitEmulated, type Unit } from '$lib/decisions/units';
	import { provideUiLang } from '$lib/ui';
	import { istClock } from '$lib/primitives/time';
	import { fetchDispatches, type DispatchFeedState } from '$lib/comms/dispatch-feed';
	import {
		AUDIENCES,
		audienceLabel,
		composeAdvisoryTrilingual,
		composeAllClearTrilingual,
		holdSourceKey,
		templateForKind,
		type AdvisoryDraft,
		type AdvisoryFacts,
		type Audience,
	} from '$lib/comms/advisory';
	import { factsKey, resolveFacts } from '$lib/comms/facts';
	import { commsWithholding, osintLabel, osintMarkOf } from '$lib/comms/osint';
	import { PUBLIC_EVENT_KINDS, clockAtMs, isPublicKind } from '$lib/citizen/holds';
	import { wireInterrupts, inboxFromUnits } from '$lib/assistant/page-interrupts';
	import { dataFeeds, feedRows, worstStatus } from '$lib/decisions/wall/feeds';
	import '$lib/i18n/strings.citizen';
	import '$lib/i18n/packs';
	import '$lib/v3/packs.v3';
	import '$lib/v3/comms/packs.comms3';
	import Glyph from '$lib/v3/Glyph.svelte';
	import V3Tag from '$lib/v3/ui/V3Tag.svelte';
	import { v3Bar } from '$lib/v3/shell/v3-bar.svelte';
	import { artFor, splitLabel, unitKey } from '$lib/v3/home/model';
	import { decisionVM, plannedVM, roadLines } from '$lib/v3/home/view';
	import { objectHref } from '$lib/v3/object/model';
	import EventRow from '$lib/v3/comms/EventRow.svelte';
	import EventHeader from '$lib/v3/comms/EventHeader.svelte';
	import DraftColumn from '$lib/v3/comms/DraftColumn.svelte';
	import CommsSheet from '$lib/v3/comms/CommsSheet.svelte';
	import AudienceMark from '$lib/v3/comms/AudienceMark.svelte';
	import { factRows, rovingIndex, rowWithheld } from '$lib/v3/comms/model';

	registerProviders();
	provideUiLang(() => ops.lang);

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const C = (key: string, ...args: unknown[]) => citizenT(lang, key, ...args);

	/** Decision units waiting — the shell's inbox count (SPEC §7.3). */
	const units = $derived(selectors.decisionUnits());

	// ── Event pick ────────────────────────────────────────────────────────
	let selectedId = $state<string | null>(null);
	let events = $derived(ops.events.length ? ops.events : []);
	let selected = $derived(events.find((e) => e.eventId === selectedId) ?? null);

	// The desk must show what it is working on: adopt the first event
	// (and re-adopt when the selected one leaves the board).
	$effect(() => {
		if (events.length && !events.some((e) => e.eventId === selectedId)) {
			selectedId = events[0].eventId;
		}
	});

	function eventLabel(ev: (typeof events)[number]): string {
		const name = ev.name && ev.name !== ev.eventId ? ev.name : ev.eventId.slice(0, 8);
		const src = ev.source === 'offline-fixture' ? t(lang, 'opsSourceOffline') : t(lang, 'opsSourceLive');
		// An OSINT-sourced event says so wherever the desk lists it.
		const mark = osintMarkOf(ev);
		return `${kindLabel(lang, ev.eventKind)} · ${name} · ${mark ? osintLabel(mark, lang) : src}`;
	}

	const upFirst = (x: string) => (x ? x.charAt(0).toLocaleUpperCase() + x.slice(1) : x);

	/** One list row: art, kind line, title, one meta word — and whether the row will not be drafted for citizens (a hint). */
	const rows = $derived(
		events.map((ev) => {
			const name = ev.name && ev.name !== ev.eventId ? upFirst(splitLabel(ops.text(ev.name)).title) : ev.eventId.slice(0, 8);
			const mark = osintMarkOf(ev);
			return {
				id: ev.eventId,
				art: artFor(ev.eventKind),
				kind: kindLabel(lang, ev.eventKind),
				title: name,
				meta: mark ? osintLabel(mark, lang) : upFirst(ev.source === 'offline-fixture' ? t(lang, 'opsSourceOffline') : t(lang, 'opsSourceLive')),
				withheld: rowWithheld(ev, isPublicKind, mark),
			};
		}),
	);

	let listEl = $state<HTMLElement | null>(null);
	function onRowKey(e: KeyboardEvent, i: number) {
		const to = rovingIndex(e.key, i, rows.length);
		if (to === null) return;
		e.preventDefault();
		selectedId = rows[to].id;
		void tick().then(() => listEl?.querySelectorAll<HTMLElement>('[role="radio"]')[to]?.focus());
	}

	// ── Facts (resolved per event; same derivation as /citizen) ───────────
	// Re-resolved when the event's facts change and every 30 s (the live
	// adaptive advance closure moves with the situation band); a token
	// drops answers that arrive after a newer request.
	let facts = $state<AdvisoryFacts | null>(null);
	let factsTick = $state(0);
	let factsFor = '';
	let factsToken = 0;
	$effect(() => {
		const ev = selected;
		const tick = factsTick;
		if (!ev) {
			facts = null;
			factsFor = '';
			return;
		}
		const key = factsKey(ev);
		if (`${key}|${tick}` === factsFor) return;
		if (!factsFor.startsWith(`${key}|`)) facts = null;
		factsFor = `${key}|${tick}`;
		const token = ++factsToken;
		void resolveFacts(ev).then((f) => {
			if (token === factsToken) facts = f;
		});
	});

	/**
	 * The kind the drafts are written for: the oracle's raw kind once the
	 * facts resolved (an unknown kind is withheld), the board's until then.
	 */
	const draftKind = $derived(
		facts && selected && facts.eventId === selected.eventId ? facts.eventKind : (selected?.eventKind ?? ''),
	);

	/**
	 * An OSINT-sourced event (comms/osint.ts): withheld from citizens and 108,
	 * whatever its kind — the resolved facts' mark, the board row's until then.
	 */
	const osintMark = $derived(
		facts && selected && facts.eventId === selected.eventId ? (facts.osint ?? null) : osintMarkOf(selected),
	);
	const withholding = $derived(commsWithholding(osintMark, lang));

	// ── Advisory generation ───────────────────────────────────────────────
	let audience = $state<Audience>('citizens');
	const audienceWithheld = $derived(!!withholding && withholding.audiences.includes(audience));
	let drafts = $derived(facts ? composeAdvisoryTrilingual(facts, audience) : ([] as AdvisoryDraft[]));
	let generatedAt = $state(0);

	// ── Template library ──────────────────────────────────────────────────
	let templateKind = $state<string | null>(null);
	const templateKinds = [...PUBLIC_EVENT_KINDS];
	/**
	 * An operator-only kind (pursuit, crime): no citizen draft exists for it,
	 * so GENERATE steps back (ghost, disabled, said why) and the centre
	 * column shows the citizen TEMPLATES preview instead of empty drafts.
	 */
	const operatorOnly = $derived(!!selected && !isPublicKind(draftKind));
	const previewKind = $derived(templateKind ?? (isPublicKind(draftKind) ? draftKind : templateKinds[0]));

	// ── Draft log (this tab only; drafted, never delivered, by design) ────
	interface LogEntry {
		id: number;
		ts: number;
		texts: Array<{ lang: string; text: string }>;
	}
	let log = $state<LogEntry[]>([]);
	let logSeq = 0;

	// ── Dispatch threads (all agencies incl. civic volunteers) ────────────
	let feed = $state<DispatchFeedState>({
		dispatches: [],
		source: 'unavailable',
		note: null,
		lastUpdated: 0,
	});
	let threadScope = $state<'event' | 'all'>('event');
	let pollTimer: ReturnType<typeof setInterval> | null = null;

	// ── the side sheet (draft log · dispatch threads) ─────────────────────
	let sheet = $state<'log' | 'threads' | null>(null);
	let opener: HTMLElement | null = null;
	function openSheet(which: 'log' | 'threads', e?: Event) {
		if (sheet === which) {
			closeSheet();
			return;
		}
		if (!sheet && e?.currentTarget instanceof HTMLElement) opener = e.currentTarget;
		sheet = which;
	}
	function closeSheet() {
		sheet = null;
		const back = opener;
		opener = null;
		void tick().then(() => back?.focus());
	}
	function onWindowKey(e: KeyboardEvent) {
		if (e.key === 'Escape' && sheet && !e.defaultPrevented) {
			e.preventDefault();
			closeSheet();
		}
	}

	async function pollDispatches() {
		try {
			const dispatches = await fetchDispatches();
			feed = { dispatches, source: 'live', note: null, lastUpdated: Date.now() };
		} catch (err) {
			const notDeployed = err instanceof Error && err.name === 'ApiNotDeployed';
			feed = {
				dispatches: [],
				source: notDeployed ? 'not-deployed' : 'unavailable',
				note: err instanceof Error ? err.message : String(err),
				lastUpdated: feed.lastUpdated,
			};
		}
	}

	let factsTimer: ReturnType<typeof setInterval> | null = null;
	let clockTimer: ReturnType<typeof setInterval> | null = null;
	let now = $state(Date.now());
	let Omnibar = $state<Component | null>(null);

	onMount(() => {
		ops.start();
		liveWorld.graph(); // build the world once now — the omnibar reads it
		cityRegistry.start();
		void pollDispatches();
		pollTimer = setInterval(() => void pollDispatches(), 10_000);
		factsTimer = setInterval(() => (factsTick += 1), 30_000);
		clockTimer = setInterval(() => (now = Date.now()), 30_000);
		void import('$lib/workspace/components/omnibar/Omnibar.svelte').then((m) => (Omnibar = m.default as unknown as Component));
	});

	onDestroy(() => {
		cityRegistry.stop();
		ops.stop();
		if (pollTimer) clearInterval(pollTimer);
		if (factsTimer) clearInterval(factsTimer);
		if (clockTimer) clearInterval(clockTimer);
	});

	// ── the shell (plan R10/X12) and this page's one omnibar ──────────────
	$effect(() => {
		commandBar.lang = ops.lang;
		commandBar.onLangChange = (l: string) => (ops.lang = l);
		commandBar.onShare = null;
		commandBar.onSearch = (q?: string) => workspace.openOmnibar(q);
		wireInterrupts('/comms');
	});

	$effect(() => {
		inboxFromUnits(units);
	});

	// The alerts list follows the decisions waiting (the canonical units, as every V3 page counts them); the first
	// round of the stores is not announced as new.
	const v3Units = $derived.by((): Unit[] => {
		void cityRegistry.version;
		return decisionUnits(ops);
	});
	const mountedAt = Date.now();
	const firstRound = $derived(
		(ops.boardUpdated > 0 && ops.recommendationsUpdated > 0 && ops.dispatchesUpdated > 0 && ops.escortsDeployed !== null && cityRegistry.status !== 'idle') ||
			now - mountedAt > 10_000,
	);
	$effect(() => {
		v3Bar.title = L('v3_nav_advisories');
		v3Bar.sub = L('v3c_sub');
		v3Bar.active = 'advisories';
	});
	$effect(() => {
		const list = firstRound ? v3Units.map((u) => ({ key: unitKey(u), title: u.title, href: decisionVM(u, lang, now).href, emulated: unitEmulated(u) })) : null;
		v3Bar.decisions = list;
	});

	// An omnibar pick made on this desk has nothing to show it in (no canvas,
	// no inspector): open it on the workspace, where the Inspector and the map
	// live. Only a pick made WHILE this page is mounted navigates — a selection
	// carried in from elsewhere stays put; the guard keeps the navigation
	// one-shot (a goto never re-arms it).
	let pickArmed = false;
	let pickNavigating = false;
	$effect(() => {
		const urn = selection.current;
		const source = selection.source;
		if (!pickArmed) {
			pickArmed = true;
			return;
		}
		if (pickNavigating) return;
		if (source === 'omnibar' && urn) {
			pickNavigating = true;
			queueMicrotask(() => void goto(WORKSPACE_URL));
		}
	});

	$effect(() => {
		commandBar.officer = {
			value: ops.dutyOfficer,
			fromSession: ops.dutyOfficerFromSession,
			set: (v: string) => ops.setDutyOfficer(v),
		};
	});

	const commsFeeds = $derived.by(() =>
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
			feeds: dataFeeds(commsFeeds, lang),
			worst: worstStatus(commsFeeds),
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
								? t(lang, 'wall_exercise_simulated', f.segments)
								: t(lang, 'wall_exercise_mixed', Math.round((100 * f.synthetic) / Math.max(1, f.real + f.synthetic))),
					}
				: null;
	});

	$effect(() => {
		const city = ops.cityBand;
		commandBar.band = city ? (city.stale ? null : city.band) : ops.bandSourceKind === 'city-band' ? ops.band : null;
		commandBar.bandSource = city ? (city.stale ? ops.bandSource : null) : commandBar.band ? ops.bandSource : null;
		const at = ops.cityBand?.evaluatedAt ?? (ops.cityBandUpdated || null);
		commandBar.bandAgeSec = at && commandBar.band ? Math.max(0, (Date.now() - at) / 1000) : null;
	});

	function pushLog(texts: LogEntry['texts']) {
		log.unshift({ id: ++logSeq, ts: Date.now(), texts });
		log = log.slice(0, 40);
	}

	async function generate() {
		if (!selected || !drafts.length || audienceWithheld) return;
		// the log freezes the three texts: the HI and MR strings must be in first (FIX-E-PERF2)
		await Promise.all([ensureLang('hi'), ensureLang('mr')]);
		generatedAt = Date.now();
		pushLog(drafts.map((d) => ({ lang: d.lang, text: d.text })));
		toasts.push({
			kind: 'info',
			title: citizenT(lang, 'comms_drafted_badge'),
			body: `${kindLabel(lang, draftKind)} · ${audienceLabel(audience, lang)}`,
		});
	}

	async function draftAllClear() {
		// A citizen all-clear: never for an operator-only kind or an OSINT event.
		if (!selected || !isPublicKind(draftKind) || osintMark) return;
		// the log freezes the three texts: the HI and MR strings must be in first (FIX-E-PERF2)
		await Promise.all([ensureLang('hi'), ensureLang('mr')]);
		pushLog(composeAllClearTrilingual(draftKind, selected.emulated === true, osintMark));
	}

	function copyDraft(text: string) {
		// The exercise marker rides in the string: a copied draft can never
		// pass for a real road hold (SPEC §6.5).
		void navigator.clipboard?.writeText(text).catch(() => undefined);
		toasts.push({ kind: 'info', title: citizenT(lang, 'comms_copied') });
	}

	const eventDispatches = $derived(
		selected ? feed.dispatches.filter((d) => d.event_id === selected.eventId) : [],
	);
	const shownDispatches = $derived(
		threadScope === 'all' || !selected ? feed.dispatches.slice(0, 20) : eventDispatches,
	);
	const otherEventCount = $derived(feed.dispatches.length - eventDispatches.length);

	function statusWord(status: string): string {
		const key = `dispatch_status_${status}`;
		const word = citizenT(lang, key);
		return word === key ? status : word;
	}

	const langName = (code: string) => SUPPORTED.find((s) => s.code === code)?.label ?? code;

	// ── what the selected event shows at the head of the desk ─────────────
	const head = $derived(selected ? plannedVM(selected, lang, now) : null);
	const roads = $derived(roadLines());

	/** The facts the drafts were written from, as the disclosure prints them. */
	const usedFacts = $derived.by(() => {
		if (!facts || !isPublicKind(draftKind)) return [];
		const hold =
			facts.holdMinutes != null
				? `${t(lang, 'freezeMinutes', localizeNumber(facts.holdMinutes, lang, false))} · ${citizenT(lang, holdSourceKey(facts.holdSource))}`
				: citizenT(lang, facts.unavailable?.hold ? 'card_hold_unavailable' : 'card_hold_unknown');
		const alt = facts.alternate?.length
			? facts.alternate.join(' / ')
			: citizenT(lang, facts.unavailable?.alternate ? 'card_alt_unavailable' : 'card_alt_none');
		return factRows(facts, { kind: kindLabel(lang, facts.eventKind), hold, when: clockAtMs(facts.anchorMs, lang), alt });
	});
	const FACT_KEY: Record<string, string> = { kind: 'v3c_f_kind', road: 'v3c_f_road', hold: 'v3c_f_hold', when: 'v3c_f_when', alt: 'v3c_f_alt' };
</script>

<svelte:window onkeydown={onWindowKey} />

<svelte:head>
	<title>{t(lang, 'nav_module_advisories')} · Sajag</title>
</svelte:head>

{#if ops.signInRequired}
	<!-- F-10: gate on, nobody signed in — one sign-in card, no panel of refused reads -->
	<div class="signin" data-testid="comms-signin-required">
		<div class="signin-card">
			<h2>{tOps(lang, 'opsSigninTitle')}</h2>
			<p>{tOps(lang, 'commsSigninBody')}</p>
			<OperatorSignIn {lang} inline />
		</div>
	</div>
{:else}
	<div class="comms" data-screen="comms" data-v3="comms">
		<!-- EVENTS ──────────────────────────────────────────────────────────── -->
		<section class="events" aria-labelledby="comms-events-h">
			<h2 id="comms-events-h" class="h">
				{L('v3c_events')}
				{#if rows.length}<span class="count fig">{rows.length}</span>{/if}
			</h2>

			{#if events.length === 0}
				<div class="empty" data-testid="comms-empty">
					<img src="/illustrations/events/advisory.svg" alt="" width="120" height="120" />
					<p class="empty-t">{t(lang, 'opsNoEvents')}</p>
					<p class="empty-h">{t(lang, 'startDemo')}</p>
				</div>
			{:else}
				<div class="list" role="radiogroup" aria-label={L('v3c_events_aria')} bind:this={listEl}>
					{#each rows as r, i (r.id)}
						<EventRow
							art={r.art}
							kind={r.kind}
							title={r.title}
							meta={r.meta}
							selected={r.id === selectedId}
							withheld={r.withheld}
							withheldTip={L('v3c_row_withheld')}
							tabindex={r.id === selectedId ? 0 : -1}
							eventId={r.id}
							onpick={() => (selectedId = r.id)}
							onkeydown={(e) => onRowKey(e, i)}
						/>
					{/each}
				</div>
				<!-- the same choice as a native select (the desk's test hook and an assistive-tech fallback): out of sight, out of the tab order -->
				<select class="sr" tabindex="-1" aria-hidden="true" bind:value={selectedId} data-testid="comms-event-select">
					{#each events as ev (ev.eventId)}
						<option value={ev.eventId}>{eventLabel(ev)}</option>
					{/each}
				</select>

				<details class="fold">
					<summary>{C('comms_template_title')}</summary>
					<ul class="templates">
						{#each templateKinds as kind (kind)}
							<li>
								<button
									type="button"
									class={['tpl', (templateKind ?? draftKind) === kind && 'is-selected']}
									onclick={() => (templateKind = kind)}
									data-template-kind={kind}
								>
									<span class="tpl-name">{kindLabel(lang, kind)}</span>
								</button>
							</li>
						{/each}
					</ul>
					{#if templateKind ?? draftKind}
						<p class="tpl-preview" data-testid="comms-template-preview">
							{templateForKind(templateKind ?? draftKind, lang)}
						</p>
					{:else}
						<p class="tpl-preview">{C('comms_template_hint')}</p>
					{/if}
				</details>
			{/if}
		</section>

		<!-- DESK ────────────────────────────────────────────────────────────── -->
		<div class="desk">
			{#if selected && head}
				{@const ev = selected}
				<EventHeader
					overlay={head.thumb.overlay}
					mapAlt={L('v3c_map_alt', head.title)}
					noPlace={L('v3c_no_place')}
					art={head.art}
					kind={head.kindLine}
					title={head.title}
					{roads}
					openHref={objectHref(`event:${ev.eventId}`)}
					openLabel={L('v3c_open_event')}
				>
					{#snippet tags()}
						<!-- an open-source report carries its verification label (in the withholding badge), never a "live" word -->
						{#if !osintMark}
							<V3Tag tone={ev.source === 'offline-fixture' ? 'dashed' : 'neutral'} size="sm">
								{upFirst(ev.source === 'offline-fixture' ? t(lang, 'opsSourceOffline') : t(lang, 'opsSourceLive'))}
							</V3Tag>
						{/if}
						{#if ev.emulated}
							<!-- every draft of this event carries the same marker in its text -->
							<span data-testid="comms-emulated-badge" title={citizenT(lang, 'adv_emulated_prefix')}>
								<V3Tag tone="dashed" glyph="flask" size="sm">{citizenT(lang, 'citizen_emulated_badge')}</V3Tag>
							</span>
						{/if}
						{#if withholding}
							<!-- An OSINT-sourced event: withheld from citizens and 108, with its verification label. -->
							<span class="wh"><Glyph name="eyeoff" size={16} /><span class="withheld-note" data-testid="comms-withheld-badge" data-withheld-reason="osint" title={withholding.label}>{withholding.badge}</span></span>
						{:else if !isPublicKind(draftKind)}
							<!-- An operator-only kind: said, never composed for citizens. -->
							<span class="wh"><Glyph name="eyeoff" size={16} /><span class="withheld-note" data-testid="comms-withheld-badge" data-withheld-reason="operator-kind">{citizenT(lang, 'comms_withheld')}</span></span>
						{/if}
					{/snippet}
					{#snippet factsLine()}
						{#if facts && isPublicKind(draftKind)}
							<!-- Where the drafted hold length came from (or that a read failed). -->
							<p
								class="facts-line"
								data-testid="comms-facts"
								data-hold-source={facts.holdSource ?? (facts.unavailable?.hold ? 'unavailable' : 'none')}
							>
								{#if facts.holdMinutes != null}
									<span class="fig">{t(lang, 'freezeMinutes', localizeNumber(facts.holdMinutes, lang, false))}</span>
									· {citizenT(lang, holdSourceKey(facts.holdSource))}
								{:else}
									{citizenT(lang, facts.unavailable?.hold ? 'card_hold_unavailable' : 'card_hold_unknown')}
								{/if}
								{#if facts.unavailable?.alternate}
									· {citizenT(lang, 'card_alt_unavailable')}
								{/if}
							</p>
						{/if}
					{/snippet}
					{#snippet actions()}
					
						<button type="button" class={['sb', sheet === 'log' && 'is-pressed']} aria-pressed={sheet === 'log'} onclick={(e) => openSheet('log', e)} data-testid="comms-open-log">
							<Glyph name="history" size={18} />{C('comms_draft_log')}{#if log.length}<span class="n fig">{log.length}</span>{/if}
						</button>
						<button type="button" class={['sb', sheet === 'threads' && 'is-pressed']} aria-pressed={sheet === 'threads'} onclick={(e) => openSheet('threads', e)} data-testid="comms-open-threads">
							<Glyph name="list" size={18} />{C('comms_dispatch_threads')}{#if feed.dispatches.length}<span class="n fig">{feed.dispatches.length}</span>{/if}
						</button>
										{/snippet}
				</EventHeader>

				<div class="bar">
					<div class="seg" role="group" aria-label={C('comms_audience')}>
						{#each AUDIENCES as a (a)}
							<button
								type="button"
								class={['aud', audience === a && 'is-pressed']}
								onclick={() => (audience = a)}
								data-audience={a}
								aria-pressed={audience === a}
							>
								<AudienceMark audience={a} {lang} />{audienceLabel(a, lang)}
							</button>
						{/each}
					</div>
				</div>

				<div class="gen-row">
					<!-- Regenerate is the ONE primary. -->
					<button
						type="button"
						class={['btn', operatorOnly || audienceWithheld ? 'ghost' : 'primary']}
						onclick={generate}
						disabled={!facts || operatorOnly || audienceWithheld}
						title={audienceWithheld ? withholding?.badge : undefined}
					>
						<span data-testid="comms-generate" data-demoted={operatorOnly || audienceWithheld ? 'yes' : 'no'}>
							{generatedAt ? citizenT(lang, 'comms_regenerate') : citizenT(lang, 'comms_generate')}
						</span>
					</button>
					<button type="button" class="btn ghost" onclick={draftAllClear} disabled={!isPublicKind(draftKind) || !!osintMark} data-testid="comms-all-clear">
						{citizenT(lang, 'comms_all_clear')}
					</button>
					{#if generatedAt}
						<span class="gen-at fig" data-testid="comms-generated-at">{istClock(generatedAt)} IST</span>
					{/if}
					<!-- The desk's one statement of what these are: nothing is sent from here. -->
					<span class="status" data-testid="comms-drafted" title={citizenT(lang, 'comms_no_gateway')}>
						<V3Tag tone="ghost" glyph="info">{citizenT(lang, 'comms_drafted_badge')}</V3Tag>
					</span>
				</div>

				{#if operatorOnly}
					<!-- No citizen draft for an operator-only kind: the citizen templates,
						previewed above, and the three draft columns WITHHELD — each keeps
						only its language name (the badge on the event says why, once): no
						placeholder dash, no dead Copy button (audit E, S3). The
						[data-lang][data-withheld] nodes stay for the citizen smoke. -->
					<section class="tpl-centre" data-testid="comms-template-centre" data-kind={previewKind}>
						<h3>{citizenT(lang, 'comms_template_title')} · {kindLabel(lang, previewKind)}</h3>
						<div class="trilingual preview">
							{#each SUPPORTED as s (s.code)}
								<!-- data-template-lang, not data-lang: [data-lang] names the three DRAFT columns -->
								<article class="lang-col" data-template-lang={s.code}>
									<header><span class="lang-name" lang={s.code}>{s.label}</span></header>
									<p class="adv-text" lang={s.code}>{templateForKind(previewKind, s.code)}</p>
								</article>
							{/each}
						</div>
						<p class="preview-note">{citizenT(lang, 'comms_template_hint')}</p>
					</section>
					<div class="trilingual withheld" data-testid="comms-trilingual" data-ready={facts ? 'yes' : 'no'}>
						{#each SUPPORTED as s (s.code)}
							<article class="lang-col" data-lang={s.code} data-withheld="yes" data-facts="">
								<header><span class="lang-name">{s.label}</span></header>
								<p class="adv-text withheld" lang={s.code}></p>
							</article>
						{/each}
					</div>
				{:else}
					<!-- an OSINT-withheld audience: the badge states why ONCE; the three columns stay in the DOM, unshown -->
					<div class="trilingual" class:withheld={drafts.length > 0 && drafts.every((d) => d?.withheld && d.withheldReason === 'osint')} data-testid="comms-trilingual" data-ready={facts ? 'yes' : 'no'}>
						{#each SUPPORTED as s, i (s.code)}
							<DraftColumn
								code={s.code}
								label={s.label}
								draft={drafts[i]}
								copyLabel={citizenT(lang, 'comms_copy')}
								copyAria={L('v3c_copy_lang', s.label)}
								copiedLabel={L('v3c_copied_inline')}
								oncopy={copyDraft}
							/>
						{/each}
					</div>
					{#if drafts.length > 0 && drafts.every((d) => d?.withheld && d.withheldReason === 'osint')}
						<div class="pick" data-testid="comms-withheld-pick">
							<img src="/illustrations/events/advisory.svg" alt="" width="96" height="96" />
							<p>{L('v3c_withheld_pick')}</p>
						</div>
					{:else}
						<p class="no-gateway">{citizenT(lang, 'comms_no_gateway')}</p>
					{/if}
					{#if usedFacts.length}
						<details class="fold used" data-testid="comms-facts-used">
							<summary>{L('v3c_facts_used')}</summary>
							<dl>
								{#each usedFacts as f (f.key)}
									{#if f.value}
										<div><dt>{L(FACT_KEY[f.key])}</dt><dd>{f.value}</dd></div>
									{/if}
								{/each}
							</dl>
						</details>
					{/if}
				{/if}
			{:else if events.length === 0}
				<div class="empty big">
					<img src="/illustrations/events/advisory.svg" alt="" width="160" height="160" />
					<p class="empty-t">{t(lang, 'opsNoEvents')}</p>
					<p class="empty-h">{t(lang, 'startDemo')}</p>
				</div>
			{/if}
		</div>

		{#if sheet}
			<CommsSheet
				tab={sheet}
				ontab={(s) => (sheet = s)}
				onclose={closeSheet}
				{L}
				C={C}
				{log}
				{feed}
				scope={threadScope}
				onscope={(s) => (threadScope = s)}
				shown={shownDispatches}
				{otherEventCount}
				{statusWord}
				{langName}
			/>
		{/if}
	</div>

	{#if Omnibar}<Omnibar />{/if}
{/if}

<style>
	.comms {
		position: relative;
		display: grid;
		grid-template-columns: 300px minmax(0, 1fr);
		gap: 24px;
		height: 100%;
		min-height: 0;
		padding: var(--v3-gut) var(--v3-gut) 0;
		overflow: hidden;
	}

	/* at 1680 px and wider the desk holds its measure and centres */
	@media (min-width: 1680px) {
		.comms {
			grid-template-columns: 340px minmax(0, 1fr);
			max-width: 1760px;
			margin-inline: auto;
		}
	}

	/* a tablet: the events become a row above the desk */
	@media (max-width: 1280px) {
		.comms {
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: auto minmax(0, 1fr);
			gap: 16px;
		}

		.events {
			overflow: visible;
			padding-bottom: 0;
		}

		.list {
			flex-direction: row;
			overflow-x: auto;
			padding-bottom: 6px;
		}

		.list :global(.row) {
			flex: 0 0 280px;
		}

		.fold {
			display: none;
		}
	}

	.events,
	.desk {
		min-width: 0;
		min-height: 0;
		overflow-y: auto;
		padding-bottom: var(--v3-gut);
		scrollbar-width: thin;
		scrollbar-color: var(--v3-s4) transparent;
	}

	.desk {
		display: flex;
		flex-direction: column;
		gap: 18px;
	}

	/* nothing on the desk shrinks below its content (a card with overflow: hidden would, in a flex column) */
	.desk > :global(*) {
		flex: none;
	}

	.fig {
		font-variant-numeric: tabular-nums;
	}

	.h {
		display: flex;
		align-items: center;
		gap: 10px;
		margin: 0 0 14px;
		font-size: var(--v3-text-heading);
		font-weight: 640;
		line-height: var(--v3-lh-heading);
	}

	.count {
		padding: 1px 9px;
		border-radius: 11px;
		background: var(--v3-s3);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		padding: 0;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
		border: 0;
	}

	/* ── folded extras ─────────────────────────────────────────────────── */
	.fold {
		margin-top: 18px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}

	.fold summary {
		display: flex;
		align-items: center;
		min-height: var(--v3-ctl-lg);
		padding: 0 16px;
		color: var(--v3-t2);
		font-size: var(--v3-text-body);
		font-weight: 620;
		cursor: pointer;
	}

	.fold summary:hover {
		color: var(--v3-t1);
	}

	.fold summary:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: -2px;
		border-radius: var(--v3-radius-l);
	}

	.fold[open] summary {
		color: var(--v3-t1);
	}

	.templates {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0;
		padding: 0 10px 8px;
		list-style: none;
	}

	.tpl {
		display: flex;
		align-items: center;
		width: 100%;
		min-height: var(--v3-ctl);
		padding: 0 10px;
		border: 0;
		border-radius: var(--v3-radius-s);
		background: transparent;
		color: var(--v3-t2);
		font: inherit;
		font-size: var(--v3-text-meta);
		text-align: left;
		cursor: pointer;
	}

	.tpl:hover {
		background: var(--v3-s2);
		color: var(--v3-t1);
	}

	.tpl.is-selected {
		background: var(--v3-brand-veil) !important;
		box-shadow: none !important;
		color: var(--v3-t1);
	}

	.tpl:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: -2px;
	}

	.tpl-preview {
		margin: 0;
		padding: 10px 16px 14px;
		border-top: 1px solid var(--v3-line-1);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.used dl {
		display: grid;
		gap: 8px;
		margin: 0;
		padding: 4px 16px 16px;
	}

	.used dl > div {
		display: grid;
		grid-template-columns: 120px minmax(0, 1fr);
		gap: 12px;
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.used dt {
		color: var(--v3-t3);
	}

	.used dd {
		margin: 0;
		color: var(--v3-t1);
	}

	/* ── the desk ──────────────────────────────────────────────────────── */
	.wh {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--v3-t2);
	}

	.withheld-note {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 620;
		line-height: var(--v3-lh-meta);
	}

	.facts-line {
		margin: 0;
	}

	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 12px;
	}

	.seg {
		display: inline-flex;
		flex-wrap: wrap;
		gap: 2px;
		padding: 4px;
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
		box-shadow: inset 0 0 0 1px var(--v3-line-1);
	}

	.aud {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: var(--v3-ctl-lg);
		padding: 0 16px;
		border: 0;
		border-radius: var(--v3-radius-m);
		background: transparent;
		color: var(--v3-t2);
		font: inherit;
		font-size: var(--v3-text-body);
		font-weight: 600;
		cursor: pointer;
		transition: background var(--v3-dur-1) var(--v3-ease);
	}

	.aud:hover {
		color: var(--v3-t1);
	}

	.aud.is-pressed {
		background: var(--v3-s4) !important;
		box-shadow: none !important;
		color: var(--v3-t1) !important;
	}

	.aud:focus-visible,
	.sb:focus-visible,
	.btn:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.sb {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: var(--v3-ctl);
		padding: 0 12px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: transparent;
		color: var(--v3-t1);
		font: inherit;
		font-size: var(--v3-text-meta);
		font-weight: 600;
		cursor: pointer;
	}

	.sb:hover {
		background: var(--v3-s2);
	}

	.sb.is-pressed {
		background: var(--v3-s3) !important;
		box-shadow: none !important;
		color: var(--v3-t1) !important;
	}

	.n {
		padding: 0 8px;
		border-radius: 10px;
		background: var(--v3-s3);
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: 20px;
	}

	.gen-row {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 10px;
	}

	.btn {
		min-height: var(--v3-ctl-lg);
		padding: 0 20px;
		border: 1px solid transparent;
		border-radius: var(--v3-radius-m);
		font: inherit;
		font-size: var(--v3-text-body);
		font-weight: 650;
		cursor: pointer;
		transition:
			background var(--v3-dur-1) var(--v3-ease),
			opacity var(--v3-dur-1) var(--v3-ease);
	}

	.btn.primary {
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
	}

	.btn.primary:hover:not(:disabled) {
		background: var(--v3-primary-hover);
	}

	.btn.ghost {
		border-color: var(--v3-line-2);
		background: transparent;
		color: var(--v3-t1);
	}

	.btn.ghost:hover:not(:disabled) {
		background: var(--v3-s2);
	}

	.btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.gen-at {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.status {
		margin-left: auto;
	}

	.tpl-centre {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 18px 20px 20px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}

	.tpl-centre h3 {
		margin: 0;
		font-size: var(--v3-text-sub);
		font-weight: 640;
		line-height: var(--v3-lh-sub);
	}

	/* withheld columns (operator-only kind, or an OSINT-withheld audience) render no empty bordered boxes: the
	   notice is stated once, on the badge (audit E-ASSIST R2) */
	.trilingual.withheld {
		display: none;
	}

	.trilingual {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 16px;
	}

	@media (max-width: 1280px) {
		.trilingual {
			grid-template-columns: minmax(0, 1fr);
		}
	}

	.trilingual.preview .lang-col {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-width: 0;
		padding: 14px 16px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.lang-name {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 650;
	}

	.adv-text {
		margin: 0;
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
		overflow-wrap: anywhere;
	}

	.adv-text:lang(hi),
	.adv-text:lang(mr) {
		line-height: 1.7;
	}

	.preview-note {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.no-gateway {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.pick {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		padding: 28px 16px;
		border: 1px dashed var(--v3-line-2);
		border-radius: var(--v3-radius-l);
		color: var(--v3-t2);
		text-align: center;
	}

	.pick p {
		margin: 0;
	}

	/* ── empty and sign-in ─────────────────────────────────────────────── */
	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		padding: 24px 12px;
		text-align: center;
	}

	.empty.big {
		margin: auto;
		padding: 64px 0;
	}

	.empty-t {
		margin: 0;
		font-size: var(--v3-text-sub);
		font-weight: 620;
	}

	.empty-h {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.signin {
		display: grid;
		place-items: center;
		height: 100%;
		padding: 16px;
	}

	.signin-card {
		display: flex;
		flex-direction: column;
		gap: 12px;
		width: min(440px, calc(100vw - 32px));
		padding: 20px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}

	.signin-card h2 {
		margin: 0;
		font-size: var(--v3-text-sub);
	}

	.signin-card p {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}
</style>
