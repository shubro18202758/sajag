<script lang="ts">
	/**
	 * EventDossier — the dossier frame, rebuilt as the event property block of
	 * src/lib/ui (SPEC §5.2): the title (H5), the event id through the
	 * formatter (mono), the band chip and the state tag; then the page's
	 * grouped sections (details, phases, audit, advisory), each under a 12 px
	 * group heading like a PropertyTable group. The pages own the content.
	 * With no event: the honest empty state. `data-prim="event-dossier"` stays.
	 */
	import type { Band } from '$lib/design/tokens';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import Tag from '$lib/ui/Tag.svelte';
	import Id from '$lib/ui/format/Id.svelte';
	import { uiLang } from '$lib/ui/lang';
	import BandChip from './BandChip.svelte';
	import EmptyState from './EmptyState.svelte';
	import { sentenceStart } from './text';

	interface Props {
		event?: {
			eventId?: string | null;
			name?: string | null;
			band?: Band | null;
			state?: string | null;
		} | null;
		/** Override title when no event object is handed in. */
		title?: string;
		emptyTitle?: string;
		lang?: string;
		meta?: import('svelte').Snippet;
		phases?: import('svelte').Snippet;
		audit?: import('svelte').Snippet;
		advisory?: import('svelte').Snippet;
		footer?: import('svelte').Snippet;
		children?: import('svelte').Snippet;
	}

	let { event = null, title, emptyTitle, lang, meta, phases, audit, advisory, footer, children }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	const heading = $derived(title ?? event?.name ?? null);
</script>

{#snippet group(key: string, body: import('svelte').Snippet)}
	<div class="group" data-group={key}>
		<h4 class="gh">{t(L, `dossier_sec_${key}`)}</h4>
		{@render body()}
	</div>
{/snippet}

<section class="dossier" data-prim="event-dossier">
	{#if heading}
		<header class="head">
			<div class="title-row">
				<h3 class="title">{heading}</h3>
				{#if event?.band}<BandChip band={event.band} size="sm" lang={L} />{/if}
				{#if event?.state}<Tag>{sentenceStart(event.state)}</Tag>{/if}
			</div>
			{#if event?.eventId}
				<div class="eid"><Id value={event.eventId} /></div>
			{/if}
		</header>

		{#if meta}{@render group('meta', meta)}{/if}
		{#if phases}{@render group('phases', phases)}{/if}
		{#if audit}{@render group('audit', audit)}{/if}
		{#if advisory}{@render group('advisory', advisory)}{/if}

		{@render children?.()}

		{#if footer}
			<footer class="foot">
				{@render footer()}
			</footer>
		{/if}
	{:else}
		<EmptyState title={emptyTitle ?? t(L, 'dossier_empty')} hint={t(L, 'dossier_empty_hint')} />
	{/if}
</section>

<style>
	.dossier {
		display: flex;
		flex-direction: column;
		min-height: 0;
		padding: 12px 16px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
		box-shadow: var(--v-elev-0);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	.head {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding-bottom: 8px;
	}

	.title-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.title {
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: 20px;
		overflow-wrap: anywhere;
	}

	.eid {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	/* a group: the PropertyTable group heading (12 px, 600, ink-2) over its rows */
	.group {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 12px 0 8px;
		border-top: 1px solid var(--v-line-1);
	}

	.gh {
		margin: 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 600;
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.foot {
		padding-top: 8px;
		border-top: 1px solid var(--v-line-1);
	}
</style>
