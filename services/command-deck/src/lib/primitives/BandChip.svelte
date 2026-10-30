<script lang="ts">
	/**
	 * BandChip — the one legal renderer of a band as a chip (SPEC §5.2, §2.4),
	 * rebuilt on the tag metrics of src/lib/ui: a 20 px chip, the band's
	 * swatch and its word in sentence case ("Amber"), ink-1 on the neutral
	 * veil. Band colours appear only as the band ladder's own tokens.
	 *
	 * BLACK is a dark fill with a 1 px red hairline — everywhere a band is
	 * drawn — never an opaque void (the fill is translucent). A hollow chip is
	 * the candidate band during hysteresis: an outline, no fill. `label`
	 * overrides the word (daylight: citizens never see "Black").
	 * `data-prim="band-chip"` and `data-band` stay on the root.
	 */
	import type { Band } from '$lib/design/tokens';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import { uiLang } from '$lib/ui/lang';

	interface Props {
		band: Band;
		/** Hollow = candidate band during hysteresis (outline only). */
		hollow?: boolean;
		/** Plain-language override (daylight: citizens never see 'BLACK'). */
		label?: string;
		size?: 'sm' | 'md';
		lang?: string;
	}

	let { band, hollow = false, label, size = 'md', lang }: Props = $props();

	const ctxLang = uiLang();
	const word = $derived(label ?? t(lang ?? ctxLang(), `shell_band_word_${band}`));
</script>

<span class="chip b-{band}" class:hollow class:sm={size === 'sm'} data-band={band} data-prim="band-chip"
	><i class="sw" aria-hidden="true"></i><span class="w">{word}</span></span
>

<style>
	.chip {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 6px;
		box-sizing: border-box;
		min-height: var(--v-ws-tag);
		padding: 1px 6px;
		border: 1px solid transparent;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		font-weight: 400;
		line-height: calc(var(--v-text-xs) + 4px);
		white-space: nowrap;
		vertical-align: middle;
	}

	.sm {
		gap: 4px;
		padding: 1px 5px;
	}

	.sw {
		display: inline-block;
		flex: 0 0 auto;
		width: 10px;
		height: 10px;
		border-radius: 2px;
	}

	.b-GREEN .sw {
		background: var(--v-band-green);
	}

	.b-AMBER .sw {
		background: var(--v-band-amber);
	}

	.b-RED .sw {
		background: var(--v-band-red);
	}

	/* BLACK: a translucent dark fill with a 1 px red hairline, never an opaque void */
	.b-BLACK {
		border-color: var(--v-band-black-hairline);
		background: var(--v-band-black-fill);
	}

	.b-BLACK .sw {
		background: var(--v-band-black-fill);
		box-shadow: inset 0 0 0 1px var(--v-band-black-hairline);
	}

	/* the candidate during hysteresis: an outline only, no fill at all */
	.hollow {
		border-color: var(--v-line-strong);
		background: transparent;
		color: var(--v-ink-2);
	}

	.hollow .sw {
		background: transparent;
	}

	.hollow.b-GREEN .sw {
		box-shadow: inset 0 0 0 1.5px var(--v-band-green);
	}

	.hollow.b-AMBER .sw {
		box-shadow: inset 0 0 0 1.5px var(--v-band-amber);
	}

	.hollow.b-RED .sw {
		box-shadow: inset 0 0 0 1.5px var(--v-band-red);
	}

	.hollow.b-BLACK {
		border-color: var(--v-band-black-hairline);
		background: transparent;
	}

	.hollow.b-BLACK .sw {
		box-shadow: inset 0 0 0 1.5px var(--v-band-black-hairline);
	}
</style>
