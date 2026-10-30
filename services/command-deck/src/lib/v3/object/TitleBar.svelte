<script lang="ts">
	/**
	 * TitleBar (V3-SPEC §5.4, §6.3) — the record's art (96 px; 76 below 1500 px; an original illustration or a
	 * glyph tile, never a photo), its kind line, the display title (a registration mark in a masked chip), at
	 * most four tags (one provenance tag, the state, "waits for you"), and the actions: at most ONE white
	 * primary (only when a decision waits: it opens that decision's one home — never a verb here), "Ask about
	 * it", and More.
	 */
	import type { Snippet } from 'svelte';
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import PlateChip from '../ui/PlateChip.svelte';
	import type { Run } from '$lib/workspace/kinds/common';
	import { fmtStamp, fmtRange } from '$lib/ui/format/format';
	import type { TitleTag } from './model';

	let {
		art,
		alert = false,
		kindLine,
		title,
		tags,
		primary = null,
		lang,
		now,
		actions,
	}: {
		art: { src: string | null; glyph: string };
		alert?: boolean;
		kindLine: string;
		title: readonly Run[];
		tags: readonly TitleTag[];
		primary?: { href: string; label: string } | null;
		lang: string;
		now: number;
		actions: Snippet;
	} = $props();

	const isPlate = (r: Run): r is { plate: string | null; masked: boolean } => 'plate' in r;
	const textOf = (r: Run): string => {
		if ('text' in r) return r.text;
		if ('id' in r) return r.id;
		if ('start' in r) return r.end != null ? fmtRange(r.start, r.end, now) : fmtStamp(r.start, now);
		if ('time' in r) return r.time != null ? fmtStamp(r.time, now) : '';
		return '';
	};
	const fullTitle = $derived(title.map((r) => (isPlate(r) ? (r.plate ?? '') : textOf(r))).join(''));
</script>

<div class="titlebar" data-testid="obj-titlebar">
	<div class={['art', alert && 'alert', !art.src && 'tile']}>
		{#if art.src}<img src={art.src} alt="" width="96" height="96" />{:else}<Glyph name={art.glyph} size={44} />{/if}
	</div>
	<div class="copy">
		<p class="kind" data-testid="obj-kindline">{kindLine}</p>
		<h1 class="display" title={fullTitle} data-testid="obj-title">
			{#each title as r, i (i)}{#if isPlate(r)}{#if r.plate}<PlateChip mark={r.plate} masked={r.masked} {lang} />{/if}{:else}{textOf(r)}{/if}{/each}
		</h1>
		{#if tags.length}
			<div class="tags">
				{#each tags.slice(0, 4) as tg, i (i)}
					<span class="tg" {...tg.attrs}><V3Tag tone={tg.tone} glyph={tg.glyph ?? null} title={tg.title ?? null}>{tg.text}</V3Tag></span>
				{/each}
			</div>
		{/if}
	</div>
	<div class="acts">
		{#if primary}
			<a class="btn-primary" href={primary.href} data-testid="obj-primary">{primary.label}<Glyph name="arrowR" size={20} /></a>
		{/if}
		{@render actions()}
	</div>
</div>

<style>
	.titlebar {
		position: relative;
		z-index: 3;
		display: flex;
		align-items: flex-end;
		gap: 22px;
		margin-top: -150px;
		padding: 0 var(--v3-gut);
	}

	.art {
		display: grid;
		flex: none;
		place-items: center;
		width: 96px;
		height: 96px;
		overflow: hidden;
		border-radius: 26px;
		background: var(--v3-s2);
		box-shadow: var(--v3-elev-2);
		color: var(--v3-t1);
	}

	.art img {
		display: block;
		width: 100%;
		height: 100%;
	}

	.art.tile {
		border: 1px solid var(--v3-line-2);
		background: var(--v3-s3);
	}

	.art.alert {
		box-shadow: 0 0 0 3px var(--v3-alert), var(--v3-elev-2);
	}

	.copy {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-width: 0;
	}

	.kind {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		font-weight: 600;
		line-height: var(--v3-lh-micro);
	}

	.display {
		display: -webkit-box;
		margin: 2px 0 10px;
		overflow: hidden;
		color: var(--v3-t1);
		font-size: var(--v3-text-display);
		font-weight: 650;
		line-height: var(--v3-lh-display);
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow-wrap: anywhere;
	}

	.display :global([data-v3='plate']) {
		font-size: 0.8em;
		vertical-align: 0.1em;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.acts {
		display: flex;
		flex: none;
		align-items: center;
		gap: 10px;
		padding-bottom: 6px;
	}

	.btn-primary {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: var(--v3-ctl-xl);
		padding: 0 28px;
		border-radius: 28px;
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		font-size: var(--v3-text-sub);
		font-weight: 650;
		text-decoration: none;
		white-space: nowrap;
		transition: background var(--v3-dur-1) var(--v3-ease);
	}

	.btn-primary:hover {
		background: var(--v3-primary-hover);
	}

	.btn-primary:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	:global(:lang(hi)) .display,
	:global(:lang(mr)) .display {
		line-height: 1.35;
	}

	@media (max-width: 1500px) {
		.titlebar {
			gap: 18px;
			margin-top: -120px;
		}

		.art {
			width: 76px;
			height: 76px;
			border-radius: 20px;
		}

		.btn-primary {
			padding: 0 22px;
		}
	}

	/* a phone: a smaller mark and title, the actions wrap under the name */
	@media (max-width: 720px) {
		.titlebar {
			flex-wrap: wrap;
			gap: 12px;
		}

		.art {
			width: 56px;
			height: 56px;
			border-radius: 16px;
		}

		.display {
			font-size: 26px;
			line-height: 33px;
		}
	}
</style>
