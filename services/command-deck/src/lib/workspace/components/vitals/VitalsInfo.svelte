<script lang="ts">
	/**
	 * The City vitals Info tab (SPEC §6.2, §12.2): the full vitals, every
	 * `vitals-*` id the smokes read, in the order an operator scans them —
	 * posture, events, decisions waiting, units and ANPR, the ethics rails
	 * (kept above the fold at 1080 p), signals, AI tiers, feeds.
	 *
	 * Docked sections (32 px headers), 24 px rows, sentence case, figures in
	 * tabular Inter, identifiers through the formatter. Colour by role only:
	 * a band in its band chip, orange only while a decision waits, green only
	 * for healthy; a rung that cannot answer is neutral text that says why.
	 * A figure with an object behind it selects (and flies to) it; a decision
	 * links to its home on /ops (no decision is taken here).
	 */
	import { ACTION_ICON } from '$lib/design/icons';
	import BandChip from '$lib/primitives/BandChip.svelte';
	import { Icon, ProvenanceTag, Section, Tag, Tooltip, fmtDuration, fmtTime } from '$lib/ui';
	import { kindLabel, t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.views';
	import { human } from '../../vocabulary';
	import type { CountLink, VitalsView } from './types';

	let { view, lang, onpick }: { view: VitalsView; lang: string; onpick?: (urn: string | null) => void } = $props();
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const dur = (sec: number | null | undefined) => fmtDuration(sec, lang);

	const p = $derived(view.posture);
	const d = $derived(view.decisions);
	const ret = $derived(view.ethics.retention);
	const brain = $derived(view.brain);
	const ingest = $derived(view.feeds.ingest);
	const runs = $derived(view.feeds.runs);
	const living = $derived(view.feeds.living);

	/** HH:MM IST today, "22 Oct 21:40" on an older day. */
	function istMinute(ms: number): string {
		return view.now - ms < 20 * 3600_000 ? fmtTime(ms) : `${new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short' }).format(ms)} ${fmtTime(ms)}`;
	}

	/** A rung that has not answered, in words. */
	function rungText(r: { state: string; note: string | null }): string {
		if (r.state === 'idle') return L('vw_i_waiting');
		if (r.state === 'not-deployed') return L('vw_i_not_deployed');
		return r.note ?? L('vw_i_unreachable');
	}

	const pick = (urn: string | null | undefined) => onpick?.(urn ?? null);
	/** A latency as the navbar's Data button says it: "2.3 s", or "640 ms" under a second (never split from its unit). */
	const p95 = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)}\u00a0s` : `${Math.round(ms)}\u00a0ms`);
	const onOff = (v: string | null | undefined, on: string) => L(v === on ? 'vw_i_on' : v ? 'vw_i_off' : 'vw_i_unknown');
</script>

{#snippet decision(testid: string, label: string, hint: string, c: CountLink, href: string | null, always: boolean)}
	{#if always || c.n > 0}
		<li class="drow" data-testid={testid} data-count={c.n}>
			<Tooltip content={hint} placement="right">
				<button type="button" class="pick" disabled={!c.urn} onclick={() => pick(c.urn)}>
					<span class="k">{label}</span>
					<span class={['v', c.n === 0 && 'zero', c.n > 0 && href && 'warn']}>{c.n}</span>
				</button>
			</Tooltip>
			{#if c.n > 0 && href}<a class="home" href={href}>{L('vw_i_decide')}</a>{/if}
		</li>
	{/if}
{/snippet}

<div class="info" data-testid="city-vitals" data-variant="info">
	<header class="ihead">
		<span class="title">{L('vw_i_title')}</span>
		<Tooltip content={view.registry.note ?? L('vw_i_registry_hint')}>
			<span class={['reg', view.registry.status !== 'ok' && 'off']} data-status={view.registry.status}>
				{L('vw_i_objects', view.registry.size)}{#if view.registry.ageSec != null}{` · ${dur(view.registry.ageSec)}`}{/if}
			</span>
		</Tooltip>
	</header>
	{#if view.replay}
		<p class="replay" data-testid="vitals-replay-note"><Icon name={ACTION_ICON.return_to_live} size={12} />{L('vw_v_replay_note')}</p>
	{/if}

	<!-- POSTURE -->
	<Section title={L('vw_i_posture')} compact data-testid="vitals-posture">
		<div class="body">
			{#if p}
				<button
					type="button"
					class="posture"
					disabled={!p.urn}
					onclick={() => pick(p.urn)}
					data-source={p.source}
					data-basis={p.basis}
				>
					{#if p.band}
						<BandChip band={p.band} {lang} />
					{:else}
						<span class="unknown" data-testid="vitals-band-unknown">{L('vw_i_band_unknown')}</span>
					{/if}
					<span class="age" data-age-sec={p.ageSec ?? ''}>
						{#if p.engineStale}
							{p.staleSince != null ? L('vw_i_stale_since', `${istMinute(p.staleSince)} IST`) : L('vw_i_stale_plain')}
						{:else if p.basis === 'none'}
							{L('vw_i_posture_city')}
						{:else}
							{L(p.basis === 'transition' ? 'vw_i_age_transition' : 'vw_i_age_reading', dur(p.ageSec))}
						{/if}
					</span>
				</button>
				<div class="tags">
					{#if p.stale}<Tag data-testid="vitals-posture-stale" tooltip={L('vw_i_stale_hint')}>{L('vw_i_stale')}</Tag>{/if}
					{#if p.emulated}<ProvenanceTag source="emulated" data-testid="vitals-posture-emulated" />{/if}
					{#if p.simulated}<ProvenanceTag source="simulated" class="sim" data-testid="vitals-posture-simulated" />{/if}
				</div>
				{#if p.heldSince != null && p.heldSec != null}
					<p class="line" data-testid="vitals-posture-held" data-held-sec={p.heldSec}>{L('vw_i_held', dur(p.heldSec), `${istMinute(p.heldSince)} IST`)}</p>
				{/if}
				<p class="line muted">
					{#if p.source === 'events'}{p.label}{p.events > 1 ? ` · +${p.events - 1}` : ''}{:else}{L('vw_i_posture_writer')}{/if}
				</p>
			{:else}
				<p class="line muted">{L('vw_i_posture_none')}</p>
			{/if}
		</div>
	</Section>

	<!-- EVENTS BY KIND -->
	<Section title={L('vw_i_events')} sub={view.events.total} compact data-vitals-section="events">
		<ul class="rows">
			{#each view.events.kinds as k (k.kind)}
				<li>
					<button type="button" class="pick" onclick={() => pick(k.urn)} data-kind={k.kind}>
						<span class="k">{kindLabel(lang, k.kind)}</span>
						{#if k.emulated}<ProvenanceTag source="emulated" compact />{/if}
						<span class="v">{k.total}{#if k.active}<span class="of">{` · ${L('vw_i_active', k.active)}`}</span>{/if}</span>
					</button>
				</li>
			{:else}
				<li class="muted line">{L('vw_i_events_none')}</li>
			{/each}
		</ul>
	</Section>

	<!-- DECISIONS WAITING -->
	<Section title={L('vw_i_decisions')} compact data-testid="vitals-decisions" data-hot={d.units > 0} data-units={d.units}>
		{#snippet right()}
			<Tooltip content={d.fromUnits ? L('vw_v_decisions_hint') : L('vw_v_decisions_hint_registry')}>
				{#if d.units > 0}<Tag round intent="warning" data-testid="vitals-decision-units">{d.units}</Tag>{:else}<span class="zero-n" data-testid="vitals-decision-units">0</span>{/if}
			</Tooltip>
		{/snippet}
		<ul class="rows">
			{#if d.escortProposals}
				<li class="drow" data-testid="vitals-escort-proposals">
					<Tooltip content={L('vw_i_escorts_hint')} placement="right">
						<a class="pick" href="/analyst">
							<span class="k">{L('vw_i_escorts')}</span>
							<span class="v warn">{d.escortProposals}</span>
						</a>
					</Tooltip>
					<a class="home" href="/ops">{L('vw_i_decide')}</a>
				</li>
			{/if}
			{@render decision('vitals-echallans', L('vw_i_echallans'), L('vw_i_echallans_hint'), d.echallans, d.echallans.id ? `/ops#rec=${d.echallans.id}` : null, true)}
			{@render decision('vitals-stolen-sightings', L('vw_i_stolen'), L('vw_i_stolen_hint'), d.stolen, d.stolen.id ? `/ops#rec=${d.stolen.id}` : null, false)}
			{@render decision('vitals-withheld', L('vw_i_withheld'), L('vw_i_withheld_hint'), d.withheld, null, false)}
			{@render decision('vitals-dispatch-requests', L('vw_i_dispatch'), L('vw_i_dispatch_hint'), d.requested, d.requested.id ? `/ops#dsp=${d.requested.id}` : null, true)}
			{@render decision('vitals-ambulance', L('vw_i_ambulance'), L('vw_i_ambulance_hint'), d.ambulance, null, true)}
		</ul>
		<!-- F-14: the header counts DECISIONS (the Inbox's units), the rows the RECORDS behind them — said, so 4 over rows summing to 9 is not a contradiction -->
		<p class="line muted records" data-testid="vitals-decisions-records">{L('vw_i_decisions_records', d.units)}</p>
	</Section>

	<!-- UNITS + ANPR -->
	<Section title={L('vw_i_units_anpr')} compact data-vitals-section="units-anpr">
		<ul class="rows">
			<li>
				<button type="button" class="pick" disabled={!view.units.urn} onclick={() => pick(view.units.urn)} data-vital="units">
					<span class="k">{L('vw_i_units')}</span>
					{#if view.units.out}<ProvenanceTag source="emulated" compact />{/if}
					<span class={['v', view.units.out === 0 && 'zero']}>{view.units.out}</span>
				</button>
				<p class="sub">{L('vw_i_units_sub', view.units.enRoute, view.units.onScene)}</p>
			</li>
			<li>
				<button type="button" class="pick" disabled={!view.anpr.urn} onclick={() => pick(view.anpr.urn)} data-vital="anpr">
					<span class="k">{L('vw_i_anpr')}</span>
					<span class={['v', view.anpr.hits === 0 && 'zero']}>{view.anpr.hits}</span>
				</button>
				<p class="sub">{L('vw_i_anpr_sub', view.anpr.reads, view.anpr.reporting, view.anpr.cameras)}</p>
			</li>
		</ul>
	</Section>

	<!-- ETHICS RAILS -->
	<Section title={L('vw_i_ethics')} compact data-testid="vitals-ethics">
		<div class="body">
			<p class="line rail"><Icon name={ACTION_ICON.policies} size={12} />{L('vw_i_ethics_line')}</p>
			<dl class="kv">
				<dt>{L('vw_i_reaper')}</dt>
				<dd>
					{#if ret.value}
						<span class={['dot', ret.value.healthy === true && 'ok']} aria-hidden="true"></span>{ret.value.healthy === false ? L('vw_i_failing') : L('vw_i_healthy')}
					{:else}
						<span class="muted">{rungText(ret)}</span>
					{/if}
				</dd>
				{#if ret.value}
					<dt>{L('vw_i_retention_k')}</dt>
					<dd>{L('vw_i_retention', ret.value.defaultRetentionDays ?? '—', ret.value.earmarkCapDays ?? '—')}</dd>
				{/if}
				{#if ret.value?.lastReap}
					{@const reap = ret.value.lastReap}
					<dt>{L('vw_i_last_reap')}</dt>
					<dd data-testid="vitals-last-reap">
						{#if reap.ran}{L('vw_i_reap_removed', reap.removed ?? 0)}{:else if reap.failed}{L('vw_i_failing')}{reap.reason ? `: ${reap.reason}` : ''}{:else}{L('vw_i_reap_skipped')}{/if}
						{#if ret.value.lastSuccessAt}<span class="muted">{` · ${L('vw_i_ago', dur((view.now - ret.value.lastSuccessAt) / 1000))}`}</span>{/if}
					</dd>
				{/if}
				{#if view.ethics.lawful.length}
					<dt>{L('vw_i_lawful')}</dt>
					<dd>{view.ethics.lawful.map(([basis, n]) => `${human(basis)}: ${n}`).join(', ')}</dd>
				{/if}
				<dt>{L('vw_i_marks')}</dt>
				<dd class:on={!!view.ethics.officer}>
					<Icon name={view.ethics.officer ? 'unlock' : ACTION_ICON.masked} size={12} />
					{view.ethics.officer ? L('vw_i_marks_shown', view.ethics.officer) : L('vw_i_marks_masked')}
				</dd>
			</dl>
		</div>
	</Section>

	<!-- SIGNALS -->
	<Section title={L('vw_i_signals')} compact data-vitals-section="signals">
		<dl class="kv body">
			<dt>{L('vw_i_writer')}</dt>
			<dd>
				{#if view.signals.plans}
					<Tag tooltip={L('vw_i_writer_hint')}>{view.signals.plans.writerEnabled ? L('vw_i_writer_on') : L('vw_i_writer_off')}</Tag>
				{:else}
					<span class="muted">{view.signals.note ?? L('vw_i_signals_pending')}</span>
				{/if}
			</dd>
			{#if view.signals.plans}
				<dt>{L('vw_i_twin_k')}</dt>
				<dd>{L('vw_i_twin', view.signals.plans.gate.twinInFlight ?? 0)}</dd>
			{/if}
			{#if view.signals.plans?.lastPlan}
				{@const lp = view.signals.plans.lastPlan}
				<dt>{L('vw_i_last_plan')}</dt>
				<dd>{lp.applied ? L('vw_i_plan_applied', lp.band ?? '') : L('vw_i_plan_held', lp.reason ?? L('vw_i_fail_closed'))}</dd>
			{/if}
			<dt>{L('vw_i_programs')}</dt>
			<dd>{L('vw_i_programs_n', view.signals.programs, view.signals.amber, view.signals.red)}</dd>
		</dl>
	</Section>

	<!-- AI TIERS -->
	<Section title={L('vw_i_ai')} compact data-testid="vitals-ai">
		<dl class="kv body">
			{#if brain.value}
				<dt>{L('vw_i_decider')}</dt>
				<dd>
					<!-- the dot stays with its word and "p95 2.3 s" stays whole: a narrow dock breaks at the " · " -->
					<span class="nw"><span class={['dot', brain.value.decider === 'connected' && !brain.value.deciderDegraded && 'ok']} aria-hidden="true"></span>{L(`vw_i_${brain.value.decider}`)}</span>{#if brain.value.p95Ms != null}<span class="muted p95">{` · p95\u00a0${p95(brain.value.p95Ms)}`}</span>{/if}
				</dd>
				<dt>{L('vw_i_tactical')}</dt>
				<dd>
					<span class={['dot', brain.value.gemma === 'connected' && 'ok']} aria-hidden="true"></span>
					{L(`vw_i_${brain.value.gemma}`)}
				</dd>
				<dt>{L('vw_i_checks')}</dt>
				<dd>
					<Tooltip content={`novelty_latch: ${brain.value.noveltyLatch ?? '—'} · tier0_cache: ${brain.value.tier0Cache ?? '—'}`}>
						<span
							>{brain.value.deciderDegraded ? L('vw_i_degraded', brain.value.deciderDegradedReason ?? '—') : L('vw_i_novelty', onOff(brain.value.noveltyLatch, 'armed'))}<span class="muted"
								>{`, ${L('vw_i_cache', onOff(brain.value.tier0Cache, 'enabled'))}`}</span
							></span
						>
					</Tooltip>
				</dd>
			{:else}
				<dt>{L('vw_i_brain')}</dt>
				<dd class="muted">{rungText(brain)}</dd>
			{/if}
		</dl>
	</Section>

	<!-- FEEDS -->
	<Section title={L('vw_i_feeds')} compact data-testid="vitals-feeds" data-simulated={view.feeds.trafficSimulated}>
		<dl class="kv body">
			<dt>{L('vw_v_traffic_feed')}</dt>
			<dd>
				{#if view.feeds.trafficSimulated}<ProvenanceTag source="simulated" class="sim" />{:else}{L('vw_v_live')}{/if}
			</dd>
			<dt>{L('vw_i_ingest')}</dt>
			<dd>
				{#if ingest.value}
					{L('vw_i_per_min', ingest.value.msgsPerMin ?? 0)}<span class="muted">{` · ${L('vw_i_ago', dur(ingest.value.lastMsgAgeSec))}`}</span>
					{#if !ingest.value.connected}<span class="muted">{` · ${L('vw_i_bus_down')}`}</span>{/if}
				{:else}
					<span class="muted">{rungText(ingest)}</span>
				{/if}
			</dd>
			<dt>{L('vw_i_registry')}</dt>
			<dd>
				{L('vw_i_objects', view.registry.size)}<span class="muted"
					>{view.registry.ageSec != null ? ` · ${dur(view.registry.ageSec)}` : ''}{view.registry.tookMs != null ? ` · ${Math.round(view.registry.tookMs)} ms` : ''}</span
				>
			</dd>
			<dt>{L('vw_i_roads')}</dt>
			<dd data-testid="vitals-roads" data-traced={view.feeds.roads.traced} data-schematic={view.feeds.roads.schematic}>
				{#if view.feeds.roads.known}
					{L('vw_i_osm_traced', view.feeds.roads.traced)}{#if view.feeds.roads.schematic}<span class="muted">{` · ${L('vw_i_schematic', view.feeds.roads.schematic)}`}</span>{/if}
				{:else}
					<span class="muted">{L('vw_i_waiting')}</span>
				{/if}
			</dd>
			<dt>{L('vw_i_newest_read')}</dt>
			<dd>{view.feeds.sightingAgeSec != null ? L('vw_i_ago', dur(view.feeds.sightingAgeSec)) : '—'}</dd>
			<dt>{L('vw_i_emulator')}</dt>
			<dd>
				{#if runs.value?.[0]}
					{@const run = runs.value[0]}
					{L('vw_i_run', run.runId)}<span class="muted">{` · ${[run.useCaseId, run.status].filter(Boolean).join(', ') || '—'}`}</span>
				{:else}
					<span class="muted">{runs.state === 'ok' ? L('vw_i_no_runs') : rungText(runs)}</span>
				{/if}
			</dd>
			<dt>{L('vw_i_living')}</dt>
			<dd>
				{#if living.value}
					{living.value.status ?? L(living.value.enabled ? 'vw_i_on' : 'vw_i_off')}<span class="muted">{` · ${L('vw_i_slots', living.value.activeSlots)}`}</span>
				{:else}
					<span class="muted">{rungText(living)}</span>
				{/if}
			</dd>
		</dl>
	</Section>
</div>

<style>
	.info {
		display: flex;
		flex-direction: column;
		min-width: 0;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.ihead {
		display: flex;
		align-items: center;
		gap: 8px;
		height: 32px;
		padding: 0 12px;
		border-bottom: 1px solid var(--v-line-2);
	}

	.title {
		flex: 1 1 auto;
		font-size: var(--v-text-base);
		font-weight: 600;
	}

	.reg {
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.reg.off {
		color: var(--v-ink-1);
		font-weight: 600;
	}

	.replay {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 0;
		padding: 6px 12px;
		border-bottom: 1px solid var(--v-line-1);
		color: var(--v-ink-2);
	}

	.body {
		padding: 0 12px 8px;
	}

	.posture {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		min-height: 24px;
		margin: 0;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.posture:disabled {
		cursor: default;
	}

	.unknown {
		display: inline-flex;
		align-items: center;
		height: 20px;
		padding: 0 6px;
		border-radius: var(--v-radius-chip);
		box-shadow: inset 0 0 0 1px var(--v-line-strong);
		color: var(--v-ink-1);
		font-weight: 600;
	}

	.age {
		min-width: 0;
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-top: 4px;
	}

	.tags:empty {
		display: none;
	}

	.line {
		margin: 4px 0 0;
		overflow-wrap: anywhere;
		font-variant-numeric: tabular-nums;
	}

	.line.records {
		padding: 0 12px 8px;
		font-size: var(--v-text-xs);
	}

	.line.rail {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 0 0 4px;
		color: var(--v-ink-1);
	}

	.muted {
		color: var(--v-ink-2);
	}

	.rows {
		margin: 0;
		padding: 0 0 6px;
		list-style: none;
	}

	.rows > li.line {
		padding: 0 12px;
	}

	.pick {
		display: flex;
		flex: 1 1 auto;
		align-items: center;
		gap: 8px;
		box-sizing: border-box;
		width: 100%;
		min-width: 0;
		height: 24px;
		margin: 0;
		padding: 0 12px;
		border: 0;
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		text-align: left;
		text-decoration: none;
		cursor: pointer;
	}

	.pick:hover:not(:disabled) {
		background: var(--v-row-hover);
	}

	.pick:disabled {
		cursor: default;
	}

	.pick:focus-visible,
	.home:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.k {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		color: var(--v-ink-2);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.v {
		color: var(--v-ink-1);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.v.zero,
	.zero-n {
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
	}

	.v.warn {
		color: var(--v-warning-text);
		font-weight: 600;
	}

	.of {
		color: var(--v-ink-2);
	}

	.drow {
		display: flex;
		align-items: center;
	}

	.home {
		flex: 0 0 auto;
		padding: 0 12px 0 4px;
		color: var(--v-primary-text);
		text-decoration: none;
		white-space: nowrap;
	}

	.home:hover {
		text-decoration: underline;
	}

	.sub {
		margin: -2px 0 4px;
		padding: 0 12px;
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
	}

	.kv {
		display: grid;
		grid-template-columns: max-content minmax(0, 1fr);
		column-gap: 12px;
		row-gap: 4px;
		margin: 0;
	}

	.kv dt {
		color: var(--v-ink-2);
		white-space: nowrap;
	}

	/* inline flow: a long value wraps word by word, never as a detached chunk */
	.kv dd {
		display: block;
		min-width: 0;
		margin: 0;
		overflow-wrap: anywhere;
		font-variant-numeric: tabular-nums;
	}

	/* a status dot never sits alone on a line: it keeps its word */
	.nw {
		white-space: nowrap;
	}

	.kv dd.on {
		color: var(--v-ink-1);
		font-weight: 600;
	}

	.dot {
		display: inline-block;
		width: 8px;
		height: 8px;
		margin-right: 6px;
		border-radius: 50%;
		vertical-align: middle;
		box-shadow: inset 0 0 0 1px var(--v-ink-2);
	}

	.dot.ok {
		background: var(--v-success);
		box-shadow: none;
	}
</style>
