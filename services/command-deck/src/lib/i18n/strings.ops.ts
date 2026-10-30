/**
 * Ops-screens string pack (EN / HI / MR) — operator-surface copy for the
 * situation wall, decision queue, dispatch tiles, signal gate card,
 * watchlist console and pursuit plan.
 *
 * The i18n core (strings.ts) stays frozen; this module carries ONLY the new
 * operator vocabulary and exposes `tOps()` which consults this pack first
 * and falls back to the core `t()` — so a missing key here still renders the
 * core's copy or the raw key (never a crash), and every user-facing string
 * this stream adds ships in all three languages.
 */

import { registerPack, t, touchPacks } from './strings';
import { langChunks } from './load';
import type { LangCode } from './strings';

/** Re-export the frozen core resolver so ops components import one module. */
export { t };

type Pack = Record<string, string | ((...args: unknown[]) => string)>;

const en: Pack = {
	// Event kinds (incl. the watchlist-anpr vehicle_pursuit/crime_incident)
	// live in the CORE pack (strings.ts) so every surface resolves them —
	// tOps() falls through to core t() for them.

	// ── Situation masthead ─────────────────────────────────────────────
	mastheadPosture: 'city posture',
	mastheadDwell: (band, tick, need) => `${band} held · tick ${tick}/${need}`,
	mastheadWipeIn: 'committing band',
	mastheadOfficer: 'Duty officer',
	mastheadOfficerPlaceholder: 'name on console',
	mastheadOfficerSet: 'on console',
	mastheadOfficerMissing: 'set a named officer to enable commit actions',
	posture_GREEN: 'Normal operations — city band green.',
	posture_AMBER: 'Corridor operations active — watch the queue and the dwell before any band move.',
	posture_RED: 'Intervene — multiple concurrent pressures, decisions pending beyond tolerance.',
	posture_BLACK: 'Take over — citywide coordination under the control room.',

	// ── Commander counters ─────────────────────────────────────────────
	counterActiveEvents: 'Active events',
	counterPendingDecisions: 'Pending human decisions',
	counterUnitsDispatched: 'Units dispatched',
	counterAmbulanceWindows: 'Ambulance windows granted',

	// ── Decision queue ─────────────────────────────────────────────────
	queueTitle: 'Decision queue',
	queueSub: 'machines propose · a named officer disposes',
	queueEmpty: 'No pending recommendations — the queue is honest about being empty.',
	queueEmptyTileRequests: (n) => `${n} unit request${n === 1 ? '' : 's'} await${n === 1 ? 's' : ''} Approve on the dispatch tiles`,
	queueEchallan: 'e-challan recommendation',
	queueEvidence: 'evidence',
	queueHideEvidence: 'hide evidence',
	queueRule: 'rule',
	queueRetention: 'retention',
	queueApprove: 'Approve',
	queueReject: 'Reject with reason',
	queueReasonPlaceholder: 'reason (logged to the audit trail)',
	queueDecided: (status) => `decided · ${status}`,
	queueGoldenHour: 'golden hour',
	queueOpenPursuit: 'Open pursuit',
	queuePursuitConfirm: 'Confirm pursuit opening — a human initiates, never the machine.',
	queuePursuitHumanConfirms: 'Human confirms',

	// ── Dispatch tiles (field units) ───────────────────────────────────
	dispatchTitle: 'Field unit dispatch',
	dispatchSub: 'requested → approved → en route → on scene',
	dispatchRequestUnit: 'Request unit',
	dispatchUnitPlaceholder: 'unit id, as on the unit list',
	dispatchApprove: 'Approve',
	dispatchDefer: 'Defer',
	dispatchEnRoute: 'en route',
	dispatchOnScene: 'on scene',
	dispatchComplete: 'complete',
	dispatchCancel: 'cancel',
	dispatchAudit: 'audit trail',
	dispatchNone: 'No dispatches yet.',
	dispatchAtWaypoint: (junction) => `waypoint junction ${junction}`,
	dispatchEventClosed: 'event closed',

	// ── Signal gate card ───────────────────────────────────────────────
	gateTitle: 'City signal plans',
	gateSub: 'the gated writer — proposed vs held, in full view',
	gateWriterEnabled: 'writer enabled',
	gateWriterDisabled: 'writer disabled',
	gateCityBand: 'city band',
	gateSubjects: (n) => `${n} band subjects`,
	gatePlanTableBand: 'band',
	gatePlanTableShare: 'priority share',
	gatePlanTableFloor: 'cross green floor (s)',
	gatePlanTableWrites: 'junction writes',
	gateApply: 'Apply plan',
	gateApplying: 'applying…',
	gateApplied: 'plan applied',
	gateHeldBaseline: 'held at baseline',
	gateRefusal: 'refusal',
	gateLastPlan: 'last plan',
	gateRestore: 'Restore',
	gateHistory: 'history',
	gateHistoryEmpty: 'no history rows yet',
	gateScopeNote: 'scope: city (all programmed junctions)',

	// ── AMA module ─────────────────────────────────────────────────────
	amaStages: 'stages',
	amaFloors: 'protocol floors',
	amaWriterPosture: 'writer posture',
	amaShadowEval: 'shadow eval',

	// ── Watchlist console ──────────────────────────────────────────────
	watchTitle: 'Pursuit & watchlist',
	watchSub: 'earmarked plates, ANPR sightings and live traces',
	watchPlate: 'plate',
	watchState: 'earmark',
	watchBasis: 'lawful basis',
	watchRetention: 'retention until',
	watchLastSeen: 'last seen',
	watchEarmark: 'earmark',
	watchClear: 'clear',
	watchReasonPlaceholder: 'reason (min 3 chars)',
	watchDays: 'days',
	watchNone: 'No earmarked vehicles.',
	watchSpeed: (kmh) => `${kmh} km/h`,
	watchSource: 'source',

	// ── Pursuit plan ───────────────────────────────────────────────────
	pursuitTitle: 'Interception choke plan',
	pursuitRank: 'choke',
	pursuitEta: 'graph cost (s)',
	pursuitHold: 'hold cost',
	pursuitSignalized: 'signalized',
	pursuitCaption: 'assists the operator — it never dispatches on its own',
	pursuitNoneForEvent: 'not a pursuit event — no interception plan',
	pursuitLatestSighting: 'latest sighting',
	pursuitSeedSegment: 'seed segment',

	// ── Event dossier ──────────────────────────────────────────────────
	dossierTitle: 'Event dossier',
	dossierMetadata: 'metadata',
	dossierPhases: 'phases',
	dossierAuditNarrative: 'audit narrative',
	dossierAdvisory: 'advisory preview',
	dossierWindow: 'window',

	// ── Degradation ledger ─────────────────────────────────────────────
	ledgerTitle: 'Degradation ledger',
	ledgerSub: 'recurring failures mined from the decisions_log audit trail',
	ledgerEmpty: 'No degradation on record — the audit log is honest about being empty.',
	ledgerEmptyHint: 'every checkpoint answered through its intended tier; nothing withheld, nothing fell back',
	ledgerTimes: (n) => `${n}×`,
	ledgerFirstSeen: (t) => `first ${t}`,
	ledgerSampleRef: 'sample',
	ledgerScanLine: (rows, contexts) => `${rows} audit rows across ${contexts} movements`,
	ledgerTruncated: 'scan truncated — more movements on record than the ledger reads',

	// ── Event lifecycle (C-F verb rail) ────────────────────────────────
	verbApprove: 'Approve',
	verbActivate: 'Activate',
	verbComplete: 'Complete',
	verbCancel: 'Cancel',
	verbConfirmCancel: 'Confirm cancel',
	verbCancelPlaceholder: 'reason for cancelling (logged to the audit trail)',
	verbKeep: 'keep event',
	lifecycleApproved: (who, t) => `approved by ${who} · ${t} IST`,
	lifecycleActivated: (who, t) => `activated by ${who} · ${t} IST`,
	lifecycleCompleted: (who, t) => `completed by ${who} · ${t} IST`,
	lifecycleCancelled: (who, t) => `cancelled by ${who} · ${t} IST`,
	lifecycleClosedDispatches: (n) => `${n} dispatch${n === 1 ? '' : 'es'} closed`,
	lifecycleRefused: (status, detail) => `refused (${status}): ${detail}`,
	lifecycleAllowed: (list) => `allowed from here: ${list}`,
	lifecycleNeedsOfficer: 'a named duty officer is required',
	previewToggle: 'preview',
	previewToggleHint: 'show the labelled use-case fixtures beside the live board',

	// ── Audit stream (a view over server data) ─────────────────────────
	auditSubServer: 'a view over the server audit: officer rows carry the officer glyph, system rows recede; it survives reloads',
	auditScopeLabel: 'audit scope',
	auditScopeEvent: 'selected event',
	auditScopeCity: 'city',
	auditScopeEventNone: 'select a live event to follow its own audit',
	auditViewEvent: (name) => `event audit · ${name}`,
	auditViewCity: 'city feed · all agencies',
	auditViewLegacy: 'legacy adaptive status (no C-C narrative on this oracle)',
	auditViewNone: 'no audit source answered',
	auditCounts: (server, human, local) => `${server} server rows (${human} human), ${local} local`,
	auditClearLocal: 'clear local',
	auditProbeHintScoped: (name) => `Streams one turn from /chat/stream for the selected event (${name}): decider → tactical (Gemma) → tools.`,
	auditProbeTiers: (tiers) => `tiers used: ${tiers}`,
	auditProbeDegraded: 'degraded',
	auditProbeAnswer: 'answer (streamed prose)',
	platesMasked: 'plates masked — name a duty officer to unmask',
	dossierNoAudit: 'No audit rows yet for this event.',
	dossierFixtureAudit: 'Preview fixture — no server audit exists for it.',
	dossierAdvisoryWithheld: 'Operator-only event kind — no citizen advisory is previewed for it (pursuits and crime never leave the operator surfaces).',

	// ── Counters + masthead posture ────────────────────────────────────
	counterEmulatedSuffix: (n) => `· ${n} emulated`,
	labelWaiting: 'waiting',
	postureActive: (n) => `${n} active`,
	posturePending: (n) => `${n} pending decision${n === 1 ? '' : 's'}`,
	postureUnits: (n) => `${n} unit${n === 1 ? '' : 's'} out`,
	mastheadSessionSigned: 'signed in (operator gate)',
	brainDecider: 'decider',
	brainGemma: 'Gemma · tactical',
	brainTier: 'degradation',
	brainLoaded: 'loaded',
	brainLoading: 'loading',
	brainUnreachable: 'unreachable',
	brainConnected: 'connected',
	brainP95: (s) => `p95 ${s} s`,
	brainLatch: (s) => `latch ${s}`,
	brainDegraded: 'degraded',
	feedTitle: 'traffic feed',
	feedSimulated: 'Simulated feed',
	feedMixed: (pct) => `Mixed · ${pct}% simulated`,
	feedLive: 'Live feed',
	feedNone: 'No live feed',

	// ── Situation band + overrides evidence ────────────────────────────
	bandUnknown: 'Unknown',
	bandNoSubject: 'no band subject (no live event observed, no city band)',
	bandSourceEvent: 'event situation log',
	bandSourceCity: 'city band (signal writer)',
	bandSourceNone: 'no band source',
	bandHeld: (dur, t) => `held ${dur} · committed ${t} IST`,
	bandHeldBeyondWindow: 'committed before the log window',
	bandNewestReading: (age) => `newest reading ${age} ago`,
	bandNoHistory: 'no history yet',
	overridesNewest: (src, cls, verdict) => `newest publish: ${src} params at ${cls} · shadow-eval ${verdict}`,
	overridesAdvance: (s) => `advance closure ${s} s`,
	overridesFloor: 'protocol floor applied',
	overridesCount: (n) => `${n} published parameter set${n === 1 ? '' : 's'} on record`,
	overridesNone: 'no parameter set published for this subject yet',
	amaNoFloor: 'none',
	amaDegradation: (tier) => `engine degradation tier ${tier}`,
	amaCheckpointsPaused: 'decider checkpoints paused',

	// ── Signal gate ────────────────────────────────────────────────────
	gateWriterActive: 'writing now',
	gateWriterIdle: 'writer idle',
	gateWriterQueued: (n) => `${n} queued`,
	gateTwinInFlight: (n) => `twin in flight: ${n}`,
	gateRestoreAll: 'Restore all',
	gateRestoreAllConfirm: 'Confirm restore all · city-wide',
	gateRestoreAllKeep: 'keep programs',
	gateRestoreNeedsLive: 'Restore targets the selected live event — preview fixtures carry no signal history',
	gateHistoryUnattributed: 'unattributed',

	// ── Dispatch request ───────────────────────────────────────────────
	dispatchForEvent: (name) => `for ${name}`,
	dispatchAgency: 'agency',
	dispatchUnit: 'unit',
	dispatchWaypoint: 'waypoint',
	dispatchToChoke: (rank, name) => `choke #${rank} · ${name}`,
	dispatchChokeShort: (rank) => `choke #${rank}`,
	dispatchNearSpine: (id, name, m) => `J${id} ${name} · ${m} m from the spine`,
	dispatchNoWaypoint: 'no waypoint (the unit stages at the spine start)',
	dispatchNoWaypointHint: 'loading junctions near the spine…',
	dispatchNotePlaceholder: 'note for the unit (optional, audited)',
	dispatchRequestTo: (agency, target) => `Dispatch ${agency} → ${target}`,
	dispatchSelectLive: 'Select a live event on the board to request a unit for it.',
	dispatch108: 'Ambulance (108) driver',
	dispatchRequestedBy: (who) => `requested by ${who}`,

	// ── Decision queue: filings + pursuit openings ─────────────────────
	queueFiled: (t) => `filed ${t} IST`,
	queuePursuitAnchor: (seg, road, m) => `anchor #${seg} ${road} · ${m} m from the latest sighting`,
	queuePursuitFrom: (rec) => `from approved rec ${rec}`,
	queuePursuitNoAnchor: 'Cannot open: the latest sighting is not on any road within 300 m — no anchor for the pursuit.',
	queuePursuitNoApproval: 'Cannot open: no human-authorised recommendation for this vehicle — a pursuit opens only from a duty officer’s approval (C6).',
	queuePursuitBlockedAnchor: 'no road anchor',
	queuePursuitBlockedApproval: 'needs an approved recommendation (C6)',

	// ── Interception plan honesty ──────────────────────────────────────
	pursuitStale: (age) => `Stale — the latest sighting is older than ${age}: the vehicle may be beyond every junction listed.`,
	pursuitAgo: (age) => `${age} ago`,
	pursuitHeading: (names, basis) => `heading towards ${names} (basis: ${basis})`,
	pursuitAgainstOneway: 'against a one-way',
	pursuitOnward: 'onward via',
	pursuitDownstream: 'downstream',
	pursuitLikelyPassed: 'likely passed',

	// ── Watchlist retention (C6 / DPDP) ────────────────────────────────
	retentionLine: (days, cap) => `retention: sightings ${days} d · earmark ≤ ${cap} d`,
	retentionHealthy: 'reaper healthy',
	retentionFailing: (n) => `reaper failing (${n}× in a row)`,
	retentionLastRun: (t, n) => `last reap ${t} IST · removed ${n}`,
	retentionUnknown: 'retention status unavailable',

	// ── Emulator control plane (C-G) ───────────────────────────────────
	emuSubProxy: 'cause-tape control via the deck proxy (/api/emulator) — every cause is emulated',
	emuLibrary: (n) => `${n} tapes in the emulator library`,
	emuUseCase: 'use case',
	emuClock: 'clock',
	emuHeroCap: (cap) => `flagship tape — capped at ×${cap}`,
	emuHeroCapShort: 'flagship cap',
	emuSampling: (scale, note) => `engine samples every 5 s → at ×${scale}: ${note}`,
	emuSamplingNote: (n, unit) => `1 decision / ${n} sim-${unit === 'min' ? 'min' : 's'}`,
	emuLaunchBtn: 'Launch',
	emuPhase_posting: 'posting',
	emuPhase_running: 'running',
	emuPhase_completed: 'completed',
	emuPhase_stopped: 'stopped',
	emuPhase_interrupted: 'interrupted',
	emuPhase_refused: 'refused',
	emuPhase_failed: 'failed',
	emuReplayOf: 'replay · ',
	emuSince: (age) => `${age} ago`,
	emuProgress: (f, total, d, x) => `frame ${f}/${total}, delivered ${d}, failed ${x}`,
	emuSyncNote: 'this emulator build holds the launch request until the tape ends — the run is followed from its ledger row (the deck proxy drops a held request after 60 s; the run continues)',
	emuRunsTitle: 'runs (ledger)',
	emuReplayClock: 'replay at',
	emuStatus: 'status',
	emuStarted: 'IST',
	emuStop: 'Stop',
	emuReplay: 'Replay',
	emuLivingCity: 'Living city',
	emuLivingStart: 'Start',
	emuLivingStop: 'Stop',
	emuLivingAbsent: 'not served by this emulator build (contract C-G pending)',
	emuLivingSlots: (n) => `${n} active slot${n === 1 ? '' : 's'}`,
	emuLivingUnits: (n) => `${n} patrol unit${n === 1 ? '' : 's'}`,
	emuLivingNext: 'next',
	emuCausesOnly: 'Injects causes only — event rows, inputs docs, ANPR reads, patrol units and NATS corridor.traffic.emulated; the decision stack plans, classifies and shadow-evaluates on its own.',

	// ── Common ─────────────────────────────────────────────────────────
	updatedAgo: (s) => `updated ${s}s ago`,
	labelLive: 'live',
	labelEmulated: 'Emulated',
	labelOffline: 'offline',
	labelNotDeployed: 'not deployed',
	labelStale: 'stale',
	gateRefusedNoOfficer: 'refused — no named duty officer on console',
	queueLockedNoOfficer: 'commits locked — no named duty officer',
	canvasLockTitle: 'camera locked to subject',
	canvasUnlock: 'release lock',
	tourTitle: 'Guided tour',
	tourStart: 'Start tour',
	tourStop: 'Stop tour',
	tourSteps: 'tour step',
	// ── wave 3: band honesty, stolen vehicles, escort, provenance ───────
	bandSourceStale: (since) => `Unknown — engine poll failing since ${since}`,
	bandSimulatedTag: 'Simulated feed',
	bandSimulatedHint: 'This band was computed from a simulated (synthetic) traffic feed, not from field sensors.',
	bandScopeEvent: 'selected event · situation log',
	bandScopeCity: 'city band',
	bandScopeAdaptive: 'adaptive status',
	bandScopeNone: 'no band',
	amaTitle: 'Active movement adaptation',
	amaSummary: 'Every active corridor event is classified into a situation band; hysteresis, protocol floors and a twin shadow-check stand between a reading and a published parameter.',
	amaFailClosed: 'fail-closed',
	amaFailClosedHint: 'A candidate plan never takes effect unless the calibrated twin shows it beats the baseline.',
	amaStage_situation: 'Situation',
	amaStage_hysteresis: 'Hysteresis',
	amaStage_protocol_floors: 'Protocol floors',
	amaStage_twin_shadow_eval: 'Twin shadow-check',
	amaStage_audited_persistence: 'Audited record',
	amaStage_city_signal_plans: 'City signal plans',
	amaStageDetail_situation: 'classify each active event into green, amber, red or black',
	amaStageDetail_hysteresis: 'a band change must persist through its dwell window',
	amaStageDetail_protocol_floors: 'advance-closure floors Z+ 180 / Z 120 / Y 60 s on every publish',
	amaStageDetail_twin_shadow_eval: 'a non-baseline plan must beat baseline in a paired twin run, else it falls back',
	amaStageDetail_audited_persistence: 'situation log + parameter overrides, mirrored to the cache',
	amaStageDetail_city_signal_plans: 'the city band drives the gated signal-plan writer',
	brainNovelty: (state) => `novelty check ${state}`,
	brainLatchState_armed: 'on',
	brainLatchState_disabled: 'off',
	brainLatchState_tripped: 'tripped — confirming',
	brainTier_FULL: 'full (both AI tiers)',
	brainTier_TACTICAL_FALLBACK: 'tactical only (decider slow)',
	brainTier_RULES_ONLY: 'rules only (AI tiers down)',
	queueEchallanBadge: 'e-challan',
	queueEvidencePurge: (t) => `evidence purge in ${t}`,
	queueEvidencePurgeHint:
		'Evidence-retention countdown: when it runs out, the sighting and its evidence are purged (30 days by default; an active earmark extends it, capped at 90 days).',
	queueStolenBadge: 'stolen vehicle',
	queueStolenTitle: (fir) => `Stolen vehicle sighted — e-challan withheld (vehicle reported stolen${fir ? `, FIR ${fir}` : ''})`,
	queueStolenNoFine: 'No fine · evidence only',
	queueStolenNoFineHint: 'A reported-stolen vehicle is never fined: its owner is the theft victim. The sighting is evidence for a pursuit an officer authorises.',
	queueStolenSightings: (n) => `${n} sighting${n === 1 ? '' : 's'} on file`,
	queueStolenAuthorised: (by) => `pursuit authorised by ${by}`,
	queueAuthorisePursuit: 'Authorise pursuit',
	queueDismiss: 'Dismiss',
	queueDismissReason: 'reason for dismissing (required)',
	queueStolenAuthoriseNote: 'pursuit authorised on a reported-stolen vehicle (evidence, no fine)',
	queueStolenChip: 'Reported stolen — no fine',
	queueStolenOwnerVictim:
		'This vehicle is reported stolen (FIR): its registered owner is the theft victim, so no e-challan can be approved — only rejected, with a note.',
	queueStolenRejectPlaceholder: 'note: vehicle reported stolen — owner is the victim',
	queueRefusedVerbatim: (status, d) => `refused (${status}): ${d}`,
	filterEmulatedHide: 'hide emulated',
	filterEmulatedShow: 'show emulated',
	filterEmulatedHint: 'Hide or show everything the event emulator produced (living city, use-case runs).',
	filterEmulatedHidden: (n) => `${n} emulated hidden`,
	dispatchHistory: (n) => `history (${n})`,
	dispatchHistoryHide: (n) => `hide history (${n})`,
	dispatchHistoryHint: 'Completed, cancelled and deferred dispatches older than 30 minutes.',
	dispatchNoneLive: 'No open dispatches — older ones are under history.',
	emuEventNotLive: 'corridor event not live yet — activation retried every 5 s',
	emuEventPendingShort: 'event not live yet',
	emuFailReason: (r) => `ended because: ${r}`,
	emuPremiseTitle: 'scenario premise',
	emuPremise_created: (plate, fir) =>
		`stolen-FIR earmark created for ${plate}${fir ? ` · ${fir}` : ''} — its reads are evidence-only sightings, never a fine`,
	emuPremise_already_active: (plate, fir) => `${plate}'s stolen-FIR earmark already active${fir ? ` · ${fir}` : ''} — reused`,
	emuPremise_failed: (plate, reason) =>
		`Not met — no stolen-FIR earmark for ${plate}, so its camera reads were skipped${reason ? ` (${reason})` : ''}`,
	emuPremise_skipped: (plate) => `not checked for ${plate} (this emulator seam cannot read earmarks)`,
	emuLivingPreempted: (n) => `${n} slot${n === 1 ? '' : 's'} paused by a use-case run`,
	emuLivingRefiling: (n) => `${n} ambulance (108) request${n === 1 ? '' : 's'} to re-file`,
	emuLivingNoViolators: 'violators off',
	dossierKind: 'kind',
	dossierProtection: 'protection',
	dossierProtectionNone: 'none (public event)',
	dossierCrowd: 'crowd',
	dossierStatus: 'status',
	dossierSource: 'source',
	dossierRun: 'run',
	dossierMovement: 'movement',
	dossierSpine: 'route',
	dossierCrowd_LOW: 'low',
	dossierCrowd_MODERATE: 'moderate',
	dossierCrowd_HIGH: 'high',
	dossierCrowd_EXTREME: 'extreme',
	dossierStatus_planning: 'planning',
	dossierStatus_approved: 'approved',
	dossierStatus_active: 'active',
	dossierStatus_completed: 'completed',
	dossierStatus_cancelled: 'cancelled',
	dossierStatus_planned: 'planned',
	'dossierSource_live-events-api': 'live (events API)',
	'dossierSource_live-movements-api': 'live (movements feed)',
	'dossierSource_offline-fixture': 'offline preview',
	dossierMode_use_case: 'use-case run',
	dossierMode_living_city: 'living city',
	twinCalibratedYes: 'twin calibrated',
	twinCalibratedNo: 'twin not calibrated (results not trusted for publishing)',
	twinForecastCoupling: (c) => `forecast coupling: ${c}`,
	gateBandUnknown: 'The city band is unknown (its engine poll is failing) — no plan is applied as green by default. Pick the band to apply, explicitly:',
	gateApplyBand: (b) => `apply the ${b} plan under your name`,
	hudEmulatedGps: 'Emulated GPS',
	hudOfficer: 'Officer',
	hudStatus: 'Status',
	hudSimulatedFeed: 'Simulated feed',
	hudSimulatedFeedHint: 'The congestion this escort reads comes from a simulated (synthetic) feed.',
	hudHolding: (roads, by) => `Holding on ${roads} (${by})`,
	hudPeak: (pct) => `peak congestion ${pct}%`,
	hudApprovalsTitle: 'Awaiting the duty officer',
	hudDetour: (roads) => `detour via ${roads} (dashed on the map)`,
	hudApprovalDone: (st) => `answered: ${st}`,
	hudApprovalFailed: (d) => `not answered: ${d}`,
	hudApprove: 'Approve',
	hudReject: 'Reject',
	hudApprovalsNote: 'The escort referred this to a human — it waits for your decision; the AI never approves it.',
	escAiProposes: 'AI proposes',
	escRuleProposes: 'Rule proposes',
	escKind_plan_b: 'Plan B',
	escKind_reroute: 'Re-route',
	escKind_hold: 'Hold',
	escKind_continue: 'Keep monitoring',
	escRouteVia: (kind, via) => `${kind} via ${via}`,
	escKm: (left, now) => `${left} km left (now ${now} km)`,
	escLongDetour: 'long detour',
	escAvoids: (roads, pct) => `avoids ${roads} (congestion ${pct}%)`,
	escHold: (roads, pct, sec) => `hold the convoy short of ${roads} (congestion ${pct}%) until it clears · up to ${sec} s`,
	escHoldDeparture: (roads, pct, sec) => `hold the departure until ${roads} clears (congestion ${pct}%) · up to ${sec} s`,
	escContinue: (roads, pct) => `keep monitoring — no change (congestion ${pct}% on ${roads})`,
	escReplan: (roads) => `re-plan around ${roads} from the convoy's position (route computed on approval)`,
	escClosures: (added, lifted) => `closures: +${added} new · ${lifted} lifted`,
	escDecider: (tier, conf) => `${tier} · confidence ${conf}`,
	escTier_decider: 'strategic tier',
	escTier_tier0_cache_hit: 'tier-0 memory',
	escTier_novelty_latched: 'novelty latch (answer withheld)',
	escTier_rate_limited: 'rate-limited',
	escTier_gemma: 'tactical fallback (Gemma)',
	escTier_unavailable: 'unavailable',
	escTier_deterministic: 'deterministic rule — no model',
	escTier_none: 'no model wired — deterministic rule',
	escExpiresIn: (mmss) => `expires in ${mmss}`,
	escExpiring: 'expiring — current plan holds',
	escApprove: 'Approve',
	escReject: 'Reject',
	escNeedOfficer: 'name the duty officer to decide',
	escOutcomeApproved: (by) => `approved by ${by}`,
	escOutcomeNotApplied: (by) => `approved by ${by} — not applied (the convoy had passed the branch point); a fresh proposal follows`,
	escOutcomeRejected: (by) => `rejected by ${by} — current plan kept`,
	escOutcomeExpired: 'expired — no officer response, current plan held',
	escOutcomeSuperseded: 'superseded by a newer proposal',
	escOutcomeExpiredWhy: (why) => `expired — ${why}`,
	escAuthorityNote: 'Officer approves every switch: the AI only proposes. Unanswered before the timer runs out, the convoy holds its current approved plan.',
	escQueueBadge: 'Escort · AI proposes',
	escQueueBadgeRule: 'Escort · rule proposes',
	escQueueEvent: (name) => `escort · ${name}`,
	escRailTitle: 'AI proposal — your decision',
	hudDiversions: (n) => `${n} diversion${n === 1 ? '' : 's'} active`,
	escortAdopted: 'Following an escort already running for this movement (launched elsewhere).',
	escortRunningStopFirst: 'escort running — stop it first',
	escortCleared: 'Movement cleared',
	escortClear: 'Clear',
	escortClearing: 'Clearing…',
	escortClearHint: 'Post-clearance restoration under your name: lifts the closures and closes the corridor event (completed, or cancelled if it never went live).',
	escortClearOutcome: (to) => `corridor event → ${to}`,
	escortClearFailed: (d) => `clear not completed: ${d}`,
	officerFromSession: 'signed in through the operator gate — this name is what the server audits',
	labelSimulatedFeed: 'Simulated feed',
	opsSigninTitle: 'Operator sign-in required',
	opsSigninBody: 'This deck runs the operator gate: the situation wall opens for a signed-in duty officer. Sign in with your name and the operator PIN.',
	opsSessionLapsed: 'Your operator session has lapsed — panels cannot read the city. Sign in again (top right).',
	cockpitSigninBody: 'This deck runs the operator gate: the VVIP corridor cockpit — its canvas, planner and escort controls — opens for a signed-in duty officer. Sign in with your name and the operator PIN.',
	chatSigninBody: 'This deck runs the operator gate: the assistant opens for a signed-in duty officer. Sign in with your name and the operator PIN.',
	commsSigninBody: 'This deck runs the operator gate: the advisory desk opens for a signed-in duty officer. Sign in with your name and the operator PIN.',
};



const OPS_PACKS: Record<string, Pack> = { en };

// Register into the core (design-shell's sanctioned additive mechanism) so
// primitives that resolve via core t() can read these keys too. registerPack
// never overrides existing keys; importing this module applies the effect.
registerPack('en', en);

/**
 * Trilingual lookup for ops-screens copy: this pack first, then the frozen
 * core pack, then the raw key (the core's documented fallback behaviour).
 */
export function tOps(lang: string, key: string, ...args: unknown[]): string {
	// re-render signal, same contract as core t() (FIX-E-PERF2)
	touchPacks();
	const pack = OPS_PACKS[lang] ?? OPS_PACKS.en;
	const val = pack[key] ?? null;
	if (typeof val === 'function') return String(val(...args));
	if (typeof val === 'string') return val;
	return t(lang as LangCode, key, ...args);
}

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: Pack): void {
	OPS_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): this module's HI and MR strings live ONLY in
 * ./strings.ops.hi.ts and ./strings.ops.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./strings.ops.hi')).hi);
	adopt('mr', (await import('./strings.ops.mr')).mr);
} else {
	await langChunks('strings.ops', (code) =>
		code === 'hi' ? import('./strings.ops.hi').then((c) => adopt('hi', c.hi)) : import('./strings.ops.mr').then((c) => adopt('mr', c.mr)),
	);
}
