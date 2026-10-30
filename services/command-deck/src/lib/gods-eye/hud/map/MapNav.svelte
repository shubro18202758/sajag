<script lang="ts">
	/**
	 * MapNav — zoom in, zoom out and reset north, bottom right of the map
	 * (SPEC §5.3), stacked above Cesium's credits so the credits are never
	 * covered. The compass glyph turns with the camera's heading.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.map';
	import Button from '$lib/ui/Button.svelte';

	interface Props {
		lang?: string;
		/** Camera heading (deg): the compass glyph points north on screen. */
		heading?: number | null;
		onzoomin: () => void;
		onzoomout: () => void;
		onnorth: () => void;
	}

	let { lang = 'en', heading = null, onzoomin, onzoomout, onnorth }: Props = $props();
</script>

<div class="nav" data-map="nav">
	<div class="group">
		<Button minimal icon="plus" tooltip={t(lang, 'map_zoom_in')} aria-label={t(lang, 'map_zoom_in')} onclick={onzoomin} />
		<Button minimal icon="minus" tooltip={t(lang, 'map_zoom_out')} aria-label={t(lang, 'map_zoom_out')} onclick={onzoomout} />
	</div>
	<div class="group compass" style:--heading={`${-(heading ?? 0)}deg`}>
		<Button minimal icon="compass" tooltip={t(lang, 'map_reset_north')} aria-label={t(lang, 'map_reset_north')} onclick={onnorth} />
	</div>
</div>

<style>
	.nav {
		display: flex;
		flex-direction: column;
		gap: 6px;
		pointer-events: auto;
	}

	.group {
		display: inline-flex;
		flex-direction: column;
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-1);
		box-shadow: var(--v-elev-1);
	}

	.group :global([data-ui='button']) {
		border-radius: 0;
	}

	.group > :global(:first-child [data-ui='button']),
	.group > :global([data-ui='button']:first-child) {
		border-radius: var(--v-radius-btn) var(--v-radius-btn) 0 0;
	}

	.group > :global(:last-child [data-ui='button']),
	.group > :global([data-ui='button']:last-child) {
		border-radius: 0 0 var(--v-radius-btn) var(--v-radius-btn);
	}

	.compass :global([data-ui='button']) {
		border-radius: var(--v-radius-btn);
	}

	.compass :global([data-ui='icon']) {
		transform: rotate(var(--heading, 0deg));
	}
</style>
