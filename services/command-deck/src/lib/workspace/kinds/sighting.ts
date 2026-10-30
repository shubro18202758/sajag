/**
 * Sighting — one lawful ANPR read of a watchlisted vehicle (C6: the oracle
 * surfaces a read only under an active earmark or as a recommendation's
 * evidence). Labelled by its camera; the mark is masked.
 */
import { maskPlate } from '$lib/gods-eye/plates';
import { human } from '../vocabulary';
import {
	L,
	baseRow,
	compass,
	groups,
	keyFigures,
	num,
	objectRow,
	str,
	systemRows,
	textRow,
	urnFrom,
	type ViewCtx,
} from './common';
import { provenanceRows, type KindAdapter } from './generic';

export const sightingAdapter: KindAdapter = {
	kind: 'sighting',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		const p = e.props;
		const mark = str(p.plate_masked) ?? maskPlate(str(p.plate));
		return {
			...row,
			label: str(p.camera_id) ?? row.label,
			sublabel: mark,
			masked: true,
			// the matched list (stolen_vehicle) is the vehicle's alert, not the read's state
			stateIntent: 'none',
		};
	},
	implied(row) {
		return [urnFrom('vehicle', row.props.vehicle_id), urnFrom('camera', row.props.camera_id)].filter((u): u is string => !!u);
	},
	view(row, ctx: ViewCtx) {
		const p = row.props;
		const cam = str(p.camera_id);
		const raw = str(p.plate);
		const masked = !ctx.officer || !raw;
		const mark = masked ? (str(p.plate_masked) ?? maskPlate(raw)) : (ctx.plate(raw) ?? str(p.plate_masked));
		const speed = num(p.speed_kmh);
		const heading = num(p.heading);
		const vehicle = ctx.graph.get(urnFrom('vehicle', p.vehicle_id));
		const camera = ctx.graph.get(urnFrom('camera', cam));
		return {
			title: [{ text: `${L(ctx, 'ws_title_read_at')} ` }, { id: cam ?? row.id }],
			plateTitle: false,
			subtitle: [[{ text: L(ctx, 'ws_sub_anpr_read') }], [{ plate: mark, masked }], [{ time: row.t }, { text: ` ${L(ctx, 'ws_unit_ist')}` }]],
			alert: false,
			tags: [],
			figures: keyFigures([
				{ caption: L(ctx, 'ws_fig_time'), value: null, time: row.t, unit: L(ctx, 'ws_unit_ist') },
				{ caption: L(ctx, 'ws_fig_speed'), value: speed != null ? Math.round(speed) : null, unit: L(ctx, 'ws_unit_kmh') },
				{ caption: L(ctx, 'ws_fig_heading'), value: heading != null ? compass(heading, ctx.lang) : null },
			]),
			note: null,
			groups: groups(
				{
					title: L(ctx, 'ws_grp_identity'),
					rows: [
						{ key: L(ctx, 'ws_p_mark'), value: { t: 'plate', mark, masked, hint: masked ? L(ctx, 'ws_v_masked') : null } },
						objectRow(L(ctx, 'ws_p_vehicle'), vehicle),
						camera ? objectRow(L(ctx, 'ws_p_camera'), camera) : cam ? { key: L(ctx, 'ws_p_camera'), value: { t: 'id', v: cam } } : null,
						textRow(L(ctx, 'ws_p_matched'), str(p.matched_plate_hit) ? human(p.matched_plate_hit) : null),
						textRow(L(ctx, 'ws_p_lawful'), str(vehicle?.props.lawful_basis) ? human(vehicle?.props.lawful_basis) : null),
					],
				},
				{ title: L(ctx, 'ws_grp_provenance'), rows: provenanceRows(row, ctx, row.source === 'emulated' ? L(ctx, 'ws_v_emulator_anpr') : null) },
			),
			system: systemRows(row),
			plate: { mark, masked },
		};
	},
};
