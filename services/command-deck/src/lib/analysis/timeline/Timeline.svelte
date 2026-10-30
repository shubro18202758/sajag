<script lang="ts" module>
	import type { ReplayTape } from '$lib/gods-eye/hud/replay.svelte';

	/** The replay mode's binding (the existing `replay` store): a tape on its own axis, in tape seconds. */
	export interface ReplayBinding {
		tape: ReplayTape;
		cursorSec: number;
		setCursor(sec: number): void;
	}

	/** An event's span in the Events lane (the event history). */
	export interface TimelineSpan {
		urn: string;
		title: string;
		start: number;
		end: number | null;
	}
</script>

<script lang="ts">
	/**
	 * Timeline (SPEC §5.3 "Timeline [S4]") — the city feed over a range, as a
	 * histogram and seven lanes, brushable.
	 *
	 *   compact  a 44 px histogram, the axis, "Rows in view n" and "Linked n"
	 *   full     a 40 px histogram, seven 19 px lanes with counts in a 136 px
	 *            gutter, the axis, and the key (one line, bottom right)
	 *
	 * Live semantics are exact: Live ⇔ no window. A drag on the histogram (or
	 * a Shift-drag anywhere) calls onbrush(a, b) — the caller's
	 * workspace.setTimeWindow, which turns Live off; the cursor is "Now hh:mm"
	 * at the right edge while live. The window's outside is shaded, its edges
	 * are 1 px ink-1 lines with neutral grips (surface-4, ew-resize) that
	 * move one edge; the shade, edges and grips never take the data's colour.
	 *
	 * Ticks are 2 × 9 px (an officer's action 15 px): grey; blue, 3 px and on
	 * top, when linked to the selection; red for a watchlist read; orange for
	 * an enforcement row whose decision waits; band changes neutral. An
	 * open-source report rides the Events lane as the compact provenance glyph
	 * (the globe, IN PLACE of its tick, in the tick's colour) with
	 * ProvenanceTag's semantics: data-source="osint", data-verification (the
	 * raw state) and its X2 label as hidden text; its tooltip ends in that
	 * label ("News-reported"). Event spans (the event history) sit under the
	 * Events lane's ticks.
	 *
	 * Replay: with `replay` the axis is TAPE time (t+mm:ss, never IST), the
	 * marks are the tape's, and a press or drag moves the replay cursor.
	 *
	 * SVG up to 2,500 lane marks; Canvas2D beyond (SPEC §13.1).
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.analysis';
	import { Button, Icon } from '$lib/ui';
	import { fmtRange, fmtStamp, fmtTime } from '$lib/ui/format/format';
	import { cssVar } from '$lib/gods-eye/theme';
	import type { FeedRow } from '$lib/gods-eye/city-api';
	import { maskMarks } from '$lib/workspace/mask';
	import { osintVerification, rowTipParts, type OsintVerification } from './tip';
	import { selectors } from '$lib/workspace/world.svelte';
	import { axisTicks, binRows, binSpan, tapeLabel, tapeTicks, type AxisTick } from './bins';
	import { brushWindow, hitWindow, moveEdge, tOf, xOf, type Scale } from './brush';
	import { LANE_IDS, LANE_KEY, isOfficerAction, isOsint, laneOf, toneOf, type LaneId, type TickTone } from './lanes';

	interface Props {
		start: number;
		end: number;
		window: [number, number] | null;
		live: boolean;
		cursor: number;
		related: ReadonlySet<string>;
		density: 'compact' | 'full';
		onbrush(a: number, b: number): void;
		oncursor(t: number): void;
		replay?: ReplayBinding;
		/** The rows to draw (default: the live world's feed in [start, end], selectors.feedIn). */
		rows?: readonly FeedRow[];
		/** Event spans for the Events lane (the event history). */
		spans?: readonly TimelineSpan[];
		/** Rows older than this were never loaded (a capped feed): the range before it is marked. */
		olderBefore?: number | null;
		/** A tick was clicked: its row's primary object. */
		onpick?: (urn: string) => void;
		lang?: string;
		/** Draw the lane key (full density). */
		showKey?: boolean;
		/** "Fit to the data" (offered when the range holds no row but the feed does). */
		onfit?: () => void;
		/** The newest loaded row (the empty range's hint says how old it is). */
		newest?: number | null;
	}

	let {
		start,
		end,
		window: win,
		live,
		cursor,
		related,
		density,
		onbrush,
		oncursor,
		replay,
		rows,
		spans = [],
		olderBefore = null,
		onpick,
		lang = 'en',
		showKey = true,
		onfit,
		newest = null,
	}: Props = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	/** Lane marks drawn as SVG up to this many; Canvas2D beyond. */
	const CANVAS_OVER = 2500;
	const GUTTER = 136;
	const RIGHT = 16;

	let W = $state(800);
	let H = $state(124);

	// ── geometry ──────────────────────────────────────────────────────────
	//   full: a 40 px histogram, seven 19 px lanes, the axis and the key (242 px of body, the frame's full dock).
	//   A shorter host (today's City Command glass rail) first drops the key, then shortens the histogram
	//   down to 20 px, keeping lanes of at least 13 px; below that the timeline draws compact.
	const AXIS_H = 24;
	const KEY_H = 18;
	const MIN_LANE = 13;
	const histTop = 8;
	const fits = (hist: number, key: number) => Math.floor((H - (histTop + hist + 8) - AXIS_H - key) / LANE_IDS.length);
	const geo = $derived.by(() => {
		// compact: the 44 px histogram of the 124 px dock; a taller host gets a taller histogram (up to 96 px)
		if (density !== 'full') return { full: false, histH: H <= 100 ? 44 : Math.min(96, H - histTop - 30), key: false };
		if (fits(40, showKey ? KEY_H : 0) >= MIN_LANE) return { full: true, histH: 40, key: showKey };
		if (fits(40, 0) >= MIN_LANE) return { full: true, histH: 40, key: false };
		const histH = H - histTop - 8 - AXIS_H - LANE_IDS.length * MIN_LANE;
		if (histH >= 20) return { full: true, histH: Math.min(40, histH), key: false };
		return { full: false, histH: Math.max(44, Math.min(96, H - histTop - 30)), key: false };
	});
	const full = $derived(geo.full);
	const histH = $derived(geo.histH);
	const laneTop = $derived(histTop + histH + 8);
	const keyH = $derived(geo.key ? KEY_H : 0);
	const laneH = $derived(full ? Math.max(MIN_LANE, Math.min(19, fits(histH, keyH))) : 0);
	const axisY = $derived(full ? laneTop + LANE_IDS.length * laneH + 2 : histTop + histH + 2);
	const x0 = GUTTER;
	const x1 = $derived(Math.max(GUTTER + 40, W - RIGHT));

	// ── the domain: IST ms, or tape seconds in replay ────────────────────
	const tape = $derived(replay?.tape ?? null);
	const dStart = $derived(tape ? 0 : start);
	const dEnd = $derived(tape ? Math.max(1, tape.durationSec) : end);
	const scale = $derived<Scale>({ start: dStart, end: dEnd, x0, x1 });
	const X = (v: number) => xOf(scale, v);

	interface Mark {
		id: string;
		t: number;
		lane: LaneId;
		tone: TickTone;
		tall: boolean;
		osint: boolean;
		/** An open-source row's verification state (null: none yet, or not open-source). */
		verification: OsintVerification | null;
		urn: string | null;
		tip: string;
		/** The open-source row's X2 label (drawn apart from the sentence, never ellipsised). */
		label: string | null;
	}

	/** The rows in view (live mode). */
	const inView = $derived.by(() => {
		if (tape) return [] as FeedRow[];
		const list = rows ?? selectors.feedIn(start, end);
		// one row per id: a repeated row (two sources merged) is drawn once, never as a duplicate key
		const seen = new Set<string>();
		return list.filter((r) => {
			if (r.t < start || r.t > end || seen.has(r.id)) return false;
			seen.add(r.id);
			return true;
		});
	});


	const marks = $derived.by((): Mark[] => {
		if (tape) {
			// tape marks have no row id: two reads of one mark in one second are two marks, so a repeated key gets a suffix
			const out: Mark[] = [];
			const used = new Map<string, number>();
			const key = (k: string) => {
				const n = used.get(k) ?? 0;
				used.set(k, n + 1);
				return n ? `${k}~${n}` : k;
			};
			for (const a of tape.anpr)
				out.push({ id: key(`a${a.t}-${a.plate}`), t: a.t, lane: 'anpr', tone: a.hit ? 'watch' : 'neutral', tall: false, osint: false, verification: null, urn: null, tip: maskMarks(`${tapeLabel(a.t)} · ${a.cameraId ?? 'ANPR'} ${a.hit ? `· ${a.hit.replace(/_/g, ' ')}` : ''}`), label: null });
			for (const n of tape.narrative) {
				if (n.kind === 'anpr') continue;
				out.push({ id: key(`n${n.frame}-${n.kind}-${n.t}`), t: n.t, lane: n.kind === 'unit' ? 'dispatch' : 'event', tone: n.severity === 'critical' ? 'watch' : 'neutral', tall: false, osint: false, verification: null, urn: null, tip: maskMarks(`${tapeLabel(n.t)} · ${n.text}`).slice(0, 160), label: null });
			}
			return out;
		}
		const out: Mark[] = [];
		for (const r of inView) {
			const lane = laneOf(r);
			if (!lane) continue;
			const os = isOsint(r);
			const tp = rowTipParts(r, end, lang);
			out.push({ id: r.id, t: r.t, lane, tone: toneOf(r, related), tall: isOfficerAction(r), osint: os, verification: os ? osintVerification(r.verificationState) : null, urn: r.urns[0] ?? null, tip: tp.text, label: tp.label });
		}
		return out;
	});

	const counts = $derived.by(() => {
		const c = Object.fromEntries(LANE_IDS.map((l) => [l, 0])) as Record<LaneId, number>;
		for (const m of marks) c[m.lane]++;
		return c;
	});

	const hist = $derived(tape ? binRows(marks.map((m) => ({ t: m.t, urns: [] })), dStart, dEnd, null) : binRows(inView, start, end, related));
	const ticks = $derived<AxisTick[]>(tape ? tapeTicks(tape.durationSec, x1 - x0) : axisTicks(start, end, x1 - x0));
	const useCanvas = $derived(full && marks.length > CANVAS_OVER);
	const linkedCount = $derived(hist.linkedTotal);

	/** Event spans in range, clipped. */
	const spanBars = $derived.by(() => {
		if (tape || !full) return [];
		const seen = new Set<string>();
		return spans
			.filter((s) => {
				if ((s.end ?? end) < start || s.start > end || seen.has(s.urn)) return false;
				seen.add(s.urn);
				return true;
			})
			.map((s) => {
				const a = Math.max(start, s.start);
				const b = Math.min(end, s.end ?? end);
				return { s, xa: X(a), xb: Math.max(X(a) + 2, X(b)), linked: related.has(s.urn) };
			});
	});

	// ── the canvas lanes (beyond 2,500 marks) ─────────────────────────────
	let canvasEl: HTMLCanvasElement | null = $state(null);
	$effect(() => {
		if (!useCanvas || !canvasEl) return;
		const dpr = typeof devicePixelRatio === 'number' ? devicePixelRatio : 1;
		const cw = x1 - x0 + 4;
		const ch = LANE_IDS.length * laneH;
		canvasEl.width = Math.round(cw * dpr);
		canvasEl.height = Math.round(ch * dpr);
		const g = canvasEl.getContext('2d');
		if (!g) return;
		g.setTransform(dpr, 0, 0, dpr, 0, 0);
		g.clearRect(0, 0, cw, ch);
		const ink = cssVar('--v-ink-2') ?? 'gray';
		const fill: Record<TickTone, string> = {
			neutral: ink,
			watch: cssVar('--v-map-alert') ?? 'red',
			decision: cssVar('--v-map-decision') ?? 'orange',
			linked: cssVar('--v-map-select') ?? 'blue',
		};
		for (const pass of ['back', 'front'] as const) {
			for (const m of marks) {
				if (m.osint || (m.tone === 'linked') !== (pass === 'front')) continue;
				const li = LANE_IDS.indexOf(m.lane);
				const x = X(m.t) - x0 + 2;
				const y = li * laneH;
				const inWin = !win || (m.t >= win[0] && m.t <= win[1]);
				g.globalAlpha = m.tone === 'neutral' ? (inWin ? 0.7 : 0.3) : inWin ? 1 : 0.4;
				g.fillStyle = fill[m.tone];
				if (m.tone === 'linked') g.fillRect(x - 1.5, y + 2, 3, laneH - 4);
				else g.fillRect(x - 1, y + (m.tall ? 2 : (laneH - 9) / 2), 2, m.tall ? laneH - 4 : 9);
			}
		}
		g.globalAlpha = 1;
	});

	// ── interaction: brush, grips, scrub, hover ──────────────────────────
	let svgEl: SVGSVGElement | null = $state(null);
	type Drag = { mode: 'brush'; xa: number; xb: number } | { mode: 'edge'; edge: 'start' | 'end' } | { mode: 'scrub' };
	let drag = $state<Drag | null>(null);
	let tip = $state<{ x: number; y: number; text: string; label?: string | null } | null>(null);

	function localX(e: PointerEvent): { x: number; y: number } {
		const r = svgEl?.getBoundingClientRect();
		return r ? { x: e.clientX - r.left, y: e.clientY - r.top } : { x: 0, y: 0 };
	}

	const inHist = (y: number) => y >= histTop - 4 && y <= histTop + histH + 4;

	function onDown(e: PointerEvent) {
		if (e.button !== 0) return;
		const { x, y } = localX(e);
		if (x < x0 - 4) return;
		(e.currentTarget as Element).setPointerCapture?.(e.pointerId);
		if (tape) {
			drag = { mode: 'scrub' };
			oncursor(tOf(scale, x));
			return;
		}
		const hitW = hitWindow(scale, win, x);
		if ((hitW === 'start' || hitW === 'end') && y <= axisY) {
			drag = { mode: 'edge', edge: hitW };
			return;
		}
		if (inHist(y) || e.shiftKey) drag = { mode: 'brush', xa: x, xb: x };
	}

	function onMove(e: PointerEvent) {
		const { x, y } = localX(e);
		if (drag?.mode === 'brush') {
			drag = { ...drag, xb: x };
			tip = null;
			return;
		}
		if (drag?.mode === 'edge' && win) {
			const w = moveEdge(win, drag.edge, tOf(scale, x));
			onbrush(w[0], w[1]);
			return;
		}
		if (drag?.mode === 'scrub') {
			oncursor(tOf(scale, x));
			return;
		}
		tip = hoverTip(x, y);
	}

	function onUp(e: PointerEvent) {
		const d = drag;
		drag = null;
		if (!d || d.mode !== 'brush') return;
		const { x, y } = localX(e);
		const w = brushWindow(scale, d.xa, x);
		if (w) {
			onbrush(w[0], w[1]);
			return;
		}
		// a click: on a lane, the nearest tick's object; on the histogram, the cursor
		const m = !inHist(y) ? markAt(x, y) : null;
		if (m?.urn && onpick) onpick(m.urn);
		else oncursor(tOf(scale, x));
	}

	function onClickLane(e: MouseEvent) {
		if (tape || drag) return;
		const r = svgEl?.getBoundingClientRect();
		if (!r) return;
		const x = e.clientX - r.left;
		const y = e.clientY - r.top;
		if (inHist(y) || e.shiftKey) return;
		const m = markAt(x, y);
		if (m?.urn && onpick) onpick(m.urn);
	}

	/** Arrows move the cursor one histogram bin (Shift: ten); the cursor is "Now" while live. */
	function onKey(e: KeyboardEvent) {
		if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
		if (!tape && live) return;
		e.preventDefault();
		const step = ((dEnd - dStart) / hist.bins) * (e.shiftKey ? 10 : 1) * (e.key === 'ArrowLeft' ? -1 : 1);
		oncursor(Math.max(dStart, Math.min(dEnd, cursorV + step)));
	}

	function laneAt(y: number): LaneId | null {
		if (!full || y < laneTop || y >= laneTop + LANE_IDS.length * laneH) return null;
		return LANE_IDS[Math.floor((y - laneTop) / laneH)] ?? null;
	}

	function markAt(x: number, y: number): Mark | null {
		const lane = laneAt(y);
		if (!lane) return null;
		let best: Mark | null = null;
		let bd = 5;
		for (const m of marks) {
			if (m.lane !== lane) continue;
			const d = Math.abs(X(m.t) - x);
			if (d < bd || (d === bd && best && m.tone === 'linked')) {
				bd = d;
				best = m;
			}
		}
		return best;
	}

	function hoverTip(x: number, y: number): { x: number; y: number; text: string; label?: string | null } | null {
		if (x < x0 || x > x1) return null;
		if (!tape && win && (hitWindow(scale, win, x) === 'start' || hitWindow(scale, win, x) === 'end') && y <= axisY) return { x, y, text: L('an_tl_grip') };
		if (inHist(y)) {
			const i = Math.min(hist.bins - 1, Math.max(0, Math.floor(((tOf(scale, x) - dStart) / (dEnd - dStart)) * hist.bins)));
			const c = hist.all[i];
			if (!c) return { x, y, text: tape ? '' : L('an_tl_brush_hint') };
			const [a, b] = binSpan(hist, i);
			if (tape) return { x, y, text: `${c} · ${tapeLabel(a)}–${tapeLabel(b)}` };
			const linked = hist.linked[i] ? ` · ${L('an_tl_bin_linked', hist.linked[i])}` : '';
			return { x, y, text: `${L('an_tl_bin_tip', c, fmtRange(a, b, end))}${linked}` };
		}
		const m = markAt(x, y);
		if (m) return { x, y, text: m.tip, label: m.label };
		const lane = laneAt(y);
		if (lane === 'event') {
			const tAt = tOf(scale, x);
			const sp = spanBars.find((s) => tAt >= s.s.start && tAt <= (s.s.end ?? end));
			if (sp) return { x, y, text: L('an_tl_span', maskMarks(sp.s.title), fmtRange(sp.s.start, sp.s.end ?? end, end)) };
		}
		return null;
	}

	// ── drawn values ──────────────────────────────────────────────────────
	const bw = $derived((x1 - x0) / hist.bins);
	const inWin = (v: number) => !win || (v >= win[0] && v <= win[1]);
	const binMid = (i: number) => dStart + ((i + 0.5) / hist.bins) * (dEnd - dStart);
	const winX = $derived(!tape && win ? [X(Math.max(dStart, win[0])), X(Math.min(dEnd, win[1]))] : null);
	const brushX = $derived(drag?.mode === 'brush' ? [Math.min(drag.xa, drag.xb), Math.max(drag.xa, drag.xb)] : null);
	const cursorV = $derived(tape ? (replay?.cursorSec ?? 0) : cursor);
	const cursorX = $derived(Math.max(x0, Math.min(x1, X(cursorV))));
	const cursorText = $derived(tape ? tapeLabel(cursorV) : live ? L('an_tl_now', fmtTime(cursorV)) : fmtStamp(cursorV, end, { seconds: true }));
	const cursorW = $derived(cursorText.length * 7 + 14);
	const tagX = $derived(Math.max(x0, Math.min(x1 - cursorW, cursorX - cursorW / 2)));
	const olderX = $derived(!tape && olderBefore != null && olderBefore > start ? Math.min(x1, X(olderBefore)) : null);
	// an open-source mark is drawn as its provenance glyph, in place of a tick
	const frontMarks = $derived(marks.filter((m) => m.tone === 'linked' && !m.osint));
	const backMarks = $derived(marks.filter((m) => m.tone !== 'linked' && !m.osint));
	const osintMarks = $derived(full ? marks.filter((m) => m.osint) : []);
	const OSINT_GLYPH = 12;
</script>

<div class="tl" class:full class:replay={!!tape} bind:clientWidth={W} bind:clientHeight={H} data-density={density} data-live={live} data-marks={marks.length} data-render={useCanvas ? 'canvas' : 'svg'}>
	<svg
		bind:this={svgEl}
		width={W}
		height={H}
		role="slider"
		tabindex="0"
		aria-label={L('an_tl_label')}
		aria-valuemin={dStart}
		aria-valuemax={dEnd}
		aria-valuenow={cursorV}
		aria-valuetext={cursorText}
		class:brushing={drag?.mode === 'brush'}
		onkeydown={onKey}
		onpointerdown={onDown}
		onpointermove={onMove}
		onpointerup={onUp}
		onpointerleave={() => (tip = null)}
		onclick={onClickLane}
	>
		<!-- gridlines at the axis ticks -->
		{#each ticks as tk (tk.t)}
			<line class="grid" class:major={tk.major} x1={X(tk.t)} x2={X(tk.t)} y1={histTop} y2={axisY} />
		{/each}

		<!-- the range before the oldest loaded row of a capped feed -->
		{#if olderX != null}
			<rect class="older" x={x0} y={histTop} width={Math.max(0, olderX - x0)} height={axisY - histTop} />
			{#if olderX - x0 > 140}<text class="older-t" x={x0 + 6} y={histTop + 14}>{L('an_tl_older')}</text>{/if}
		{/if}

		<!-- histogram: grey bars (lighter inside the window), linked rows in blue on top -->
		{#each hist.all as c, i (i)}
			{#if c}
				{@const h = Math.max(2, (c / hist.max) * histH)}
				<rect class="bar" class:inside={!!win && inWin(binMid(i))} x={x0 + i * bw + 0.5} y={histTop + histH - h} width={Math.max(1, bw - 1)} height={h} />
				{#if hist.linked[i]}
					{@const hr = Math.max(2, (hist.linked[i] / hist.max) * histH)}
					<rect class="bar rel" x={x0 + i * bw + 0.5} y={histTop + histH - hr} width={Math.max(1, bw - 1)} height={hr} />
				{/if}
			{/if}
		{/each}
		<line class="base" x1={x0} x2={x1} y1={histTop + histH + 0.5} y2={histTop + histH + 0.5} />

		<!-- the gutter -->
		<text class="g-l" x="16" y={histTop + 15}>{tape ? L('an_tl_tape_rows') : L('an_tl_rows_in_view')}</text>
		<text class="g-n" x={GUTTER - 12} y={histTop + 15}>{tape ? marks.length : inView.length}</text>
		{#if !full && !tape}
			<!-- compact always shows both lines (SPEC: "Rows in view n", "Linked n"); blue only when something is linked -->
			<text class="g-l" class:lk={!!linkedCount} x="16" y={histTop + 33}>{L('an_tl_linked')}</text>
			<text class="g-n" class:lk={!!linkedCount} class:zero={!linkedCount} x={GUTTER - 12} y={histTop + 33}>{linkedCount}</text>
		{/if}

		{#if full}
			{#each LANE_IDS as lane, li (lane)}
				{@const y = laneTop + li * laneH}
				<text class="g-l" x="16" y={y + laneH / 2 + 4}>{L(LANE_KEY[lane])}</text>
				<text class="g-n" class:zero={!counts[lane]} x={GUTTER - 12} y={y + laneH / 2 + 4}>{counts[lane]}</text>
				<line class="lane-sep" x1={x0} x2={x1} y1={y + laneH - 0.5} y2={y + laneH - 0.5} />
			{/each}
			<!-- event spans under the Events lane's ticks -->
			{#each spanBars as sb (sb.s.urn)}
				<rect class="span" class:lk={sb.linked} x={sb.xa} y={laneTop + laneH - 4} width={sb.xb - sb.xa} height="2" rx="1" />
			{/each}
			{#if !useCanvas}
				{#each backMarks as m (m.id)}
					<rect
						class="tick t-{m.tone}"
						class:out={!inWin(m.t)}
						x={X(m.t) - 1}
						y={laneTop + LANE_IDS.indexOf(m.lane) * laneH + (m.tall ? 2 : (laneH - 9) / 2)}
						width="2"
						height={m.tall ? laneH - 4 : 9}
					/>
				{/each}
				{#each frontMarks as m (m.id)}
					<rect class="tick t-linked" class:out={!inWin(m.t)} x={X(m.t) - 1.5} y={laneTop + LANE_IDS.indexOf(m.lane) * laneH + 2} width="3" height={laneH - 4} rx="1" />
				{/each}
			{/if}
			<!-- open-source reports: the compact provenance glyph in place of the tick (ProvenanceTag semantics, X2) -->
			{#each osintMarks as m (m.id)}
				{@const li = LANE_IDS.indexOf(m.lane)}
				<g
					class="osint t-{m.tone}"
					class:out={!inWin(m.t)}
					data-ui="provenance-tag"
					data-source="osint"
					data-verification={m.verification ?? undefined}
					transform="translate({X(m.t) - OSINT_GLYPH / 2},{laneTop + li * laneH + (laneH - OSINT_GLYPH) / 2})"
				>
					<title>{m.label}</title>
					<Icon name="globe" size={OSINT_GLYPH} />
				</g>
			{/each}
		{/if}

		<!-- the time window: shade outside, neutral edges, grips -->
		{#if winX}
			<rect class="shade" x={x0} y={histTop - 4} width={Math.max(0, winX[0] - x0)} height={axisY - histTop + 4} />
			<rect class="shade" x={winX[1]} y={histTop - 4} width={Math.max(0, x1 - winX[1])} height={axisY - histTop + 4} />
			{#each winX as bx, k (k)}
				<line class="edge" x1={bx} x2={bx} y1={histTop - 4} y2={axisY} />
				<g class="grip" transform="translate({bx - 5},{histTop + histH / 2 - 10})">
					<rect width="10" height="20" rx="3" />
					<line x1="3.5" x2="3.5" y1="6" y2="14" />
					<line x1="6.5" x2="6.5" y1="6" y2="14" />
				</g>
			{/each}
		{/if}
		{#if brushX && brushX[1] - brushX[0] >= 2}
			<rect class="brush" x={brushX[0]} y={histTop - 4} width={brushX[1] - brushX[0]} height={axisY - histTop + 4} />
		{/if}

		<!-- the axis -->
		{#if tape}<text class="g-l axis-name" x="16" y={axisY + 14}>{L('an_tl_tape')}</text>{/if}
		{#each ticks as tk (tk.t)}
			{@const lx = X(tk.t) + 4}
			{#if lx + tk.label.length * 6.6 < tagX - 4 || lx > tagX + cursorW + 4}
				<text class="ax" x={lx} y={axisY + 14}>{tk.label}</text>
			{/if}
		{/each}

		<!-- the cursor: "Now hh:mm" while live -->
		<line class="cursor" x1={cursorX} x2={cursorX} y1={histTop - 4} y2={axisY} />
		<g class="cursor-tag" transform="translate({tagX},{axisY + 1})">
			<rect width={cursorW} height="18" rx="3" />
			<text x={cursorW / 2} y="13">{cursorText}</text>
		</g>
	</svg>

	{#if useCanvas}
		<canvas bind:this={canvasEl} class="lanes-canvas" style:left="{x0 - 2}px" style:top="{laneTop}px" style:width="{x1 - x0 + 4}px" style:height="{LANE_IDS.length * laneH}px"></canvas>
	{/if}

	{#if full && geo.key && !tape}
		<div class="key" aria-hidden="true">
			<span><i class="k-officer"></i>{L('an_tl_key_officer')}</span>
			<span class="lk"><i class="k-linked"></i>{L('an_tl_key_linked')}</span>
			<span class="wt"><i></i>{L('an_tl_key_watch')}</span>
			<span class="dc"><i></i>{L('an_tl_key_decision')}</span>
			{#if osintMarks.length}<span class="os" data-osint-count={osintMarks.length}><Icon name="globe" size={12} />{L('an_tl_key_osint')} {osintMarks.length}</span>{/if}
		</div>
	{/if}

	{#if !tape && !inView.length}
		<div class="empty" style:left="{x0}px" style:width="{x1 - x0}px" style:top="{histTop}px" style:height="{Math.max(20, axisY - histTop)}px">
			<span>{newest != null && newest < start ? L('an_tl_empty_older', fmtStamp(newest, end)) : L('an_tl_empty')}</span>
			{#if onfit && newest != null && newest < start}<Button small minimal icon="zoom-to-fit" onclick={onfit}>{L('an_fit')}</Button>{/if}
		</div>
	{/if}

	{#if tip && tip.text}
		<div class="tip" role="tooltip" style:left="{Math.min(W - 260, Math.max(8, tip.x + 12))}px" style:top="{Math.max(2, tip.y - 30)}px">
			<span class="tip-t">{tip.text}</span>{#if tip.label}{' '}<span class="tip-l" data-tip-provenance>· {tip.label}</span>{/if}
		</div>
	{/if}
</div>

<style>
	.tl {
		position: relative;
		width: 100%;
		height: 100%;
		min-height: 0;
		overflow: hidden;
		user-select: none;
		font-size: 12px;
		font-variant-numeric: tabular-nums;
	}

	svg {
		display: block;
		cursor: crosshair;
		touch-action: none;
	}

	svg:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	svg.brushing {
		cursor: col-resize;
	}

	svg text {
		font-family: var(--v-font-ui);
		font-size: 12px;
		fill: var(--v-ink-2);
	}

	.grid {
		stroke: var(--v-line-1);
	}

	.grid.major {
		stroke: var(--v-line-2);
	}

	.older {
		fill: color-mix(in srgb, var(--v-surface-sink) 35%, transparent);
	}

	.older-t {
		fill: var(--v-ink-2);
	}

	.bar {
		fill: color-mix(in srgb, var(--v-ink-2) 42%, transparent);
	}

	.bar.inside {
		fill: color-mix(in srgb, var(--v-ink-2) 80%, transparent);
	}

	.bar.rel {
		fill: var(--v-map-select);
		pointer-events: none;
	}

	.base {
		stroke: var(--v-line-2);
	}

	.g-n {
		fill: var(--v-ink-1);
		text-anchor: end;
	}

	.g-n.zero {
		fill: var(--v-ink-2);
	}

	.g-l.lk,
	.g-n.lk {
		fill: var(--v-primary-text);
	}

	.lane-sep {
		stroke: var(--v-line-1);
	}

	.tick {
		fill: color-mix(in srgb, var(--v-ink-2) 70%, transparent);
	}

	.tick.t-watch {
		fill: var(--v-map-alert);
	}

	.tick.t-decision {
		fill: var(--v-map-decision);
	}

	.tick.t-linked {
		fill: var(--v-map-select);
	}

	.tick.out {
		opacity: 0.4;
	}

	/* an event's span: a quiet 2 px rail under the lane's ticks (blue at half strength when it is the selection's) */
	.span {
		fill: color-mix(in srgb, var(--v-ink-2) 30%, transparent);
	}

	.span.lk {
		fill: color-mix(in srgb, var(--v-map-select) 45%, transparent);
	}

	/* the open-source glyph takes its tick's colour role: neutral ink, blue when linked */
	.osint {
		color: var(--v-ink-1);
		pointer-events: none;
	}

	.osint.t-linked {
		color: var(--v-map-select);
	}

	.osint.out {
		opacity: 0.4;
	}

	/* the window: shade outside (rgba(17,20,24,.45) = surface-sink at 45 %), neutral edges and grips */
	.shade {
		fill: color-mix(in srgb, var(--v-surface-sink) 45%, transparent);
		pointer-events: none;
	}

	.edge {
		stroke: var(--v-ink-1);
		stroke-width: 1;
	}

	.grip {
		cursor: ew-resize;
	}

	.grip rect {
		fill: var(--v-surface-4);
		stroke: var(--v-line-strong);
	}

	.grip line {
		stroke: var(--v-ink-2);
	}

	.brush {
		fill: var(--v-primary-veil);
		stroke: var(--v-primary-text);
		stroke-dasharray: 3 2;
		pointer-events: none;
	}

	.ax {
		fill: var(--v-ink-2);
	}

	.axis-name {
		fill: var(--v-ink-1);
	}

	.cursor {
		stroke: var(--v-map-select);
		stroke-width: 1.5;
		pointer-events: none;
	}

	.cursor-tag rect {
		fill: var(--v-primary);
	}

	.cursor-tag text {
		fill: var(--v-on-fill);
		text-anchor: middle;
		font-weight: 600;
	}

	.replay .cursor {
		stroke: var(--v-ink-1);
	}

	.replay .cursor-tag rect {
		fill: var(--v-surface-4);
	}

	.lanes-canvas {
		position: absolute;
		pointer-events: none;
	}

	.key {
		position: absolute;
		right: 16px;
		bottom: 2px;
		display: flex;
		gap: 16px;
		align-items: center;
		font-size: 12px;
		line-height: 16px;
		color: var(--v-ink-2);
		white-space: nowrap;
		pointer-events: none;
	}

	.key span {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.key i {
		display: inline-block;
		width: 2px;
		height: 9px;
		background: currentColor;
	}

	.key i.k-officer {
		height: 13px;
		background: var(--v-ink-2);
	}

	.key .lk {
		color: var(--v-primary-text);
	}

	.key i.k-linked {
		width: 3px;
	}

	.key .wt {
		color: var(--v-danger-text);
	}

	.key .wt i {
		background: var(--v-map-alert);
	}

	.key .dc {
		color: var(--v-warning-text);
	}

	.key .dc i {
		background: var(--v-map-decision);
	}

	.empty {
		position: absolute;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		color: var(--v-ink-2);
		font-size: 12px;
		pointer-events: none;
	}

	.empty :global(button) {
		pointer-events: auto;
	}

	.tip {
		position: absolute;
		z-index: 2;
		display: flex;
		gap: 4px;
		max-width: 360px;
		padding: 4px 8px;
		border-radius: var(--v-radius-chip);
		background: var(--v-tooltip-bg);
		color: var(--v-tooltip-ink);
		font-size: 12px;
		line-height: 16px;
		white-space: nowrap;
		pointer-events: none;
		box-shadow: var(--v-elev-2);
	}

	/* the sentence is ellipsised; the open-source label after it never is */
	.tip-t {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.tip-l {
		flex: 0 0 auto;
	}
</style>
