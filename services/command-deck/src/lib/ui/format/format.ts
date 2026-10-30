/**
 * THE formatter (SPEC §3.3) — every view formats times, ranges, ages,
 * durations, identifiers and coordinates through these helpers and the five
 * components beside them (Id, Plate, Time, TimeRange, Coord).
 *
 * - The control room runs on India Standard Time whatever the browser's own
 *   zone is: every helper pins timeZone Asia/Kolkata, 24-hour.
 * - Monospace is for identifiers and coordinates only (registration marks,
 *   camera, junction, unit and recommendation ids, URNs), at max(12px, .9em).
 *   Times, durations, counts, speeds and percentages are Inter with tabular
 *   figures. The style lint allows the mono face only inside this folder.
 * - One format per column: colStamp() gives hh:mm (or hh:mm:ss) when every
 *   value falls on the anchor's IST day, otherwise "23 Oct 23:52" for every
 *   row. Ranges use one precision: "01:20–01:42" or "23 Oct 23:52–00:04".
 *
 * Pure functions; the components render them. Unparseable input renders
 * '—' (never "Invalid Date", never a throw).
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.ui';

export const IST_ZONE = 'Asia/Kolkata';
const DASH = '—';

/** A moment: epoch milliseconds, an ISO 8601 string or a Date. */
export type Moment = number | string | Date | null | undefined;

const hmFmt = new Intl.DateTimeFormat('en-GB', {
	timeZone: IST_ZONE,
	hour: '2-digit',
	minute: '2-digit',
	hourCycle: 'h23'
});
const hmsFmt = new Intl.DateTimeFormat('en-GB', {
	timeZone: IST_ZONE,
	hour: '2-digit',
	minute: '2-digit',
	second: '2-digit',
	hourCycle: 'h23'
});
const dayFmt = new Intl.DateTimeFormat('en-GB', { timeZone: IST_ZONE, day: 'numeric', month: 'short' });
const ymdFmt = new Intl.DateTimeFormat('en-CA', {
	timeZone: IST_ZONE,
	year: 'numeric',
	month: '2-digit',
	day: '2-digit'
});

/** Epoch ms of a moment; NaN when it does not parse. Numbers are epoch ms. */
export function toMs(v: Moment): number {
	if (v instanceof Date) return v.getTime();
	if (typeof v === 'number') return Number.isFinite(v) ? v : NaN;
	if (typeof v === 'string' && v.trim()) return Date.parse(v);
	return NaN;
}

/** The IST calendar day of a moment as YYYY-MM-DD ('' when unparseable). */
export function istDay(v: Moment): string {
	const ms = toMs(v);
	return Number.isFinite(ms) ? ymdFmt.format(ms) : '';
}

/** "23 Oct" in IST ('—' when unparseable). */
export function fmtDay(v: Moment): string {
	const ms = toMs(v);
	return Number.isFinite(ms) ? dayFmt.format(ms) : DASH;
}

/** hh:mm (or hh:mm:ss) in IST, 24-hour. */
export function fmtTime(v: Moment, opts: { seconds?: boolean } = {}): string {
	const ms = toMs(v);
	if (!Number.isFinite(ms)) return DASH;
	return (opts.seconds ? hmsFmt : hmFmt).format(ms);
}

/**
 * A stamp against an anchor (usually now): hh:mm on the anchor's IST day,
 * else "23 Oct 23:52". With seconds, the same-day form is hh:mm:ss (the
 * dated form keeps minutes: one precision per column is colStamp's job).
 */
export function fmtStamp(v: Moment, anchor: Moment = Date.now(), opts: { seconds?: boolean } = {}): string {
	const ms = toMs(v);
	if (!Number.isFinite(ms)) return DASH;
	if (istDay(ms) === istDay(anchor)) return fmtTime(ms, opts);
	return `${dayFmt.format(ms)} ${hmFmt.format(ms)}`;
}

/** A range shorter than this keeps its right end undated across midnight. */
const SHORT_RANGE_MS = 12 * 3_600_000;

/**
 * A range at one precision: "01:20–01:42" when both ends fall on the
 * anchor's IST day, else "23 Oct 23:52–00:04". An open range is one stamp.
 *
 * The right end carries its own date when it falls on another IST day than
 * the left end AND the range lasts 12 h or more ("22 Oct 10:00–23 Oct
 * 09:00"), so a long window never reads as ending before it starts. A short
 * window past midnight keeps SPEC §3.3's compact form ("23 Oct 23:52–00:04"):
 * under half a day, an earlier clock time can only be the next morning.
 */
export function fmtRange(a: Moment, b: Moment, anchor: Moment = Date.now()): string {
	const msA = toMs(a);
	const msB = toMs(b);
	if (!Number.isFinite(msA)) return DASH;
	if (!Number.isFinite(msB)) return fmtStamp(msA, anchor);
	const dayAnchor = istDay(anchor);
	const left =
		istDay(msA) === dayAnchor && istDay(msB) === dayAnchor
			? hmFmt.format(msA)
			: `${dayFmt.format(msA)} ${hmFmt.format(msA)}`;
	const datedRight = istDay(msB) !== istDay(msA) && Math.abs(msB - msA) >= SHORT_RANGE_MS;
	const right = datedRight ? `${dayFmt.format(msB)} ${hmFmt.format(msB)}` : hmFmt.format(msB);
	return `${left}–${right}`;
}

/**
 * One format for a whole column: hh:mm (hh:mm:ss with seconds) when every
 * value falls on the anchor's IST day, else "23 Oct 23:52" for every row.
 * Unparseable values render '—' and do not change the column's format.
 */
export function colStamp(list: readonly Moment[], anchor: Moment = Date.now(), opts: { seconds?: boolean } = {}): string[] {
	const ms = list.map(toMs);
	const dayAnchor = istDay(anchor);
	const sameDay = ms.every((m) => !Number.isFinite(m) || istDay(m) === dayAnchor);
	return ms.map((m) => {
		if (!Number.isFinite(m)) return DASH;
		return sameDay ? fmtTime(m, opts) : `${dayFmt.format(m)} ${hmFmt.format(m)}`;
	});
}

/** Compact duration: "45 s", "12 min", "1 h 40 min", "2 d 3 h" (units in `lang`). */
export function fmtDuration(sec: number | null | undefined, lang = 'en'): string {
	if (sec == null || !Number.isFinite(sec)) return DASH;
	const s = Math.max(0, Math.round(sec));
	const u = (k: 'ui_unit_s' | 'ui_unit_min' | 'ui_unit_h' | 'ui_unit_d') => t(lang, k);
	if (s < 60) return `${s} ${u('ui_unit_s')}`;
	const m = Math.floor(s / 60);
	if (m < 60) return `${m} ${u('ui_unit_min')}`;
	const h = Math.floor(m / 60);
	if (h < 24) return m % 60 ? `${h} ${u('ui_unit_h')} ${m % 60} ${u('ui_unit_min')}` : `${h} ${u('ui_unit_h')}`;
	const d = Math.floor(h / 24);
	return h % 24 ? `${d} ${u('ui_unit_d')} ${h % 24} ${u('ui_unit_h')}` : `${d} ${u('ui_unit_d')}`;
}

/** Relative age: "12 s ago", "1 h 40 min ago"; a future moment reads "in 5 min". */
export function fmtAgo(v: Moment, now: Moment = Date.now(), lang = 'en'): string {
	const ms = toMs(v);
	const n = toMs(now);
	if (!Number.isFinite(ms) || !Number.isFinite(n)) return DASH;
	const diff = (n - ms) / 1000;
	if (Math.abs(diff) < 1) return t(lang, 'ui_now');
	const span = fmtDuration(Math.abs(diff), lang);
	return diff >= 0 ? t(lang, 'ui_ago', span) : t(lang, 'ui_in', span);
}

/** A countdown "m:ss" (a decision's time left); negative clamps to 0:00. */
export function fmtCountdown(sec: number | null | undefined): string {
	if (sec == null || !Number.isFinite(sec)) return DASH;
	const s = Math.max(0, Math.round(sec));
	const h = Math.floor(s / 3600);
	const m = Math.floor((s % 3600) / 60);
	const r = String(s % 60).padStart(2, '0');
	return h ? `${h}:${String(m).padStart(2, '0')}:${r}` : `${m}:${r}`;
}

/** The full IST stamp for tooltips and ISO attributes: "23 Oct 2026, 23:52:04 IST". */
export function fmtFull(v: Moment): string {
	const ms = toMs(v);
	if (!Number.isFinite(ms)) return DASH;
	const date = new Intl.DateTimeFormat('en-GB', {
		timeZone: IST_ZONE,
		day: 'numeric',
		month: 'short',
		year: 'numeric'
	}).format(ms);
	return `${date}, ${hmsFmt.format(ms)} IST`;
}

// ── registration marks (defence in depth for Plate) ─────────────────────────

/** The mask run inside a masked mark (MH01XX•••7). */
export const MARK_MASK = '•••';

/**
 * Indian registration marks inside text: state code, RTO number, optional
 * series letters, a 4-digit number. Only the number is masked, last digit
 * kept. The same rule as the oracle's city/common.py and gods-eye/plates.ts
 * (mirrored here: src/lib/ui may not import from $lib/gods-eye).
 */
const MARK_IN_TEXT_RE = /\b([A-Z]{2}[ -]?\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?)(\d{4})\b/g;

/** True when a mark already carries the mask (•). */
export function isMaskedMark(mark: string | null | undefined): boolean {
	return !!mark && mark.includes('•');
}

/**
 * A mark as it may be shown without a named officer: the state code, RTO
 * number and series, then the mask and the last digit only (`MH01XX•••7`);
 * an already-masked mark is returned unchanged; an
 * unrecognised shape keeps its first characters and its last one only.
 * Plate uses it when a caller says `masked` but hands over a mark without
 * the mask, so a lock never sits beside a full mark.
 */
export function maskMark(mark: string): string {
	if (isMaskedMark(mark)) return mark;
	const masked = mark.replace(MARK_IN_TEXT_RE, (_m, head: string, num: string) => `${head}${MARK_MASK}${num.slice(-1)}`);
	if (masked !== mark) return masked;
	return mark.length >= 6 ? `${mark.slice(0, -4)}${MARK_MASK}${mark.slice(-1)}` : `${MARK_MASK}${mark.slice(-1)}`;
}

/** "19.0176° N 72.8562° E" (WGS 84), `digits` decimals; '—' for an invalid pair. */
export function fmtCoord(lat: number | null | undefined, lon: number | null | undefined, digits = 4): string {
	if (lat == null || lon == null || !Number.isFinite(lat) || !Number.isFinite(lon)) return DASH;
	if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return DASH;
	const ns = lat >= 0 ? 'N' : 'S';
	const ew = lon >= 0 ? 'E' : 'W';
	return `${Math.abs(lat).toFixed(digits)}° ${ns} ${Math.abs(lon).toFixed(digits)}° ${ew}`;
}

/**
 * IST wall time "hh:mm" or "hh:mm:ss" from loose input ("9:5", "0905",
 * "09:05:30"); null when it is not a valid 24-hour time. TimeField uses it.
 */
export function parseIstTime(input: string, seconds = false): string | null {
	const s = input.trim();
	let m = /^(\d{1,2})[:.](\d{1,2})(?:[:.](\d{1,2}))?$/.exec(s);
	if (!m) {
		const d = /^(\d{2})(\d{2})(\d{2})?$/.exec(s);
		if (d) m = d;
	}
	if (!m) return null;
	const h = Number(m[1]);
	const min = Number(m[2]);
	const sec = m[3] != null ? Number(m[3]) : 0;
	if (h > 23 || min > 59 || sec > 59) return null;
	const p = (n: number) => String(n).padStart(2, '0');
	return seconds ? `${p(h)}:${p(min)}:${p(sec)}` : `${p(h)}:${p(min)}`;
}

/** Epoch ms of an IST wall time "hh:mm[:ss]" on the IST day of `anchor`. */
export function istTimeToMs(hhmm: string, anchor: Moment = Date.now()): number {
	const norm = parseIstTime(hhmm, true);
	const day = istDay(anchor);
	if (!norm || !day) return NaN;
	return Date.parse(`${day}T${norm}+05:30`);
}

// ── SVG labels (map and graph) ───────────────────────────────────────────────

/** One run of an SVG label: an identifier (mono), a time (Inter, tabular) or text. */
export type SvgLabelPart =
	| { id: string }
	| { time: Moment; anchor?: Moment; seconds?: boolean }
	| { text: string };

/** A rendered run: its text and its face ('mono' for identifiers, 'ui' otherwise). */
export interface SvgLabelRun {
	text: string;
	face: 'mono' | 'ui';
	kind: 'id' | 'time' | 'text';
}

/** The runs of an SVG label (for a Svelte {#each} over <tspan>s). */
export function svgLabelParts(parts: readonly SvgLabelPart[]): SvgLabelRun[] {
	return parts.map((p) => {
		if ('id' in p) return { text: p.id, face: 'mono', kind: 'id' } as const;
		if ('time' in p) {
			const text = p.anchor !== undefined ? fmtStamp(p.time, p.anchor, p) : fmtTime(p.time, p);
			return { text, face: 'ui', kind: 'time' } as const;
		}
		return { text: p.text, face: 'ui', kind: 'text' } as const;
	});
}

function escapeXml(s: string): string {
	return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c);
}

/**
 * SVG <tspan> markup for a label inside a <text>: identifiers in a mono
 * tspan, times in an Inter tspan with tabular figures, runs separated by a
 * space. Text is escaped. `svgLabel([{ id: 'EM-CAM-03' }, { time: ms }])`.
 */
export function svgLabel(parts: readonly SvgLabelPart[]): string {
	return svgLabelParts(parts)
		.map((r, i) => {
			const lead = i > 0 ? ' ' : '';
			const style =
				r.face === 'mono'
					? 'font-family: var(--v-font-mono)'
					: 'font-family: var(--v-font-ui); font-variant-numeric: tabular-nums';
			return `<tspan class="v-${r.kind}" style="${style}">${escapeXml(lead + r.text)}</tspan>`;
		})
		.join('');
}
