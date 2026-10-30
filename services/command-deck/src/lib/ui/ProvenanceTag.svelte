<script lang="ts">
	/**
	 * ProvenanceTag (plan contract X2; SPEC §9.2) — where a row comes from,
	 * stated honestly and quietly.
	 *
	 *   source        emulated | simulated | test | osint
	 *   verification  for osint: UNVERIFIED-OSINT | NEWS-REPORTED |
	 *                 OFFICIAL-VERIFIED | CONFIRMED | null
	 *   compact       the 16 px glyph, a visually hidden text label (tests read
	 *                 textContent) and a tooltip — for mixed lists
	 *
	 * Labels (EN): Emulated, Simulated, Test; for osint "Unverified OSINT",
	 * "News-reported", "Official, verified", "Confirmed by officer", or
	 * "Open-source" without a state. Glyphs: lab-test, random, playbook,
	 * globe. The root carries data-source and data-verification (the raw
	 * enum value; absent without a state). Neutral colour: provenance is a
	 * fact, not a state that asks for action.
	 *
	 * Honest fallbacks (ethics rule 7): a live source (or none) renders no
	 * tag at all — live rows are unmarked (SPEC §9.2); any other value this
	 * console does not know renders a neutral "Unknown source" tag with the
	 * raw value in data-source. It never borrows another source's label.
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { PROVENANCE_ICON } from '$lib/design/icons';
	import type { UiKey } from '$lib/i18n/packs.ui';
	import Icon from './Icon.svelte';
	import Tooltip from './Tooltip.svelte';
	import { uiLang, ut } from './lang';
	import type { ProvenanceSource, VerificationState } from './types';

	interface Props extends HTMLAttributes<HTMLSpanElement> {
		source: ProvenanceSource;
		verification?: VerificationState | null;
		compact?: boolean;
		lang?: string;
	}

	let { source, verification = null, compact = false, lang, class: cls = '', ...rest }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());

	const SOURCE_KEY: Record<ProvenanceSource, [UiKey, UiKey]> = {
		emulated: ['ui_prov_emulated', 'ui_prov_emulated_tip'],
		simulated: ['ui_prov_simulated', 'ui_prov_simulated_tip'],
		test: ['ui_prov_test', 'ui_prov_test_tip'],
		osint: ['ui_prov_osint', 'ui_prov_osint_tip']
	};
	const VERIFICATION_KEY: Record<VerificationState, [UiKey, UiKey]> = {
		'UNVERIFIED-OSINT': ['ui_verif_unverified', 'ui_verif_unverified_tip'],
		'NEWS-REPORTED': ['ui_verif_news', 'ui_verif_news_tip'],
		'OFFICIAL-VERIFIED': ['ui_verif_official', 'ui_verif_official_tip'],
		CONFIRMED: ['ui_verif_confirmed', 'ui_verif_confirmed_tip']
	};

	const UNKNOWN: [UiKey, UiKey] = ['ui_prov_unknown', 'ui_prov_unknown_tip'];
	const has = (o: object, k: unknown) => typeof k === 'string' && Object.prototype.hasOwnProperty.call(o, k);

	/** Live (or no source) is unmarked; a known source has its label; anything else is unknown. */
	const raw = $derived(typeof source === 'string' ? source.trim() : '');
	const unmarked = $derived(raw === '' || raw.toLowerCase() === 'live');
	const known = $derived(has(SOURCE_KEY, raw));
	const keys = $derived(
		raw === 'osint' && verification && has(VERIFICATION_KEY, verification)
			? VERIFICATION_KEY[verification]
			: known
				? SOURCE_KEY[raw as ProvenanceSource]
				: UNKNOWN
	);
	const label = $derived(ut(L, keys[0]));
	const tip = $derived(ut(L, keys[1]));
	const glyph = $derived(known ? PROVENANCE_ICON[raw as ProvenanceSource] : 'help');
</script>

{#snippet explain()}<b>{label}.</b> {tip}{/snippet}

{#if !unmarked}
	<Tooltip content={explain}>
		<span
			data-ui="provenance-tag"
			data-source={source}
			data-verification={raw === 'osint' && verification ? verification : undefined}
			class={['prov', compact && 'compact', cls]}
			{...rest}
		>
			<Icon name={glyph} size={compact ? 16 : 12} />
			{#if compact}<span class="sr">{label}</span>{:else}<span class="text">{label}</span>{/if}
		</span>
	</Tooltip>
{/if}

<style>
	.prov {
		/* the screen-reader span is absolutely positioned: anchor it here, or it escapes the column and stretches the page */
		position: relative;
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 4px;
		box-sizing: border-box;
		min-height: 20px;
		max-width: 100%;
		padding: 2px 6px;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		color: var(--v-ink-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		white-space: nowrap;
		vertical-align: middle;
	}

	.prov :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	/* the label is the tag's baseline (not the glyph's synthesized bottom edge),
	   so in a baseline row (a PropertyTable value) the tag's text sits on the
	   key's baseline and the row keeps its 30 px; in a 20 px tag with 2 px
	   padding the 16 px label line lands exactly where centring put it */
	.text {
		align-self: baseline;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.compact {
		justify-content: center;
		min-width: 20px;
		padding: 2px;
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		padding: 0;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
		border: 0;
	}
</style>
