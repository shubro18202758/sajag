/**
 * Dispatch — a unit request on an event (a 108 corridor request, a police
 * unit to a choke). The record is live (a real request and decision); the
 * unit that answers it may be emulated, and the view says so on the unit.
 * Also built from history records through `dispatchRow`.
 */
import { kindIcon } from '$lib/design/icons';
import { actorName, actorParts, displayTitle } from '../display';
import { human } from '../vocabulary';
import type { ObjectRow } from '../types';
import { L, anyTest, baseRow, groups, keyFigures, maskMarks, maskedRow, ms, num, objectRow, rec, shownText, str, systemRows, textRow, timeRow, urnFrom } from './common';
import { kindOne, provenanceRows, stateTags, type KindAdapter } from './generic';

/**
 * The event a dispatch answers, in words, masked (C6): the oracle sends a
 * dispatch's `event_title` RAW (a pursuit's is "PURSUIT — <mark>"), and the
 * sublabel reaches the omnibar, the search, the table and CSV.
 */
function eventWords(p: Readonly<Record<string, unknown>>): string | null {
	const title = str(p.event_title);
	return title ? maskMarks(displayTitle(title)) : null;
}

function agencyWords(p: Readonly<Record<string, unknown>>): string | null {
	return str(p.agency_label) ?? (str(p.agency) ? human(p.agency) : null);
}

export const dispatchAdapter: KindAdapter = {
	kind: 'dispatch',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		const p = e.props;
		const agency = agencyWords(p);
		const unit = str(p.unit_id);
		const state = str(p.status) ?? e.state;
		return {
			...row,
			label: [agency, unit].filter(Boolean).join(' · ') || row.label,
			sublabel: eventWords(p),
			state,
			stateIntent: state === 'requested' ? 'warning' : state === 'approved' ? 'success' : 'none',
			t: ms(p.created_at) ?? e.t,
			end: ms(p.updated_at),
			test: row.test || anyTest(p.requested_by, p.unit_id, p.decided_by),
		};
	},
	implied(row) {
		const p = row.props;
		return [urnFrom('event', p.event_id), urnFrom('junction', p.waypoint_junction), urnFrom('unit', p.unit_id)].filter((u): u is string => !!u);
	},
	view(row, ctx) {
		const p = row.props;
		const event = ctx.graph.get(urnFrom('event', p.event_id));
		const waypoint = ctx.graph.get(urnFrom('junction', p.waypoint_junction));
		const unitEmulated = p.unit_emulated === true;
		const requester = str(p.requested_by) ? actorParts(String(p.requested_by)) : null;
		const decider = str(p.decided_by) ? actorParts(String(p.decided_by)) : null;
		return {
			title: [{ text: row.label }],
			plateTitle: false,
			subtitle: [[{ text: kindOne('dispatch', ctx.lang) }], ...(row.t != null ? [[{ time: row.t }, { text: ` ${L(ctx, 'ws_unit_ist')}` }]] : [])],
			alert: false,
			tags: stateTags(row, ctx),
			// the state is the header's tag; the key figures are times and numbers
			figures: keyFigures([
				{ caption: L(ctx, 'ws_fig_requested'), value: null, time: row.t, unit: L(ctx, 'ws_unit_ist') },
				{ caption: L(ctx, 'ws_fig_eta'), value: num(p.eta_sec) != null ? Math.round((num(p.eta_sec) as number) / 60) : null, unit: L(ctx, 'ws_unit_min') },
			]),
			note: null,
			groups: groups(
				{
					title: L(ctx, 'ws_grp_dispatch'),
					rows: [
						textRow(L(ctx, 'ws_p_agency'), agencyWords(p)),
						str(p.unit_id) ? { key: L(ctx, 'ws_p_unit'), value: { t: 'id', v: String(p.unit_id), hint: unitEmulated ? L(ctx, 'ws_v_unit_emulated') : null } } : null,
						// the raw title only for a named duty officer (SPEC §9.3)
						event ? objectRow(L(ctx, 'ws_p_for'), event) : textRow(L(ctx, 'ws_p_for'), shownText(ctx, str(p.event_title) ? displayTitle(str(p.event_title), ctx.lang) : null)),
						waypoint ? objectRow(L(ctx, 'ws_p_waypoint'), waypoint) : num(p.waypoint_junction) != null ? { key: L(ctx, 'ws_p_waypoint'), value: { t: 'id', v: `J${p.waypoint_junction}` } } : null,
						requester ? textRow(L(ctx, 'ws_p_requested_by'), actorName(requester, ctx.lang), requester.scenario) : null,
						decider ? textRow(L(ctx, 'ws_p_decided_by'), actorName(decider, ctx.lang), decider.scenario) : null,
						timeRow(L(ctx, 'ws_p_approved'), p.approved_at),
					],
				},
				{ title: L(ctx, 'ws_grp_provenance'), rows: provenanceRows(row, ctx) },
			),
			system: systemRows(row),
			plate: null,
		};
	},
};

/** A dispatch known only from history (GET /dispatches rows), as a row. */
export function dispatchRow(d: Record<string, unknown>): ObjectRow | null {
	const id = str(d.dispatch_id) ?? str(d.id);
	if (!id) return null;
	const agency = agencyWords(d);
	const unit = str(d.unit_id);
	const state = str(d.status);
	const wp = rec(d.waypoint);
	return maskedRow({
		urn: `dispatch:${id}`,
		kind: 'dispatch',
		id,
		label: [agency, unit].filter(Boolean).join(' · ') || id,
		sublabel: eventWords(d),
		icon: kindIcon('dispatch'),
		state,
		stateIntent: state === 'requested' ? 'warning' : state === 'approved' ? 'success' : 'none',
		t: ms(d.created_at),
		end: ms(d.updated_at),
		lon: num(wp.lon),
		lat: num(wp.lat),
		// a dispatch the emulator's 108 control room asked for (its EM units) is EMULATED, never a live record
		source: /\(emulated\)|event-emulator/i.test(String(d.requested_by ?? '')) || /-EM\d/i.test(String(d.unit_id ?? '')) ? 'emulated' : 'live',
		verification: null,
		credibility: null,
		test: anyTest(d.requested_by, d.unit_id, d.decided_by),
		masked: false,
		props: d,
	});
}
