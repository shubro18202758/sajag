/**
 * Trilingual string packs (EN / HI / MR) for the corridor showcase.
 *
 * The citizen/driver keys are ported from the legacy advisory layer
 * (frontend/src/i18n/advisoryStrings.js) so the integrated citizen view keeps
 * its copy; this pack EXTENDS them with the eight corridor-event kinds and the
 * ops-board panel vocabulary required by the generalized event model.
 *
 * Public-facing copy only; road names stay transliterated as on city signage.
 */
import { langChunks } from './load';

/**
 * The three UI languages: `label` is the language's own name in its own script (the switch shows it with
 * `lang={code}`), `short` the two-to-three-letter mark a compact switch shows (EN · हि · मरा). Hindi and Marathi
 * are both written in Devanagari (one face, Noto Sans Devanagari).
 */
export const SUPPORTED = [
	{ code: 'en', label: 'English', short: 'EN' },
	{ code: 'hi', label: 'हिंदी', short: 'हि' },
	{ code: 'mr', label: 'मराठी', short: 'मरा' },
] as const;

/** The compact mark of a language code (EN · हि · मरा); an unknown code shows upper-cased. */
export function langShort(code: string): string {
	return SUPPORTED.find((s) => s.code === code)?.short ?? code.toUpperCase();
}

export type LangCode = (typeof SUPPORTED)[number]['code'];

type Pack = Record<string, string | ((...args: unknown[]) => string)>;

const en: Pack = {
	// ── Event kinds (the eight corridor-event archetypes) ─────────────
	kind_protected_movement: 'Protected movement',
	kind_procession: 'Procession (Ganesh visarjan)',
	kind_mass_gathering: 'Mass gathering (Lalbaugcha Raja-class)',
	kind_race: 'Road race (marathon)',
	kind_ceremonial: 'Ceremonial parade',
	kind_egress_surge: 'Stadium egress surge',
	kind_emergency_evacuation: 'Flood evacuation / relief',
	kind_work_zone: 'Infrastructure work zone',
	// Operator-only kinds (watchlist-anpr, migration 010) — labelled in the
	// core so no surface ever renders the raw key; public surfaces never
	// receive these events at all (holds.ts PUBLIC_EVENT_KINDS).
	kind_vehicle_pursuit: 'Vehicle pursuit',
	kind_crime_incident: 'Crime incident',
	// The six OSINT kinds (migration 021): reported situations for RESPONSE.
	kind_reported_crime: 'Reported crime',
	kind_public_disorder: 'Public disorder',
	kind_road_accident: 'Road accident',
	kind_hazard: 'Hazard',
	kind_flooding: 'Flooding',
	kind_infra_failure: 'Infrastructure failure',
	kind_unknown: 'Corridor event',

	// ── Crowd classes ──────────────────────────────────────────────────
	crowd_LOW: 'Low crowd',
	crowd_MODERATE: 'Moderate crowd',
	crowd_HIGH: 'High crowd',
	crowd_EXTREME: 'Extreme crowd',

	// ── Situation bands (operational codes stay in English) ───────────
	band_GREEN: 'Green · normal',
	band_AMBER: 'Amber · watch',
	band_RED: 'Red · intervene',
	band_BLACK: 'Black · take over',

	// ── Ops board ─────────────────────────────────────────────────────
	opsTitle: 'Corridor operations board',
	opsSub: 'Concurrent corridor events, the live decision audit and the adaptive situation band',
	opsSourceLive: 'live',
	opsSourceMovements: 'movements API',
	opsSourceOffline: 'offline preview',
	opsNoEvents: 'No active corridor events',
	opsEventsApiMissing: 'events API not deployed yet — showing the movements fallback and a labelled offline preview',
	opsPhase: 'phase',
	opsWindow: 'window',
	opsRouteSpine: 'route spine',
	opsSelectEvent: 'Select',
	opsSelected: 'selected',
	opsLastUpdated: (ago) => `updated ${ago}s ago`,
	opsStale: 'stale',
	opsNever: 'waiting for first response',

	// ── Audit stream ──────────────────────────────────────────────────
	auditTitle: 'Decision-audit stream',
	auditSub: 'decider → Gemma agent → tool calls, from the brain’s audit channels',
	auditLadder: (rung) => `channel: ${rung}`,
	auditRungWsEvent: 'WebSocket /ws/event',
	auditRungWsConvoy: 'WebSocket /ws/convoy',
	auditRungPoll: '2 s poll',
	auditRungUnavailable: 'unavailable',
	auditProbe: 'Probe the agent',
	auditProbeHint: 'Sends one audit query to /chat/stream and streams the ladder live.',
	auditClear: 'clear',
	auditEmpty: 'No audit entries yet — the stream appends live decisions, band changes and tool calls.',

	// ── Situation band ────────────────────────────────────────────────
	// R9 — the band panel is the Active Movement Adaptation module's face.
	bandTitle: 'Active movement adaptation',
	bandSub: 'situation → hysteresis → policy floors → twin shadow-eval (fail-closed) → audited persistence',
	bandHistory: 'Band history',
	bandSourceLog: 'situation_log',
	bandSourceStatus: 'adaptive status',
	bandAccumulated: 'client-accumulated',
	bandShadowEval: 'shadow eval',
	bandFloorApplied: 'floor applied',
	bandFailClosed: 'fail-closed',

	// ── Twin compare ──────────────────────────────────────────────────
	twinTitle: 'Twin shadow-eval comparison',
	twinSub: 'baseline vs candidate closure policy on the seeded corridor twin',
	twinRun: 'Run comparison',
	twinRunning: 'Running twin…',
	twinBaseline: 'baseline',
	twinCandidate: 'candidate',
	twinAdvance: 'advance (s)',
	twinClosure: 'closure',
	twinDisruption: 'disruption (veh·h)',
	twinQueue: 'max queue (m)',
	twinClosureDur: 'closure duration (s)',
	twinTransit: 'priority transit (s)',
	twinRecovery: 'recovery (s)',
	twinAmbulance: 'ambulance delay (s)',
	twinDelta: 'Δ',
	twinSourceCompare: 'via /simulate/twin/compare',
	twinSourceDirect: 'compare endpoint not deployed — two explicit /simulate/twin arms',
	twinCached: 'cached — refresh on demand',
	twinReplications: (n) => `${n} replications`,

	// ── Emulator ──────────────────────────────────────────────────────
	emuTitle: 'Event emulator',
	emuSub: 'cause-tape injection on loopback :8090',
	emuOnline: 'emulator online',
	emuOffline: 'emulator offline',
	emuCheck: 'check health',
	emuLaunch: 'stage use case',
	emuLaunchNote: 'Launch contract is owned by the emulator stream; failures surface verbatim.',

	// ── Citizen advisory (ported) ─────────────────────────────────────
	brand: 'Corridor alerts · Mumbai',
	tagline: '',
	updated: 'Advisories last checked',
	statusActive: 'Corridor event in progress',
	statusActiveSub: 'Rolling holds of ~2–3 minutes per stretch — not a full freeze.',
	statusClear: 'No active corridor restrictions',
	statusClearSub: 'These advisories cover planned corridor holds only — not general traffic.',
	statusDone: 'Event completed — corridor released',
	statusDoneSub: 'Traffic returning to normal flow.',
	startDemo: 'Play a demo movement',
	freezeTitle: 'Where holds are expected',
	freezeZone: 'Stretch',
	freezeWindow: 'Hold window',
	freezeMinutes: (m) => `~${m} min`,
	alternate: 'Use instead',
	holdNow: 'Holding now',
	passed: 'Cleared',
	why: 'Why so short?',
	whyBody:
		'Closures are timed to the event’s live position (60–180 s ahead) using traffic forecasting — the corridor freezes only while the movement actually passes.',
	subscribeTitle: 'Get alerts on your phone',
	subscribeSub: 'SMS / WhatsApp, free, in your language.',
	phoneLabel: 'Mobile number',
	phonePlaceholder: '10-digit mobile',
	languageLabel: 'Alert language',
	subscribeBtn: 'Subscribe',
	demoBadge: 'Demo preview — no real SMS/WhatsApp is sent',
	previewTitle: 'You would receive:',
	subscribed: 'Subscribed (demo)',
	emergencyTitle: 'Driving an emergency vehicle?',
	emergencyBody: 'Request a green-corridor window on an active corridor event. A named duty officer decides; follow ambulance (108) control until it is approved.',
	emergencyBodyNone: 'No corridor event is active right now, so there is nothing to request. The driver view opens a labelled scripted demo; nothing is sent.',
	citizenTabTitle: 'Corridor alerts',
	emergencyCta: 'Request green corridor',
	backToOps: 'Operator console',
	footerNote:
		'Corridor-event orchestration prototype. Alternate routes are indicative.',
	driverTitle: 'Green corridor — ambulance (108)',
	driverSub: 'Your request goes to the duty officer’s queue. Follow ambulance (108) control until it is approved.',
	driverBack: 'Citizen alerts',
	noMovement: 'No active corridor',
	noMovementSub:
		'No corridor event right now — drive normally. Pick a demo event above to try this flow.',
	atStretch: 'You are at',
	urgency: 'Patient urgency',
	urgCardiac: 'Cardiac',
	urgTrauma: 'Trauma',
	urgStroke: 'Stroke',
	urgOther: 'Other emergency',
	requestBtn: 'Request corridor window',
	evaluating: 'Evaluating corridor gap…',
	proposalTitle: 'Window proposed by the platform',
	convoyReachesIn: 'The event reaches your stretch in',
	crossBefore: 'Cross before',
	officerLabel: 'Duty officer (demo)',
	approveBtn: 'Approve · open window',
	deferBtn: 'Defer',
	windowOpen: 'Window open — cross now',
	windowClosesIn: 'Window closes in',
	holdPosition: 'Hold position — next window at',
	baselineNote:
		'Without a request channel: documented ambulance holds behind convoy corridors run 5–20 minutes.',
	openDriverView: 'Open the ambulance (108) driver view',
	demoNote: 'Demo flow driven by the scripted simulation — no real dispatch, no real patient data.',
};



const PACKS: Record<string, Pack> = { en };

/*
 * Read-only test seam for the production smoke (tests/perf2-prod-smoke.mjs):
 * the string a language's OWN pack holds for a key (no EN fallback), so the
 * smoke can prove, in the shipped build, that every pack module's HI/MR chunk
 * landed. Public UI copy only; it writes nothing.
 */
if (typeof window !== 'undefined') {
	Object.defineProperty(window, '__sajagLangProbe', {
		configurable: true,
		value: (lang: string, key: string): string | null => {
			const v = PACKS[lang]?.[key];
			if (v === undefined) return null;
			try {
				return typeof v === 'function' ? String(v('‹x›', '‹x›', '‹x›')) : String(v);
			} catch {
				return 'ƒ';
			}
		},
	});
}

/**
 * The pack-registry's reactive read (FIX-E-PERF2). Language chunks now arrive
 * asynchronously in the browser, so every derived/template resolving copy
 * through t() must re-run when one lands; the registry (a runes module — this
 * one stays rune-free for the node harness) registers its version reader here
 * on load. The lookup answers from whatever is registered NOW — EN is the
 * fallback while a chunk is in flight, never a raw key.
 */
let versionReader: (() => number) | null = null;

/** Wire the reactive version read (pack-registry.svelte.ts does this once). */
export function setPackVersionReader(read: () => number): void {
	versionReader = read;
}

/** Touch the reactive version inside any resolver (t, tOps, citizenT). */
export function touchPacks(): void {
	if (versionReader) versionReader();
}

export function t(lang: string, key: string, ...args: unknown[]): string {
	touchPacks();
	const pack = PACKS[lang] ?? PACKS.en;
	const val = pack[key] ?? PACKS.en[key];
	if (typeof val === 'function') return String(val(...args));
	return val != null ? String(val) : key;
}

/**
 * Event-kind label with a fallback: the per-language kind name, else the
 * generic 'Corridor event' wording — NEVER the raw `kind_*` key, whatever
 * kind string the API sends (new archetypes degrade to the generic label).
 */
export function kindLabel(lang: string, kind: string | null | undefined): string {
	const key = `kind_${kind ?? ''}`;
	const val = t(lang, key);
	return val === key ? t(lang, 'kind_unknown') : val;
}

/**
 * Native digits — PUBLIC pages only (the citizen and driver pages, the advisory text a citizen receives, the
 * demo alert preview): Devanagari digits (०–९) for HI and MR alike. The operator console never calls these; it keeps
 * Western digits 0–9 in every language (the glossary's digit rule).
 */
const DIGITS: Record<string, string> = {
	en: '0123456789',
	hi: '०१२३४५६७८९',
	mr: '०१२३४५६७८९',
};

/** Western digits → the reader's native digits (public pages). `native: false` keeps 0–9; nothing else changes. */
export function localizeNumber(n: number | string, lang: string, native = true): string {
	const table = native ? (DIGITS[lang] ?? DIGITS.en) : DIGITS.en;
	return String(n).replace(/[0-9]/g, (d) => table[+d]);
}

/** The optional Marathi-digit formatter (public pages only): every Western digit → ०–९, everything else as it is. */
export function marathiDigits(text: number | string): string {
	return localizeNumber(text, 'mr');
}

/**
 * A number for a PUBLIC page: Indian digit grouping (12,34,567), then the reader's digits when `native` (the
 * default) — १२,३४,५६७ in Marathi and Hindi, 12,34,567 in English. Never used on the console.
 */
export function publicNumber(n: number, lang: string, opts: { native?: boolean; maximumFractionDigits?: number } = {}): string {
	const grouped = Number.isFinite(n) ? new Intl.NumberFormat('en-IN', { maximumFractionDigits: opts.maximumFractionDigits ?? 0 }).format(n) : '—';
	return localizeNumber(grouped, lang, opts.native ?? true);
}

/**
 * Additive pack registration (design-shell integration point).
 *
 * The core packs above are FROZEN — existing keys are never overridden.
 * Streams register their own strings per language (en+hi+mr mandatory for
 * every new user-facing string); t() keeps its fallback chain
 * (lang → en → raw key) so a partially-registered language degrades to
 * English rather than key text.
 */
export function registerPack(code: string, pack: Pack): void {
	const existing = PACKS[code] ?? (PACKS[code] = {});
	for (const [key, value] of Object.entries(pack)) {
		if (!(key in existing)) existing[key] = value;
	}
}

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: Pack): void {
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): this module's HI and MR strings live ONLY in
 * ./strings.hi.ts and ./strings.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./strings.hi')).hi);
	adopt('mr', (await import('./strings.mr')).mr);
} else {
	await langChunks('strings', (code) =>
		code === 'hi' ? import('./strings.hi').then((c) => adopt('hi', c.hi)) : import('./strings.mr').then((c) => adopt('mr', c.mr)),
	);
}
