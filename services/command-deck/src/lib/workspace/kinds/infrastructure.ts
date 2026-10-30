/**
 * Junction, road segment, unit, convoy and feed anomaly. Junctions and
 * roads are infrastructure (they never fade in a time window); units and
 * convoys are live positions (emulated units say so); anomalies stand on the
 * signal-ingress feed, which reads 'simulated' while that feed is synthetic.
 */
import { human } from '../vocabulary';
import { L, baseRow, compass, groups, intentOf, keyFigures, ms, num, objectRow, rec, str, systemRows, textRow, urnFrom } from './common';
import { kindOne, provenanceRows, stateTags, type KindAdapter } from './generic';

export const junctionAdapter: KindAdapter = {
	kind: 'junction',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		const p = e.props;
		return { ...row, label: str(p.name) ?? row.label, sublabel: str(p.junction_type) ? human(p.junction_type) : null, stateIntent: 'none' };
	},
	view(row, ctx) {
		const p = row.props;
		const ap = rec(p.active_phase);
		const cycle = num(p.cycle_sec);
		const green = num(p.green_ratio);
		return {
			title: [{ text: row.label }],
			plateTitle: false,
			subtitle: [[{ text: kindOne('junction', ctx.lang) }], ...(row.sublabel ? [[{ text: row.sublabel }]] : [])],
			alert: false,
			tags: [],
			figures: keyFigures(
				cycle != null
					? [
							{ caption: L(ctx, 'ws_fig_cycle'), value: cycle, unit: L(ctx, 'ws_unit_s') },
							{ caption: L(ctx, 'ws_fig_green'), value: green != null ? Math.round(green * 100) : null, unit: L(ctx, 'ws_unit_pct') },
							{ caption: L(ctx, 'ws_fig_phase'), value: num(ap.index) },
							{ caption: L(ctx, 'ws_fig_remaining'), value: num(ap.remaining_sec), unit: L(ctx, 'ws_unit_s') },
						]
					: [],
			),
			note: null,
			groups: groups(
				{
					title: L(ctx, 'ws_grp_identity'),
					rows: [textRow(L(ctx, 'ws_p_name'), str(p.name)), textRow(L(ctx, 'ws_p_name_mr'), str(p.name_mr)), textRow(L(ctx, 'ws_p_type'), row.sublabel)],
				},
				{
					title: L(ctx, 'ws_grp_signal'),
					rows: [
						textRow(L(ctx, 'ws_p_signal_control'), p.signal_control === true ? L(ctx, 'ws_v_yes') : p.signal_control === false ? L(ctx, 'ws_v_no') : null),
						textRow(L(ctx, 'ws_p_program'), str(p.program_source) ? human(p.program_source) : null),
						textRow(L(ctx, 'ws_p_phase_basis'), str(p.phase_basis) ? human(p.phase_basis) : null),
						// FIX-G-ORACLE (HON-10): the phase is PLANNED from the stored program — said in words
						textRow(L(ctx, 'ws_p_phase_status'), str(p.phase_status) || p.live_phase === false ? L(ctx, 'ws_v_phase_planned') : null),
					],
				},
				{ title: L(ctx, 'ws_grp_provenance'), rows: provenanceRows(row, ctx) },
			),
			system: systemRows(row),
			plate: null,
		};
	},
};

export const segmentAdapter: KindAdapter = {
	kind: 'segment',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		const p = e.props;
		return { ...row, label: str(p.road_name) ?? row.label, sublabel: str(p.road_class) ? human(p.road_class) : null, stateIntent: 'none' };
	},
	view(row, ctx) {
		const p = row.props;
		const speed = num(p.speed_kmh);
		const cong = num(p.congestion_idx);
		const len = num(p.length_m);
		// the road class in the reader's language (the V3 pack's word, where the page loaded it), else the English one
		const code = str(p.road_class);
		const local = code && ctx.lang !== 'en' ? L(ctx, `v3_road_${code}`) : null;
		const cls = local && local !== `v3_road_${code}` ? local : row.sublabel;
		return {
			title: [{ text: row.label }],
			plateTitle: false,
			subtitle: [[{ text: kindOne('segment', ctx.lang) }], ...(cls ? [[{ text: cls }]] : [])],
			alert: false,
			tags: [],
			figures: keyFigures([
				{ caption: L(ctx, 'ws_fig_speed'), value: speed != null ? Math.round(speed) : null, unit: L(ctx, 'ws_unit_kmh') },
				{ caption: L(ctx, 'ws_fig_congestion'), value: cong != null ? Math.round(cong * 100) : null, unit: L(ctx, 'ws_unit_pct') },
				{ caption: L(ctx, 'ws_fig_limit'), value: num(p.speed_limit_kmh), unit: L(ctx, 'ws_unit_kmh') },
				{ caption: L(ctx, 'ws_fig_lanes'), value: num(p.lanes) },
			]),
			note: null,
			groups: groups(
				{
					title: L(ctx, 'ws_grp_road'),
					rows: [
						textRow(L(ctx, 'ws_p_class'), cls),
						textRow(L(ctx, 'ws_p_oneway'), p.oneway === true ? L(ctx, 'ws_v_yes') : p.oneway === false ? L(ctx, 'ws_v_no') : null),
						textRow(L(ctx, 'ws_p_length'), len != null ? `${Math.round(len)} m` : null),
					],
				},
				{ title: L(ctx, 'ws_grp_provenance'), rows: provenanceRows(row, ctx) },
			),
			system: systemRows(row),
			plate: null,
		};
	},
};

export const unitAdapter: KindAdapter = {
	kind: 'unit',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		const p = e.props;
		const agency = str(p.agency_label) ?? (str(p.agency) ? human(p.agency) : null);
		return { ...row, label: e.id, sublabel: agency, stateIntent: intentOf(e.state) === 'warning' ? 'warning' : 'none' };
	},
	implied(row) {
		return [urnFrom('junction', row.props.waypoint_junction)].filter((u): u is string => !!u);
	},
	view(row, ctx) {
		const p = row.props;
		const eta = num(p.eta_sec);
		const progress = num(p.progress);
		const waypoint = ctx.graph.get(urnFrom('junction', p.waypoint_junction));
		return {
			title: [{ id: row.id }],
			plateTitle: false,
			subtitle: [[{ text: kindOne('unit', ctx.lang) }], ...(row.sublabel ? [[{ text: row.sublabel }]] : [])],
			alert: false,
			tags: stateTags(row, ctx),
			// the state is the header's tag; the key figures are numbers
			figures: keyFigures([
				{ caption: L(ctx, 'ws_fig_eta'), value: eta != null ? Math.round(eta / 60) : null, unit: L(ctx, 'ws_unit_min') },
				{ caption: L(ctx, 'ws_fig_progress'), value: progress != null ? Math.round(progress * 100) : null, unit: L(ctx, 'ws_unit_pct') },
			]),
			note: null,
			groups: groups(
				{
					title: L(ctx, 'ws_grp_identity'),
					rows: [textRow(L(ctx, 'ws_p_agency'), row.sublabel), waypoint ? objectRow(L(ctx, 'ws_p_waypoint'), waypoint) : null],
				},
				{ title: L(ctx, 'ws_grp_provenance'), rows: provenanceRows(row, ctx) },
			),
			system: systemRows(row),
			plate: null,
		};
	},
};

export const convoyAdapter: KindAdapter = {
	kind: 'convoy',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		const speed = num(e.props.speed_kmh);
		return { ...row, sublabel: speed != null ? `${Math.round(speed)} km/h` : null, stateIntent: 'none' };
	},
	implied(row) {
		return [urnFrom('event', row.props.event_id)].filter((u): u is string => !!u);
	},
	view(row, ctx) {
		const p = row.props;
		const speed = num(p.speed_kmh);
		const progress = num(p.progress);
		const gps = str(p.position_source);
		return {
			title: [{ text: row.label }],
			plateTitle: false,
			subtitle: [[{ text: kindOne('convoy', ctx.lang) }]],
			alert: false,
			tags: [],
			figures: keyFigures([
				{ caption: L(ctx, 'ws_fig_speed'), value: speed != null ? Math.round(speed) : null, unit: L(ctx, 'ws_unit_kmh') },
				{ caption: L(ctx, 'ws_fig_heading'), value: num(p.heading) != null ? compass(num(p.heading), ctx.lang) : null },
				{ caption: L(ctx, 'ws_fig_progress'), value: progress != null ? Math.round(progress * 100) : null, unit: L(ctx, 'ws_unit_pct') },
			]),
			note: null,
			groups: groups(
				{
					title: L(ctx, 'ws_grp_identity'),
					rows: [
						{ key: L(ctx, 'ws_p_movement'), value: { t: 'id', v: String(p.movement_id ?? row.id) } },
						textRow(L(ctx, 'ws_p_position'), gps === 'emulated_gps' ? L(ctx, 'ws_v_emulated_gps') : gps ? human(gps) : null),
					],
				},
				{ title: L(ctx, 'ws_grp_provenance'), rows: provenanceRows(row, ctx) },
			),
			system: systemRows(row),
			plate: null,
		};
	},
};

export const anomalyAdapter: KindAdapter = {
	kind: 'anomaly',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		const p = e.props;
		const type = str(p.anomaly_type) ? human(p.anomaly_type) : row.label;
		const road = str(p.road_name);
		return { ...row, label: road ? `${type} · ${road}` : type, sublabel: str(p.severity) ? human(p.severity) : null, stateIntent: 'none', t: ms(p.flagged_at) ?? e.t };
	},
	implied(row) {
		return [urnFrom('segment', row.props.segment_id)].filter((u): u is string => !!u);
	},
	view(row, ctx) {
		const p = row.props;
		const segment = ctx.graph.get(urnFrom('segment', p.segment_id));
		const flags = Array.isArray(p.anomaly_flags) ? (p.anomaly_flags as unknown[]).map((f) => human(f)).join(', ') : null;
		return {
			title: [{ text: row.label }],
			plateTitle: false,
			subtitle: [[{ text: kindOne('anomaly', ctx.lang) }], ...(row.t != null ? [[{ time: row.t }, { text: ` ${L(ctx, 'ws_unit_ist')}` }]] : [])],
			alert: false,
			tags: [],
			figures: keyFigures([
				{ caption: L(ctx, 'ws_fig_severity'), value: str(p.severity) ? human(p.severity) : null },
				{ caption: L(ctx, 'ws_fig_in_15m'), value: num(p.count_15m) },
			]),
			note: null,
			groups: groups(
				{
					title: L(ctx, 'ws_grp_identity'),
					rows: [
						textRow(L(ctx, 'ws_p_type'), str(p.anomaly_type) ? human(p.anomaly_type) : null),
						segment ? objectRow(L(ctx, 'ws_p_road'), segment) : textRow(L(ctx, 'ws_p_road'), str(p.road_name)),
						textRow(L(ctx, 'ws_p_flags'), flags),
					],
				},
				{ title: L(ctx, 'ws_grp_provenance'), rows: provenanceRows(row, ctx) },
			),
			system: systemRows(row),
			plate: null,
		};
	},
};
