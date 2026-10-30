<script lang="ts">
	/**
	 * The Properties tab's grouped key/value table (SPEC §3.6, §5.1
	 * PropertyTable metrics): 12 px keys and 14 px values on one baseline,
	 * 30 px rows, group titles in 600. Rendered here (not through
	 * ui/PropertyTable) so a pinned hook such as `dossier-phase-window` sits
	 * on the value alone.
	 */
	import type { PropGroup } from '../../kinds/common';
	import PropValue from './PropValue.svelte';

	let { groups, now, onselect, keyWidth = '36%' }: { groups: readonly PropGroup[]; now: number; onselect: (urn: string) => void; keyWidth?: string } = $props();
</script>

<table class="props">
	<colgroup><col style:width={keyWidth} /><col /></colgroup>
	{#each groups as g, gi (gi)}
		<tbody data-group={g.title}>
			<tr class="grp"><th colspan="2" scope="colgroup">{g.title}</th></tr>
			{#each g.rows as r, ri (ri)}
				<tr>
					<th scope="row" class="k">{r.key}</th>
					<td class="v"><span class="vflex"><PropValue value={r.value} {now} {onselect} testid={r.testid} attrs={r.attrs} /></span></td>
				</tr>
			{/each}
		</tbody>
	{/each}
</table>

<style>
	.props {
		width: 100%;
		border-collapse: collapse;
		table-layout: fixed;
		color: var(--v-ink-1);
	}

	th,
	td {
		padding: 4px 0;
		border-bottom: 1px solid var(--v-line-1);
		vertical-align: baseline;
		text-align: left;
	}

	tr:not(.grp) {
		height: 30px;
	}

	tbody:last-child tr:last-child th,
	tbody:last-child tr:last-child td {
		border-bottom: 0;
	}

	.k {
		padding-right: 12px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 400;
		line-height: 20px;
		overflow-wrap: anywhere;
	}

	.v {
		font-size: var(--v-text-base);
		line-height: 20px;
		overflow-wrap: anywhere;
	}

	.vflex {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 8px;
		vertical-align: baseline;
	}

	.grp th {
		padding: 12px 0 4px;
		border-bottom: 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 600;
		line-height: 16px;
	}

	tbody:first-child .grp th {
		padding-top: 4px;
	}
</style>
