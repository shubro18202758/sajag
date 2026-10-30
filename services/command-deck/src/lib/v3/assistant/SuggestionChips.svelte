<script lang="ts">
	/**
	 * SuggestionChips (V3-SPEC §5.7, §6.10) — questions the officer can ask in one tap, in their language (the wire
	 * carries the brain's English question). They wrap at 1920 and scroll in one row at 1366. Disabled while a turn
	 * is answering (one turn at a time).
	 */
	import Glyph from '../Glyph.svelte';

	let { items, disabled = false, label, onask }: { items: readonly { key: string; label: string }[]; disabled?: boolean; label: string; onask: (key: string) => void } = $props();
</script>

<div class="sugs" role="group" aria-label={label} data-testid="v3-suggestions">
	{#each items as s (s.key)}
		<button type="button" class="sug" data-suggest={s.key} {disabled} onclick={() => onask(s.key)}><Glyph name="spark" size={16} />{s.label}</button>
	{/each}
</div>

<style>
	.sugs {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.sug {
		display: inline-flex;
		flex: none;
		align-items: center;
		gap: 6px;
		height: 36px;
		padding: 0 14px;
		border: 1px solid var(--v3-line-3);
		border-radius: 18px;
		background: none;
		color: var(--v3-t1);
		font: inherit;
		font-size: 14px;
		font-weight: 600;
		white-space: nowrap;
		cursor: pointer;
	}

	.sug :global(.v3-glyph) {
		color: var(--v3-ai-text);
	}

	.sug:hover:not(:disabled) {
		background: var(--v3-s2);
	}

	.sug:disabled {
		color: var(--v3-t3);
		cursor: not-allowed;
	}

	.sug:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	@media (max-width: 1500px) {
		.sugs {
			flex-wrap: nowrap;
			overflow-x: auto;
			scrollbar-width: none;
			/* the row scrolls sideways: its right edge fades, so a cut chip reads as "more", never as a clipped one */
			-webkit-mask-image: linear-gradient(to right, black calc(100% - 48px), transparent);
			mask-image: linear-gradient(to right, black calc(100% - 48px), transparent);
			padding-right: 40px;
		}
	}
</style>
