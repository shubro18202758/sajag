<script lang="ts">
	/**
	 * Caution (V3-SPEC §5.7, §7.6) — one human sentence for one of the brain's diagnostics (a disagreement, low
	 * confidence, the backup model …) or the page's standing rule. The raw code never reaches it: the model maps
	 * codes to pack keys (cautionsOf) and an unknown code to the generic sentence.
	 */
	import Glyph from '../Glyph.svelte';

	let { text, tone = 'info', code = null }: { text: string; tone?: 'info' | 'warn'; code?: string | null } = $props();
</script>

<p class={['caution', tone]} data-testid="v3-caution" data-caution={code ?? ''}><Glyph name={tone === 'warn' ? 'alert' : 'info'} size={16} /><span>{text}</span></p>

<style>
	.caution {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 19px;
	}

	.caution :global(.v3-glyph) {
		margin-top: 2px;
		color: var(--v3-t3);
	}

	.warn :global(.v3-glyph) {
		color: var(--v3-decide-text);
	}
</style>
