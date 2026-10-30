/**
 * The display layer's vocabulary (SPEC §3.4): machine codes in words, the
 * acronym allowlist, test and scenario markers, actor and tool names.
 *
 * HUMAN is English: it humanises SERVER codes inside server text (titles,
 * feed rows, reasons), which arrives in English. Words a view shows as its
 * own — system actor names, rule names in titles, activity phrases — have
 * pack keys in i18n/packs.workspace.ts (EN/HI/MR), as every chrome string.
 */

/**
 * The acronym allowlist (SPEC §3.4 plus plan X3) — identical to
 * tests/copy-lint.mjs ACRONYMS (tests/workspace.unit.mjs asserts it).
 * An ALL-CAPS word in this set is never sentence-cased.
 */
export const ACRONYMS: ReadonlySet<string> = new Set(
	(
		'FIR ANPR IST VVIP AMA PS CCTV MV BNSS GPS ETA AI ID OSM SVPI CG SG GIDC RTO GJ UTC J ' +
		'OSINT ICCC SACHET IMD NDMA SDMA GDELT CAP AMC COA AHP TOPSIS EVOI DSS KMC KMDA NKDA WB WBSDMA WBTC WBFES CESC ERSS SSKM NRS BMC MMRDA MSDMA MSRDC BEST MTP MH BKC CSMT LTT WEH EEH JVLR SCLR LBS SV NM KEM JJ TT GSB LTMGH SVP VP JSS DN'
	).split(/\s+/),
);

/** Codes the oracle and the emulator send, in words. */
export const HUMAN: Readonly<Record<string, string>> = {
	stolen_vehicle_fir: 'Stolen vehicle (FIR)',
	R_STOLEN_SIGHTING: 'Stolen-vehicle sighting',
	R_SPD_SEGMENT: 'Speeding on segment',
	stolen_vehicle: 'Stolen vehicle',
	flagged: 'Watchlist',
	watch: 'Watch',
	protected_movement: 'Protected movement',
	procession: 'Procession',
	work_zone: 'Work zone',
	vehicle_pursuit: 'Vehicle pursuit',
	crime_incident: 'Crime incident',
	mass_gathering: 'Mass gathering',
	race: 'Road race',
	ceremonial: 'Ceremonial parade',
	egress_surge: 'Egress surge',
	emergency_evacuation: 'Emergency evacuation',
	reported_crime: 'Reported crime',
	public_disorder: 'Public disorder',
	road_accident: 'Road accident',
	hazard: 'Hazard',
	flooding: 'Flooding',
	infra_failure: 'Infrastructure failure',
	public_conflict: 'Public conflict',
	fire: 'Fire',
	urban_flooding: 'Urban flooding',
	public_gathering: 'Public gathering',
	unrest: 'Unrest',
	road_closure: 'Road closure',
	weather_hazard: 'Weather hazard',
	general_news: 'General news',
	full_closure: 'Full closure',
	partial_closure: 'Partial closure',
	speed_jump: 'Speed jump',
	speed_zscore: 'Speed outlier',
	congestion_outlier: 'Congestion outlier',
	road_class_mismatch: 'Road-class mismatch',
	stale_data: 'Stale data',
	phantom_reading: 'Phantom reading',
	emulated_anpr: 'Emulated ANPR',
	anpr: 'ANPR',
	intersection: 'Intersection',
	roundabout: 'Roundabout',
	signal: 'Signal',
	green: 'Green phase',
	red: 'Red phase',
	no_program: 'No signal program',
	ambulance: '108 ambulance',
	jan_rakshak: 'Civic Volunteers',
	police: 'Police',
	traffic: 'Traffic police',
	completed: 'Completed',
	cancelled: 'Cancelled',
	active: 'Active',
	planning: 'Planning',
	approved: 'Approved',
	pending: 'Pending',
	rejected: 'Rejected',
	deferred: 'Deferred',
	requested: 'Requested',
	en_route: 'En route',
	on_scene: 'On scene',
	available: 'Available',
	patrol: 'On patrol',
	osm_assumed: 'OSM, assumed program',
	osm: 'OpenStreetMap',
	program_clock: 'Program clock (not controller telemetry)',
	// a junction's state is the stored program's PLANNED phase (FIX-G-ORACLE / HON-10), never a controller reading
	planned_green: 'Planned green (signal program)',
	planned_lost: 'Planned change interval (signal program)',
	medium: 'Medium',
	high: 'High',
	low: 'Low',
	critical: 'Critical',
	synthetic: 'Synthetic',
	car: 'Car',
	motorcycle: 'Motorcycle',
	truck: 'Truck',
	bus: 'Bus',
	auto_rickshaw: 'Auto-rickshaw',
	primary: 'Primary road',
	secondary: 'Secondary road',
	trunk: 'Trunk road',
	tertiary: 'Tertiary road',
	residential: 'Residential road',
	ama: 'Band change',
	brain: 'AI decision',
	enforcement: 'Enforcement',
	event: 'Event',
	dispatch: 'Dispatch',
	signals: 'Signals',
	osint: 'Open-source report',
	none: 'None',
	road: 'Road',
	junction: 'Junction',
	neighbourhood: 'Neighbourhood',
	landmark: 'Landmark',
	admin: 'Administrative area',
	poi: 'Place of interest',
};

/** A code in words: the vocabulary, else its words in sentence case ('—' for nothing). */
export function human(code: unknown): string {
	if (code == null || code === '') return '—';
	if (typeof code !== 'string') return String(code);
	if (Object.prototype.hasOwnProperty.call(HUMAN, code)) return HUMAN[code];
	const s = code.replace(/_/g, ' ').trim();
	if (!s) return '—';
	// a token with a digit or a mask is an id: never altered
	if (/[0-9•]/.test(s)) return s;
	return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

/** Rehearsal, test and scripted-demo markers (a Test tag; kept out of counts). */
export const TEST_RE =
	/scripted demo|journey check|acceptance test|acceptance tester|showcase|smoke test|gate test|fleet smoke|argus smoke|tier-0|audit mock|wp-\d|cc smoke|automated check/i;

export function isTestText(s: unknown): boolean {
	return typeof s === 'string' && TEST_RE.test(s);
}

/** Test labels at the start of a title, with their separator. */
export const TEST_PREFIX_RE =
	/(?:TIER-0 GATE TEST|ARGUS SMOKE TEST|FLEET SMOKE TEST|JOURNEY CHECK \(automated\)|ACCEPTANCE TEST)\s*(?:·|—)\s*/gi;

/** Scenario suffixes an actor or a text carries (dropped from the display name). */
export const SCENARIO_SUFFIX_RE = /\s*\((?:God's Eye Morning|God’s Eye Morning|demo reset|showcase script|automated)\)\s*$/i;

/**
 * System actor display names: the first rule that matches wins. Each names
 * its EN word and its pack key (`ws_actor_name_<key>`, EN/HI/MR in
 * packs.workspace.ts; tests/workspace.unit.mjs asserts the EN words are the
 * pack's). A person's name never matches a rule and is never translated.
 */
export const ACTOR_RULES: ReadonlyArray<readonly [RegExp, string, string]> = [
	[/^traffic-oracle$|^rules?( engine)?$/i, 'Rules engine', 'rules'],
	[/^convoy-brain( \(system\))?$|^decider|gemma|^sajag ai$/i, 'Sajag AI', 'ai'],
	[/^AMA policy$/i, 'Adaptation policy', 'policy'],
	[/^AMA situation engine$/i, 'Situation engine', 'situation'],
	[/^event-emulator/i, 'Scenario emulator', 'emulator'],
	[/^system:/i, 'System', 'system'],
	[/^108-driver$/i, '108 driver', 'driver108'],
	[/^Sajag data hygiene/i, 'Data hygiene', 'hygiene'],
	[/^osint-ingress/i, 'Open-source ingest', 'osint'],
];

/** Tool names (the assistant's steps) as a step an officer reads. */
export const TOOL_NAMES: Readonly<Record<string, string>> = {
	city_get_dossier: "Read the object's dossier",
	city_feed: 'Read the city feed',
	city_query_entities: 'Queried the city registry',
	city_decision_support: 'Read the decision support',
	list_enforcement_recommendations: 'Listed the decisions waiting',
	get_interception_plan: 'Read the interception plan',
	get_corridor_summary: 'Read the corridor summary',
	get_city_band: 'Read the city band',
	list_active_events: 'Listed the active events',
	plan_corridor: 'Planned a corridor',
};
