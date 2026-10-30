<script lang="ts">
	/**
	 * MapReadout — bottom left of the map (SPEC §5.3): the position under the
	 * pointer (else the view's centre) through the formatter's Coord, a
	 * scale bar, and the quiet rule line "Vehicles only · penalties need a
	 * named officer". Cesium's credits sit at the bottom right, clear of it.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.map';
	import { ACTION_ICON } from '$lib/design/icons';
	import Coord from '$lib/ui/format/Coord.svelte';
	import Icon from '$lib/ui/Icon.svelte';

	interface Props {
		lang?: string;
		lat: number | null;
		lon: number | null;
		/** The scale bar: its width (px) and the distance it spans. */
		scale: { px: number; label: string } | null;
	}

	let { lang = 'en', lat, lon, scale }: Props = $props();

	/**
	 * F-29: on a narrow map (1366) the rule line never ends mid-word ("…need
	 * a"): when the full line does not fit, the chip reads the short rule
	 * ("Vehicles only") and carries the whole line as its tooltip. Measured
	 * against a hidden full-length copy, so the choice never oscillates.
	 */
	let short = $state(false);
	let remeasure: (() => void) | null = null;
	/** The widest the readout may become: its wrapper's max-width resolved in px (a probe), else the map's width. */
	function roomOf(box: HTMLElement): number {
		const wrap = box.parentElement;
		const host = wrap?.parentElement;
		if (!wrap || !host) return box.clientWidth;
		const spec = getComputedStyle(wrap).maxWidth;
		if (!spec || spec === 'none') return host.clientWidth;
		const probe = document.createElement('div');
		probe.style.cssText = `position:absolute;visibility:hidden;height:0;padding:0;border:0;width:${spec}`;
		host.appendChild(probe);
		const w = probe.offsetWidth;
		probe.remove();
		return w;
	}
	function fitRule(node: HTMLElement) {
		const measure = () => {
			const full = node.querySelector<HTMLElement>('.rule-full');
			const box = node.parentElement;
			if (!full || !box) return;
			// the room the chip has: the widest the readout may grow (its wrapper's max-width, resolved
			// against the map) minus its sibling chips and the gaps — the readout itself shrink-wraps
			const used = [...box.children].filter((c) => c !== node).reduce((w, c) => w + (c as HTMLElement).offsetWidth + 6, 0);
			short = full.scrollWidth + 30 > roomOf(box) - used;
		};
		const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
		// the readout and every sibling chip (the coordinate and the scale bar change width as the map moves)
		if (node.parentElement) for (const el of [node.parentElement, ...node.parentElement.children]) ro?.observe(el);
		remeasure = measure;
		measure();
		return { destroy: () => ro?.disconnect() };
	}
	// a language switch changes the full line's length: measure again once it rendered
	$effect(() => {
		void lang;
		queueMicrotask(() => remeasure?.());
	});
</script>

<div class="readout" data-map="readout">
	{#if lat != null && lon != null}
		<span class="box" title={t(lang, 'map_cursor')}><Coord {lat} {lon} /></span>
	{/if}
	{#if scale}
		<span class="box scale" title={t(lang, 'map_scale')}><i style:width={`${Math.round(scale.px)}px`}></i>{scale.label}</span>
	{/if}
	<span class="box rule" use:fitRule data-rule={short ? 'short' : 'full'} title={short ? t(lang, 'map_rule_note') : null}
		><Icon name={ACTION_ICON.policies} size={12} /><span class="rule-text">{short ? t(lang, 'map_rule_note_short') : t(lang, 'map_rule_note')}</span><span
			class="rule-full"
			aria-hidden="true">{t(lang, 'map_rule_note')}</span
		></span
	>
</div>

<style>
	.readout {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
		pointer-events: auto;
		font-family: var(--v-font-ui);
	}

	.box {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 22px;
		padding: 0 6px;
		border-radius: var(--v-radius-chip);
		background: var(--v-map-label-bg);
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}

	.box :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.scale i {
		display: inline-block;
		height: 6px;
		border: 1px solid var(--v-ink-2);
		border-top: 0;
	}

	.rule {
		position: relative;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	/* the measuring copy: laid out at full length, never seen */
	.rule-full {
		position: absolute;
		left: 0;
		top: 0;
		visibility: hidden;
		white-space: nowrap;
		pointer-events: none;
	}
</style>
