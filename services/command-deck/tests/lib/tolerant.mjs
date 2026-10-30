/**
 * The FINAL pins for the S7-owned smokes (UI-S7B, the last UI merge).
 *
 * The redesign (.sajag-orchestration/redesign/SPEC.md, slices S1–S6) rebuilt
 * the markup and the copy these smokes pin. UI-S7A made every pin tolerant
 * (old-or-new); UI-S7B tightens each one to the final copy and selector of
 * the MERGED deck (SPEC §12.4–12.5, the "S7b (final)" column) and drops the
 * old alternative. Where the SPEC's §12.5 "New copy" never landed in product
 * (noted on the entry), the pin takes the merged deck's own final copy —
 * exact, verbatim, equal strength — and the drift is a reported product
 * defect, never silently tolerated.
 *
 *   COPY       copy pins: anchored regexes or exact strings — the final
 *              form. Pins kept VERBATIM (oracle and brain text, data
 *              attributes; WP UI-S7A "Keep these verbatim") are not here:
 *              the smokes keep those as they were.
 *   SEL        selector builders: the final selector only (SPEC §12.4).
 *   in-page    self-contained functions for page.evaluate (they read
 *              `document`; the self-check runs them over tests/lib/minidom.mjs)
 *   page       helpers that drive a puppeteer page (open the Plan rail, the
 *              Audit tab, the Info tab, an inspector tab; leave replay;
 *              select a row)
 *
 * Nothing here writes to a backend: every helper reads the page or clicks a
 * navigation control (a tab, a rail button, a row); none clicks a decision.
 */

import { normText } from './queue.mjs';
import { WORKSPACE } from './routes.mjs';

// ─── copy pins ──────────────────────────────────────────────────────────────

export const COPY = {
	// SPEC §12.5, the S7b (final) column, as tabled
	/** ops-wall:1176, 1448 — the "Simulated" tag (the final label; §12.5 keeps the tolerant word) */
	simulatedFeed: /simulated( feed)?/i,
	/** ops-wall:1176, 1448 — the "Emulated GPS" tag */
	emulatedGps: /emulated gps/i,
	/** ops-wall:1420 — the compact glyph's hidden label reads exactly 'Emulated' (packs.ui ui_prov_emulated) */
	liverailEmulated: /^Emulated$/,
	/** ops-wall:1432 — the escort proposal's tag reads 'Proposed by Sajag AI' (packs.decisions dec_by_ai) */
	aiProposes: /Proposed by Sajag AI/,
	/** ops-wall:1447 — "Holding on Indira Gandhi Sarani (Red Road) (officer …)" (strings.ops hudHolding) */
	holdingRedRoad: /holding on indira gandhi sarani \(red road\)/i,
	/** ops-wall:1472 — the rule proposal's tag, exact (packs.decisions dec_by_rule) */
	ruleTag: 'Proposed by rule',
	/**
	 * ops-wall:1472 — the decider line, exact. §12.5's "New copy" says
	 * 'Deterministic rule, no model', but the merged deck still prints the
	 * sentence-cased pass's 'deterministic rule — no model'
	 * (src/lib/i18n/strings.ops.ts:475 escTier_deterministic, read through
	 * ops.escortDeciderText). Product copy is not this WP's to change: the
	 * pin takes the merged deck's own final copy and the drift is reported.
	 */
	ruleDecider: 'deterministic rule — no model',
	/** ops-wall:1545 — the TEST pill reads exactly 'Test' (corridor/events TEST_TEXT) */
	liverailTest: /^Test$/,
	/** ops-wall:1273 — "Cancel Metro work zone" in the audit row (displayText sentence-cases the verb) */
	cancelWorkZone: /cancel metro work zone/i,
	/** city-command:843 — the held line in the final fmtDuration form ("Held 3 h 50 min · since HH:MM IST", packs.views vw_i_held) */
	heldLine: /^Held 3 h 5\d min · since \d{2}:\d{2} IST$/,
	/** city-command:516, 847–849 — the simulated provenance tag (text or tooltip) */
	simulated: /simulated/i,
	/** citizen:501 — EN badge exactly 'Simulated feed · emulated' (strings.citizen citizen_emulated_badge); HI and MR unchanged (S1's pass is EN-only) */
	emuBadge: { en: 'Simulated feed · emulated', hi: 'सिम्युलेटेड फ़ीड · EMULATED', mr: 'সিমুলেটেড ফিড · এমুলেটেড' },

	// pins outside §12.5 (deck copy that S1B's EN sentence-case pass, S3's map chrome or S5/S6 rebuild)
	/** ops-wall:1039 — emulated server rows carry the EMULATED pill → the provenance column's "Emulated" */
	emulated: /emulated/i,
	/** ops-wall:1071 (a wait) — the probe's tool rows: raw tool name or its displayTool phrase */
	probeTool: /get_active_events|active events/i,
	probeResult: /result/i,
	/** ops-wall:1128 — the server's 'Event activated: …' row through displayText */
	eventActivated: /event activated/i,
	/** ops-wall:1266 — a 409 renders inline with the moves the server allows */
	allowedFromHere: /allowed from here/i,
	/** ops-wall:1173, 1432 — the decider line ("decider · strategic tier · confidence 0.93"; redesign drops "decider ·") */
	deciderConfidence: /(?:decider · )?strategic tier · confidence 0\.93/i,
	/** ops-wall:1173, 1432 — the countdown ("expires in 01:25"; the prototype's tag "Expires in 1:25") */
	expiresIn: /expires in 0?1:\d\d/i,
	/** ops-wall:1183 — the escort lane's receipt */
	approvedBy: /approved by/i,
	/** ops-wall:1200 — a hold proposal says where and for how long */
	holdProposal: /hold the convoy short of Strand Road \(congestion 86%\) until it clears · up to 180 s/i,
	/** ops-wall:1210, 1500 — an unanswered (or late) proposal */
	expiredHeld: 'expired — no officer response, current plan held',
	/** ops-wall:1246 — terminal dispatches folded behind 'history (n)' */
	history2: 'history (2)',
	/** ops-wall:1310 — the emulator's effective sampling */
	emuSampling: /1 decision \/ 50 sim-s/i,
	/** ops-wall:1322 — a run whose corridor event is still 'planning' */
	emuEventPending: 'corridor event not live yet — activation retried every 5 s',
	/** canvas-ux:549 — the LiveRail / Active events focus note */
	noSpine: /no spine|unavailable/i,
	/** canvas-ux:581 — the stale focus flash */
	noRouteGeometry: /no route geometry/i,
	/** city-command:767 — an empty-but-healthy layer's hint */
	noUnitsFielded: 'no units fielded',
	/** city-command:907 — the replay pills say EMULATED */
	replayEmulated: /emulated/i,
	/** city-command:1344, 1362 — the anomaly layer hint and pick card */
	simulatedFeedWords: /simulated feed/i,
	bareFeedName: /source signal-ingress feed\s*$/i,
	/** gods-eye:504–509 — the /ops h2 titles, compared case-insensitively (§12.4) */
	amaTitle: 'Active Movement Adaptation',
	gateTitle: 'City Signal Plans',
	/** gods-eye:545 — the guided tour control (text, tooltip or label) */
	tour: /\btour\b/i,
	/** agent-canvas:214 — the map proposal chip's final copy (packs.map map_proposal_head) */
	agentSuggests: /Proposed on the map/,
	/** citizen:730 — the /driver unit label */
	unitEmulated: /emulated/i,
	/** citizen:1058 — the /comms log's languages */
	logLangs: 'en · hi · mr',
};

/**
 * screens-verify /ops key elements — the FINAL list (§12.4: rewritten against
 * test ids and `data-prim`): the rebuilt section's title and the test ids
 * that prove the section renders. The legacy panel titles are gone.
 */
export const OPS_KEY_ELEMENTS = [
	{ key: 'event board (Corridor Operations Board)', titles: ['Corridor operations'], testids: ['preview-toggle'] },
	{ key: 'pursuit console (Pursuit & Watchlist)', titles: ['Watchlist and retention'], testids: ['pursuit-section', 'retention-health'] },
	{ key: 'enforcement queue (Decision Queue)', titles: ['Decisions'], testids: ['queue-card'] },
	{ key: 'Civic Volunteers dispatch (Civic Volunteers Dispatch)', titles: ['Dispatch'], testids: ['dispatch-request', 'dispatch-tile'] },
	{ key: 'signal panel (City Signal Plans)', titles: ['City signal plans'], testids: ['gate-restore-all'] },
	{ key: 'AMA module card (Active Movement Adaptation)', titles: ['Active movement adaptation'], testids: ['ama-band'] },
	{ key: 'audit stream (Decision-Audit Stream)', titles: ['Audit'], testids: ['audit-feed'] },
];

/**
 * One /ops key element: found when a panel title equals one of `spec.titles`
 * (case- and whitespace-insensitively) or one of `spec.testids` is rendered.
 * `present` maps test id → rendered.
 */
export function opsKeyElementOk(spec, titles, present = {}) {
	const title = titles.find((t) => spec.titles.some((want) => normText(want) === normText(t)));
	if (title) return { ok: true, via: `title '${title}'` };
	const id = spec.testids.find((t) => present[t]);
	return id ? { ok: true, via: `test id ${id}` } : { ok: false, via: null };
}

/** True when `text` contains `needle`, case- and whitespace-insensitively. */
export function textHas(text, needle) {
	return normText(text).includes(normText(needle));
}

/** The C6 mark mask the oracle and the deck print (MH47EM9001 → MH47EM•••1), over free text. */
export function maskMarks(text) {
	return String(text ?? '').replace(/\b([A-Z]{2}[ -]?\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?)(\d{4})\b/g, (_m, head, digits) => `${head}•••${digits.slice(-1)}`);
}

/**
 * A registration mark in free text, raw (MH47EM9001, MH 47 EM 9001,
 * MH-01-AB-1234: the oracle's pattern) or masked — the C6 mask '•••'
 * (MH47EM•••1, and maskPlate's short form •••1 for an odd plate).
 */
export const MARK_IN_TEXT = /\b[A-Z]{2}[ -]?\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?\d{4}\b|•{3}/;

// ─── verdicts (pure; the self-check runs them on synthetic samples) ─────────

/**
 * canvas-ux idle:<route> orbit — the FINAL rule (§12.4):
 *   - '/gods-eye': never orbits while something is selected (an idle orbit
 *     with nothing selected is allowed, never required);
 *   - '/' (a workspace page): never orbits while something is selected or a
 *     dock is open; otherwise an orbit is tolerated, not required;
 *   - '/ops': the wall orbit runs while nothing is selected (orbiting at the
 *     end, heading turned > 5° over the last window); with a selection it
 *     must not orbit.
 * `samples` are the 5 s idle reads {orbiting, selected, docksOpen}; `last` the final read.
 */
export function orbitVerdict({ route, last, turned, samples = [] }) {
	const overSelection = samples.find((s) => s.orbiting && s.selected);
	if (route === '/gods-eye') {
		return overSelection ? { ok: false, detail: 'orbiting while something is selected' } : { ok: true, detail: `${samples.filter((s) => s.orbiting).length}/${samples.length} reads orbiting, never over a selection` };
	}
	if (route === WORKSPACE) {
		const overDock = samples.find((s) => s.orbiting && s.docksOpen);
		if (overSelection) return { ok: false, detail: "orbiting on '/' while something is selected" };
		if (overDock) return { ok: false, detail: "orbiting on '/' while a dock is open" };
		return { ok: true, detail: `no orbit while selected or a dock is open (${samples.filter((s) => s.orbiting).length}/${samples.length} reads orbiting)` };
	}
	if (route === '/ops' && last?.selected) {
		return last.orbiting ? { ok: false, detail: 'orbiting while something is selected' } : { ok: true, detail: 'something is selected: the wall holds still' };
	}
	const runs = last?.orbiting === true && turned > 5;
	return { ok: runs, detail: `orbiting=${last?.orbiting} heading turned ${Number(turned ?? 0).toFixed(1)}° over the last window` };
}

/**
 * canvas-ux exit — the FINAL rule (§12.4): on /gods-eye Esc never navigates,
 * and `.chip.exit` ("Exit map mode") restores the docks on the same route.
 */
export function exitVerdict({ pathAfterEsc, docksBefore = [], docksAfterExit = [], pathAfterExit = null }) {
	const ok = pathAfterEsc === '/gods-eye' && pathAfterExit === '/gods-eye' && docksAfterExit.length > docksBefore.length;
	return { ok, detail: `Esc → ${pathAfterEsc} (never navigates) · EXIT → ${pathAfterExit} with docks [${docksBefore}] → [${docksAfterExit}]` };
}

/**
 * screens-verify /citizen 'event cards render': at least one card — except on
 * a NON-live deck whose public feed lists no event (a sandbox's data), where
 * the honest answer is the empty state over a live or stale feed and no card.
 * The live deck (:5273; LG 21 regenerates the tracked evidence of record
 * there) always needs a card, as before. `listed` is the number of events
 * GET /api/public/events lists (null when unreadable).
 */
export function citizenCardsVerdict({ live, listed, cards, empty, feed, holds }) {
	if (!live && listed === 0) {
		return {
			ok: cards === 0 && !!empty && (feed === 'live' || feed === 'stale'),
			detail: `non-live deck, the public feed lists no event: cards=${cards} · empty state ${!!empty} · feed=${feed}`,
		};
	}
	return { ok: cards > 0, detail: `cards=${cards} hold rows=${holds}${listed === 0 ? ' · the public feed lists no event (the live deck must show one)' : ''}` };
}

/**
 * The merged desk's WITHHELD-column contract (comms/+page.svelte; audit
 * E-ASSIST R2, E-S7B W1), checked on commsDrafts' reading. Used by
 * screens-verify (every listed event withheld) and citizen-smoke (a pursuit,
 * a kind unknown to the board mapper).
 *   Always: exactly three columns, every one `data-withheld="yes"`; the
 *     withholding stated ONCE — exactly one `comms-withheld-badge`, with
 *     text, its `data-withheld-reason` one of operator-kind | osint (and
 *     `reason`, when the caller knows it, that one); no column names its
 *     facts' road or alternate or carries a registration mark (raw or
 *     masked); no ENABLED Copy anywhere in a column.
 *   operator-kind (the arm a pursuit takes): nothing is composed — each
 *     column's draft line is EMPTY, it has NO Copy control at all and its
 *     data-facts is EMPTY (the language name is the column's only text).
 *   osint (a public kind from an open-source report, withheld from citizens
 *     and 108): the columns stay in the DOM unshown, each holding the desk's
 *     withheld NOTICE (non-empty) with a DISABLED Copy; the road and mark
 *     refusals above are what keep a composed draft out of it.
 * `badges` and `cols` are commsDrafts' fields. A mark found is quoted masked.
 */
export function withheldColumnsVerdict({ cols = [], badges = [], reason = null }) {
	const withheld = cols.filter((c) => c.withheld === 'yes').length;
	if (cols.length !== 3 || withheld !== 3) return { ok: false, detail: `${cols.length} draft column(s), ${withheld} withheld — expected three, all withheld` };
	if (badges.length !== 1) return { ok: false, detail: `the withholding must be stated exactly once (one comms-withheld-badge): ${badges.length} found` };
	const why = badges[0].reason;
	if (why !== 'operator-kind' && why !== 'osint') return { ok: false, detail: `withheld badge reason '${why}' — expected operator-kind or osint` };
	if (reason && why !== reason) return { ok: false, detail: `withheld badge reason '${why}' — expected ${reason}` };
	if (!badges[0].text) return { ok: false, detail: 'the withheld badge carries no text' };
	const problems = [];
	const roads = new Set();
	for (const c of cols) {
		const text = String(c.text ?? '');
		const named = [c.facts?.road, ...String(c.facts?.alternate ?? '').split(' / ')].map((r) => String(r ?? '').trim()).filter(Boolean);
		for (const r of named) roads.add(r);
		const road = named.find((r) => textHas(text, r));
		if (road) problems.push(`${c.lang}: names the road '${road}'`);
		const mark = text.match(MARK_IN_TEXT);
		if (mark) problems.push(`${c.lang}: carries a registration mark (${maskMarks(mark[0])})`);
		if (c.copy && !c.copy.disabled) problems.push(`${c.lang}: Copy enabled`);
		if (why === 'operator-kind') {
			if (text !== '') problems.push(`${c.lang}: draft line not empty (${JSON.stringify(maskMarks(text).slice(0, 60))})`);
			if (c.copy) problems.push(`${c.lang}: has a Copy control (the operator-only arm renders none)`);
			if (c.factsRaw !== '' && c.factsRaw !== null && c.factsRaw !== undefined) problems.push(`${c.lang}: data-facts not empty (${String(c.factsRaw).slice(0, 40)})`);
		} else {
			if (!text.trim()) problems.push(`${c.lang}: no withheld notice`);
			if (!c.copy) problems.push(`${c.lang}: no Copy control (the osint arm keeps a disabled one)`);
		}
	}
	if (problems.length) return { ok: false, detail: `withheld drafts (${why}): ${problems.join(' · ')}` };
	return {
		ok: true,
		detail:
			why === 'operator-kind'
				? `withheld (operator-kind) in all three languages — the badge states it once ('${badges[0].text}'); each column empty: no draft text, no Copy, empty data-facts; no mark`
				: `withheld (osint) in all three languages — the badge states it once ('${badges[0].text}'); each column holds the notice only${roads.size ? ` (no road: ${[...roads].join(', ')})` : ''}, Copy disabled, no mark`,
	};
}

/**
 * screens-verify /comms 'same facts in all three (road name verbatim)'.
 *   - A public event's drafts (no column withheld): HEAD's assertion,
 *     unchanged — the Latin-script road names inside the HI and MR drafts
 *     appear verbatim in all three (`sameRoad`, from commsDrafts).
 *     pickPublicCommsEvent puts the desk on a public event whenever its
 *     select lists one.
 *   - Every column withheld: accepted only on a NON-live deck whose desk lists
 *     no public event (`pick.public === false`: every listed event tried, and
 *     each one withheld), and then the columns must hold the merged desk's
 *     withheld contract POSITIVELY (withheldColumnsVerdict: the badge once;
 *     operator-kind columns empty, Copy-less, data-facts empty; no road, no
 *     mark, no enabled Copy in any arm). A live origin, a public event
 *     listed, or the list unread is refused outright. The live deck (:5273; LG 21
 *     regenerates the tracked evidence of record there) keeps HEAD's
 *     assertion: no fallback.
 *   - Anything else (no three columns, columns that disagree, every draft
 *     withheld although a public event was listed or the list could not be
 *     read in full): refused.
 * `cols` are commsDrafts' columns: {lang, withheld, text, facts: {road,
 * alternate, kind} | null, copy: {disabled} | null}. A mark found is quoted
 * masked, never raw.
 */
export function commsFactsVerdict({ live, pick = {}, cols = [], sameRoad = false, facts = [], badges = [] }) {
	const withheld = cols.filter((c) => c.withheld === 'yes').length;
	if (cols.length === 3 && withheld === 0) {
		const picked = pick.tried ? ` · the desk's first event was operator-only: picked the first public one (${pick.tried} switch${pick.tried > 1 ? 'es' : ''})` : '';
		return { ok: !!sameRoad, detail: `facts=[${facts.join(' | ')}]${picked}` };
	}
	if (cols.length !== 3 || withheld !== 3) {
		return { ok: false, detail: `${cols.length} draft column(s), ${withheld} withheld — expected three, either all drafted or all withheld` };
	}
	if (live) {
		return { ok: false, detail: `live deck: every citizen draft is withheld — the road-verbatim check needs a public event (${pick.listed ?? '?'} listed); no withheld fallback on :5273` };
	}
	if (pick.public !== false) {
		return { ok: false, detail: `every citizen draft withheld although ${pick.public ? 'a public event was picked' : 'the desk\'s event list could not be read in full'} (${pick.listed ?? '?'} listed, ${pick.tried ?? 0} tried)` };
	}
	const w = withheldColumnsVerdict({ cols, badges });
	return w.ok ? { ok: true, detail: `non-live deck, none of the ${pick.listed} listed event(s) public: ${w.detail}` } : w;
}

/**
 * True when `origin` is a vite dev server (it serves /@vite/client): the
 * production-only edge contracts (the CSP header, the proxy's WebSocket 501,
 * the dev-only /design nav entry) are not in force there by the deck's own
 * design (hooks.server.ts, shell/nav.ts).
 */
export async function isViteDevServer(origin) {
	try {
		const r = await fetch(`${origin.replace(/\/$/, '')}/@vite/client`, { signal: AbortSignal.timeout(5000) });
		return r.ok && /javascript/.test(r.headers.get('content-type') ?? '');
	} catch {
		return false;
	}
}

// ─── selectors ──────────────────────────────────────────────────────────────

/** Append `suffix` to every alternative of a comma list (`a, b` + ' x' → `a x, b x`). */
export function within(list, suffix) {
	return list
		.split(/,(?![^[(]*[\])])/)
		.map((s) => `${s.trim()} ${suffix}`)
		.join(', ');
}

export const SEL = {
	/** A button by test id: the rebuilt buttons carry it themselves; PlanPanel-style slots keep the span-inside form (both are the merged deck's markup). */
	btn: (id) => `button:has([data-testid="${id}"]), button[data-testid="${id}"]`,
	/** The same inside one scope (a single, comma-free selector). */
	btnIn: (scope, id) => `${scope} button:has([data-testid="${id}"]), ${scope} button[data-testid="${id}"]`,
	/** A LiveRail provenance marker in an Explorer Active-events row (§12.4; ActiveEvents.svelte). */
	railMarker: (eventId, testid) => `[data-testid="active-events"] [data-event-id="${eventId}"] [data-testid="${testid}"]`,
	railMarkers: (testid) => `[data-testid="active-events"] [data-testid="${testid}"]`,
	/** The cockpit's event rows (canvas-ux, city-command): the Explorer's Active events (§12.4). */
	cockpitRows: '[data-testid="active-events"] [data-event-id]',
	cockpitRow: (eventId) => `[data-testid="active-events"] [data-event-id="${eventId}"]`,
	cockpitFocusNotes: '[data-testid="active-events"] .ev-focus',
	/** The navbar band tag's ticking age (§12.4: the AMA chip is retired). */
	bandAge: '[data-testid="band-tag"][data-age-sec]',
	/** The inspector opened on the picked event (§12.4: no pick card). */
	eventPick: '[data-testid="entity-dossier"][data-urn^="event:"]',
	/** A layer row in the LayerTree (§12.4). */
	layer: (id) => `[data-layer="${id}"]`,
	/** The flow layer's simulated tag in the LayerTree and the vitals' `.sim` provenance tag (§12.4: the tree's `.sim` → `chip-simulated`; the vitals tag kept). */
	flowSimulated: '[data-layer="flow"] [data-testid="chip-simulated"]',
	vitalsSimulated: '[data-testid="vitals-feeds"] .sim',
	/** The view header's Share on /ops (SPEC §5.3: the navbar holds none). */
	share: '[data-share]',
	/**
	 * A shell link: the operator shell's navbar, or its More menu
	 * (`[role=menu]`, SPEC §5.3). Never a link in the page body that
	 * `[data-shell=command]` wraps (CommandShell.svelte:45).
	 */
	shellLink: (href) => `[data-shell="command-bar"] a[href="${href}"], [role="menu"] a[href="${href}"]`,
	/** The navbar's More control (SPEC §5.3 navbar; UI-S1B's More popover). */
	moreControl: '[data-shell="command-bar"] [aria-label="More"], [data-shell="command-bar"] [data-menu="more"], [data-shell="command-bar"] [title="More"], [data-shell="command-bar"] [data-tip="More"]',
	/** The AMA floors: any element carrying the class/seconds attributes. */
	amaFloors: '[data-testid="ama-floors"] [data-class]',
	/** Panel titles: the rebuilt Section's h2 (`data-prim` kept). */
	panelTitles: '[data-prim="panel"] h2',
	panels: '[data-prim="panel"]',
	/** Panel ages ('updated Ns ago'): the rebuilt Section's age label. */
	panelAges: '[data-prim=panel] .age, [data-prim=panel] [data-age-sec]',
	/** A dispatch tile's audit tail: the rebuilt table row's `.audit`. */
	dispatchTail: (id) => `[data-testid="dispatch-tile"][data-dispatch-id="${id}"] .audit`,
	/** /comms DRAFT columns: the rebuilt desk's `[data-lang]` (§12.4: the rebuilt desk). */
	commsCols: '[data-testid="comms-trilingual"] [data-lang]',
	commsColsNew: '[data-testid="comms-trilingual"] [data-lang]',
	/**
	 * A column's draft line. BOTH arms of the merged desk: the drafted column's
	 * `<p class="adv-text" data-adv-lang>` and the operator-only arm's
	 * `<p class="adv-text withheld">`, which carries NO data-adv-lang (comms/
	 * +page.svelte) — narrowing this to `[data-adv-lang]` leaves the withheld
	 * column's text unread, so a draft leaked there would pass (audit E-S7B W1).
	 */
	commsText: '.adv-text, [data-adv-lang]',
	/** The desk's ONE statement of a withholding (operator-kind or osint), on the event's meta line. */
	commsWithheldBadge: '[data-testid="comms-withheld-badge"]',
	/** The desk's event pick (SPEC §12.2: kept by S6; citizen-smoke drives it with page.select) and the drafts box. */
	commsSelect: '[data-testid="comms-event-select"]',
	commsBox: '[data-testid="comms-trilingual"]',
	/** A draft column's Copy: the rebuilt desk's Copy control. */
	commsCopy: 'button.copy, button[data-copy], button[data-testid="comms-copy"]',
	/** The workspace frame of the redesign (S2): its presence marks a rebuilt page. */
	frame: '[data-ws="frame"]',
};

/** The inspector opened on the picked event (§12.4). */
export const EVENT_PICK = ['[data-testid="entity-dossier"][data-urn^="event:"]'];

/** commsDrafts' argument: the /comms selectors it reads. */
export const COMMS_DRAFTS = { cols: SEL.commsCols, colsNew: SEL.commsColsNew, text: SEL.commsText, box: SEL.commsBox, select: SEL.commsSelect, copy: SEL.commsCopy, badge: SEL.commsWithheldBadge };

// ─── in-page functions (self-contained; read `document`) ────────────────────

/** In-page: the text of the first selector in `sels` that matches (old before new), or null. */
export function firstPresentText(sels) {
	for (const sel of sels) {
		const el = document.querySelector(sel);
		if (el) return (el.textContent ?? '').replace(/\s+/g, ' ').trim();
	}
	return null;
}

/** In-page: the page is a rebuilt workspace page (SPEC §5.3 WorkspaceFrame, `data-ws="frame"`). */
export function isWorkspacePage() {
	return !!document.querySelector('[data-ws="frame"]');
}

/** In-page: the camera is held — the v2 Follow chip pressed (§12.4: `.chip.lock[aria-pressed=true]`). */
export function cameraLocked() {
	return [...document.querySelectorAll('.ge-hud .chip.lock')].some((c) => c.getAttribute('aria-pressed') === 'true');
}

/** In-page: the title of the chip that holds the camera (cameraLocked's chip), or null. */
export function lockTitle() {
	const chip = [...document.querySelectorAll('.ge-hud .chip.lock')].find((c) => c.getAttribute('aria-pressed') === 'true');
	return chip?.getAttribute('title') ?? null;
}

/** In-page: the open docks of the workspace frame (`[data-dock][data-open=true]`), as ids. */
export function openDocks() {
	return [...document.querySelectorAll('[data-ws="frame"] [data-dock][data-open="true"]')].map((d) => d.getAttribute('data-dock'));
}

/**
 * In-page: the row's state class — today's `.linked` (the rail row marked for
 * the selection); the rebuilt table's `.is-selected` or aria-selected.
 */
export function rowMarked(sel) {
	const el = document.querySelector(sel);
	return !!el && (el.classList.contains('linked') || el.classList.contains('is-selected') || el.getAttribute('aria-selected') === 'true');
}

/** In-page: a layer control is off — today `.off`; an EyeToggle row `aria-pressed=false` / `data-visible=false`. */
export function layerOff(id) {
	const el = document.querySelector(`.chip.layer[data-layer="${id}"], [data-layer="${id}"]`);
	if (!el) return null;
	return el.classList.contains('off') || el.getAttribute('aria-pressed') === 'false' || el.getAttribute('data-visible') === 'false';
}

/**
 * In-page (`page.evaluate(commsDrafts, COMMS_DRAFTS)`): the /comms desk's
 * three DRAFT columns — today's `.lang-col[data-lang]` (an operator-only
 * kind's template-preview columns carry data-template-lang, not data-lang),
 * else the rebuilt desk's `[data-testid=comms-trilingual] [data-lang]`.
 *   langs / filled / facts / sameRoad: screens-verify's reading as at HEAD —
 *     the Latin-script road names inside the HI and MR drafts (signed in,
 *     the desk drafts from the live event, so they are read from those
 *     columns, never hard-coded), and whether each is in all three drafts;
 *   ready: the drafts box answered (`data-ready` not 'no') with three columns;
 *   event: the select's current event id;
 *   cols: per column its language, data-withheld, draft text, the facts'
 *     road / alternate / kind (data-facts; null when it does not parse), the
 *     raw data-facts attribute (`factsRaw`; null when absent) and its Copy
 *     control ({disabled}; null when there is none);
 *   badges: every withheld badge on the page ({reason, text}) — the desk
 *     states a withholding ONCE.
 */
export function commsDrafts(sel) {
	let cols = [...document.querySelectorAll(sel.cols)];
	if (!cols.length) cols = [...document.querySelectorAll(sel.colsNew)];
	const texts = cols.map((c) => c.querySelector(sel.text)?.textContent?.trim() ?? '');
	const latin = (t) => (t.match(/[A-Za-z][A-Za-z0-9.'’()–-]*(?:[ /]+[A-Za-z0-9(][A-Za-z0-9.'’()–-]*)*/g) ?? []).map((x) => x.trim());
	const byLang = (l) => texts[cols.findIndex((c) => c.getAttribute('data-lang') === l)] ?? '';
	const facts = [...new Set([...latin(byLang('hi')), ...latin(byLang('mr'))])];
	const box = document.querySelector(sel.box);
	const select = document.querySelector(sel.select);
	return {
		langs: cols.map((c) => c.getAttribute('data-lang')),
		filled: texts.filter((t) => t.length > 10).length,
		facts,
		sameRoad: facts.length > 0 && ['en', 'hi', 'mr'].every((l) => facts.every((f) => byLang(l).includes(f))),
		ready: !!box && box.getAttribute('data-ready') !== 'no' && cols.length === 3,
		event: select ? (select.value ?? null) : null,
		badges: sel.badge ? [...document.querySelectorAll(sel.badge)].map((b) => ({ reason: b.getAttribute('data-withheld-reason'), text: (b.textContent ?? '').trim() })) : [],
		cols: cols.map((c, i) => {
			let f = null;
			try {
				f = JSON.parse(c.getAttribute('data-facts') || 'null');
			} catch {
				f = null;
			}
			const copy =
				c.querySelector(sel.copy) ??
				[...c.querySelectorAll('button')].find((b) => /^copy\b/i.test(`${b.getAttribute('aria-label') ?? ''} ${b.getAttribute('title') ?? ''} ${b.textContent ?? ''}`.trim()));
			return {
				lang: c.getAttribute('data-lang'),
				withheld: c.getAttribute('data-withheld'),
				text: texts[i],
				facts: f && typeof f === 'object' ? { road: f.road ?? null, alternate: f.alternate ?? null, kind: f.kind ?? null } : null,
				factsRaw: c.getAttribute('data-facts'),
				copy: copy ? { disabled: copy.hasAttribute('disabled') || copy.getAttribute('aria-disabled') === 'true' } : null,
			};
		}),
	};
}

/** In-page: the guided-tour control (text, tooltip or label). */
export function tourControl() {
	return [...document.querySelectorAll('button.chip, .ge-hud button')].some((b) =>
		/\btour\b/i.test(`${b.textContent ?? ''} ${b.getAttribute('title') ?? ''} ${b.getAttribute('aria-label') ?? ''}`),
	);
}

/**
 * In-page: the clear canvas region the panels leave on City Command (client
 * px, with its centre) — the workspace frame ONLY (§12.4; the legacy `.stage`
 * layout is gone): the map pane (`[data-pane=map]`, else `.ge-canvas`) below
 * its toolbar row, minus every open dock (`[data-dock][data-open=true]`), the
 * floating vitals card (`city-vitals`) and the inspector (`entity-dossier`)
 * that overlap it; each is trimmed from the side that keeps the larger region
 * (a dock that holds the pane is not an obstacle). Null when there is no
 * workspace frame (the page is not the redesigned one).
 */
export function clearCanvasRegion() {
	if (!document.querySelector('[data-ws="frame"]')) return null;
	const rect = (el) => {
		const r = el?.getBoundingClientRect();
		return r && r.width > 0 && r.height > 0 ? { left: r.left, top: r.top, right: r.right, bottom: r.bottom } : null;
	};
	const paneEl = document.querySelector('[data-pane="map"]') ?? document.querySelector('.ge-canvas');
	const pane = rect(paneEl);
	if (!pane) return null;
	const holders = new Set();
	for (let n = paneEl; n; n = n.parentElement) holders.add(n);
	let r = { left: pane.left, right: pane.right, top: pane.top + 56, bottom: pane.bottom };
	const area = (k) => (k.right - k.left) * (k.bottom - k.top);
	const covers = [...document.querySelectorAll('[data-ws="frame"] [data-dock][data-open="true"], [data-testid="city-vitals"], [data-testid="entity-dossier"]')]
		.filter((el) => !holders.has(el))
		.map(rect)
		.filter(Boolean);
	for (const o of covers) {
		if (o.right <= r.left || o.left >= r.right || o.bottom <= r.top || o.top >= r.bottom) continue;
		const keep = [
			{ ...r, right: o.left },
			{ ...r, left: o.right },
			{ ...r, bottom: o.top },
			{ ...r, top: o.bottom },
		].filter((k) => k.right > k.left && k.bottom > k.top);
		if (!keep.length) return null;
		r = keep.reduce((a, b) => (area(b) > area(a) ? b : a));
	}
	if (r.right <= r.left || r.bottom <= r.top) return null;
	return { ...r, cx: (r.left + r.right) / 2, cy: (r.top + r.bottom) / 2 };
}


// ─── page helpers (puppeteer; a no-op on today's deck) ──────────────────────

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** The first `[role=tab]` / button inside `root` whose text matches `re` (a handle, or null). */
export async function tabByText(page, root, re) {
	const handles = await page.$$(`${root} [role="tab"], ${root} button`);
	for (const h of handles) {
		const text = await h.evaluate((el) => (el.textContent ?? '').replace(/\s+/g, ' ').trim());
		if (re.test(text)) return h;
	}
	return null;
}

/** Wait (bounded) for `sel`; true when it appeared. */
async function appears(page, sel, timeout) {
	return page
		.waitForSelector(sel, { timeout })
		.then(() => true)
		.catch(() => false);
}

/**
 * A left-dock tab's content: today every panel is mounted; the redesign
 * keeps it behind its rail button (`[data-rail=<id>]`, SPEC §5.3
 * WorkspaceFrame). When `contentSel` is absent and the rail button exists,
 * one click opens it. True when it clicked.
 */
export async function ensureRail(page, rail, contentSel, { timeout = 8000 } = {}) {
	if (await page.$(contentSel)) return false;
	const btn = await page.$(`[data-rail="${rail}"]`);
	if (!btn) return false;
	await btn.click();
	await appears(page, contentSel, timeout);
	return true;
}

/**
 * '/'s planner: behind the left dock's Plan tab (`[data-rail=plan]`, §12.4).
 * True when it opened the tab; throws when the page renders neither the
 * PlanPanel nor its rail button (the tab must exist on the merged deck).
 */
export async function ensurePlanner(page, { timeout = 8000 } = {}) {
	if (await page.$('[data-testid="planner-origin"], [data-testid="planner-label"], [data-testid="planner-officer"]')) return false;
	const btn = await page.$('[data-rail="plan"]');
	if (!btn) throw new Error('ensurePlanner: no [data-rail=plan] button and no PlanPanel on the page');
	await btn.click();
	await appears(page, '[data-testid="planner-label"]', timeout);
	return true;
}

/** The layer controls: the LayerTree behind the Layers rail (`[data-rail=layers]`, §12.4). */
export function ensureLayers(page, { timeout = 8000 } = {}) {
	return ensureRail(page, 'layers', '[data-layer]', { timeout });
}

/**
 * The bottom dock's audit rows (`.f-row`): under the Audit tab
 * (`[data-bottom-tab=audit]`, §12.4) — the tab is opened BEFORE the rows are
 * read. True when it opened the tab; throws when the dock renders no audit
 * tab and no rows (the dock must exist on the merged deck).
 */
export async function ensureAuditRows(page, { timeout = 8000 } = {}) {
	if (await page.$('[data-testid="fusion-rail"] .f-row')) return false;
	const tab = await page.$('[data-bottom-tab="audit"]');
	if (!tab) throw new Error('ensureAuditRows: no [data-bottom-tab=audit] and no .f-row on the page');
	await tab.click();
	await appears(page, '[data-testid="fusion-rail"] .f-row', timeout);
	return true;
}

/**
 * A City vitals section by test id: today on the vitals card; the redesign's
 * map mode keeps the full set in the left dock's Info tab (`[data-rail=info]`,
 * SPEC §6.2). True when it opened the tab.
 */
export function ensureVitals(page, testid, { timeout = 8000 } = {}) {
	return ensureRail(page, 'info', `[data-testid="${testid}"]`, { timeout });
}

/**
 * An inspector tab's content (`contentSel` inside the dossier): today the
 * dossier renders every block at once; the redesign's ObjectInspector has
 * tabs (Properties · Links n · Activity n · Actions, SPEC §5.3). True when
 * it opened the tab named `name`.
 */
export async function ensureInspectorTab(page, name, contentSel, { timeout = 6000 } = {}) {
	const root = '[data-testid="entity-dossier"]';
	if (await page.$(`${root} ${contentSel}`)) return false;
	const tab = await tabByText(page, root, new RegExp(`^${name}\\b`, 'i'));
	if (!tab) return false;
	await tab.click();
	await appears(page, `${root} ${contentSel}`, timeout);
	return true;
}

/**
 * Leave replay for the live picture: the Timeline's Live/Replay control
 * (`replay-toggle`, §12.4). Returns which control it clicked; null when
 * neither a replay is on nor the control renders.
 */
export function leaveReplay(page) {
	return page.evaluate(() => {
		const el = document.querySelector('[data-testid="replay-toggle"]');
		el?.click();
		return el ? 'replay-toggle' : null;
	});
}

/**
 * Select a corridor-operations row: a row click (§12.4 — the redesign has no
 * per-row select button). Returns 'row', or null when the row is absent.
 */
export async function selectEventRow(page, rowSel) {
	const row = await page.$(rowSel);
	if (!row) return null;
	await row.click();
	return 'row';
}

/** The navbar's More control (by label, menu hook, tooltip, or its text), or null. */
async function moreControl(page) {
	return (await page.$(SEL.moreControl)) ?? (await tabByText(page, '[data-shell="command-bar"]', /^more$/i));
}

/**
 * Where the operator shell links `href`: 'shell' (today's nav rail, or the
 * redesign's navbar), 'more-menu' (the navbar's More menu, SPEC §5.3: More
 * holds the public views — one click opens it), or null (neither). The menu
 * is closed again (one more click on More) unless `keepOpen` and the link is
 * there; a page without a More control is never clicked.
 */
export async function findShellLink(page, href, { keepOpen = false, timeout = 3000 } = {}) {
	if (await page.$(SEL.shellLink(href))) return 'shell';
	const more = await moreControl(page);
	if (!more) return null;
	await more.click();
	const link = await page.waitForSelector(SEL.shellLink(href), { timeout }).catch(() => null);
	if (!link || !keepOpen) await more.click().catch(() => undefined);
	return link ? 'more-menu' : null;
}

/**
 * Click a client-side link to `href` from the operator shell: today's nav
 * rail link; the redesign's navbar link, or its More menu's after one click
 * on More (findShellLink). When the shell renders neither, an anchor click —
 * SvelteKit routes it client-side the same way. Returns how it navigated:
 * 'shell-link' | 'more-menu' | 'anchor'.
 */
export async function shellNavigate(page, href) {
	const where = await findShellLink(page, href, { keepOpen: true });
	const link = where ? await page.$(SEL.shellLink(href)) : null;
	if (link) {
		await link.click();
		return where === 'shell' ? 'shell-link' : 'more-menu';
	}
	await page.evaluate((h) => {
		const a = document.createElement('a');
		a.href = h;
		a.textContent = 'smoke nav';
		document.body.appendChild(a);
		a.click();
		a.remove();
	}, href);
	return 'anchor';
}

/**
 * Wait until the canvas camera has settled (the home flight landed): the
 * spots `locate(prefix)` reports stay within 1 px over three reads 500 ms
 * apart (bounded). A click before then lands where the marker WAS.
 */
export async function settleSpots(page, prefix, { timeout = 20000 } = {}) {
	const read = () => page.evaluate((p) => (window.__GODS_EYE__?.locate?.(p) ?? []).map((s) => [s.id, Math.round(s.x), Math.round(s.y)]), prefix);
	const deadline = Date.now() + timeout;
	let prev = await read();
	let still = 0;
	while (Date.now() < deadline && still < 2) {
		await sleep(500);
		const now = await read();
		const same = now.length > 0 && now.length === prev.length && now.every((s, i) => s[0] === prev[i][0] && Math.abs(s[1] - prev[i][1]) <= 1 && Math.abs(s[2] - prev[i][2]) <= 1);
		still = same ? still + 1 : 0;
		prev = now;
	}
	return still >= 2;
}

/**
 * Dismiss a pick that landed on a neighbour, as an operator would, so the
 * next click reaches the canvas (city-command's clickPrefix):
 *   - today's pick card closes on its ✕ (`.ge-pick .pick-x`) → 'pick-x';
 *   - otherwise — today's City Command opens the dossier for any pick with a
 *     URN, the redesign opens the inspector on it (SPEC §12.4: no pick card)
 *     — Esc closes it (SPEC §5.3: "Esc closes, then clears; it never
 *     navigates"; today's /gods-eye clears the selection first, as
 *     agent-canvas-smoke's closeDossier relies on) → 'escape' once the
 *     selection moved or no inspector shows it any more, 'escape-held' when
 *     neither happened within `timeout`.
 * Esc is pressed only for a selection the click made: one set, not the
 * wanted object (`wantUrn`, a URN prefix) and not the selection held before
 * the click (`before`, e.g. a row the smoke selected). Never with nothing
 * selected: today's /gods-eye takes that Esc as EXIT. Returns null when
 * there is nothing to dismiss.
 */
export async function dismissPick(page, { wantUrn = null, before = null, timeout = 3000 } = {}) {
	const closedCard = await page.evaluate(() => {
		const x = document.querySelector('.ge-pick .pick-x');
		x?.click();
		return !!x;
	});
	if (closedCard) return 'pick-x';
	const selected = () => page.evaluate(() => window.__GODS_EYE__?.selection?.urn ?? null);
	const urn = await selected();
	if (!urn || urn === before || (wantUrn && urn.startsWith(wantUrn))) return null;
	await page.keyboard.press('Escape');
	const deadline = Date.now() + timeout;
	while (Date.now() < deadline) {
		const now = await selected();
		const shown = await page.evaluate(
			(u) => [...document.querySelectorAll('[data-testid="entity-dossier"]')].some((el) => el.getAttribute('data-urn') === u && el.getClientRects().length > 0),
			urn,
		);
		if (now !== urn || !shown) return 'escape';
		await sleep(100);
	}
	return 'escape-held';
}

/**
 * /comms (screens-verify): put the desk on a PUBLIC event when its select
 * lists one, so the road-verbatim check reads real drafts. The desk adopts its
 * first event (comms/+page.svelte:74-75); when that one is operator-only —
 * every citizen draft withheld — each other listed event is selected in turn
 * (`page.select`, as citizen-smoke drives it) until one's drafts are not
 * withheld. Only the select's local selection changes: no write, no request
 * beyond the reads the desk makes for its facts. With none public, the desk
 * is put back on its first event. Returns {listed, tried, picked, public}:
 * `public` true once a public event's drafts show, false when every listed
 * event was read and withheld, null when that could not be established (no
 * `<select>`, a draft box that never answered, or more than `max` events).
 */
export async function pickPublicCommsEvent(page, { timeout = 8000, max = 20 } = {}) {
	const settled = async () => {
		const deadline = Date.now() + timeout;
		let s = await page.evaluate(commsDrafts, COMMS_DRAFTS);
		while (!s.ready && Date.now() < deadline) {
			await sleep(150);
			s = await page.evaluate(commsDrafts, COMMS_DRAFTS);
		}
		return s;
	};
	const drafted = (s) => s.ready && s.cols.length === 3 && s.cols.every((c) => c.withheld === 'no');
	const withheld = (s) => s.ready && s.cols.length === 3 && s.cols.every((c) => c.withheld === 'yes');
	const first = await settled();
	const options = await page.evaluate((sel) => {
		const el = document.querySelector(sel);
		return el && el.localName === 'select' ? [...el.querySelectorAll('option')].map((o) => o.value) : null;
	}, SEL.commsSelect);
	if (drafted(first)) return { listed: options?.length ?? null, tried: 0, picked: first.event, public: true };
	if (!options || !withheld(first)) return { listed: options?.length ?? null, tried: 0, picked: null, public: null };
	let tried = 0;
	let unread = false;
	for (const value of options) {
		if (value === first.event) continue;
		if (tried >= max) {
			unread = true;
			break;
		}
		tried++;
		await page.select(SEL.commsSelect, value);
		await sleep(200); // the desk drops the old facts (data-ready → no) before it reads the new ones
		const s = await settled();
		if (drafted(s)) return { listed: options.length, tried, picked: value, public: true };
		if (!withheld(s)) unread = true;
	}
	if (tried && first.event != null) {
		await page.select(SEL.commsSelect, first.event);
		await sleep(200);
		await settled();
	}
	return { listed: options.length, tried, picked: null, public: unread || !options.includes(first.event) ? null : false };
}
