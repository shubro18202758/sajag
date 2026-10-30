/**
 * Camera — an ANPR camera (infrastructure: never fades in a time window).
 * Labelled by its id; it captures registration marks only (SPEC §9.3).
 */
import { fmtAgo } from '$lib/ui/format/format';
import { human } from '../vocabulary';
import { L, baseRow, compass, groups, keyFigures, ms, num, objectRow, str, systemRows, textRow, urnFrom } from './common';
import { provenanceRows, type KindAdapter } from './generic';

/** The camera's place: the part of its name after the first colon ("…camera 3: Chowringhee Road"). */
export function cameraPlace(label: string | null | undefined): string | null {
	if (!label) return null;
	const i = label.indexOf(':');
	const place = (i >= 0 ? label.slice(i + 1) : label).trim();
	return place || null;
}

export const cameraAdapter: KindAdapter = {
	kind: 'camera',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		return {
			...row,
			label: e.id,
			sublabel: cameraPlace(e.label),
			t: ms(e.props.last_read_t) ?? e.t,
			stateIntent: 'none',
		};
	},
	implied(row) {
		return [urnFrom('junction', row.props.junction_id), urnFrom('segment', row.props.segment_id)].filter((u): u is string => !!u);
	},
	view(row, ctx) {
		const p = row.props;
		const lastRead = ms(p.last_read_t);
		const junction = ctx.graph.get(urnFrom('junction', p.junction_id));
		const segment = ctx.graph.get(urnFrom('segment', p.segment_id));
		const kind = str(p.camera_kind);
		return {
			title: [{ id: row.id }],
			plateTitle: false,
			subtitle: [[{ text: kind ? L(ctx, 'ws_sub_camera_of', human(kind)) : L(ctx, 'ws_kind_camera') }], ...(row.sublabel ? [[{ text: row.sublabel }]] : [])],
			alert: false,
			tags: [],
			// the window is the caption's ("Reads, 15 min"), so a figure is one number; an unknown heading is no figure
			figures: keyFigures([
				{ caption: L(ctx, 'ws_fig_reads_15m'), value: num(p.reads_15m) ?? 0, hint: L(ctx, 'ws_hint_reads_15m') },
				{ caption: L(ctx, 'ws_fig_hits_15m'), value: num(p.hits_15m) ?? 0, hint: L(ctx, 'ws_hint_hits_15m') },
				{ caption: L(ctx, 'ws_fig_last_read'), value: null, time: lastRead, unit: L(ctx, 'ws_unit_ist'), hint: lastRead != null ? fmtAgo(lastRead, ctx.now, ctx.lang) : null },
				{ caption: L(ctx, 'ws_fig_heading'), value: num(p.heading_deg) != null ? compass(num(p.heading_deg), ctx.lang) : null },
			]),
			note: null,
			groups: groups(
				{
					title: L(ctx, 'ws_grp_location'),
					rows: [
						textRow(L(ctx, 'ws_p_place'), row.sublabel),
						junction ? objectRow(L(ctx, 'ws_p_junction'), junction) : null,
						segment ? objectRow(L(ctx, 'ws_p_road'), segment) : null,
						row.lat != null && row.lon != null ? { key: L(ctx, 'ws_p_coord'), value: { t: 'coord', lat: row.lat, lon: row.lon } } : null,
					],
				},
				{
					title: L(ctx, 'ws_grp_data'),
					rows: [
						textRow(L(ctx, 'ws_p_captures'), L(ctx, 'ws_v_captures')),
						textRow(L(ctx, 'ws_p_registry'), [str(p.camera_source) ? human(p.camera_source) : null, p.registered === true ? L(ctx, 'ws_v_registered') : null].filter(Boolean).join(' · ') || null),
					],
				},
				{ title: L(ctx, 'ws_grp_provenance'), rows: provenanceRows(row, ctx) },
			),
			system: systemRows(row),
			plate: null,
		};
	},
};
