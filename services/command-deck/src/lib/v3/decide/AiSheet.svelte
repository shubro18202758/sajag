<script lang="ts">
	/**
	 * AiSheet — one AI proposal (forecast, waterlogging, signal timing) as a decision card in Decide:
	 *
	 *   the evidence     the numbers in the reader's language (V/C now and its band, the risk class and when the
	 *                    water turns deep, the twin's before / after), each with its honest label; the service's
	 *                    own sentence verbatim under "The service's words"
	 *   what changes     ChangeList: the decision record (in the platform's decision log, or on this console while
	 *                    that log is not deployed, or an exercise) and the SEPARATE next step — the console actuates
	 *                    nothing: a diversion is briefed, an advisory published from Comms, a signal timing is
	 *                    recorded as approved (the signal adapter is emulated: no controller changes)
	 *   who decides      OfficerGate (a named officer; attribution, not sign-in)
	 *   approve / reject Approve; Reject… with the reason. If no one decides, the current plan holds.
	 *
	 * Writes through $lib/ai (ai.decide → writer.ts → POST /api/v1/ai-proposals/decision); a refusal is said in
	 * words, never retried by itself.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { t } from '$lib/i18n/strings';
	import { fmtDuration, fmtTime } from '$lib/ui/format/format';
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import ChangeList from './ChangeList.svelte';
	import OfficerGate from './OfficerGate.svelte';
	import './packs.decide';
	import '$lib/ai/packs.ai';
	import { ai } from '$lib/ai/ai.svelte';
	import type { AiCard } from '$lib/ai/model';
	import { provList } from '$lib/ai/labels';
	import ProvTag from '$lib/ai/ui/ProvTag.svelte';
	import TwinCompare from '$lib/ai/ui/TwinCompare.svelte';
	import { cardArt, cardBanner, cardChanges, cardKindKey, cardTitle, cardWhat } from '$lib/ai/view';
	import type { AiDecisionRow } from '$lib/ai/types';

	let { card, decided = null, lang, hasNext = false, onnext }: { card: AiCard; decided?: AiDecisionRow | null; lang: string; hasNext?: boolean; onnext?: () => void } = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const officer = $derived((commandBar.officer ? commandBar.officer.value : ops.dutyOfficer).trim());
	const named = $derived(officer.length >= 2);
	const where = $derived<'platform' | 'console' | 'exercise'>(card.exercise ? 'exercise' : ai.platformLog === false ? 'console' : 'platform');
	const provs = $derived(provList(card.labels));
	const what = $derived(cardWhat(card, lang, L));
	const changes = $derived(cardChanges(card, where, L));
	const SRC = { forecast: 'ai_src_forecast', hydro: 'ai_src_hydro', twin: 'ai_src_twin' } as const;

	const figs = $derived.by((): { value: string; label: string }[] => {
		const out: { value: string; label: string }[] = [];
		if (card.fc) {
			if (card.fc.vcNow != null) out.push({ value: card.fc.vcNow.toFixed(2), label: L('ai_s_fig_vc_now') });
			if (card.fc.band && card.fc.inMin != null) out.push({ value: card.fc.band.p50.toFixed(2), label: L('ai_s_fig_vc_at', card.fc.inMin) });
			if (card.fc.band) out.push({ value: `${card.fc.band.p10.toFixed(2)}–${card.fc.band.p90.toFixed(2)}`, label: L('ai_s_fig_band') });
			if (card.fc.share != null) out.push({ value: `${Math.round(card.fc.share * 100)}%`, label: L('ai_s_fig_share') });
		} else if (card.hy && card.kind !== 'public_advisory_draft') {
			out.push({ value: String(card.hy.risk), label: L('ai_s_fig_risk') });
			if (card.hy.band) out.push({ value: card.hy.band, label: L('ai_s_fig_depth') });
			if (card.hy.deepMin != null) out.push({ value: fmtDuration(card.hy.deepMin * 60, lang), label: L('ai_s_fig_deep') });
			if (card.hy.detourM != null) out.push({ value: `${(card.hy.detourM / 1000).toFixed(1)} km`, label: L('ai_s_fig_detour') });
		} else if (card.tw) {
			out.push({ value: `${card.tw.delayPct > 0 ? '+' : ''}${card.tw.delayPct.toFixed(1)}%`, label: L('ai_s_fig_delay') });
			out.push({ value: `${card.tw.crossPct > 0 ? '+' : ''}${card.tw.crossPct.toFixed(1)}%`, label: L('ai_s_fig_cross') });
			out.push({ value: `${card.tw.networkPct > 0 ? '+' : ''}${card.tw.networkPct.toFixed(1)}%`, label: L('ai_s_fig_network') });
			out.push({ value: fmtDuration(card.tw.durationMin * 60, lang), label: L('ai_s_fig_duration') });
		}
		return out.slice(0, 4);
	});

	let rejecting = $state(false);
	let reason = $state('');
	let busy = $state(false);
	let refusal = $state<{ text: string; detail: string | null } | null>(null);
	let reasonField = $state<HTMLInputElement | null>(null);

	async function decide(decision: 'approve' | 'reject') {
		if (busy) return;
		if (!named) {
			refusal = { text: L('ai_r_officer'), detail: null };
			return;
		}
		if (decision === 'reject' && !rejecting) {
			rejecting = true;
			queueMicrotask(() => reasonField?.focus());
			return;
		}
		if (decision === 'reject' && !reason.trim()) {
			refusal = { text: L('ai_r_reason'), detail: null };
			reasonField?.focus();
			return;
		}
		busy = true;
		refusal = null;
		const res = await ai.decide(card, { decision, officer, note: decision === 'reject' ? reason : undefined });
		busy = false;
		if (!res.ok) {
			refusal = {
				text:
					res.refusal === 'officer-required'
						? L('ai_r_officer')
						: res.refusal === 'reason-required'
							? L('ai_r_reason')
							: res.refusal === 'already-decided'
								? L('ai_r_already', res.row?.officer ?? '—')
								: res.refusal === 'sign-in'
									? L('ai_r_signin')
									: L('ai_r_failed'),
				detail: res.detail,
			};
		}
	}
</script>

<div class="sheet-in" data-testid="ai-sheet" data-source={card.source} data-kind={card.kind} data-id={card.id} data-exercise={card.exercise ? 'true' : 'false'}>
	<div class="scroll">
		<div class="banner"><img src={cardBanner(card)} alt="" width="640" height="360" loading="eager" decoding="async" /></div>
		<header class="sh-top">
			<div class="art"><img src={cardArt(card)} alt="" width="60" height="60" /></div>
			<div class="head">
				<p class="micro">{L(SRC[card.source])} · {L(cardKindKey(card))}</p>
				<h1 class="title" id="v3d-sheet-title">{cardTitle(card, lang, L)}</h1>
				<div class="tags">
					<V3Tag tone="ai" glyph="spark" size="sm">{L('ai_tag')}</V3Tag>
					{#if card.exercise}<V3Tag tone="dashed" glyph="history" size="sm" title={L('ai_d_exercise_tip')}>{L('ai_d_exercise_tag')}</V3Tag>{/if}
					{#each provs as p (p)}<ProvTag prov={p} {lang} />{/each}
				</div>
			</div>
		</header>

		<section class="ev" aria-label={L('ai_s_figs')}>
			{#each what as w, i (i)}<p class="what" data-testid="ai-what">{w}</p>{/each}
			{#if card.generatedAt != null && (card.source === 'forecast' || card.exercise)}<p class="when-line">{card.exercise ? L('ai_s_hs_at', fmtTime(card.generatedAt)) : L('ai_s_run_at', fmtTime(card.generatedAt))}</p>{/if}
			{#if figs.length}
				<div class="figs">
					{#each figs as f (f.label)}<div class="fig"><b>{f.value}</b><span>{f.label}</span></div>{/each}
				</div>
			{/if}
		</section>

		{#if card.tw}
			<TwinCompare before={card.tw.before} after={card.tw.after} horizonMin={45} confidence={card.tw.confidence} demand={card.tw.demand} {lang} />
		{/if}

		{#if card.hy?.textMr || card.hy?.textEn}
			<section class="drafts">
				{#if card.hy?.textMr}<div class="draft" lang="mr"><p class="micro">{L('ai_s_draft_mr')}</p><p>{card.hy.textMr}</p></div>{/if}
				{#if card.hy?.textEn}<div class="draft" lang="en"><p class="micro">{L('ai_s_draft_en')}</p><p>{card.hy.textEn}</p></div>{/if}
			</section>
		{/if}

		<ChangeList rows={changes} unchanged={[L('ai_c_unchanged')]} title={L('ai_c_title')} {lang} />
		<p class="hold"><Glyph name="shield" size={16} />{L('ai_c_hold')}</p>

		<details class="why">
			<summary><Glyph name="chevD" size={16} />{L('ai_s_why')}</summary>
			<div class="in">
				<p>{L(card.source === 'forecast' ? 'ai_s_why_fc' : card.source === 'hydro' ? 'ai_s_why_hy' : 'ai_s_why_tw')}</p>
				{#if card.summary}<p class="micro">{L('ai_s_service')}</p><p class="said" lang="en">“{card.summary}”</p>{/if}
			</div>
		</details>
	</div>

	<div class="act" data-part="decision-footer">
		{#if decided}
			<div class="done" data-testid="ai-outcome" data-decision={decided.decision} data-recorded={decided.recorded}>
				<Glyph name={decided.decision === 'approve' ? 'checkc' : 'close'} size={22} />
				<div>
					<p class="o-v">{L(decided.decision === 'approve' ? 'ai_q_approved' : 'ai_q_rejected')}</p>
					<p class="o-m">{L('ai_o_by', decided.officer, fmtTime(Date.parse(decided.decided_at)))}</p>
					<p class="o-m">{card.exercise ? L('ai_o_exercise') : decided.recorded === 'platform' ? L('ai_o_platform') : L('ai_o_console')}</p>
					{#if decided.decision === 'approve' && card.tw}<p class="o-m">{L('ai_o_signal')}</p>{/if}
				</div>
				{#if hasNext && onnext}<button type="button" class="btn primary" onclick={onnext}>{L('ai_o_next')}<Glyph name="arrowR" size={18} /></button>{/if}
			</div>
		{:else}
			{#if refusal}
				<div class="refusal" role="alert" data-testid="ai-refusal">
					<Glyph name="alert" size={18} />
					<p><b>{refusal.text}</b>{#if refusal.detail}<span class="verbatim">“{refusal.detail}”</span>{/if}</p>
				</div>
			{/if}
			<OfficerGate {lang} />
			{#if rejecting}
				<div class="reason">
					<label for="ai-reason-{card.id}">{L('ai_b_reason')}</label>
					<input bind:this={reasonField} id="ai-reason-{card.id}" class="field" data-testid="ai-reason" maxlength={500} autocomplete="off" placeholder={L('ai_b_reason_ph')} bind:value={reason} />
				</div>
			{/if}
			<div class="btns">
				<button type="button" class="btn ghost" data-testid="ai-reject" aria-disabled={!named || busy} onclick={() => void decide('reject')}>{rejecting ? L('ai_b_reject_go') : L('ai_b_reject')}</button>
				<button type="button" class="btn primary grow" data-testid="ai-approve" aria-disabled={!named || busy} onclick={() => void decide('approve')}>
					{#if busy}<span class="spin" aria-hidden="true"></span>{/if}{L('ai_b_approve')}
				</button>
			</div>
			{#if !named}<p class="block">{L('ai_r_officer')}</p>{/if}
		{/if}
	</div>
</div>

<style>
	.sheet-in {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
	}

	.scroll {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 18px;
		min-height: 0;
		padding: 24px 26px 18px;
		overflow: auto;
		scrollbar-width: thin;
		scrollbar-color: var(--v3-s4) transparent;
	}

	.banner {
		position: relative;
		flex: none;
		height: 120px;
		margin: -24px -26px -10px;
		overflow: hidden;
	}

	.banner img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: 50% 58%;
	}

	.banner::after {
		content: '';
		position: absolute;
		inset: 0;
		background: linear-gradient(to bottom, transparent 30%, var(--v3-scrim));
	}

	@media (max-width: 1500px), (max-height: 820px) {
		.banner {
			height: 72px;
			margin-bottom: -16px;
		}
	}

	.sh-top {
		position: relative;
		display: flex;
		gap: 14px;
		align-items: flex-start;
	}

	.art {
		flex: none;
		width: 60px;
		height: 60px;
		overflow: hidden;
		border-radius: 16px;
		background: var(--v3-map-bg);
	}

	.art img {
		display: block;
		width: 100%;
		height: 100%;
	}

	.head {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}

	.micro {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
	}

	.title {
		margin: 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-title);
		line-height: var(--v3-lh-title);
		font-weight: 700;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.ev {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.what {
		margin: 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
	}

	.when-line {
		margin: -4px 0 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
	}

	.figs {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 8px;
	}

	.fig {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 10px 12px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.fig b {
		color: var(--v3-t1);
		font-size: var(--v3-text-sub);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.fig span {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}

	.drafts {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.draft {
		padding: 10px 12px;
		border-left: 3px solid var(--v3-line-3);
		border-radius: 4px;
		background: var(--v3-s1);
	}

	.draft p {
		margin: 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.draft .micro {
		margin-bottom: 4px;
		color: var(--v3-t3);
	}

	.hold {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: -6px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.why summary {
		display: flex;
		align-items: center;
		gap: 6px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 600;
		cursor: pointer;
	}

	.why .in {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 8px 0 0 22px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.why .in p {
		margin: 0;
	}

	.said {
		color: var(--v3-t2);
	}

	.act {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 14px 26px 20px;
		border-top: 1px solid var(--v3-line-1);
	}

	.btns {
		display: flex;
		gap: 10px;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		height: var(--v3-ctl-lg);
		padding: 0 18px;
		border: 1px solid var(--v3-line-2);
		border-radius: 12px;
		background: none;
		color: var(--v3-t1);
		font: inherit;
		font-weight: 650;
		cursor: pointer;
	}

	.btn.primary {
		border-color: transparent;
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
	}

	.btn.grow {
		flex: 1;
	}

	.btn[aria-disabled='true'] {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.reason {
		display: flex;
		flex-direction: column;
		gap: 6px;
		font-size: var(--v3-text-meta);
		color: var(--v3-t2);
	}

	.field {
		height: 40px;
		padding: 0 12px;
		border: 1px solid var(--v3-line-2);
		border-radius: 10px;
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
	}

	.refusal {
		display: flex;
		gap: 10px;
		padding: 10px 12px;
		border-radius: 10px;
		background: var(--v3-alert-veil);
		color: var(--v3-alert-text);
		font-size: var(--v3-text-meta);
	}

	.refusal p {
		margin: 0;
	}

	.verbatim {
		display: block;
		color: var(--v3-t2);
	}

	.block {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}

	.done {
		display: flex;
		align-items: center;
		gap: 14px;
		color: var(--v3-ok-text);
	}

	.done > div {
		flex: 1;
	}

	.o-v {
		margin: 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-sub);
		font-weight: 700;
	}

	.o-m {
		margin: 2px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.spin {
		width: 14px;
		height: 14px;
		border: 2px solid currentColor;
		border-right-color: transparent;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
