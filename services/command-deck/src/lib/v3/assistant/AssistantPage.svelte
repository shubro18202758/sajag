<script lang="ts">
	/**
	 * /assistant — the V3 Assistant (V3-SPEC §5.7, §6.10, §7.6; V3-P4). The conversation runs on the SAME ChatSession
	 * as the v2 AssistantPanel ($lib/assistant/session.svelte.ts: the turn, the stream, the brain session, the kept
	 * conversation) — only the presentation is new:
	 *
	 *   Thread / BotTurn   prose at 16/26 with the objects it names as chips; the working steps while it reads,
	 *                      folded once it answers (lookups in words); the grounding note the brain gave; the
	 *                      cautions (one human sentence per diagnostic — never a raw code); proposal cards
	 *   ProposalCard       the decisions this turn touched (cited objects with a unit waiting): Open to decide (the
	 *                      unit's ONE home in Decide) · Show on map; a map proposal waits on /map. Never Apply,
	 *                      never Approve — the assistant reads and proposes, a named officer decides.
	 *   SuggestionChips · AskBar · ContextPanel (the objects named, how it works, model and trace in words)
	 *
	 * It asks about the whole city (no event scope): the wire carries the question, the session, nothing else.
	 * Every text from the brain goes through the mask (ops.text): marks stay masked unless a duty officer is named.
	 * No model id, tool name or alert code reaches the page (the test hook lists what the smoke checks).
	 */
	import { onDestroy, onMount, tick, untrack } from 'svelte';
	import type { Component } from 'svelte';
	import { goto } from '$app/navigation';
	import { ops } from '$lib/ops/store.svelte';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { canvasBus } from '$lib/gods-eye/canvas-bus.svelte';
	import { parseUrn } from '$lib/gods-eye/city-api';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import OperatorSignIn from '$lib/shell/OperatorSignIn.svelte';
	import { registerProviders } from '$lib/workspace/providers';
	import { selectors } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { decisionUnits, unitEmulated, type Unit } from '$lib/decisions/units';
	import { keptConversation } from '$lib/assistant/conversation';
	import { groundingOf, splitLookups } from '$lib/assistant/answer';
	import { ChatSession, answerOf, citationParts, type Message } from '$lib/assistant/session.svelte';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.wall';
	import '$lib/i18n/packs.assistant';
	import { provideUiLang } from '$lib/ui';
	import { fmtTime } from '$lib/ui/format/format';
	import '../packs.v3';
	import '../map/packs.map3';
	import './packs.asst3';
	import { v3Bar } from '../shell/v3-bar.svelte';
	import { artFor, countdownText, unitKey } from '../home/model';
	import { decisionVM, roadLines } from '../home/view';
	import { entityArt } from '../map/model';
	import Glyph from '../Glyph.svelte';
	import Thread from './Thread.svelte';
	import SuggestionChips from './SuggestionChips.svelte';
	import ContextPanel from './ContextPanel.svelte';
	import { SUGGESTIONS, SIMULATED_TOOLS, chipGlyph, cautionsOf, directiveLabel, humaniseLookups, modelKey, scrubCodes, segmentProse, toolLabel, type Chip } from './model';
	import type { ContextItem, ProposalVM, TurnVM } from './view';

	const VARIANT = 'v3';

	provideUiLang(() => ops.lang);
	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	// ── the conversation: the shared session (kept across mounts of this page) ──
	const chat = new ChatSession(untrack(() => keptConversation<Message>(VARIANT)));
	chat.rescope('');
	let draft = $state('');

	// ── clocks ──────────────────────────────────────────────────────────────
	let now = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(id);
	});

	// ── the decisions (canonical units) ─────────────────────────────────────
	const units = $derived.by((): Unit[] => {
		void cityRegistry.version;
		return decisionUnits(ops);
	});
	const unitBySubject = $derived.by(() => {
		const m = new Map<string, Unit>();
		for (const u of units) if (!m.has(u.subjectUrn)) m.set(u.subjectUrn, u);
		return m;
	});
	const roads = $derived(roadLines());

	/** A cited urn as the deck knows it (a label-shaped vehicle urn stays a chip; a convoy stands for its movement). */
	function decisionFor(urn: string): Unit | null {
		const hit = unitBySubject.get(urn);
		if (hit) return hit;
		const ent = cityRegistry.get(urn);
		const ev = typeof ent?.props.event_id === 'string' ? `event:${ent.props.event_id}` : null;
		return ev ? (unitBySubject.get(ev) ?? null) : null;
	}

	function chipOf(c: Chip): { glyph: string; decide: boolean } {
		const p = citationParts(c.urn);
		return { glyph: chipGlyph(p?.kind), decide: !!decisionFor(c.urn) };
	}

	// ── one turn's view (every text through the mask; codes in words) ──────
	function turnVM(m: Message, last: boolean): TurnVM {
		const at = m.at ? fmtTime(m.at) : '';
		if (m.role === 'user') return { id: m.id, role: 'user', text: ops.text(m.text), segments: [], at, working: false, steps: [], lookups: null, stepsSummary: '', noProse: false, error: null, grounding: null, cautions: [], proposals: [] };
		const working = last && chat.streaming && !m.done && !m.error;
		const answer = answerOf(m);
		const split = answer.prose ? splitLookups(answer.prose) : null;
		const prose = split ? scrubCodes(ops.text(split.answer), L) : '';
		const cites = (m.done?.citations ?? []).map((c) => ({ urn: c.urn, label: ops.text(c.label) }));
		const steps = m.toolCalls.map((tc) => ({
			label: toolLabel(tc.toolName, L),
			state: tc.state,
			simulated: SIMULATED_TOOLS.has(tc.toolName),
			summary: tc.summary ? humaniseLookups(ops.text(tc.summary), L) : null,
		}));
		const grounding = m.done ? groundingOf(m.done) : null;
		const proposals: ProposalVM[] = [];
		const seen = new Set<string>();
		for (const c of cites) {
			const u = decisionFor(c.urn);
			if (!u || seen.has(unitKey(u)) || proposals.length >= 2) continue;
			seen.add(unitKey(u));
			const vm = decisionVM(u, lang, now);
			proposals.push({
				key: unitKey(u),
				kind: 'decision',
				thumb: vm.thumb,
				inset: vm.inset,
				tag: vm.by.ai ? L('v3a_proposal') : L('v3a_waiting'),
				ai: vm.by.ai,
				timer: vm.deadline != null && vm.deadline > now ? L('v3a_left', countdownText(vm.deadline - now, lang)) : null,
				title: vm.title,
				why: vm.why,
				openHref: vm.href,
				urn: u.subjectUrn,
			});
		}
		for (const d of m.directives.slice(0, 1)) {
			proposals.push({ key: `dir:${d.id}`, kind: 'map', thumb: null, tag: L('v3a_map_proposal'), ai: true, timer: null, title: scrubCodes(ops.text(directiveLabel(d.label)), L), why: L('v3a_map_proposal_body'), openHref: null, urn: null });
		}
		return {
			id: m.id,
			role: 'agent',
			text: prose,
			segments: prose ? segmentProse(prose, cites) : [],
			at,
			working,
			steps,
			lookups: split?.lookups ? humaniseLookups(ops.text(split.lookups), L) : null,
			stepsSummary: L('v3a_steps', steps.length + (split?.lookups ? 1 : 0)),
			noProse: !answer.prose && !!answer.raw,
			error: m.error ? L('v3a_error') : null,
			grounding: grounding?.removed ? L('asst_grounding_removed', grounding.removed) : null,
			cautions: cautionsOf(m.done).map((k) => ({ key: k, text: L(k) })),
			proposals,
		};
	}

	const turns = $derived(chat.messages.map((m, i) => turnVM(m, i === chat.messages.length - 1)));

	// ── the context panel ───────────────────────────────────────────────────
	const ctxItems = $derived.by((): ContextItem[] => {
		void cityRegistry.version;
		const out = new Map<string, ContextItem>();
		for (const m of chat.messages) {
			for (const c of m.done?.citations ?? []) {
				if (out.has(c.urn)) continue;
				const p = citationParts(c.urn);
				const ent = cityRegistry.get(c.urn);
				const kindKey = `v3m_kind_${p?.kind ?? ''}`;
				const kindWord = L(kindKey) === kindKey ? L('v3m_sel_object') : L(kindKey);
				const decide = !!decisionFor(c.urn);
				out.set(c.urn, {
					urn: c.urn,
					label: ops.text(c.label),
					meta: decide ? `${kindWord} · ${L('v3a_ctx_waits')}` : kindWord,
					art: entityArt(p?.kind ?? '', ent?.props ?? {}, artFor),
					decide,
				});
			}
		}
		return [...out.values()];
	});
	const lastDone = $derived([...chat.messages].reverse().find((m) => m.role === 'agent' && m.done) ?? null);
	const modelLine = $derived(L(modelKey(lastDone?.done?.tiersUsed)));
	const lastAnswer = $derived(lastDone?.at && lastDone.doneAt ? L('v3a_last_answer', ((lastDone.doneAt - lastDone.at) / 1000).toFixed(1)) : null);

	// ── asking ──────────────────────────────────────────────────────────────
	const WIRE = { movementId: null, vvipClass: null, eventId: null, contextUrn: null } as const;
	function send() {
		if (chat.send(draft, WIRE)) draft = '';
	}
	function ask(key: string) {
		const s = SUGGESTIONS.find((x) => x.key === key);
		if (s) chat.send(s.message, WIRE, L(s.label));
	}
	const suggestions = $derived(SUGGESTIONS.slice(0, 4).map((s) => ({ key: s.key, label: L(s.label) })));

	/** Open a named object: a decision waiting on it opens in Decide; anything else is selected and shown on the map. */
	function openObject(urn: string) {
		const u = decisionFor(urn);
		if (u) {
			const vm = decisionVM(u, lang, now);
			void goto(vm.href);
			return;
		}
		showOnMap(urn);
	}
	function showOnMap(urn: string | null) {
		if (urn && parseUrn(urn)) {
			selection.select(urn, { source: 'chat' });
			canvasBus.requestSelection(urn);
		}
		void goto('/map');
	}

	// ── follow the reply as it streams ──────────────────────────────────────
	let scrollEl = $state<HTMLDivElement | null>(null);
	$effect(() => {
		const last = chat.messages[chat.messages.length - 1];
		void chat.messages.length;
		void last?.text.length;
		void last?.toolCalls.length;
		void tick().then(() => {
			if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
		});
	});

	// ── lifecycle and the shell ─────────────────────────────────────────────
	let Omnibar = $state<Component | null>(null);
	onMount(() => {
		registerProviders();
		ops.start();
		cityRegistry.start();
		void import('$lib/workspace/components/omnibar/Omnibar.svelte').then((m) => (Omnibar = m.default as unknown as Component));
	});
	onDestroy(() => {
		chat.release(VARIANT, L('asst_interrupted'));
		cityRegistry.stop();
		ops.stop();
		if (typeof window !== 'undefined') delete (window as unknown as Record<string, unknown>).__V3_ASSISTANT__;
	});

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
		v3Bar.title = L('v3a_title');
		v3Bar.sub = L('v3a_sub');
		v3Bar.active = 'assistant';
	});
	const mountedAt = Date.now();
	const firstRound = $derived(
		(ops.boardUpdated > 0 && ops.recommendationsUpdated > 0 && ops.dispatchesUpdated > 0 && ops.escortsDeployed !== null && cityRegistry.status !== 'idle') ||
			now - mountedAt > 10_000,
	);
	$effect(() => {
		v3Bar.decisions = firstRound ? units.map((u) => ({ key: unitKey(u), title: u.title, href: decisionVM(u, lang, now).href, emulated: unitEmulated(u) })) : null;
	});

	// ── the test hook ───────────────────────────────────────────────────────
	$effect(() => {
		if (typeof window === 'undefined') return;
		(window as unknown as Record<string, unknown>).__V3_ASSISTANT__ = {
			canonical: { decisions: selectors.decisionUnits().length },
			turns: chat.messages.length,
			streaming: chat.streaming,
			sessionKept: !!chat.sessionId,
			context: ctxItems.map((c) => ({ urn: c.urn, decide: c.decide })),
			proposals: turns.flatMap((x) => x.proposals.map((p) => ({ kind: p.kind, href: p.openHref }))),
			cautions: turns.flatMap((x) => x.cautions.map((c) => c.key)),
			officerOn: ops.officerOn,
		};
	});
</script>

<svelte:head>
	<title>{L('v3a_title')} · Sajag</title>
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
	<div class="as" data-v3="assistant">
		<section class="conv" aria-label={L('v3a_conversation')}>
			<div class="thread" bind:this={scrollEl} aria-live="polite" aria-busy={chat.streaming ? 'true' : 'false'}>
				{#if chat.degraded}<p class="offline" role="status" data-testid="v3-assistant-offline">{L('v3a_offline')}</p>{/if}
				<Thread {turns} {L} {chipOf} onopen={openObject} onshowmap={showOnMap} {roads} />
			</div>
			<div class="dock">
				<div class="dcol">
					<SuggestionChips items={suggestions} disabled={chat.streaming} label={L('v3a_suggest')} onask={ask} />
					<form
						class="askbar"
						onsubmit={(e) => {
							e.preventDefault();
							send();
						}}
					>
						<input type="text" bind:value={draft} placeholder={L('v3a_ask')} aria-label={L('v3a_ask')} data-testid="v3-ask" autocomplete="off" />
						<button type="submit" class="send" aria-label={L('v3a_send')} title={L('v3a_send')} disabled={!draft.trim() || chat.streaming} data-testid="v3-send"><Glyph name="send" size={20} /></button>
					</form>
					<div class="scope">
						<Glyph name="shield" size={16} /><span>{L('v3a_scope')}</span>
						{#if chat.messages.length}<button type="button" class="clear" data-testid="v3-clear" onclick={() => chat.clear(VARIANT)}>{L('v3a_clear')}</button>{/if}
					</div>
				</div>
			</div>
		</section>
		<ContextPanel items={ctxItems} {modelLine} {lastAnswer} {L} onopen={openObject} />
	</div>
{/if}

{#if Omnibar}<Omnibar />{/if}

<style>
	.as {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 380px;
		height: 100%;
		overflow: hidden;
	}

	.conv {
		display: flex;
		flex-direction: column;
		min-height: 0;
		border-right: 1px solid var(--v3-line-1);
	}

	.thread {
		flex: 1;
		min-height: 0;
		overflow: auto;
		padding: 28px 0 20px;
		scrollbar-width: thin;
		scrollbar-color: var(--v3-s4) transparent;
	}

	.offline {
		max-width: 756px;
		margin: 0 auto 16px;
		padding: 10px 14px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.dock {
		padding: 12px 0 22px;
		border-top: 1px solid var(--v3-line-1);
	}

	.dcol {
		display: flex;
		flex-direction: column;
		gap: 12px;
		max-width: 820px;
		margin: 0 auto;
		padding: 0 32px;
	}

	.askbar {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 6px 6px 6px 18px;
		border: 1px solid var(--v3-line-3);
		border-radius: 26px;
		background: var(--v3-s1);
	}

	.askbar:focus-within {
		border-color: var(--v3-brand);
	}

	.askbar input {
		flex: 1;
		min-width: 0;
		height: 40px;
		border: 0;
		background: none;
		color: var(--v3-t1);
		font: inherit;
		font-size: 16px;
		outline: none;
	}

	.askbar input::placeholder {
		color: var(--v3-t3);
	}

	.send {
		display: grid;
		place-items: center;
		flex: none;
		width: 44px;
		height: 44px;
		border: 0;
		border-radius: 22px;
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		cursor: pointer;
	}

	.send:disabled {
		background: var(--v3-s3);
		color: var(--v3-t3);
		cursor: not-allowed;
	}

	.send:focus-visible,
	.clear:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.scope {
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		font-weight: 600;
	}

	.clear {
		margin-left: auto;
		border: 0;
		background: none;
		padding: 0;
		color: var(--v3-brand-text);
		font: inherit;
		white-space: nowrap;
		cursor: pointer;
	}

	.signin {
		display: grid;
		place-items: center;
		height: 100%;
		padding: 16px;
	}

	.signin-card {
		width: min(440px, calc(100vw - 32px));
		display: flex;
		flex-direction: column;
		gap: 12px;
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

	@media (max-width: 1500px) {
		.as {
			grid-template-columns: minmax(0, 1fr) 300px;
		}

		.dcol {
			padding: 0 24px;
		}
	}

	/* a phone: the conversation alone (the context column is a desktop aside) */
	@media (max-width: 720px) {
		.as {
			grid-template-columns: minmax(0, 1fr);
		}

		.as > :global(.ctx) {
			display: none;
		}

		.conv {
			border-right: 0;
		}

		.dcol {
			padding: 0 14px;
		}

		.thread {
			padding-top: 16px;
		}
	}
</style>
