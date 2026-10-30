<script lang="ts" module>
	/** Structural mirror of ops AuditLevel (primitives cannot import $lib/ops). */
	export type FeedLevel = 'info' | 'decision' | 'tool' | 'model' | 'band' | 'error';
	/** Structural mirror of ops AuditSource. */
	export type FeedSource = 'ws-event' | 'ws-convoy' | 'ndjson-chat' | 'audit-poll' | 'operator' | (string & {});
</script>

<script lang="ts">
	/**
	 * FeedItem — one row of the decision audit, rebuilt as the AuditTable row
	 * renderer of src/lib/ui (SPEC §5.2, §5.3): the IST time (Inter, tabular),
	 * the actor's glyph from the frozen ACTOR_ICON map (an officer, Sajag AI in
	 * indigo, the rules engine, the system), the actor, the text, the compact
	 * provenance glyphs (their hidden labels read "Emulated" / "Simulated")
	 * and the source tag. A row with `detail` is a button that opens the
	 * evidence in a Dialog. Officers' rows read in ink-1; system bookkeeping
	 * (the emulator, event-closed walks) recedes to ink-2 so it never reads as
	 * a person or a model. AuditRow = FeedItem + its source.
	 *
	 * `data-prim="feed-item"`, `data-level`, `data-actor-kind`, `data-row-id`
	 * and `row-simulated` stay; the row's textContent carries the actor and
	 * the text (the smokes read both).
	 */
	import { ACTOR_ICON, INTENT_ICON, type IconName } from '$lib/design/icons';
	import Icon from '$lib/ui/Icon.svelte';
	import ProvenanceTag from '$lib/ui/ProvenanceTag.svelte';
	import Tag from '$lib/ui/Tag.svelte';
	import Time from '$lib/ui/format/Time.svelte';
	import { fmtTime } from '$lib/ui/format/format';
	import Modal from './Modal.svelte';

	interface Props {
		ts: number;
		actor: string;
		actorKind: 'human' | 'machine' | 'system';
		level: FeedLevel;
		text: string;
		detail?: unknown;
		source?: FeedSource | null;
		/** The row's source is emulated — the compact Emulated glyph. */
		emulated?: boolean;
		/** The row's numbers came from a SIMULATED feed (C-Q) — the compact Simulated glyph. */
		simulated?: boolean;
		/** Server rows: the stable FeedItem id (data attribute for tests/deep links). */
		rowId?: string | null;
		lang?: string;
		right?: import('svelte').Snippet;
		children?: import('svelte').Snippet;
	}

	let {
		ts,
		actor,
		actorKind,
		level,
		text,
		detail,
		source = null,
		emulated = false,
		simulated = false,
		rowId = null,
		lang,
		right,
		children
	}: Props = $props();

	let open = $state(false);

	const hasDetail = $derived(detail !== undefined && detail !== null);
	const glyph = $derived<IconName>(
		actorKind === 'human'
			? ACTOR_ICON.officer
			: actorKind === 'system'
				? ACTOR_ICON.system
				: level === 'error'
					? INTENT_ICON.danger
					: level === 'model' || level === 'tool'
						? ACTOR_ICON.ai
						: ACTOR_ICON.rules
	);
	const ai = $derived(actorKind === 'machine' && (level === 'model' || level === 'tool'));

	function rowText(): string {
		return `${fmtTime(ts, { seconds: true })} IST · ${actor} · ${text}`;
	}
</script>

{#snippet cells()}
	<Time value={ts} seconds class="ts" />
	<span class="glyph" class:ai><Icon name={glyph} size={16} /></span>
	<span class="actor" title={actor}>{actor}</span>
	<span class="text">{text}{@render children?.()}</span>
	{#if emulated || simulated || source}
		<span class="marks">
			{#if emulated}<ProvenanceTag source="emulated" compact {lang} />{/if}
			{#if simulated}<ProvenanceTag source="simulated" compact {lang} data-testid="row-simulated" />{/if}
			{#if source}<Tag class="src">{source}</Tag>{/if}
		</span>
	{/if}
	{@render right?.()}
{/snippet}

{#if hasDetail}
	<button
		class="row clickable {actorKind}"
		type="button"
		aria-label={rowText()}
		onclick={() => (open = true)}
		data-prim="feed-item"
		data-level={level}
		data-actor-kind={actorKind}
		data-row-id={rowId ?? undefined}
	>
		{@render cells()}
	</button>
	<Modal {open} title="{actor} · {text}" onClose={() => (open = false)}>
		<pre class="detail">{JSON.stringify(detail, null, 2)}</pre>
	</Modal>
{:else}
	<div class="row {actorKind}" data-prim="feed-item" data-level={level} data-actor-kind={actorKind} data-row-id={rowId ?? undefined}>
		{@render cells()}
	</div>
{/if}

<style>
	/* wraps rather than squeezes: in a narrow host the text drops to its own
	   full-width line instead of collapsing to a sliver beside a long name.
	   Never shrinks either: the explicit min-height replaces a flex item's
	   content minimum, so in a fixed-height flex-column scroller (the trace
	   console, the dossier narrative) a shrinkable row would be squeezed
	   under its own text; the scroller scrolls instead. */
	.row {
		display: flex;
		flex: 0 0 auto;
		flex-wrap: wrap;
		align-items: center;
		column-gap: 8px;
		row-gap: 2px;
		box-sizing: border-box;
		width: 100%;
		min-height: var(--v-ws-row);
		margin: 0;
		padding: 4px 8px;
		border: 0;
		border-bottom: 1px solid var(--v-line-1);
		border-radius: 0;
		background: transparent;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		text-align: left;
	}

	.clickable {
		cursor: pointer;
	}

	.clickable:hover {
		background: var(--v-row-hover);
	}

	.clickable:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.row :global(.ts) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.glyph {
		display: inline-flex;
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.glyph.ai {
		color: var(--v-ai-text);
	}

	.actor {
		flex: 0 1 auto;
		max-width: 100%;
		min-width: 0;
		overflow: hidden;
		color: var(--v-ink-2);
		font-weight: 600;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.human .actor {
		color: var(--v-ink-1);
	}

	.text {
		flex: 1 1 14rem;
		min-width: 0;
		/* long audit tokens (ids, channel names) wrap, never overflow */
		overflow-wrap: anywhere;
	}

	/* system bookkeeping recedes: never read as a person or a model */
	.system .text {
		color: var(--v-ink-2);
	}

	.marks {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 4px;
	}

	.marks :global(.src) {
		color: var(--v-ink-2);
	}

	.detail {
		margin: 0;
		overflow-x: auto;
		color: var(--v-ink-2);
		font-family: inherit;
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		white-space: pre-wrap;
	}
</style>
