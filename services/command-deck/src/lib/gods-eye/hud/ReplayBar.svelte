<script lang="ts">
	/**
	 * ReplayBar — the bottom dock's REPLAY mode (SPEC §5.3, §7.3): one recorded
	 * emulator tape on its own axis, bound to the existing `replay` store
	 * (hud/replay.svelte.ts → gods-eye/replay.ts on the canvas clock).
	 *
	 *   the Emulated provenance (`replay-emulated-pill`: a tape is a recording
	 *   of emulated causes; the pill's text says so, never only a tooltip) ·
	 *   the run picker (`replay-run`) · play / pause · speed · the scrubber
	 *   (`replay-scrubber`, tape seconds) · the tape clock and when it was
	 *   recorded (IST) · reads and hits so far
	 *   the timeline in replay mode: its axis is TAPE time (t+mm:ss), never
	 *   IST; a press or a drag on it moves the cursor
	 *   the latest narrative row at the cursor
	 *
	 * Nothing here writes anywhere: a replay never re-delivers frames (that is
	 * the emulator's own POST /replay, which this module never calls). The
	 * root keeps `replay-bar[data-status]`.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.analysis';
	import { Button, HTMLSelect, Icon, Tooltip } from '$lib/ui';
	import { fmtStamp } from '$lib/ui/format/format';
	import { ops } from '$lib/ops/store.svelte';
	import Timeline from '$lib/analysis/timeline/Timeline.svelte';
	import { tapeLabel } from '$lib/analysis/timeline/bins';
	import { masked } from '$lib/analysis/audit/rows';
	import { replay } from './replay.svelte';

	let { density = 'compact', lang = ops.lang }: { density?: 'compact' | 'full'; lang?: string } = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const tape = $derived(replay.tape);
	const duration = $derived(tape?.durationSec ?? 0);
	const readsSoFar = $derived(tape ? tape.anpr.filter((r) => r.t <= replay.cursorSec).length : 0);
	const hitsSoFar = $derived(tape ? tape.anpr.filter((r) => r.t <= replay.cursorSec && r.hit).length : 0);
	const latest = $derived(replay.narrativeUpTo(replay.cursorSec)[0] ?? null);
	const binding = $derived(tape ? { tape, cursorSec: replay.cursorSec, setCursor: (s: number) => replay.setCursor(s) } : undefined);

	const runOptions = $derived.by(() => {
		const opts = replay.runs.map((r) => ({
			value: String(r.runId),
			label: `${L('an_rp_run_n', r.runId)} · ${r.useCaseId ?? '—'}${r.isReplay ? ` (${L('an_rp_run_replay')})` : ''}`,
		}));
		if (replay.runId != null && !replay.runs.some((r) => r.runId === replay.runId)) opts.unshift({ value: String(replay.runId), label: L('an_rp_run_n', replay.runId) });
		return opts;
	});
	const speedOptions = [10, 30, 60, 120].map((s) => ({ value: String(s), label: `×${s}` }));

	function pickRun(e: Event) {
		// run ids are positive integers; an empty selection loads nothing
		const raw = (e.currentTarget as HTMLSelectElement).value;
		const id = Number(raw);
		if (raw !== '' && Number.isInteger(id) && id > 0 && id !== replay.runId) void replay.load(id);
	}
</script>

<div class="rp" data-testid="replay-bar" data-status={replay.status}>
	<div class="ctl">
		<Tooltip content={L('an_rp_emulated_tip')}>
			<span class="emu" data-testid="replay-emulated-pill"><Icon name="lab-test" size={12} />{L('an_rp_emulated')}</span>
		</Tooltip>
		<label class="fld">
			<span>{L('an_rp_run')}</span>
			<HTMLSelect small value={replay.runId != null ? String(replay.runId) : ''} options={runOptions} onchange={pickRun} data-testid="replay-run" aria-label={L('an_rp_run')} />
		</label>
		<Button
			small
			minimal
			icon={replay.playing ? 'pause' : 'play'}
			disabled={replay.status !== 'ready'}
			tooltip={replay.playing ? L('an_rp_pause') : L('an_rp_play')}
			aria-label={replay.playing ? L('an_rp_pause') : L('an_rp_play')}
			onclick={() => (replay.playing ? replay.pause() : replay.play())}
		/>
		<label class="fld">
			<span>{L('an_rp_speed')}</span>
			<HTMLSelect small value={String(replay.speed)} options={speedOptions} onchange={(e) => (replay.speed = Number((e.currentTarget as HTMLSelectElement).value) || 60)} aria-label={L('an_rp_speed')} />
		</label>
		{#if replay.status === 'ready' && tape}
			<input
				type="range"
				class="scrubber"
				min="0"
				max={duration}
				step="1"
				value={replay.cursorSec}
				oninput={(e) => {
					replay.pause();
					replay.setCursor(Number((e.currentTarget as HTMLInputElement).value));
				}}
				aria-label={L('an_rp_scrubber')}
				data-testid="replay-scrubber"
			/>
			<span class="clock">
				{tapeLabel(replay.cursorSec)} / {tapeLabel(duration)}
				<span class="rec">{L('an_rp_recorded', fmtStamp(tape.t0))}</span>
			</span>
			<span class="counts">{L('an_rp_counts', readsSoFar, hitsSoFar)}</span>
		{:else}
			<span class="note">{replay.status === 'loading' ? L('an_rp_loading') : (replay.note ?? L('an_rp_empty'))}</span>
		{/if}
	</div>
	{#if binding}
		<div class="body">
			<Timeline
				start={0}
				end={duration}
				window={null}
				live={false}
				cursor={replay.cursorSec}
				related={new Set()}
				{density}
				replay={binding}
				onbrush={() => {}}
				oncursor={(s) => {
					replay.pause();
					replay.setCursor(s);
				}}
				{lang}
				showKey={false}
			/>
		</div>
		{#if latest}
			<p class="latest"><span class="ll">{L('an_rp_latest')}</span> {tapeLabel(latest.t)} · {masked(latest.text, ops.officerOn)}</p>
		{/if}
	{/if}
</div>

<style>
	.rp {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		min-width: 0;
		font-size: 12px;
		line-height: 16px;
		color: var(--v-ink-1);
	}

	.ctl {
		display: flex;
		align-items: center;
		gap: 10px;
		flex: 0 0 auto;
		height: 32px;
		padding: 0 16px;
		min-width: 0;
		overflow: hidden;
		white-space: nowrap;
	}

	.emu {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		height: 20px;
		padding: 0 6px;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		color: var(--v-ink-1);
	}

	.fld {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--v-ink-2);
	}

	.scrubber {
		flex: 1 1 160px;
		min-width: 80px;
		accent-color: var(--v-ink-2);
	}

	.clock,
	.counts {
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
	}

	.rec {
		margin-left: 6px;
	}

	.note {
		color: var(--v-ink-2);
	}

	.body {
		position: relative;
		flex: 1 1 auto;
		min-height: 0;
	}

	.latest {
		flex: 0 0 auto;
		margin: 0;
		padding: 0 16px 4px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--v-ink-2);
	}

	.ll {
		color: var(--v-ink-1);
	}
</style>
