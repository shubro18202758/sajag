<script lang="ts">
	/**
	 * BotTurn (V3-SPEC §5.7) — one answer: the violet avatar, "Sajag assistant · 19:42 · read only", the working steps
	 * while it reads (StepList, folded once it answers), the answer as prose (16/26) with the objects it names as
	 * chips, the grounding check's note when it removed statements, the cautions (one human sentence each), the
	 * proposal cards (Open to decide · Show on map — never Apply/Approve) and the standing rule under them.
	 */
	import Glyph from '../Glyph.svelte';
	import ObjectChip from './ObjectChip.svelte';
	import StepList from './StepList.svelte';
	import ProposalCard from './ProposalCard.svelte';
	import Caution from './Caution.svelte';
	import type { TurnVM } from './view';
	import type { Chip } from './model';

	let {
		turn,
		L,
		chipOf,
		onopen,
		onshowmap,
		roads = null,
	}: {
		turn: TurnVM;
		L: (key: string, ...args: unknown[]) => string;
		chipOf: (c: Chip) => { glyph: string; decide: boolean };
		onopen: (urn: string) => void;
		onshowmap: (urn: string | null) => void;
		roads?: readonly (readonly (readonly [number, number])[])[] | null;
	} = $props();
</script>

<article class="bot" data-testid="v3-bot-turn" data-working={turn.working ? 'true' : 'false'}>
	<span class="av" aria-hidden="true"><Glyph name="spark" size={18} /></span>
	<div class="body">
		<div class="who">{L('v3a_bot')} · {turn.at} · {turn.working ? L('v3a_working') : L('v3a_read_only')}</div>
		{#if turn.working || turn.steps.length || turn.lookups}
			<StepList
				steps={turn.steps}
				lookups={turn.lookups}
				working={turn.working}
				summaryText={turn.stepsSummary}
				lookupsTitle={L('v3a_lookups')}
				simulatedWord={L('v3a_step_simulated')}
				failedWord={L('v3a_step_failed')}
			/>
		{/if}
		{#if turn.segments.length}
			<p class="prose" data-testid="v3-answer">
				{#each turn.segments as seg, i (i)}{#if 'chip' in seg}{@const meta = chipOf(seg.chip)}<ObjectChip label={seg.chip.label} glyph={meta.glyph} decide={meta.decide} onopen={() => onopen(seg.chip.urn)} />{:else}{seg.text}{/if}{/each}
			</p>
		{:else if turn.working}
			<p class="prose dim">{L('v3a_thinking')}…</p>
		{/if}
		{#if turn.noProse}<Caution text={L('v3a_no_prose')} />{/if}
		{#if turn.error}<Caution tone="warn" text={turn.error} code="error" />{/if}
		{#if turn.grounding}<p class="grounding" data-testid="v3-grounding">{turn.grounding}</p>{/if}
		{#each turn.cautions as c (c.key)}<Caution tone="warn" text={c.text} code={c.key} />{/each}
		{#each turn.proposals as p (p.key)}
			<ProposalCard
				kind={p.kind}
				thumb={p.thumb}
				inset={p.inset ?? null}
				{roads}
				tag={p.tag}
				ai={p.ai}
				timer={p.timer}
				title={p.title}
				why={p.why}
				openHref={p.openHref}
				openText={L('v3a_open_decide')}
				mapText={L('v3a_show_map')}
				onshowmap={() => onshowmap(p.urn)}
			/>
		{/each}
		{#if turn.proposals.length}<Caution text={L('v3a_rule')} />{/if}
	</div>
</article>

<style>
	.bot {
		display: grid;
		grid-template-columns: 36px minmax(0, 1fr);
		gap: 14px;
	}

	.av {
		display: grid;
		place-items: center;
		width: 36px;
		height: 36px;
		border-radius: 18px;
		background: var(--v3-ai-veil);
		color: var(--v3-ai-text);
	}

	.body {
		display: flex;
		flex-direction: column;
		gap: 14px;
		min-width: 0;
	}

	.who {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 36px;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		font-weight: 650;
	}

	.prose {
		margin: 0;
		font-size: 16px;
		line-height: 26px;
		white-space: pre-line;
		overflow-wrap: anywhere;
	}

	.prose.dim {
		color: var(--v3-t3);
	}

	.grounding {
		margin: 0;
		width: fit-content;
		padding: 4px 10px;
		border: 1px dashed var(--v3-dashed);
		border-radius: 12px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	:global(:lang(hi)) .prose,
	:global(:lang(mr)) .prose {
		font-size: 17px;
		line-height: 1.7;
	}
</style>
