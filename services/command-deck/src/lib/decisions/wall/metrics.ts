/**
 * The /ops metric strip's model (SPEC §5.3 "MetricStrip", §6.3): eight
 * cells, in this order —
 *
 *   Active events · Decisions waiting · Units dispatched · Ambulance windows
 *   · Corridor speed · Congested roads · Watchlist reads 24 h · Feed anomalies
 *
 * EXACTLY FOUR cells are the commander's counters: they carry
 * `data-prim="data-tile"` with `data-counter` (active-events,
 * pending-decisions, units-dispatched, ambulance-windows) and `data-value`
 * (ops-wall-smoke reads it). A zero value recedes (ink-2, weight 400: the
 * eye goes to what is non-zero, and "Decisions waiting 0" is never orange).
 * Corridor speed and watchlist reads carry a sparkline from 1600 px up.
 *
 * The sub line of "Decisions waiting" names the SOONEST decision's real
 * kind (FIX-E-DSSCARD item 10: it said "Escort proposal expires in …" even
 * when the soonest decision was a DSS response or a 108 decision). The
 * page's frozen input carries the deadline only, so the kind is read off
 * the same decision units the page counted — with the input's escort
 * sentence standing when no unit matches (the legacy contract, and what an
 * empty registry reads).
 *
 * Pure in its inputs; the soonest-kind lookup reads the decision-unit
 * registry. tests/wall.unit.mjs checks the counters and the receding zeros;
 * tests/decisions.unit.mjs pins the per-kind sentences.
 */
import type { IconName } from '$lib/design/icons';
import { t, kindLabel } from '$lib/i18n/strings';
import { fmtCountdown, fmtDuration, fmtTime } from '$lib/ui/format/format';
import '$lib/i18n/packs.wall';
import '$lib/i18n/packs.decisions';
import { decisionUnits } from '../units';

/** The four commander counters, in strip order (the only cells that are data tiles). */
export const COUNTER_KEYS = ['active-events', 'pending-decisions', 'units-dispatched', 'ambulance-windows'] as const;
export type CounterKey = (typeof COUNTER_KEYS)[number];

export interface MetricCell {
	key: string;
	caption: string;
	value: number | string | null;
	unit: string | null;
	sub: string | null;
	/** A glyph before the sub line (the simulated-feed glyph). */
	subIcon: IconName | null;
	intent: 'none' | 'warning';
	/** data-counter: set on exactly four cells. */
	counter: CounterKey | null;
	/** The cell recedes: its value is zero. */
	zero: boolean;
	spark: number[] | null;
	tooltip: string | null;
}

export interface MetricInput {
	lang: string;
	now: number;
	/** Live (not fixture) events in state active. */
	active: number;
	/** Live events still open (planning, approved, active). */
	open: number;
	/** Events the history lists (null while it has not answered). */
	history: number | null;
	/** Decision units waiting. */
	units: number;
	/** The soonest deadline among the waiting units, epoch ms. */
	soonestDeadline: number | null;
	/** The soonest deadline unit's kind, when the page knows it (the ±1 s deadline lookup is the fallback). */
	soonestKind?: string | null;
	/** The oldest item still waiting, epoch ms. */
	oldestWaiting: number | null;
	dispatched: number;
	dispatchesClosed: number;
	ambulance: number;
	ambulanceClosed: number;
	speedKmh: number | null;
	/** Where the traffic readings come from. */
	speedSource: 'simulated' | 'mixed' | 'live' | 'none' | null;
	speedSamples: readonly number[];
	roads: number | null;
	congested: number | null;
	critical: number | null;
	/** Watchlist reads in the last 24 h (the city feed rows loaded). */
	reads24: number;
	readVehicles: number;
	lastRead: number | null;
	/** Reads per hour over the last 24 h, oldest first. */
	readBins: readonly number[];
	anomalies: number;
	/**
	 * COPY-1: where the dispatched units' positions and statuses come from
	 * (the unit feed's `emulated` flags; null = no dispatched unit seen), and
	 * the ambulance units' and the watchlist reads' own mix. An emulated or
	 * mixed source puts its word in the cell's sub line, as the speed cell's.
	 */
	unitsSource?: SourceMix;
	ambulanceSource?: SourceMix;
	readsSource?: SourceMix;
}

export type SourceMix = 'emulated' | 'mixed' | 'live' | null;

/** The provenance of a set: every member emulated, some, none — null for an empty set. */
export function sourceMix(emulatedFlags: readonly boolean[]): SourceMix {
	if (!emulatedFlags.length) return null;
	const n = emulatedFlags.filter(Boolean).length;
	return n === emulatedFlags.length ? 'emulated' : n > 0 ? 'mixed' : 'live';
}

const L = (lang: string, key: string, ...args: unknown[]) => t(lang, key, ...args);

/** A value recedes when it is zero (a number 0 or the string '0'). */
export function isZero(v: number | string | null | undefined): boolean {
	return v === 0 || v === '0';
}

/** Counts per hour over the `hours` before `now`, oldest first. */
export function hourlyBins(times: readonly number[], now: number, hours = 24): number[] {
	const bins = new Array<number>(hours).fill(0);
	const start = now - hours * 3_600_000;
	for (const ms of times) {
		if (!Number.isFinite(ms) || ms < start || ms > now) continue;
		const i = Math.min(hours - 1, Math.floor((ms - start) / 3_600_000));
		bins[i]++;
	}
	return bins;
}

function cell(c: Omit<MetricCell, 'zero' | 'subIcon' | 'intent' | 'counter' | 'spark' | 'tooltip' | 'unit'> & Partial<MetricCell>): MetricCell {
	return {
		unit: null,
		subIcon: null,
		intent: 'none',
		counter: null,
		spark: null,
		tooltip: null,
		...c,
		zero: isZero(c.value),
	};
}

/**
 * The soonest deadline's own countdown sentence (FIX-E-DSSCARD item 10): the
 * unit whose deadline it is names the kind — a decision-support response, a
 * 108 decision, the escort. The page's `soonestKind` names it directly when
 * present; the ±1 s deadline lookup over the decision units is the fallback.
 * The escort keeps the wall pack's pinned sentence; with no kind at all (an
 * empty registry, the legacy fixture input) the escort sentence stands too.
 */
function soonestExpires(lang: string, soonestDeadline: number, now: number, soonestKind?: string | null): string {
	const countdown = fmtCountdown((soonestDeadline - now) / 1000);
	let kind: string | null = soonestKind ?? null;
	if (kind == null) {
		let best = Number.POSITIVE_INFINITY;
		for (const u of decisionUnits()) {
			if (u.deadline == null) continue;
			const d = Math.abs(u.deadline - soonestDeadline);
			if (d < best && d <= 1_000) {
				best = d;
				kind = u.kind;
			}
		}
	}
	if (kind == null || kind === 'escort-proposal') return L(lang, 'wall_m_decisions_expires', countdown);
	const word =
		kind === 'dss'
			? L(lang, 'dec_kind_dss')
			: kind === 'corridor-request'
				? L(lang, 'dec_kind_corridor')
				: kindLabel(lang, kind);
	return L(lang, 'dec_m_soonest_expires', word, countdown);
}

/** The eight cells of the strip (exactly four counters). */
export function metricCells(i: MetricInput): MetricCell[] {
	const { lang } = i;
	const speed = i.speedKmh != null && Number.isFinite(i.speedKmh) ? i.speedKmh.toFixed(1) : null;
	const sourceWord =
		i.speedSource === 'simulated'
			? L(lang, 'wall_m_speed_simulated')
			: i.speedSource === 'mixed'
				? L(lang, 'wall_m_speed_mixed')
				: i.speedSource === 'live'
					? L(lang, 'wall_m_speed_live')
					: L(lang, 'wall_m_speed_none');
	const decisionsSub =
		i.units === 0
			? L(lang, 'wall_m_decisions_none')
			: i.soonestDeadline != null && i.soonestDeadline > i.now
				? soonestExpires(lang, i.soonestDeadline, i.now, i.soonestKind)
				: i.oldestWaiting != null
					? L(lang, 'wall_m_decisions_oldest', fmtDuration((i.now - i.oldestWaiting) / 1000, lang))
					: L(lang, 'wall_m_decisions_some');
	/** The units' sub line: the source word first when emulated or mixed (COPY-1), else the closed count alone. */
	const unitsSub = (src: SourceMix | undefined, closed: number, plain: string): string =>
		src === 'emulated' || src === 'mixed' ? L(lang, 'wall_m_units_src', L(lang, `wall_m_src_${src}_units`), closed) : plain;
	return [
		cell({
			key: 'active',
			caption: L(lang, 'wall_m_active'),
			value: i.active,
			sub: i.history != null ? L(lang, 'wall_m_active_sub', i.open, i.history) : L(lang, 'wall_m_active_open', i.open),
			counter: 'active-events',
			tooltip: L(lang, 'wall_m_active_tip'),
		}),
		cell({
			key: 'decisions',
			caption: L(lang, 'wall_m_decisions'),
			value: i.units,
			sub: decisionsSub,
			intent: 'warning',
			counter: 'pending-decisions',
			tooltip: L(lang, 'wall_m_decisions_tip'),
		}),
		cell({
			key: 'units',
			caption: L(lang, 'wall_m_units'),
			value: i.dispatched,
			sub: unitsSub(i.unitsSource, i.dispatchesClosed, L(lang, 'wall_m_units_sub', i.dispatchesClosed)),
			counter: 'units-dispatched',
			tooltip: L(lang, 'wall_m_units_tip'),
		}),
		cell({
			key: 'ambulance',
			caption: L(lang, 'wall_m_ambulance'),
			value: i.ambulance,
			sub: unitsSub(i.ambulanceSource, i.ambulanceClosed, L(lang, 'wall_m_ambulance_sub', i.ambulanceClosed)),
			counter: 'ambulance-windows',
			tooltip: L(lang, 'wall_m_ambulance_tip'),
		}),
		cell({
			key: 'speed',
			caption: L(lang, 'wall_m_speed'),
			value: speed ?? '—',
			unit: speed != null ? L(lang, 'wall_unit_kmh') : null,
			sub: sourceWord,
			subIcon: i.speedSource === 'simulated' || i.speedSource === 'mixed' ? 'random' : null,
			spark: i.speedSamples.length >= 2 ? [...i.speedSamples] : null,
			tooltip: L(lang, 'wall_m_speed_tip', i.roads ?? '—'),
		}),
		cell({
			key: 'congested',
			caption: L(lang, 'wall_m_congested'),
			value: i.congested ?? '—',
			unit: i.roads != null ? L(lang, 'wall_m_congested_of', i.roads) : null,
			sub: L(lang, 'wall_m_congested_sub', i.critical ?? 0),
			tooltip: L(lang, 'wall_m_congested_tip'),
		}),
		cell({
			key: 'reads',
			caption: L(lang, 'wall_m_reads'),
			value: i.reads24,
			unit: L(lang, 'wall_unit_24h'),
			sub:
				i.lastRead == null
					? L(lang, 'wall_m_reads_none')
					: i.readsSource === 'emulated' || i.readsSource === 'mixed'
						? L(lang, 'wall_m_reads_src', L(lang, `wall_m_src_${i.readsSource}_reads`), fmtTime(i.lastRead))
						: L(lang, 'wall_m_reads_sub', i.readVehicles, fmtTime(i.lastRead)),
			spark: i.readBins.some((n) => n > 0) ? [...i.readBins] : null,
			tooltip: L(lang, 'wall_m_reads_tip'),
		}),
		cell({
			key: 'anomalies',
			caption: L(lang, 'wall_m_anomalies'),
			value: i.anomalies,
			sub: L(lang, 'wall_m_anomalies_sub'),
			tooltip: L(lang, 'wall_m_anomalies_tip'),
		}),
	];
}
