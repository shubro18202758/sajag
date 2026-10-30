/**
 * The generic adapter (plan X5): every city entity kind without an adapter
 * of its own — `osint_event`, `place`, and any kind a later contract adds —
 * still yields an ObjectRow (kind glyph, masked label through displayTitle,
 * provenance from source and verification) and an inspector view. So OSINT
 * objects appear in the omnibar, table, graph and inspector before any
 * provider registers their sections.
 */
import { parseUrn, type CityEntity } from '$lib/gods-eye/city-api';
import { classWord, contextNoteKeys, geocodeBucket, objectValue, relatedObject, situationClass, tagsValue } from '$lib/osint/model';
import { human } from '../vocabulary';
import type { ObjectRow } from '../types';
import {
	L,
	baseRow,
	groups,
	keyFigures,
	ms,
	num,
	rec,
	str,
	systemRows,
	textRow,
	timeRow,
	timeRun,
	type Figure,
	type InspectorView,
	type PropRow,
	type RowCtx,
	type Run,
	type ViewCtx,
	type ViewTag,
} from './common';

/**
 * A link a row's props imply: a URN (the kinds name it), or a URN with the
 * relation the props themselves name — `promoted_event_id` is "Promoted
 * to", `attach.corroborates_live_urn` is "Corroborates" (contract C-T). A
 * named one outranks an unnamed snapshot link between the same objects.
 */
export type ImpliedLink = string | { urn: string; rel: string };

export interface KindAdapter {
	kind: string;
	/** The row a city entity becomes. */
	row(e: CityEntity, ctx: RowCtx): ObjectRow;
	/** The links the row's props imply (rows from history carry no `links`). */
	implied?(row: ObjectRow): readonly ImpliedLink[];
	/** The inspector's view of the row. */
	view(row: ObjectRow, ctx: ViewCtx): InspectorView;
}

/** The kind's singular name ("Vehicle", "Reported event"; unknown kinds in words). */
export function kindOne(kind: string, lang: string): string {
	const key = `ws_kind_${kind}`;
	const v = L({ lang }, key);
	return v === key ? human(kind) : v;
}

/** The kind's plural name ("Vehicles", "Reported events"). */
export function kindMany(kind: string, lang: string): string {
	const key = `ws_kinds_${kind}`;
	const v = L({ lang }, key);
	return v === key ? human(kind) : v;
}

/** A state as a word ("Needs decision", "Approved"), or null. An OSINT row state
 * ('surfaced') has no workspace key — it reads the osint pack's own `os_state_*` in the
 * VIEW's language (the caller passes ctx.lang; pickLang routes through onLangChange, so the
 * shell's own lang stays at its boot value while the OSINT surfaces switch — fix round 2:
 * the header state tag localizes in HI/MR too). */
export function stateWord(state: string | null, lang: string): string | null {
	if (!state) return null;
	const key = `ws_state_${state}`;
	const v = L({ lang }, key);
	if (v !== key) return v;
	const osKey = `os_state_${state}`;
	const os = L({ lang }, osKey);
	return os === osKey ? human(state) : os;
}

/** A state in one short word for list rows ("Pending" where a header says "Needs decision"). */
export function shortStateWord(state: string | null, lang: string): string | null {
	if (!state) return null;
	const key = `ws_short_${state}`;
	const v = L({ lang }, key);
	return v === key ? stateWord(state, lang) : v;
}

/** The state tag of a row (none for a neutral state the subtitle already says). */
export function stateTags(row: ObjectRow, ctx: ViewCtx): ViewTag[] {
	const word = stateWord(row.state, ctx.lang);
	return word ? [{ text: word, intent: row.stateIntent }] : [];
}

/** The verification label in words (osint rows), or null. */
export function verificationWord(v: string | null, lang: string): string | null {
	if (!v) return null;
	const key = `ws_verif_${v.toLowerCase().replace(/-/g, '_')}`;
	const out = L({ lang }, key);
	return out === key ? v : out;
}

/**
 * The Provenance group every view ends with. `deduped` drops the
 * verification word and the credibility rows — for an `osint_event` the
 * inspector's header tag and the report section carry both exactly once
 * (item 7) — and reads the Source row as PLAIN TEXT (a `text` value, never
 * a ProvenanceTag): with the header and the section tags already carrying
 * the verification, a third tag here rendered the same words again (item 7,
 * fix round 2).
 */
export function provenanceRows(row: ObjectRow, ctx: ViewCtx, sourceText?: string | null, deduped = false): PropRow[] {
	const rows: PropRow[] = [];
	const text =
		sourceText ??
		(row.source === 'emulated'
			? L(ctx, 'ws_v_emulator')
			: row.source === 'simulated'
				? L(ctx, 'ws_v_simulated_feed')
				: row.source === 'osint'
					? L(ctx, 'ws_v_osint')
					: L(ctx, 'ws_v_live'));
	if (deduped) {
		const r = textRow(L(ctx, 'ws_p_source'), text);
		if (r) rows.push(r);
		return rows;
	}
	rows.push({ key: L(ctx, 'ws_p_source'), value: { t: 'source', source: row.source, verification: row.verification, text } });
	const verif = verificationWord(row.verification, ctx.lang);
	if (verif && row.source === 'osint') {
		const r = textRow(L(ctx, 'ws_p_verification'), verif);
		if (r) rows.push(r);
	}
	if (row.credibility != null) {
		const r = textRow(L(ctx, 'ws_p_credibility'), row.credibility.toFixed(2));
		if (r) rows.push(r);
	}
	return rows;
}

/** The osint_event Properties groups' Situation rows (item 7, round 2: moved out of the compact report section). */
function osintSituationRows(row: ObjectRow, ctx: ViewCtx): PropRow[] {
	const p = row.props;
	const rows: PropRow[] = [];
	const kind = situationClass(str(p.sajag_event_kind), ctx.lang);
	if (kind) rows.push({ key: L(ctx, 'os_class'), value: { t: 'text', v: kind }, testid: 'osint-class' });
	const subtype = str(p.subtype);
	if (subtype) {
		const r = textRow(L(ctx, 'os_subtype'), classWord(subtype));
		if (r) rows.push(r);
	}
	const correlated = (Array.isArray(p.correlated_classes) ? p.correlated_classes : []).filter((c): c is string => typeof c === 'string' && !!c.trim());
	if (correlated.length > 1) {
		rows.push({ key: L(ctx, 'os_correlated'), value: tagsValue(correlated.map((c) => classWord(c))), testid: 'osint-correlated' });
	}
	return rows;
}

/** The osint_event Properties groups' Location rows (moved out of the compact report section, item 7 round 2). */
function osintLocationRows(row: ObjectRow, ctx: ViewCtx): PropRow[] {
	const p = row.props;
	const rows: PropRow[] = [];
	const seg = num(p.segment_id);
	if (seg != null) {
		const linked = relatedObject(ctx.dossier, 'on_road');
		rows.push({
			key: L(ctx, 'os_road'),
			value: objectValue(linked?.urn ?? `segment:${seg}`, 'segment', linked?.label ?? `Segment ${seg}`),
			testid: 'osint-road',
		});
	}
	const jct = num(p.junction_id);
	if (jct != null) {
		const linked = relatedObject(ctx.dossier, 'at_junction');
		rows.push({
			key: L(ctx, 'os_junction'),
			value: objectValue(linked?.urn ?? `junction:${jct}`, 'junction', linked?.label ?? `Junction ${jct}`),
			testid: 'osint-junction',
		});
	}
	const confidence = num(p.geocode_confidence);
	if (confidence != null) {
		const bucket = geocodeBucket(confidence);
		// an AREA-level report is a district-scale figure: the row's hint says why it is not a
		// street location (the compact section's district note, visible here instead)
		rows.push({
			key: L(ctx, 'os_geocode'),
			value: { t: 'text', v: `${confidence.toFixed(2)} · ${L(ctx, `os_bucket_${bucket ?? 'low'}`)}`, hint: p.area_level === true ? L(ctx, 'os_area_note') : null },
		});
	}
	return rows;
}

function genericView(row: ObjectRow, ctx: ViewCtx): InspectorView {
	const p = row.props;
	const figures: Figure[] = [];
	// a place counts the open-source reports linked to it
	if (row.kind === 'place') figures.push({ caption: L(ctx, 'ws_fig_reports'), value: ctx.links.filter((l) => l.row.kind === 'osint_event').length });
	// the credibility figure — the ONE place an OSINT report's credibility is a figure (item 7:
	// the report section carries no credibility row of its own)
	if (row.credibility != null) figures.push({ caption: L(ctx, 'ws_fig_credibility'), value: row.credibility.toFixed(2) });
	// the sources figure counts REPORTS: C-T keeps source_count == every member, a district
	// CONTEXT member included — context is never corroboration. The oracle's own
	// ``context_members`` count (its entities prop) is the truth; the distinct, capped
	// context_publishers length is only the fallback when the prop has not arrived. The count
	// stays short (a word figure never widens its cell, so a long value would truncate); the
	// context note — the deck's OWN two translated keys (official vs report), never the
	// oracle's EN string — is the figure's visible second line (`sub`).
	const sources = num(p.source_count);
	if (sources != null) {
		const prov = rec(p.provenance);
		const members = num(p.context_members);
		const context = members != null ? members : Array.isArray(prov.context_publishers) ? prov.context_publishers.length : 0;
		const reports = Math.max(1, sources - context); // a situation stands on ≥ 1 report
		const count = L(ctx, reports === 1 ? 'ui_fig_report' : 'ui_fig_reports', reports);
		const note = context > 0 ? L(ctx, contextNoteKeys(str(prov.context_note)).figure) : null;
		figures.push({ caption: L(ctx, 'ws_fig_sources'), value: count, sub: note });
	}
	if (row.t != null) figures.push({ caption: L(ctx, 'ws_fig_time'), value: null, time: row.t, unit: L(ctx, 'ws_unit_ist') });
	const subtitle: Run[][] = [[{ text: kindOne(row.kind, ctx.lang) }]];
	if (row.sublabel) subtitle.push([{ text: row.sublabel }]);
	// a report's window is one range at one precision (SPEC §3.3)
	if (row.t != null) subtitle.push([timeRun(row.t, row.end), { text: ` ${L(ctx, 'ws_unit_ist')}` }]);
	return {
		title: [{ text: row.label }],
		plateTitle: false,
		subtitle,
		alert: false,
		tags: stateTags(row, ctx),
		figures: keyFigures(figures),
		note: null,
		groups: groups(
			{
				title: L(ctx, 'ws_grp_identity'),
				rows: [
					textRow(L(ctx, 'ws_p_kind'), kindOne(row.kind, ctx.lang)),
					textRow(L(ctx, 'ws_p_status'), stateWord(row.state, ctx.lang)),
					timeRow(L(ctx, 'ws_p_time'), row.t),
					textRow(L(ctx, 'ws_p_place'), str(p.toponym) ?? str(p.canonical_name) ?? str(p.road_name)),
					// a reported situation's class, subtype and correlated classes read here (item 7,
					// fix round 2: the compact report section carries the summary line only)
					...(row.kind === 'osint_event' ? osintSituationRows(row, ctx) : []),
				],
			},
			{
				title: L(ctx, 'ws_grp_location'),
				rows: [
					row.lat != null && row.lon != null ? { key: L(ctx, 'ws_p_coord'), value: { t: 'coord', lat: row.lat, lon: row.lon } } : null,
					// a reported situation's road, junction and geocode read here (item 7, fix round 2);
					// the Place row above names the toponym already
					...(row.kind === 'osint_event' ? osintLocationRows(row, ctx) : []),
				],
			},
			// an OSINT report's verification and credibility live in the header tag, the header
			// figure and the report section — the Provenance group says only the source (item 7)
			{ title: L(ctx, 'ws_grp_provenance'), rows: provenanceRows(row, ctx, undefined, row.kind === 'osint_event') },
		),
		system: systemRows(row),
		plate: null,
	};
}

export const genericAdapter: KindAdapter = {
	kind: '*',
	row(e, ctx) {
		const row = baseRow(e, ctx);
		const p = e.props;
		// an OSINT report's sublabel is its place, a place's its feature type; a report spans its window
		const feature = str(p.feature_type);
		const sub = e.kind === 'place' ? (feature ? human(feature) : null) : str(p.toponym);
		const start = ms(p.window_start);
		return { ...row, sublabel: sub, t: start ?? row.t, end: ms(p.window_end) };
	},
	implied(row) {
		const p = row.props;
		const out: ImpliedLink[] = [];
		if (row.kind === 'osint_event') {
			const seg = num(p.segment_id);
			const j = num(p.junction_id);
			if (seg != null) out.push(`segment:${seg}`);
			if (j != null) out.push(`junction:${j}`);
			// C-T: the event this report was promoted to, and the live object it corroborates —
			// each named by the props, so the snapshot's unnamed link to it reads the same way
			const promoted = str(p.promoted_event_id);
			if (promoted && parseUrn(`event:${promoted}`)) out.push({ urn: `event:${promoted}`, rel: 'promoted_to' });
			const corroborates = str(rec(p.attach).corroborates_live_urn);
			if (corroborates && parseUrn(corroborates)) out.push({ urn: corroborates, rel: 'corroborates' });
		}
		if (row.kind === 'place') {
			const seg = num(p.segment_id);
			const j = num(p.junction_id);
			if (seg != null) out.push(`segment:${seg}`);
			if (j != null) out.push(`junction:${j}`);
		}
		return out;
	},
	view: genericView,
};

export { genericView };
