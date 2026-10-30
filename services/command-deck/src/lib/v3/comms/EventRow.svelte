<script lang="ts">
	/**
	 * One event in the Advisories list (V3-SPEC §6.7): its art, its kind line and its title, as a radio in the list's
	 * radiogroup (the page owns the roving focus). A row that will not be drafted for citizens carries a quiet eye-off
	 * glyph — a hint; the one statement of the withholding is the badge on the selected event (comms-withheld-badge).
	 */
	import Glyph from '../Glyph.svelte';
	import { mediaForTile } from '../media/art';

	let {
		art,
		kind,
		title,
		meta,
		selected,
		withheld,
		withheldTip,
		tabindex,
		eventId,
		onpick,
		onkeydown,
	}: {
		art: string;
		kind: string;
		title: string;
		meta: string;
		selected: boolean;
		withheld: boolean;
		withheldTip: string;
		tabindex: number;
		eventId: string;
		onpick: () => void;
		onkeydown: (e: KeyboardEvent) => void;
	} = $props();

	/** V3-P7: the kind's key art as the row's small picture (agency tiles and unknown art stay). */
	function rowArt(src: string): string {
		const m = mediaForTile(src);
		return m?.kind === 'art' ? m.src : src;
	}
</script>

<button
	type="button"
	role="radio"
	aria-checked={selected}
	class={['row', selected && 'is-selected']}
	{tabindex}
	data-event-id={eventId}
	data-testid="comms-event-row"
	onclick={onpick}
	{onkeydown}
>
	<img class={['art', rowArt(art) !== art && 'wide']} src={rowArt(art)} alt="" width="44" height="44" loading="lazy" />
	<span class="txt">
		<span class="kind">{kind}</span>
		<span class="title" {title}>{title}</span>
		<span class="meta">{meta}</span>
	</span>
	{#if withheld}<span class="wh" title={withheldTip}><Glyph name="eyeoff" size={18} label={withheldTip} /></span>{/if}
</button>

<style>
	.row {
		display: flex;
		align-items: center;
		gap: 12px;
		width: 100%;
		min-width: 0;
		padding: 10px 12px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		text-align: left;
		cursor: pointer;
		transition:
			border-color var(--v3-dur-1) var(--v3-ease),
			background var(--v3-dur-1) var(--v3-ease),
			transform var(--v3-dur-2) var(--v3-ease);
	}

	.row:hover {
		background: var(--v3-s2);
		transform: translateY(-3px);
	}

	/* the global .is-selected rule paints the data-row veil (!important); the Advisories row keeps its own, calmer one */
	.row.is-selected {
		border-color: var(--v3-brand);
		background: var(--v3-brand-veil) !important;
		box-shadow: inset 3px 0 0 var(--v3-brand) !important;
	}

	.row:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.art.wide {
		width: 64px;
		height: 40px;
		object-fit: cover;
	}

	.art {
		flex: none;
		width: 44px;
		height: 44px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s3);
		object-fit: cover;
	}

	.txt {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 1px;
		min-width: 0;
	}

	.kind {
		overflow: hidden;
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.title {
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		overflow: hidden;
		font-size: var(--v3-text-body);
		font-weight: 620;
		line-height: 1.3;
	}

	.meta {
		overflow: hidden;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.wh {
		flex: none;
		display: grid;
		place-items: center;
		color: var(--v3-t2);
	}

	@media (prefers-reduced-motion: reduce) {
		.row,
		.row:hover {
			transition: none;
			transform: none;
		}
	}
</style>
