<script lang="ts">
	/**
	 * FieldReportSheet — "Report by voice" (PLAN §2.4 C): a signed-in officer holds the button, speaks a short report
	 * (Marathi by default), and the on-premises speech service turns it into a structured claim — the place from the
	 * city gazetteer (on a mini map), the kind, the severity, the transcript and the words that decided them — labelled
	 * UNVERIFIED-FIELD. A typed report takes the same path. "Send to the board" creates ONE board entry through the
	 * platform's event ingestion (board.ts → POST /api/v1/events) in the oracle's `planning` state, by the named
	 * officer, labelled unverified; an officer confirms, edits or dismisses it there. Nothing is auto-confirmed.
	 *
	 * Privacy: the recording lives in memory for one request; it is never stored, and no voice is identified.
	 * Accessibility: a native modal <dialog> (focus held inside, Esc closes); the hold button works with a pointer and
	 * with Space or Enter held down; every state change is announced in a polite live region.
	 */
	import { onDestroy, tick } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import { LANDMARKS, inBox } from '$lib/city';
	import Glyph from '../Glyph.svelte';
	import MapThumb from '../map/MapThumb.svelte';
	import { loadSegments } from '../public/geometry';
	import './packs.field';
	import './packs.field.core';
	import Mic from './Mic.svelte';
	import { FieldApiError, reportFromAudio, reportFromText } from './api';
	import { writeBoardEntry } from './board';
	import { boardDraftFromReport, chosenPlace, cueRuns, nearestSegment, officerOf, placeRingM, speakLang, SPOKEN_LANGS, type FieldReport, type ReportPlace, type SpokenLang } from './model';
	import { Recorder } from './recorder.svelte';
	import { SPOKEN_EXAMPLES } from './samples';

	let { open = $bindable(false), lang, officer }: { open?: boolean; lang: string; officer: string | null } = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const SPOKEN_LABEL: Record<SpokenLang, string> = { mr: 'मराठी', en: 'English', hi: 'हिंदी' };

	let dialog = $state<HTMLDialogElement | null>(null);
	const rec = new Recorder();

	/** The spoken language starts as the console's (English by default; मराठी or हिंदी when the console is in it) each
	 * time the sheet opens, until the officer picks one on the three-way switch (English reports go through the
	 * speech service's multilingual model). */
	let spoken = $state<SpokenLang>('en');
	let spokenPicked = false;
	$effect(() => {
		if (open && !spokenPicked) spoken = speakLang(lang);
	});
	/** The switch lists English first, then the console's order. */
	const SPOKEN_ORDER: readonly SpokenLang[] = (['en', 'hi', 'mr'] as const).filter((c) => (SPOKEN_LANGS as readonly string[]).includes(c));
	let phase = $state<'idle' | 'recording' | 'reading' | 'result'>('idle');
	let problem = $state<string | null>(null);
	let report = $state<FieldReport | null>(null);
	let picked = $state<ReportPlace | null>(null);
	let text = $state('');
	let send = $state<{ state: 'idle' | 'sending' | 'sent' | 'error'; eventId?: string; detail?: string }>({ state: 'idle' });
	let ctl: AbortController | null = null;

	const place = $derived(picked ?? report?.place ?? null);
	const who = $derived(officerOf(officer));
	const secs = $derived(Math.floor(rec.elapsed / 1000));
	const clock = $derived(`0:${String(Math.min(60, secs)).padStart(2, '0')}`);
	const runs = $derived(report ? cueRuns(report.transcript, [...report.kindCues, ...report.severityCues]) : []);
	const overlay = $derived(
		place
			? {
					points: [{ at: [place.lon, place.lat] as [number, number], glyph: 'pin', tone: 'brand' as const, halo: true, label: lang === 'en' ? place.nameEn : place.nameMr }],
					rings: [{ at: [place.lon, place.lat] as [number, number], radiusM: placeRingM(place.score) }],
				}
			: null,
	);
	const status = $derived(
		phase === 'recording' ? `${L('fld_listening')} ${clock}` : phase === 'reading' ? L('fld_transcribing') : problem ?? (report ? L('fld_res_title') : ''),
	);

	$effect(() => {
		if (!dialog) return;
		if (open && !dialog.open) {
			dialog.showModal();
			void tick().then(() => dialog?.querySelector<HTMLElement>('.hold')?.focus());
		} else if (!open && dialog.open) dialog.close();
	});

	function onClose() {
		rec.cancel();
		ctl?.abort();
		open = false;
		if (phase === 'recording' || phase === 'reading') phase = 'idle';
	}

	function reset() {
		ctl?.abort();
		report = null;
		picked = null;
		problem = null;
		send = { state: 'idle' };
		phase = 'idle';
	}

	function explain(err: unknown): string {
		if (err instanceof FieldApiError) {
			if (err.kind === 'busy') return L('fld_busy');
			if (err.kind === 'down') return L('fld_down');
		}
		return L('fld_failed');
	}

	// ── hold to speak ─────────────────────────────────────────────────────
	let holding = false;
	async function down(e?: Event) {
		e?.preventDefault();
		if (holding || phase === 'reading') return;
		holding = true;
		reset();
		phase = 'recording';
		await rec.start();
		if (rec.state === 'error') {
			holding = false;
			phase = 'idle';
			problem = rec.error === 'denied' ? L('fld_mic_denied') : rec.error === 'short' ? L('fld_too_short') : L('fld_mic_none');
		}
	}

	async function up() {
		if (!holding) return;
		holding = false;
		const blob = await rec.stop();
		if (!blob) {
			phase = 'idle';
			if (rec.error === 'short') problem = L('fld_too_short');
			else if (rec.error) problem = L('fld_failed');
			return;
		}
		await read(() => reportFromAudio(blob, spoken, ctl?.signal));
	}

	function key(e: KeyboardEvent, isDown: boolean) {
		if (e.key !== ' ' && e.key !== 'Enter') return;
		e.preventDefault();
		if (isDown && !e.repeat) void down();
		if (!isDown) void up();
	}

	async function read(fn: () => Promise<FieldReport>) {
		ctl?.abort();
		ctl = new AbortController();
		phase = 'reading';
		problem = null;
		try {
			report = await fn();
			phase = 'result';
		} catch (err) {
			if (err instanceof DOMException && err.name === 'AbortError') return;
			phase = 'idle';
			problem = explain(err);
		}
	}

	function readText(e: SubmitEvent) {
		e.preventDefault();
		const v = text.trim();
		if (!v) return;
		reset();
		void read(() => reportFromText(v, spoken, ctl?.signal));
	}

	// ── the officer's own pick: any of the city's places ─────────────────────
	const landmarks = [...LANDMARKS].sort((a, b) => a.en.localeCompare(b.en));
	function pickLandmark(id: string) {
		const l = LANDMARKS.find((x) => x.id === id);
		if (l) picked = chosenPlace(l);
	}

	// ── send to the board ─────────────────────────────────────────────────
	const blocked = $derived(!who ? L('fld_need_officer') : !place ? L('fld_no_place') : null);

	async function toBoard() {
		if (!report || !place || !who || send.state === 'sending' || send.state === 'sent') return;
		send = { state: 'sending' };
		try {
			const segs = await loadSegments();
			const road = nearestSegment([place.lon, place.lat], [...segs.values()]);
			if (!road) {
				send = { state: 'error', detail: L('fld_no_road') };
				return;
			}
			const draft = boardDraftFromReport(report, place, road.segmentId, who, Date.now(), inBox(place.lon, place.lat));
			const out = await writeBoardEntry(draft);
			send = { state: 'sent', eventId: out.eventId };
		} catch (err) {
			send = { state: 'error', detail: L('fld_send_failed', err instanceof FieldApiError ? err.detail : err instanceof Error ? err.message : String(err)) };
		}
	}

	onDestroy(() => {
		rec.cancel();
		ctl?.abort();
	});

	// the test hook: the smoke drives the same client path with a recorded clip (no microphone in a headless browser)
	$effect(() => {
		if (typeof window === 'undefined') return;
		(window as unknown as Record<string, unknown>).__FIELD_REPORT__ = {
			phase,
			report: report ? { kind: report.kind, severity: report.severity, place: place?.id ?? null, transcript: report.transcript, verification: report.verification } : null,
			send: send.state,
			submitAudio: (blob: Blob) => {
				reset();
				return read(() => reportFromAudio(blob, spoken, ctl?.signal));
			},
		};
	});
</script>

<dialog bind:this={dialog} class="sheet" aria-labelledby="fld-title" onclose={onClose} oncancel={onClose} data-testid="field-sheet" data-phase={phase}>
	<div class="inner">
		<header class="head">
			<span class="badge"><Mic size={22} /></span>
			<div class="ht">
				<h2 id="fld-title">{L('fld_sheet_title')}</h2>
				<p class="lead">{L('fld_sheet_lead')}</p>
			</div>
			<button type="button" class="x" aria-label={L('fld_close')} onclick={() => (open = false)}><Glyph name="close" size={20} /></button>
		</header>

		<div class="langs" role="group" aria-label={L('fld_lang_label')}>
			{#each SPOKEN_ORDER as c (c)}
				<button type="button" lang={c} class={['lang', spoken === c && 'is-pressed']} aria-pressed={spoken === c} onclick={() => ((spoken = c), (spokenPicked = true))} disabled={phase === 'recording' || phase === 'reading'}>{SPOKEN_LABEL[c]}</button>
			{/each}
		</div>

		{#if phase !== 'result'}
			<div class={['stage', phase]}>
				<div class="wave" aria-hidden="true">
					{#each rec.bars as b, i (i)}<i style:height={`${8 + b * 52}px`} style:opacity={phase === 'recording' ? 0.35 + b * 0.65 : 0.18}></i>{/each}
				</div>
				<button
					type="button"
					class={['hold', phase === 'recording' && 'recording']}
					aria-label={L('fld_hold')}
					aria-describedby="fld-hint"
					disabled={phase === 'reading'}
					data-testid="field-hold"
					onpointerdown={(e) => {
						(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
						void down(e);
					}}
					onpointerup={() => void up()}
					onpointercancel={() => void up()}
					onkeydown={(e) => key(e, true)}
					onkeyup={(e) => key(e, false)}
					oncontextmenu={(e) => e.preventDefault()}
				>
					{#if phase === 'reading'}<span class="spin" aria-hidden="true"></span>{:else}<Mic size={40} />{/if}
				</button>
				<p class="hold-label">
					{#if phase === 'recording'}<b class="rec-dot" aria-hidden="true"></b>{L('fld_release')} <span class="fig">{clock}</span>
					{:else if phase === 'reading'}{L('fld_transcribing')}
					{:else}{L('fld_hold')}{/if}
				</p>
				<p class="hint" id="fld-hint">{L('fld_hold_hint')}</p>
			</div>

			<div class="example" lang={spoken}>
				<span class="ex-k">{L('fld_example')}</span>
				<span class="ex-v">“{SPOKEN_EXAMPLES[spoken]}”</span>
			</div>

			<form class="typed" onsubmit={readText}>
				<label for="fld-text" class="or">{L('fld_or_type')}</label>
				<div class="row">
					<textarea id="fld-text" rows="2" maxlength="600" bind:value={text} placeholder={L('fld_text_ph')} aria-label={L('fld_text_label')} disabled={phase === 'reading'} data-testid="field-text"></textarea>
					<button type="submit" class="go" disabled={!text.trim() || phase === 'reading'} data-testid="field-text-go">{L('fld_text_go')}</button>
				</div>
			</form>
		{/if}

		{#if problem}<p class="problem" role="alert"><Glyph name="info" size={18} />{problem}</p>{/if}

		{#if report && phase === 'result'}
			<section class="result" aria-labelledby="fld-res" data-testid="field-result" data-verification={report.verification} data-kind={report.kind} data-severity={report.severity}>
				<div class="res-head">
					<h3 id="fld-res">{L('fld_res_title')}</h3>
					<span class="tag dashed" data-label="UNVERIFIED-FIELD" title={L('fld_not_action')}><Glyph name="unverified" size={15} />{L('fld_tag_unverified')}</span>
				</div>

				<div class="where">
					<div class="map">
						{#if overlay}
							<MapThumb class="map-thumb" {overlay} zoom={15} maxTiles={9} markerR={14} alt={L('fld_map_alt', place ? place.nameEn : '')} />
						{:else}
							<div class="map-none"><Glyph name="pin" size={28} /></div>
						{/if}
					</div>
					<div class="where-t">
						<span class="k">{L('fld_place')}</span>
						{#if place}
							<b class="pl" lang="mr">{place.nameMr}</b>
							<span class="pl-en">{place.nameEn}</span>
							<span class="meta">{L('fld_place_match', Math.round(place.score * 100), place.said)}</span>
						{:else}
							<span class="meta">{L('fld_place_none')}</span>
						{/if}
						{#if place?.chosen}<span class="meta">{L('fld_place_chosen')}</span>{/if}
						{#if report.candidates.length > (report.place ? 1 : 0)}
							<span class="k sm">{report.place ? L('fld_place_pick') : ''}</span>
							<div class="cands">
								{#each report.candidates.filter((c) => c.id !== place?.id) as c (c.id)}
									<button type="button" class="cand" onclick={() => (picked = c)} lang="mr">{c.nameMr}</button>
								{/each}
							</div>
						{/if}
						<select class="other" aria-label={L('fld_place_other')} value="" onchange={(e) => pickLandmark(e.currentTarget.value)} data-testid="field-place-other">
							<option value="">{L('fld_place_other')}</option>
							{#each landmarks as l (l.id)}<option value={l.id}>{lang === 'en' ? l.en : `${l.mr} · ${l.en}`}</option>{/each}
						</select>
					</div>
				</div>

				<div class="facts">
					<div class="fact">
						<span class="k">{L('fld_kind')}</span>
						<b>{L(`fld_kind_${report.kind}`)}</b>
					</div>
					<div class="fact">
						<span class="k">{L('fld_severity')}</span>
						<b class={['sev', `sev-${report.severity}`]}><i aria-hidden="true"></i><i aria-hidden="true"></i><i aria-hidden="true"></i>{L(`fld_sev_${report.severity}`)}</b>
					</div>
				</div>

				<div class="tx">
					<span class="k">{report.typed ? L('fld_typed') : L('fld_transcript')}</span>
					<p class="quote" lang={report.language}>
						{#each runs as r, i (i)}{#if r.cue}<mark>{r.text}</mark>{:else}{r.text}{/if}{/each}
					</p>
					{#if report.kindCues.length || report.severityCues.length}
						<p class="meta">{L('fld_cues')}: <span lang={report.language}>{[...report.kindCues, ...report.severityCues].join(' · ')}</span></p>
					{/if}
					{#if !report.typed && report.asrConfidence !== null}
						<p class="meta fig">{L('fld_asr', report.asrConfidence.toFixed(2), (report.audioSeconds ?? 0).toFixed(1))}</p>
					{/if}
				</div>

				<p class="rule"><Glyph name="shield" size={16} />{L('fld_not_action')}</p>

				{#if send.state === 'sent'}
					<div class="sent" role="status" data-testid="field-sent">
						<Glyph name="checkc" size={20} />
						<span>{L('fld_sent')}</span>
						<a href={`/o/event:${send.eventId}`} class="open">{L('fld_open')}</a>
					</div>
				{:else}
					<div class="acts">
						<button type="button" class="primary" disabled={!!blocked || send.state === 'sending'} title={blocked ?? L('fld_send')} onclick={() => void toBoard()} data-testid="field-send">
							<Glyph name="send" size={18} />{send.state === 'sending' ? L('fld_sending') : L('fld_send_board')}
						</button>
						<button type="button" class="ghost" onclick={reset}>{L('fld_discard')}</button>
					</div>
					<p class="meta why">{blocked ?? L('fld_send')}</p>
					{#if send.state === 'error'}<p class="problem" role="alert"><Glyph name="info" size={18} />{send.detail}</p>{/if}
				{/if}
				{#if send.state === 'sent'}<button type="button" class="ghost again" onclick={reset}><Mic size={18} />{L('fld_again')}</button>{/if}
			</section>
		{/if}

		<p class="privacy"><Glyph name="lock" size={16} />{L('fld_privacy')}</p>
		<p class="sr" aria-live="polite">{status}</p>
	</div>
</dialog>

<style>
	.sheet {
		overflow-y: auto;
		overscroll-behavior: contain;
		position: fixed;
		inset: 0 0 0 auto;
		width: min(520px, 100vw);
		max-width: 100vw;
		height: 100dvh;
		max-height: 100dvh;
		margin: 0;
		padding: 0;
		border: none;
		border-left: 1px solid var(--v3-line-2);
		background: var(--v3-s1);
		color: var(--v3-t1);
		box-shadow: var(--v3-elev-2);
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
	}

	.sheet[open] {
		animation: slide var(--v3-dur-3) var(--v3-ease);
	}

	.sheet::backdrop {
		background: var(--v3-scrim-soft);
	}

	@keyframes slide {
		from {
			transform: translateX(32px);
			opacity: 0;
		}
	}

	.inner {
		display: flex;
		flex-direction: column;
		gap: 18px;
		min-height: 100%;
		padding: 24px 28px 28px;
		box-sizing: border-box;
	}

	.head {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: start;
		gap: 14px;
	}

	.badge {
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		border-radius: 50%;
		background: var(--v3-brand-veil);
		color: var(--v3-brand-text);
	}

	h2 {
		margin: 2px 0 6px;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 650;
	}

	.lead {
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
		line-height: 20px;
	}

	.x {
		display: grid;
		place-items: center;
		width: var(--v3-ctl-lg);
		height: var(--v3-ctl-lg);
		border: none;
		border-radius: 50%;
		background: var(--v3-s2);
		color: var(--v3-t2);
		cursor: pointer;
	}

	.x:hover {
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.langs {
		display: inline-flex;
		align-self: flex-start;
		gap: 4px;
		padding: 4px;
		border: 1px solid var(--v3-line-2);
		border-radius: 24px;
		background: var(--v3-bg);
	}

	.lang {
		min-height: 36px;
		padding: 0 16px;
		border: none;
		border-radius: 18px;
		background: none;
		color: var(--v3-t2);
		font: inherit;
		font-size: 14px;
		font-weight: 600;
		cursor: pointer;
	}

	.lang.is-pressed {
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.lang:disabled {
		cursor: default;
		opacity: 0.6;
	}

	.stage {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		padding: 26px 16px 20px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-bg);
		overflow: hidden;
	}

	.wave {
		position: absolute;
		left: 0;
		right: 0;
		top: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 4px;
		height: 72px;
		pointer-events: none;
	}

	.wave i {
		display: block;
		width: 5px;
		border-radius: 3px;
		background: var(--v3-brand);
		transition: height 90ms linear;
	}

	.hold {
		position: relative;
		z-index: 1;
		display: grid;
		place-items: center;
		width: 112px;
		height: 112px;
		border: 1px solid var(--v3-line-3);
		border-radius: 50%;
		background: var(--v3-s2);
		color: var(--v3-t1);
		box-shadow: var(--v3-elev-1);
		cursor: pointer;
		touch-action: none;
		user-select: none;
		-webkit-user-select: none;
		transition:
			transform var(--v3-dur-2) var(--v3-ease),
			background var(--v3-dur-2) var(--v3-ease),
			box-shadow var(--v3-dur-2) var(--v3-ease);
	}

	.hold:hover:not(:disabled) {
		background: var(--v3-s3);
	}

	/* recording: the brand fill (not the system's grey .is-pressed — this is a live state, not a toggle) */
	.hold.recording,
	.hold.recording:hover:not(:disabled) {
		transform: scale(1.06);
		border-color: var(--v3-brand);
		background: var(--v3-brand);
		color: var(--v3-on-brand);
		box-shadow: 0 0 0 10px var(--v3-brand-veil), 0 0 0 22px var(--v3-ai-veil);
	}

	.hold:focus-visible,
	.x:focus-visible,
	.lang:focus-visible,
	.go:focus-visible,
	.primary:focus-visible,
	.ghost:focus-visible,
	.cand:focus-visible,
	.open:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 3px;
	}

	.hold:disabled {
		cursor: progress;
	}

	.spin {
		width: 34px;
		height: 34px;
		border: 3px solid var(--v3-line-3);
		border-top-color: var(--v3-brand);
		border-radius: 50%;
		animation: spin 0.9s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.hold-label {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		margin: 6px 0 0;
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 650;
	}

	.rec-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--v3-brand);
		animation: blink 1s ease-in-out infinite;
	}

	@keyframes blink {
		50% {
			opacity: 0.25;
		}
	}

	.fig {
		font-variant-numeric: tabular-nums;
	}

	.hint {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		text-align: center;
	}

	.example {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 10px;
		padding: 0 4px;
		font-size: 14px;
	}

	.ex-k {
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
	}

	.ex-v {
		color: var(--v3-t2);
	}

	.typed {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.or {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 700;
	}

	.row {
		display: flex;
		gap: 10px;
		align-items: stretch;
	}

	textarea {
		flex: 1;
		min-width: 0;
		min-height: 52px;
		padding: 12px 14px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: var(--v3-bg);
		color: var(--v3-t1);
		font: inherit;
		resize: vertical;
	}

	textarea:focus {
		outline: none;
		border-color: var(--v3-brand);
	}

	.go,
	.ghost {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		min-height: var(--v3-ctl-lg);
		padding: 0 18px;
		border: 1px solid var(--v3-line-3);
		border-radius: 22px;
		background: none;
		color: var(--v3-t1);
		font: inherit;
		font-weight: 650;
		white-space: nowrap;
		cursor: pointer;
	}

	.go:hover:not(:disabled),
	.ghost:hover {
		background: var(--v3-s3);
	}

	.go:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.problem {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		margin: 0;
		padding: 12px 14px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		color: var(--v3-t1);
		font-size: 14px;
	}

	.result {
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding: 18px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-l);
		background: var(--v3-bg);
		animation: rise var(--v3-dur-3) var(--v3-ease);
	}

	@keyframes rise {
		from {
			transform: translateY(8px);
			opacity: 0;
		}
	}

	.res-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		flex-wrap: wrap;
	}

	h3 {
		margin: 0;
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 650;
	}

	.tag {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 28px;
		padding: 0 12px;
		border-radius: 14px;
		font-size: var(--v3-text-meta);
		font-weight: 650;
		white-space: nowrap;
	}

	.tag.dashed {
		border: 1px dashed var(--v3-dashed);
		color: var(--v3-t2);
	}

	.where {
		display: grid;
		grid-template-columns: 196px minmax(0, 1fr);
		gap: 16px;
		align-items: start;
	}

	.map {
		position: relative;
		height: 164px;
		overflow: hidden;
		border-radius: var(--v3-radius-m);
		background: var(--v3-map-bg);
	}

	.map :global(.map-thumb) {
		position: absolute;
		inset: 0;
	}

	.map-none {
		display: grid;
		place-items: center;
		height: 100%;
		color: var(--v3-t3);
	}

	.where-t,
	.tx {
		display: flex;
		flex-direction: column;
		gap: 3px;
		min-width: 0;
	}

	.k {
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		font-weight: 650;
	}

	.k.sm {
		margin-top: 8px;
	}

	.pl {
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 650;
	}

	.pl-en {
		color: var(--v3-t2);
		font-size: 14px;
	}

	.meta {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.cands {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 4px;
	}

	.cand {
		min-height: 32px;
		padding: 0 12px;
		border: 1px solid var(--v3-line-2);
		border-radius: 16px;
		background: var(--v3-s2);
		color: var(--v3-t1);
		font: inherit;
		font-size: 13px;
		cursor: pointer;
	}

	.cand:hover {
		border-color: var(--v3-brand);
	}

	.other {
		max-width: 100%;
		min-height: 34px;
		margin-top: 6px;
		padding: 0 10px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-s);
		background: var(--v3-s2);
		color: var(--v3-t2);
		font: inherit;
		font-size: 13px;
	}

	.other:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.facts {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 10px;
	}

	.fact {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 12px 14px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.fact b {
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 650;
	}

	.sev {
		display: inline-flex;
		align-items: center;
		gap: 3px;
	}

	.sev i {
		display: inline-block;
		width: 6px;
		height: 14px;
		margin-right: 1px;
		border-radius: 2px;
		background: var(--v3-s4);
	}

	.sev i:last-of-type {
		margin-right: 8px;
	}

	.sev-low i:nth-of-type(1),
	.sev-medium i:nth-of-type(-n + 2),
	.sev-high i {
		background: var(--v3-t1);
	}

	.quote {
		margin: 2px 0 4px;
		padding: 12px 14px;
		border-left: 3px solid var(--v3-brand);
		border-radius: 0 var(--v3-radius-s) var(--v3-radius-s) 0;
		background: var(--v3-s2);
		font-size: var(--v3-text-sub);
		line-height: 28px;
	}

	mark {
		padding: 0 2px;
		border-radius: 4px;
		background: var(--v3-brand-veil);
		color: var(--v3-t1);
	}

	.rule,
	.privacy {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.rule :global(.v3-glyph),
	.privacy :global(.v3-glyph),
	.problem :global(.v3-glyph) {
		flex: none;
		margin-top: 1px;
		color: var(--v3-t3);
	}

	.privacy {
		margin-top: auto;
		padding-top: 6px;
	}

	.acts {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}

	.primary {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		flex: 1;
		min-height: var(--v3-ctl-xl);
		padding: 0 20px;
		border: none;
		border-radius: 28px;
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}

	.primary:hover:not(:disabled) {
		background: var(--v3-primary-hover);
	}

	.primary:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.why {
		margin-top: -6px;
	}

	.sent {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 14px 16px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-ok-veil);
		color: var(--v3-ok-text);
		font-weight: 650;
	}

	.sent span {
		flex: 1;
	}

	.open {
		color: var(--v3-t1);
		font-weight: 700;
	}

	.again {
		align-self: flex-start;
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	@media (max-width: 560px) {
		.inner {
			padding: 18px 16px 22px;
		}

		.where {
			grid-template-columns: minmax(0, 1fr);
		}

		.row {
			flex-direction: column;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.sheet[open],
		.result,
		.rec-dot,
		.spin {
			animation: none;
		}

		.hold,
		.wave i {
			transition: none;
		}
	}
</style>
