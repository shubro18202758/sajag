<script lang="ts">
	/**
	 * PropertyTable — an object's properties, grouped (Identity, Lawful
	 * basis, Last read, Decisions, Provenance). 12 px keys in ink-2 and
	 * 14 px values in ink-1 share a baseline (vertical-align: baseline on
	 * both cells, SPEC §3.6); a row may add a muted hint ("30 days left") or
	 * render custom content (a Plate, tags). An empty value reads "—".
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import type { PropertyGroup } from './types';

	interface Props extends HTMLAttributes<HTMLTableElement> {
		groups: readonly PropertyGroup[];
		/** Width of the key column (CSS length). */
		keyWidth?: string;
	}

	let { groups, keyWidth = '36%', class: cls = '', ...rest }: Props = $props();
</script>

<table data-ui="property-table" class={['props', cls]} {...rest}>
	<colgroup><col style:width={keyWidth} /><col /></colgroup>
	{#each groups as g, gi (gi)}
		<tbody>
			{#if g.title}
				<tr class="grp"><th colspan="2" scope="colgroup">{g.title}</th></tr>
			{/if}
			{#each g.rows as r, ri (ri)}
				<tr {...r.attrs}>
					<th scope="row" class="k">{r.key}</th>
					<td class="v">
						<span class="vflex">
							{#if r.render}{@render r.render()}{:else if r.value != null && r.value !== ''}{r.value}{:else}<span
									class="empty">—</span
								>{/if}
							{#if r.hint}<span class="hint">{r.hint}</span>{/if}
						</span>
					</td>
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
		font-family: var(--v-font-ui);
	}

	/* property rows are 30 px (SPEC §3.6): 4 px padding on the 4 px grid, a
	   20 px line box shared by the 12 px key and the 14 px value so they sit
	   on one baseline, and the row height holds the pitch at 30 px */
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
		line-height: calc(var(--v-text-base) + 6px);
		overflow-wrap: anywhere;
	}

	.v {
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 6px);
		overflow-wrap: anywhere;
	}

	.vflex {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 8px;
		vertical-align: baseline;
	}

	.hint {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.empty {
		color: var(--v-ink-2);
	}

	.grp th {
		padding: 12px 0 4px;
		border-bottom: 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 600;
		line-height: calc(var(--v-text-xs) + 4px);
	}

	tbody:first-child .grp th {
		padding-top: 4px;
	}
</style>
