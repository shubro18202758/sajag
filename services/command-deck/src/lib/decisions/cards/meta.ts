/**
 * The words around a decision unit that every surface shares — the Inbox
 * row, the /ops Decisions item and the ProposalCard header — so the three
 * never disagree: the proposer's glyph and line, the row's second line, the
 * right column (waiting … / expires in …), and the header tags.
 *
 * Marks go through ops.plate / ops.text (raw only for a named duty officer,
 * C6); times through the formatter (IST, one format per column).
 */
import { ops } from '$lib/ops/store.svelte';
import { t } from '$lib/i18n/strings';
import { tOps } from '$lib/i18n/strings.ops';
import '$lib/i18n/packs.decisions';
import '$lib/i18n/packs.dss';
import { ACTOR_ICON, kindIcon, type IconName } from '$lib/design/icons';
import { fmtAgo, fmtCountdown, fmtDuration, fmtStamp } from '$lib/ui/format/format';
import {
	STOLEN_RULE,
	UNIT_KINDS,
	corridorOf,
	dssOf,
	echallanOf,
	escortOf,
	pursuitOf,
	stolenOf,
	type Unit,
} from '../units';

const ms = (iso: string | null | undefined): number | null => {
	const v = iso ? Date.parse(iso) : NaN;
	return Number.isFinite(v) ? v : null;
};

/** When the unit started waiting on an officer (epoch ms), or null. */
export function waitingSince(u: Unit): number | null {
	switch (u.kind) {
		case 'stolen-sighting':
			return ms(stolenOf(u).newest.createdAt);
		case 'pursuit':
			return ms(pursuitOf(u).candidate.vehicle.lastSighting?.t ?? null);
		case 'echallan':
			return ms(echallanOf(u).rec.createdAt);
		case 'escort-proposal':
			return escortOf(u).proposal.createdAt ?? null;
		case 'corridor-request':
			return ms(corridorOf(u).dispatch.createdAt);
		case 'dss':
			return ms(dssOf(u).summary.generatedAt);
		default:
			return null;
	}
}

/** True for a time-boxed unit (escort proposals): its countdown is shown, never a "waiting" line. */
export const timeBoxed = (u: Unit) => UNIT_KINDS[u.kind]?.timeBoxed === true;

/** A human rule label for a recommendation's rule id (never the raw R_* code in the chrome). */
export function ruleLabel(ruleId: string | null | undefined, lang: string): string {
	if (!ruleId) return t(lang, 'dec_rule_unknown');
	const key = `dec_rule_${ruleId.toLowerCase()}`;
	const v = t(lang, key);
	if (v !== key) return v;
	return ruleId
		.replace(/^R_/, '')
		.toLowerCase()
		.replace(/_/g, ' ');
}

/** The proposer's glyph (rules engine, Sajag AI, the requester's dispatch). */
export function actorIcon(u: Unit): IconName {
	if (u.kind === 'escort-proposal') return escortRule(u) ? ACTOR_ICON.rules : ACTOR_ICON.ai;
	if (u.kind === 'corridor-request') return kindIcon('dispatch');
	if (u.kind === 'dss') return ACTOR_ICON.rules; // the decision-support engine (plan X22: the `function` glyph)
	return ACTOR_ICON.rules;
}

/** An escort proposal that the deterministic rule made (no model answered): never labelled AI. */
export function escortRule(u: Unit): boolean {
	const tier = escortOf(u).proposal.tier;
	return tier === 'deterministic' || tier === 'none';
}

/** The X2 verification label as this console prints it in a subtitle (pack text, never the raw enum). */
export function verificationLabel(verification: string | null | undefined, lang: string): string {
	const key = `dss_verif_${(verification ?? 'none').replace(/-/g, '_')}`;
	const v = t(lang, key);
	return v === key ? t(lang, 'dss_verif_none') : v;
}

/** The ProposalCard subtitle: who proposed it and how long it has waited. */
export function proposerLine(u: Unit, lang: string, now: number): string {
	const since = waitingSince(u);
	const waited = since != null ? fmtDuration((now - since) / 1000, lang) : '—';
	switch (u.kind) {
		case 'stolen-sighting':
			return t(lang, 'dec_sub_stolen', waited);
		case 'echallan':
			return t(lang, 'dec_sub_rule', ruleLabel(echallanOf(u).rec.ruleId, lang), waited);
		case 'pursuit': {
			const s = pursuitOf(u).candidate.vehicle.lastSighting;
			return t(lang, 'dec_sub_pursuit', s?.t ? fmtAgo(s.t, now, lang) : '—');
		}
		case 'escort-proposal': {
			const p = escortOf(u).proposal;
			return `${t(lang, escortRule(u) ? 'dec_by_rule' : 'dec_by_ai')} · ${ops.escortDeciderText(p)}`;
		}
		case 'corridor-request': {
			const d = corridorOf(u).dispatch;
			return t(lang, 'dec_sub_corridor', d.requestedBy === '108-driver' ? tOps(lang, 'dispatch108') : ops.text(d.requestedBy) || '—', waited);
		}
		case 'dss': {
			const d = dssOf(u);
			const cred = d.credibility != null ? t(lang, 'dss_credibility', Math.round(d.credibility * 100) / 100) : '';
			return [t(lang, 'dss_by_engine'), verificationLabel(d.verification, lang), cred].filter(Boolean).join(' · ');
		}
		default:
			return '';
	}
}

/** The item's / row's second line (counts, newest read, road …). */
export function rowMeta(u: Unit, lang: string, now: number): string {
	switch (u.kind) {
		case 'stolen-sighting': {
			const d = stolenOf(u);
			const cam = typeof d.newest.evidence?.camera_id === 'string' ? (d.newest.evidence.camera_id as string) : null;
			const road = typeof d.newest.evidence?.road_name === 'string' ? (d.newest.evidence.road_name as string) : d.step.candidate?.anchor?.roadName ?? null;
			const newest = [cam, d.newest.createdAt ? fmtStamp(d.newest.createdAt, now) : null].filter(Boolean).join(' ');
			return [t(lang, 'dec_meta_sightings', d.recs.length), newest ? t(lang, 'dec_meta_newest', newest) : null, road].filter(Boolean).join(' · ');
		}
		case 'pursuit': {
			const d = pursuitOf(u);
			if (d.refusal) return d.refusal === 'no-anchor' ? tOps(lang, 'queuePursuitBlockedAnchor') : tOps(lang, 'queuePursuitBlockedApproval');
			const a = d.candidate.anchor;
			return t(lang, 'dec_meta_anchor', a?.roadName ?? (a ? `#${a.segmentId}` : '—'));
		}
		case 'echallan': {
			const d = echallanOf(u);
			// F-26: a stolen vehicle's e-challan is withheld — its title says "Reject"; the meta line
			// must not read "e-challan recommended" under it
			if (d.stolen) return t(lang, 'dec_meta_echallan_stolen');
			return ops.text(d.rec.recommendation) || ruleLabel(d.rec.ruleId, lang);
		}
		case 'escort-proposal': {
			const d = escortOf(u);
			const name = d.event ? ops.text(d.event.name) : d.proposal.movementId.slice(0, 8);
			return `${tOps(lang, 'escQueueEvent', name)} · ${ops.escortDeciderText(d.proposal)}`;
		}
		case 'corridor-request': {
			const d = corridorOf(u).dispatch;
			const wp = d.waypointJunction != null ? `J${d.waypointJunction}${ops.junctionName(d.waypointJunction) ? ` ${ops.junctionName(d.waypointJunction)}` : ''}` : null;
			return [d.agencyLabel ?? d.agency, d.requestedBy === '108-driver' ? tOps(lang, 'dispatch108') : null, wp].filter(Boolean).join(' · ');
		}
		case 'dss': {
			const d = dssOf(u);
			const top = d.summary.topCoaLabel ? t(lang, 'dss_meta_top', d.summary.topCoaLabel) : null;
			return [top, d.urn.startsWith('osint_event:') ? t(lang, 'dss_meta_report') : null].filter(Boolean).join(' · ');
		}
		default:
			return '';
	}
}

/** The right column: "waiting" over "1 h 40 min", or "expires in" over "1:25" (urgent under 15 s). */
export function ageOf(u: Unit, lang: string, now: number): { label: string; value: string; urgent: boolean; countdown: boolean } {
	// a dss unit has a hard expiry (generated_at + horizon_min): it counts down like a time-boxed proposal
	if ((timeBoxed(u) || u.kind === 'dss') && u.deadline != null) {
		const left = (u.deadline - now) / 1000;
		return { label: t(lang, 'dec_age_expires'), value: fmtCountdown(left), urgent: left < 15, countdown: true };
	}
	const since = waitingSince(u);
	return { label: t(lang, 'dec_age_waiting'), value: since != null ? fmtDuration((now - since) / 1000, lang) : '—', urgent: false, countdown: false };
}

/** The masked-or-raw mark of a unit's subject (for the title's Plate). */
export function unitPlate(u: Unit): string | null {
	switch (u.kind) {
		case 'stolen-sighting':
			return stolenOf(u).plate;
		case 'pursuit':
			return pursuitOf(u).plate;
		case 'echallan':
			return echallanOf(u).plate;
		default:
			return null;
	}
}

/** True for an R_STOLEN_SIGHTING recommendation (evidence for a pursuit, never a fine). */
export const isStolenRule = (ruleId: string | null | undefined) => ruleId === STOLEN_RULE;
