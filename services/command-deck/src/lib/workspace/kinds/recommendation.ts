/**
 * Recommendation — a rule's proposal that a named officer decides: an
 * e-challan (R_SPD_SEGMENT) or a stolen-vehicle sighting on file
 * (R_STOLEN_SIGHTING, evidence only). Also built from history records (the
 * ops store's recommendation lists) through `recommendationRow`.
 *
 * The oracle's withheld note ("e-challan withheld (vehicle reported stolen,
 * FIR …)") is shown verbatim (SPEC §12.5).
 */
import { ACTION_ICON, ACTOR_ICON, kindIcon } from '$lib/design/icons';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.workspace';
import { maskPlate } from '$lib/gods-eye/plates';
import { actorName, actorParts, capFirst, displayText } from '../display';
import { HUMAN, human } from '../vocabulary';
import type { ObjectRow } from '../types';
import {
	L,
	anyTest,
	baseRow,
	groups,
	keyFigures,
	maskedRow,
	ms,
	num,
	objectRow,
	rec,
	shownText,
	str,
	systemRows,
	textRow,
	timeRow,
	urnFrom,
	type RuleNote,
} from './common';
import { kindOne, provenanceRows, stateTags, stateWord, type KindAdapter } from './generic';

const STOLEN_RULE = 'R_STOLEN_SIGHTING';

/**
 * The rule in words ("Stolen-vehicle sighting", "Speeding on segment"), in
 * `lang`: a known rule has a pack key (`ws_rule_<RULE_ID>`); any other rule
 * code reads in words (EN). Row labels use EN (the search matches them);
 * the views pass their language.
 */
export function ruleWords(ruleId: unknown, lang = 'en'): string {
	const id = str(ruleId);
	if (!id) return t(lang, 'ws_kind_recommendation');
	const key = `ws_rule_${id}`;
	const named = t(lang, key);
	return named !== key ? named : (HUMAN[id] ?? human(id));
}

function fields(row: ObjectRow) {
	const p = row.props;
	const ev = rec(p.evidence);
	return {
		rule: str(p.rule_id),
		camera: str(ev.camera_id) ?? str(p.camera_id),
		road: str(ev.road_name),
		speed: num(ev.speed_kmh),
		limit: num(ev.speed_limit_kmh),
		segment: num(ev.segment_id),
		created: ms(p.created_at),
		decidedAt: ms(p.decided_at),
		decidedBy: str(p.decided_by),
	};
}

export const recommendationAdapter: KindAdapter = {
	kind: 'recommendation',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		const p = e.props;
		const ev = rec(p.evidence);
		const state = str(p.status) ?? e.state;
		const camera = str(ev.camera_id) ?? str(p.camera_id);
		return {
			...row,
			label: camera ? `${ruleWords(p.rule_id)} · ${camera}` : ruleWords(p.rule_id),
			sublabel: str(ev.road_name),
			masked: true,
			state,
			stateIntent: state === 'pending' ? 'warning' : state === 'approved' ? 'success' : 'none',
			t: ms(p.created_at) ?? e.t,
			test: row.test || anyTest(p.decided_by),
		};
	},
	implied(row) {
		const p = row.props;
		const ev = rec(p.evidence);
		const pursuit = rec(p.pursuit);
		return [
			urnFrom('vehicle', p.vehicle_id),
			urnFrom('sighting', p.sighting_id),
			urnFrom('segment', ev.segment_id),
			urnFrom('event', pursuit.event_id),
		].filter((u): u is string => !!u);
	},
	view(row, ctx) {
		const p = row.props;
		const f = fields(row);
		const raw = str(p.plate);
		const masked = !ctx.officer || !raw;
		const mark = masked ? (str(p.plate_masked) ?? maskPlate(raw)) : (ctx.plate(raw) ?? str(p.plate_masked));
		const stolenRule = f.rule === STOLEN_RULE;
		const vehicle = ctx.graph.get(urnFrom('vehicle', p.vehicle_id));
		const read = ctx.graph.get(urnFrom('sighting', p.sighting_id));
		const camera = ctx.graph.get(urnFrom('camera', f.camera));
		const decider = f.decidedBy ? actorParts(f.decidedBy) : null;

		// Key figures are numbers and times (SPEC §5.3 metric type); the state is the header's tag, said once.
		// A figure with no value is dropped: an undecided proposal shows no "Decided —".
		const figures = keyFigures([
			{ caption: L(ctx, 'ws_fig_speed'), value: f.speed != null ? Math.round(f.speed) : null, unit: L(ctx, 'ws_unit_kmh') },
			{ caption: L(ctx, 'ws_fig_filed'), value: null, time: f.created, unit: L(ctx, 'ws_unit_ist') },
			{ caption: L(ctx, 'ws_fig_decided'), value: null, time: f.decidedAt, unit: L(ctx, 'ws_unit_ist') },
		]);

		const note: RuleNote | null = stolenRule
			? { icon: ACTION_ICON.rule_no_fine, title: L(ctx, 'ws_note_stolen_title'), text: L(ctx, 'ws_note_stolen') }
			: row.state === 'pending'
				? { icon: ACTOR_ICON.officer, title: null, text: L(ctx, 'ws_note_officer_decides') }
				: null;

		const speedText =
			f.speed != null ? (f.limit != null ? L(ctx, 'ws_v_speed_in_zone', Math.round(f.speed), Math.round(f.limit)) : `${Math.round(f.speed)} ${L(ctx, 'ws_unit_kmh')}`) : null;

		return {
			title: [{ text: `${ruleWords(f.rule, ctx.lang)}${f.camera ? ' · ' : ''}` }, ...(f.camera ? [{ id: f.camera }] : [])],
			plateTitle: false,
			subtitle: [
				[{ text: kindOne('recommendation', ctx.lang) }],
				[{ text: L(ctx, 'ws_sub_filed_by_rules') }],
				...(mark ? [[{ plate: mark, masked }]] : []),
				...(f.created != null ? [[{ time: f.created }, { text: ` ${L(ctx, 'ws_unit_ist')}` }]] : []),
			],
			alert: false,
			tags: stateTags(row, ctx),
			figures,
			note,
			groups: groups(
				{
					title: L(ctx, 'ws_grp_decision'),
					rows: [
						textRow(L(ctx, 'ws_p_status'), stateWord(row.state, ctx.lang)),
						decider
							? textRow(L(ctx, 'ws_p_decided_by'), actorName(decider, ctx.lang), decider.scenario)
							: textRow(L(ctx, 'ws_p_decided_by'), L(ctx, 'ws_v_waiting_officer')),
						timeRow(L(ctx, 'ws_p_decided'), p.decided_at),
						// the oracle's proposal text carries the RAW mark ("e-challan recommended: <mark> read at …"):
						// shown raw only for a named duty officer (SPEC §9.3)
						textRow(L(ctx, 'ws_p_proposal'), str(p.recommendation) ? shownText(ctx, capFirst(displayText(str(p.recommendation)))) : null),
						// the oracle's withheld note, verbatim (SPEC §12.5)
						textRow(L(ctx, 'ws_p_rule'), shownText(ctx, str(p.withheld_text))),
					],
				},
				{
					title: L(ctx, 'ws_grp_evidence'),
					rows: [
						mark ? { key: L(ctx, 'ws_p_mark'), value: { t: 'plate', mark, masked, hint: masked ? L(ctx, 'ws_v_masked') : null } } : null,
						objectRow(L(ctx, 'ws_p_vehicle'), vehicle),
						objectRow(L(ctx, 'ws_p_read'), read),
						camera ? objectRow(L(ctx, 'ws_p_camera'), camera) : f.camera ? { key: L(ctx, 'ws_p_camera'), value: { t: 'id', v: f.camera } } : null,
						textRow(L(ctx, 'ws_p_road'), f.road),
						textRow(L(ctx, 'ws_p_speed'), speedText),
					],
				},
				{ title: L(ctx, 'ws_grp_provenance'), rows: provenanceRows(row, ctx) },
			),
			system: systemRows(row, { rule_id: f.rule, decided_by: f.decidedBy }),
			plate: mark ? { mark, masked } : null,
		};
	},
};

/**
 * A recommendation known only from history (the ops store's lists: GET
 * /enforcement/recommendations), as a row. Providers register these
 * through registerObjectSource.
 */
export function recommendationRow(r: Record<string, unknown>): ObjectRow | null {
	const id = str(r.recommendation_id) ?? str(r.id);
	if (!id) return null;
	const ev = rec(r.evidence);
	const state = str(r.status);
	const camera = str(ev.camera_id) ?? str(r.camera_id);
	const plateMasked = str(r.plate_masked) ?? maskPlate(str(r.plate));
	return maskedRow({
		urn: `recommendation:${id}`,
		kind: 'recommendation',
		id,
		label: camera ? `${ruleWords(r.rule_id)} · ${camera}` : ruleWords(r.rule_id),
		sublabel: str(ev.road_name),
		icon: kindIcon('recommendation'),
		state,
		stateIntent: state === 'pending' ? 'warning' : state === 'approved' ? 'success' : 'none',
		t: ms(r.created_at),
		end: ms(r.decided_at),
		lon: num(ev.lon),
		lat: num(ev.lat),
		// the coercion rule of plan X4: emulated and osint kept, anything else live
		source: r.source === 'emulated' || r.emulated === true ? 'emulated' : r.source === 'osint' ? 'osint' : 'live',
		verification: null,
		credibility: null,
		test: anyTest(r.decided_by),
		masked: true,
		props: { ...r, plate: undefined, plate_masked: plateMasked },
	});
}
