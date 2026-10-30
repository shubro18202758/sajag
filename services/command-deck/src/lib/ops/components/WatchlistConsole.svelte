<script lang="ts">
	/**
	 * Watchlist and retention (SPEC §6.3 col 3, §9.3; ownership UI-S5B):
	 * the earmarked vehicles and the DPDP retention control.
	 *
	 *   retention  how long reads are kept and whether the purge is actually
	 *              running (`retention-health` data-healthy 1 | 0 | ''): a
	 *              failing control is shown, never silent
	 *   table      each earmarked vehicle: the mark (masked, with its lock,
	 *              unless a duty officer is named), earmark state, lawful
	 *              basis, last read; selecting a row opens the vehicle in the
	 *              inspector. Withdrawing an earmark asks once in an Alert
	 *              (the officer's name is recorded with it).
	 *   add        a popover form: mark, state, lawful basis (the enum the
	 *              oracle enforces), reason, retention days; Earmark stays
	 *              disabled with its reason until a duty officer is named.
	 * Vehicles only: no person, owner or driver field anywhere (ethics rule 3).
	 */
	import { kindIcon } from '$lib/design/icons';
	import { Alert, Button, FormGroup, HTMLSelect, Input, Plate, Popover, ProvenanceTag, Section, Tag } from '$lib/ui';
	import { fmtAgo, fmtDay, fmtTime } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import { ops } from '$lib/ops/store.svelte';
	import { EARMARK_STATES, LAWFUL_BASIS_CODES, type LawfulBasisCode } from '$lib/ops/endpoints';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import Age from '$lib/decisions/wall/Age.svelte';
	import type { VehicleWatchRecord } from '$lib/ops/types';

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	let clock = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (clock = Date.now()), 1000);
		return () => clearInterval(id);
	});

	const ret = $derived(ops.retention);

	// ── add to the watchlist (popover form) ───────────────────────────────
	let plate = $state('');
	let earmark = $state<string>('flagged');
	let basis = $state<string>('stolen_vehicle_fir');
	let reason = $state('');
	let days = $state('30');
	let formOpen = $state(false);

	const daysNum = $derived(Math.max(1, Math.min(90, Math.round(Number(days) || 30))));
	const formReason = $derived(
		!ops.officerOn ? L('wall_watch_needs_officer') : !plate.trim() ? L('wall_watch_needs_mark') : reason.trim().length < 3 ? L('wall_watch_needs_reason') : null,
	);

	async function submit(close: () => void) {
		if (formReason) return;
		const ok = await ops.earmarkPlate(plate.trim(), earmark as 'watch' | 'flagged', reason.trim(), basis as LawfulBasisCode, daysNum);
		if (ok) {
			plate = '';
			reason = '';
			close();
		}
	}

	// ── withdraw (Alert) ──────────────────────────────────────────────────
	let withdrawing = $state<VehicleWatchRecord | null>(null);
	let alertOpen = $state(false);

	function askWithdraw(w: VehicleWatchRecord) {
		withdrawing = w;
		alertOpen = true;
	}

	async function confirmWithdraw() {
		const w = withdrawing;
		if (!w) return;
		await ops.clearWatch(w.vehicleId);
		alertOpen = false;
		withdrawing = null;
	}

	function basisWord(code: string | null): string {
		if (!code) return '—';
		const key = `wall_basis_${code}`;
		const w = L(key);
		return w === key ? code : w;
	}

	function pick(w: VehicleWatchRecord) {
		selection.select(`vehicle:${w.vehicleId}`, { source: 'table' });
	}

	function onKey(e: KeyboardEvent, w: VehicleWatchRecord) {
		if (e.target !== e.currentTarget) return;
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			pick(w);
		}
	}

	const shownMark = (w: VehicleWatchRecord) => ops.plate(w.plate) ?? w.vehicleId.slice(0, 8);
</script>

{#snippet right()}
	<Age at={ops.watchlistUpdated || null} {lang} />
	<Popover placement="bottom-end" bind:open={formOpen}>
		<Button minimal small icon="plus" tooltip={L('wall_watch_add_tip')}>{L('wall_watch_add')}</Button>
		{#snippet content({ close })}
			<form
				class="form"
				onsubmit={(e) => {
					e.preventDefault();
					void submit(close);
				}}
			>
				<div class="f-head">{L('wall_watch_add')}</div>
				<FormGroup label={L('wall_watch_mark')}>
					<Input small fill bind:value={plate} spellcheck="false" autocomplete="off" maxlength={16} data-autofocus />
				</FormGroup>
				<div class="f-row">
					<FormGroup label={L('wall_watch_state')}>
						<HTMLSelect small fill bind:value={earmark} options={EARMARK_STATES.map((s) => ({ value: s, label: L(`wall_earmark_${s}`) }))} />
					</FormGroup>
					<FormGroup label={L('wall_watch_days')}>
						<Input small fill type="number" min="1" max="90" bind:value={days} />
					</FormGroup>
				</div>
				<FormGroup label={L('wall_watch_basis')}>
					<HTMLSelect small fill bind:value={basis} options={LAWFUL_BASIS_CODES.map((b) => ({ value: b, label: basisWord(b) }))} />
				</FormGroup>
				<FormGroup label={L('wall_watch_reason')}>
					<Input small fill bind:value={reason} maxlength={200} placeholder={L('wall_watch_reason_ph')} />
				</FormGroup>
				<div class="f-foot">
					<Button small onclick={close}>{L('wall_cancel')}</Button>
					<Button small intent="primary" type="submit" disabled={!!formReason || ops.watchBusy !== null} disabledReason={formReason} reasonInline>
						{L('wall_watch_earmark')}
					</Button>
				</div>
			</form>
		{/snippet}
	</Popover>
{/snippet}

<Section title={L('wall_watch')} icon={kindIcon('vehicle')} level={2} sub={L('wall_watch_count', ops.watchlist.length)} {right} data-prim="panel" data-wall="watchlist">
	<div class="retention" data-testid="retention-health" data-healthy={ret?.healthy == null ? '' : ret.healthy ? '1' : '0'}>
		{#if ret}
			<span class="ell">{L('wall_ret_line', ret.defaultDays ?? '—', ret.earmarkCapDays ?? '—')}</span>
			{#if ret.healthy === true}
				<Tag intent="success" tooltip={ret.lastSuccessAt ? L('wall_ret_last', fmtTime(ret.lastSuccessAt), ret.lastRemoved ?? 0) : null}>{L('wall_ret_healthy')}</Tag>
			{:else if ret.healthy === false}
				<Tag intent="danger" tooltip={L('wall_ret_failing_tip')}>{L('wall_ret_failing', ret.consecutiveFailures)}</Tag>
			{:else}
				<Tag>{L('wall_ret_unknown')}</Tag>
			{/if}
		{:else}
			<span class="muted">{ops.retentionNote ?? L('wall_ret_waiting')}</span>
		{/if}
	</div>

	{#if ops.watchlist.length === 0}
		<p class="empty">{ops.watchlistNote ?? L('wall_watch_none')}</p>
	{:else}
		<table class="wdt">
			<colgroup><col /><col style:width="76px" /><col style:width="132px" /><col style:width="88px" /><col style:width="40px" /></colgroup>
			<thead>
				<tr>
					<th scope="col">{L('wall_watch_col_vehicle')}</th>
					<th scope="col">{L('wall_watch_col_state')}</th>
					<th scope="col">{L('wall_watch_col_basis')}</th>
					<th scope="col" class="num">{L('wall_watch_col_last')}</th>
					<th aria-hidden="true"></th>
				</tr>
			</thead>
			<tbody>
				{#each ops.watchlist as w (w.vehicleId)}
					{@const sel = selection.current === `vehicle:${w.vehicleId}`}
					<tr class={['pick', sel && 'is-selected']} tabindex="0" aria-selected={sel} data-vehicle-id={w.vehicleId} onclick={() => pick(w)} onkeydown={(e) => onKey(e, w)}>
						<td>
							<div class="c">
								<Plate mark={shownMark(w)} masked={!ops.officerOn} data-testid="watch-plate" />
								{#if w.lastSighting?.source === 'emulated_anpr'}<ProvenanceTag source="emulated" compact {lang} />{/if}
							</div>
						</td>
						<td><div class="c"><Tag intent={w.earmarkState === 'flagged' ? 'danger' : 'none'}>{L(`wall_earmark_${w.earmarkState ?? 'watch'}`)}</Tag></div></td>
						<td><div class="c"><span class="ell" title={ops.text(w.earmarkReason) || undefined}>{basisWord(w.lawfulBasis)}</span></div></td>
						<td class="num">
							<div class="c">
								<span class="tn" title={w.retentionUntil ? L('wall_watch_keep_until', fmtDay(w.retentionUntil)) : undefined}>{w.lastSighting?.t ? fmtAgo(w.lastSighting.t, clock, lang) : '—'}</span>
							</div>
						</td>
						<td class="num">
							<div class="c" role="presentation" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
								<Button
									minimal
									small
									icon="cross"
									tooltip={ops.officerOn ? L('wall_watch_withdraw') : L('wall_watch_needs_officer')}
									aria-label={L('wall_watch_withdraw')}
									disabled={!ops.officerOn || ops.watchBusy !== null}
									loading={ops.watchBusy === w.vehicleId}
									onclick={() => askWithdraw(w)}
								/>
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</Section>

<Alert
	bind:open={alertOpen}
	intent="primary"
	icon="cross"
	confirmLabel={L('wall_watch_withdraw')}
	cancelLabel={L('wall_cancel')}
	loading={!!withdrawing && ops.watchBusy === withdrawing.vehicleId}
	onconfirm={() => void confirmWithdraw()}
	oncancel={() => (withdrawing = null)}
	{lang}
>
	{#if withdrawing}
		<p class="a-title">{L('wall_watch_withdraw_q')} <Plate mark={shownMark(withdrawing)} masked={!ops.officerOn} /></p>
		<p class="a-body">{L('wall_watch_withdraw_body')}</p>
	{/if}
</Alert>

<style>
	.retention {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		padding: 8px 16px;
		border-bottom: 1px solid var(--v-line-1);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.ell {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.muted {
		color: var(--v-ink-2);
	}

	.tn {
		font-variant-numeric: tabular-nums;
	}

	.empty {
		margin: 0;
		padding: 10px 16px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.form {
		display: flex;
		flex-direction: column;
		gap: 4px;
		width: 320px;
		padding: 12px 16px;
	}

	.f-head {
		margin-bottom: 4px;
		font-weight: 600;
	}

	.f-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 96px;
		gap: 8px;
	}

	.f-foot {
		display: flex;
		align-items: flex-start;
		justify-content: flex-end;
		gap: 8px;
		margin-top: 4px;
	}

	.a-title {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 6px;
		margin: 0 0 6px;
		font-weight: 600;
	}

	.a-body {
		margin: 0;
		color: var(--v-ink-2);
	}
</style>
