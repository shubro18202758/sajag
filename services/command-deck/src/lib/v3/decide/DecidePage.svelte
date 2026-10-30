<script lang="ts">
	/**
	 * /decide and /decide/<kind>:<id> — V3 Decide (V3-SPEC §6.2, §10 P2). The one-card flow:
	 *
	 *   queue    DecideQueue — every decision unit, soonest deadline first (decisionUnits(), the canonical
	 *            list every surface counts), then what this console just closed;
	 *   map      the real map of the decision's place (MapThumb: graded OSM tiles + the overlay Home draws,
	 *            no Cesium viewer), framed in the part the sheet leaves free;
	 *   sheet    DecisionSheet for a waiting unit; OutcomeState once it is decided here, ran out (plan kept)
	 *            or stopped waiting elsewhere — with "Next decision →".
	 *
	 * Opens on the deep link's unit when there is one, else the soonest deadline (P6). Selecting a unit swaps
	 * the URL in place (shallow routing): the page never remounts, the pollers never restart.
	 *
	 * Keyboard (§7.1): J / K next / previous waiting unit, 1–4 choose a response option, Enter FOCUSES the
	 * primary button (never presses it), R opens the reason. No single key approves.
	 *
	 * Data: the deck's existing stores — the ops store (polled as on Home), the city registry, decision
	 * units, the writers' change rows, the dss store's one GET per proposal — and the AI services ($lib/ai:
	 * forecast, hydro, twin), whose proposals queue under "AI proposals" and open AiSheet; their decisions go to
	 * the decision record (POST /api/v1/ai-proposals/decision). Every mark goes through ops.plate (masked until a
	 * duty officer is named).
	 */
	import { onDestroy, onMount, tick, untrack } from 'svelte';
	import type { Component } from 'svelte';
	import { replaceState } from '$app/navigation';
	import { ops } from '$lib/ops/store.svelte';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import OperatorSignIn from '$lib/shell/OperatorSignIn.svelte';
	import { registerProviders } from '$lib/workspace/providers';
	import { selectors } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { UNIT_KINDS, decisionUnits, dssOf, unitEmulated, type Unit } from '$lib/decisions/units';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.wall';
	import { provideUiLang } from '$lib/ui';
	import '../packs.v3';
	import { v3Bar } from '../shell/v3-bar.svelte';
	import MapThumb from '../map/MapThumb.svelte';
	import { mapStyle } from '../map/map-style.svelte';
	import type { ThumbOverlay } from '../map/overlay';
	import Glyph from '../Glyph.svelte';
	import { decisionVM, roadLines, type DecisionVM } from '../home/view';
	import DecideQueue, { type QueueItem } from './DecideQueue.svelte';
	import DecisionSheet from './DecisionSheet.svelte';
	import OutcomeState from './OutcomeState.svelte';
	import './packs.decide';
	import { decideHref, keyIntent, keyOf, parseDeepLink, stepKey, whenOf } from './model';
	import { decideSession } from './session.svelte';
	import AiSheet from './AiSheet.svelte';
	import type { AiQueueItem } from './DecideQueue.svelte';
	import { ai } from '$lib/ai/ai.svelte';
	import '$lib/ai/packs.ai';
	import { replayProposals, type AiCard } from '$lib/ai/model';
	import { provList } from '$lib/ai/labels';
	import { cardArt, cardKindKey, cardOverlay, cardPlace, cardTitle, cardWhen } from '$lib/ai/view';
	import type { LonLat } from '../map/mercator';

	let { param = null }: { param?: string | null } = $props();

	provideUiLang(() => ops.lang);
	const lang = $derived(ops.lang);
	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);

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

	// ── the units (canonical: decisionUnits()) ─────────────────────────────
	const units = $derived.by((): Unit[] => {
		void cityRegistry.version;
		return decisionUnits(ops);
	});
	const liveKeys = $derived(new Set(units.map(keyOf)));

	// ── the AI proposals (forecast, waterlogging, signal timing) ───────────
	const aiKey = (c: AiCard) => `ai:${c.id}`;
	const aiCards = $derived(ai.cards);
	/** Every AI card this page has shown (a decided one keeps its sheet and its outcome). */
	let seenAi = $state<Record<string, AiCard>>({});
	$effect(() => {
		const list = aiCards;
		untrack(() => {
			let changed = false;
			const next = { ...seenAi };
			for (const c of list) {
				if (next[aiKey(c)] !== c) {
					next[aiKey(c)] = c;
					changed = true;
				}
			}
			if (changed) seenAi = next;
		});
	});
	const aiItems = $derived.by((): AiQueueItem[] => {
		const out: AiQueueItem[] = [];
		const live = new Set(aiCards.map(aiKey));
		const row = (c: AiCard, state: AiQueueItem['state']): AiQueueItem => ({
			key: aiKey(c),
			kindLine: c.road && c.source === 'hydro' ? `${L(cardKindKey(c))} · ${c.road}` : L(cardKindKey(c)),
			title: cardTitle(c, lang, L),
			art: cardArt(c),
			when: state === 'done' ? L('ai_q_approved') : state === 'rejected' ? L('ai_q_rejected') : cardWhen(c, L),
			state,
			provs: provList(c.labels),
			exercise: c.exercise,
		});
		for (const c of aiCards) out.push(row(c, 'waiting'));
		for (const [k, c] of Object.entries(seenAi)) {
			if (live.has(k)) continue;
			const d = ai.decisions[c.id];
			if (d) out.push(row(c, d.decision === 'approve' ? 'done' : 'rejected'));
		}
		return out;
	});
	const aiNote = $derived.by(() => {
		if (ai.exercise && ai.replay && !aiCards.length && !replayProposals(ai.replay).length) return L('ai_d_exercise_none');
		const down = (['forecast', 'hydro', 'twin'] as const).filter((n) => ai.feeds[n].status === 'down' || ai.feeds[n].status === 'not-deployed');
		if (!down.length || aiCards.length) return null;
		return down.map((n) => L('ai_d_feed_down', L(`ai_src_${n}`))).join(' · ');
	});
	/** This console's tally: the units decided here, and the AI proposals decided here. */
	const tally = $derived.by(() => {
		const here = Object.values(ai.decidedHere);
		return { ...decideSession.tally, approved: decideSession.tally.approved + here.filter((d) => d === 'approve').length, rejected: decideSession.tally.rejected + here.filter((d) => d === 'reject').length };
	});
	function setExercise(on: boolean) {
		ai.exercise = on;
		if (on) void ai.loadReplay();
	}

	/** Every unit this page has shown, as last seen (the sheet's header once it leaves the queue). */
	let seen = $state<Record<string, Unit>>({});
	$effect(() => {
		const list = units;
		untrack(() => {
			let changed = false;
			const next = { ...seen };
			for (const u of list) {
				if (next[keyOf(u)] !== u) {
					next[keyOf(u)] = u;
					changed = true;
				}
			}
			if (changed) seen = next;
		});
	});

	// a time-boxed proposal that runs out unanswered while it is shown here keeps the current plan
	$effect(() => {
		const at = now;
		untrack(() => {
			for (const u of Object.values(seen)) {
				if (!UNIT_KINDS[u.kind]?.timeBoxed || u.deadline == null || u.deadline > at) continue;
				const k = keyOf(u);
				if (decideSession.outcomes[k]?.ok) continue;
				if (u.kind === 'escort-proposal' && ops.escortAnswered((u.data as { proposal: { approvalId: string } }).proposal.approvalId)) continue;
				decideSession.markExpired(k, u, at);
			}
		});
	});

	// ── selection: the deep link's unit, else the soonest ─────────────────
	// the deep link is read once, on mount: later selections swap the URL in place (shallow), never the prop
	const deep = untrack(() => parseDeepLink(param));
	let selected = $state<string | null>(deep ? `${deep.kind}:${deep.id}` : null);
	const mountedAt = Date.now();
	const firstRound = $derived(
		(ops.boardUpdated > 0 && ops.recommendationsUpdated > 0 && ops.dispatchesUpdated > 0 && ops.escortsDeployed !== null && cityRegistry.status !== 'idle') ||
			now - mountedAt > 20_000,
	);
	/**
	 * Without a deep link the page FOLLOWS the soonest deadline until the first full round of polls has
	 * answered (the feeds land one by one — the first unit to arrive is not necessarily the soonest), then
	 * stays on it: a sooner unit arriving later never yanks the card from under the officer (the queue and
	 * the alert show it). Any selection by the officer ends the following at once.
	 */
	let following = !deep;
	$effect(() => {
		const first = units[0];
		const settled = firstRound;
		untrack(() => {
			if (!following && selected) return;
			if (first) selected = keyOf(first);
			else if (!selected && aiCards[0]) selected = aiKey(aiCards[0]);
			if (settled && selected) following = false;
		});
	});

	function select(key: string | null, focusSheet = false) {
		if (!key) return;
		following = false;
		selected = key;
		const u = key.startsWith('ai:') ? null : seen[key];
		try {
			replaceState(u ? decideHref(u) : '/decide', {});
		} catch {
			// before the router is ready (first paint): the URL catches up on the next selection
		}
		if (focusSheet) void tick().then(() => document.getElementById('v3d-sheet-title')?.focus());
	}

	const shownAi = $derived(selected?.startsWith('ai:') ? (seenAi[selected] ?? null) : null);
	const current = $derived(selected ? (units.find((u) => keyOf(u) === selected) ?? null) : null);
	const shown = $derived(current ?? (selected ? (seen[selected] ?? null) : null));
	const outcome = $derived(selected ? (decideSession.outcomes[selected] ?? null) : null);
	const expiredHere = $derived(selected ? (decideSession.expired[selected] ?? null) : null);
	/** What the sheet shows: the live card, or how it ended. */
	const mode = $derived.by((): 'sheet' | 'done' | 'expired' | 'gone' | 'loading' | 'empty' | 'ai' => {
		if (!selected) return firstRound || units.length ? 'empty' : 'loading';
		if (shownAi) return 'ai';
		if (outcome?.ok) return 'done';
		if (current) return 'sheet';
		if (expiredHere) return 'expired';
		if (seen[selected] || firstRound) return 'gone';
		return 'loading';
	});

	const nextKey = $derived(units.map(keyOf).find((k) => k !== selected && !decideSession.outcomes[k]?.ok) ?? aiCards.map(aiKey).find((k) => k !== selected) ?? null);
	function goNext() {
		select(nextKey, true);
	}

	// ── view models ────────────────────────────────────────────────────────
	const vms = $derived.by((): Record<string, DecisionVM> => {
		void ops.officerOn;
		void cityRegistry.version;
		const out: Record<string, DecisionVM> = {};
		for (const u of Object.values(seen)) {
			try {
				out[keyOf(u)] = decisionVM(u, lang, slow);
			} catch {
				// one unit's view model failing never blanks the queue
			}
		}
		return out;
	});

	const items = $derived.by((): QueueItem[] => {
		const out: QueueItem[] = [];
		for (const u of units) {
			const k = keyOf(u);
			const vm = vms[k];
			if (!vm) continue;
			const o = decideSession.outcomes[k];
			const w = whenOf(u, now, lang, L);
			out.push({
				key: k,
				href: decideHref(u),
				kindLine: vm.kindLine,
				title: vm.title,
				plate: vm.plate,
				art: vm.art,
				when: o?.ok ? o.verb : o ? L('v3d_q_refused') : decideSession.expired[k] ? L('v3d_q_expired') : w.text,
				urgent: !o && w.urgent,
				state: o?.ok ? 'done' : o ? 'refused' : decideSession.expired[k] ? 'expired' : 'waiting',
				hooks: UNIT_KINDS[u.kind]?.dataHooks(u) ?? { kind: u.kind, id: u.id },
				emulated: unitEmulated(u),
			});
		}
		// closed here and gone from the queue: decided (green), or ran out with the plan kept
		const closed = Object.keys(seen)
			.filter((k) => !liveKeys.has(k) && (decideSession.outcomes[k]?.ok || decideSession.expired[k]))
			.sort((a, b) => (decideSession.outcomes[b]?.at ?? decideSession.expired[b]?.at ?? 0) - (decideSession.outcomes[a]?.at ?? decideSession.expired[a]?.at ?? 0));
		for (const k of closed) {
			const vm = vms[k];
			if (!vm) continue;
			const o = decideSession.outcomes[k];
			out.push({
				key: k,
				href: decideHref(seen[k]),
				kindLine: vm.kindLine,
				title: vm.title,
				plate: vm.plate,
				art: vm.art,
				when: o?.ok ? o.verb : L('v3d_q_expired'),
				urgent: false,
				state: o?.ok ? 'done' : 'expired',
				hooks: null,
				emulated: vm.emulated,
			});
		}
		return out;
	});

	// ── the map ────────────────────────────────────────────────────────────
	const roads = $derived(roadLines());
	const mapVM = $derived(shown ? (vms[keyOf(shown)] ?? null) : null);
	const segLines = $derived(new Map<number, readonly LonLat[]>(ops.segmentLines.filter((x) => x.coordinates?.length >= 2).map((x) => [x.segmentId, x.coordinates as LonLat[]])));
	const junctionAt = $derived(new Map<number, LonLat>(ops.junctions.map((j) => [j.junctionId, [j.lon, j.lat] as LonLat])));
	const aiOverlay = $derived(shownAi ? cardOverlay(shownAi, segLines, junctionAt, cardPlace(shownAi, lang), !!ai.decisions[shownAi.id]) : null);
	const mapOverlay = $derived.by((): ThumbOverlay | null => {
		if (!mapVM || !shown) return null;
		const o = mapVM.thumb.overlay;
		if (shown.kind === 'dss') {
			const place = dssOf(shown).label.split(' · ').pop() ?? '';
			return { ...o, points: (o.points ?? []).map((p) => (p.small ? p : { ...p, label: p.label ?? L('v3d_map_reported_here', ops.text(place)) })) };
		}
		if (shown.kind === 'stolen-sighting' || shown.kind === 'pursuit') {
			return { ...o, points: (o.points ?? []).map((p) => (p.small ? p : { ...p, label: p.label ?? L('v3d_map_last_read') })) };
		}
		return o;
	});
	const mapTag = $derived.by(() => {
		if (shownAi) return `${L(cardKindKey(shownAi))} · ${cardPlace(shownAi, lang) || L('ai_d_section')}`;
		if (!shown) return L('v3_map_alt_plain');
		switch (shown.kind) {
			case 'escort-proposal':
				return L('v3d_map_escort');
			case 'dss':
				return L('v3d_map_dss', ops.text(dssOf(shown).label.split(' · ').pop() ?? ''));
			case 'stolen-sighting':
			case 'pursuit':
				return L('v3d_map_reads');
			case 'corridor-request':
				return L('v3d_map_corridor');
			default:
				return L('v3d_map_place');
		}
	});
	const legend = $derived.by((): { tone: string; text: string }[] => {
		if (shownAi) return [...(shownAi.source === 'hydro' ? [{ tone: 'flood', text: L('ai_l_waterlog') }] : []), ...(shownAi.viaSegmentIds.length ? [{ tone: 'road', text: L('ai_lg_detour') }] : []), { tone: 'decide', text: L('v3d_lg_decision') }];
		if (!shown) return [];
		const out: { tone: string; text: string }[] = [];
		if (shown.kind === 'escort-proposal') out.push({ tone: 'route', text: L('v3d_lg_route') });
		if (shown.kind === 'stolen-sighting' || shown.kind === 'pursuit') out.push({ tone: 'alert', text: L('v3d_lg_reads') });
		out.push({ tone: 'decide', text: L('v3d_lg_decision') });
		return out;
	});

	// ── keyboard (§7.1) ────────────────────────────────────────────────────
	let sheet = $state<{ chooseIndex(i: number): boolean; startReason(): boolean; focusPrimary(): boolean } | null>(null);
	function typing(target: EventTarget | null): boolean {
		const el = target as HTMLElement | null;
		return el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement || !!el?.isContentEditable;
	}
	function onKey(e: KeyboardEvent) {
		const target = e.target as HTMLElement | null;
		// Enter on a control is that control's own (a link, a button, an option): only from the page itself
		if (e.key === 'Enter' && target && target !== document.body && target.closest('a, button, [role="radio"], summary, input')) return;
		const intent = keyIntent(e, typing(e.target));
		if (!intent) return;
		const waiting = units.filter((u) => !decideSession.outcomes[keyOf(u)]?.ok);
		switch (intent.kind) {
			case 'next':
			case 'prev': {
				if (e.key.startsWith('Arrow') && !target?.closest('[data-v3="decide-queue"]')) return;
				e.preventDefault();
				select(stepKey(waiting, selected, intent.kind === 'next' ? 1 : -1));
				void tick().then(() => (document.querySelector(`[data-key="${CSS.escape(selected ?? '')}"]`) as HTMLElement | null)?.focus());
				return;
			}
			case 'option':
				if (sheet?.chooseIndex(intent.index)) e.preventDefault();
				return;
			case 'focus-primary':
				if (sheet?.focusPrimary()) e.preventDefault();
				return;
			case 'reason':
				if (sheet?.startReason()) e.preventDefault();
				return;
		}
	}

	// ── the Omnibar (the page's one, after first paint) ───────────────────
	let Omnibar = $state<Component | null>(null);
	let sessionWaitOver = $state(false);

	onMount(() => {
		registerProviders();
		ops.start();
		cityRegistry.start();
		const releaseAi = ai.use('forecast', 'twin', 'hydro', 'decisions');
		const wait = setTimeout(() => (sessionWaitOver = true), 2500);
		void import('$lib/workspace/components/omnibar/Omnibar.svelte').then((m) => (Omnibar = m.default as unknown as Component));
		return () => {
			clearTimeout(wait);
			releaseAi();
		};
	});

	onDestroy(() => {
		cityRegistry.stop();
		ops.stop();
		if (typeof window !== 'undefined') delete (window as unknown as Record<string, unknown>).__V3_DECIDE__;
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
		commandBar.officer = { value: ops.dutyOfficer, fromSession: ops.dutyOfficerFromSession, set: (v: string) => ops.setDutyOfficer(v) };
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
	$effect(() => {
		v3Bar.title = L('v3_nav_decide');
		v3Bar.sub = units.length ? L('v3d_sub', units.length) : L('v3d_sub_none');
		v3Bar.active = 'decide';
	});
	$effect(() => {
		v3Bar.decisions = firstRound ? units.map((u) => ({ key: keyOf(u), title: u.title, href: decideHref(u), emulated: unitEmulated(u) })) : null;
	});

	// ── the test hook (the smoke holds the page to the canonical selectors) ─
	$effect(() => {
		if (typeof window === 'undefined') return;
		(window as unknown as Record<string, unknown>).__V3_DECIDE__ = {
			canonical: selectors.decisionUnits().length,
			units: units.map(keyOf),
			selected,
			mode,
			officerOn: ops.officerOn,
			tally: { ...decideSession.tally },
			ai: { cards: aiCards.map((c) => ({ id: c.id, source: c.source, kind: c.kind })), selected: shownAi?.id ?? null, exercise: ai.exercise, platformLog: ai.platformLog, decided: Object.keys(ai.decisions).length },
		};
	});
</script>

<svelte:head>
	<title>{L('v3_nav_decide')} · Sajag</title>
</svelte:head>

<svelte:window onkeydown={onKey} />

{#if ops.signInRequired}
	<div class="signin" data-testid="cockpit-signin-required">
		<div class="signin-card">
			<h2>{tOps(lang, 'opsSigninTitle')}</h2>
			<p>{tOps(lang, 'cockpitSigninBody')}</p>
			<OperatorSignIn lang={ops.lang} inline />
		</div>
	</div>
{:else}
	<div class="dec" data-v3="decide" data-ready={sessionWaitOver || ops.boardUpdated > 0 ? 'true' : 'false'} data-mode={mode}>
		<DecideQueue
			{items}
			{selected}
			waiting={units.length}
			tally={tally}
			recordHref="/ops"
			{lang}
			onselect={(k) => select(k, true)}
			{aiItems}
			aiWaiting={aiCards.length}
			{aiNote}
			exercise={ai.exercise}
			onexercise={setExercise}
		/>

		<section class="center" aria-label={L('v3d_center')}>
			<div class="stage">
				{#if shownAi && aiOverlay}
					{#key shownAi.id}
						<MapThumb class="decide-map" overlay={aiOverlay} alt={cardTitle(shownAi, lang, L)} focus={[0.3, 0.5]} maxTiles={48} markerR={18} frameOn="all" zoom={15} labels eager creditInside={false} {roads} />
					{/key}
				{:else if mapVM && mapOverlay}
					{#key keyOf(shown!)}
						<MapThumb
							class="decide-map"
							overlay={mapOverlay}
							alt={mapVM.thumb.alt}
							focus={[0.3, 0.5]}
							maxTiles={48}
							markerR={18}
							frameOn={mapVM.thumb.frameOn ?? 'all'}
							zoom={mapVM.thumb.zoom ?? 15}
							labels
							eager
							creditInside={false}
							{roads}
						/>
					{/key}
				{:else}
					<div class="map-empty" aria-hidden="true"></div>
				{/if}
			</div>
			{#if shown || shownAi}
				<div class="map-src"><span class="glass-tag"><Glyph name="map" size={15} />{mapTag}</span></div>
			{/if}
			<div class="map-legend">
				{#each legend as l (l.text)}<span><i class={`lg-${l.tone}`}></i>{l.text}</span>{/each}
				{#if mapStyle.effective === 'satellite' && mapStyle.imagery}
					<span class="credit" data-testid="v3d-imagery-credit">{mapStyle.imagery}</span>
				{:else}
					<span class="credit">{L('v3d_map_data')} <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a></span>
				{/if}
			</div>

			<article class="sheet" aria-labelledby="v3d-sheet-title" data-testid="v3-sheet" aria-live="polite">
				{#if mode === 'ai' && shownAi}
					{#key shownAi.id}
						<AiSheet card={shownAi} decided={ai.decisions[shownAi.id] ?? null} {lang} hasNext={!!nextKey} onnext={goNext} />
					{/key}
				{:else if mode === 'sheet' && current}
					{#key keyOf(current)}
						<DecisionSheet bind:this={sheet} unit={current} {lang} {now} {slow} />
					{/key}
				{:else if mode === 'done' && outcome}
					<OutcomeState mode="done" verb={outcome.verb} officer={outcome.officer} at={outcome.at} next={outcome.next} hasNext={!!nextKey} onnext={goNext} {lang} />
				{:else if mode === 'expired' || mode === 'gone'}
					<OutcomeState {mode} hasNext={!!nextKey} onnext={goNext} {lang} />
				{:else if mode === 'loading'}
					<div class="skel" aria-busy="true">
						<h1 class="sr" id="v3d-sheet-title">{L('v3d_loading')}</h1>
						<div class="sk h"></div>
						<div class="sk l"></div>
						<div class="sk l short"></div>
						<div class="sk b"></div>
					</div>
				{:else}
					<div class="clear">
						<img src="/illustrations/empty/all-clear.svg" alt="" width="200" height="150" />
						<h1 id="v3d-sheet-title">{L('v3_hero_clear')}</h1>
						<p>{L('v3d_clear_body')}</p>
						<a class="link" href="/home">{L('v3d_back_home')}</a>
					</div>
				{/if}
			</article>
		</section>
	</div>
{/if}

{#if Omnibar}<Omnibar />{/if}

<style>
	.dec {
		display: grid;
		grid-template-columns: 340px minmax(0, 1fr);
		height: 100%;
		min-height: 0;
		overflow: hidden;
	}

	.center {
		position: relative;
		min-width: 0;
		overflow: hidden;
		background: var(--v3-map-bg);
	}

	.stage {
		position: absolute;
		inset: 0;
	}

	.stage :global(.decide-map) {
		width: 100%;
		height: 100%;
		border-radius: 0;
	}

	.map-empty {
		width: 100%;
		height: 100%;
		background: var(--v3-map-bg);
	}

	.map-src {
		position: absolute;
		top: 20px;
		left: 20px;
		z-index: 4;
	}

	/* every panel floating over the map is the one glass (the map's material: tokens --v3-glass-*); without a blur the
	   tint alone keeps every ink ≥ 4.5:1 (tests/v3-tokens.unit.mjs) */
	.glass-tag,
	.map-legend,
	.sheet {
		border-color: var(--v3-glass-border);
		background: var(--v3-glass-bg);
		-webkit-backdrop-filter: var(--v3-glass-blur);
		backdrop-filter: var(--v3-glass-blur);
	}

	.glass-tag {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 28px;
		padding: 0 12px;
		border: 1px solid var(--v3-glass-border);
		border-radius: 14px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 600;
	}

	.map-legend {
		position: absolute;
		bottom: 20px;
		left: 20px;
		z-index: 4;
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 10px 14px;
		border: 1px solid var(--v3-glass-border);
		border-radius: 14px;
		font-size: var(--v3-text-meta);
		color: var(--v3-t2);
	}

	.map-legend span {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.map-legend i {
		display: inline-block;
		width: 14px;
		height: 4px;
		border-radius: 2px;
	}

	.lg-route {
		background: var(--v3-route);
	}

	.lg-alert {
		background: var(--v3-alert);
	}

	.lg-decide {
		background: var(--v3-decide);
	}

	.lg-flood {
		background: var(--v-map-water);
	}

	.lg-road {
		background: var(--v3-t1);
		opacity: 0.55;
	}

	.credit a {
		color: var(--v3-t2);
	}

	.sheet {
		position: absolute;
		top: 20px;
		right: 20px;
		bottom: 20px;
		z-index: 5;
		display: flex;
		flex-direction: column;
		width: 540px;
		overflow: hidden;
		border: 1px solid var(--v3-glass-border);
		border-radius: var(--v3-radius-xl);
		box-shadow: var(--v3-elev-2);
	}

	/* a new decision (or outcome) enters the sheet softly: 180 ms, a fade and a 6 px rise; none under reduced motion */
	.sheet > :global(*) {
		animation: v3d-enter 180ms var(--v3-ease) both;
	}

	@keyframes v3d-enter {
		from {
			opacity: 0;
			transform: translateY(6px);
		}
		to {
			opacity: 1;
			transform: none;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.sheet > :global(*) {
			animation: none;
		}
	}

	.skel {
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding: 26px;
	}

	.sk {
		border-radius: 12px;
		background: var(--v3-s2);
	}

	.sk.h {
		height: 60px;
		width: 70%;
	}

	.sk.l {
		height: 18px;
	}

	.sk.short {
		width: 60%;
	}

	.sk.b {
		height: 180px;
	}

	.clear {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		padding: 64px 32px;
		text-align: center;
	}

	.clear h1 {
		margin: 8px 0 0;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 650;
	}

	.clear p {
		margin: 0;
		max-width: 360px;
		color: var(--v3-t2);
		font-size: 14px;
	}

	.link {
		color: var(--v3-brand-text);
		font-weight: 600;
		text-decoration: none;
	}

	.link:hover {
		text-decoration: underline;
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
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

	/* §6.10: the 1366 class — a narrower labelled queue (title, kind, plate, time), the sheet 470 px */
	@media (max-width: 1500px) {
		.dec {
			grid-template-columns: 288px minmax(0, 1fr);
		}

		.sheet {
			top: 14px;
			right: 14px;
			bottom: 14px;
			width: 470px;
		}

		.map-src {
			top: 14px;
			left: 14px;
		}

		.map-legend {
			display: none;
		}
	}

	/* below 1280 px the queue is its art only (92 px): a labelled queue would leave the map no room */
	@media (max-width: 1279px) {
		.dec {
			grid-template-columns: 92px minmax(0, 1fr);
		}
	}

	/* a phone: queue strip on top, then a short map, then the whole sheet in the page's own scroll */
	@media (max-width: 720px) {
		.dec {
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: auto minmax(0, 1fr);
		}

		.center {
			overflow-x: hidden;
			overflow-y: auto;
		}

		.stage {
			position: relative;
			height: 190px;
		}

		.map-src {
			top: 10px;
			left: 10px;
		}

		.sheet {
			position: relative;
			top: auto;
			right: auto;
			bottom: auto;
			width: auto;
			margin: -20px 10px 12px;
			min-height: 420px;
		}
	}
</style>
