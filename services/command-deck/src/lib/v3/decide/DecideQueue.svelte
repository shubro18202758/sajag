<script lang="ts" module>
	import type { PlateVM } from '../home/view';

	/** One row of the queue: a waiting unit, or one this console just closed (decided, expired, gone). */
	export interface QueueItem {
		key: string;
		href: string;
		kindLine: string;
		title: string;
		plate: PlateVM | null;
		art: string;
		/** The timer line ("0:47 left", "waiting 14 min") or the outcome ("Approved"). */
		when: string;
		urgent: boolean;
		state: 'waiting' | 'done' | 'expired' | 'refused';
		/** The `queue-card` data-* hooks (UNIT_KINDS dataHooks) — only while the unit still waits. */
		hooks: Record<string, string> | null;
		emulated: boolean;
	}

	/** One AI proposal row (forecast, waterlogging, signal timing — $lib/ai): its own section under the units. */
	export interface AiQueueItem {
		key: string;
		kindLine: string;
		title: string;
		art: string;
		when: string;
		state: 'waiting' | 'done' | 'rejected';
		provs: string[];
		exercise: boolean;
	}
</script>

<script lang="ts">
	/**
	 * DecideQueue (V3-SPEC §5.3, §6.2) — the decisions waiting, soonest deadline first (decisionUnits()
	 * order): a 64 px illustration, the kind, the title (its mark in a masked chip), and the timer. The row
	 * the sheet shows is selected (`.is-selected`, `aria-current`). A row this console just decided turns
	 * green with its outcome; one that ran out says the plan was kept.
	 *
	 * Every waiting row is a `queue-card` with the unit's data-* hooks (UNIT_KINDS dataHooks — the v2 DOM
	 * contract, so the v2 smokes target /decide with a URL change only). Rows are links to the unit's deep
	 * link (/decide/<kind>:<id>); a plain click selects in place. Below 1500 px the queue collapses to its art
	 * (the whole row text stays its accessible name and tooltip).
	 *
	 * Under the list: "Decided on this console" (this session's approved · rejected · deferred · expired with
	 * the plan kept) and the link to the full record in Analyst.
	 */
	import { t } from '$lib/i18n/strings';
	import Glyph from '../Glyph.svelte';
	import PlateChip from '../ui/PlateChip.svelte';
	import './packs.decide';
	import '$lib/ai/packs.ai';
	import ProvTag from '$lib/ai/ui/ProvTag.svelte';
	import type { Prov } from '$lib/ai/labels';

	let {
		items,
		selected,
		waiting,
		tally,
		recordHref,
		lang,
		onselect,
		aiItems = [],
		aiWaiting = 0,
		aiNote = null,
		exercise = false,
		onexercise,
	}: {
		items: QueueItem[];
		selected: string | null;
		waiting: number;
		tally: { approved: number; rejected: number; deferred: number; expired: number };
		recordHref: string;
		lang: string;
		onselect: (key: string) => void;
		aiItems?: AiQueueItem[];
		aiWaiting?: number;
		/** A forecast service that does not answer, in words. */
		aiNote?: string | null;
		exercise?: boolean;
		onexercise?: (on: boolean) => void;
	} = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);

	const aria = (it: QueueItem) =>
		[it.kindLine, it.title, it.plate ? (it.plate.masked ? L('v3_masked') : it.plate.mark) : null, it.when].filter(Boolean).join(', ');
</script>

<aside class="queue" aria-labelledby="v3d-queue-h" data-v3="decide-queue">
	<h2 class="qh" id="v3d-queue-h">
		{L('v3d_waiting')} <span class="count" data-testid="v3-queue-count">{waiting}</span><span class="meta">{L('v3d_soonest_first')}</span>
	</h2>
	{#if items.length}
		<ul class="list">
			{#each items as it (it.key)}
				<li>
					<a
						class={['q', it.state !== 'waiting' && `st-${it.state}`]}
						class:is-selected={selected === it.key}
						href={it.href}
						aria-current={selected === it.key ? 'true' : undefined}
						aria-label={aria(it)}
						title={aria(it)}
						data-testid={it.hooks ? 'queue-card' : 'v3-queue-closed'}
						data-key={it.key}
						data-state={it.state}
						{...Object.fromEntries(Object.entries(it.hooks ?? {}).map(([k, v]) => [`data-${k}`, v]))}
						onclick={(e) => {
							if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
							e.preventDefault();
							onselect(it.key);
						}}
					>
						<span class="mini"><img src={it.art} alt="" width="64" height="64" /></span>
						<span class="txt" aria-hidden="true">
							<span class="k">{it.kindLine}</span>
							<span class="tt">{it.title}{#if it.plate}{' '}<PlateChip mark={it.plate.mark} masked={it.plate.masked} {lang} />{/if}</span>
							<span class="when" class:urgent={it.urgent}>
								<Glyph name={it.state === 'done' ? 'check' : it.state === 'refused' ? 'alert' : 'clock'} size={15} />{it.when}
							</span>
						</span>
					</a>
				</li>
			{/each}
		</ul>
	{:else}
		<div class="empty">
			<img src="/illustrations/empty/all-clear.svg" alt="" width="120" height="90" />
			<p>{L('v3d_empty')}</p>
		</div>
	{/if}
	<section class="ai" aria-labelledby="v3d-ai-h" data-testid="ai-queue">
		<h2 class="qh ai-h" id="v3d-ai-h"><span class="spark"><Glyph name="spark" size={18} /></span>{L('ai_d_section')} <span class="count" data-testid="ai-queue-count">{aiWaiting}</span></h2>
		<p class="ai-sub">{L('ai_d_sub')}</p>
		{#if aiItems.length}
			<ul class="list">
				{#each aiItems as it (it.key)}
					<li>
						<a
							class={['q', it.state !== 'waiting' && `st-${it.state === 'done' ? 'done' : 'expired'}`]}
							class:is-selected={selected === it.key}
							href="/decide"
							aria-current={selected === it.key ? 'true' : undefined}
							aria-label={`${it.kindLine}, ${it.title}, ${it.when}`}
							title={`${it.kindLine}, ${it.title}, ${it.when}`}
							data-testid="ai-queue-card"
							data-key={it.key}
							data-state={it.state}
							onclick={(e) => {
								if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
								e.preventDefault();
								onselect(it.key);
							}}
						>
							<span class="mini"><img src={it.art} alt="" width="64" height="64" /></span>
							<span class="txt" aria-hidden="true">
								<span class="k">{it.kindLine}</span>
								<span class="tt">{it.title}</span>
								<span class="when ai-when"><Glyph name={it.state === 'done' ? 'check' : it.state === 'rejected' ? 'close' : 'clock'} size={15} />{it.when}</span>
								<span class="provs">{#each it.provs as p (p)}<ProvTag prov={p as Prov} {lang} />{/each}</span>
							</span>
						</a>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="ai-none">{aiNote ?? L('ai_d_none')}</p>
		{/if}
		{#if onexercise}
			<button type="button" class={['ex', exercise && 'is-pressed']} aria-pressed={exercise} title={L('ai_d_exercise_tip')} data-testid="ai-exercise" onclick={() => onexercise(!exercise)}>
				<Glyph name="history" size={16} />{exercise ? L('ai_d_exercise_off') : L('ai_d_exercise')}
			</button>
		{/if}
	</section>

	<div class="history">
		<h3 class="micro">{L('v3d_decided_here')}</h3>
		<p class="row"><span>{L('v3d_tally_approved')}</span><b>{tally.approved}</b></p>
		<p class="row"><span>{L('v3d_tally_rejected')}</span><b>{tally.rejected}</b></p>
		{#if tally.deferred}<p class="row"><span>{L('v3d_tally_deferred')}</span><b>{tally.deferred}</b></p>{/if}
		<p class="row"><span>{L('v3d_tally_expired')}</span><b>{tally.expired}</b></p>
		<a class="link" href={recordHref}>{L('v3d_full_record')}</a>
	</div>
</aside>

<style>
	.queue {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-height: 0;
		padding: 18px 14px;
		border-right: 1px solid var(--v3-line-1);
		overflow: auto;
		scrollbar-width: thin;
		scrollbar-color: var(--v3-s4) transparent;
	}

	.qh {
		display: flex;
		align-items: baseline;
		gap: 10px;
		margin: 2px 6px 8px;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 650;
		color: var(--v3-t1);
	}

	.count {
		color: var(--v3-decide-text);
	}

	.meta {
		font-size: var(--v3-text-meta);
		font-weight: 500;
		color: var(--v3-t2);
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.q {
		display: grid;
		grid-template-columns: 64px minmax(0, 1fr);
		gap: 12px;
		padding: 10px;
		border: 1px solid transparent;
		border-radius: 14px;
		color: var(--v3-t1);
		text-decoration: none;
		transition: background-color var(--v3-dur-1) var(--v3-ease);
	}

	.q:hover {
		background: var(--v3-s2);
	}

	.q.is-selected {
		border-color: var(--v3-line-3);
		background: var(--v3-s2);
	}

	.q:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.mini {
		display: block;
		width: 64px;
		height: 64px;
		overflow: hidden;
		border-radius: 12px;
		background: var(--v3-map-bg);
	}

	.mini img {
		display: block;
		width: 100%;
		height: 100%;
	}

	.txt {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.k {
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 650;
		color: var(--v3-t3);
	}

	.tt {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		font-size: 15px;
		line-height: 20px;
		font-weight: 640;
	}

	.when {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-top: 3px;
		font-size: var(--v3-text-meta);
		font-weight: 650;
		color: var(--v3-decide-text);
		font-variant-numeric: tabular-nums;
	}

	.when.urgent {
		color: var(--v3-alert-text);
	}

	.st-done .when {
		color: var(--v3-ok-text);
	}

	.st-done .tt,
	.st-expired .tt {
		color: var(--v3-t2);
	}

	.st-expired .when,
	.st-refused .when {
		color: var(--v3-t2);
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		padding: 24px 10px;
		text-align: center;
		font-size: 14px;
		color: var(--v3-t2);
	}

	.empty p {
		margin: 0;
	}

	.history {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-top: 10px;
		padding: 14px 10px;
		border-top: 1px solid var(--v3-line-1);
		font-size: 14px;
		color: var(--v3-t2);
	}

	.micro {
		margin: 0;
		font-size: var(--v3-text-micro);
		font-weight: 600;
		color: var(--v3-t3);
	}

	.row {
		display: flex;
		justify-content: space-between;
		margin: 0;
	}

	.row b {
		font-weight: 600;
		color: var(--v3-t1);
		font-variant-numeric: tabular-nums;
	}

	.link {
		color: var(--v3-brand-text);
		font-weight: 600;
		text-decoration: none;
	}

	.link:hover {
		text-decoration: underline;
	}

	.ai {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-top: 12px;
		padding-top: 14px;
		border-top: 1px solid var(--v3-line-1);
	}

	.ai-h {
		align-items: center;
	}

	.spark {
		display: inline-flex;
		color: var(--v3-ai-text);
	}

	.ai-h .count {
		color: var(--v3-ai-text);
	}

	.ai-sub,
	.ai-none {
		margin: -6px 6px 4px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.ai-when {
		color: var(--v3-t1);
	}

	.provs {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-top: 4px;
	}

	.ex {
		display: inline-flex;
		align-items: center;
		align-self: flex-start;
		gap: 8px;
		height: 32px;
		margin: 2px 6px 0;
		padding: 0 14px;
		border: 1px dashed var(--v3-line-3);
		border-radius: 16px;
		background: none;
		color: var(--v3-t2);
		font: inherit;
		font-size: var(--v3-text-meta);
		font-weight: 600;
		cursor: pointer;
	}

	.ex.is-pressed {
		border-style: solid;
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.ex:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	/* the 1366 class: the labelled queue stays (a cryptic strip of art reads as nothing), a little tighter */
	@media (max-width: 1500px) {
		.q {
			grid-template-columns: 52px minmax(0, 1fr);
			gap: 10px;
			padding: 8px;
		}

		.mini {
			width: 52px;
			height: 52px;
		}

		.tt {
			font-size: var(--v3-text-body);
		}
	}

	/* below 1280 px the queue is its art only (92 px) */
	@media (max-width: 1279px) {
		.queue {
			align-items: center;
			padding: 14px 8px;
		}

		.qh,
		.txt,
		.history,
		.ai-sub,
		.ai-none,
		.ex,
		.empty p {
			display: none;
		}

		.q {
			position: relative;
			grid-template-columns: 64px;
			padding: 4px;
		}

		.mini {
			width: 64px;
			height: 64px;
		}

		.empty img {
			width: 64px;
			height: 48px;
		}

		.st-done::after {
			content: '';
			position: absolute;
			right: 2px;
			bottom: 2px;
			width: 12px;
			height: 12px;
			border: 2px solid var(--v3-bg);
			border-radius: 50%;
			background: var(--v3-ok);
		}
	}

	/* a phone: the queue is a strip of art along the top (scrolls sideways); the sheet takes the page below it */
	@media (max-width: 720px) {
		.queue {
			flex-direction: row;
			align-items: center;
			gap: 6px;
			padding: 8px 12px;
			border-right: 0;
			border-bottom: 1px solid var(--v3-line-1);
			overflow-x: auto;
			overflow-y: hidden;
		}

		.list {
			flex-direction: row;
			gap: 6px;
		}

		.q {
			grid-template-columns: 52px;
			padding: 3px;
		}

		.mini {
			width: 52px;
			height: 52px;
		}

		.ai {
			flex-direction: row;
			align-items: center;
			margin: 0 0 0 6px;
			padding: 0 0 0 10px;
			border-top: 0;
			border-left: 1px solid var(--v3-line-1);
		}

		.empty {
			padding: 0;
		}
	}
</style>
