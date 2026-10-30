<script lang="ts">
	/**
	 * LiveStrip (SPEC §5.3, §7.3) — the 36 px live-operations strip under the
	 * navbar (`data-testid="live-strip"`), rendered from commandBar.live, which
	 * pages fill (UI-S5A's liveStripFeed(), plan X21). The shell imports no
	 * store (R4): everything here is the feed's, already masked by the page.
	 *
	 * Left to right: the IST clock (hh:mm:ss, 600, tabular); the movement
	 * (opens the Movement tab); each open pursuit (selects the vehicle); the
	 * soonest-expiring decision with its countdown on an orange veil and a
	 * Review button (`data-testid="interrupt"`); then the interrupts (band RED
	 * or BLACK during a movement, feed loss). Interrupts never open a modal and
	 * make no sound. The decision segment never shrinks: the movement and
	 * pursuit segments ellipsise first.
	 */
	import { t } from '$lib/i18n/strings';
	import Button from '$lib/ui/Button.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import Plate from '$lib/ui/format/Plate.svelte';
	import { fmtCountdown, fmtDuration, fmtTime } from '$lib/ui/format/format';
	import type { LiveStripFeed } from './command-bar.svelte';
	import { shellClock, useShellClock } from './clock.svelte';
	import { DECISION_ICON, FEED_LOSS_ICON } from './icons';

	let { live, lang }: { live: LiveStripFeed; lang: string } = $props();

	$effect(() => useShellClock());

	const now = $derived(shellClock.now);

	/** "1 min 35 s" (minutes and seconds under 10 min; the compact duration beyond). */
	function inText(sec: number): string {
		const s = Math.max(0, Math.round(sec));
		if (s < 60 || s >= 600) return fmtDuration(s, lang);
		const m = Math.floor(s / 60);
		const r = s % 60;
		return r ? `${m} ${t(lang, 'ui_unit_min')} ${r} ${t(lang, 'ui_unit_s')}` : `${m} ${t(lang, 'ui_unit_min')}`;
	}

	const soonestLeft = $derived(live.soonest ? (live.soonest.deadlineMs - now) / 1000 : null);
</script>

<div class="strip" data-testid="live-strip" role="region" aria-label={t(lang, 'shell_live')}>
	<!-- the heartbeat: a dot that breathes beside the live clock (still under reduced motion) -->
	<span class="beat" aria-hidden="true" data-testid="live-heartbeat"></span>
	<span class="clock" data-live-clock>{fmtTime(now, { seconds: true })}</span><span class="ist">{t(lang, 'live_ist')}</span>

	{#if live.movement}
		{@const mv = live.movement}
		<button type="button" class="seg line mv" data-live-seg="movement" title={t(lang, 'live_open_movement')} onclick={() => mv.onOpen()}>
			<i class="sw route" aria-hidden="true"></i>
			<b class="lbl">{mv.label}</b>
			{#if mv.speedKmh != null}<span class="n">{Math.round(mv.speedKmh)} {t(lang, 'live_kmh')}</span>{/if}
			{#if mv.nextJunction}
				<span class="k">{t(lang, 'live_next')}</span><span class="txt">{mv.nextJunction}</span>
				{#if mv.nextInSec != null}<span class="n">{t(lang, 'live_in', inText(mv.nextInSec))}</span>{/if}
			{/if}
			{#if mv.etaMs != null}<span class="k">{t(lang, 'live_eta')}</span><span class="n">{fmtTime(mv.etaMs)}</span>{/if}
		</button>
	{/if}

	{#each live.pursuits as p, i (`${p.plateMasked}-${i}`)}
		<button type="button" class="seg line pu" data-live-seg="pursuit" title={t(lang, 'live_select_vehicle')} onclick={() => p.onSelect()}>
			<i class="sw alert" aria-hidden="true"></i>
			<b class="lbl">{t(lang, 'live_pursuit')}</b>
			<Plate mark={p.plateMasked} masked />
			{#if p.lastReadAgoSec != null}
				<span class="k">{t(lang, 'live_last_read')}</span><span class="n">{t(lang, 'ui_ago', fmtDuration(p.lastReadAgoSec, lang))}</span>
			{/if}
			{#if p.heading}<span class="k">{t(lang, 'live_heading')}</span><span class="txt">{p.heading}</span>{/if}
		</button>
	{/each}

	{#if live.soonest}
		{@const so = live.soonest}
		<span class="seg decide" data-live-seg="decision" title={t(lang, 'live_review_tip')}>
			<Icon name={DECISION_ICON} size={16} />
			<span class="txt">{so.title}</span>
			<span class="k">{t(lang, 'live_expires')}</span>
			<span class="cd" data-countdown-sec={soonestLeft != null ? Math.max(0, Math.round(soonestLeft)) : undefined}>{fmtCountdown(soonestLeft)}</span>
			<Button small data-testid="interrupt" onclick={() => so.onReview()}>{t(lang, 'live_review')}</Button>
		</span>
	{/if}

	{#each live.interrupts as it, i (`${it.kind}-${i}`)}
		<svelte:element
			this={it.onOpen ? 'button' : 'span'}
			type={it.onOpen ? 'button' : undefined}
			class="seg int"
			data-live-seg="interrupt"
			data-interrupt={it.kind}
			data-band={it.band}
			role={it.onOpen ? undefined : 'status'}
			onclick={it.onOpen ? () => it.onOpen?.() : undefined}
		>
			{#if it.kind === 'band'}
				<i class="sw band b-{it.band ?? 'RED'}" aria-hidden="true"></i>
			{:else}
				<Icon name={FEED_LOSS_ICON} size={16} />
			{/if}
			<span class="txt">{it.text}</span>
		</svelte:element>
	{/each}
	<span class="grow"></span>
</div>

<style>
	.strip {
		display: flex;
		align-items: center;
		box-sizing: border-box;
		height: var(--v-ws-strip);
		min-width: 0;
		padding: 0 8px 0 12px;
		overflow: hidden;
		background: var(--v-surface-2);
		border-bottom: 1px solid var(--v-line-2);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		white-space: nowrap;
	}

	.beat {
		flex: none;
		width: 7px;
		height: 7px;
		margin-right: 8px;
		border-radius: 50%;
		background: var(--v3-ok, var(--v-band-green));
		animation: live-breathe 2.4s ease-in-out infinite;
	}

	@keyframes live-breathe {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.4;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.beat {
			animation: none;
		}
	}

	.clock {
		flex: 0 0 auto;
		margin-right: 4px;
		font-size: var(--v-text-base);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}

	.ist {
		flex: 0 0 auto;
		margin-right: 8px;
		color: var(--v-ink-2);
	}

	.seg {
		display: inline-flex;
		flex: 0 1 auto;
		align-items: center;
		gap: 6px;
		box-sizing: border-box;
		height: 100%;
		min-width: 0;
		margin: 0;
		padding: 0 12px;
		border: 0;
		border-left: 1px solid var(--v-line-1);
		border-radius: 0;
		background: transparent;
		color: inherit;
		font: inherit;
		text-align: left;
		white-space: nowrap;
		overflow: hidden;
	}

	button.seg {
		cursor: pointer;
	}

	/* the movement and a pursuit shrink first, with an ellipsis at the end of the line */
	.seg.line {
		display: inline-block;
		flex: 0 1 auto;
		line-height: calc(var(--v-ws-strip) - 1px);
		text-overflow: ellipsis;
	}

	.seg.line > :global(*) {
		margin-right: 6px;
		vertical-align: middle;
	}

	.seg.line > :global(*:last-child) {
		margin-right: 0;
	}

	.seg.line .sw {
		vertical-align: 2px;
	}

	button.seg:hover {
		background: var(--v-hover);
	}

	button.seg:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.lbl {
		flex: 0 0 auto;
		font-weight: 600;
	}

	.k {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.n {
		flex: 0 0 auto;
		font-variant-numeric: tabular-nums;
	}

	.txt {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.seg :global([data-ui='icon']) {
		color: var(--v-ink-2);
		flex: 0 0 auto;
	}

	.sw {
		display: inline-block;
		flex: 0 0 auto;
		width: 10px;
		height: 3px;
		border-radius: 2px;
	}

	.sw.route {
		background: var(--v-map-route);
	}

	.sw.alert {
		background: var(--v-map-alert);
	}

	.sw.band {
		width: 10px;
		height: 10px;
	}

	.b-RED {
		background: var(--v-band-red);
	}

	.b-BLACK {
		background: var(--v-band-black-fill);
		box-shadow: inset 0 0 0 1px var(--v-band-black-hairline);
	}

	/* the soonest decision: an orange veil, the countdown in the warning ink; it never shrinks */
	.decide {
		flex: 0 0 auto;
		background: var(--v-warning-veil);
	}

	.decide > :global([data-ui='icon']),
	.decide .cd {
		color: var(--v-warning-text);
	}

	.decide .txt {
		max-width: 360px;
	}

	.cd {
		flex: 0 0 auto;
		font-size: var(--v-text-base);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}

	.int {
		flex: 0 0 auto;
	}

	.grow {
		flex: 1 1 auto;
	}
</style>
