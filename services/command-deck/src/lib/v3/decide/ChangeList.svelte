<script lang="ts">
	/**
	 * ChangeList (V3-SPEC §5.3) — "What changes if you …", GENERATED from decisions/writers.ts (the unchanged
	 * v2 contract: each row is what the writer really changes, never more). One row per object: the object,
	 * then "from → to" (or "No change" in the quiet ink), and a tag: "changes" where the writer posts the
	 * change, "next" where the change is a request that waits for its own, separate decision (a dispatch the
	 * oracle files). What the writer leaves alone is said once, under the list.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.decisions';
	import type { ChangeRow } from '$lib/decisions/writers';
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import './packs.decide';

	let { rows, unchanged = [], title, lang }: { rows: ChangeRow[]; unchanged?: string[]; title: string; lang: string } = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const tagOf = (r: ChangeRow): 'changes' | 'next' | null => (r.after == null ? null : r.writes && r.writes.length === 0 ? 'next' : 'changes');
</script>

{#if rows.length}
	<section class="sec" data-v3="change-list" aria-label={title}>
		<h3 class="sec-t"><Glyph name="sliders" size={16} />{title}</h3>
		<ul class="changes">
			{#each rows as r, i (i)}
				{@const tag = tagOf(r)}
				<li class="chg" data-writes={r.writes?.join(' ') || undefined} data-change={tag ?? 'none'}>
					<span class="o">{r.object}</span>
					{#if tag}<V3Tag tone={tag === 'changes' ? 'decide' : 'neutral'} size="sm">{L(tag === 'changes' ? 'v3d_tag_changes' : 'v3d_tag_next')}</V3Tag>{/if}
					<span class="ft">
						{#if r.after == null}
							<span class="same">{r.now ? L('v3d_no_change_still', r.now) : L('dec_no_change')}</span>
						{:else}
							<span class="from">{r.now}</span><span class="arrow" aria-label={L('v3d_becomes')}>→</span><span class="to">{r.after}</span>
						{/if}
					</span>
				</li>
			{/each}
		</ul>
		{#if unchanged.length}<p class="note"><Glyph name="info" size={16} />{L('dec_unchanged', unchanged.join('; '))}</p>{/if}
	</section>
{/if}

<style>
	.sec-t {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0 0 10px;
		font-size: var(--v3-text-meta);
		font-weight: 700;
		color: var(--v3-t2);
	}

	.changes {
		display: flex;
		flex-direction: column;
		margin: 0;
		padding: 0;
		list-style: none;
		border: 1px solid var(--v3-line-2);
		border-radius: 14px;
		overflow: hidden;
	}

	.chg {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 4px 12px;
		align-items: center;
		padding: 12px 16px;
		border-top: 1px solid var(--v3-line-1);
		font-size: 14px;
		line-height: 20px;
	}

	.chg:first-child {
		border-top: 0;
	}

	.o {
		font-weight: 600;
		color: var(--v3-t1);
		overflow-wrap: anywhere;
	}

	.ft {
		grid-column: 1 / 3;
		display: flex;
		flex-wrap: wrap;
		gap: 4px 8px;
		align-items: baseline;
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		color: var(--v3-t2);
	}

	.arrow {
		color: var(--v3-t3);
	}

	.to {
		color: var(--v3-t1);
		font-weight: 600;
	}

	.same {
		color: var(--v3-t3);
	}

	.note {
		display: flex;
		gap: 8px;
		align-items: flex-start;
		margin: 8px 0 0;
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		color: var(--v3-t2);
	}

	.note :global(svg) {
		margin-top: 1px;
	}
</style>
