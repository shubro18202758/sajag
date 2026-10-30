<script lang="ts">
	/**
	 * NearbyList (V3-SPEC §3.5 "Nearby links Open in the graph") — what the city picture links to this record,
	 * grouped by relation (the inspector's linkGroups: the oracle's order of importance, one shared state said
	 * once). Every row opens that record's own page; labels are the masked row labels. The graph, search-around
	 * and paths stay in Analyst, one click away.
	 */
	import { t } from '$lib/i18n/strings';
	import './packs.object';
	import Glyph from '../Glyph.svelte';
	import type { LinkGroup } from '$lib/workspace/components/inspector/model';
	import { sharedStateWord } from '$lib/workspace/components/inspector/model';
	import { markerGlyph, objectHref } from './model';

	let { groups, lang, analyst }: { groups: readonly LinkGroup[]; lang: string; analyst: string } = $props();

	const PER = 6;
</script>

{#if groups.length}
	<div class="groups" data-testid="obj-nearby">
		{#each groups as g (g.relation)}
			{@const shared = sharedStateWord(g, lang)}
			<section class="grp" data-relation={g.relation} aria-labelledby={`obj-rel-${g.relation}`}>
				<h3 id={`obj-rel-${g.relation}`}>{g.label} <span class="n">{g.rows.length}</span>{#if shared}<span class="shared"> · {shared}</span>{/if}</h3>
				<ul>
					{#each g.rows.slice(0, PER) as r, i (r.urn)}
						{@const href = objectHref(r.urn)}
						<li>
							{#if href}
								<a {href} class="row" data-urn={r.urn}
									><span class="g"><Glyph name={markerGlyph(r)} size={16} /></span><span class="lbl">{r.label}</span>{#if g.times[i]}<span class="tm">{g.times[i]}</span>{/if}</a
								>
							{:else}
								<span class="row"><span class="g"><Glyph name={markerGlyph(r)} size={16} /></span><span class="lbl">{r.label}</span></span>
							{/if}
						</li>
					{/each}
				</ul>
				{#if g.rows.length > PER}<a class="more" href={analyst}>{t(lang, 'obj_near_more', g.rows.length - PER)}</a>{/if}
			</section>
		{/each}
	</div>
	<a class="graph" href={analyst} data-testid="obj-open-graph"><Glyph name="graph" size={16} />{t(lang, 'obj_near_graph')}</a>
{:else}
	<p class="empty">{t(lang, 'obj_near_empty')}</p>
{/if}

<style>
	.groups {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 18px 24px;
	}

	.grp {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}

	h3 {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 700;
	}

	.n {
		margin-left: 4px;
		padding: 0 6px;
		border-radius: 9px;
		background: var(--v3-s3);
		font-size: var(--v3-text-micro);
	}

	.shared {
		color: var(--v3-t3);
		font-weight: 600;
	}

	ul {
		display: flex;
		flex-direction: column;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: 36px;
		padding: 0 8px;
		border-radius: var(--v3-radius-s);
		color: var(--v3-t1);
		font-size: 14px;
		text-decoration: none;
	}

	a.row:hover {
		background: var(--v3-s2);
	}

	.g {
		display: grid;
		flex: none;
		place-items: center;
		width: 26px;
		height: 26px;
		border-radius: 8px;
		background: var(--v3-s3);
		color: var(--v3-t2);
	}

	.lbl {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.tm {
		flex: none;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-variant-numeric: tabular-nums;
	}

	.more,
	.graph {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--v3-brand-text);
		font-size: var(--v3-text-meta);
		font-weight: 600;
		text-decoration: none;
	}

	.graph {
		align-self: flex-start;
		margin-top: 4px;
	}

	a:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.empty {
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
	}
</style>
