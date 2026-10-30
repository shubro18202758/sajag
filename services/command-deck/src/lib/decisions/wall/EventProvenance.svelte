<script lang="ts">
	/**
	 * A promoted OSINT event's provenance in a row (SPEC §9.2, ethics rule 7):
	 * the verification tag WITH its visible label ("Unverified OSINT",
	 * "News-reported", …) and the credibility. Renders nothing for an event
	 * that is not open-source. The copy comes from provenance.ts.
	 */
	import { ProvenanceTag } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import type { CorridorEvent } from '$lib/ops/types';
	import { eventProvenance } from './provenance';

	interface Props {
		event: Pick<CorridorEvent, 'sourceKind' | 'verificationState' | 'credibility'>;
		lang?: string;
	}

	let { event, lang = 'en' }: Props = $props();

	const p = $derived(eventProvenance(event, lang));
</script>

{#if p}
	<ProvenanceTag source="osint" verification={p.verification} {lang} data-testid="event-verification" />
	{#if p.credibilityText}
		<span class="cred" data-testid="event-credibility" title={t(lang, 'wall_ops_credibility_tip')}>{p.credibilityText}</span>
	{/if}
{/if}

<style>
	.cred {
		flex: 0 0 auto;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
</style>
