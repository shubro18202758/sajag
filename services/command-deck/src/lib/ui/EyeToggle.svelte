<script lang="ts">
	/**
	 * EyeToggle — a layer's visibility: the eye-open / eye-off glyph in a
	 * 24 px minimal button (aria-pressed = visible, under a name that stays
	 * the same in both states: "Show: Cameras"). When the layer is
	 * `empty` the toggle dims and reads "None now", so an empty layer never
	 * looks broken or switched off. `visible` is bindable; `...rest` goes on
	 * the <button>.
	 */
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import { ACTION_ICON } from '$lib/design/icons';
	import Icon from './Icon.svelte';
	import Tooltip from './Tooltip.svelte';
	import { uiLang, ut } from './lang';

	interface Props extends Omit<HTMLButtonAttributes, 'onchange'> {
		visible?: boolean;
		empty?: boolean;
		/** What is shown or hidden (the layer's name), for the accessible label. */
		label?: string | null;
		onchange?: (visible: boolean) => void;
		lang?: string;
	}

	let {
		visible = $bindable(true),
		empty = false,
		label = null,
		onchange,
		lang,
		class: cls = '',
		...rest
	}: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	// the tooltip says what a click does; the accessible name stays fixed and
	// aria-pressed carries the state (a toggle's label never flips with it)
	const action = $derived(ut(L, visible ? 'ui_eye_hide' : 'ui_eye_show'));
	const name = $derived(label ? `${ut(L, 'ui_eye_show')}: ${label}` : ut(L, 'ui_eye_show'));

	function toggle(e: MouseEvent) {
		e.stopPropagation();
		visible = !visible;
		onchange?.(visible);
	}
</script>

<span data-ui="eye-toggle" data-visible={visible ? 'true' : 'false'} class={['eye', empty && 'empty', cls]}>
	{#if empty}<span class="none">{ut(L, 'ui_eye_none')}</span>{/if}
	<Tooltip content={action}>
		<button type="button" class={['btn', !visible && 'off']} aria-pressed={visible} aria-label={name} onclick={toggle} {...rest}>
			<Icon name={visible ? ACTION_ICON.layer_visible : ACTION_ICON.layer_hidden} size={16} />
		</button>
	</Tooltip>
</span>

<style>
	.eye {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		vertical-align: middle;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 24px;
		height: 24px;
		padding: 0;
		border: 0;
		border-radius: calc(var(--v-radius-btn) - 1px);
		background: transparent;
		color: var(--v-ink-1);
		cursor: pointer;
	}

	.btn:hover {
		background: var(--v-minimal-hover);
	}

	.btn:focus-visible {
		outline: 2px solid var(--v-focus);
	}

	.off {
		color: var(--v-ink-2);
	}

	.none {
		color: var(--v-ink-disabled);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		white-space: nowrap;
	}

	.empty .btn {
		color: var(--v-ink-disabled);
	}
</style>
