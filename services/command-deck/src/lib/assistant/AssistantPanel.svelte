<script lang="ts">
	/**
	 * AssistantPanel (SPEC §5.3 [S6], §6.4) — the assistant as a right-dock
	 * tab (variant 'dock') and as the full /chat page (variant 'page').
	 *
	 * It READS and PROPOSES, never decides (SPEC §9.3): the real NDJSON
	 * streamChat wiring (POST /api/convoy/chat/stream, contract C-D, via
	 * $lib/api/client — read-only, UI-S6A owns the client) drives the turns;
	 * tool calls render as steps humanised by displayTool, COLLAPSED by
	 * default, with the raw tool names, model, tier and session under
	 * "Details" (chat-tiers and chat-session stay in the DOM while it is
	 * closed). Answers render as prose; a brain that still streams its JSON
	 * envelope gets an honest "no prose answer" note with the envelope
	 * verbatim. Citations render as ObjectTags.
	 *
	 * NO Apply and NO Approve control anywhere (SPEC §9.3): a map proposal
	 * shows as a link card to the map ("Proposed on the map: … · Review it
	 * on the map"), a decision waiting on the scoped object shows as a link
	 * card to its ONE home (homeLink, UI-S5A). Switches replace the legacy
	 * native checkboxes.
	 *
	 * Context: the scope line names the selection (`contextUrn`, else the
	 * workspace selection) and the view; every turn is scoped to it on the
	 * wire (event_id — C-D2 — plus movement_id + protection class and
	 * context_urn). Changing the scope opens a new session. Every text the
	 * brain streams goes through the mask (ops.text): plates stay masked
	 * unless a duty officer is named on this console.
	 *
	 * `sample` renders ONE labelled sample turn (composed locally, no model
	 * called, the note on screen) — an opt-in review state (`?sample=1` on
	 * /chat), never mixed with real turns.
	 *
	 * The conversation logic (the turn, the stream, the brain session, the
	 * kept conversation, the answer's prose) is the shared ChatSession
	 * (session.svelte.ts, V3-P4) — the V3 Assistant (/assistant) runs the
	 * same one; this panel keeps its own presentation.
	 */
	import { onDestroy, untrack } from 'svelte';
	import { keptConversation } from './conversation';
	import { groundingOf, splitLookups } from './answer';
	import { ChatSession, answerOf, citationParts, parseTier, type Message, type ToolCall } from './session.svelte';
	import { goto } from '$app/navigation';
	import { ops } from '$lib/ops/store.svelte';
	import type { CorridorEvent } from '$lib/ops/types';
	import type { VvipClass } from '$lib/types';
	import { kindLabel, t } from '$lib/i18n/strings';
	import { citizenT } from '$lib/i18n/strings.citizen';
	import '$lib/i18n/packs.agent';
	import '$lib/i18n/packs.assistant';
	import type { ChatCitation } from '$lib/api/client';
	import { movementIdOf } from '$lib/comms/facts';
	import { canvasBus } from '$lib/gods-eye/canvas-bus.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { parseUrn } from '$lib/gods-eye/city-api';
	import { displayTitle, displayTool } from '$lib/workspace/display';
	import { liveWorld, selectors } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { homeLink } from '$lib/decisions/homes';
	import { landmarkName } from '$lib/city';
	import { reviewTarget } from './review-target';
	import { Button, Drawer, Icon, NonIdealState, ObjectTag, Section, Switch } from '$lib/ui';

	let {
		contextUrn = null,
		eventId = null,
		variant = 'dock',
		sample = false,
	}: {
		contextUrn?: string | null;
		eventId?: string | null;
		variant?: 'dock' | 'page';
		/** One labelled sample turn, composed locally (review state only). */
		sample?: boolean;
	} = $props();

	// the conversation outlives the panel (a citation opens the Inspector; a page change remounts it)
	const chat = new ChatSession(untrack(() => keptConversation<Message>(variant)));
	const messages = $derived(chat.messages);
	const streaming = $derived(chat.streaming);
	const degraded = $derived(chat.degraded);
	/** Brain session carried across follow-ups (done.data.session_id). */
	const sessionId = $derived(chat.sessionId);
	let draft = $state('');
	let showSteps = $state(false);
	let showThoughts = $state(false);
	let scrollEl: HTMLDivElement | undefined = $state();
	/** Below 1440 px the page variant holds the context in a drawer. */
	let ctxOpen = $state(false);
	/** The viewport width (the drawer's FAB renders below 1440 only). */
	let vw = $state(1600);

	/** The scope: the prop, else the workspace selection (the dock's default). */
	const urn = $derived(contextUrn ?? selection.current);
	const evId = $derived(eventId ?? (urn && urn.startsWith('event:') ? urn.slice('event:'.length) : ops.selectedEventId));
	const ev = $derived<CorridorEvent | null>(ops.events.find((e) => e.eventId === evId) ?? null);

	// A new EVENT opens a new session (the brain scopes a session to its event). Selecting a cited vehicle or camera
	// keeps the session: the officer is still asking about the same situation.
	$effect(() => {
		chat.rescope(evId ?? '');
	});

	/** The scope line's readable label: a masked mark for a vehicle, an id otherwise. */
	const urnParsed = $derived(urn ? parseUrn(urn) : null);
	/** The scope object's display label from the world (a vehicle's masked mark, not its uuid). */
	const urnRow = $derived(urn ? (liveWorld.registry().find((r) => r.urn === urn) ?? null) : null);

	// Follow the reply as it streams (tokens, thoughts and tool cards).
	$effect(() => {
		const last = messages[messages.length - 1];
		void messages.length;
		void last?.text.length;
		void last?.thoughts.length;
		void last?.toolCalls.length;
		requestAnimationFrame(() => {
			if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
		});
	});

	onDestroy(() => {
		// a turn cut off by the unmount says so; it is never left "thinking" forever
		chat.release(variant, L('asst_interrupted'));
	});

	const VVIP_CLASSES: readonly VvipClass[] = ['Z+', 'Z', 'Y', 'X'];

	function vvipClassOf(e: CorridorEvent | null): VvipClass | null {
		const cls = e?.protectionClass;
		return cls && (VVIP_CLASSES as readonly string[]).includes(cls) ? (cls as VvipClass) : null;
	}

	/** Decision units waiting on the scoped object (link cards — never a second Approve). */
	const scopeUnits = $derived(
		urn
			? selectors.decisionUnits().filter((u) => u.subjectUrn === urn)
			: evId
				? selectors.decisionUnits().filter((u) => u.subjectUrn === `event:${evId}`)
				: [],
	);

	/** Suggestions: about the scope when there is one, else the city's questions. */
	interface Suggestion {
		key: string;
		label: string;
		message: string;
	}
	const suggestions = $derived.by((): Suggestion[] => {
		if (ev) {
			const out: Suggestion[] = [
				{ key: 'traffic', label: t(lang, 'chat_suggest_traffic'), message: 'Live traffic on this corridor — which segments are slowest right now?' },
			];
			if (ev.eventKind === 'vehicle_pursuit') {
				out.push({ key: 'interception', label: t(lang, 'chat_suggest_interception'), message: 'What is the interception plan for this pursuit?' });
			}
			out.push(
				{ key: 'closures', label: t(lang, 'chat_suggest_closures'), message: 'What is the status of this corridor and its closures?' },
				{ key: 'map', label: t(lang, 'chat_suggest_map'), message: 'Show this event on the map' },
			);
			return out.slice(0, 4);
		}
		return [
			{ key: 'stolen', label: t(lang, 'chat_suggest_stolen'), message: 'Show me the stolen vehicle on the map' },
			{ key: 'events', label: t(lang, 'chat_suggest_events'), message: 'Which corridor events are active right now?' },
			{ key: 'units', label: t(lang, 'chat_suggest_units'), message: 'Where are the agency units right now?' },
		];
	});

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	function ask(s: Suggestion) {
		if (streaming) return;
		draft = s.message;
		send(s.label);
	}

	/**
	 * A proposed canvas move waits as a card on the map; the card only
	 * navigates — on a page without a canvas. The dock lives beside a map,
	 * so its review happens where the operator is (S2, audit UI-S6B).
	 */
	function openDirective(e: MouseEvent | null) {
		const where = reviewTarget(variant, workspace.view);
		e?.preventDefault();
		if (where.goto) {
			void goto(where.goto);
			return;
		}
		workspace.view = where.view;
	}

	/**
	 * A cited object: select it (one selection everywhere) and review it on
	 * the map. On the dock the canvas is mounted with hud 'wall', which never
	 * serves a queued `canvasBus.requestSelection` (only hud 'full' does —
	 * God's-eye canvas) — so the citation selects DIRECTLY: the Inspector
	 * fills and the current map stays. The /chat page has no canvas: queue
	 * the selection for the map it opens (audit E, S2).
	 */
	function openCitation(c: ChatCitation) {
		if (variant === 'page') {
			canvasBus.requestSelection(c.urn);
			const where = reviewTarget(variant, workspace.view);
			void goto(where.goto ?? '/gods-eye');
			return;
		}
		selection.select(c.urn, { fly: true, source: 'chat' });
		const where = reviewTarget(variant, workspace.view);
		if (where.goto) void goto(where.goto);
		else workspace.view = where.view;
	}

	function send(shown: string | null = null) {
		const text = draft.trim();
		if (!text || streaming) return;
		const sent = chat.send(
			text,
			{ movementId: ev ? movementIdOf(ev) : null, vvipClass: vvipClassOf(ev), eventId: evId ?? null, contextUrn: urn ?? null },
			shown,
		);
		if (sent) draft = '';
	}

	function clearConversation() {
		chat.clear(variant);
	}

	function stateLabel(s: ToolCall['state']): string {
		switch (s) {
			case 'pending':
				return citizenT(lang, 'chat_tool_pending');
			case 'running':
				return citizenT(lang, 'chat_tool_running');
			case 'success':
				return citizenT(lang, 'chat_tool_success');
			case 'error':
				return citizenT(lang, 'chat_tool_error');
		}
	}

	function tierLabel(tier: string): string {
		if (tier === 'decider') return citizenT(lang, 'chat_tier_decider');
		if (tier === 'gemma') return citizenT(lang, 'chat_tier_gemma');
		if (tier === 'heuristic') return citizenT(lang, 'chat_tier_heuristic');
		return tier;
	}

	/** A corridor event's state in this panel's language ("planned" → "Planned"). */
	function evState(state: string): string {
		const key = `asst_ev_state_${state}`;
		const word = L(key);
		return word === key ? state : word;
	}

	// ── the labelled sample turn (opt-in review state; no model is called) ──
	function pushSample() {
		const mark = 'MH47EM•••1';
		// pushed in place (never reassigned): the server render reads the same array the page will
		chat.messages.push(
			{ id: ++chat.seq, role: 'user', text: `Where has ${mark} been in the last hour, and what can I do now?`, thoughts: [], toolCalls: [], done: null, error: null, directives: [] },
			{
				id: ++chat.seq,
				role: 'agent',
				text: `It came down the west side north to south in 14 minutes: ${landmarkName('sea_link', 'en')} at 01:24, then ${landmarkName('worli_naka', 'en')} and ${landmarkName('haji_ali', 'en')} — last read 01:38 on EM-CAM-03. One decision waits: authorise a pursuit or dismiss the six sightings. I can't decide it for you.`,
				thoughts: [],
				toolCalls: [
					{ callId: 's1', toolName: 'city_get_dossier', state: 'success', durationMs: 40, summary: 'dossier of the watchlisted vehicle' },
					{ callId: 's2', toolName: 'city_feed', state: 'success', durationMs: 55, summary: '6 reads in the latest pass' },
					{ callId: 's3', toolName: 'list_enforcement_recommendations', state: 'success', durationMs: 62, summary: '1 decision waiting' },
				],
				done: {
					sessionId: 'sample-local',
					tiersUsed: ['heuristic:sample-local'],
					operatorAlerts: [],
					degraded: false,
					citations: [
						{ urn: 'vehicle:MH47EM4444', label: mark },
						{ urn: 'camera:EM-CAM-03', label: 'EM-CAM-03' },
					],
				},
				error: null,
				directives: [
					{
						id: 'sample-directive',
						verb: 'canvas_highlight',
						args: {},
						label: `highlight the 6 reads and fly to EM-CAM-03 (${mark})`,
						provenance: { sessionId: 'sample-local', tier: 'heuristic', confidence: null, toolCallId: 's2' },
					},
				],
			},
		);
	}

	/** Seed the labelled sample (also under svelte/server, where effects never run). */
	function ensureSample() {
		if (sample && messages.length === 0) pushSample();
	}

	ensureSample();
	$effect(() => {
		ensureSample();
	});
</script>

{#snippet scopeLine()}
	<section class="scope" data-testid="chat-context">
		{#if urn || ev}
			<span class="scope-line">
				{#if L('asst_scope_prefix')}<span class="scope-word">{L('asst_scope_prefix')}</span>{/if}
				<span class="scope-urn" data-testid="chat-context-event" title={urn ?? ev?.eventId ?? ''}>
					{#if urn}
						{#if urnParsed}
							<ObjectTag urn={urn} kind={urnParsed.kind} label={ops.text(urnRow?.label ?? urnParsed.id)} eventKind={urnParsed.kind === 'event' ? (ev?.eventKind ?? null) : null} />
						{:else}
							<b>{ops.text(urn)}</b>
						{/if}
					{:else if ev}
						{kindLabel(lang, ev.eventKind)} · <b>{ops.text(displayTitle(ev.name, lang) || ev.eventId.slice(0, 8))}</b>
						{#if ev.state}· <span class="state">{evState(ev.state)}</span>{/if}
						{#if vvipClassOf(ev)}· <span class="state">{vvipClassOf(ev)}</span>{/if}
					{/if}
				</span>
				{#if L('asst_scope_suffix')}<span class="scope-word">{L('asst_scope_suffix')}</span>{/if}
			</span>
		{:else}
			<span class="scope-none">{L('asst_scope_view')}</span>
		{/if}
	</section>
{/snippet}

<div class="panel" class:page={variant === 'page'} data-variant={variant}>
	<div class="cols">
		<!-- The conversation column: a 760 px measure on the page variant. -->
		<section class="convo">
			{#if degraded}
				<p class="degraded" data-testid="chat-degraded">{citizenT(lang, 'chat_offline_note')}</p>
			{/if}

				<div class="stream" bind:this={scrollEl} data-testid="chat-stream">
					{#if messages.length === 0}
						<!-- The page header already carries the subtitle (the page
							variant's copy must not state it twice). -->
						<NonIdealState icon="chat" title={L('asst_empty_title')} description={variant === 'page' ? null : L('asst_page_sub')} />
						<div class="suggest" data-testid="chat-suggestions">
							<span class="suggest-label">{t(lang, 'chat_suggest_title')}</span>
							{#each suggestions as s (s.key)}
								<Button minimal small onclick={() => ask(s)} data-suggest={s.key}>{s.label}</Button>
							{/each}
						</div>
					{:else}
					{#each messages as m (m.id)}
						{@const answer = m.role === 'agent' ? answerOf(m) : null}
						{@const split = answer?.prose ? splitLookups(answer.prose) : null}
						{@const grounding = m.role === 'agent' && m.done ? groundingOf(m.done) : null}
						<article class="msg role-{m.role}" data-msg-role={m.role}>
							<span class="who">{m.role === 'user' ? citizenT(lang, 'chat_you') : L('asst_actor')}</span>

							{#if m.role === 'agent' && m.thoughts.length}
								<details class="thoughts" open={showThoughts}>
									<summary>{citizenT(lang, 'chat_thoughts')} · <span class="fig">{m.thoughts.length}</span></summary>
									{#each m.thoughts as th, i (i)}
										<p class="thought">
											<span class="fig idx">{th.stepIndex}</span>
											{#if th.tier}<span class="tier-tag" data-tier={th.tier}>{tierLabel(th.tier)}</span>{/if}
											{ops.text(th.text)}
										</p>
									{/each}
								</details>
							{/if}

							{#if m.role === 'agent' && (m.toolCalls.length || split?.lookups)}
								<ul class="steps" class:collapsed={!showSteps}>
									{#each m.toolCalls as tc, i (i)}
										<li class="step state-{tc.state}" data-tool-state={tc.state} data-testid="chat-tool-card" hidden={!showSteps}>
											<Icon name={tc.state === 'error' ? 'cross' : 'tick-circle'} size={14} />
											<span class="step-label">{displayTool(tc.toolName)}</span>
											<span class="step-state">{stateLabel(tc.state)}</span>
											{#if tc.durationMs != null}
												<span class="fig step-dur">{tc.durationMs} ms</span>
											{/if}
											{#if tc.summary}
												<span class="step-summary">{ops.text(tc.summary)}</span>
											{/if}
										</li>
									{/each}
									{#if split?.lookups}
										<!-- the lookups' raw detail is diagnostics: in the collapsed steps, never the answer -->
										<li class="step lookups" data-testid="chat-lookups" hidden={!showSteps}>
											<Icon name="search" size={14} />
											<span class="step-label">{L('asst_lookups_label')}</span>
											<span class="step-summary">{ops.text(split.lookups)}</span>
										</li>
									{/if}
								</ul>
							{/if}

							{#if m.role === 'user'}
								<p class="body">{ops.text(m.text)}</p>
							{:else if answer?.prose}
								{#if answer.action}
									<span class="action-tag">{citizenT(lang, 'chat_action')} · {answer.action}</span>
								{/if}
								<p class="body prose" data-testid="chat-answer">{ops.text(split?.answer ?? answer.prose)}</p>
								{#if grounding?.removed}
									<p class="grounding" data-testid="chat-grounding-removed" data-removed={grounding.removed}>{L('asst_grounding_removed', grounding.removed)}</p>
								{/if}
							{:else if answer?.raw}
								<p class="no-prose" data-testid="chat-no-prose">{citizenT(lang, 'chat_raw_envelope')}</p>
								<pre class="raw">{ops.text(answer.raw)}</pre>
							{:else if streaming && m === messages[messages.length - 1]}
								<p class="body dim">…</p>
							{/if}

							{#if m.role === 'agent' && m.error}
								<p class="msg-error">{ops.text(m.error)}</p>
							{/if}

							{#if m.role === 'agent' && m.directives.length}
								<!-- Link card to the map — the proposal's home. No Apply here.
									On the dock the card stays on the current map (review-target). -->
								<div class="cards">
									{#each m.directives as d (d.id)}
										<a class="card" href="/gods-eye" onclick={(e) => openDirective(e)} data-directive={d.verb}>
											<span class="card-title">{L('asst_proposed_map', ops.text(d.label.replace(/^(track|fly to|highlight|note on|sensor|layer)\s+/i, '')))}</span>
											<span class="card-sub">{L('asst_review_map')}</span>
											<Icon name="chevron-right" size={14} />
										</a>
									{/each}
								</div>
							{/if}

							{#if m.role === 'agent' && m.done && (m.done.tiersUsed.length || m.done.degraded || m.done.citations.length || sessionId)}
								<!-- Details: raw tool names, model, tier and session. In the DOM while closed. -->
								<details class="details">
									<summary>{L('asst_details')}</summary>
									{#if m.toolCalls.length}
										<div class="details-row">
											<span class="details-k">{L('asst_details_tools')}</span>
											<span class="details-v">{m.toolCalls.map((tc) => tc.toolName).join(', ')}</span>
										</div>
									{/if}
									{#if m.done?.tiersUsed.length}
										<div class="details-row" data-testid="chat-tiers">
											<span class="details-k">{citizenT(lang, 'chat_tiers')}</span>
											<span class="details-v tiers">
												{#each m.done.tiersUsed as entry, i (i)}
													{@const tier = parseTier(entry)}
													<span class="tier-chip" data-tier={tier.tier} title={tier.model ?? tier.tier}>
														{tierLabel(tier.tier)}{#if tier.model}&nbsp;· {tier.model}{/if}
													</span>
												{/each}
												{#if m.done.degraded}<span class="tier-chip degraded">{citizenT(lang, 'chat_degraded_turn')}</span>{/if}
											</span>
										</div>
									{/if}
									{#if sessionId || m.done?.sessionId}
										<div class="details-row" data-testid="chat-session">
											<span class="details-k">{L('asst_details_session')}</span>
											<span class="details-v">{sessionId ?? m.done?.sessionId ?? ''}</span>
										</div>
									{/if}
								</details>
							{/if}

							{#if m.role === 'agent' && grounding && grounding.alerts.length}
								<ul class="alerts" aria-label={citizenT(lang, 'chat_alerts')}>
									{#each grounding.alerts as alert, i (i)}
										<li>{ops.text(alert)}</li>
									{/each}
								</ul>
							{/if}

							{#if m.role === 'agent' && m.done && m.done.citations.length && variant === 'dock'}
								<!-- Inline citations on the dock; the page lists them in its context column. -->
								<div class="cites">
									<span class="cites-label">{t(lang, 'chat_cited')}</span>
									{#each m.done.citations as c (c.urn)}
										{@const p = citationParts(c.urn)}
										<!-- Dock copy: the citation selects on the CURRENT map —
											"Open in City command" would lie here (audit E, S3). -->
										<button type="button" class="cite" title={`${c.urn} — ${L('asst_cite_select_map')}`} onclick={() => openCitation(c)}>
											{#if p}
												<ObjectTag urn={c.urn} kind={p.kind} label={ops.text(c.label)} />
											{:else}
												{ops.text(c.label)}
											{/if}
										</button>
									{/each}
								</div>
							{/if}
						</article>
					{/each}
					{#if sample}
						<p class="sample-note">{L('asst_sample_note')}</p>
					{/if}
				{/if}
			</div>

			{#if messages.length > 0 && !streaming}
				<div class="suggest compact" data-testid="chat-suggestions">
					{#each suggestions as s (s.key)}
						<Button minimal small onclick={() => ask(s)} data-suggest={s.key}>{s.label}</Button>
					{/each}
				</div>
			{/if}

			{@render scopeLine()}

			<div class="toggles">
				<Switch small checked={showSteps} onchange={(v) => (showSteps = v)} label={L('asst_steps_toggle')} />
				<Switch small checked={showThoughts} onchange={(v) => (showThoughts = v)} label={L('asst_thoughts_toggle')} />
				{#if messages.length}
					<Button minimal small icon="trash" onclick={clearConversation}>{L('asst_clear')}</Button>
				{/if}
			</div>

			<form
				class="composer"
				onsubmit={(e) => {
					e.preventDefault();
					send();
				}}
			>
				<input
					type="text"
					bind:value={draft}
					placeholder={citizenT(lang, 'chat_placeholder')}
					aria-label={citizenT(lang, 'chat_placeholder')}
					data-testid="chat-input"
				/>
				<Button type="submit" intent="primary" small loading={streaming} disabled={!draft.trim() || streaming}>
					{citizenT(lang, 'chat_send')}
				</Button>
			</form>
		</section>

		{#if variant === 'page'}
			<!-- The context column (≥ 1440 px); a drawer below it. -->
			<aside class="aside">
				<Section title={L('asst_context_title')} icon="properties">
					{#if urn}
						<div class="ctx-scope">
							{#if urnParsed}
								<!-- The world's label (a masked mark), never the raw uuid — the
									scope line below shows the same words (audit E, S3). -->
								<ObjectTag urn={urn} kind={urnParsed.kind} label={ops.text(urnRow?.label ?? urnParsed.id)} eventKind={urnParsed.kind === 'event' ? (ev?.eventKind ?? null) : null} />
							{:else}
								<span class="ctx-raw">{urn}</span>
							{/if}
						</div>
					{:else if ev}
						<div class="ctx-scope">
							<span class="ctx-raw">{kindLabel(lang, ev.eventKind)} · {ops.text(displayTitle(ev.name, lang) || ev.eventId.slice(0, 8))}</span>
						</div>
					{:else}
						<p class="ctx-none">{L('asst_context_none')}</p>
						<p class="ctx-none-note">{L('asst_context_hint')}</p>
					{/if}
				</Section>

				{#if scopeUnits.length}
					<Section title={L('asst_decisions')} icon={scopeUnits.length > 9 ? 'dot' : 'inbox'}>
						<!-- Link cards to each decision's ONE home. No Approve here. -->
						{#each scopeUnits as u (u.kind + ':' + u.id)}
							{@const link = homeLink(u.kind, u.id, '/')}
							<a class="card" href={link.href}>
								<span class="card-title">{ops.text(u.title)}</span>
								<span class="card-sub">{link.label}</span>
								<Icon name="chevron-right" size={14} />
							</a>
						{/each}
					</Section>
				{/if}

				{#if messages.some((m) => m.done?.citations.length)}
					<Section title={L('asst_citations')} icon="link">
						<div class="cites col">
							{#each messages.filter((m) => m.done?.citations.length) as m (m.id)}
								{#each m.done?.citations ?? [] as c (c.urn)}
									{@const p = citationParts(c.urn)}
									<!-- Page copy: the citation opens the map route. -->
									<button type="button" class="cite" title={`${c.urn} — ${t(lang, 'chat_open_city')}`} onclick={() => openCitation(c)}>
										{#if p}
											<ObjectTag urn={c.urn} kind={p.kind} label={ops.text(c.label)} />
										{:else}
											{ops.text(c.label)}
										{/if}
									</button>
								{/each}
							{/each}
						</div>
					</Section>
				{/if}

				{#if messages.some((m) => m.directives.length)}
					<Section title={t(lang, 'chat_directives')} icon="map">
						{#each messages.filter((m) => m.directives.length) as m (m.id)}
							{#each m.directives as d (d.id)}
								<a class="card" href="/gods-eye" onclick={(e) => openDirective(e)} data-directive={d.verb}>
									<span class="card-title">{L('asst_proposed_map', ops.text(d.label.replace(/^(track|fly to|highlight|note on|sensor|layer)\s+/i, '')))}</span>
									<span class="card-sub">{L('asst_review_map')}</span>
									<Icon name="chevron-right" size={14} />
								</a>
							{/each}
						{/each}
					</Section>
				{/if}
			</aside>
		{/if}
	</div>

	{#if variant === 'page'}
		{#if vw < 1440}
			<Button minimal small class="ctx-fab" icon="drawer-right" onclick={() => (ctxOpen = !ctxOpen)}>
				{L('asst_context_title')}
			</Button>
		{/if}
		<Drawer bind:open={ctxOpen} title={L('asst_context_title')} position="right" size="400px">
			{#if urn || ev}
				<div class="ctx-scope">
					{#if urn}
						{#if urnParsed}
							<ObjectTag urn={urn} kind={urnParsed.kind} label={ops.text(urnRow?.label ?? urnParsed.id)} eventKind={urnParsed.kind === 'event' ? (ev?.eventKind ?? null) : null} />
						{:else}
							<span class="ctx-raw">{urn}</span>
						{/if}
					{:else if ev}
						<span class="ctx-raw">{kindLabel(lang, ev.eventKind)} · {ops.text(displayTitle(ev.name, lang) || ev.eventId.slice(0, 8))}</span>
					{/if}
				</div>
			{:else}
				<p class="ctx-none">{L('asst_context_none')}</p>
				<p class="ctx-none-note">{L('asst_context_hint')}</p>
			{/if}
		</Drawer>
	{/if}
</div>

<svelte:window bind:innerWidth={vw} />

<style>
	.panel {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		gap: var(--v-gap-panel);
		color: var(--v-ink-1);
	}

	/* The dock tab has the dock's own padding — its scope line and composer
	 * never sit on the dock's edge, and Send never clips (S3, audit). */
	.panel[data-variant='dock'] {
		padding: var(--v-space-2) var(--v-space-3);
	}

	.cols {
		flex: 1;
		min-height: 0;
		display: flex;
		gap: var(--v-gap-panel);
	}

	.convo {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: var(--v-gap-panel);
	}

	/* The page variant: ONE centred grid — the conversation at its 760 px
	 * measure, the context column beside it, the pair centred as a unit and
	 * the page header aligned to the same columns (S3, audit UI-S6B). */
	.panel.page .cols {
		display: grid;
		grid-template-columns: minmax(0, 760px) 360px;
		justify-content: center;
		gap: var(--v-gap-panel);
	}

	.panel.page .convo {
		min-width: 0;
	}

	.panel.page .aside {
		border-left: 1px solid var(--v-line-1);
		padding-left: var(--v-gap-panel);
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: var(--v-gap-panel);
	}

	@media (max-width: 1439px) {
		.panel.page .aside {
			display: none;
		}

		.panel.page .cols {
			grid-template-columns: minmax(0, 1fr);
		}
	}

	.ctx-fab {
		align-self: flex-end;
	}

	.scope {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: var(--v-space-1) var(--v-space-3);
		padding: var(--v-space-2) var(--v-space-3);
		background: var(--v-surface-2);
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-chip);
		font-size: var(--v-text-xs);
	}

	/* "Scoped to <subject> and this view" — the words wrap around the tag. */
	.scope-line {
		display: inline-flex;
		align-items: center;
		flex-wrap: wrap;
		gap: var(--v-space-1) var(--v-space-2);
	}

	.scope-word {
		color: var(--v-ink-2);
	}

	.scope-urn {
		display: inline-flex;
		align-items: center;
		gap: var(--v-space-2);
		color: var(--v-ink-1);
	}

	.scope-none {
		color: var(--v-ink-3);
	}

	.state {
		color: var(--v-ink-2);
	}

	.degraded {
		margin: 0;
		padding: var(--v-space-2) var(--v-space-3);
		border: 1px solid color-mix(in srgb, var(--v-danger-text) 45%, transparent);
		border-radius: var(--v-radius-chip);
		color: var(--v-danger-text);
		font-size: var(--v-text-xs);
	}

	.stream {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: var(--v-space-3);
		padding-right: var(--v-space-1);
	}

	.msg {
		display: flex;
		flex-direction: column;
		gap: var(--v-space-2);
		padding: var(--v-space-3);
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
	}

	.msg.role-user {
		background: var(--v-surface-2);
	}

	.who {
		font-size: var(--v-text-2xs);
		font-weight: var(--v-weight-status);
		color: var(--v-ink-3);
	}

	.steps {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: var(--v-space-1);
	}

	/* Collapsed steps stay in the DOM (Details holds the raw names) — hidden,
	 * never removed, so a test that counts them still sees one per call; and
	 * [hidden] beats the flex row below (the audit's S2). */
	.step[hidden] {
		display: none;
	}

	.step {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: var(--v-space-2);
		padding: var(--v-space-2) var(--v-space-3);
		border: 1px solid var(--v-line-1);
		border-left: 2px solid var(--v-ai);
		border-radius: var(--v-radius-chip);
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.step[data-tool-state='error'] .step-state {
		color: var(--v-danger-text);
	}

	.step-label {
		color: var(--v-ink-1);
	}

	.step-state {
		color: var(--v-ink-3);
	}

	/* Figures on this panel are text: ink-2 keeps them at AA (the audit's
	 * contrast list named the step durations). */
	.step-dur {
		color: var(--v-ink-2);
	}

	.step-summary {
		flex-basis: 100%;
		color: var(--v-ink-2);
	}

	.body {
		margin: 0;
		white-space: pre-wrap;
		font-size: var(--v-text-sm);
		line-height: 1.55;
		color: var(--v-ink-1);
	}

	.body.dim {
		color: var(--v-ink-3);
	}

	.action-tag {
		align-self: flex-start;
		font-size: var(--v-text-2xs);
		color: var(--v-ink-3);
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-chip);
		padding: 0 var(--v-space-2);
	}

	.no-prose {
		margin: 0;
		font-size: var(--v-text-xs);
		color: var(--v-ink-3);
	}

	.raw {
		margin: 0;
		max-height: 12rem;
		overflow: auto;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		font-size: var(--v-text-2xs);
		color: var(--v-ink-3);
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-chip);
		padding: var(--v-space-2);
	}

	.msg-error {
		margin: 0;
		font-size: var(--v-text-2xs);
		color: var(--v-danger-text);
		overflow-wrap: anywhere;
	}

	.thoughts {
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-chip);
		padding: var(--v-space-2) var(--v-space-3);
		font-size: var(--v-text-xs);
	}

	.thoughts summary {
		cursor: pointer;
		color: var(--v-ink-3);
	}

	.thought {
		margin: var(--v-space-1) 0 0;
		color: var(--v-ink-2);
	}

	.idx {
		margin-right: var(--v-space-1);
		color: var(--v-ink-3);
	}

	.tier-tag {
		font-size: var(--v-text-2xs);
		margin-right: var(--v-space-1);
		color: var(--v-ai-text);
	}

	/* Details: the raw machinery under a quiet disclosure. */
	.details {
		border-top: 1px solid var(--v-line-1);
		padding-top: var(--v-space-2);
		font-size: var(--v-text-xs);
	}

	.details summary {
		cursor: pointer;
		color: var(--v-ink-3);
	}

	.details-row {
		display: flex;
		gap: var(--v-space-2);
		margin-top: var(--v-space-1);
		align-items: baseline;
	}

	.details-k {
		flex: 0 0 7em;
		color: var(--v-ink-3);
	}

	.details-v {
		color: var(--v-ink-2);
		overflow-wrap: anywhere;
	}

	.tiers {
		display: flex;
		flex-wrap: wrap;
		gap: var(--v-space-1);
	}

	.tier-chip {
		font-size: var(--v-text-2xs);
		color: var(--v-ink-2);
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-pill);
		padding: 0 var(--v-space-2);
	}

	.tier-chip.degraded {
		color: var(--v-warning-text);
	}

	/* the grounding check's removals: one plain line under the answer */
	.grounding {
		margin: 0;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.alerts {
		margin: 0;
		padding-left: var(--v-space-4);
		font-size: var(--v-text-xs);
		color: var(--v-warning-text);
	}

	/* Link cards: the proposal's home, never a second control. */
	.cards {
		display: flex;
		flex-direction: column;
		gap: var(--v-space-1);
	}

	.card {
		display: flex;
		align-items: center;
		gap: var(--v-space-2);
		padding: var(--v-space-2) var(--v-space-3);
		border: 1px solid var(--v-line-1);
		border-left: 2px solid var(--v-ai);
		border-radius: var(--v-radius-chip);
		color: var(--v-ink-1);
		text-decoration: none;
		font-size: var(--v-text-xs);
	}

	.card:hover {
		border-color: var(--v-line-2);
		background: var(--v-surface-2);
	}

	.card-title {
		flex: 1;
		min-width: 0;
	}

	.card-sub {
		color: var(--v-ink-3);
		white-space: nowrap;
	}

	.cites {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--v-space-1);
	}

	.cites.col {
		flex-direction: column;
		align-items: flex-start;
	}

	.cites-label {
		font-size: var(--v-text-2xs);
		color: var(--v-ink-3);
	}

	.cite {
		font: inherit;
		font-size: var(--v-text-2xs);
		background: transparent;
		border: none;
		padding: 0;
		cursor: pointer;
		color: var(--v-ink-1);
	}

	.cite:focus-visible {
		outline: 1px solid var(--v-act-focus);
		outline-offset: 2px;
	}

	.suggest {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: center;
		gap: var(--v-space-2);
	}

	/* In the dock the chips wrap from the left, like every other dock list. */
	.panel[data-variant='dock'] .suggest {
		justify-content: flex-start;
	}

	.suggest.compact {
		justify-content: flex-start;
	}

	.suggest-label {
		font-size: var(--v-text-2xs);
		color: var(--v-ink-3);
	}

	/* The suggestion chips read at the panel's text size, not as headings
	 * (audit E: the minimal Button's 14 px against 12 px panel text). */
	.suggest :global([data-ui='button']) {
		font-size: var(--v-text-xs);
		/* a suggestion reads as a pill to tap, not as loose text (the V3 assistant's chips) */
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-pill);
		padding-inline: var(--v-space-3);
	}

	.toggles {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: var(--v-space-2) var(--v-space-4);
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	/* On the dock the scope is ONE quiet line (the prototype): no frame, and
	 * a long subject or event name truncates instead of wrapping (audit E,
	 * S3) — every flex child of the line shrinks under an ellipsis. */
	.panel[data-variant='dock'] .scope {
		flex-wrap: nowrap;
		border: none;
		background: transparent;
		padding: 0;
	}

	.panel[data-variant='dock'] .scope-line {
		flex-wrap: nowrap;
		min-width: 0;
	}

	/* only the SUBJECT gives way (one ellipsis); "Scoped to" and "and this view" stay whole (audit E-ASSIST R2) */
	.panel[data-variant='dock'] .scope-line > * {
		flex: 0 0 auto;
		white-space: nowrap;
	}

	.panel[data-variant='dock'] .scope-line > .scope-urn {
		flex: 0 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.panel[data-variant='dock'] .scope-urn .state {
		display: none; /* the dock line names the subject; its state reads in the Inspector */
	}

	.composer {
		display: flex;
		gap: var(--v-space-2);
	}

	.composer input {
		flex: 1;
		min-width: 0;
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-btn);
		padding: var(--v-space-2) var(--v-space-3);
		font: inherit;
		font-size: var(--v-text-sm);
		background: var(--v-surface-1);
		color: var(--v-ink-1);
		height: var(--v-ctl-lg);
	}

	.composer input:focus-visible {
		outline: 1px solid var(--v-act-focus);
		outline-offset: 2px;
	}

	.sample-note {
		margin: 0;
		font-size: var(--v-text-2xs);
		color: var(--v-ink-3);
	}

	.ctx-raw {
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.ctx-none {
		margin: 0;
		font-size: var(--v-text-sm);
		color: var(--v-ink-2);
	}

	.ctx-none-note {
		margin: var(--v-space-1) 0 0;
		font-size: var(--v-text-xs);
		color: var(--v-ink-3);
	}
</style>
