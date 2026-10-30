<script lang="ts">
	/**
	 * SelectionCard (V3-SPEC §5.6, L1) — what is selected: art, kind line, title (a mark masked with
	 * its lock), at most two state tags, at most three figures, then ONE primary verb ("Review the hold" opens
	 * the decision's one home in Decide — never an Approve here), Follow (the canvas's own follow) and Details.
	 * Every figure comes from a feed; an object with none shows none. One provenance tag at most.
	 */
	import { t } from '$lib/i18n/strings';
	import Glyph from '../Glyph.svelte';
	import PlateChip from '../ui/PlateChip.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import type { PlateVM, TagVM } from '../home/view';
	import type { Stat } from './model';
	import './packs.map3';
	import { mediaForTile } from '../media/art';
	import VehicleShot from '../media/VehicleShot.svelte';
	import AgencyMark from '../media/AgencyMark.svelte';
	import '../media/packs.media';
	import type { Snippet } from 'svelte';

	let {
		art,
		kind,
		title,
		plate = null,
		tags = [],
		stats = [],
		primary = null,
		details,
		follow,
		lang,
		onclose,
		onfollow,
		children,
	}: {
		art: string;
		kind: string;
		title: string;
		plate?: PlateVM | null;
		tags?: readonly TagVM[];
		stats?: readonly Stat[];
		primary?: { href: string; text: string } | null;
		details: string;
		follow: { pressed: boolean; disabled: boolean; title: string } | null;
		lang: string;
		onclose: () => void;
		onfollow: () => void;
		/** A section the selection brings with it (a road's forecast band, $lib/ai). */
		children?: Snippet;
	} = $props();

	// V3-P7: the selection opens on its picture — the kind's key art or the vehicle class's studio shot
	const media = $derived(mediaForTile(art));
</script>

<section class={['card', 'v3-glass', media && media.kind !== 'agency' && 'has-media']} aria-live="polite" aria-label={title} data-testid="v3-selection" data-ge-keepout>
	{#if media && media.kind === 'art'}
		<div class="media" data-testid="v3-selection-art"><img src={media.src} alt={t(lang, 'v3i_art_alt', kind)} width="640" height="360" loading="lazy" decoding="async" /></div>
	{:else if media && media.kind === 'vehicle'}
		<div class="media vehicle" data-testid="v3-selection-art"><VehicleShot cls={media.cls} {lang} width={300} /></div>
	{/if}
	<div class="row1">
		{#if media && media.kind === 'agency'}<AgencyMark role={media.role} {lang} size={56} fallback={art} />{:else}<img class="art" src={art} alt="" width="56" height="56" />{/if}
		<div class="ht">
			<div class="micro">{kind}</div>
			<h2 class="h2" title={title}>{title}{#if plate}&nbsp;<PlateChip mark={plate.mark} masked={plate.masked} {lang} />{/if}</h2>
		</div>
		<button type="button" class="x" aria-label={t(lang, 'v3m_close')} title={t(lang, 'v3m_close')} data-testid="v3-selection-close" onclick={onclose}><Glyph name="close" size={18} /></button>
	</div>
	{#if tags.length}
		<div class="tags">
			{#each tags.slice(0, 2) as tag, i (i)}<V3Tag tone={tag.tone} glyph={tag.glyph ?? null} title={tag.title ?? null}>{tag.text}</V3Tag>{/each}
		</div>
	{/if}
	{#if stats.length}
		<div class="stats" data-testid="v3-selection-stats">
			{#each stats.slice(0, 3) as st, i (i)}
				<div class="stat"><b>{st.value}</b><span>{st.label}</span></div>
			{/each}
		</div>
	{/if}
	{#if children}{@render children()}{/if}
	<div class="btns">
		{#if primary}
			<a class="btn primary" href={primary.href} data-testid="v3-selection-primary">{primary.text}<Glyph name="arrowR" size={18} /></a>
		{/if}
		{#if follow}
			<button
				type="button"
				class={['btn', 'secondary', follow.pressed && 'is-pressed']}
				aria-pressed={follow.pressed}
				aria-disabled={follow.disabled ? 'true' : undefined}
				title={follow.title}
				data-testid="v3-selection-follow"
				onclick={() => {
					if (!follow.disabled) onfollow();
				}}><Glyph name="target" size={18} />{t(lang, follow.pressed ? 'v3m_following' : 'v3m_follow')}</button
			>
		{/if}
		<a class="btn ghost" href={details} title={t(lang, 'v3m_details_tip')} data-testid="v3-selection-details">{t(lang, 'v3m_details')}</a>
	</div>
</section>

<style>
	.card {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 18px 20px;
		border: 1px solid var(--v3-glass-border);
		border-radius: var(--v3-radius-l);
		background: var(--v3-glass-surface);
		box-shadow: var(--v3-elev-2);
		pointer-events: auto;
		animation: rise var(--v3-dur-2) var(--v3-ease);
	}

	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(6px);
		}
	}

	.media {
		height: 132px;
		margin: -18px -20px 0;
		overflow: hidden;
		border-radius: var(--v3-radius-l) var(--v3-radius-l) 0 0;
	}

	.media img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: 50% 60%;
	}

	.media.vehicle {
		display: grid;
		place-items: center;
		background: var(--v3-s2);
	}

	.media.vehicle :global(.shot) {
		width: auto;
		height: 100%;
	}

	.row1 {
		display: flex;
		align-items: center;
		gap: 14px;
		min-width: 0;
	}

	.art {
		flex: none;
		width: 56px;
		height: 56px;
		border-radius: 15px;
	}

	.ht {
		min-width: 0;
		flex: 1;
	}

	.micro {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 600;
	}

	.h2 {
		margin: 2px 0 0;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 640;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		overflow-wrap: anywhere;
	}

	.x {
		align-self: flex-start;
		flex: none;
		display: grid;
		place-items: center;
		width: 36px;
		height: 36px;
		border: 0;
		border-radius: 18px;
		background: none;
		color: var(--v3-t2);
		cursor: pointer;
	}

	.x:hover {
		background: var(--v3-s2);
		color: var(--v3-t1);
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 10px;
	}

	.stat {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 10px 12px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		min-width: 0;
	}

	.stat b {
		font-size: 17px;
		line-height: 22px;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.stat span {
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.btns {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		height: 44px;
		padding: 0 20px;
		border: 0;
		border-radius: 22px;
		font: inherit;
		font-size: 15px;
		font-weight: 650;
		white-space: nowrap;
		text-decoration: none;
		cursor: pointer;
		transition: background var(--v3-dur-1);
	}

	.btn:focus-visible,
	.x:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.primary {
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
	}

	.primary:hover {
		background: var(--v3-primary-hover);
	}

	.secondary {
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.secondary:hover {
		background: var(--v3-s4);
	}

	.secondary.is-pressed {
		background: var(--v3-route-veil);
		color: var(--v3-route-text);
	}

	.secondary[aria-disabled='true'] {
		color: var(--v3-t3);
		cursor: not-allowed;
	}

	.ghost {
		border: 1px solid var(--v3-line-3);
		background: none;
		color: var(--v3-t1);
	}

	.ghost:hover {
		background: var(--v3-s2);
	}

	@media (max-width: 1500px) {
		.card {
			padding: 16px;
			gap: 10px;
		}

		.btn {
			height: 40px;
			padding: 0 16px;
			font-size: 14px;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.card {
			animation: none;
		}

		.btn {
			transition: none;
		}
	}
</style>
