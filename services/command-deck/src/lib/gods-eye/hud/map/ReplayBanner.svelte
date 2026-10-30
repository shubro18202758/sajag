<script lang="ts">
	/**
	 * ReplayBanner — top centre of the map while an emulator tape plays
	 * (SPEC §5.3, §7.3): "Replay · run 20 · Emulated" when the run is an
	 * emulated recording (`emulated`, read from the replay state by the
	 * canvas — a tape's plates carry the EM series), and no provenance word
	 * when it is not (a replay never claims emulation it cannot show). The
	 * live layers stand down as they always have (the 3D tiles stay); the
	 * inbox and the live strip stay live, so the banner says the layers, not
	 * the console, are paused. Test hooks: `replay-pill`, `live-paused`.
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.map';
	import Icon from '$lib/ui/Icon.svelte';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		runId?: number | string | null;
		/** The loaded tape is an emulated recording (its own provenance, not a guess). */
		emulated?: boolean;
		lang?: string;
	}

	let { runId = null, emulated = false, lang = 'en', class: cls = '', ...rest }: Props = $props();
</script>

<div class={['replay-banner', cls]} role="status" {...rest}>
	<Icon name="history" size={16} />
	<span data-testid="replay-pill">
		{t(lang, 'map_replay_banner', runId)}{#if emulated}<span class="sep" aria-hidden="true">·</span>{t(lang, 'map_replay_emulated')}{/if}
	</span>
	<span class="sep" aria-hidden="true">·</span>
	<span data-testid="live-paused" title={t(lang, 'map_live_paused_hint')}>{t(lang, 'map_live_paused')}</span>
</div>

<style>
	.replay-banner {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 32px;
		padding: 0 12px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-2);
		box-shadow: var(--v-elev-2);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		white-space: nowrap;
	}

	.replay-banner :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.sep,
	[data-testid='live-paused'] {
		color: var(--v-ink-2);
	}

	[data-testid='replay-pill'] .sep {
		margin: 0 8px;
	}
</style>
