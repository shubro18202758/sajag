<script lang="ts">
	/**
	 * The dss card's resource-blocked best response, in the card HEADER area
	 * above the recommendation (FIX-E-DSSCARD item 6: the banner lived inside
	 * the "Why" body, below "What changes" and below the fold on /ops at
	 * 1920).
	 *
	 * The line names the blocked response, what is missing and, in the
	 * console's language, how to unblock it (FIX-E-DSSCARD item 4: the raw
	 * engine enum printed verbatim); beside it a LINK that
	 * opens the Dispatch surface (/ops, its Request-unit form). Sajag files NO
	 * dispatch request from this banner — the request form in Dispatch is the
	 * one write path, officer-gated there, and it takes no prefill (fix
	 * round 2: the banner's own dispatch-writing button is gone; it filed one
	 * hard-coded unit per click and misreported the count). The link is a
	 * plain navigation aid, never gated: Dispatch says, inline, what a
	 * request needs. The block is a NEUTRAL note (a resource fact, not the
	 * orange "decision waits" colour — fix round 2, prototype 05's next-step
	 * treatment) with the warning glyph only. The object is the card's ONE
	 * shared fetch (`ensureDssObject` — a hidden /ops item fetches nothing;
	 * the body's observer shares the same once-per-id guard), so before it
	 * lands the banner renders nothing; a failed GET is stated ONCE, by the
	 * body's failure line with its Retry (fix round 2 removed the banner's
	 * duplicate).
	 */
	import { goto } from '$app/navigation';
	import { ops } from '$lib/ops/store.svelte';
	import { INTENT_ICON } from '$lib/design/icons';
	import { Icon } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.dss';
	import type { DssData, Unit } from '$lib/decisions/units';
	import { bestBlockedLine } from './dss-data';
	import { dssState, ensureDssObject } from './dss-store.svelte';

	let { unit, lang = ops.lang }: { unit: Unit; lang?: string } = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const dss = $derived(dssState.objects[unit.id] ?? null);
	const line = $derived(bestBlockedLine(lang, dss));
	/** The corridor event units are requested against: the subject itself when it is an event, else the event an OSINT
	 *  report was promoted to. An unpromoted report has none — Dispatch cannot request units for it yet. */
	const d = $derived(unit.data as unknown as DssData);
	const eventId = $derived(d?.subjectKind === 'event' ? d.urn.replace(/^event:/, '') : (d?.promotedEventId ?? null));

	/** Select the event in Dispatch (its Request-unit form follows the selected event), then open /ops. */
	function openDispatch(e: MouseEvent) {
		if (!eventId) return;
		e.preventDefault();
		ops.selectedEventId = eventId;
		if (typeof location === 'undefined' || location.pathname !== '/ops') void goto('/ops');
	}

	// the same visible-when-intersecting fetch the body runs (one GET per id)
	let root = $state<HTMLDivElement | null>(null);
	$effect(() => {
		if (typeof IntersectionObserver === 'undefined') return;
		if (!root) return;
		const io = new IntersectionObserver((entries) => {
			if (entries.some((e) => e.isIntersecting)) void ensureDssObject(unit.id);
		});
		io.observe(root);
		return () => io.disconnect();
	});
</script>

<div bind:this={root}>
	{#if line}
		<p class="blocked" data-testid="dss-best-blocked">
			<Icon name={INTENT_ICON.warning} size={16} />
			<span class="b-line">{line}</span>
			{#if eventId}
				<a class="open-dispatch" data-testid="dss-open-dispatch" data-event={eventId} href="/ops" onclick={openDispatch}>{L('dss_best_blocked_open_dispatch')}</a>
			{:else}
				<span class="open-dispatch no-event" data-testid="dss-dispatch-needs-event">{L('dss_best_blocked_needs_event')}</span>
			{/if}
		</p>
	{/if}
</div>

<style>
	.blocked {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 4px 8px;
		margin: 12px 16px 0;
		padding: 8px 12px;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		font-size: var(--v-text-xs);
		line-height: 18px;
		color: var(--v-ink-1);
		overflow-wrap: anywhere;
	}

	.blocked :global(svg) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.b-line {
		flex: 1 1 0;
		min-width: 0;
	}

	/* the next step on its own row, under the sentence (a nowrap link beside it squeezed the line to ~170 px) */
	.open-dispatch {
		flex: 1 0 100%;
		padding-left: 24px;
		color: var(--v-ink-1);
		font-size: var(--v-text-xs);
		line-height: 18px;
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.no-event {
		color: var(--v-ink-2);
		text-decoration: none;
	}

	.open-dispatch:hover {
		color: var(--v-primary-text);
	}
</style>
