/**
 * Event — a corridor event (a protected movement, a procession, a pursuit,
 * a reported incident …). Its title goes through displayTitle: test labels
 * become a Test tag, "(Emulated)" the provenance tag, and a pursuit title
 * reads "Pursuit of <mark>" with its FIR in Properties.
 *
 * The event view keeps the pinned hooks of the old dossier drawer:
 * `dossier-phase-window` (each phase's IST window, as the ops board prints
 * it) and `dossier-advisory-withheld` (an operator-only kind gets no citizen
 * advisory preview).
 */
import { t } from '$lib/i18n/strings';
import { parseUrn } from '$lib/gods-eye/city-api';
import { actorName, actorParts, localTitle, titleParts } from '../display';
import { maskMarks } from '../mask';
import { human } from '../vocabulary';
import type { ObjectRow } from '../types';
import {
	L,
	anyTest,
	baseRow,
	groups,
	iconOf,
	keyFigures,
	ms,
	num,
	rec,
	sameMinute,
	str,
	systemRows,
	textRow,
	timeRun,
	urnFrom,
	type PropRow,
} from './common';
import { provenanceRows, stateTags, stateWord, type ImpliedLink, type KindAdapter } from './generic';

/**
 * An event's window from its own fields ONLY (F-02): the actual start, else
 * the planned one. An event with neither has not started — its row carries
 * no time (never the snapshot's as_of or the row's last change, which read
 * as "started now").
 */
export function eventTimes(p: Readonly<Record<string, unknown>>): { t: number | null; end: number | null } {
	return {
		t: ms(p.actual_start) ?? ms(p.planned_start),
		end: ms(p.actual_end) ?? ms(p.planned_end),
	};
}

/** Event kinds a crowd class says nothing about (F-27: a pursuit has no crowd). */
const NO_CROWD_KINDS: ReadonlySet<string> = new Set(['vehicle_pursuit']);

/**
 * An event kind in words, in `lang`: the core packs name the corridor kinds
 * (`kind_<event_kind>`, HI/MR); EN and any kind they do not name read
 * through the vocabulary ("Vehicle pursuit").
 */
function eventKindWords(kind: string, lang: string): string {
	if (lang !== 'en') {
		const key = `kind_${kind}`;
		const named = t(lang, key);
		if (named !== key) return named;
	}
	return human(kind);
}

function eventTest(p: Readonly<Record<string, unknown>>, titleTest: boolean): boolean {
	const md = rec(p.metadata);
	return titleTest || !!str(md.label) || md.acceptance_test === true || anyTest(p.title, md.opened_by);
}

export const eventAdapter: KindAdapter = {
	kind: 'event',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		const p = e.props;
		const parts = titleParts(str(p.title) ?? e.label);
		const md = rec(p.metadata);
		const own = eventTimes(p);
		// the row's TIME (lists, the timeline, time windows): its own start, else the entity's last
		// change — never shown as a start: the view reads the event's own fields (F-02)
		const t = own.t ?? e.t;
		const end = own.end;
		const state = str(p.status) ?? e.state;
		const emulated = parts.emulated || md.source === 'event-emulator';
		return {
			...row,
			label: maskMarks(parts.title),
			sublabel: str(p.event_kind) ? human(p.event_kind) : null,
			icon: iconOf('event', str(p.event_kind)),
			state,
			stateIntent: 'none',
			t,
			end,
			source: row.source === 'live' && emulated ? 'emulated' : row.source,
			test: eventTest(p, parts.test),
		};
	},
	implied(row) {
		const md = rec(row.props.metadata);
		const out: ImpliedLink[] = [urnFrom('vehicle', md.vehicle_id), urnFrom('recommendation', md.recommendation_id)].filter((u): u is string => !!u);
		// an event promoted from an open-source report names it (C-T provenance.osint_event_id): "Promoted from"
		const report = urnFrom('osint_event', rec(row.props.provenance).osint_event_id);
		if (report && parseUrn(report)) out.push({ urn: report, rel: 'promoted_from' });
		return out;
	},
	view(row, ctx) {
		const p = row.props;
		const md = rec(p.metadata);
		const parts = titleParts(str(p.title) ?? row.label);
		const kind = str(p.event_kind);
		const fir = parts.fir ?? str(md.fir)?.replace(/^FIR\s+/i, '') ?? null;
		const opener = str(md.opened_by) ? actorParts(String(md.opened_by)) : null;
		const protection = str(p.protection_class);
		const spines = Array.isArray(p.route_spines) ? (p.route_spines as unknown[]).map(rec) : [];
		const phases = ctx.phases?.(row.id) ?? null;
		const operatorOnly = ctx.publicKind ? !ctx.publicKind(kind) : false;
		// F-02: the window is the event's OWN start and end — row.t may be the entity's last change
		// (a pursuit's band is re-evaluated every few seconds: "Start" read as now)
		const own = eventTimes(p);
		const start = own.t;
		// an end in the start's minute reads the same (hh:mm): one stamp, no End figure, never "23:55–23:55"
		const end = start != null && sameMinute(start, own.end) ? null : own.end;
		const notStarted = start == null;

		const phaseRows: PropRow[] = (phases ?? []).map((ph, i) => ({
			key: ph.label,
			value: { t: 'text', v: ph.window },
			testid: 'dossier-phase-window',
			attrs: { 'data-phase-index': String(i) },
		}));

		return {
			title: [{ text: localTitle(row.label, ctx.lang) }],
			plateTitle: false,
			subtitle: [
				[{ text: kind ? eventKindWords(kind, ctx.lang) : L(ctx, 'ws_kind_event') }],
				// the window is ONE range at one precision ("23 Oct 23:52–00:04 IST"), never two stamps
				...(start != null ? [[timeRun(start, own.end), { text: ` ${L(ctx, 'ws_unit_ist')}` }]] : []),
			],
			alert: false,
			tags: stateTags(row, ctx),
			// figures without a value are dropped (no "Class —" for an unprotected event)
			figures: keyFigures([
				{ caption: L(ctx, 'ws_fig_class'), value: protection && protection !== 'none' ? protection : null },
				{ caption: L(ctx, 'ws_fig_crowd'), value: str(p.crowd_class) && !(kind && NO_CROWD_KINDS.has(kind)) ? human(String(p.crowd_class).toLowerCase()) : null },
				notStarted
					? { caption: L(ctx, 'ws_fig_start'), value: L(ctx, 'ws_v_not_started') }
					: { caption: L(ctx, 'ws_fig_start'), value: null, time: start, unit: L(ctx, 'ws_unit_ist') },
				{ caption: L(ctx, 'ws_fig_end'), value: null, time: end, unit: L(ctx, 'ws_unit_ist') },
			]),
			note: null,
			groups: groups(
				{
					title: L(ctx, 'ws_grp_event'),
					rows: [
						textRow(L(ctx, 'ws_p_kind'), kind ? eventKindWords(kind, ctx.lang) : null),
						textRow(L(ctx, 'ws_p_status'), stateWord(row.state, ctx.lang)),
						// a window that opened and closed within one minute is one stamp, never "23:55–23:55"
						start != null
							? { key: L(ctx, 'ws_p_window'), value: { t: 'range', a: start, b: end } }
							: textRow(L(ctx, 'ws_p_window'), L(ctx, 'ws_v_not_started')),
						textRow(L(ctx, 'ws_p_protection'), protection && protection !== 'none' ? protection : null),
						textRow(L(ctx, 'ws_p_fir'), fir),
						opener ? textRow(L(ctx, 'ws_p_opened_by'), actorName(opener, ctx.lang), opener.scenario) : null,
						textRow(L(ctx, 'ws_p_route'), spines.map((s) => str(s.label)).filter(Boolean).join(', ') || null),
					],
				},
				{ title: L(ctx, 'ws_grp_phases'), rows: phaseRows },
				{
					title: L(ctx, 'ws_grp_advisory'),
					rows: [operatorOnly ? { key: L(ctx, 'ws_p_citizens'), value: { t: 'text', v: L(ctx, 'ws_v_advisory_withheld') }, testid: 'dossier-advisory-withheld' } : null],
				},
				{ title: L(ctx, 'ws_grp_provenance'), rows: provenanceRows(row, ctx, row.source === 'emulated' ? L(ctx, 'ws_v_emulator') : null) },
			),
			system: systemRows(row, { title: str(p.title), source: md.source, run_id: num(md.run_id), mode: md.mode }),
			plate: null,
		};
	},
};

/**
 * An event known only from history (GET /api/v1/events rows), as a row.
 * Providers register these through registerObjectSource.
 */
export function eventRow(ev: Record<string, unknown>): ObjectRow | null {
	const id = str(ev.event_id) ?? str(ev.id);
	if (!id) return null;
	const title = str(ev.title) ?? str(ev.name) ?? id;
	const parts = titleParts(title);
	const md = rec(ev.metadata);
	const own = eventTimes(ev);
	// the row's time (lists, the timeline): its own start, else its last change (never shown as a start, F-02)
	const t = own.t ?? ms(ev.updated_at);
	const end = own.end;
	const kind = str(ev.event_kind);
	const geo = rec(ev.geotag);
	const sourceKind = str(ev.source_kind);
	return {
		urn: `event:${id}`,
		kind: 'event',
		id,
		label: maskMarks(parts.title),
		sublabel: kind ? human(kind) : null,
		icon: iconOf('event', kind),
		state: str(ev.status),
		stateIntent: 'none',
		t,
		end: end ?? ms(ev.updated_at),
		lon: num(geo.lon),
		lat: num(geo.lat),
		source: sourceKind === 'osint' ? 'osint' : parts.emulated || md.source === 'event-emulator' || sourceKind === 'emulator' ? 'emulated' : 'live',
		verification: (str(ev.verification_state) as ObjectRow['verification']) ?? null,
		credibility: num(ev.credibility),
		test: eventTest({ ...ev, title }, parts.test),
		masked: /•/.test(parts.title),
		props: { ...ev, title: maskMarks(title) },
	};
}
