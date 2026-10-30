<script lang="ts">
	/**
	 * SourcesList (V3-SPEC §6.3 Sources tab; OSINT rules 1–3) — who reported the situation, one row per
	 * REPORTING source (model.ts reportingSources over osint/model.ts sourceRows: a context member is never a
	 * row here): the publisher, ITS OWN tier, a cached-sample tag only when the copy really is one, and the
	 * already-redacted title with its redactions as chips.
	 *
	 *   a news / social source   NO link, ever (the deck never holds one): "Link not kept: it may name a person"
	 *   an official source       a link only when its TIER is official and its url is https
	 *                            (rel="noopener noreferrer"); officialness never rides the web address
	 *   no official source yet   said once, with what would change it
	 *   context                  an alert in effect for the district, listed apart and never counted
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.osint';
	import { kindLabel } from '$lib/i18n/strings';
	import { contextLine, tierWord, type OsintReportProps } from '$lib/osint/model';
	import AgencyMark from '../media/AgencyMark.svelte';
	import { sourceMark } from '../media/logos';
	import './packs.object';
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import RedactedText from '../ui/RedactedText.svelte';
	import { officialLink, reportingSources } from './model';

	let { report, lang }: { report: OsintReportProps; lang: string } = $props();

	const T = (key: string, ...args: unknown[]): string => (key.startsWith('os_event_kind_') ? kindLabel(lang, key.slice('os_event_kind_'.length)) : t(lang, key, ...args));
	const rows = $derived(reportingSources(report));
	const anyOfficial = $derived(rows.some((r) => r.official));
	const context = $derived(contextLine(report, T));
	const snapshotOnly = $derived(!report.sources.length && rows.length > 0);
</script>

<ul class="srcs" data-testid="obj-sources">
	{#each rows as r (r.signalId ?? `pub:${r.publisher.toLowerCase()}`)}
		{@const href = officialLink(r)}
		<li class="src" data-testid="obj-source" data-publisher={r.publisher} data-official={r.official ? '1' : '0'} data-withheld={r.linkWithheld ? '1' : '0'}>
			<div class="pub">
				{#if sourceMark(r.publisher)}<AgencyMark role={null} mark={sourceMark(r.publisher)} {lang} size={22} decorative />{:else}<Glyph name={r.official ? 'verified' : 'news'} size={18} />{/if}
				<span>{r.publisher}</span>
				{#if r.tier}<V3Tag size="sm" tone={r.official ? 'ok' : 'ghost'}>{tierWord(r.tier, lang, T)}</V3Tag>{/if}
				{#if r.fetchMode === 'cached-sample'}<V3Tag size="sm" tone="dashed">{t(lang, 'obj_src_cached')}</V3Tag>{/if}
			</div>
			{#if href}
				<a class="ttl link" {href} target="_blank" rel="noopener noreferrer" data-testid="obj-official-link"
					>{#if r.title}<RedactedText text={r.title} {lang} />{:else}{t(lang, 'obj_src_open')}{/if}<Glyph name="arrowUR" size={15} /></a
				>
			{:else if r.title}
				<p class="ttl">“<RedactedText text={r.title} {lang} />”</p>
			{/if}
			{#if !r.official && r.linkWithheld}
				<p class="nl"><Glyph name="eyeoff" size={16} />{t(lang, 'obj_src_link_withheld')}</p>
			{/if}
		</li>
	{/each}
	{#if !anyOfficial}
		<li class="src" data-testid="obj-source-official-none">
			<div class="pub"><Glyph name="verified" size={18} /><span>{t(lang, 'obj_src_official_h')}</span><V3Tag size="sm" tone="dashed">{t(lang, 'obj_src_none_yet')}</V3Tag></div>
			<p class="ttl">{t(lang, 'obj_src_official_hint')}</p>
		</li>
	{/if}
</ul>
{#if snapshotOnly}<p class="hint">{t(lang, 'obj_src_snapshot')}</p>{/if}
{#if context}
	<div class="context" data-testid="obj-context">
		<p class="cap">{t(lang, 'obj_src_context_h')}</p>
		<p class="ctx">{context}</p>
		<p class="hint"><Glyph name="info" size={15} />{t(lang, 'obj_context_note')}</p>
	</div>
{/if}

<style>
	.srcs {
		display: flex;
		flex-direction: column;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.src {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 12px 0;
		border-top: 1px solid var(--v3-line-1);
	}

	.src:first-child {
		padding-top: 2px;
		border-top: 0;
	}

	.pub {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
		color: var(--v3-t1);
		font-size: 14px;
		font-weight: 650;
	}

	.pub :global(.v3-glyph) {
		color: var(--v3-t2);
	}

	.ttl {
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
		line-height: 20px;
	}

	.link {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--v3-brand-text);
		font-weight: 600;
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.link:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.nl {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
		line-height: var(--v3-lh-micro);
	}

	.context {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding-top: 12px;
		border-top: 1px dashed var(--v3-line-2);
	}

	.cap {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
	}

	.ctx {
		margin: 0;
		color: var(--v3-t1);
		font-size: 14px;
	}

	.hint {
		display: flex;
		align-items: flex-start;
		gap: 6px;
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 19px;
	}
</style>
