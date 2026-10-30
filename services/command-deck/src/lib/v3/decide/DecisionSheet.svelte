<script lang="ts">
	/**
	 * DecisionSheet (V3-SPEC §5.3, §6.2) — the one card: what is proposed, why, what changes, the choice, who
	 * is deciding, and the buttons. Same anatomy for every unit kind:
	 *
	 *   header   the kind's illustration, the kind line, the title (its mark in a masked chip), ≤ 4 tags, and
	 *            the countdown ring for a time-boxed proposal;
	 *   body     per kind — escort (the hold / re-route sentence, three facts, "If no one answers…"), decision
	 *            support (the quoted report with its redactions, the public-safety floor, "Pick a response"
	 *            as OptionCards, the blocked stronger option, "Why this one"), stolen vehicle (the vehicle
	 *            silhouette, the two steps, the reads as a timeline, "Evidence only"), pursuit opening,
	 *            e-challan (Reject only on a stolen vehicle), 108 corridor request;
	 *   changes  ChangeList, generated from the verb's writer (decisions/writers.ts);
	 *   actions  OfficerGate, then the secondary verbs and the ONE primary. A verb that needs the officer's
	 *            reason opens the reason field first (the R key does the same) — never a POST without it.
	 *
	 * Every verb runs through run.ts → its EXISTING writer (officer gate, double-click guard, refusal codes).
	 * A refusal is printed IN the sheet, the server's own words verbatim (`decision-refusal`), never a toast.
	 * Buttons are never removed for a missing officer: they stay visible, `aria-disabled`, with the reason.
	 * An escort proposal past its countdown keeps the current plan (said, buttons locked); one this console
	 * already answered is locked (ops.escortAnswered — never sent twice).
	 */
	import { tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { ops } from '$lib/ops/store.svelte';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.decisions';
	import '$lib/i18n/packs.dss';
	import { fmtDuration, fmtTime } from '$lib/ui/format/format';
	import Id from '$lib/ui/format/Id.svelte';
	import { UNIT_KINDS, corridorOf, dssOf, echallanOf, escortOf, escortSentence, pursuitOf, stolenOf, type Unit } from '$lib/decisions/units';
	import type { ChangeRow } from '$lib/decisions/writers';
	import { ruleLabel } from '$lib/decisions/cards/meta';
	import { homeLink } from '$lib/decisions/homes';
	import {
		approveBlocked,
		coaBlockReason,
		coaById,
		coaSelectable,
		defaultCoaId,
		floorLine,
		rankedRows,
		strategyPriorLine,
	} from '$lib/dss/dss-data';
	import { dssState, ensureDssObject, forgetDssObject, selectCoa } from '$lib/dss/dss-store.svelte';
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import PlateChip from '../ui/PlateChip.svelte';
	import RedactedText from '../ui/RedactedText.svelte';
	import { decisionVM, echallanWhy, type TagVM } from '../home/view';
	import { keyArt } from '../media/art';
	import VehicleShot from '../media/VehicleShot.svelte';
	import AgencyMark from '../media/AgencyMark.svelte';
	import '../media/packs.media';
	import CountdownRing from './CountdownRing.svelte';
	import ChangeList from './ChangeList.svelte';
	import OptionCard from './OptionCard.svelte';
	import BlockedOption from './BlockedOption.svelte';
	import OfficerGate from './OfficerGate.svelte';
	import './packs.decide';
	import { TAG_GLYPH, actionsOf, escortPhase, keyOf, needsReason, whenOf, writerOf } from './model';
	import { deciding, runDecision } from './run';
	import { decideSession } from './session.svelte';

	let {
		unit,
		lang,
		now,
		slow,
		ondone,
	}: {
		unit: Unit;
		lang: string;
		/** The 1 s clock (countdowns). */
		now: number;
		/** The 15 s clock (everything else that ages). */
		slow: number;
		/** A verb succeeded: the page collapses the sheet to its outcome. */
		ondone?: (key: string) => void;
	} = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const key = $derived(keyOf(unit));
	const vm = $derived.by(() => {
		void ops.officerOn;
		void cityRegistry.version;
		return decisionVM(unit, lang, slow);
	});
	const acts = $derived(actionsOf(unit));
	const officerOn = $derived(ops.officerOn);
	const officer = $derived(ops.dutyOfficer.trim());

	// ── time ───────────────────────────────────────────────────────────────
	const timeBoxed = $derived(UNIT_KINDS[unit.kind]?.timeBoxed === true);
	const leftSec = $derived(unit.deadline != null ? (unit.deadline - now) / 1000 : null);
	const phase = $derived(unit.kind === 'escort-proposal' ? escortPhase(unit, now, (id) => ops.escortAnswered(id)) : 'open');
	const expired = $derived(phase === 'expired');
	const when = $derived(whenOf(unit, now, lang, L));

	// ── decision support: the C-U object (one GET per id, shared with the v2 card) ──
	const isDss = $derived(unit.kind === 'dss');
	$effect(() => {
		if (unit.kind === 'dss') void ensureDssObject(unit.id);
	});
	const dss = $derived(isDss ? (dssState.objects[unit.id] ?? null) : null);
	const dssLoading = $derived(isDss && dssState.loading[unit.id] === true);
	const dssFailed = $derived(isDss ? (dssState.failed[unit.id] ?? null) : null);
	const ranked = $derived(rankedRows(dss));
	const selectable = $derived(ranked.filter((c) => coaSelectable(c)));
	const blockedRows = $derived(ranked.filter((c) => !coaSelectable(c)));
	const bestBlockedId = $derived(dss?.recommendation.bestBlocked?.coaId ?? null);
	const coaId = $derived(isDss ? (dssState.selected[unit.id] ?? (dss ? defaultCoaId(dss) : null)) : null);
	const coa = $derived(coaById(dss, coaId));

	function choose(id: string) {
		selectCoa(unit.id, id);
		decideSession.clearRefusal(key);
	}

	/** Keyboard 1–4 (the page calls it): the n-th option the officer can choose. */
	export function chooseIndex(i: number): boolean {
		const c = selectable[i];
		if (!c) return false;
		choose(c.coaId);
		return true;
	}

	// ── the verbs ──────────────────────────────────────────────────────────
	let reasonFor = $state<string | null>(null);
	let reason = $state('');
	let reasonField = $state<HTMLInputElement | null>(null);
	let primaryBtn = $state<HTMLButtonElement | null>(null);
	let sending = $state(false);
	const storeBusy = $derived(ops.recommendationBusy !== null || ops.escortDecisionBusy !== null || ops.dispatchBusy !== null || ops.pursuitBusy !== null);
	const busy = $derived(sending || storeBusy || deciding(unit));

	/** The verb whose changes the list shows: the primary, else the first secondary (a Reject-only e-challan). */
	const shownAction = $derived(reasonFor ?? acts.primary ?? acts.secondary[0] ?? null);
	const changeRows = $derived.by((): ChangeRow[] => {
		void ops.officerOn;
		void lang;
		const w = writerOf(unit, shownAction);
		try {
			return w ? w.changes(unit, isDss ? { dss, coaId, note: reason } : undefined) : [];
		} catch {
			return [];
		}
	});
	const unchanged = $derived.by((): string[] => {
		void lang;
		const w = writerOf(unit, shownAction);
		try {
			return w ? w.unchanged(unit) : [];
		} catch {
			return [];
		}
	});
	const changesTitle = $derived.by(() => {
		if (!shownAction) return L('v3d_changes');
		if (isDss && shownAction === 'approve' && coa) return L('v3d_changes_coa', coa.label);
		return L(`v3d_changes_${shownAction}`);
	});

	const primaryLabel = $derived.by(() => {
		switch (acts.primary) {
			case 'authorise':
				return L('v3d_btn_authorise');
			case 'open':
				return L('v3d_btn_open_pursuit');
			case 'approve':
				if (unit.kind === 'escort-proposal') {
					const k = escortOf(unit).proposal.kind;
					return L(k === 'hold' ? 'v3d_btn_approve_hold' : k === 'plan_b' || k === 'reroute' ? 'v3d_btn_approve_route' : 'dec_btn_approve');
				}
				if (unit.kind === 'dss') return coa ? L('v3d_btn_approve_coa', coa.label) : L('dec_btn_approve');
				if (unit.kind === 'corridor-request') return L('v3d_btn_approve_corridor');
				if (unit.kind === 'echallan') return L('v3d_btn_approve_echallan');
				return L('dec_btn_approve');
			default:
				return '';
		}
	});

	const secondaryLabel = (a: string) => {
		if (a === 'dismiss') {
			const n = stolenOf(unit).recs.length;
			return n > 1 ? L('v3d_btn_dismiss_all', n) : L('v3d_btn_dismiss');
		}
		return L(`dec_btn_${a}`);
	};

	/** Why the primary cannot act now (null = it can). */
	const primaryBlock = $derived.by((): string | null => {
		if (!acts.primary) return null;
		if (expired) return L('dec_reason_expired');
		if (phase === 'answered') return L('v3d_reason_answered');
		if (!officerOn) return L('v3d_reason_officer');
		if (acts.primary === 'open') {
			const refusal = unit.kind === 'stolen-sighting' ? stolenOf(unit).step.refusal : pursuitOf(unit).refusal;
			if (refusal) return refusal === 'no-anchor' ? L('dec_refuse_no_anchor') : L('dec_refuse_no_approval');
		}
		if (isDss) {
			if (!dss) return dssFailed ? L('dss_load_failed') : L('v3d_reason_loading');
			return approveBlocked(lang, officer, coa);
		}
		return null;
	});
	const secondaryBlock = (a: string): string | null => {
		if (expired) return L('dec_reason_expired');
		if (phase === 'answered') return L('v3d_reason_answered');
		if (!officerOn) return L('v3d_reason_officer');
		if (reasonFor === a && needsReason(unit, a) && !reason.trim()) return L(a === 'dismiss' ? 'dec_reason_dismiss' : a === 'defer' ? 'v3d_reason_defer' : 'dec_reason_reject');
		return null;
	};
	const blockLine = $derived(primaryBlock ?? (acts.primary ? null : acts.secondary.map(secondaryBlock).find(Boolean) ?? null));

	async function openReason(a: string) {
		reasonFor = a;
		await tick();
		reasonField?.focus();
	}

	/** The R key (the page calls it): open the reason for the first verb that needs one. */
	export function startReason(): boolean {
		const a = acts.secondary.find((x) => needsReason(unit, x));
		if (!a || expired || phase === 'answered') return false;
		void openReason(a);
		return true;
	}

	/** Enter (the page calls it): focus the primary button — never press it. */
	export function focusPrimary(): boolean {
		if (!primaryBtn) return false;
		primaryBtn.focus();
		return true;
	}

	async function act(a: string, primary: boolean) {
		if (busy) return;
		const block = primary ? primaryBlock : secondaryBlock(a);
		if (block) return;
		if (!primary && needsReason(unit, a) && (reasonFor !== a || !reason.trim())) {
			void openReason(a);
			return;
		}
		sending = true;
		decideSession.clearRefusal(key);
		try {
			const o = await runDecision(unit, a, { note: reasonFor === a ? reason.trim() : '', coaId: isDss && a === 'approve' ? coaId : null }, lang);
			if (o?.ok) {
				reason = '';
				reasonFor = null;
				ondone?.(key);
			}
		} finally {
			sending = false;
		}
	}

	// ── refusals, verbatim ────────────────────────────────────────────────
	const outcome = $derived(decideSession.outcomes[key] ?? null);
	const standing = $derived.by((): { text: string; detail: string | null } | null => {
		if (outcome && !outcome.ok) return { text: outcome.refusal ?? '', detail: outcome.detail };
		// a refusal recorded before this sheet opened (the oracle's 409 on this unit — never retried)
		if (unit.kind === 'echallan' && echallanOf(unit).refusal) return { text: L('dec_refuse_refused'), detail: echallanOf(unit).refusal!.detail };
		if (unit.kind === 'stolen-sighting' && stolenOf(unit).refusal) return { text: L('dec_refuse_refused'), detail: stolenOf(unit).refusal!.detail };
		if (isDss && dssState.refusals[unit.id]) return { text: L('dss_refuse_refused'), detail: dssState.refusals[unit.id].detail };
		return null;
	});

	// ── per-kind words ────────────────────────────────────────────────────
	const tags = $derived.by((): TagVM[] => {
		const out: TagVM[] = [];
		switch (unit.kind) {
			case 'escort-proposal': {
				out.push({ text: vm.by.text, tone: vm.by.ai ? 'ai' : 'neutral', glyph: vm.by.ai ? 'spark' : 'shield' });
				const ev = escortOf(unit).event;
				if (ev) {
					const cls = ev.protectionClass && ev.protectionClass !== 'none' ? L('v3d_tag_class', ev.protectionClass) : null;
					out.push({ text: [cls, ops.text(ev.name).split(' · ').pop()].filter(Boolean).join(' · '), tone: 'route', glyph: TAG_GLYPH.movement });
				}
				break;
			}
			case 'dss': {
				const v = dssOf(unit).verification;
				out.push(
					v === 'OFFICIAL-VERIFIED' || v === 'CONFIRMED'
						? { text: L(v === 'CONFIRMED' ? 'v3_rep_confirmed' : 'v3_rep_official'), tone: 'ok', glyph: 'verified' }
						: v === 'NEWS-REPORTED'
							? { text: L('v3_rep_news'), tone: 'ghost', glyph: 'news' }
							: { text: L('v3_rep_unverified'), tone: 'dashed', glyph: 'unverified' },
				);
				const cred = dssOf(unit).credibility;
				const pubs = dss?.provenance.publishers.length ?? 0;
				if (cred != null) out.push({ text: pubs ? L('v3d_tag_cred_pubs', cred.toFixed(2), pubs) : L('v3d_tag_cred', cred.toFixed(2)), tone: 'neutral', title: L('v3_cred_tip', cred.toFixed(2)) });
				out.push({ text: when.text, tone: 'decide', glyph: 'clock' });
				break;
			}
			case 'stolen-sighting': {
				const fir = stolenOf(unit).fir;
				// an emulated vehicle's FIR is a scripted demo reference, never a real case (HON-4)
				out.push({ text: fir ? L(stolenOf(unit).emulated ? 'v3d_tag_stolen_fir_demo' : 'v3d_tag_stolen_fir', fir) : L('v3d_tag_stolen'), tone: 'alert', glyph: 'alert' });
				out.push({ text: vm.by.text, tone: 'neutral' });
				out.push({ text: when.text, tone: 'decide', glyph: 'clock' });
				break;
			}
			case 'pursuit':
				out.push({ text: L('v3d_tag_watchlisted'), tone: 'alert', glyph: 'alert' });
				out.push({ text: vm.by.text, tone: 'neutral' });
				break;
			case 'echallan': {
				const d = echallanOf(unit);
				out.push({ text: ruleLabel(d.rec.ruleId, lang), tone: 'neutral', glyph: 'anpr' });
				out.push({ text: when.text, tone: 'decide', glyph: 'clock' });
				break;
			}
			case 'corridor-request':
				out.push({ text: vm.by.text, tone: 'neutral', glyph: 'ambulance' });
				out.push({ text: when.text, tone: 'decide', glyph: 'clock' });
				break;
			default:
				out.push({ text: when.text, tone: 'decide', glyph: 'clock' });
		}
		if (vm.prov) out.push(vm.prov);
		return out.slice(0, 4);
	});

	const what = $derived.by((): string => {
		switch (unit.kind) {
			case 'escort-proposal':
				return ops.text(escortSentence(escortOf(unit).proposal, ops));
			case 'dss':
				return dssOf(unit).situationSummary ? ops.text(dssOf(unit).situationSummary!) : vm.why;
			case 'echallan':
				return echallanWhy(ops.text(echallanOf(unit).rec.recommendation), lang) || vm.why;
			case 'stolen-sighting': {
				// HON-4: an emulated vehicle's FIR sentence is the demo one (dec_why_stolen_fir_demo). The shared view
				// model says it once main's key is present; until then (or if it ever is not) the sentence is swapped here.
				const d = stolenOf(unit);
				if (!d.emulated || !d.fir) return vm.why;
				const demo = L('dec_why_stolen_fir_demo', d.fir);
				return demo === 'dec_why_stolen_fir_demo' ? vm.why : vm.why.replace(L('dec_why_stolen_fir', d.fir), demo);
			}
			default:
				return vm.why;
		}
	});

	const facts = $derived.by(() => {
		// decision support says its credibility and pick in the tags and the options; a stolen vehicle's reads are
		// the timeline below — the facts row would only repeat them
		if (unit.kind === 'dss' || unit.kind === 'stolen-sighting') return [];
		const out = [...vm.facts];
		if (unit.kind === 'escort-proposal') {
			// a hold is said in seconds under three minutes ("90 s", never a rounded "1 min")
			const hold = escortOf(unit).proposal.proposed?.maxHoldSec;
			const i = out.findIndex((f) => f.label === L('v3_fact_hold'));
			if (i >= 0 && hold != null && hold < 180) out[i] = { ...out[i], value: `${Math.round(hold)} ${L('ui_unit_s')}` };
		}
		if (unit.kind === 'corridor-request') {
			const ds = corridorOf(unit).dispatch;
			const wp = ds.waypointJunction != null ? ops.junctionName(ds.waypointJunction, lang) : null;
			if (wp) out.push({ value: wp, label: L('v3d_fact_waypoint') });
			if (leftSec != null && leftSec > 0) out.push({ value: fmtDuration(leftSec, lang), label: L('v3_fact_golden') });
		}
		if (unit.kind === 'escort-proposal' && out.length < 3) {
			const p = escortOf(unit).proposal;
			if (p.peakCongestion != null && !out.some((f) => f.value.endsWith('%'))) out.push({ value: `${Math.round(p.peakCongestion * 100)}%`, label: L('v3_fact_congestion') });
		}
		return out.slice(0, 3);
	});

	// V3-P7: the sheet opens on the kind's key art (an illustration of the situation, never the situation itself)
	const bannerKind = $derived(
		unit.kind === 'escort-proposal'
			? 'protected_movement'
			: unit.kind === 'pursuit'
				? 'vehicle_pursuit'
				: unit.kind === 'corridor-request'
					? 'green_corridor'
					: unit.kind === 'dss'
						? (dssOf(unit).sajagEventKind ?? dssOf(unit).eventClass ?? 'advisory')
						: 'crime_incident',
	);
	const corridorAgency = $derived(unit.kind === 'corridor-request' ? corridorOf(unit).dispatch : null);

	// stolen vehicle: the silhouette, the steps, the reads
	const vehicleClass = $derived.by(() => {
		if (unit.kind !== 'stolen-sighting' && unit.kind !== 'pursuit') return null;
		const id = unit.kind === 'stolen-sighting' ? stolenOf(unit).vehicleId : pursuitOf(unit).vehicleId;
		const c = cityRegistry.get(`vehicle:${id}`)?.props.vehicle_class;
		const known = ['car', 'suv', 'bus', 'truck', 'tempo', 'two_wheeler', 'auto_rickshaw'];
		return typeof c === 'string' && known.includes(c) ? c : 'car';
	});
	const reads = $derived.by(() => {
		if (unit.kind !== 'stolen-sighting') return [];
		return [...stolenOf(unit).recs]
			.reverse()
			.map((r) => {
				const ev = r.evidence ?? {};
				const str = (v: unknown) => (typeof v === 'string' && v ? v : null);
				const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
				return {
					id: r.recommendationId,
					cam: str(ev['camera_id']),
					road: str(ev['road_name']),
					kmh: num(ev['speed_kmh']),
					at: r.createdAt ? Date.parse(r.createdAt) : NaN,
				};
			});
	});
	const readSpan = $derived.by(() => {
		const ts = reads.map((r) => r.at).filter((x) => Number.isFinite(x));
		return ts.length > 1 ? Math.max(...ts) - Math.min(...ts) : 0;
	});
	const camCount = $derived(new Set(reads.map((r) => r.cam).filter(Boolean)).size || reads.length);
	const step = $derived(unit.kind === 'stolen-sighting' ? stolenOf(unit).step : null);
	const approved = $derived(unit.kind === 'stolen-sighting' && !!stolenOf(unit).approved);

	const floor = $derived.by((): { glyph: string; lead: string; text: string; testid: string } | null => {
		switch (unit.kind) {
			case 'escort-proposal':
				return expired
					? { glyph: 'clock', lead: L('v3d_expired_lead'), text: L('v3d_expired_text'), testid: 'v3-plan-kept' }
					: { glyph: 'clock', lead: L('v3d_ifnot_lead'), text: L('v3d_ifnot_escort'), testid: 'v3-if-no-one' };
			case 'dss': {
				const f = floorLine(lang, dss);
				return f ? { glyph: 'shield', lead: '', text: f, testid: 'dss-safety-floor' } : null;
			}
			case 'stolen-sighting':
			case 'pursuit':
				return { glyph: 'shield', lead: L('v3d_evidence_lead'), text: L(unit.kind === 'pursuit' ? 'v3d_evidence_pursuit' : 'v3d_evidence_text'), testid: 'v3-evidence-only' };
			case 'echallan':
				return echallanOf(unit).stolen ? { glyph: 'shield', lead: L('v3d_stolen_lead'), text: L('v3d_echallan_stolen'), testid: 'stolen-warning' } : null;
			case 'corridor-request':
				return { glyph: 'clock', lead: '', text: L('v3_ifnot_waits'), testid: 'v3-if-no-one' };
			default:
				return null;
		}
	});

	// decision support: "Why this one" and Request a unit
	const whyLines = $derived.by((): string[] => {
		if (!dss) return [];
		const out: string[] = [];
		if (dss.summary) out.push(ops.text(dss.summary));
		if (dss.recommendation.evoiWhy) out.push(L('dss_why_evoi', dss.recommendation.evoiWhy));
		if (dss.recommendation.topCoaId && coaId && coaId !== dss.recommendation.topCoaId)
			out.push(L('dss_pick_mismatch', coaById(dss, dss.recommendation.topCoaId)?.label ?? dss.recommendation.topCoaId));
		if (dss.recommendation.dissent) out.push(dss.recommendation.dissent);
		return out;
	});
	const aiLine = $derived(dss ? strategyPriorLine(lang, dss) : '');
	const requestEvent = $derived.by(() => {
		if (!isDss) return null;
		const d = dssOf(unit);
		return d.subjectKind === 'event' ? d.urn.replace(/^event:/, '') : d.promotedEventId;
	});
	function requestUnit() {
		if (!requestEvent) return;
		ops.selectedEventId = requestEvent;
		void goto('/ops');
	}
	const analystHref = $derived(homeLink(unit.kind, unit.id, '/ops', lang).href);

	const howLines = $derived.by((): string[] => {
		if (unit.kind !== 'escort-proposal') return [];
		const p = escortOf(unit).proposal;
		const out = [L('v3d_how_decider', ops.escortDeciderText(p))];
		const why = ops.escortProposalWhy(p);
		if (why) out.push(ops.text(why));
		if (p.peakCongestion != null) out.push(L('v3d_how_congestion', Math.round(p.peakCongestion * 100)));
		if (p.simulated) out.push(L('v3d_how_simulated'));
		const w = writerOf(unit, 'approve');
		const next = w?.nextStep?.(unit);
		if (next) out.push(next);
		return out;
	});
</script>

<div class="sheet-in" data-testid="v3-decision-sheet" data-kind={unit.kind} data-id={unit.id} data-phase={phase}>
	<div class="scroll">
		<div class="banner" data-testid="v3-sheet-art" data-kind={bannerKind}>
			<img src={keyArt(bannerKind)} alt={L('v3i_art_alt', vm.kindLine)} width="640" height="360" loading="eager" decoding="async" />
		</div>
		<header class="sh-top">
			<div class="art"><img src={vm.art} alt="" width="60" height="60" /></div>
			<div class="head">
				<p class="micro">{vm.kindLine}</p>
				<h1 class="title" id="v3d-sheet-title">
					{vm.title}{#if vm.plate}{' '}<PlateChip mark={vm.plate.mark} masked={vm.plate.masked} {lang} />{/if}
				</h1>
				<div class="tags">
					{#each tags as tg, i (i)}
						<V3Tag tone={tg.tone} glyph={tg.glyph ?? null} title={tg.title ?? null}>{tg.text}</V3Tag>
					{/each}
				</div>
			</div>
			{#if timeBoxed && leftSec != null}
				<CountdownRing leftSec={leftSec} totalSec={escortOf(unit).proposal.timeoutSec ?? 90} {lang} />
			{/if}
		</header>

		{#if what}
			<p class={['what', isDss && dssOf(unit).situationSummary && 'quote']} data-testid="v3-what">
				{#if isDss && dssOf(unit).situationSummary}“<RedactedText text={what} {lang} />”{:else}<RedactedText text={what} {lang} />{/if}
			</p>
		{/if}

		{#if unit.kind === 'stolen-sighting' || unit.kind === 'pursuit'}
			<div class="vehicle">
				<VehicleShot cls={vehicleClass} {lang} width={132} />
				<div>
					<p class="v-t">{L(`v3d_class_${vehicleClass}`)} · {officerOn ? L('v3d_mark_shown') : L('v3_masked')}</p>
					<p class="v-s">{officerOn ? L('v3d_mark_shown_body', officer) : L('v3d_mark_masked_body')}</p>
				</div>
			</div>
		{/if}

		{#if corridorAgency}
			<div class="vehicle agency" data-testid="v3-sheet-agency">
				<VehicleShot cls="ambulance" {lang} width={132} decorative />
				<div>
					<p class="v-t a-row"><AgencyMark role="108" {lang} size={22} decorative />{L('v3i_agency_ems')}</p>
					<p class="v-s">{[lang === 'en' ? (corridorAgency.agencyLabel ?? corridorAgency.agency) : L('v3_fact_unit'), corridorAgency.unitId].filter(Boolean).join(' · ')}</p>
				</div>
			</div>
		{/if}

		{#if unit.kind === 'stolen-sighting' && step}
			{@const d = stolenOf(unit)}
			<ol class="steps" aria-label={L('v3d_steps')}>
				<li class:is-selected={!approved} class:done={approved}><b>{#if approved}<Glyph name="check" size={13} />{:else}1{/if}</b>{L('v3d_step_authorise')}</li>
				<li class="ln" aria-hidden="true"></li>
				<li class:is-selected={approved}><b>2</b>{L('v3d_step_open')}</li>
			</ol>
			<div class="step2" data-testid="pursuit-step" data-kind="pursuit" data-id={d.vehicleId} data-refusal={step.refusal ?? ''} data-step="2" data-state={step.state}>
				{#if step.state === 'open'}
					<Glyph name="check" size={16} /><span>{L('dec_next_pursuit_open')}</span>
				{:else}
					<Glyph name="arrowR" size={16} />
					<span>
						<b>{approved ? L('dec_next_now') : L('dec_next_after_authorise')}</b>
						{' '}{step.candidate?.anchor?.roadName ? L('dec_next_open_pursuit_on', step.candidate.anchor.roadName) : L('dec_next_open_pursuit')}
						{#if approved && step.refusal}
							{' '}<span class="refused" data-testid="pursuit-refusal">{step.refusal === 'no-anchor' ? L('dec_refuse_no_anchor') : L('dec_refuse_no_approval')}</span>
						{/if}
					</span>
				{/if}
			</div>
		{/if}

		{#if unit.kind === 'pursuit' && pursuitOf(unit).refusal}
			<p class="inline-refusal" data-testid="pursuit-refusal" role="status">
				<Glyph name="lock" size={16} />{pursuitOf(unit).refusal === 'no-anchor' ? L('dec_refuse_no_anchor') : L('dec_refuse_no_approval')}
			</p>
		{/if}

		{#if facts.length}
			<div class="facts3" style:--n={facts.length}>
				{#each facts as f, i (i)}
					<div><b class:long={String(f.value).length > 9}>{f.value}</b><span>{f.label}</span></div>
				{/each}
			</div>
		{/if}

		{#if unit.kind === 'stolen-sighting' && reads.length}
			<section class="sec" aria-labelledby="v3d-reads-h">
				<h3 class="sec-t" id="v3d-reads-h"><Glyph name="anpr" size={16} />{L('v3d_reads', reads.length, camCount, Math.max(1, Math.round(readSpan / 60_000)))}</h3>
				<ol class="reads">
					{#each reads as r, i (r.id)}
						<li class="rd" class:last={i === reads.length - 1}>
							<i aria-hidden="true"></i>
							<span class="rd-w">{#if r.cam}<Id value={r.cam} />{/if}{#if r.road}{r.cam ? ' · ' : ''}{r.road}{/if}</span>
							<span class="tm">{r.kmh != null ? L('v3_op_speed', Math.round(r.kmh)) : ''}</span>
							<span class="tm">{Number.isFinite(r.at) ? fmtTime(r.at) : '—'}</span>
						</li>
					{/each}
				</ol>
			</section>
		{/if}

		{#if isDss}
			{#if floor}
				<p class="floor" data-testid={floor.testid}><Glyph name={floor.glyph} size={18} /><span>{#if floor.lead}<b>{floor.lead}</b>{' '}{/if}{floor.text}</span></p>
			{/if}
			<section class="sec" aria-labelledby="v3d-opts-h">
				<h3 class="sec-t" id="v3d-opts-h"><Glyph name="route" size={16} />{L('v3d_pick')}<span class="sec-meta">{L('v3d_ranked')}</span></h3>
				{#if dssFailed && !dss}
					<p class="load" data-testid="dss-load-failed">
						<Glyph name="alert" size={16} />{L('dss_load_failed')}
						<button type="button" class="link" onclick={() => (forgetDssObject(unit.id), void ensureDssObject(unit.id))}>{L('dss_retry')}</button>
					</p>
				{:else if !dss}
					<div class="opts" aria-busy="true">
						{#each [0, 1, 2] as i (i)}<div class="opt-skel"></div>{/each}
						<p class="sr">{L('dss_loading')}</p>
					</div>
				{:else}
					<div class="opts" role="radiogroup" aria-labelledby="v3d-opts-h" data-testid="dss-coa-list">
						{#each selectable as c, i (c.coaId)}
							<OptionCard
								coa={c}
								selected={coaId === c.coaId}
								recommended={c.coaId === dss.recommendation.topCoaId}
								index={i}
								{lang}
								onselect={choose}
								onkeynav={(e) => {
									if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
									e.preventDefault();
									e.stopPropagation();
									const next = selectable[(i + (e.key === 'ArrowDown' ? 1 : selectable.length - 1)) % selectable.length];
									choose(next.coaId);
									void tick().then(() => (document.querySelector(`[data-testid="v3-option"][data-coa-id="${CSS.escape(next.coaId)}"]`) as HTMLElement | null)?.focus());
								}}
							/>
						{/each}
					</div>
					{#each blockedRows as c (c.coaId)}
						<BlockedOption coa={c} reason={coaBlockReason(lang, c)} best={c.coaId === bestBlockedId} request={requestEvent ? requestUnit : null} {lang} />
					{/each}
				{/if}
			</section>
		{/if}

		<ChangeList rows={changeRows} {unchanged} title={changesTitle} {lang} />

		{#if !isDss && floor}
			<p class="floor" class:expired data-testid={floor.testid} role={expired ? 'status' : undefined}>
				<Glyph name={floor.glyph} size={18} /><span>{#if floor.lead}<b>{floor.lead}</b>{' '}{/if}{floor.text}</span>
			</p>
		{/if}

		{#if howLines.length}
			<details class="why">
				<summary><Glyph name="chevD" size={16} class="chev" />{L('v3d_how')}</summary>
				<div class="in">
					{#each howLines as l, i (i)}<p>{l}</p>{/each}
				</div>
			</details>
		{/if}

		{#if isDss && dss}
			<details class="why">
				<summary><Glyph name="chevD" size={16} class="chev" />{L('v3d_why_this')}</summary>
				<div class="in">
					{#each whyLines as l, i (i)}<p>{l}</p>{/each}
					{#if aiLine}<p><V3Tag tone="ai" glyph="spark" size="sm">{L('v3d_ai_view')}</V3Tag> {aiLine}</p>{/if}
					<a class="link" href={analystHref}>{L('v3d_full_analysis')} <Glyph name="arrowUR" size={16} /></a>
				</div>
			</details>
		{/if}
	</div>

	<div class="act" data-part="decision-footer">
		{#if standing}
			<div class="refusal" role="alert" data-testid="decision-refusal">
				<Glyph name="alert" size={18} />
				<p>
					<b>{standing.text}</b>
					{#if standing.detail}<span class="verbatim" data-testid="v3-refusal-detail">“{standing.detail}”</span>{/if}
				</p>
			</div>
		{/if}

		{#if phase === 'answered'}
			<p class="locked" data-testid="v3-locked"><Glyph name="lock" size={16} />{L('v3d_answered_here')}</p>
		{:else}
			<OfficerGate {lang} />

			{#if reasonFor}
				<div class="reason">
					<label for="v3d-reason-{unit.id}">{L('v3d_reason_label', secondaryLabel(reasonFor).replace(/…$/, ''))}</label>
					<input
						bind:this={reasonField}
						id="v3d-reason-{unit.id}"
						class="field"
						data-testid={unit.kind === 'stolen-sighting' ? 'stolen-dismiss-reason' : 'decision-reason'}
						maxlength={500}
						autocomplete="off"
						placeholder={L(unit.kind === 'echallan' ? 'dec_reason_placeholder_echallan' : unit.kind === 'corridor-request' ? 'dec_reason_placeholder_corridor' : unit.kind === 'dss' ? 'dec_reason_placeholder_dss' : 'dec_reason_placeholder')}
						bind:value={reason}
						onkeydown={(e) => {
							if (e.key === 'Escape') {
								e.preventDefault();
								reasonFor = null;
								reason = '';
							}
						}}
					/>
				</div>
			{/if}

			<div class="btns">
				{#each acts.secondary as a (a)}
					{@const block = secondaryBlock(a)}
					<button
						type="button"
						class="btn ghost"
						data-testid="v3-secondary"
						data-action={a}
						aria-disabled={!!block || busy}
						title={block ?? undefined}
						onclick={() => void act(a, false)}>{secondaryLabel(a)}</button
					>
				{/each}
				{#if acts.primary}
					<button
						bind:this={primaryBtn}
						type="button"
						class="btn primary grow"
						data-testid="v3-primary"
						data-action={acts.primary}
						aria-disabled={!!primaryBlock || busy}
						aria-describedby={blockLine ? `v3d-block-${unit.id}` : undefined}
						title={primaryBlock ?? undefined}
						onclick={() => void act(acts.primary!, true)}
					>
						{#if busy}<span class="spin" aria-hidden="true"></span>{/if}<span class="lbl-txt" title={primaryLabel}>{primaryLabel}</span>
					</button>
				{/if}
			</div>
			{#if blockLine}<p class="block" id="v3d-block-{unit.id}" data-testid="v3-block-reason">{blockLine}</p>{/if}
		{/if}
	</div>
</div>

<style>
	.sheet-in {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
	}

	.scroll {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 20px;
		min-height: 0;
		padding: 24px 26px 18px;
		overflow: auto;
		scrollbar-width: thin;
		scrollbar-color: var(--v3-s4) transparent;
	}

	.banner {
		position: relative;
		flex: none;
		height: 128px;
		margin: -24px -26px -12px;
		overflow: hidden;
	}

	.banner img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: 50% 58%;
	}

	/* a short screen keeps its room for the decision: the picture becomes a strip */
	@media (max-width: 1500px), (max-height: 820px) {
		.banner {
			height: 76px;
			margin-bottom: -18px;
		}
	}

	.banner::after {
		content: '';
		position: absolute;
		inset: 0;
		background: linear-gradient(to bottom, transparent 30%, var(--v3-scrim));
	}

	.sh-top {
		position: relative;
		display: flex;
		gap: 14px;
		align-items: flex-start;
	}

	.art {
		flex: none;
		width: 60px;
		height: 60px;
		overflow: hidden;
		border-radius: 16px;
		background: var(--v3-map-bg);
	}

	.art img {
		display: block;
		width: 100%;
		height: 100%;
	}

	.head {
		flex: 1;
		min-width: 0;
	}

	.micro {
		margin: 0;
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 600;
		color: var(--v3-t2);
	}

	.title {
		margin: 2px 0 10px;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 650;
		color: var(--v3-t1);
		overflow-wrap: anywhere;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.what {
		margin: 0;
		font-size: 16px;
		line-height: 24px;
		color: var(--v3-t1);
	}

	.facts3 {
		display: grid;
		grid-template-columns: repeat(var(--n), minmax(0, 1fr));
		gap: 10px;
	}

	.facts3 div {
		padding: 12px 14px;
		border-radius: 12px;
		background: var(--v3-s2);
	}

	.facts3 b {
		display: block;
		font-size: 18px;
		line-height: 24px;
		font-weight: 650;
		color: var(--v3-t1);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	/* a place name or a long figure: smaller, wrapping between words (never inside one) */
	.facts3 b.long {
		font-size: 15px;
		line-height: 20px;
		white-space: normal;
		overflow-wrap: break-word;
	}

	.facts3 span {
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		color: var(--v3-t2);
	}

	.vehicle {
		display: flex;
		gap: 16px;
		align-items: center;
		padding: 12px 16px;
		border-radius: 14px;
		background: var(--v3-s2);
	}

	.vehicle :global(.shot) {
		flex: none;
		width: 132px;
	}

	.a-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.v-t {
		margin: 0;
		font-weight: 650;
		color: var(--v3-t1);
	}

	.v-s {
		margin: 2px 0 0;
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		color: var(--v3-t2);
	}

	.steps {
		display: flex;
		gap: 8px;
		align-items: center;
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: var(--v3-text-meta);
		font-weight: 650;
		color: var(--v3-t3);
	}

	.steps li {
		display: flex;
		gap: 8px;
		align-items: center;
	}

	.steps b {
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		border-radius: 11px;
		background: var(--v3-s3);
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
	}

	.steps li.is-selected {
		color: var(--v3-t1);
	}

	.steps li.is-selected b {
		background: var(--v3-t1);
		color: var(--v3-bg);
	}

	.steps li.done b {
		background: var(--v3-ok-veil);
		color: var(--v3-ok-text);
	}

	.steps .ln {
		width: 28px;
		height: 2px;
		background: var(--v3-s4);
	}

	.step2,
	.inline-refusal {
		display: flex;
		gap: 8px;
		align-items: flex-start;
		margin: -8px 0 0;
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		color: var(--v3-t2);
	}

	.step2 :global(svg),
	.inline-refusal :global(svg) {
		flex: none;
		margin-top: 1px;
	}

	.step2 b {
		color: var(--v3-t1);
		font-weight: 600;
	}

	.refused {
		color: var(--v3-alert-text);
	}

	.sec-t {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0 0 10px;
		font-size: var(--v3-text-meta);
		font-weight: 700;
		color: var(--v3-t2);
	}

	.sec-meta {
		margin-left: auto;
		font-weight: 600;
		color: var(--v3-t3);
	}

	.reads {
		display: flex;
		flex-direction: column;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.rd {
		position: relative;
		display: grid;
		grid-template-columns: 18px minmax(0, 1fr) auto auto;
		gap: 10px;
		align-items: center;
		padding: 7px 0;
		font-size: 14px;
		color: var(--v3-t1);
	}

	.rd i {
		position: relative;
		z-index: 1;
		justify-self: center;
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--v3-t2);
	}

	.rd.last i {
		background: var(--v3-alert);
		box-shadow: 0 0 0 4px var(--v3-alert-veil);
	}

	.rd::before {
		content: '';
		position: absolute;
		top: 0;
		bottom: 0;
		left: 8px;
		width: 2px;
		background: var(--v3-s4);
	}

	.rd:first-child::before {
		top: 50%;
	}

	.rd:last-child::before {
		bottom: 50%;
	}

	.rd-w {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.tm {
		color: var(--v3-t2);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.opts {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin-bottom: 10px;
	}

	.opt-skel {
		height: 74px;
		border-radius: 16px;
		background: var(--v3-s2);
	}

	.load {
		display: flex;
		gap: 8px;
		align-items: center;
		margin: 0;
		font-size: 14px;
		color: var(--v3-t2);
	}

	.floor {
		display: flex;
		gap: 10px;
		margin: 0;
		padding: 12px 14px;
		border-radius: 12px;
		background: var(--v3-s2);
		font-size: 14px;
		line-height: 20px;
		color: var(--v3-t2);
	}

	.floor :global(svg) {
		flex: none;
		margin-top: 1px;
		color: var(--v3-t1);
	}

	.floor b {
		color: var(--v3-t1);
		font-weight: 650;
	}

	.floor.expired {
		border: 1px solid var(--v3-line-3);
	}

	details.why summary {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 15px;
		font-weight: 650;
		color: var(--v3-t1);
		list-style: none;
		cursor: pointer;
	}

	details.why summary::-webkit-details-marker {
		display: none;
	}

	details.why[open] summary :global(.chev) {
		transform: rotate(180deg);
	}

	details.why .in {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin-top: 10px;
		font-size: 14px;
		line-height: 21px;
		color: var(--v3-t2);
	}

	details.why .in p {
		margin: 0;
	}

	.link {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 0;
		border: 0;
		background: none;
		color: var(--v3-brand-text);
		font: inherit;
		font-weight: 600;
		text-decoration: none;
		cursor: pointer;
	}

	.link:hover {
		text-decoration: underline;
	}

	/* ── the action bar ── */
	.act {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 16px 26px 20px;
		border-top: 1px solid var(--v3-line-2);
		background: var(--v3-s1);
	}

	.refusal {
		display: flex;
		gap: 10px;
		padding: 10px 14px;
		border: 1px solid var(--v3-line-3);
		border-radius: 12px;
		background: var(--v3-s2);
		color: var(--v3-t1);
		font-size: 14px;
		line-height: 20px;
	}

	.refusal :global(svg) {
		flex: none;
		margin-top: 1px;
		color: var(--v3-decide-text);
	}

	.refusal p {
		margin: 0;
	}

	.refusal b {
		font-weight: 650;
	}

	.verbatim {
		display: block;
		margin-top: 2px;
		color: var(--v3-t2);
	}

	.locked {
		display: flex;
		gap: 8px;
		align-items: center;
		margin: 0;
		font-size: 14px;
		color: var(--v3-t2);
	}

	.reason {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.reason label {
		font-size: var(--v3-text-meta);
		font-weight: 600;
		color: var(--v3-t2);
	}

	.field {
		height: var(--v3-ctl-lg);
		padding: 0 14px;
		border: 1px solid var(--v3-line-2);
		border-radius: 12px;
		background: var(--v3-s2);
		color: var(--v3-t1);
		font: inherit;
		font-size: 15px;
	}

	.field::placeholder {
		color: var(--v3-t3);
	}

	.btns {
		display: flex;
		gap: 10px;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		flex: none;
		height: var(--v3-ctl-lg);
		padding: 0 20px;
		border: 1px solid var(--v3-line-2);
		border-radius: 22px;
		font: inherit;
		font-size: 15px;
		font-weight: 650;
		cursor: pointer;
		transition: background-color var(--v3-dur-1) var(--v3-ease);
	}

	.btn.grow {
		flex: 1;
		min-width: 0;
	}

	.lbl-txt {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.btn.ghost {
		background: transparent;
		color: var(--v3-t1);
	}

	.btn.ghost:hover {
		background: var(--v3-s2);
	}

	.btn.primary {
		border-color: transparent;
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
	}

	.btn.primary:hover {
		background: var(--v3-primary-hover);
	}

	.btn[aria-disabled='true'] {
		cursor: not-allowed;
		color: var(--v3-t3);
	}

	.btn.primary[aria-disabled='true'] {
		border-color: var(--v3-line-1);
		background: var(--v3-s3);
	}

	.btn:focus-visible,
	.field:focus-visible,
	.link:focus-visible,
	summary:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.spin {
		width: 14px;
		height: 14px;
		border: 2px solid currentColor;
		border-right-color: transparent;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.block {
		margin: -4px 0 0;
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		color: var(--v3-t2);
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	@media (max-width: 1500px) {
		.scroll {
			gap: 16px;
			padding: 20px 22px 14px;
		}

		.act {
			padding: 14px 22px 16px;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.spin {
			animation: none;
		}
	}
</style>
