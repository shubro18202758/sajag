<script lang="ts">
	/**
	 * ActiveEvents (SPEC §5.3 Explorer, §9.2; §12.4) — the live corridor
	 * events, filling the S2X Explorer's `activeEvents` snippet. Rows
	 * `[data-event-id]` with the focus affordance `.ev-focus` (click:
	 * select the event and fly the canvas to it — LOCKED only when the
	 * flight lands, never claimed here). Provenance on every non-live row:
	 * a COMPACT emulated glyph whose hidden text is exactly "Emulated"
	 * (`liverail-emulated`, an ethics pin), a visible "Test" tag
	 * (`liverail-test`, its title carrying the plan label) on a labelled
	 * rehearsal, and a promoted OSINT report's verification tag. Titles ride
	 * the display-title layer, then the mask (audit E item 5): a pursuit's
	 * raw "PURSUIT — stolen … (FIR …)" reads "Pursuit of <mark>", masked
	 * whatever an officer state is.
	 *
	 * The highlight is the workspace selection's (audit C S2):
	 * `selection.current === 'event:<id>'` — the same fact the assistant
	 * scopes by — never `ops.selectedEventId` (the board's pick may differ
	 * from what the operator is looking at). Rows read LABELS: the kind
	 * through the vocabulary ("Vehicle pursuit") and the state through the
	 * display-label layer ("Planned"), never a raw enum.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { godsEye } from '$lib/gods-eye/store.svelte';
	import { focus } from '$lib/gods-eye/focus.svelte';
	import { displayText } from '$lib/gods-eye/plates';
	import { displayTitle } from '$lib/workspace/display';
	import { eventKindIcon, kindIcon } from '$lib/design/icons';
	import { Icon, ProvenanceTag, provideUiLang } from '$lib/ui';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { kindLabel, t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.agent';
	import { stateWord } from '$lib/workspace/kinds/generic';
	import '$lib/i18n/packs.corridor';
	import { TEST_TEXT, activeEventRows, eventProvenance, eventTestLabel, eventVerification } from './events';
	type UiVerification = 'UNVERIFIED-OSINT' | 'NEWS-REPORTED' | 'OFFICIAL-VERIFIED' | 'CONFIRMED';
	const asUiVerification = (v: ReturnType<typeof eventVerification>): UiVerification | null =>
		v === 'UNVERIFIED-OSINT' || v === 'NEWS-REPORTED' || v === 'OFFICIAL-VERIFIED' || v === 'CONFIRMED' ? v : null;
	import type { CorridorEvent } from '$lib/ops/types';

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	const rows = $derived(activeEventRows(ops.events));

	/** The row's state through the display-label layer (a state the pack lacks degrades to its humanised word). */
	const stateLabel = (ev: CorridorEvent) => stateWord(ev.state, lang) ?? ev.state;

	function selectEvent(ev: CorridorEvent) {
		// Re-selecting the selected event must not reset its band + audit tail.
		if (ops.selectedEventId !== ev.eventId) ops.selectEvent(ev.eventId);
		selection.select(`event:${ev.eventId}`, { source: 'rail' });
		focus.request(ev.eventId); // the canvas flies, locks when it lands, then reports back
	}

	/** Honest per-row focus state: locked only once the canvas holds the camera. */
	function focusState(id: string): { label: string; tone: 'ok' | 'wait' | 'warn' } | null {
		if (godsEye.subjectLockId === id) return { label: L('cor_events_focus_locked'), tone: 'ok' };
		if (focus.eventId !== id) return null;
		if (focus.outcome === 'pending') return { label: L('cor_events_focus_locating'), tone: 'wait' };
		if (focus.outcome === 'no-geometry') return { label: L('cor_events_no_spine'), tone: 'warn' };
		if (focus.outcome === 'no-canvas') return { label: L('cor_events_no_canvas'), tone: 'warn' };
		return null; // locked-then-released, or cancelled by the operator
	}

	const kindGlyph = (ev: CorridorEvent) => eventKindIcon(ev.eventKind);
</script>

<div class="active-events" data-testid="active-events">
	{#if rows.length === 0}
		<p class="empty">{L('cor_events_none')}</p>
	{:else}
		<ul>
			{#each rows as ev (ev.eventId)}
				{@const prov = eventProvenance(ev)}
				{@const verification = eventVerification(ev)}
				{@const testLabel = eventTestLabel(ev)}
				{@const fs = focusState(ev.eventId)}
				<li>
					<button
						type="button"
						class="ev"
						class:selected={selection.current === `event:${ev.eventId}`}
						data-event-id={ev.eventId}
						onclick={() => selectEvent(ev)}
						title={displayText(displayTitle(ev.name, lang), false)}
					>
						<span class="ev-name">{displayText(displayTitle(ev.name, lang), false)}</span>
						<span class="ev-kind">
							<Icon name={kindGlyph(ev)} size={12} />
							{kindLabel(lang, ev.eventKind)}
							<!-- provenance on the kind line, never inside the cut name: the marker always shows -->
							{#if prov === 'emulated'}
								<span data-testid="liverail-emulated"><ProvenanceTag source="emulated" compact {lang} /></span>
							{:else if prov === 'osint'}
								<ProvenanceTag source="osint" verification={asUiVerification(verification)} {lang} />
							{/if}
							{#if testLabel}
								<span
									class="ev-test"
									data-testid="liverail-test"
									title={L('cor_events_test_tip', displayText(testLabel, false))}
								>{lang === 'en' ? TEST_TEXT : t(lang, 'dossier_test')}</span>
							{/if}
							{#if fs}
								<span
									class="ev-focus tone-{fs.tone}"
									title={focus.eventId === ev.eventId && focus.note ? displayText(focus.note, false) : undefined}
								>
									· {fs.label}
								</span>
							{/if}
						</span>
						<span class="ev-state" data-state={ev.state}>{stateLabel(ev)}</span>
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.active-events {
		min-width: 0;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.empty {
		margin: 0;
		padding: 2px 16px 10px;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	ul {
		list-style: none;
		margin: 0;
		padding: 0 8px 8px;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.ev {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 2px;
		width: 100%;
		padding: 4px 8px;
		background: transparent;
		border: 0;
		border-left: 2px solid transparent;
		border-radius: var(--v-radius-btn);
		color: var(--v-ink-1);
		cursor: pointer;
		text-align: left;
		font: inherit;
	}

	.ev:hover {
		background: var(--v-minimal-hover);
	}

	.ev.is-selected,
	.ev.selected {
		background: var(--v-primary-veil);
		border-left-color: var(--v-primary-text);
	}

	.ev-name {
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--v-text-xs);
	}

	.ev-kind {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		max-width: 100%;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.ev-kind :global(svg) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	/* a labelled rehearsal is a quiet fact of the console, not a warning:
	   neutral ink (SPEC §2.4 — orange is only ever a waiting decision) */
	.ev-test {
		padding: 0 5px;
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-pill);
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		white-space: nowrap;
	}

	.ev-focus {
		white-space: nowrap;
	}

	.ev-focus.tone-ok {
		color: var(--v-primary-text);
	}

	.ev-focus.tone-wait {
		color: var(--v-ink-2);
	}

	.ev-focus.tone-warn {
		color: var(--v-warning-text);
	}

	.ev-state {
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}
</style>
