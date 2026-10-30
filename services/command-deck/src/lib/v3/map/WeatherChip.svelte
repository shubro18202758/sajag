<script lang="ts">
	/**
	 * WeatherChip (V3-SPEC §5.6) — an OFFICIAL district-level weather warning as one chip over the map, never a
	 * ring: the verified tick, "Official weather warning", and the warning's own words. Only an official source
	 * reaches it (model.isOfficialWeather); a news or unverified weather report stays a report in the Now list.
	 */
	import { t } from '$lib/i18n/strings';
	import Glyph from '../Glyph.svelte';
	import RedactedText from '../ui/RedactedText.svelte';
	import './packs.map3';

	let { text, href, lang }: { text: string; href: string; lang: string } = $props();
</script>

<a class="wx v3-glass" {href} data-testid="v3-weather" data-ge-keepout>
	<Glyph name="verified" size={18} />
	<span><b>{t(lang, 'v3m_wx_official')}</b> · <RedactedText {text} {lang} /></span>
</a>

<style>
	.wx {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		max-width: 100%;
		padding: 8px 14px;
		border: 1px solid var(--v3-glass-border);
		border-radius: 20px;
		background: var(--v3-glass-surface);
		box-shadow: var(--v3-elev-1);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		text-decoration: none;
		pointer-events: auto;
	}

	.wx span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.wx :global(.v3-glyph) {
		color: var(--v3-ok-text);
	}

	b {
		color: var(--v3-t1);
		font-weight: 650;
	}

	.wx:hover {
		border-color: var(--v3-line-3);
	}

	.wx:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}
</style>
