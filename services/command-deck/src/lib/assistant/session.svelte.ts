/**
 * The assistant's conversation logic, shared by every surface that talks to the brain (V3-P4): the v2 AssistantPanel
 * (the Analyst dock tab and /chat) and the V3 Assistant (/assistant). One implementation of the turn — no copy:
 *
 *   ChatSession   the turns (a deep $state proxy), the brain session carried across follow-ups, the stream's
 *                 lifecycle (send → tokens / thoughts / tool calls / directives → done | error), "a new event
 *                 opens a new session", clear, and keeping the conversation when the panel unmounts
 *                 (conversation.ts: a citation or a page change remounts it).
 *   answerOf      the answer as prose (contract C-D streams prose; an older brain's JSON envelope gives its
 *                 prose field, else an honest "no prose answer" with the envelope kept verbatim).
 *   parseTier     "decider:pplx-…" → { tier, model } (diagnostics; the V3 page never prints the model).
 *   citationParts a cited urn's tag parts (a label-shaped urn keeps its kind prefix).
 *
 * It READS and PROPOSES, never decides: streamChat is the read-only chat client; every map directive the brain
 * streams is queued on the canvas bus for a human to review on the map (canvasBus.offer) — never applied here.
 *
 * Svelte 5 note (kept from the panel): `messages` is a deep $state proxy — streamed tokens are written to the
 * proxied entry (messages[i]), never to the pushed literal (the reply bubble used to stay empty).
 */
import { streamChat, type ChatDirective, type ChatDone, type ChatTier } from '$lib/api/client';
import { canvasBus } from '$lib/gods-eye/canvas-bus.svelte';
import { isEntityKind, parseUrn } from '$lib/gods-eye/city-api';
import type { VvipClass } from '$lib/types';
import { forgetConversation, keepConversation, type KeptConversation } from './conversation';

export interface ToolCall {
	callId: string;
	toolName: string;
	state: 'pending' | 'running' | 'success' | 'error';
	durationMs: number | null;
	summary: string | null;
}

export interface Thought {
	stepIndex: number;
	text: string;
	tier: ChatTier | null;
}

export interface Message {
	id: number;
	role: 'user' | 'agent';
	text: string;
	thoughts: Thought[];
	toolCalls: ToolCall[];
	/** done.data of the finished turn (null while streaming / on error). */
	done: ChatDone | null;
	error: string | null;
	/** Map proposals the turn made (link cards to the map — never Apply). */
	directives: ChatDirective[];
	/** When the turn was asked and when it finished (epoch ms; the V3 "how long it took"). */
	at?: number;
	doneAt?: number | null;
}

/** What one turn is scoped to on the wire (C-D2). */
export interface TurnScope {
	movementId: string | null;
	vvipClass: VvipClass | null;
	eventId: string | null;
	contextUrn: string | null;
}

export class ChatSession {
	messages = $state<Message[]>([]);
	streaming = $state(false);
	degraded = $state(false);
	/** Brain session carried across follow-ups (done.data.session_id). */
	sessionId = $state<string | null>(null);
	/** The id of the newest message (the next one is ++seq). */
	seq = 0;
	/** The scope the brain session belongs to (its event id, '' for the city). */
	scope = '';
	#controller: AbortController | null = null;

	constructor(prior: KeptConversation<Message> | null = null) {
		if (prior) {
			this.messages = prior.messages;
			this.sessionId = prior.sessionId;
			this.seq = prior.seq;
			this.scope = prior.scope;
		}
	}

	/**
	 * A new EVENT opens a new session (the brain scopes a session to its event). Selecting a cited vehicle or camera
	 * keeps the session: the officer is still asking about the same situation.
	 */
	rescope(key: string): void {
		if (this.scope && key !== this.scope) {
			this.sessionId = null;
			this.#controller?.abort();
			this.#controller = null;
			this.streaming = false;
		}
		this.scope = key;
	}

	/** The newest message, as the proxied entry. */
	get last(): Message | undefined {
		return this.messages[this.messages.length - 1];
	}

	/**
	 * Ask: `text` goes on the wire, `shown` (when given) is what the user bubble says (a suggestion's label).
	 * Returns false when nothing was sent (empty, or a turn is still streaming).
	 */
	send(text: string, scope: TurnScope, shown: string | null = null): boolean {
		const q = text.trim();
		if (!q || this.streaming) return false;
		const at = Date.now();
		this.messages.push({ id: ++this.seq, role: 'user', text: shown ?? q, thoughts: [], toolCalls: [], done: null, error: null, directives: [], at });
		this.messages.push({ id: ++this.seq, role: 'agent', text: '', thoughts: [], toolCalls: [], done: null, error: null, directives: [], at, doneAt: null });
		// The PROXIED entry — writes to it re-render; writes to the pushed literal would be invisible.
		const r = this.messages[this.messages.length - 1];
		this.streaming = true;
		this.degraded = false;
		this.#controller?.abort();
		const ctrl = new AbortController();
		this.#controller = ctrl;

		streamChat(
			q,
			scope.movementId,
			scope.vvipClass,
			{
				onToken: (tok) => (r.text += tok),
				onDirective: (d) => {
					r.directives.push(d);
					// queued for a human to review on the map — never applied here
					canvasBus.offer(d, null);
				},
				onThought: (s) => r.thoughts.push({ stepIndex: s.stepIndex, text: s.text, tier: s.tier }),
				onToolCall: (c) => {
					const open = r.toolCalls.find((tc) => tc.callId === c.callId && (tc.state === 'pending' || tc.state === 'running'));
					if (open) open.state = c.state;
					else r.toolCalls.push({ callId: c.callId, toolName: c.toolName, state: c.state, durationMs: null, summary: null });
				},
				onToolResult: (res) => {
					const tc =
						r.toolCalls.findLast((x) => x.callId === res.callId && (x.state === 'pending' || x.state === 'running')) ??
						r.toolCalls.findLast((x) => x.callId === res.callId);
					if (tc) {
						tc.state = res.state;
						tc.durationMs = res.durationMs;
						tc.summary = res.summary;
					} else {
						r.toolCalls.push({ callId: res.callId, toolName: res.toolName ?? res.callId, state: res.state, durationMs: res.durationMs, summary: res.summary });
					}
				},
				onDone: (d) => {
					r.done = d;
					r.doneAt = Date.now();
					if (d.sessionId) this.sessionId = d.sessionId;
					this.streaming = false;
				},
				onError: (e) => {
					if (ctrl.signal.aborted) return;
					r.error = e.message;
					r.doneAt = Date.now();
					this.streaming = false;
					this.degraded = true;
				},
			},
			{ sessionId: this.sessionId, signal: ctrl.signal, eventId: scope.eventId ?? null, contextUrn: scope.contextUrn ?? undefined },
		).catch((e) => {
			// streamChat rejects outright when fetch itself fails (proxy down / request aborted) — the callbacks never
			// run, so the streaming state is cleared here too.
			if (ctrl.signal.aborted) return;
			r.error = e instanceof Error ? e.message : String(e);
			r.doneAt = Date.now();
			this.streaming = false;
			this.degraded = true;
		});
		return true;
	}

	/** Forget the turns and the brain session ("Clear conversation"). */
	clear(variant: string): void {
		this.#controller?.abort();
		this.#controller = null;
		this.messages = [];
		this.sessionId = null;
		this.streaming = false;
		this.degraded = false;
		forgetConversation(variant);
	}

	/**
	 * The surface unmounts: a turn cut off says so (`interrupted`, in the officer's language) — it is never left
	 * "thinking" forever — and the conversation is kept for the next mount of the same variant.
	 */
	release(variant: string, interrupted: string): void {
		if (this.streaming) {
			const last = this.last;
			if (last?.role === 'agent' && !last.done && !last.error) last.error = interrupted;
		}
		this.#controller?.abort();
		keepConversation<Message>(variant, { messages: $state.snapshot(this.messages) as Message[], sessionId: this.sessionId, seq: this.seq, scope: this.scope });
	}
}

/** "decider:pplx-decider-v1.2" → {tier:'decider', model:'pplx-…'}. */
export function parseTier(entry: string): { tier: string; model: string | null } {
	const i = entry.indexOf(':');
	return i < 0 ? { tier: entry, model: null } : { tier: entry.slice(0, i), model: entry.slice(i + 1) || null };
}

export const PROSE_FIELDS = ['answer', 'final_answer', 'response', 'reasoning', 'summary', 'message', 'text'];

export interface Answer {
	prose: string | null;
	raw: string | null;
	action: string | null;
	pending: boolean;
}

/**
 * The answer as prose. Contract C-D streams prose tokens; an older brain streams its JSON envelope instead — take
 * its prose field, else say there is none and keep the envelope verbatim (never shown as prose).
 */
export function answerOf(m: Pick<Message, 'text' | 'done' | 'error'>): Answer {
	const text = m.text.trim();
	if (!text) return { prose: null, raw: null, action: null, pending: false };
	if (!text.startsWith('{')) return { prose: m.text, raw: null, action: null, pending: false };
	const finished = m.done !== null || m.error !== null;
	try {
		const obj = JSON.parse(text) as unknown;
		const rec = obj && typeof obj === 'object' && !Array.isArray(obj) ? (obj as Record<string, unknown>) : {};
		const field = PROSE_FIELDS.find((k) => typeof rec[k] === 'string' && (rec[k] as string).trim());
		const action = typeof rec.action === 'string' && rec.action !== 'call_tool' ? rec.action : null;
		return { prose: field ? String(rec[field]) : null, raw: text, action, pending: false };
	} catch {
		// Mid-stream a JSON envelope is not parseable yet: wait for it.
		return finished ? { prose: m.text, raw: null, action: null, pending: false } : { prose: null, raw: null, action: null, pending: true };
	}
}

/**
 * A citation's tag parts: the parsed urn, else its kind prefix when that prefix is a real entity kind — a brain may
 * cite a label-shaped urn (`vehicle:<its mark>`), and a cited mark is always an object tag.
 */
export function citationParts(urn: string): { kind: string; id: string } | null {
	const p = parseUrn(urn);
	if (p) return p;
	const i = urn.indexOf(':');
	if (i <= 0) return null;
	const kind = urn.slice(0, i);
	return isEntityKind(kind) ? { kind, id: urn.slice(i + 1) } : null;
}
