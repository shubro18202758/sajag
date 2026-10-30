<script lang="ts">
	/**
	 * ObjectPage (V3-SPEC §5.4, §6.3, §6.4; phase P3) — "tell me everything about this", for every kind the
	 * city picture holds: a reported situation, a corridor event, a vehicle, a named place, an operation, a
	 * junction, a camera, a unit request, a recommendation, a camera read.
	 *
	 *   HeroMap    the real map at the place (MapThumb; no Cesium viewer), crumbs, "Open in the map"
	 *   TitleBar   art, kind line, display title (a mark in a masked chip), ≤ 4 tags (ONE provenance tag),
	 *              at most one white primary — only when a decision waits, and it opens that decision's one
	 *              home (never a verb on this page) — then "Ask about it" and More
	 *   Field AI   a camera's road state from a still; a road's two-hour forecast and waterlogging (LazyFieldPanels)
	 *   Tabs       Overview · Sources · Reads · Pursuit · Timeline · Nearby · Record; Record holds EVERY field
	 *              the v2 inspector shows (its registered sections and property groups, composed by import)
	 *   Side       the decisions that wait on or touch this record (link cards), the decision-support section
	 *              (generate / promote; v2, by import), key facts, recent activity and the rule in words
	 *
	 * Data: the deck's existing stores only (ops, the city registry, the dossier loader the inspector uses,
	 * the object graph, decision units) — no new endpoint. The page writes nothing itself: the only writes are
	 * the v2 components' own (lifecycle verbs, a pursuit's Request unit, decision support's Generate and
	 * Promote), each one POST per press and each behind its own officer rule.
	 *
	 * Ethics on the page: marks masked unless a duty officer is named (the adapters' guard, ops.plate, the
	 * workspace mask on free text); OSINT text never links a news or social source (an official tier's https
	 * link only), redactions read as chips, a context alert is never counted; one honest provenance tag.
	 */
	import { onDestroy, onMount, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import type { Component } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { fmtWindowIst } from '$lib/ops/format';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { dossier } from '$lib/gods-eye/entities/dossier.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { parseUrn } from '$lib/gods-eye/city-api';
	import { isPublicKind } from '$lib/citizen/holds';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { toasts } from '$lib/shell/toast.svelte';
	import { registerProviders } from '$lib/workspace/providers';
	import { liveWorld } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { adapterFor, rowOf } from '$lib/workspace/kinds';
	import { kindMany } from '$lib/workspace/kinds/generic';
	import { actionsFor, inspectorSectionsFor } from '$lib/workspace/registry';
	import type { ObjectRow } from '$lib/workspace/types';
	import type { PropRow, Run } from '$lib/workspace/kinds/common';
	import { readReport } from '$lib/osint/model';
	import { dssState } from '$lib/dss/dss-store.svelte';
	import LazyDecisionSupportSection from '$lib/dss/LazyDecisionSupportSection.svelte';
	import LazyPursuitSection from '$lib/decisions/sections/LazyPursuitSection.svelte';
	import LifecycleVerbs from '$lib/decisions/sections/LifecycleVerbs.svelte';
	import LazyPlaceSection from '$lib/osint/LazyPlaceSection.svelte';
	import { decisionUnits } from '$lib/decisions/units';
	import { Menu, Popover, provideUiLang } from '$lib/ui';
	import type { MenuItemSpec } from '$lib/ui/types';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.workspace';
	import '$lib/i18n/packs.osint';
	import '$lib/i18n/packs.wall';
	import '$lib/v3/packs.v3';
	import './packs.object';
	import Glyph from '../Glyph.svelte';
	import { v3Bar } from '../shell/v3-bar.svelte';
	import { decisionVM, roadLines } from '../home/view';
	import HeroMap from './HeroMap.svelte';
	import TitleBar from './TitleBar.svelte';
	import Tabs from './Tabs.svelte';
	import Panel from './Panel.svelte';
	import FactsCard from './FactsCard.svelte';
	import FiguresPanel from './FiguresPanel.svelte';
	import DecisionCTA from './DecisionCTA.svelte';
	import ActivityList from './ActivityList.svelte';
	import SourcesList from './SourcesList.svelte';
	import NearbyList from './NearbyList.svelte';
	import RecordTab from './RecordTab.svelte';
	import OsintOverview from './OsintOverview.svelte';
	import VehicleOverview from './VehicleOverview.svelte';
	import ReadsList from './ReadsList.svelte';
	import AskPanel from './AskPanel.svelte';
	import LazyFieldPanels from './LazyFieldPanels.svelte';
	import {
		PROVENANCE,
		analystHref,
		artOf,
		posterOf,
		credibilityChecks,
		effectTiles,
		mapHref,
		objectHref,
		percent,
		provenanceOf,
		reportingSources,
		tabsFor,
		type FactRow,
		type TabId,
		type TitleTag,
	} from './model';
	import { activityOf, decisionsFor, heroVM, kindLine, nearbyOf, osintFacts, readsOf, shown, titleText } from './view';

	let { urn }: { urn: string | null } = $props();

	provideUiLang(() => ops.lang);
	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	// ── clocks: 1 s for countdowns ──────────────────────────────────────────
	let now = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(id);
	});

	// ── the record ──────────────────────────────────────────────────────────
	const officer = $derived(ops.officerOn);
	// the traffic feed's honest label rides every road record: anything but a live feed reads SIMULATED
	const simulatedFeed = $derived(ops.trafficFeed?.label !== 'live');
	$effect(() => {
		liveWorld.simulatedFeed = simulatedFeed;
	});
	const graph = $derived(liveWorld.graph());
	const current = $derived(!!urn && dossier.urn === urn);
	const data = $derived(current ? dossier.data : null);
	const dState = $derived(!urn ? 'bad' : current ? dossier.state : 'loading');
	const row = $derived.by((): ObjectRow | null => {
		if (!urn) return null;
		const g = graph.get(urn);
		if (g) return g;
		return data?.entity && data.entity.urn === urn ? rowOf(data.entity, { simulatedFeed }) : null;
	});
	const kind = $derived(row?.kind ?? parseUrn(urn)?.kind ?? 'other');
	const links = $derived(row ? graph.links(row.urn) : []);
	const view = $derived.by(() => {
		if (!row) return null;
		return adapterFor(row.kind).view(row, {
			lang,
			now,
			officer,
			plate: (raw) => ops.plate(raw),
			graph,
			links,
			dossier: data,
			phases: (id) => {
				const ev = ops.eventById(id);
				return ev ? ev.phases.map((ph) => ({ label: ph.label, window: fmtWindowIst(ph.startTime, ph.endTime, now) })) : null;
			},
			publicKind: (k) => isPublicKind(k),
		});
	});
	const report = $derived(row?.kind === 'osint_event' ? readReport(row.props) : null);
	const withheld = $derived(dState === 'withheld');
	const missing = $derived((dState === 'not-found' || dState === 'down') && !row);

	// ── decisions (link cards to one home each; never a verb here) ─────────
	const units = $derived.by(() => {
		void cityRegistry.version;
		return decisionUnits(ops);
	});
	const ctas = $derived(urn ? decisionsFor(urn, lang, now, units) : []);
	const own = $derived(ctas.filter((c) => !c.touches));

	// ── what the page shows ────────────────────────────────────────────────
	const title = $derived(row ? titleText(row, view, now) : '');
	const titleRuns = $derived.by((): readonly Run[] => {
		if (!row) return [];
		if (row.kind === 'osint_event' || row.kind === 'event' || !view) return [{ text: shown(title) }];
		if (row.kind === 'vehicle') {
			const watched = row.props.earmark_state === 'flagged' || row.props.earmark_state === 'watch';
			return [{ text: `${L(watched ? 'obj_veh_title_watch' : 'obj_screen_vehicle')} ` }, ...view.title];
		}
		return view.title;
	});
	const hero = $derived(row && !withheld ? heroVM(row, links, report, own.length > 0, title, lang) : { overlay: null, at: null, alt: L('obj_hero_alt', title || L('obj_screen_other')), zoom: 15 });
	const roads = $derived(roadLines());
	const crumbs = $derived([{ label: L('obj_crumb_home'), href: '/' }, { label: kindMany(kind, lang) }]);
	const toMap = $derived(urn ? mapHref(urn, hero.at, kind) : '/gods-eye');
	const analyst = $derived(urn ? analystHref(urn) : '/analyst');

	const checks = $derived(report ? credibilityChecks(report, report.toponym) : []);
	const effects = $derived(report ? effectTiles(report, (u) => graph.get(u)?.label ?? null).map((e) => ({ ...e, notes: e.notes.map((n) => shown(n)) })) : []);
	const reads = $derived(row?.kind === 'vehicle' ? readsOf(row.urn, links) : []);
	const activity = $derived(activityOf(data, lang, now));
	const nearby = $derived(nearbyOf(links, lang, now));
	const pursuitOpen = $derived(
		row?.kind === 'vehicle' ? !!ops.pursuitFor(row.id) : row?.kind === 'event' ? ops.eventById(row.id)?.eventKind === 'vehicle_pursuit' : false,
	);
	const recordCount = $derived(view ? view.groups.reduce((n, g) => n + g.rows.length, 0) : 0);
	const tabs = $derived(
		tabsFor(kind, {
			sources: report ? reportingSources(report).length : 0,
			reads: reads.length,
			pursuit: pursuitOpen,
			timeline: activity.length,
			nearby: new Set(links.map((l) => l.row.urn)).size,
			record: recordCount,
		}),
	);
	let tab = $state<TabId>('overview');
	$effect(() => {
		if (!tabs.some((x) => x.id === tab)) tab = 'overview';
	});

	/** The registered v2 sections the Record tab shows (Pursuit, decision links and decision support have their own homes here). */
	const HOMED = new Set(['pursuit', 'decisions.links', 'dss']);
	const sections = $derived(row ? inspectorSectionsFor(row.kind).filter((s) => !HOMED.has(s.id)) : []);
	const dssKind = $derived(row?.kind === 'osint_event' || row?.kind === 'event');
	const dssHost = $derived(dssKind && (!own.some((c) => c.kind === 'dss') || dssState.promoteUrn === urn));

	const art = $derived(row ? artOf(row) : { src: null, glyph: 'pin' });
	const istHourNow = $derived(Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Asia/Kolkata' }).format(now)));
	const poster = $derived(row && !withheld ? posterOf(row, istHourNow) : null);
	const prov = $derived(row ? provenanceOf(row) : null);
	const TONE: Record<string, string> = { warning: 'decide', success: 'ok', danger: 'alert', primary: 'brand', none: 'neutral' };
	const tags = $derived.by((): TitleTag[] => {
		if (!row || !view) return [];
		const out: TitleTag[] = [];
		if (prov) {
			const p = PROVENANCE[prov];
			out.push({ text: L(p.key), tone: p.tone, glyph: p.glyph, title: L(p.tip), attrs: { 'data-provenance': prov, 'data-testid': 'obj-provenance' } });
		}
		if (row.kind === 'osint_event' && row.credibility != null) out.push({ text: L('obj_cred', row.credibility.toFixed(2)), tone: 'neutral' });
		for (const tg of view.tags) out.push({ text: tg.text, tone: TONE[tg.intent] ?? 'neutral', title: tg.tooltip ?? null });
		const waits: TitleTag | null = own.length
			? { text: L(own.some((c) => c.kind === 'dss') ? 'obj_tag_response_waits' : 'obj_tag_decision_waits'), tone: 'decide', glyph: 'clock', attrs: { 'data-testid': 'obj-waits' } }
			: null;
		return waits ? [...out.slice(0, 3), waits] : out.slice(0, 4);
	});
	const primary = $derived(own.length ? { href: own[0].href, label: L(own[0].kind === 'dss' ? 'obj_act_review_response' : 'obj_act_review') } : null);

	const facts = $derived.by((): FactRow[] => {
		if (!row || !view) return [];
		if (report) return osintFacts(row, report, data, lang, now);
		const rows: PropRow[] = view.groups.flatMap((g) => g.rows);
		return rows.slice(0, 7).map((r) => ({ key: r.key, prop: r.value }));
	});
	const rule = $derived(
		row?.kind === 'osint_event' ? L('obj_rule_osint') : row?.kind === 'vehicle' || row?.kind === 'sighting' || row?.kind === 'camera' ? L('obj_rule_vehicle') : L('obj_rule_default'),
	);
	const event = $derived(row?.kind === 'event' ? ops.eventById(row.id) : null);
	const placeReports = $derived(row?.kind === 'place' ? links.filter((l) => l.row.kind === 'osint_event').map((l) => l.row) : []);
	const progress = $derived(row?.kind === 'convoy' ? percent(row.props.progress) : null);
	const nextJunction = $derived(row?.kind === 'convoy' && typeof row.props.next_junction_name === 'string' ? shown(row.props.next_junction_name) : null);

	// ── Ask about it (one turn per press; never while one streams) ─────────
	let askOpen = $state(false);
	let askSeq = $state(0);
	let askStatus = $state<'streaming' | 'done' | 'error'>('done');
	function ask() {
		if (askOpen && askStatus === 'streaming') return;
		askStatus = 'streaming';
		askSeq++;
		askOpen = true;
	}

	// ── navigation inside the page ─────────────────────────────────────────
	function open(u: string) {
		const href = objectHref(u);
		if (href) void goto(href);
	}

	// ── the record follows the route ───────────────────────────────────────
	$effect(() => {
		const u = urn;
		untrack(() => {
			dossier.open(u);
			if (u) selection.select(u, { source: 'dossier' });
			tab = 'overview';
			askOpen = false;
		});
	});

	// ── More ───────────────────────────────────────────────────────────────
	async function copyLink() {
		const href = urn ? objectHref(urn) : null;
		if (!href) return;
		try {
			await navigator.clipboard.writeText(`${location.origin}${href}`);
			toasts.push({ kind: 'act', title: L('obj_act_copied') });
		} catch {
			toasts.push({ kind: 'error', title: L('obj_act_copy_failed') });
		}
	}
	const moreItems = $derived.by((): MenuItemSpec[] => {
		if (!row) return [];
		const acts = actionsFor(row).filter((a) => !a.id.startsWith('decisions.lifecycle'));
		const items: MenuItemSpec[] = acts.map((a) => ({
			id: a.id,
			label: a.label,
			icon: a.icon,
			intent: a.intent,
			disabled: a.disabled,
			disabledReason: a.disabledReason ?? null,
			onclick: () => {
				if (a.id === 'osint.sources') tab = 'sources';
				else void a.run();
			},
		}));
		if (items.length) items.push({ id: 'obj.div', kind: 'divider' });
		items.push(
			{ id: 'obj.copy', label: L('obj_act_copy'), icon: 'link', onclick: () => void copyLink() },
			{ id: 'obj.analyst', label: L('obj_act_analyst'), icon: 'th', href: analyst },
			{ id: 'obj.record', label: L('obj_act_record'), icon: 'properties', onclick: () => (tab = 'record') },
		);
		return items;
	});

	// ── the shell (the v2 contract + the V3 bar) ───────────────────────────
	let Omnibar = $state<Component | null>(null);
	onMount(() => {
		registerProviders();
		ops.start();
		cityRegistry.start();
		void import('$lib/workspace/components/omnibar/Omnibar.svelte').then((m) => (Omnibar = m.default as unknown as Component));
	});
	onDestroy(() => {
		dossier.close();
		cityRegistry.stop();
		ops.stop();
		if (typeof window !== 'undefined') delete (window as unknown as Record<string, unknown>).__V3_OBJECT__;
	});

	$effect(() => {
		commandBar.lang = ops.lang;
		commandBar.onLangChange = (l: string) => (ops.lang = l);
		commandBar.onShare = null;
		commandBar.onSearch = (q?: string) => workspace.openOmnibar(q);
		commandBar.onInbox = null;
	});
	$effect(() => {
		commandBar.officer = { value: ops.dutyOfficer, fromSession: ops.dutyOfficerFromSession, set: (v: string) => ops.setDutyOfficer(v) };
	});
	$effect(() => {
		const f = ops.trafficFeed;
		commandBar.exercise =
			f && (f.label === 'simulated' || f.label === 'mixed')
				? {
						label: f.label,
						text: f.label === 'simulated' ? L('wall_exercise_simulated', f.segments) : L('wall_exercise_mixed', Math.round((100 * f.synthetic) / Math.max(1, f.real + f.synthetic))),
					}
				: null;
	});
	$effect(() => {
		commandBar.inboxCount = units.length;
		commandBar.inboxIntent = units.length ? 'warning' : 'none';
	});
	const SCREEN = new Set(['osint_event', 'event', 'vehicle', 'place', 'convoy', 'junction', 'camera', 'dispatch', 'recommendation', 'sighting']);
	$effect(() => {
		const k = SCREEN.has(kind) ? kind : 'other';
		v3Bar.title = L(`obj_screen_${k}`);
		v3Bar.sub = L(`obj_sub_${k}`);
		v3Bar.active = 'home';
	});
	// the alert list (the shell's bell) primes on the first full answer, as on Home
	const mountedAt = Date.now();
	const firstRound = $derived(
		(ops.boardUpdated > 0 && ops.recommendationsUpdated > 0 && ops.dispatchesUpdated > 0 && ops.escortsDeployed !== null && cityRegistry.status !== 'idle') || now - mountedAt > 10_000,
	);
	$effect(() => {
		v3Bar.decisions = firstRound
			? units.map((u) => {
					const vm = decisionVM(u, lang, now);
					return { key: vm.key, title: vm.maskedTitle, href: vm.href, emulated: vm.emulated };
				})
			: null;
	});

	// ── the test hook (the smoke reads the page's own state) ───────────────
	$effect(() => {
		if (typeof window === 'undefined') return;
		(window as unknown as Record<string, unknown>).__V3_OBJECT__ = {
			urn,
			kind,
			state: dState,
			tab,
			tabs: tabs.map((x) => x.id),
			officerOn: officer,
			provenance: prov,
			decisions: ctas.map((c) => c.key),
			sections: sections.map((s) => s.id),
			record: recordCount,
		};
	});
</script>

<svelte:head>
	<title>{title ? `${title} · Sajag` : 'Sajag'}</title>
</svelte:head>

<div class="obj" data-v3="object" data-urn={urn ?? ''} data-kind={kind} data-state={dState} data-testid="obj-page">
	{#if !urn}
		<div class="state" data-testid="obj-bad">
			<img src="/illustrations/empty/select-something.svg" alt="" width="240" height="150" />
			<h1>{L('obj_bad_h')}</h1>
			<p>{L('obj_bad')}</p>
			<a class="back" href="/">{L('obj_back_home')}</a>
		</div>
	{:else}
		<HeroMap {hero} {crumbs} mapHref={toMap} {lang} {roads} poster={poster} />
		{#if withheld}
			<div class="state under" data-testid="obj-withheld">
				<Glyph name="eyeoff" size={40} />
				<h1>{L('obj_withheld_h')}</h1>
				<p>{L('obj_withheld')}</p>
				<a class="back" href="/">{L('obj_back_home')}</a>
			</div>
		{:else if missing}
			<div class="state under" data-testid="obj-missing">
				<img src={dState === 'down' ? '/illustrations/empty/offline.svg' : '/illustrations/empty/no-reports.svg'} alt="" width="240" height="150" />
				<h1>{L('obj_notfound_h')}</h1>
				<p>{dState === 'down' ? L('obj_down') : L('obj_notfound')}</p>
				<a class="back" href="/">{L('obj_back_home')}</a>
			</div>
		{:else if row && view}
			<TitleBar {art} alert={view.alert} kindLine={kindLine(row, view, report, lang, now)} title={titleRuns} {tags} {primary} {lang} {now}>
				{#snippet actions()}
					<button type="button" class="btn-ghost" onclick={ask} data-testid="obj-ask-btn" aria-expanded={askOpen} aria-label={L('obj_act_ask')}><Glyph name="spark" size={20} /><span class="lbl">{L('obj_act_ask')}</span></button>
					<Popover placement="bottom-end" aria-label={L('obj_act_more')}>
						<button type="button" class="btn-icon" aria-label={L('obj_act_more')} data-testid="obj-more"><Glyph name="more" size={20} /></button>
						{#snippet content({ close })}<div class="menu" data-testid="obj-more-menu"><Menu items={moreItems} onselect={close} label={L('obj_act_more')} /></div>{/snippet}
					</Popover>
				{/snippet}
			</TitleBar>
			{#if dState === 'down'}<p class="down" role="status">{L('obj_down')}</p>{/if}

			<div class="cols">
				<div class="main">
					<Tabs {tabs} bind:value={tab} label={L('obj_tabs_label')} {lang} />
					<div class="body" role="tabpanel" id={`obj-panel-${tab}`} aria-labelledby={`obj-tab-${tab}`} tabindex="-1" data-tab-panel={tab}>
						{#if tab === 'overview'}
							{#if report}
								<OsintOverview {report} summary={report.summary ? shown(report.summary) : null} credibility={row.credibility} {checks} {effects} {lang} />
							{:else if row.kind === 'vehicle'}
								<VehicleOverview {row} {view} {officer} {lang} {now} />
								<FiguresPanel figures={view.figures} {lang} {now} />
							{:else if row.kind === 'place'}
								<Panel title={L('obj_place_h')} testid="obj-place"><LazyPlaceSection {row} dossier={data} /></Panel>
								<Panel title={L('obj_place_reports_h')}>
									{#if placeReports.length}
										<ul class="plain">
											{#each placeReports as r (r.urn)}<li><a href={objectHref(r.urn)}><Glyph name={r.verification === 'OFFICIAL-VERIFIED' ? 'verified' : 'news'} size={16} />{r.label}</a></li>{/each}
										</ul>
									{:else}<p class="quiet">{L('obj_place_reports_none')}</p>{/if}
								</Panel>
							{:else}
								{#if progress != null || nextJunction}
									<Panel title={L('obj_op_h')} testid="obj-progress">
										{#if progress != null}
											<div class="prog" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress} aria-label={L('obj_op_progress', progress)}><i style:width={`${progress}%`}></i></div>
											<p class="quiet">{L('obj_op_progress', progress)}{#if nextJunction}{' · '}{L('obj_op_next', nextJunction)}{/if}</p>
										{:else if nextJunction}<p class="quiet">{L('obj_op_next', nextJunction)}</p>{/if}
									</Panel>
								{/if}
								<FiguresPanel figures={view.figures} {lang} {now} />
								{#if row.kind === 'camera' || row.kind === 'segment'}<LazyFieldPanels {row} {lang} officer={ops.dutyOfficer || null} />{/if}
								{#if view.note}
									<p class="rule-note" data-testid="obj-note"><Glyph name="shield" size={17} /><span>{#if view.note.title}<b>{view.note.title}</b>{' '}{/if}{view.note.text}</span></p>
								{/if}
							{/if}
							{#if event}
								<Panel title={L('obj_ev_actions_h')} testid="obj-event-actions">
									<LifecycleVerbs {event} />
									<p class="quiet">{L('obj_ev_actions_note')}</p>
								</Panel>
							{/if}
						{:else if tab === 'sources' && report}
							<Panel title={L('obj_src_h')}><SourcesList {report} {lang} /></Panel>
						{:else if tab === 'reads'}
							<Panel title={L('obj_reads_h')}><ReadsList {reads} {lang} {now} /></Panel>
						{:else if tab === 'pursuit'}
							<Panel title={L('obj_tab_pursuit')} testid="obj-pursuit"><LazyPursuitSection {row} dossier={data} /></Panel>
						{:else if tab === 'timeline'}
							<Panel title={L('obj_tl_h')}><ActivityList rows={activity} {lang} full waits={own.length ? (own[0].kind === 'dss' ? L('obj_tag_response_waits') : L('obj_tag_decision_waits')) : null} /></Panel>
						{:else if tab === 'nearby'}
							<Panel title={L('obj_near_h')}><NearbyList groups={nearby} {lang} {analyst} /></Panel>
						{:else if tab === 'record'}
							<RecordTab {row} {view} dossier={data} {sections} {lang} {now} onselect={open} />
						{/if}
					</div>
				</div>

				<aside class="side" aria-label={L('obj_facts_h')}>
					{#if askOpen && urn}
						{#key askSeq}<AskPanel {urn} {lang} bind:status={askStatus} onclose={() => (askOpen = false)} />{/key}
					{/if}
					{#each ctas as c (c.key)}<DecisionCTA vm={c} {now} {lang} />{/each}
					{#if dssHost}
						<Panel title={L('obj_dss_h')} flush testid="obj-dss"><LazyDecisionSupportSection {row} dossier={data} /></Panel>
					{/if}
					<FactsCard rows={facts} title={L('obj_facts_h')} {now} onselect={open} />
					<Panel title={L('obj_recent_h')} flush>
						<ActivityList rows={activity} {lang} limit={5} />
					</Panel>
					<p class="rule" data-testid="obj-rule"><Glyph name="shield" size={17} />{rule}</p>
				</aside>
			</div>
		{:else}
			<div class="state under" data-testid="obj-loading" aria-busy="true"><p>{L('obj_loading')}</p></div>
		{/if}
	{/if}
</div>

{#if Omnibar}<Omnibar />{/if}

<style>
	.obj {
		max-width: 2200px;
		padding: 0 0 40px;
	}

	.cols {
		position: relative;
		z-index: 2;
		display: grid;
		grid-template-columns: minmax(0, 1fr) 420px;
		gap: 28px;
		padding: 30px var(--v3-gut) 0;
	}

	.main,
	.side {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.side {
		gap: 18px;
	}

	.body {
		display: flex;
		flex-direction: column;
		gap: 18px;
		padding-top: 18px;
	}

	.body:focus {
		outline: none;
	}

	.btn-ghost,
	.btn-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		height: var(--v3-ctl-lg);
		border: 1px solid var(--v3-line-3);
		border-radius: 22px;
		background: none;
		color: var(--v3-t1);
		font: inherit;
		font-size: var(--v3-text-body);
		font-weight: 650;
		white-space: nowrap;
		cursor: pointer;
	}

	.btn-ghost {
		padding: 0 20px;
	}

	.btn-icon {
		width: var(--v3-ctl-lg);
		border-color: transparent;
		background: var(--v3-s2);
		color: var(--v3-t2);
	}

	.btn-ghost:hover,
	.btn-icon:hover {
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.btn-ghost:focus-visible,
	.btn-icon:focus-visible,
	.back:focus-visible,
	.plain a:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.menu {
		min-width: 260px;
	}

	.rule,
	.rule-note {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		margin: 0;
		padding: 0 4px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 19px;
	}

	.rule :global(.v3-glyph),
	.rule-note :global(.v3-glyph) {
		flex: none;
		margin-top: 1px;
		color: var(--v3-t3);
	}

	.rule-note {
		padding: 14px 16px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
		border: 1px solid var(--v3-line-1);
	}

	.quiet {
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
	}

	.prog {
		height: 6px;
		overflow: hidden;
		border-radius: 3px;
		background: var(--v3-s3);
	}

	.prog i {
		display: block;
		height: 100%;
		border-radius: 3px;
		background: var(--v3-route);
	}

	.plain {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.plain a {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 36px;
		color: var(--v3-t1);
		font-size: 14px;
		text-decoration: none;
	}

	.plain a:hover {
		color: var(--v3-brand-text);
	}

	.down {
		margin: 12px var(--v3-gut) 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		max-width: 560px;
		margin: 80px auto;
		padding: 0 var(--v3-gut);
		color: var(--v3-t2);
		text-align: center;
	}

	.state.under {
		position: relative;
		z-index: 3;
		margin-top: -120px;
	}

	.state h1 {
		margin: 6px 0 0;
		color: var(--v3-t1);
		font-size: var(--v3-text-title);
		font-weight: 650;
		line-height: var(--v3-lh-title);
	}

	.state p {
		margin: 0;
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
	}

	.back {
		margin-top: 8px;
		color: var(--v3-brand-text);
		font-weight: 600;
		text-decoration: none;
	}

	@media (max-width: 1500px) {
		.cols {
			grid-template-columns: minmax(0, 1fr) 360px;
			gap: 20px;
			padding-top: 24px;
		}

		.btn-ghost .lbl {
			display: none;
		}

		.btn-ghost {
			width: var(--v3-ctl-lg);
			padding: 0;
		}
	}

	@media (max-width: 1100px) {
		.cols {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
