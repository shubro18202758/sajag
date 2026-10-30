<script lang="ts">
	/**
	 * "Ask about it" (V3-SPEC §3.5 #29) — the assistant explains this record, grounded in it (the v2 inspector's
	 * Explain: one streamed chat turn with `contextUrn`, the same client). READ ONLY: an answer never changes
	 * anything; a map proposal it makes is only offered on the map (canvasBus.offer), never applied. ONE request
	 * per press (a second press while one streams does nothing). Without a named duty officer every
	 * registration mark in the answer is masked, in any spelling (workspace/mask.ts).
	 */
	import { onDestroy, onMount } from 'svelte';
	import { streamChat } from '$lib/api/client';
	import { canvasBus } from '$lib/gods-eye/canvas-bus.svelte';
	import { parseUrn } from '$lib/gods-eye/city-api';
	import { maskMarks } from '$lib/workspace/mask';
	import { ops } from '$lib/ops/store.svelte';
	import { t } from '$lib/i18n/strings';
	import './packs.object';
	import Glyph from '../Glyph.svelte';

	let {
		urn,
		lang,
		onclose,
		status = $bindable('streaming'),
	}: { urn: string; lang: string; onclose: () => void; status?: 'streaming' | 'done' | 'error' } = $props();

	let text = $state('');
	let ctrl: AbortController | null = null;

	/** One turn per mount: the page re-keys the panel for the next question, never while one streams. */
	function ask() {
		const c = new AbortController();
		ctrl = c;
		text = '';
		status = 'streaming';
		const p = parseUrn(urn);
		void streamChat(
			t(lang, 'obj_ask_prompt'),
			null,
			null,
			{
				onToken: (tok) => {
					text += tok;
				},
				onThought: () => {},
				onToolCall: () => {},
				onToolResult: () => {},
				onDirective: (d) => canvasBus.offer(d, null),
				onDone: () => {
					status = 'done';
				},
				onError: () => {
					if (!c.signal.aborted) status = 'error';
				},
			},
			{ signal: c.signal, contextUrn: urn, eventId: p?.kind === 'event' ? p.id : null },
		).catch(() => {
			if (!c.signal.aborted) status = 'error';
		});
	}

	function stop() {
		ctrl?.abort();
		ctrl = null;
		status = text ? 'done' : 'error';
	}

	onMount(ask);
	onDestroy(() => ctrl?.abort());

	const shown = $derived(ops.officerOn ? text : maskMarks(text));
</script>

<aside class="ask" data-testid="obj-ask" aria-live="polite" aria-busy={status === 'streaming'}>
	<div class="head">
		<span class="by"><Glyph name="spark" size={16} />{t(lang, 'obj_ask_by')}</span>
		{#if status === 'streaming'}<button type="button" class="lnk" onclick={stop}>{t(lang, 'obj_ask_stop')}</button>{/if}
		<button type="button" class="x" aria-label={t(lang, 'obj_ask_close')} onclick={onclose}><Glyph name="close" size={16} /></button>
	</div>
	<p class="ans" data-testid="obj-ask-answer" data-status={status}>
		{shown || (status === 'error' ? t(lang, 'obj_ask_failed') : t(lang, 'obj_ask_working'))}
	</p>
	{#if !ops.officerOn}<p class="note">{t(lang, 'obj_ask_masked')}</p>{/if}
</aside>

<style>
	.ask {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 16px 18px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-l);
		background: linear-gradient(var(--v3-ai-veil), var(--v3-ai-veil)), var(--v3-s1);
	}

	.head {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.by {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--v3-ai-text);
		font-size: var(--v3-text-meta);
		font-weight: 650;
	}

	.lnk {
		margin-left: auto;
		padding: 0;
		border: 0;
		background: none;
		color: var(--v3-brand-text);
		font: inherit;
		font-size: var(--v3-text-meta);
		font-weight: 600;
		cursor: pointer;
	}

	.x {
		display: grid;
		place-items: center;
		width: 32px;
		height: 32px;
		margin-left: auto;
		border: 0;
		border-radius: 16px;
		background: none;
		color: var(--v3-t2);
		cursor: pointer;
	}

	.lnk + .x {
		margin-left: 0;
	}

	.x:hover {
		background: var(--v3-s3);
	}

	.lnk:focus-visible,
	.x:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.ans {
		margin: 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-body);
		line-height: 24px;
		white-space: pre-wrap;
	}

	.note {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}
</style>
