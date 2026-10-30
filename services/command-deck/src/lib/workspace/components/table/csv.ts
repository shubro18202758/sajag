/**
 * CSV export of the ObjectTable's rows (SPEC §7.5, §8.9; ethics rules 5 and 7).
 *
 *   toCsv(rows)   one line per row, a header line first, CRLF line ends.
 *
 * Egress is ALWAYS masked, whatever the officer state: the officer's
 * unmasked view is never written anywhere (§7.5). Every text cell goes
 * through maskMarks (any case and spelling), the row's props are never
 * dumped, and the only identifiers are URNs (never a mark).
 *
 * Every row says where it comes from: a Provenance column (Live, Emulated,
 * Simulated, Test, Open-source), the open-source Verification state as its
 * honest label (UNVERIFIED-OSINT, NEWS-REPORTED, OFFICIAL-VERIFIED,
 * CONFIRMED), the Credibility score, and a Test column. Times are IST
 * ("2026-10-24 01:38:37"; the header says IST).
 *
 * A cell a spreadsheet would read as a formula (= + - @, a tab or a carriage
 * return first) is prefixed with an apostrophe.
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.views';
import '$lib/i18n/packs.workspace';
import { kindOne, shortStateWord } from '../../kinds/generic';
import { maskMarks } from '../../mask';
import type { ObjectRow } from '../../types';
import { sourceWord } from '../histogram/bins';
import { placeOf, speedOf } from './model';

export interface CsvOptions {
	lang?: string;
	/** Resolve a linked object (a camera's place for a read); default: none. */
	get?: (urn: string) => ObjectRow | null;
	/** One-hop link counts, when the caller has them (the table's Links column). */
	links?: (urn: string) => number;
}

const IST_DATE = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' });
const IST_TIME = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' });

/** "2026-10-24 01:38:37" in IST, or '' for no time. */
export function istStamp(ms: number | null | undefined): string {
	if (ms == null || !Number.isFinite(ms)) return '';
	return `${IST_DATE.format(ms)} ${IST_TIME.format(ms)}`;
}

/** One CSV field: masked, formula-guarded, quoted when it must be. */
export function csvCell(v: unknown): string {
	if (v == null) return '';
	let s = typeof v === 'number' ? (Number.isFinite(v) ? String(v) : '') : maskMarks(String(v));
	if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
	return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** The CSV of `rows`, masked, with provenance and verification columns (header first). */
export function toCsv(rows: readonly ObjectRow[], opts: CsvOptions = {}): string {
	const lang = opts.lang ?? 'en';
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const header = [
		L('vw_csv_urn'),
		L('vw_t_col_object'),
		L('vw_t_col_type'),
		L('vw_t_col_state'),
		L('vw_t_col_time'),
		L('vw_t_col_place'),
		L('vw_csv_speed'),
		...(opts.links ? [L('vw_t_col_links')] : []),
		L('vw_csv_provenance'),
		L('vw_csv_verification'),
		L('vw_csv_credibility'),
		L('vw_csv_test'),
	];
	const lines = [header.map(csvCell).join(',')];
	for (const r of rows) {
		const speed = speedOf(r);
		const cells: unknown[] = [
			r.urn,
			r.label,
			kindOne(r.kind, lang),
			shortStateWord(r.state, lang) ?? '',
			istStamp(r.t),
			placeOf(r, opts.get) ?? '',
			speed != null ? Math.round(speed) : '',
			...(opts.links ? [opts.links(r.urn)] : []),
			sourceWord(r.source, lang),
			r.source === 'osint' ? (r.verification ?? '') : '',
			r.credibility != null && Number.isFinite(r.credibility) ? r.credibility.toFixed(2) : '',
			r.test ? L('ws_v_yes') : '',
		];
		lines.push(cells.map(csvCell).join(','));
	}
	return `${lines.join('\r\n')}\r\n`;
}

/** The file name of an export: "sajag-objects-2026-10-24-0138-ist.csv". */
export function csvFileName(now = Date.now()): string {
	const [date, time] = istStamp(now).split(' ');
	return `sajag-objects-${date}-${(time ?? '').slice(0, 5).replace(':', '')}-ist.csv`;
}

/** Hand the CSV to the browser as a download (a UTF-8 BOM so spreadsheets read • and Indic text). */
export function downloadCsv(csv: string, name = csvFileName()): void {
	if (typeof document === 'undefined') return;
	const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = name;
	a.rel = 'noopener';
	document.body.appendChild(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}
