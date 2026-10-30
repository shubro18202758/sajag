/**
 * City Command formatting — kept for the layers, the vitals and the rail
 * that import it, and delegating to THE formatter (src/lib/ui/format, SPEC
 * §3.3): IST everywhere (the city's own clock, never the browser's zone),
 * one stamp rule, durations in words. Pure helpers.
 */
import { fmtDay, fmtDuration, fmtStamp, fmtTime } from '$lib/ui/format/format';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.workspace';

/** HH:MM:SS in IST ('—' when unknown). */
export function istTime(ms: number | null | undefined): string {
	return ms != null && Number.isFinite(ms) ? fmtTime(ms, { seconds: true }) : '—';
}

/** '22 Oct 21:40' in IST (the date always shown). */
export function istDayTime(ms: number | null | undefined): string {
	return ms != null && Number.isFinite(ms) ? `${fmtDay(ms)} ${fmtTime(ms)}` : '—';
}

/** Row time: HH:MM:SS on today's IST date, '22 Oct 21:40' on an older day. */
export function istStamp(ms: number | null | undefined, now = Date.now()): string {
	if (ms == null || !Number.isFinite(ms)) return '—';
	return fmtStamp(ms, now, { seconds: true });
}

/** Compact age: "42 s", "4 min", "3 h 12 min", "2 d 5 h". */
export function fmtAge(sec: number | null | undefined): string {
	return fmtDuration(sec);
}

/** Seconds since an epoch-ms instant (null-safe). */
export function ageOf(ms: number | null | undefined, now = Date.now()): number | null {
	return ms != null && Number.isFinite(ms) ? Math.max(0, (now - ms) / 1000) : null;
}

/**
 * The pack key of each kind's operator word (packs.workspace.ts, EN/HI/MR):
 * the workspace's kind names, except a read ("ANPR read") and a penal
 * recommendation ("E-challan"), which City Command names by what they are.
 */
const KIND_WORD_KEY: Record<string, string> = {
	event: 'ws_kind_event',
	vehicle: 'ws_kind_vehicle',
	sighting: 'ws_word_sighting',
	camera: 'ws_kind_camera',
	junction: 'ws_kind_junction',
	unit: 'ws_kind_unit',
	convoy: 'ws_kind_convoy',
	dispatch: 'ws_kind_dispatch',
	recommendation: 'ws_word_recommendation',
	anomaly: 'ws_kind_anomaly',
	segment: 'ws_kind_segment',
	osint_event: 'ws_kind_osint_event',
	place: 'ws_kind_place',
};

/**
 * The operator word for an entity kind, sentence case, in `lang`. A
 * recommendation under the evidence-only R_STOLEN_SIGHTING rule is a
 * sighting on file, never a fine: it reads "Stolen-vehicle sighting", not
 * "E-challan". An unknown kind reads in words.
 */
export function kindWord(kind: string | null | undefined, ruleId?: string | null, lang = 'en'): string {
	if (kind === 'recommendation' && ruleId === 'R_STOLEN_SIGHTING') return t(lang, 'ws_rule_R_STOLEN_SIGHTING');
	if (kind && Object.prototype.hasOwnProperty.call(KIND_WORD_KEY, kind)) return t(lang, KIND_WORD_KEY[kind]);
	const w = (kind ?? 'object').replace(/_/g, ' ');
	return w.charAt(0).toUpperCase() + w.slice(1);
}

/** 'requested_by' → 'requested by'. */
export function humanKey(key: string): string {
	return key.replace(/_/g, ' ');
}
