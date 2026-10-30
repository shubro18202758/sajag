<script lang="ts">
	/**
	 * Cover — the picture at the top of a card, a hero or a sheet: the event kind's key art (an original illustration),
	 * or a reference photograph of the place. A photo ALWAYS carries "Reference photo · not live" and its credit on the
	 * picture itself (never hidden behind a hover), so it can never be read as a live camera or as the situation now.
	 * Overlays (state tags, a map inset) come in as children. Lazy, sized, from the deck's own origin.
	 */
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import './packs.media';
	import { KEY_ART } from './art';
	import { photoSrc, photoSrcset, type PlacePhoto } from './photos';

	let {
		art,
		photo = null,
		alt,
		lang,
		sizes = '(max-width: 1500px) 440px, 600px',
		eager = false,
		compact = false,
		class: cls = '',
		children,
	}: {
		art: string;
		photo?: PlacePhoto | null;
		alt: string;
		lang: string;
		sizes?: string;
		eager?: boolean;
		/** One-line caption (cards); the full one shows the credit on its own line. */
		compact?: boolean;
		class?: string;
		children?: Snippet;
	} = $props();
</script>

<figure class={['cover', cls, compact && 'compact']} data-testid="v3-cover" data-cover={photo ? 'photo' : 'art'}>
	{#if photo}
		<img
			src={photoSrc(photo, 640)}
			srcset={photoSrcset(photo)}
			{sizes}
			alt={t(lang, 'v3i_photo_alt', photo.title)}
			width={KEY_ART.w}
			height={KEY_ART.h}
			loading={eager ? 'eager' : 'lazy'}
			decoding="async"
		/>
		<figcaption class="ref" data-testid="v3-photo-caption" title={t(lang, 'v3i_photo_tip', photo.title, photo.credit)}>
			<span class="tag">{t(lang, 'v3i_ref_photo')}</span>
			<span class="credit">{photo.credit}</span>
		</figcaption>
	{:else}
		<img src={art} {alt} width={KEY_ART.w} height={KEY_ART.h} loading={eager ? 'eager' : 'lazy'} decoding="async" />
	{/if}
	{@render children?.()}
</figure>

<style>
	.cover {
		position: relative;
		margin: 0;
		overflow: hidden;
		background: var(--v3-s2);
	}

	.cover > img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.ref {
		position: absolute;
		inset: auto 0 0 0;
		z-index: 1;
		display: flex;
		flex-direction: column;
		gap: 1px;
		padding: 18px 12px 8px;
		background: linear-gradient(to top, var(--v3-photo-scrim), var(--v3-photo-scrim-soft) 70%, var(--v3-photo-scrim-none));
		color: var(--v3-photo-ink);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		pointer-events: none;
	}

	.tag {
		font-weight: 650;
	}

	.credit {
		overflow: hidden;
		color: inherit;
		opacity: 0.86;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.compact .ref {
		flex-direction: row;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0 8px;
		padding: 16px 10px 6px;
	}

	.compact .credit {
		flex: 1 1 0;
		min-width: 0;
	}
</style>
