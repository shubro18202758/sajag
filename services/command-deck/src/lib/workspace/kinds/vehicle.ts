/**
 * Vehicle — a watchlist entry (the registry carries earmarked vehicles only).
 * Its label is the masked mark; its view shows the lawful basis, retention,
 * the last read and the decisions on it. Every vehicle carries the red
 * Watchlist tag and a red ring (SPEC §2.4: red ring = watchlist or stolen);
 * a stolen one also carries the rule note "Evidence only" (SPEC §5.3).
 */
import { ACTION_ICON, INTENT_ICON } from '$lib/design/icons';
import { fmtAgo } from '$lib/ui/format/format';
import { maskPlate } from '$lib/gods-eye/plates';
import { displayReason, displayScenario, displayText } from '../display';
import { readsOf } from '../selectors';
import { human } from '../vocabulary';
import {
	L,
	baseRow,
	compass,
	daysLeft,
	groups,
	keyFigures,
	linkedBy,
	ms,
	num,
	objectRow,
	shownText,
	str,
	systemRows,
	textRow,
	urnFrom,
	type PropRow,
	type ViewTag,
} from './common';
import { kindOne, provenanceRows, type KindAdapter } from './generic';

const STOLEN = 'stolen_vehicle_fir';

/** The masked mark of a vehicle row. */
export function vehicleMark(props: Readonly<Record<string, unknown>>, label: string): string {
	return str(props.plate_masked) ?? maskPlate(str(props.plate)) ?? label;
}

export const vehicleAdapter: KindAdapter = {
	kind: 'vehicle',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		const p = e.props;
		const state = str(p.earmark_state) ?? e.state;
		return {
			...row,
			label: vehicleMark(p, row.label),
			masked: true,
			state,
			stateIntent: state === 'flagged' ? 'danger' : row.stateIntent,
			// data, not chrome: the class in words ("Car"); the watchlist and stolen states are the views'
			// own words in every language (the Watchlist tag, the omnibar's subtitle)
			sublabel: str(p.vehicle_class) ? human(p.vehicle_class) : null,
		};
	},
	implied(row) {
		const cam = urnFrom('camera', row.props.last_camera_id);
		const read = urnFrom('sighting', row.props.last_sighting_id);
		return [cam, read].filter((u): u is string => !!u);
	},
	view(row, ctx) {
		const p = row.props;
		const raw = str(p.plate);
		const masked = !ctx.officer || !raw;
		const mark = masked ? row.label : (ctx.plate(raw) ?? row.label);
		const stolen = str(p.lawful_basis) === STOLEN;
		const lastCam = str(p.last_camera_id);
		// the canonical reads (selectors.readsOf): every linked sighting with a time, whatever the relation
		const reads = readsOf(ctx.links, row.urn);
		const recs = linkedBy(ctx, 'recommendation');
		const n = (st: string) => recs.filter((r) => r.state === st).length;
		const retention = ms(p.retention_until);
		const days = daysLeft(retention, ctx.now);
		const speed = num(p.last_speed_kmh);
		const heading = num(p.last_heading);

		const tags: ViewTag[] = [{ text: L(ctx, 'ws_tag_watchlist'), intent: 'danger', icon: 'flag' }];
		if (stolen) tags.push({ text: L(ctx, 'ws_tag_stolen'), intent: 'danger', icon: INTENT_ICON.danger });

		const figures = keyFigures([
			{ caption: L(ctx, 'ws_fig_last_read'), value: null, time: row.t, unit: L(ctx, 'ws_unit_ist'), hint: row.t != null ? fmtAgo(row.t, ctx.now, ctx.lang) : null },
			{ caption: L(ctx, 'ws_fig_last_speed'), value: speed != null ? Math.round(speed) : null, unit: L(ctx, 'ws_unit_kmh') },
			{ caption: L(ctx, 'ws_fig_reads'), value: reads.length, hint: L(ctx, 'ws_hint_reads') },
			{ caption: L(ctx, 'ws_fig_retention'), value: days, unit: L(ctx, 'ws_unit_days') },
		]);

		const decisionTags: ViewTag[] = [];
		if (n('pending')) decisionTags.push({ text: L(ctx, 'ws_n_pending', n('pending')), intent: 'warning' });
		if (n('approved')) decisionTags.push({ text: L(ctx, 'ws_n_approved', n('approved')), intent: 'success' });
		if (n('rejected')) decisionTags.push({ text: L(ctx, 'ws_n_rejected', n('rejected')), intent: 'none' });

		const camRow = lastCam ? (ctx.graph.get(`camera:${lastCam}`) ?? null) : null;
		const speedHeading: PropRow | null =
			speed != null ? { key: L(ctx, 'ws_p_speed_heading'), value: { t: 'text', v: `${Math.round(speed)} ${L(ctx, 'ws_unit_kmh')} · ${compass(heading, ctx.lang)}` } } : null;

		return {
			title: [{ plate: mark, masked }],
			plateTitle: true,
			subtitle: [
				[{ text: kindOne('vehicle', ctx.lang) }],
				...(str(p.vehicle_class) ? [[{ text: human(p.vehicle_class) }]] : []),
				...(row.t != null
					? [
							[
								{ text: `${L(ctx, 'ws_sub_last_read')} ` },
								{ time: row.t },
								{ text: ` ${L(ctx, 'ws_unit_ist')}` },
								...(lastCam ? [{ text: ` ${L(ctx, 'ws_sub_at')} ` }, { id: lastCam }] : []),
							],
						]
					: []),
			],
			// every vehicle in the city picture is a watchlist entry and carries the red Watchlist tag above: its ring is red too
			alert: true,
			tags,
			figures,
			note: stolen ? { icon: ACTION_ICON.rule_no_fine, title: L(ctx, 'ws_note_stolen_title'), text: L(ctx, 'ws_note_stolen') } : null,
			groups: groups(
				{
					title: L(ctx, 'ws_grp_identity'),
					rows: [
						{ key: L(ctx, 'ws_p_mark'), value: { t: 'plate', mark, masked, hint: masked ? L(ctx, 'ws_v_masked') : null } },
						textRow(L(ctx, 'ws_p_class'), str(p.vehicle_class) ? human(p.vehicle_class) : null),
					],
				},
				{
					title: L(ctx, 'ws_grp_lawful'),
					rows: [
						textRow(L(ctx, 'ws_p_basis'), str(p.lawful_basis) ? human(p.lawful_basis) : null),
						// the earmark reason is officer-typed and sent RAW (it may name the mark): raw only for a named officer
						textRow(L(ctx, 'ws_p_reported'), shownText(ctx, displayReason(str(p.earmark_reason)))),
						retention != null
							? { key: L(ctx, 'ws_p_retention'), value: { t: 'time', ms: retention, hint: days != null ? L(ctx, 'ws_days_left', days) : null } }
							: null,
						textRow(L(ctx, 'ws_p_privacy'), str(p.privacy_note) ? shownText(ctx, displayText(str(p.privacy_note))) : null),
					],
				},
				{
					title: L(ctx, 'ws_grp_last_read'),
					rows: [
						camRow ? objectRow(L(ctx, 'ws_p_camera'), camRow) : lastCam ? { key: L(ctx, 'ws_p_camera'), value: { t: 'id', v: lastCam } } : null,
						row.t != null ? { key: L(ctx, 'ws_p_time'), value: { t: 'time', ms: row.t, seconds: true, hint: fmtAgo(row.t, ctx.now, ctx.lang) } } : null,
						speedHeading,
					],
				},
				{
					title: L(ctx, 'ws_grp_decisions'),
					rows: [decisionTags.length ? { key: L(ctx, 'ws_p_recommendations'), value: { t: 'tags', tags: decisionTags } } : null],
				},
				{
					title: L(ctx, 'ws_grp_provenance'),
					rows: provenanceRows(row, ctx, row.source === 'emulated' ? L(ctx, 'ws_v_emulator_anpr') : null),
				},
			),
			system: systemRows(row, { lawful_basis: p.lawful_basis, scenario: displayScenario(str(p.earmark_reason)) }),
			plate: { mark, masked },
		};
	},
};
