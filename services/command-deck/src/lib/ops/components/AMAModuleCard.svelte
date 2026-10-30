<script lang="ts">
	/**
	 * Active movement adaptation (SPEC §6.3 col 3; ownership UI-S5B): the
	 * AMA module's posture in four rows.
	 *
	 *   Band driver        the band adaptation reads (`ama-band` data-band; a
	 *                      band nobody reported is UNKNOWN, never Green; a
	 *                      stale city band says since when, in the tooltip)
	 *   Protocol floors    advance-closure floors per protection class
	 *                      (`ama-floors`, each `[data-class][data-sec]`), from
	 *                      GET /adaptive/module, else a labelled local copy of
	 *                      the same policy (Z+ 180 / Z 120 / Y 60 s)
	 *   Shadow evaluation  the newest published parameter set's twin
	 *                      evaluation (GET /adaptive/overrides): passed,
	 *                      failed closed to baseline, or unavailable, and why
	 *   Engine             the brain's degradation tier, checkpoints paused
	 *
	 * The stages of the module live behind the header's info button (copy
	 * density, SPEC §3.5). Surface only: this changes no adaptive behaviour.
	 */
	import { onMount } from 'svelte';
	import BandChip from '$lib/primitives/BandChip.svelte';
	import { ACTION_ICON } from '$lib/design/icons';
	import { Button, Icon, Popover, Section, Tag, Tooltip } from '$lib/ui';
	import { fmtStamp } from '$lib/ui/format/format';
	import { shadowRow } from '$lib/decisions/wall/ama';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import { ops } from '$lib/ops/store.svelte';
	import { ORACLE_V1 } from '$lib/ops/endpoints';
	import { displayText } from '$lib/workspace/display';
	import type { BandCode } from '$lib/ops/types';

	interface AmaStage {
		name: string;
		detail: string;
	}
	interface AmaModule {
		module: string;
		summary: string;
		stages: AmaStage[];
		protocol_floors_advance_closure_sec: Record<string, number | null>;
		fail_closed: boolean;
	}

	/** The same policy traffic_oracle/adaptive/surfacing.py AMA_MODULE serves (labelled when used). */
	const FALLBACK: AmaModule = {
		module: 'Active Movement Adaptation',
		summary:
			'Every active corridor event is classified into a situation band; hysteresis, protocol floors and a twin shadow-evaluation stand between a reading and a published parameter.',
		stages: [
			{ name: 'Situation', detail: 'classify each active event into a band' },
			{ name: 'Hysteresis', detail: 'a class change must persist through its dwell window' },
			{ name: 'Protocol floors', detail: 'advance closure floors Z+ 180 / Z 120 / Y 60 s on every publish' },
			{ name: 'Twin shadow-eval', detail: 'a non-baseline plan must beat baseline in a paired twin run, else it fails closed' },
			{ name: 'Audited persistence', detail: 'situation log and parameter overrides' },
		],
		protocol_floors_advance_closure_sec: { 'Z+': 180, Z: 120, Y: 60, X: null, none: null },
		fail_closed: true,
	};

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	let descriptor = $state<AmaModule | null>(null);
	let fallback = $state(false);

	onMount(async () => {
		try {
			const res = await fetch(`${ORACLE_V1}/adaptive/module`, { signal: AbortSignal.timeout(6000) });
			if (!res.ok) throw new Error(`${res.status}`);
			descriptor = (await res.json()) as AmaModule;
			fallback = false;
		} catch {
			descriptor = FALLBACK;
			fallback = true;
		}
	});

	const mod = $derived(descriptor ?? FALLBACK);
	const floors = $derived(Object.entries(mod.protocol_floors_advance_closure_sec ?? FALLBACK.protocol_floors_advance_closure_sec));
	const withFloor = $derived(floors.filter(([, sec]) => sec != null));
	const noFloor = $derived(floors.filter(([, sec]) => sec == null));
	const newest = $derived(ops.overrides[0] ?? null);
	const subjects = $derived(ops.cityBand?.subjects ?? ops.signalPlans?.bandSubjects ?? null);
	const brain = $derived(ops.brain);

	/**
	 * The newest evaluation in words (F-12): passed, failed closed to baseline,
	 * unavailable — or NOT REQUIRED for a baseline set (never "Unavailable");
	 * its publish time only when the word comes from that published set.
	 */
	const shadowState = $derived(shadowRow({ newest, evidence: ops.bandEvidence ?? null }));
	const shadow = $derived.by(() => {
		if (!shadowState) return null;
		const key = `wall_ama_shadow_${shadowState.state}`;
		const word = L(key);
		return { raw: shadowState.state, word: word === key ? displayText(shadowState.state) : word };
	});
	const shadowWhy = $derived(shadowState?.why ? displayText(shadowState.why) : null);

	const tierWord = $derived.by(() => {
		const tier = brain?.degradationTier?.toUpperCase() ?? null;
		if (!tier) return null;
		const key = `wall_ama_tier_${tier}`;
		const w = L(key);
		return w === key ? displayText(tier.toLowerCase()) : w;
	});
</script>

{#snippet right()}
	<span class="hint">{subjects ? L('wall_ama_subjects', subjects) : L('wall_ama_none_live')}</span>
	<Popover placement="bottom-end">
		<Button minimal small icon="info-sign" tooltip={L('wall_ama_how')} aria-label={L('wall_ama_how')} />
		{#snippet content()}
			<div class="how">
				<div class="how-h">{L('wall_ama_how')}</div>
				<p class="how-sum">{lang === 'en' ? mod.summary : L('wall_ama_summary')}</p>
				<ol class="stages">
					{#each mod.stages as s (s.name)}
						<li><span class="st-name">{s.name}</span><span class="st-detail">{s.detail}</span></li>
					{/each}
				</ol>
				{#if fallback}<p class="how-note">{L('wall_ama_fallback')}</p>{/if}
			</div>
		{/snippet}
	</Popover>
{/snippet}

<Section title={L('wall_ama')} icon="automatic-updates" level={2} {right} data-prim="panel" data-wall="adaptation">
	<table class="props">
		<tbody>
			<tr>
				<th scope="row">{L('wall_ama_band')}</th>
				<td>
					<span class="v" data-testid="ama-band" data-band={ops.band ?? 'UNKNOWN'}>
						{#if ops.band}
							<BandChip band={ops.band as BandCode} size="sm" {lang} />
						{:else}
							<Tooltip content={ops.bandStaleSince != null ? ops.bandSource : null}><span class="unknown">{L('wall_band_unknown')}</span></Tooltip>
						{/if}
						{#if ops.bandSimulated === true}
							<Tooltip content={L('wall_band_simulated_tip')}><span class="glyph"><Icon name={ACTION_ICON.simulated} size={12} /></span></Tooltip>
						{/if}
						<span class="muted">{ops.bandSourceKind === 'situation_log' ? L('wall_band_scope_event') : ops.bandSourceKind === 'none' ? L('wall_ama_no_subject') : L('wall_band_scope_city')}</span>
					</span>
				</td>
			</tr>
			<tr>
				<th scope="row">{L('wall_ama_floors')}</th>
				<td>
					<span class="v floors" data-testid="ama-floors">
						{#each withFloor as [cls, sec] (cls)}
							<span class="floor" data-class={cls} data-sec={sec ?? ''}><span class="cls">{cls}</span><span class="tn">{L('wall_sp_seconds', sec)}</span></span>
						{/each}
						{#if noFloor.length}
							<span class="nofloor muted">
								{#each noFloor as [cls], i (cls)}<span data-class={cls} data-sec="">{i ? ', ' : ''}{cls === 'none' ? L('wall_ama_class_none') : cls}</span>{/each}<span>{L('wall_ama_no_floor_suffix')}</span>
							</span>
						{/if}
						{#if fallback}<Tag tooltip={L('wall_ama_fallback')}>{L('wall_ama_local')}</Tag>{/if}
					</span>
				</td>
			</tr>
			<tr>
				<th scope="row">{L('wall_ama_shadow')}</th>
				<td>
					<span class="v">
						{#if shadow}
							<span>{shadow.word}</span>
							{#if shadowWhy}<span class="muted ell" title={shadowWhy}>{shadowWhy}</span>{/if}
						{:else}
							<span class="muted">{ops.overridesNote ?? L('wall_ama_shadow_none')}</span>
						{/if}
						{#if shadowState?.publishedAt}<span class="muted tn" data-testid="ama-shadow-published">{L('wall_ama_published', fmtStamp(shadowState.publishedAt))}</span>{/if}
					</span>
				</td>
			</tr>
			<tr>
				<th scope="row">{L('wall_ama_engine')}</th>
				<td>
					<span class="v">
						{#if tierWord}<span>{tierWord}</span>{:else}<span class="muted">{L('wall_ama_engine_unknown')}</span>{/if}
						{#if brain?.checkpointsPaused}<span class="muted">{L('wall_ama_checkpoints_paused')}</span>{/if}
						{#if mod.fail_closed}<Tag tooltip={L('wall_ama_fail_closed_tip')}>{L('wall_ama_fail_closed')}</Tag>{/if}
					</span>
				</td>
			</tr>
		</tbody>
	</table>
</Section>

<style>
	.hint {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		white-space: nowrap;
	}

	.props {
		width: 100%;
		border-collapse: collapse;
		margin: 4px 0 8px;
	}

	.props th,
	.props td {
		padding: 6px 0;
		border-bottom: 1px solid var(--v-line-1);
		line-height: 18px;
		vertical-align: baseline;
	}

	.props tr:last-child th,
	.props tr:last-child td {
		border-bottom: 0;
	}

	.props th {
		width: 38%;
		padding-left: 16px;
		padding-right: 12px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 400;
		text-align: left;
		white-space: nowrap;
	}

	.props td {
		padding-right: 16px;
		font-size: var(--v-text-base);
	}

	.v {
		display: inline-flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 4px 8px;
		min-width: 0;
		max-width: 100%;
	}

	.muted {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.ell {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.unknown {
		color: var(--v-ink-2);
	}

	.glyph {
		display: inline-flex;
		color: var(--v-ink-2);
	}

	.floors {
		gap: 4px 12px;
	}

	.floor {
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
		white-space: nowrap;
	}

	.nofloor {
		display: inline;
		white-space: nowrap;
	}

	.cls {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.tn {
		font-variant-numeric: tabular-nums;
	}

	.how {
		width: 340px;
		padding: 12px 16px;
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.how-h {
		margin-bottom: 6px;
		font-size: var(--v-text-base);
		font-weight: 600;
	}

	.how-sum {
		margin: 0 0 8px;
		color: var(--v-ink-2);
	}

	.stages {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0;
		padding-left: 18px;
	}

	.stages li {
		display: flex;
		flex-direction: column;
	}

	.st-name {
		font-weight: 600;
	}

	.st-detail {
		color: var(--v-ink-2);
	}

	.how-note {
		margin: 8px 0 0;
		color: var(--v-ink-2);
	}
</style>
