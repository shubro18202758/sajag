<script lang="ts">
	/**
	 * FactsCard (V3-SPEC §5.4) — the key facts as a quiet key/value list. A row is plain text (a report's facts,
	 * built from the whitelist reader) or a property value from the kind adapter's inspector view, rendered by
	 * the inspector's own PropValue (a mark through Plate — masked unless an officer is named; a time in IST; a
	 * linked record as a tag that opens its page).
	 */
	import PropValue from '$lib/workspace/components/inspector/PropValue.svelte';
	import Panel from './Panel.svelte';
	import type { FactRow } from './model';

	let { rows, title = null, now, onselect }: { rows: readonly FactRow[]; title?: string | null; now: number; onselect: (urn: string) => void } = $props();
</script>

{#if rows.length}
	<Panel {title} flush testid="obj-facts">
		<dl class="kv">
			{#each rows as r, i (i)}
				<dt>{r.key}</dt>
				<dd>
					{#if 'prop' in r}<PropValue value={r.prop} {now} {onselect} testid={r.testid} attrs={r.attrs} />{:else}{r.value}{/if}
				</dd>
			{/each}
		</dl>
	</Panel>
{/if}

<style>
	.kv {
		display: grid;
		grid-template-columns: minmax(84px, auto) minmax(0, 1fr);
		gap: 10px 20px;
		margin: 0;
		font-size: 14px;
		line-height: 20px;
	}

	dt {
		color: var(--v3-t2);
	}

	dd {
		margin: 0;
		min-width: 0;
		color: var(--v3-t1);
		font-weight: 550;
		overflow-wrap: anywhere;
	}
</style>
