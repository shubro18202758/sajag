<script lang="ts">
	/**
	 * The dispatch request a pursuit choke's "Request unit" opens (SPEC §5.3
	 * ObjectInspector Pursuit section, §5.4 Writers "Pursuit choke · Request
	 * unit"): the agency, the unit and the waypoint — PRE-FILLED with the
	 * choke's junction (`dispatch-waypoint`, a select over the ranked chokes).
	 * Submitting files a dispatch REQUEST on the open pursuit event through the
	 * existing writer (requestDispatch, via WRITERS 'pursuit.request-unit'): a
	 * duty officer still approves it in Dispatch. Disabled with its reason
	 * until an officer is named and the pursuit event is open.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { AGENCIES, DEFAULT_UNIT_ID } from '$lib/ops/endpoints';
	import { toasts } from '$lib/shell/toast.svelte';
	import { kindIcon } from '$lib/design/icons';
	import { Button, FormGroup, HTMLSelect, Input, Reason } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.decisions';
	import { WRITERS, type WriterResult } from '../writers';
	import type { Unit } from '../units';

	let {
		eventId,
		vehicleId = null,
		chokes,
		junctionId,
		open: eventOpen,
		lang = ops.lang,
		onclose,
	}: {
		eventId: string;
		vehicleId?: string | null;
		chokes: readonly { junctionId: number; name: string; rank: number; likelyPassed: boolean }[];
		junctionId: number;
		open: boolean;
		lang?: string;
		onclose: () => void;
	} = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const AGENCY_CHOICES = ['police', 'jan_rakshak', 'traffic'] as const;

	// svelte-ignore state_referenced_locally
	let waypoint = $state(String(junctionId));
	let agency = $state<string>('police');
	let unitId = $state(DEFAULT_UNIT_ID.police);
	let busy = $state(false);
	let refusal = $state<string | null>(null);

	const block = $derived(!ops.officerOn ? L('dec_reason_officer_request') : !eventOpen ? L('dec_refuse_event_closed') : null);
	const options = $derived(
		chokes.map((c) => ({ value: String(c.junctionId), label: `${c.rank} · ${c.name}${c.likelyPassed ? ` · ${L('dec_likely_passed')}` : ''}` })),
	);

	function onAgency() {
		unitId = DEFAULT_UNIT_ID[agency] ?? unitId;
	}

	async function submit() {
		if (block || busy) return;
		busy = true;
		refusal = null;
		const choke = chokes.find((c) => String(c.junctionId) === waypoint);
		const unit: Unit = { kind: 'pursuit', id: vehicleId ?? eventId, subjectUrn: `event:${eventId}`, title: '', deadline: null, severity: 2, data: {} };
		try {
			const res = (await WRITERS['pursuit.request-unit'].run(unit, ops.dutyOfficer.trim(), {
				eventId,
				junctionId: Number(waypoint),
				agency,
				unitId,
			})) as WriterResult;
			if (res.ok) {
				toasts.push({ kind: 'act', title: L('dec_done_request'), body: L('dec_done_request_body', AGENCIES[agency as keyof typeof AGENCIES]?.label ?? agency, choke?.name ?? `J${waypoint}`) });
				onclose();
			} else {
				refusal = res.detail ?? WRITERS['pursuit.request-unit'].refusals[res.refusal ?? ''] ?? L('dec_refuse_refused');
			}
		} finally {
			busy = false;
		}
	}
</script>

<form class="req" data-testid="pursuit-request-form" onsubmit={(e) => (e.preventDefault(), void submit())}>
	<div class="grid">
		<FormGroup label={L('dec_req_agency')} class="fg">
			<HTMLSelect
				fill
				small
				bind:value={agency}
				onchange={onAgency}
				options={AGENCY_CHOICES.map((a) => ({ value: a, label: AGENCIES[a].label }))}
			/>
		</FormGroup>
		<FormGroup label={L('dec_req_unit')} class="fg">
			<Input small fill bind:value={unitId} maxlength={32} autocomplete="off" />
		</FormGroup>
	</div>
	<FormGroup label={L('dec_req_waypoint')} class="fg">
		<HTMLSelect fill small data-testid="dispatch-waypoint" bind:value={waypoint} {options} />
	</FormGroup>
	<div class="acts">
		<span class="grow"></span>
		<Button small onclick={() => onclose()}>{L('dec_req_cancel')}</Button>
		<Button small intent="primary" type="submit" icon={kindIcon('dispatch')} loading={busy} disabled={!!block || busy} disabledReason={block}>{L('dec_btn_request_unit')}</Button>
	</div>
	{#if block}<Reason text={block} />{:else if refusal}<p class="refusal">{refusal}</p>{:else}<p class="hint">{L('dec_req_hint')}</p>{/if}
</form>

<style>
	.req {
		display: flex;
		flex-direction: column;
		gap: 0;
		margin: 4px 16px 8px 48px;
		padding: 12px;
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-2);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}

	.grid {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 8px;
	}

	.req :global(.fg) {
		margin: 0 0 8px;
	}

	.acts {
		display: flex;
		gap: 8px;
		align-items: center;
	}

	.grow {
		flex: 1 1 auto;
	}

	.hint,
	.refusal {
		margin: 8px 0 0;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.refusal {
		color: var(--v-ink-1);
	}
</style>
