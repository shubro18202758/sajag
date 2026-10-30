/**
 * The OSINT report and place view-models (OS-DECK-A): plain data, no DOM,
 * no store — the sections render it, tests/osint.unit.mjs reads it.
 *
 * WHITELIST (ethics rule 3): the report section renders only the C-T
 * `OsintEventRow` field names and the C-Q provenance block, read key by key
 * from the entity's props — never the raw props object, so a field the
 * oracle must never send (an author, a byline, a handle) has no rendering
 * path even if a source leaks one. `readReport`/`readPlace` are the only
 * readers.
 *
 * Per-source rows: the dossier carries each source's own row (R2) — the
 * publisher, its tier, the already-redacted title, the fetch mode and, on
 * OFFICIAL tiers only, its url; the snapshot (before the dossier answers)
 * still yields the publishers alone. A LINK is rendered only on an official
 * tier (officialness rides the TIER, never the domain); a news/social link
 * is never held deck-side — the row says so instead (the orchestrator
 * decision: news/social URLs are never stored; an official record's link
 * rides the dossier itself).
 */

import type { Dossier } from '$lib/gods-eye/city-api';
import type { VerificationState } from '$lib/ops/types';
import { kindIcon } from '$lib/design/icons';
import { kindLabel } from '$lib/i18n/strings';
import type { PropRow, PropValue, ViewTag } from '$lib/workspace/kinds/common';
import type { ObjectRow } from '$lib/workspace/types';

// ── the whitelist reads ─────────────────────────────────────────────────────

export interface OsintProvenance {
	sourceFeeds: string[];
	publishers: string[];
	geocoder: string | null;
	geocodeConfidence: number | null;
	linksWithheld: number;
	/** Present when the oracle withheld news/social links (their URL may name a person). */
	linkNote: string | null;
	/** Context members listed apart (a district alert in effect): never corroboration. */
	contextPublishers: string[];
	/** The oracle's own note of what the context is (matched to a translated key). */
	contextNote: string | null;
}

/** One per-signal source of the dossier (R2): publisher, tier, redacted title, fetch mode, official-tier url. */
export interface RawSourceRef {
	signalId: string | null;
	publisher: string;
	/** The oracle's own note for the source ({signal_id, source_tier, link_note}), when sent. */
	tier: string | null;
	title: string | null;
	fetchMode: string | null;
	url: string | null;
	linkNote: string | null;
}

/** The oracle's two context notes (city/common.py) — matched to translate them deck-side. */
export const CONTEXT_NOTE_OFFICIAL = 'District warning in effect';
export const CONTEXT_NOTE_REPORT = 'District-level report in effect';

/**
 * The i18n keys of a context note, EXPLICIT (no key surgery): the context
 * line reads the `os_context_*` pair, the generic Sources figure's hint the
 * `os_fig_context_*` pair — the official warning, or the conservative
 * report wording.
 */
export function contextNoteKeys(note: string | null): {
	context: 'os_context_official' | 'os_context_report';
	figure: 'os_fig_context_official' | 'os_fig_context_report';
} {
	return note === CONTEXT_NOTE_REPORT
		? { context: 'os_context_report', figure: 'os_fig_context_report' }
		: { context: 'os_context_official', figure: 'os_fig_context_official' };
}

export interface SecondOrderFlag {
	kind: string;
	urn: string;
	segmentId: number | null;
	note: string | null;
}

export interface DssSummary {
	dssId: string;
	state: string;
	topCoaId: string | null;
	topCoaLabel: string | null;
	generatedAt: number | null;
	horizonMin: number | null;
	expiresAt: number | null;
}

export interface OsintReportProps {
	eventClass: string | null;
	subtype: string | null;
	sajagEventKind: string | null;
	correlatedClasses: string[];
	summary: string | null;
	toponym: string | null;
	segmentId: number | null;
	junctionId: number | null;
	geocodeConfidence: number | null;
	areaLevel: boolean;
	credibility: number | null;
	verification: VerificationState | null;
	sourceCount: number | null;
	sourceTiers: string[];
	independentPublishers: number | null;
	crossTypeCorroborated: boolean;
	/** True when this situation is the first report (attach.novel). */
	novel: boolean;
	/** The live object it corroborates, when it corroborates one. */
	corroboratesLiveUrn: string | null;
	secondOrder: SecondOrderFlag[];
	labels: string[];
	promotedEventId: string | null;
	dss: DssSummary | null;
	/** The dossier's per-signal sources (R2), with the notes beside them; [] before it answers. */
	sources: RawSourceRef[];
	provenance: OsintProvenance;
}

export interface OsintPlaceProps {
	featureType: string | null;
	canonicalName: string | null;
	surfaceForms: string[];
	segmentId: number | null;
	junctionId: number | null;
	osintEventCount: number | null;
}

const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v.trim() : null);
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const bool = (v: unknown): boolean => v === true;
const rec = (v: unknown): Record<string, unknown> => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {});
const list = (v: unknown): string[] => (Array.isArray(v) ? v.filter((s): s is string => typeof s === 'string' && !!s.trim()) : []);
const ms = (v: unknown): number | null => {
	if (typeof v === 'number' && Number.isFinite(v)) return v > 1e12 ? v : v * 1000;
	if (typeof v === 'string') {
		const t = Date.parse(v);
		return Number.isFinite(t) ? t : null;
	}
	return null;
};
const clamp01 = (v: unknown): number | null => {
	const n = num(v);
	return n != null && n >= 0 && n <= 1 ? n : null;
};

function readProvenance(v: unknown): OsintProvenance {
	const p = rec(v);
	return {
		sourceFeeds: list(p.source_feeds),
		publishers: list(p.publishers),
		geocoder: str(p.geocoder),
		geocodeConfidence: clamp01(p.geocode_confidence),
		linksWithheld: Math.max(0, Math.trunc(num(p.links_withheld) ?? 0)),
		linkNote: str(p.link_note),
		contextPublishers: list(p.context_publishers),
		contextNote: str(p.context_note),
	};
}

/** The dossier's per-signal sources + the notes beside them ({signal_id, source_tier, link_note}). */
function readSourceRefs(v: unknown, notes: unknown): RawSourceRef[] {
	const byNote = new Map<string, Record<string, unknown>>();
	for (const raw of Array.isArray(notes) ? notes : []) {
		const n = rec(raw);
		const id = str(n.signal_id);
		if (id) byNote.set(id, n);
	}
	return (Array.isArray(v) ? v : []).flatMap((raw) => {
		const r = rec(raw);
		const publisher = str(r.publisher);
		if (!publisher) return [];
		const id = str(r.signal_id);
		const note = id ? byNote.get(id) : undefined;
		const tier = str(note?.source_tier) ?? str(r.tier);
		const official = tier === 'official';
		return [
			{
				signalId: id,
				publisher,
				tier,
				// the title is already redacted at parse; the deck never reconstructs it
				title: str(r.title),
				fetchMode: str(r.fetch_mode),
				// a url rides OFFICIAL tiers only, whatever the wire says (never a news/social link)
				url: official ? str(r.url) : null,
				linkNote: str(note?.link_note),
			},
		];
	});
}

function readDss(v: unknown): DssSummary | null {
	const d = rec(v);
	const id = str(d.dss_id);
	const state = str(d.state);
	if (!id || !state) return null;
	return {
		dssId: id,
		state,
		topCoaId: str(d.top_coa_id),
		topCoaLabel: str(d.top_coa_label),
		generatedAt: ms(d.generated_at),
		horizonMin: num(d.horizon_min),
		expiresAt: ms(d.expires_at),
	};
}

function readSecondOrder(v: unknown): SecondOrderFlag[] {
	return (Array.isArray(v) ? v : []).flatMap((raw) => {
		const f = rec(raw);
		const kind = str(f.kind);
		const urn = str(f.urn);
		return kind && urn ? [{ kind, urn, segmentId: num(f.segment_id), note: str(f.note) }] : [];
	});
}

/** Every report field the section may show, read one key at a time (the whitelist). */
export function readReport(props: Readonly<Record<string, unknown>>): OsintReportProps {
	const attach = rec(props.attach);
	return {
		eventClass: str(props.event_class),
		subtype: str(props.subtype),
		sajagEventKind: str(props.sajag_event_kind),
		correlatedClasses: list(props.correlated_classes),
		summary: str(props.summary),
		toponym: str(props.toponym),
		segmentId: num(props.segment_id),
		junctionId: num(props.junction_id),
		geocodeConfidence: clamp01(props.geocode_confidence),
		areaLevel: bool(props.area_level),
		credibility: clamp01(props.credibility),
		verification: (str(props.verification_state) ?? null) as VerificationState | null,
		sourceCount: num(props.source_count),
		sourceTiers: list(props.source_tiers),
		independentPublishers: num(props.independent_publishers),
		crossTypeCorroborated: bool(props.cross_type_corroborated),
		novel: bool(attach.novel),
		corroboratesLiveUrn: str(attach.corroborates_live_urn),
		secondOrder: readSecondOrder(props.second_order),
		labels: list(props.labels),
		promotedEventId: str(props.promoted_event_id),
		dss: readDss(props.dss),
		sources: readSourceRefs(props.sources, props.source_notes),
		provenance: readProvenance(props.provenance),
	};
}

/** Every place field the section may show. */
export function readPlace(props: Readonly<Record<string, unknown>>): OsintPlaceProps {
	return {
		featureType: str(props.feature_type),
		canonicalName: str(props.canonical_name),
		surfaceForms: list(props.surface_forms).slice(0, 32),
		segmentId: num(props.segment_id),
		junctionId: num(props.junction_id),
		osintEventCount: num(props.osint_event_count),
	};
}

// ── derived facts ───────────────────────────────────────────────────────────

/**
 * The geocoder's own confidence bucket (osint-geo confidence.py, mirrored):
 * high at 0.75 and above, medium at 0.5 and above, low below — null without
 * a confidence.
 */
export function geocodeBucket(confidence: number | null): 'high' | 'medium' | 'low' | null {
	if (confidence == null) return null;
	if (confidence >= 0.75) return 'high';
	if (confidence >= 0.5) return 'medium';
	return 'low';
}

/**
 * A decision-support proposal is WAITING on this report only while it is
 * proposed AND unexpired (the oracle reads an expired DSS as 'expired'
 * already; the deck checks again so a stale answer never draws the mark).
 */
export function dssWaiting(p: OsintReportProps, now: number): boolean {
	return p.dss != null && p.dss.state === 'proposed' && p.dss.expiresAt != null && p.dss.expiresAt > now;
}

/** A publisher on a government domain is NOT read as official: officialness rides the TIER (R2). */

/** One row of the source list: a source's publisher, ITS OWN tier, and the link facts. */
export interface SourceRow {
	/** The source signal (null on a snapshot-only row: the dossier has not answered yet). */
	signalId: string | null;
	publisher: string;
	/** The source's own tier (S1: per source, from source_notes keyed by signal_id); null when unknown. */
	tier: string | null;
	/** The already-redacted headline (the dossier's per-signal sources); null on a snapshot-only row. */
	title: string | null;
	/** How the copy entered ('cached-sample'): shown as a tag. */
	fetchMode: string | null;
	/** An OFFICIAL tier's url — the only kind the deck ever renders a link for. */
	url: string | null;
	/** From the tier, never the domain. */
	official: boolean;
	/** A news/social link is never held deck-side; the row says so instead of showing one. */
	linkWithheld: boolean;
}

/**
 * The reporting sources as rows. From the dossier: one per per-signal source,
 * in the oracle's order. From the snapshot alone (the dossier has not
 * answered): one per distinct reporting publisher, tier unknown. A CONTEXT
 * member (a district alert in effect) is never a row here — it is context,
 * listed apart (see `contextLine`).
 */
export function sourceRows(p: OsintReportProps): SourceRow[] {
	if (p.sources.length) {
		const seen = new Set<string>();
		const rows = p.sources.flatMap((r) => {
			const key = r.signalId ?? `pub:${r.publisher.toLowerCase()}`;
			if (seen.has(key)) return [];
			seen.add(key);
			const official = r.tier === 'official';
			return [
				{
					signalId: r.signalId,
					publisher: r.publisher,
					tier: r.tier,
					title: r.title,
					fetchMode: r.fetchMode,
					url: r.url,
					official,
					linkWithheld: !official && (r.linkNote != null || r.url == null),
				},
			];
		});
		// the only url the deck ever binds as a link is an official tier's https: one —
		// anything else (http:, a protocol-relative form) is dropped like a withheld link
		return rows.map((r) => (r.url != null && !r.url.startsWith('https:') ? { ...r, url: null } : r));
	}
	const seen = new Set<string>();
	const out: SourceRow[] = [];
	for (const publisher of p.provenance.publishers) {
		const key = publisher.toLowerCase();
		if (seen.has(key)) continue;
		seen.add(key);
		out.push({ signalId: null, publisher, tier: null, title: null, fetchMode: null, url: null, official: false, linkWithheld: p.provenance.linksWithheld > 0 });
	}
	return out;
}

/** The context line: the alert in effect, named apart — never a corroborating source. */
export function contextLine(p: OsintReportProps, t: (key: string, ...args: unknown[]) => string): string | null {
	if (!p.provenance.contextPublishers.length) return null;
	const note = t(contextNoteKeys(p.provenance.contextNote).context);
	return `${note} · ${p.provenance.contextPublishers.join(', ')}`;
}

/**
 * A source tier in words, LOCALIZED ("Aggregator"; HI/MR read the pack's
 * `os_tier_*` keys), falling back to the sentence-case class word for a
 * tier the pack does not know.
 */
export function tierWord(tier: string | null, lang: string, t: (key: string, ...args: unknown[]) => string): string | null {
	if (!tier) return null;
	const key = `os_tier_${tier}`;
	const word = t(key);
	return word === key ? classWord(tier) : word;
}

/** The situation's class in words (the six reported-situation kinds; a corridor event for an unknown kind). */
export function situationClass(kind: string | null, lang: string): string | null {
	return kind ? kindLabel(lang, kind) : null;
}

// ── section view-models ─────────────────────────────────────────────────────

const mono = (v: string): PropValue => ({ t: 'id', v });
const text = (v: string): PropValue => ({ t: 'text', v });

/** The sections render their rows through the inspector's PropertyGroups (the PropertyTable look). */
export type OsintRow = PropRow;

/** A linked object as a display-only row (ObjectTag reads urn, kind, label, masked). */
export function objectValue(urn: string, kind: string, label: string): PropValue {
	const row: ObjectRow = {
		urn,
		kind,
		id: urn.slice(urn.indexOf(':') + 1),
		label,
		sublabel: null,
		icon: kindIcon(kind),
		state: null,
		stateIntent: 'none',
		t: null,
		end: null,
		lon: null,
		lat: null,
		source: 'osint',
		verification: null,
		credibility: null,
		test: false,
		masked: false,
		props: {},
	};
	return { t: 'object', row };
}

/** Neutral tags (classes, tiers, surface forms): no hue — they are not states. */
export function tagsValue(words: readonly string[]): PropValue {
	const tags: ViewTag[] = words.map((text) => ({ text, intent: 'none' }));
	return { t: 'tags', tags };
}

export interface OsintSection {
	title: string;
	testid?: string;
	rows: readonly OsintRow[];
	/** The verification the section's ProvenanceTag shows (the Verification section). */
	verification?: VerificationState | null;
	/** The source rows (the Sources section, rows osint-source). */
	sources?: readonly SourceRow[];
	/** Neutral rule notes of the section, one Note each (area-level, context, held social, second-order). */
	notes?: readonly string[];
}

/** A linked segment/junction/event row from the dossier ("On road", "At junction", "Promoted to"), or null. */
export function relatedObject(dossier: Dossier | null, relation: string): { urn: string; kind: string; label: string } | null {
	if (!dossier) return null;
	for (const r of dossier.related) {
		if (r.relation !== relation) continue;
		return { urn: r.entity.urn, kind: r.entity.kind, label: r.entity.label };
	}
	return null;
}

/** The context the section builds its strings with. */
export interface ViewCtx {
	lang: string;
	/** The console's clock (ms). */
	now: number;
}

export interface ReportView {
	sections: readonly OsintSection[];
	/** The one rule note of the report section (SPEC §5.1: at most one per surface). */
	note: string;
}

/**
 * The report section's groups, from the whitelist alone. Localization is
 * the caller's: `t` maps a key (`os_event_kind_<kind>` through kindLabel),
 * so the model stays data and the test reads the strings as built.
 *
 * COMPACT (item 7, fix round 2): the section is the verification tag, a
 * one-line summary and the source list — class, subtype and correlated
 * classes, and the whole Location group (road, junction, geocode, the
 * district note) live in the inspector's Properties groups instead
 * (generic.ts builds them for `osint_event`), so the tabs sit above the
 * fold at every console size.
 */
export function reportView(p: OsintReportProps, dossier: Dossier | null, t: (key: string, ...args: unknown[]) => string, ctx: ViewCtx): ReportView {
	const sections: OsintSection[] = [];

	// ── Situation (one line) ──
	if (p.summary) sections.push({ title: t('os_group_situation'), rows: [{ key: t('os_summary'), value: text(p.summary) }] });

	// ── Verification ──
	// De-duplicated (item 7): the credibility figure and the ProvenanceTag live once elsewhere
	// (the inspector's header figure and this section's tag), so the section carries only what
	// nothing else says — the independent publishers and the cross-type corroboration. The
	// situation-level tier row is gone: each source wears its own tier (S1).
	const verification: OsintRow[] = [];
	if (p.independentPublishers != null) verification.push({ key: t('os_independent_publishers'), value: mono(String(p.independentPublishers)) });
	verification.push({ key: t('os_cross_type'), value: text(t(p.crossTypeCorroborated ? 'os_yes' : 'os_no')) });
	sections.push({ title: t('os_group_verification'), verification: p.verification, rows: verification });

	// ── Sources ──
	// R1: no per-report "n social posts held" line — it implies corroboration that does not
	// exist; the count, when the oracle holds any, is the layer's one city-wide line.
	const sources = sourceRows(p);
	const notes: string[] = [];
	const context = contextLine(p, t);
	if (context) notes.push(context);
	sections.push({ title: t('os_group_sources'), testid: 'osint-sources', sources, rows: [], notes: notes.length ? notes : undefined });

	// ── Live state ──
	const live: OsintRow[] = [];
	const liveNotes: string[] = [];
	if (p.promotedEventId) {
		const ev = relatedObject(dossier, 'promoted_to');
		live.push({
			key: t('os_attach'),
			value: objectValue(ev?.urn ?? `event:${p.promotedEventId}`, 'event', ev?.label ?? t('os_promoted_to')),
			testid: 'osint-attach',
		});
	} else if (p.corroboratesLiveUrn) {
		const ev = relatedObject(dossier, 'corroborates');
		live.push({
			key: t('os_attach'),
			value: objectValue(ev?.urn ?? p.corroboratesLiveUrn, 'event', ev?.label ?? t('os_corroborates')),
			testid: 'osint-attach',
		});
	} else if (p.novel) {
		live.push({ key: t('os_attach'), value: text(t('os_attach_novel')), testid: 'osint-attach' });
	}
	// the second-order flags: one neutral Note per distinct wording, a count when the
	// same words repeat (two "On a 108 route" notes say nothing about which is which)
	const byNote = new Map<string, number>();
	for (const flag of p.secondOrder) {
		if (!flag.note) continue;
		byNote.set(flag.note, (byNote.get(flag.note) ?? 0) + 1);
	}
	for (const [note, count] of byNote) liveNotes.push(count > 1 ? `${note} ×${count}` : note);
	if (live.length || liveNotes.length)
		sections.push({ title: t('os_group_live'), testid: 'osint-second-order', rows: live, notes: liveNotes.length ? liveNotes : undefined });

	return { sections, note: t('os_rule_note') };
}

/** Humanise a snake_case class word in SENTENCE case ("public_conflict" → "Public conflict"). */
export function classWord(raw: string): string {
	const words = raw
		.split(/[_+]/)
		.filter(Boolean)
		.map((w) => w.toLowerCase());
	return words.length ? words[0].charAt(0).toUpperCase() + words[0].slice(1) + (words.length > 1 ? ` ${words.slice(1).join(' ')}` : '') : '';
}

/** The place section's view, from the place whitelist alone. */
export function placeView(p: OsintPlaceProps, dossier: Dossier | null, t: (key: string, ...args: unknown[]) => string): { title: string; rows: readonly OsintRow[] } {
	const rows: OsintRow[] = [];
	if (p.canonicalName) rows.push({ key: t('os_place_name'), value: text(p.canonicalName) });
	if (p.featureType) rows.push({ key: t('os_place_type'), value: text(classWord(p.featureType)) });
	if (p.surfaceForms.length) {
		// EN and MR forms: the gazetteer's own spellings (Latin and Marathi scripts)
		const latin = p.surfaceForms.filter((f) => !/[\u0A80-\u0AFF]/.test(f));
		const marathi = p.surfaceForms.filter((f) => /[\u0A80-\u0AFF]/.test(f));
		rows.push({
			key: t('os_surface_forms'),
			value: tagsValue([...latin.slice(0, 4), ...marathi.slice(0, 4)]),
			testid: 'osint-place-forms',
		});
	}
	if (p.segmentId != null) {
		const seg = relatedObject(dossier, 'on_road');
		rows.push({ key: t('os_road'), value: objectValue(seg?.urn ?? `segment:${p.segmentId}`, 'segment', seg?.label ?? `Segment ${p.segmentId}`) });
	}
	if (p.junctionId != null) {
		const jct = relatedObject(dossier, 'at_junction');
		rows.push({ key: t('os_junction'), value: objectValue(jct?.urn ?? `junction:${p.junctionId}`, 'junction', jct?.label ?? `Junction ${p.junctionId}`) });
	}
	if (p.osintEventCount != null) rows.push({ key: t('os_place_reports'), value: mono(String(p.osintEventCount)) });
	return { title: t('os_group_place'), rows };
}
