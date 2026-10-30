<script lang="ts">
	/**
	 * The public pages' credits (V3-P7), at the end of the page's own scroll: the artwork is illustration, the reference
	 * photos keep their authors' licences (static/photos/NOTICE.md), and the agency and source marks belong to their
	 * owners — Sajag is a prototype and is not affiliated with or endorsed by them.
	 */
	import { t } from '$lib/i18n/strings';
	import '../media/packs.media';

	let { lang }: { lang: string } = $props();
</script>

<footer class="pub-credits" data-testid="pub-credits">
	<p>{t(lang, 'v3i_art_credit')} {t(lang, 'v3i_photos_credit')} <a href="/photos/NOTICE.md">{t(lang, 'v3i_photos_link')}</a></p>
	<p>{t(lang, 'v3i_marks_credit')}</p>
</footer>

<style>
	.pub-credits {
		width: min(100% - 32px, 560px);
		margin: 24px auto 32px;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.pub-credits p {
		margin: 0 0 4px;
	}

	.pub-credits a {
		color: var(--v3-brand-text);
	}
</style>
