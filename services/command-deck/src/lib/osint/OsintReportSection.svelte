<script lang="ts">
	/**
	 * The inspector's report section (OS-DECK-A; registered for `osint_event`
	 * by osint/register.ts, id 'osint-report', order 10). A reported
	 * situation, honestly labelled, PLACE-CENTRED, WHITELISTED: the view
	 * model (model.ts reportView) reads the C-T field names and the C-Q
	 * provenance one key at a time — never the raw props — so no field a
	 * source must never send (an author, a byline, a handle) has a rendering
	 * path (ethics rules 1–3).
	 *
	 *   Situation    the ONE summary line (already redacted at parse) —
	 *                class, subtype and correlated classes, and the whole
	 *                Location group, live in the inspector's Properties
	 *                groups (generic.ts) so the tabs stay above the fold
	 *   Verification the ProvenanceTag (osint-verification[data-verification]),
	 *                independent publishers, cross-type corroboration —
	 *                de-duplicated with the inspector's header (the
	 *                credibility figure lives there, exactly once)
	 *   Sources      one row per source (osint-source): its publisher, ITS
	 *                OWN tier tag (S1: from the dossier's source_notes keyed
	 *                by signal_id, localized — S3 round 2), the redacted
	 *                title (an OFFICIAL row names its title once, as the
	 *                link text) and a cached-sample tag ONLY when the copy
	 *                really is one (`fetch_mode` is 'live' or
	 *                'cached-sample'), and a link ONLY on an official tier's
	 *                https: url (rel="noopener noreferrer"; a news/social
	 *                url is never held deck-side — the list says so once,
	 *                not once per row); a district alert in effect is
	 *                CONTEXT, listed apart, never corroboration. "n social
	 *                posts held" appears nowhere on a per-report view (R1):
	 *                the count, when the oracle holds any, is the layer's
	 *                one city-wide line
	 *   Live state   new / corroborates / promoted; second-order flags as
	 *                one neutral Note per distinct wording, a count when the
	 *                words repeat (keyed by index either way)
	 *
	 * The one rule note: "Reported situation for response. Sajag never
	 * identifies people." No decision verb lives here — promote and decision
	 * support have their one home (OS-DECK-B).
	 */
	import type { InspectorSectionProps } from '$lib/workspace/types';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { kindIcon } from '$lib/design/icons';
	import { Icon, Id, Note, ProvenanceTag, Tag } from '$lib/ui';
	import { kindLabel, t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.osint';
	import { shellClock, useShellClock } from '$lib/shell/clock.svelte';
	import PropertyGroups from '$lib/workspace/components/inspector/PropertyGroups.svelte';
	import { readReport, reportView, tierWord } from './model';

	let { row, dossier }: InspectorSectionProps = $props();

	useShellClock();
	const lang = $derived(ops.lang);
	const now = $derived(shellClock.now);

	/** The model's key mapper: an event-kind key resolves through kindLabel (never a raw key). */
	const T = (key: string, ...args: unknown[]): string =>
		key.startsWith('os_event_kind_') ? kindLabel(lang, key.slice('os_event_kind_'.length)) : t(lang, key, ...args);

	const p = $derived(readReport(row.props));
	/** The ProvenanceTag's own union: the four OSINT states (EMULATED/SIMULATED never come from an open-source row). */
	const tagVerifOf = (v: string | null | undefined) =>
		v === 'UNVERIFIED-OSINT' || v === 'NEWS-REPORTED' || v === 'OFFICIAL-VERIFIED' || v === 'CONFIRMED' ? v : null;
	const view = $derived(reportView(p, dossier, T, { lang, now }));

	/** An official row's link: an https: url only (the model has already dropped the rest). */
	const officialHref = (url: string | null): string | null => (url != null && url.startsWith('https:') ? url : null);

	function select(urn: string) {
		selection.select(urn, { source: 'dossier' });
	}
</script>

<section class="report" data-testid="osint-report" data-kind="osint_event" data-verification={p.verification ?? ''}>
	{#each view.sections as s (s.title)}
		<div class="grp" data-testid={s.testid} data-section-title={s.title}>
			{#if s.verification !== undefined}
				<div class="verif">
					<ProvenanceTag source="osint" verification={tagVerifOf(s.verification)} {lang} data-testid="osint-verification" data-verification={s.verification ?? ''} />
				</div>
			{/if}
			{#if s.rows.length}
				<PropertyGroups groups={[{ title: s.title, rows: s.rows }]} {now} onselect={select} />
			{/if}
			{#if s.sources?.length}
				<div class="cap">{s.title}</div>
				<ul class="sources">
					{#each s.sources as src (src.signalId ?? `pub:${src.publisher.toLowerCase()}`)}
						<li class="src" data-testid="osint-source" data-signal={src.signalId ?? ''} data-publisher={src.publisher} data-official={src.official ? '1' : '0'} data-withheld={src.linkWithheld ? '1' : '0'}>
							<Icon name={kindIcon('osint_event')} size={12} class="g" />
							<Id value={src.publisher} />
							{#if src.tier}<Tag>{tierWord(src.tier, lang, T)}</Tag>{/if}
							{#if src.title && !src.official}<span class="title">{src.title}</span>{/if}
							{#if src.fetchMode === 'cached-sample'}<Tag>{t(lang, 'os_fetch_cached')}</Tag>{/if}
							{#if src.official && src.url}<a href={officialHref(src.url)} rel="noopener noreferrer">{src.title ?? src.publisher}</a>{/if}
						</li>
					{/each}
				</ul>
				{#if s.sources.some((src) => src.linkWithheld)}<span class="withheld">{t(lang, 'os_source_link_withheld')}</span>{/if}
			{/if}
			{#if s.notes?.length}
				<div class="notes">
					{#each s.notes as n, i (i)}<Note icon="help" text={n} />{/each}
				</div>
			{/if}
		</div>
	{/each}
	<div class="rule"><Note icon="eye-off" text={view.note} /></div>
</section>

<style>
	.report {
		display: flex;
		flex-direction: column;
		gap: 4px;
		/* the section renders INSIDE the inspector's Properties tab now (fix round 2, item 7):
		   the tab body already carries the console gutter, so the section pads vertically only */
		padding: 4px 0 8px;
		border-bottom: 1px solid var(--v-line-2);
	}

	.verif {
		display: flex;
		padding: 4px 0 0;
	}

	.cap {
		padding: 12px 0 4px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 600;
		line-height: 16px;
	}

	.sources {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.src {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 4px 8px;
		color: var(--v-ink-1);
		font-size: var(--v-text-xs);
		line-height: 20px;
	}

	.src :global(.g) {
		align-self: center;
		color: var(--v-ink-2);
	}

	.src .title {
		color: var(--v-ink-2);
		overflow-wrap: anywhere;
	}

	.src :global(a) {
		color: var(--v-ink-1);
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.withheld {
		color: var(--v-ink-2);
	}

	.notes {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 6px 0 0;
	}

	.rule {
		padding: 8px 0 0;
	}
</style>
