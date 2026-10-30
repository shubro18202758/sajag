<script lang="ts">
	/**
	 * ContextPanel (V3-SPEC §5.7) — beside the conversation: the objects it named (art, masked label, kind, an orange
	 * dot and "a decision waits" when one does; a tap selects the object everywhere and opens it), how the assistant
	 * works (reads, never people; proposals open in Decide; exercise data), and "Model and trace details" in words —
	 * which kind of model answered, how long the last answer took, that the conversation is kept in this tab, and
	 * where the raw steps live (Analyst → AI trace). Never a model id or a tool name.
	 */
	import Glyph from '../Glyph.svelte';
	import type { ContextItem } from './view';
	import { smallArt } from '../media/art';

	/** V3-P7: an object's small picture — the vehicle's studio shot or the kind's key art; agency tiles stay. */
	const ctxArt = smallArt;

	let {
		items,
		modelLine,
		lastAnswer,
		L,
		onopen,
	}: {
		items: readonly ContextItem[];
		modelLine: string;
		lastAnswer: string | null;
		L: (key: string, ...args: unknown[]) => string;
		onopen: (urn: string) => void;
	} = $props();
</script>

<aside class="ctx" aria-labelledby="v3a-ctx-h" data-testid="v3-context">
	<div>
		<h2 id="v3a-ctx-h">{L('v3a_ctx_title')}</h2>
		<p class="meta">{items.length ? L('v3a_ctx_sub') : L('v3a_ctx_none')}</p>
	</div>
	{#if items.length}
		<ul class="list">
			{#each items as it (it.urn)}
				<li>
					<button type="button" class="cc" data-testid="v3-context-item" data-urn={it.urn} data-decide={it.decide ? 'true' : 'false'} onclick={() => onopen(it.urn)}>
						<img class={['th', ctxArt(it.art) !== it.art && 'wide']} src={ctxArt(it.art)} alt="" width="52" height="52" loading="lazy" />
						<span class="tx">
							<span class="t">{it.label}{#if it.decide}<span class="dot" aria-hidden="true"></span>{/if}</span>
							<span class="m">{it.meta}</span>
						</span>
					</button>
				</li>
			{/each}
		</ul>
	{/if}
	<section class="rule" aria-labelledby="v3a-how-h">
		<span class="tag" id="v3a-how-h"><Glyph name="spark" size={14} />{L('v3a_how')}</span>
		<p class="note"><Glyph name="eye" size={17} />{L('v3a_how_reads')}</p>
		<p class="note"><Glyph name="decide" size={17} />{L('v3a_how_decide')}</p>
		<p class="note"><Glyph name="flask" size={17} />{L('v3a_how_exercise')}</p>
	</section>
	<details class="rule" data-testid="v3-trace">
		<summary>{L('v3a_trace')}</summary>
		<p class="meta" data-testid="v3-model-line">{modelLine}{#if lastAnswer}{` · ${lastAnswer}`}{/if}</p>
		<p class="meta">{L('v3a_session_kept')}</p>
		<p class="meta">{L('v3a_trace_where')} <a href="/analyst" class="link">{L('v3a_open_analyst')}</a></p>
	</details>
</aside>

<style>
	.ctx {
		display: flex;
		flex-direction: column;
		gap: 18px;
		min-height: 0;
		overflow: auto;
		padding: 22px 20px;
		scrollbar-width: thin;
		scrollbar-color: var(--v3-s4) transparent;
	}

	h2 {
		margin: 0 0 4px;
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 650;
	}

	.meta {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.list {
		display: flex;
		flex-direction: column;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.cc {
		display: grid;
		grid-template-columns: 52px minmax(0, 1fr);
		gap: 12px;
		align-items: center;
		width: 100%;
		padding: 8px;
		border: 0;
		border-radius: 14px;
		background: none;
		color: var(--v3-t1);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.cc:hover {
		background: var(--v3-s2);
	}

	.cc:focus-visible,
	summary:focus-visible,
	.link:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.th {
		flex: none;
		width: 52px;
		height: 52px;
		border-radius: var(--v3-radius-m);
	}

	.th.wide {
		width: 76px;
		height: 48px;
		object-fit: cover;
		background: var(--v3-s3);
	}

	.tx {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.t {
		font-size: 14px;
		line-height: 19px;
		font-weight: 640;
		overflow-wrap: anywhere;
	}

	.dot {
		display: inline-block;
		width: 8px;
		height: 8px;
		margin-left: 6px;
		border-radius: 4px;
		background: var(--v3-decide);
	}

	.m {
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
	}

	.rule {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 14px 16px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}

	.tag {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		width: fit-content;
		height: 22px;
		padding: 0 8px;
		border-radius: 11px;
		background: var(--v3-ai-veil);
		color: var(--v3-ai-text);
		font-size: var(--v3-text-micro);
		font-weight: 600;
	}

	.note {
		display: flex;
		gap: 10px;
		align-items: flex-start;
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 19px;
	}

	.note :global(.v3-glyph) {
		flex: none;
		margin-top: 1px;
		color: var(--v3-t3);
	}

	summary {
		color: var(--v3-brand-text);
		font-weight: 600;
		cursor: pointer;
	}

	.link {
		color: var(--v3-brand-text);
		font-weight: 600;
	}
</style>
