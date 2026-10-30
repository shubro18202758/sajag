<script lang="ts">
	/**
	 * The provenance marks of one Corridor operations row (SPEC §9.2, ethics
	 * rule 7):
	 *
	 *   Fixture   a labelled use-case fixture: a "Fixture" tag
	 *   Test      ALWAYS a visible "Test" tag (never the compact glyph: its
	 *             label must read on screen, not only to a screen reader)
	 *   Emulated  the compact glyph in a mixed list; nothing when the list is
	 *             uniform (`uniform`), because the header states it once
	 *   OSINT     the visible verification label and the credibility
	 *             (EventProvenance)
	 *
	 * Live rows carry nothing.
	 */
	import { ProvenanceTag, Tag } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import type { CorridorEvent } from '$lib/ops/types';
	import EventProvenance from './EventProvenance.svelte';
	import { isEmulatedEvent, isTestEvent } from './provenance';

	interface Props {
		event: Pick<CorridorEvent, 'name' | 'metadata' | 'emulated' | 'source' | 'sourceKind' | 'verificationState' | 'credibility'>;
		lang?: string;
		/** The list is uniformly emulated: its header carries the tag, so the row does not. */
		uniform?: boolean;
	}

	let { event, lang = 'en', uniform = false }: Props = $props();
</script>

{#if event.source === 'offline-fixture'}<Tag tooltip={t(lang, 'wall_ops_fixture_tip')}>{t(lang, 'wall_ops_fixture')}</Tag>{/if}
{#if isTestEvent(event)}<ProvenanceTag source="test" {lang} data-testid="event-test" />{/if}
{#if !uniform && isEmulatedEvent(event)}<ProvenanceTag source="emulated" compact {lang} />{/if}
<EventProvenance {event} {lang} />
