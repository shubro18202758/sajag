<script lang="ts">
	/**
	 * The Advisories side sheet (V3-SPEC §6.7): the two things the colleague review moved off the desk — this tab's draft
	 * log and the dispatch threads — behind one calm sheet. Nothing here is delivery: the log is "drafts kept in this
	 * browser tab", the threads are the inter-agency dispatch lifecycle the officers decide elsewhere (read only here).
	 *
	 * It is a non-modal complementary region (the desk behind it stays usable); Esc closes it and returns focus to the
	 * button that opened it. Rendered only while open.
	 */
	import { onMount, tick } from 'svelte';
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import { agencyByCode, DISPATCH_EXITS, DISPATCH_LADDER, reachedSteps } from '$lib/comms/dispatch-feed';
	import type { DispatchFeedState } from '$lib/comms/dispatch-feed';
	import { istClock } from '$lib/primitives/time';

	interface LogEntry {
		id: number;
		ts: number;
		texts: Array<{ lang: string; text: string }>;
	}
	type Dispatch = DispatchFeedState['dispatches'][number];

	let {
		tab,
		ontab,
		onclose,
		L,
		C,
		log,
		feed,
		scope,
		onscope,
		shown,
		otherEventCount,
		statusWord,
		langName,
	}: {
		tab: 'log' | 'threads';
		ontab: (t: 'log' | 'threads') => void;
		onclose: () => void;
		/** the V3 / deck string lookup */
		L: (key: string, ...args: unknown[]) => string;
		/** the desk's own words (strings.citizen) */
		C: (key: string, ...args: unknown[]) => string;
		log: LogEntry[];
		feed: DispatchFeedState;
		scope: 'event' | 'all';
		onscope: (s: 'event' | 'all') => void;
		shown: Dispatch[];
		otherEventCount: number;
		statusWord: (status: string) => string;
		langName: (code: string) => string;
	} = $props();

	let root = $state<HTMLElement | null>(null);

	onMount(() => {
		void tick().then(() => root?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.focus());
	});
</script>

<aside class="sheet" bind:this={root} aria-label={L('v3c_sheet_aria')} data-testid="comms-sheet" data-tab={tab}>
	<div class="head">
		<div class="tabs" role="tablist" aria-label={L('v3c_sheet_aria')}>
			<button type="button" role="tab" id="cs-tab-log" aria-selected={tab === 'log'} aria-controls="cs-panel" class={['tab', tab === 'log' && 'is-pressed']} onclick={() => ontab('log')} data-testid="comms-tab-log">
				{C('comms_draft_log')}
			</button>
			<button type="button" role="tab" id="cs-tab-threads" aria-selected={tab === 'threads'} aria-controls="cs-panel" class={['tab', tab === 'threads' && 'is-pressed']} onclick={() => ontab('threads')} data-testid="comms-tab-threads">
				{C('comms_dispatch_threads')}
			</button>
		</div>
		<button type="button" class="x" onclick={onclose} aria-label={L('v3c_close')} title={L('v3c_close')}><Glyph name="close" size={20} /></button>
	</div>

	<div class="body" id="cs-panel" role="tabpanel" aria-labelledby={tab === 'log' ? 'cs-tab-log' : 'cs-tab-threads'}>
		{#if tab === 'log'}
			{#if log.length === 0}
				<p class="note">{C('comms_session_only')}</p>
			{:else}
				<ul class="log" data-testid="comms-log">
					{#each log as entry (entry.id)}
						<li>
							<p class="when fig">{istClock(entry.ts)} IST</p>
							{#each entry.texts as tx (tx.lang)}
								<div class="item">
									<span class="lg" lang={tx.lang}>{langName(tx.lang)}</span>
									<p class="tx" lang={tx.lang}>{tx.text}</p>
								</div>
							{/each}
							<span class="log-langs fig">{entry.texts.map((tx) => tx.lang).join(' · ')}</span>
						</li>
					{/each}
				</ul>
				<p class="note">{C('comms_session_only')}</p>
			{/if}
		{:else}
			<div class="scope" role="group" aria-label={C('comms_dispatch_threads')}>
				<button type="button" class={[scope === 'event' && 'is-pressed']} aria-pressed={scope === 'event'} onclick={() => onscope('event')} data-scope="event">
					{C('comms_scope_event')}
				</button>
				<button type="button" class={[scope === 'all' && 'is-pressed']} aria-pressed={scope === 'all'} onclick={() => onscope('all')} data-scope="all">
					{C('comms_scope_all')} <span class="fig">{feed.dispatches.length}</span>
				</button>
			</div>
			{#if feed.source !== 'live'}
				<p class="feed-note" data-testid="comms-dispatch-fallback">
					<V3Tag tone="dashed" size="sm">{feed.source === 'not-deployed' ? C('comms_not_deployed') : C('comms_dispatch_demo')}</V3Tag>
					{#if feed.note}<span class="note-text">{feed.note}</span>{/if}
				</p>
			{/if}
			{#if shown.length === 0}
				<div class="empty">
					<img src="/illustrations/empty/no-reports.svg" alt="" width="96" height="96" />
					<p>{C('comms_dispatch_none')}</p>
					{#if scope === 'event' && otherEventCount > 0}
						<button type="button" class="other-events" onclick={() => onscope('all')}>{C('comms_other_events', otherEventCount)} →</button>
					{/if}
				</div>
			{:else}
				<ul class="threads">
					{#each shown as d (d.dispatch_id)}
						{@const ag = agencyByCode(d.agency)}
						{@const reached = reachedSteps(d)}
						<li class="thread" data-thread-status={d.status}>
							<header class="th-head">
								<span class="th-agency">{ag.label} <span class="th-native">{ag.label_native}</span></span>
								<span class="th-unit fig">{d.unit_id}</span>
							</header>
							<ol class="th-steps">
								{#each DISPATCH_LADDER as st (st)}
									<li class={['th-step', reached.has(st) && 'reached', d.status === st && 'current']} data-step={st}>{statusWord(st)}</li>
								{/each}
								{#if (DISPATCH_EXITS as readonly string[]).includes(d.status)}
									<li class={['th-step', 'th-exit', `exit-${d.status}`]} data-step={d.status}>{statusWord(d.status)}</li>
								{/if}
							</ol>
							{#if d.audit && d.audit.length}
								<ul class="th-audit">
									{#each d.audit.slice(0, 4) as step, i (d.dispatch_id + ':' + i)}
										<li>
											<span class="fig th-ts">{istClock(step.at)} IST</span>
											<span class="th-actor">{step.actor}</span>
											<span class="th-trans fig">{step.from_status ?? '—'} → {step.to_status}</span>
										</li>
									{/each}
								</ul>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		{/if}
	</div>
</aside>

<style>
	.sheet {
		position: absolute;
		top: 16px;
		right: 16px;
		bottom: 16px;
		z-index: 20;
		display: flex;
		flex-direction: column;
		width: min(440px, 100%);
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s2);
		box-shadow: var(--v3-elev-2);
		overflow: hidden;
		animation: in var(--v3-dur-2) var(--v3-ease);
	}

	@keyframes in {
		from {
			opacity: 0;
			transform: translateX(16px);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.sheet {
			animation: none;
		}
	}

	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		padding: 14px 14px 0 18px;
		border-bottom: 1px solid var(--v3-line-1);
	}

	.tabs {
		display: flex;
		gap: 4px;
	}

	.tab {
		min-height: var(--v3-ctl-lg);
		padding: 0 12px;
		border: 0;
		border-bottom: 2px solid transparent;
		background: transparent;
		color: var(--v3-t2);
		font: inherit;
		font-size: var(--v3-text-body);
		font-weight: 620;
		cursor: pointer;
	}

	.tab:hover {
		color: var(--v3-t1);
	}

	/* the selected tab is underlined (no fill) */
	.tab.is-pressed {
		border-bottom-color: var(--v3-t1);
		background: transparent !important;
		box-shadow: none !important;
		color: var(--v3-t1) !important;
	}

	.tab:focus-visible,
	.x:focus-visible,
	.scope button:focus-visible,
	.other-events:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.x {
		display: grid;
		place-items: center;
		width: var(--v3-ctl-lg);
		height: var(--v3-ctl-lg);
		margin-bottom: 4px;
		border: 0;
		border-radius: var(--v3-radius-m);
		background: transparent;
		color: var(--v3-t2);
		cursor: pointer;
	}

	.x:hover {
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.body {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		padding: 16px 18px 20px;
		scrollbar-width: thin;
	}

	.fig {
		font-variant-numeric: tabular-nums;
	}

	.note {
		margin: 12px 0 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	/* the draft log scrolls INSIDE the sheet, never pushing the threads or the desk */
	.log {
		display: flex;
		flex-direction: column;
		gap: 14px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.log > li {
		padding: 12px 14px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
	}

	.when {
		margin: 0 0 8px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 600;
	}

	.item {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin-top: 8px;
	}

	.lg {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.tx {
		margin: 0;
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
		overflow-wrap: anywhere;
	}

	.log-langs {
		display: block;
		margin-top: 8px;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}

	.scope {
		display: inline-flex;
		gap: 2px;
		padding: 3px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
		box-shadow: inset 0 0 0 1px var(--v3-line-1);
	}

	.scope button {
		min-height: var(--v3-ctl);
		padding: 0 14px;
		border: 0;
		border-radius: var(--v3-radius-s);
		background: transparent;
		color: var(--v3-t2);
		font: inherit;
		font-size: var(--v3-text-meta);
		font-weight: 600;
		cursor: pointer;
	}

	.scope button.is-pressed {
		background: var(--v3-s4) !important;
		box-shadow: none !important;
		color: var(--v3-t1) !important;
	}

	.feed-note {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 8px;
		margin: 12px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		padding: 28px 8px;
		color: var(--v3-t2);
		text-align: center;
	}

	.empty p {
		margin: 0;
	}

	.other-events {
		min-height: var(--v3-ctl);
		padding: 0 12px;
		border: 0;
		border-radius: var(--v3-radius-m);
		background: transparent;
		color: var(--v3-brand-text);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	.threads {
		display: flex;
		flex-direction: column;
		gap: 12px;
		margin: 14px 0 0;
		padding: 0;
		list-style: none;
	}

	.thread {
		padding: 12px 14px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
	}

	.th-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 8px;
	}

	.th-agency {
		font-weight: 640;
	}

	.th-native,
	.th-unit {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 500;
	}

	/* the ladder: reached steps are filled, the current one is outlined — words, never colour alone */
	.th-steps {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin: 10px 0 0;
		padding: 0;
		list-style: none;
	}

	.th-step {
		padding: 3px 10px;
		border: 1px solid var(--v3-line-2);
		border-radius: 12px;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.th-step.reached {
		border-color: transparent;
		background: var(--v3-ok-veil);
		color: var(--v3-ok-text);
	}

	.th-step.current {
		border-color: var(--v3-ok-text);
	}

	.th-exit {
		border-style: dashed;
		color: var(--v3-t2);
	}

	.th-audit {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 10px 0 0;
		padding: 0;
		list-style: none;
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.th-audit li {
		display: flex;
		flex-wrap: wrap;
		gap: 4px 10px;
	}
</style>
