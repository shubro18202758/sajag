<script lang="ts">
	/**
	 * StepList (V3-SPEC §5.7) — how the assistant worked the answer out, in words: each lookup with a check (done),
	 * a spinner (running) or "did not answer"; the traffic-twin steps say "simulated". While the turn works the
	 * steps show; once it answers they fold into "How I worked this out · N steps" (collapsed, in the DOM), with
	 * what the lookups returned — every tool name and field already in words (model.humaniseLookups).
	 */
	import Glyph from '../Glyph.svelte';

	interface Step {
		label: string;
		state: 'pending' | 'running' | 'success' | 'error';
		simulated: boolean;
		summary: string | null;
	}

	let {
		steps,
		lookups = null,
		working,
		summaryText,
		lookupsTitle,
		simulatedWord,
		failedWord,
	}: {
		steps: readonly Step[];
		lookups?: string | null;
		working: boolean;
		summaryText: string;
		lookupsTitle: string;
		simulatedWord: string;
		failedWord: string;
	} = $props();
</script>

{#snippet rows()}
	{#each steps as s, i (i)}
		<li class={['st', `s-${s.state}`]} data-testid="v3-step" data-state={s.state}>
			{#if s.state === 'success'}<Glyph name="check" size={16} />{:else if s.state === 'error'}<Glyph name="close" size={16} />{:else}<span class="spin" aria-hidden="true"></span>{/if}
			<span class="lb">{s.label}{#if s.state === 'error'}<span class="dim">{` · ${failedWord}`}</span>{/if}{#if s.summary}<span class="dim">{` · ${s.summary}`}</span>{/if}</span>
			{#if s.simulated}<span class="sim">{simulatedWord}</span>{/if}
		</li>
	{/each}
	{#if lookups}
		<li class="st look" data-testid="v3-lookups"><Glyph name="search" size={16} /><span class="lb"><b>{lookupsTitle}</b>{` · ${lookups}`}</span></li>
	{/if}
{/snippet}

{#if working}
	<ul class="steps" data-testid="v3-steps" data-open="true">{@render rows()}</ul>
{:else if steps.length || lookups}
	<details class="fold" data-testid="v3-steps-fold">
		<summary>{summaryText}</summary>
		<ul class="steps">{@render rows()}</ul>
	</details>
{/if}

<style>
	.steps {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
		padding: 12px 14px;
		list-style: none;
		border: 1px solid var(--v3-line-1);
		border-radius: 14px;
		background: var(--v3-s1);
		color: var(--v3-t2);
		font-size: 14px;
		line-height: 20px;
	}

	.st {
		display: flex;
		align-items: flex-start;
		gap: 10px;
	}

	.st :global(.v3-glyph) {
		flex: none;
		margin-top: 2px;
	}

	.s-success :global(.v3-glyph) {
		color: var(--v3-ok-text);
	}

	.s-error :global(.v3-glyph) {
		color: var(--v3-t3);
	}

	.lb {
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.dim {
		color: var(--v3-t3);
	}

	.sim {
		margin-left: auto;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
		white-space: nowrap;
	}

	.spin {
		flex: none;
		width: 16px;
		height: 16px;
		margin-top: 2px;
		border: 2px solid var(--v3-s4);
		border-top-color: var(--v3-ai);
		border-radius: 50%;
		animation: sp 1s linear infinite;
	}

	@keyframes sp {
		to {
			transform: rotate(360deg);
		}
	}

	.fold summary {
		width: fit-content;
		color: var(--v3-brand-text);
		font-size: var(--v3-text-meta);
		font-weight: 600;
		cursor: pointer;
	}

	.fold[open] summary {
		margin-bottom: 8px;
	}

	.fold summary:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	@media (prefers-reduced-motion: reduce) {
		.spin {
			animation: none;
		}
	}
</style>
