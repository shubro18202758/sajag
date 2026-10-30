<script lang="ts">
	/**
	 * ObjectTag — a typed object inline (SPEC §1.2, §5.1): the kind's glyph
	 * from KIND_ICON (events by their kind) and the label through the
	 * formatter: a vehicle's mark as a Plate (masked unless `masked` is
	 * false), a camera's id as an Id, anything else as text. With `onselect`
	 * it is a button that selects the object (selecting in one view selects
	 * it in all of them — the caller wires the selection).
	 *
	 * Root carries data-urn and data-kind; `...rest` goes on it.
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { objectIcon } from '$lib/design/icons';
	import Icon from './Icon.svelte';
	import Tooltip from './Tooltip.svelte';
	import Id from './format/Id.svelte';
	import Plate from './format/Plate.svelte';

	type LabelFormat = 'auto' | 'text' | 'id' | 'plate';

	interface Props extends Omit<HTMLAttributes<HTMLElement>, 'onselect'> {
		urn: string;
		kind: string;
		label: string;
		/** For a vehicle (or any plate label): whether the mark is masked. */
		masked?: boolean | null;
		/** For kind 'event': the corridor-event kind (its glyph). */
		eventKind?: string | null;
		format?: LabelFormat;
		onselect?: (urn: string) => void;
		tooltip?: string | null;
	}

	let {
		urn,
		kind,
		label,
		masked = null,
		eventKind = null,
		format = 'auto',
		onselect,
		tooltip = null,
		class: cls = '',
		...rest
	}: Props = $props();

	const ID_KINDS = new Set(['camera', 'unit', 'sighting', 'dispatch']);
	const shape = $derived<Exclude<LabelFormat, 'auto'>>(
		format !== 'auto' ? format : kind === 'vehicle' ? 'plate' : ID_KINDS.has(kind) ? 'id' : 'text'
	);
	const glyph = $derived(objectIcon(kind, eventKind));
</script>

{#snippet body()}
	<Icon name={glyph} size={16} />
	<span class="lbl">
		{#if shape === 'plate'}<Plate mark={label} masked={masked ?? true} />{:else if shape === 'id'}<Id
				value={label}
			/>{:else}{label}{/if}
	</span>
{/snippet}

{#snippet tagEl()}
	{#if onselect}
		<button
			type="button"
			data-ui="object-tag"
			data-urn={urn}
			data-kind={kind}
			class={['otag', 'interactive', cls]}
			onclick={() => onselect?.(urn)}
			{...rest}
		>
			{@render body()}
		</button>
	{:else}
		<span data-ui="object-tag" data-urn={urn} data-kind={kind} class={['otag', cls]} {...rest}>
			{@render body()}
		</span>
	{/if}
{/snippet}

{#if tooltip}
	<Tooltip content={tooltip}>{@render tagEl()}</Tooltip>
{:else}
	{@render tagEl()}
{/if}

<style>
	.otag {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		box-sizing: border-box;
		max-width: 100%;
		min-height: 20px;
		margin: 0;
		padding: 2px 6px;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		text-align: left;
		white-space: nowrap;
		vertical-align: middle;
	}

	.otag :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	/* the label is the tag's baseline (not the glyph's synthesized bottom edge),
	   so in a baseline row (a PropertyTable value) the tag's text sits on the
	   key's baseline and the row keeps its 30 px; in a 20 px tag with 2 px
	   padding the 16 px label line lands exactly where centring put it */
	.lbl {
		display: inline-flex;
		align-self: baseline;
		align-items: center;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.interactive {
		cursor: pointer;
	}

	.interactive:hover {
		box-shadow: inset 0 0 0 999px var(--v-neutral-veil);
	}

	.interactive:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 1px;
	}
</style>
