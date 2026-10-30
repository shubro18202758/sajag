<script lang="ts">
	/**
	 * A reported situation's Overview (V3-SPEC §6.3) — the v2 report section's content (osint/model.ts
	 * readReport: the whitelist reader, the only path any report field has to the page), made glanceable:
	 *
	 *   What is reported      the ONE summary line, already redacted at parse; [PERSON] / [AGE] as chips
	 *                         ("name withheld", "age withheld"), with the rule in words
	 *   How sure are we       CredibilityMeter: gauge, four plain checks, the verification ladder
	 *   What it may affect    the report's second-order flags — where the place meets live operations NOW
	 *                         (flags from the oracle's correlation with live state, not forecasts); each tile
	 *                         opens the affected record
	 */
	import { t } from '$lib/i18n/strings';
	import './packs.object';
	import Glyph from '../Glyph.svelte';
	import RedactedText from '../ui/RedactedText.svelte';
	import Panel from './Panel.svelte';
	import CredibilityMeter from './CredibilityMeter.svelte';
	import { objectHref, type Check, type EffectTile } from './model';
	import type { OsintReportProps } from '$lib/osint/model';
	import { kindOne } from '$lib/workspace/kinds/generic';
	import { readableIn, scriptOf } from '$lib/i18n/script';
	import '../packs.v3';

	let {
		report,
		summary,
		credibility,
		checks,
		effects,
		lang,
	}: { report: OsintReportProps; summary: string | null; credibility: number | null; checks: readonly Check[]; effects: readonly EffectTile[]; lang: string } = $props();

	/** The summary's own script when the reader does not read it: the original stays (it IS the report), labelled, never machine-translated. */
	const foreign = $derived.by(() => {
		if (!summary || readableIn(summary, lang)) return null;
		const sc = scriptOf(summary);
		return sc === 'mr' || sc === 'hi' ? sc : null;
	});
</script>

<Panel title={t(lang, 'obj_reported_h')} testid="obj-reported">
	{#if summary}
		{#if foreign}<p class="orig" data-testid="obj-summary-original">{t(lang, `v3_text_original_${foreign}`)}</p>{/if}
		<p class="quote" data-testid="obj-summary" lang={foreign ?? undefined}>“<RedactedText text={summary} {lang} />”</p>
	{:else}
		<p class="quiet">{t(lang, 'obj_no_summary')}</p>
	{/if}
	<p class="note"><Glyph name="eyeoff" size={17} />{t(lang, 'obj_redact_note')}</p>
</Panel>

<Panel title={t(lang, 'obj_sure_h')} testid="obj-sure">
	<CredibilityMeter {credibility} {checks} verification={report.verification} {lang} />
</Panel>

<Panel title={t(lang, 'obj_affect_h')} testid="obj-affect">
	{#if effects.length}
		<ul class="effects">
			{#each effects as e (e.urn)}
				{@const href = objectHref(e.urn)}
				<li>
					<svelte:element this={href ? 'a' : 'div'} class="tile" href={href ?? undefined} data-urn={e.urn}>
						<Glyph name={e.glyph} size={20} />
						<b>{e.label ?? kindOne(e.kind, lang)}</b>
						{#each e.notes as n, i (i)}<span>{n}</span>{/each}
					</svelte:element>
				</li>
			{/each}
		</ul>
	{:else}
		<p class="quiet">{t(lang, 'obj_affect_none')}</p>
	{/if}
	<p class="note"><Glyph name="info" size={17} />{t(lang, 'obj_affect_note')}</p>
</Panel>

<style>
	.orig {
		margin: 0 0 6px;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
		line-height: var(--v3-lh-micro);
	}

	.quote {
		margin: 0;
		color: var(--v3-t1);
		font-size: 18px;
		line-height: 28px;
	}

	.quiet {
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
	}

	.note {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 19px;
	}

	.note :global(.v3-glyph) {
		margin-top: 1px;
		color: var(--v3-t3);
	}

	.effects {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 12px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.tile {
		display: flex;
		flex-direction: column;
		gap: 6px;
		height: 100%;
		padding: 14px 16px;
		border-radius: 14px;
		background: var(--v3-s2);
		color: var(--v3-t1);
		text-decoration: none;
	}

	a.tile:hover {
		background: var(--v3-s3);
	}

	a.tile:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.tile :global(.v3-glyph) {
		color: var(--v3-t2);
	}

	.tile b {
		font-size: var(--v3-text-body);
		font-weight: 650;
	}

	.tile span {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 19px;
	}

	@media (max-width: 1500px) {
		.effects {
			grid-template-columns: 1fr;
		}
	}
</style>
