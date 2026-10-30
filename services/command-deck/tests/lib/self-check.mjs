/**
 * `node tests/lib/queue.mjs --self-check` — exercises every tolerant pin of
 * the S7-owned smokes WITHOUT a redesigned deck, a browser or the network.
 *
 * Each copy pin (tests/lib/tolerant.mjs COPY, SPEC §12.5) is run against the
 * OLD copy (today's deck: src/lib/i18n/*.ts, the components) and the NEW copy
 * (SPEC §12.5 "New copy", the prototype's strings), and against a near miss it
 * must refuse. Each old-or-new selector (SEL) and in-page helper is run over a
 * markup snippet of TODAY's Svelte component and one of the redesign
 * (prototype assets/*.js, SPEC §5.3/§6), through tests/lib/minidom.mjs. The
 * page helpers, expandQueueItem and openIfCollapsed run on a fake page whose
 * "app" reacts to clicks (a collapsed item expands a beat later, the Lab
 * section opens), so the click counts are asserted exactly. defaultScreensDir
 * is checked for the live, dev, sandbox and odd origins.
 *
 * Exits 0 with `ok <name> — <detail>` lines, 1 on any FAIL.
 */

import { readFileSync } from 'node:fs';
import { parseHTML } from './minidom.mjs';
import { expandQueueItem, openIfCollapsed, textIs, textMatches, textIsLoose, normText, looseText, queueItemState } from './queue.mjs';
import {
	COPY,
	SEL,
	OPS_KEY_ELEMENTS,
	opsKeyElementOk,
	orbitVerdict,
	exitVerdict,
	textHas,
	within,
	isWorkspacePage,
	cameraLocked,
	openDocks,
	rowMarked,
	layerOff,
	tourControl,
	firstPresentText,
	EVENT_PICK,
	lockTitle,
	maskMarks,
	isViteDevServer,
	settleSpots,
	clearCanvasRegion,
	dismissPick,
	findShellLink,
	citizenCardsVerdict,
	commsDrafts,
	commsFactsVerdict,
	withheldColumnsVerdict,
	pickPublicCommsEvent,
	COMMS_DRAFTS,
	MARK_IN_TEXT,
	ensureRail,
	ensureLayers,
	ensurePlanner,
	ensureAuditRows,
	ensureVitals,
	ensureInspectorTab,
	leaveReplay,
	selectEventRow,
	shellNavigate,
} from './tolerant.mjs';
import { defaultScreensDir, isLiveDeckOrigin, isTrackedScreensDir } from './screens-out.mjs';
import { officerField, nameOfficer, officerValue } from './operator-session.mjs';
import { WORKSPACE } from './routes.mjs';

let failures = 0;
let passes = 0;
function ok(name, cond, detail = '') {
	if (cond) {
		passes++;
		console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	} else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ─── a fake puppeteer page over the minimal DOM ─────────────────────────────

class FakeHandle {
	constructor(page, el) {
		this.page = page;
		this.el = el;
	}
	asElement() {
		return this.el ? this : null;
	}
	evaluate(fn, ...args) {
		return Promise.resolve(this.page.run(() => fn(this.el, ...args)));
	}
	evaluateHandle(fn, ...args) {
		const r = this.page.run(() => fn(this.el, ...args));
		return Promise.resolve(new FakeHandle(this.page, r && r.nodeType === 1 ? r : null));
	}
	async click() {
		if (!this.el) throw new Error('click on a detached handle');
		if (!this.el.getClientRects().length) throw new Error(`Node is either not visible or not an HTMLElement (${describe(this.el)})`);
		this.page.clicks.push(describe(this.el));
		this.page.run(() => this.el.click());
	}
}

function describe(el) {
	const id = el.getAttribute('data-testid') ?? el.getAttribute('data-rail') ?? el.getAttribute('data-bottom-tab') ?? el.className ?? '';
	return `${el.localName}${id ? `[${id}]` : ''}`;
}

class FakePage {
	constructor(html, { window } = {}) {
		this.doc = parseHTML(html);
		this.window = window ?? {};
		this.clicks = [];
		this.typed = [];
		this.keys = [];
		this.keyHandlers = [];
		this.selected = [];
		this.selectHandlers = [];
		// page.keyboard.press(key): logged, then the app's key handlers run (onKey)
		this.keyboard = {
			press: async (key) => {
				this.keys.push(key);
				for (const fn of this.keyHandlers) this.run(() => fn(key, this));
			},
		};
	}
	/** Hook app behaviour on a key press: `fn(key, page)`. */
	onKey(fn) {
		this.keyHandlers.push(fn);
		return this;
	}
	/** Hook app behaviour on page.select: `fn(el, value, page)`. */
	onSelect(fn) {
		this.selectHandlers.push(fn);
		return this;
	}
	/** page.select(sel, value): the <select>'s value (its value attribute here) changes, then the app's select handlers run. */
	async select(sel, ...values) {
		const el = this.doc.querySelector(sel);
		if (!el) throw new Error(`no element for ${sel}`);
		el.value = values[0];
		this.selected.push(values[0]);
		for (const fn of this.selectHandlers) this.run(() => fn(el, values[0], this));
		return values.slice(0, 1);
	}
	run(fn) {
		const prev = [globalThis.document, globalThis.window];
		globalThis.document = this.doc;
		globalThis.window = this.window;
		try {
			return fn();
		} finally {
			if (prev[0] === undefined) delete globalThis.document;
			else globalThis.document = prev[0];
			if (prev[1] === undefined) delete globalThis.window;
			else globalThis.window = prev[1];
		}
	}
	/** Hook app behaviour: `fn(el, page)` runs when an element matching `sel` (or inside it) is clicked. */
	on(sel, fn, { delayMs = 0 } = {}) {
		for (const el of this.doc.querySelectorAll(sel)) {
			el.onclick = () => (delayMs ? setTimeout(() => fn(el, this), delayMs) : fn(el, this));
		}
		return this;
	}
	async $(sel) {
		const el = this.doc.querySelector(sel);
		return el ? new FakeHandle(this, el) : null;
	}
	async $$(sel) {
		return this.doc.querySelectorAll(sel).map((el) => new FakeHandle(this, el));
	}
	async $eval(sel, fn, ...args) {
		const el = this.doc.querySelector(sel);
		if (!el) throw new Error(`no element for ${sel}`);
		return this.run(() => fn(el, ...args));
	}
	async $$eval(sel, fn, ...args) {
		return this.run(() => fn(this.doc.querySelectorAll(sel), ...args));
	}
	async evaluate(fn, ...args) {
		return this.run(() => fn(...args));
	}
	async click(sel) {
		const h = await this.$(sel);
		if (!h) throw new Error(`no element for ${sel}`);
		return h.click();
	}
	async type(sel, text) {
		const el = this.doc.querySelector(sel);
		if (!el) throw new Error(`no element for ${sel}`);
		el.value = `${el.value ?? ''}${text}`;
		this.typed.push([sel, text]);
	}
	async waitForSelector(sel, { timeout = 1000 } = {}) {
		const deadline = Date.now() + timeout;
		while (Date.now() < deadline) {
			const el = this.doc.querySelector(sel);
			if (el) return new FakeHandle(this, el);
			await sleep(5);
		}
		throw new Error(`waiting for selector \`${sel}\` failed: timeout ${timeout}ms exceeded`);
	}
}

/** Insert `html` as the last child of the first element matching `sel`. */
function append(page, sel, html) {
	const host = page.doc.querySelector(sel);
	for (const n of parseHTML(html).childNodes) host.appendChild(n);
}

// ─── 1. text helpers ────────────────────────────────────────────────────────

function textHelpers() {
	ok('textIs: case- and whitespace-insensitive', textIs('  RULE\n PROPOSES ', 'rule proposes') && !textIs('RULE PROPOSES!', 'rule proposes'));
	ok('textIs: any of several alternatives, RegExp alternatives tested on the collapsed text', textIs('Test', 'TEST', /^Pilot$/) && textIs('a  b', /^a b$/) && !textIs('Tested', 'TEST', /^test$/i));
	ok('textIs: null and undefined read as empty text', textIs(null, '') && !textIs(undefined, 'x'));
	const g = /emulated/gi;
	ok('textMatches: a /g regex keeps no state between calls', textMatches('Emulated', g) && textMatches('EMULATED', g) && textMatches('emulated', g));
	ok('textMatches: refuses a non-RegExp', (() => {
		try {
			textMatches('x', 'x');
			return false;
		} catch {
			return true;
		}
	})());
	ok('looseText: drops punctuation and symbols', looseText('Deterministic rule, no model') === 'deterministic rule no model' && looseText('deterministic rule — no model') === 'deterministic rule no model');
	ok('textIsLoose: punctuation-tolerant equality, not a substring test', textIsLoose('Deterministic rule, no model', 'deterministic rule — no model') && !textIsLoose('no model wired — deterministic rule', 'deterministic rule — no model'));
	ok('normText', normText('  Held\t3 h  50 min ') === 'held 3 h 50 min');
	ok('textHas: case-insensitive substring', textHas('Approved by Insp. K. Joshi (smoke)', 'approved by Insp. K. Joshi (smoke)') && !textHas('Approved', 'approved by'));
	ok('within(): a suffix on every alternative of a comma list', within('.a [x="1"], .b', '.c') === '.a [x="1"] .c, .b .c');
}

// ─── 2. copy pins: old copy, new copy, and a near miss ──────────────────────

/** [name, matcher(text) → bool, final samples, near misses] — UI-S7B: the FINAL copy only. */
const reCase = (re) => (s) => textMatches(s, re);
function copyPins() {
	const C = COPY;
	const cases = [
		// SPEC §12.5, the S7b (final) column
		['OW:1176/1448 simulated( feed)?', reCase(C.simulatedFeed), ['Escorting Emulated GPS Simulated', 'Simulated'], ['LIVE FEED · GPS']],
		['OW:1176/1448 emulated gps', reCase(C.emulatedGps), ['Emulated GPS'], ['EMULATED', 'GPS']],
		['OW:1420 liverail-emulated === \'Emulated\'', reCase(C.liverailEmulated), ['Emulated'], ['EMULATED', 'emulated', 'Emulated GPS', 'Simulated', 'EMULATED · TEST']],
		['OW:1432 Proposed by Sajag AI', reCase(C.aiProposes), ['Proposed by Sajag AI · strategic tier · confidence 0.93'], ['AI PROPOSES: Re-route via Eastern Metropolitan Bypass · 4.3 km left (now 3.4 km)', 'RULE PROPOSES', 'Proposed by rule']],
		['OW:1447 holding on Indira Gandhi Sarani (Red Road)', reCase(C.holdingRedRoad), ['Holding on Indira Gandhi Sarani (Red Road) (officer Duty Officer R. Mehta)'], ['Holding on Strand Road (officer …)', 'HOLD on Indira Gandhi Sarani (Red Road)']],
		['OW:1472 proposal tag === \'Proposed by rule\'', (s) => String(s ?? '').trim() === C.ruleTag, ['Proposed by rule'], ['RULE PROPOSES', 'Proposed by rule.', 'AI PROPOSES', 'Proposed by Sajag AI']],
		['OW:1472 decider line === the merged deck\'s escTier_deterministic', (s) => String(s ?? '').trim() === C.ruleDecider, ['deterministic rule — no model'], ['Deterministic rule, no model', 'no model wired — deterministic rule', 'strategic tier']],
		['OW:1545 liverail-test === \'Test\'', reCase(C.liverailTest), ['Test'], ['TEST', 'test', 'Tested', 'REHEARSAL smoke', 'TEST · EMULATED']],
		['OW:1273 cancel Metro work zone', reCase(C.cancelWorkZone), ['Cancel Metro work zone — Strand Road refused (409)'], ['Cancelled Metro work zone', 'CANCEL Strand Road']],
		['CC:843 held line (the fmtDuration form)', reCase(C.heldLine), ['Held 3 h 50 min · since 21:41 IST', 'Held 3 h 52 min · since 09:05 IST'], ['held 3h50m · since 21:41 IST', 'held 3 h 50 min · since 21:41 IST', 'Held 2 h 50 min · since 21:41 IST', 'Held 3 h 50 min · since 9:05 IST']],
		['CC:516/847–849 simulated', reCase(C.simulated), ['SIMULATED FEED', 'SIM SIMULATED FEED', 'Simulated'], ['SIM', 'Emulated']],
		['CZ:501 EN badge === \'Simulated feed · emulated\'', (s) => String(s ?? '').trim() === C.emuBadge.en, ['Simulated feed · emulated'], ['SIMULATED FEED · EMULATED', 'Simulated feed · EMULATED', 'Simulated feed']],
		['CZ:501 HI badge unchanged (verbatim)', (s) => s.includes(C.emuBadge.hi), ['सिम्युलेटेड फ़ीड · EMULATED'], ['सिम्युलेटेड फ़ीड · emulated']],
		['CZ:501 MR badge unchanged (verbatim)', (s) => s.includes(C.emuBadge.mr), ['সিমুলেটেড ফিড · এমুলেটেড'], ['সিমুলেটেড ফিড · emulated']],
		// pins outside §12.5 (the extra-pin audit)
		['OW:1039 EMULATED pill on emulated rows', reCase(C.emulated), ['EM-CAM-02 read the vehicle at 112 km/h Emulated'], ['EM-CAM-02 ANPR hit · STOLEN VEHICLE · MH47EM•••1']],
		['OW:1071 probe tool row (raw or displayTool)', (s) => textMatches(s, C.probeTool) && textMatches(s, C.probeResult), ['Read the active events · Result · 3 events', 'get_active_events · result · 3 events'], ['get_active_events · call']],
		['OW:1128 Event activated', reCase(C.eventActivated), ['Event activated: PURSUIT — stolen MH47EM•••1 (planning → active) by Insp. K. Joshi (smoke)'], ['Event approved: …']],
		['OW:1266 allowed from here', reCase(C.allowedFromHere), ['Refused (409): the event moved on meanwhile. Allowed from here: none'], ['409 · refused']],
		['OW:1173/1432 decider confidence', reCase(C.deciderConfidence), ['Proposed by Sajag AI · strategic tier · confidence 0.93'], ['decider · strategic tier · confidence 0.62', 'tactical fallback (Gemma)']],
		['OW:1173/1432 countdown', reCase(C.expiresIn), ['expires in 01:25', 'Expires in 1:25', 'Expires in 01:25'], ['expires in 02:10', 'expired']],
		['OW:1183 approved by', reCase(C.approvedBy), ['approved by Insp. K. Joshi (smoke)'], ['rejected by Insp. K. Joshi (smoke)']],
		['OW:1200 hold proposal', reCase(C.holdProposal), ['Hold the convoy short of Strand Road (congestion 86%) until it clears · up to 180 s'], ['hold the departure until Strand Road clears (congestion 86%) · up to 180 s']],
		['OW:1210/1500 expired — current plan held', (s) => textHas(s, C.expiredHeld), ['expired — no officer response, current plan held'], ['expired — proposal superseded']],
		['OW:1246 history (2)', (s) => textIs(s, C.history2), ['history (2)'], ['history (3)']],
		['OW:1310 sampling note', reCase(C.emuSampling), ['×10 · 1 decision / 50 sim-s'], ['1 decision / 5 sim-s']],
		['OW:1322 corridor event not live yet', (s) => textIs(s, C.emuEventPending), ['corridor event not live yet — activation retried every 5 s'], ['corridor event live']],
		['CU:549 focus note', reCase(C.noSpine), ['· no spine on canvas', '· unavailable'], ['· LOCKED']],
		['CU:581 focus flash', reCase(C.noRouteGeometry), ['No route geometry for this event'], ['route geometry loaded']],
		['CC:767 empty-but-healthy layer hint', (s) => textIs(s, C.noUnitsFielded), ['no units fielded'], ['no units fielded ⚠', 'units feed down']],
		['CC:907 replay pills EMULATED', reCase(C.replayEmulated), ['◐ REPLAY · run 20 · EMULATED', 'Replay · run 20 · live layers paused Emulated'], ['Replay · run 20 · live layers paused']],
		['CC:1344/1362 SIMULATED FEED (anomaly hint, pick card)', reCase(C.simulatedFeedWords), ['Speed outlier · Simulated feed (synthetic signal-ingress rows)'], ['Speed outlier · signal-ingress feed']],
		// city-command:1432 reads both halves: the Simulated feed words, and never the bare feed name at the end
		['CC:1432 bare feed name (the negative half on its own)', reCase(C.bareFeedName), ['speed outlier on 1013 · source signal-ingress feed', 'Speed outlier · Source signal-ingress feed'], ['Speed outlier · Simulated feed (synthetic signal-ingress rows)', 'source signal-ingress feed (simulated)', 'signal-ingress feed']],
		['CC:1432 anomaly pick card: Simulated feed words, never the bare feed name', (s) => textMatches(s, C.simulatedFeedWords) && !textMatches(s, C.bareFeedName), ['Speed outlier on 1013 · High · Simulated feed (synthetic signal-ingress rows)'], ['speed outlier on 1013 · high · source signal-ingress feed', 'Speed outlier · Simulated feed · source signal-ingress feed', 'Speed outlier · live signal-ingress rows (per the corridor summary)']],
		['GE:545 COPY.tour (the regex tourControl inlines)', reCase(C.tour), ['▶ TOUR', 'Guided tour over the live city', 'Guided tour'], ['Tourism layer', 'Detour advisory', 'TOURS']],
		['AG:214 map proposal chip', reCase(C.agentSuggests), ['Proposed on the map · fly to EM-CAM-03'], ['✦ AI suggests fly to MH47EM•••1', 'Apply Dismiss']],
		['CZ:730 /driver unit EMULATED', reCase(C.unitEmulated), ['108-14 · EMULATED', '108-14 · Emulated'], ['108-14 · live']],
		['CZ:1058 /comms log languages', (s) => textIs(s, C.logLangs), ['en · hi · mr'], ['en · hi']],
	];
	for (const [name, match, finals, misses] of cases) {
		const badFinal = finals.filter((s) => !match(s));
		const loose = misses.filter((s) => match(s));
		ok(`copy ${name}: the final copy accepted, near misses refused`, !badFinal.length && !loose.length, badFinal.length ? `final refused: ${badFinal.join(' | ')}` : loose.length ? `accepted a near miss: ${loose.join(' | ')}` : `${finals.length} final · ${misses.length} refused`);
	}
	// the /ops h2 titles (gods-eye:504–509) through the in-page check, old and new markup
	const h2s = (html) => parseHTML(html).querySelectorAll('h2').map((h) => h.textContent);
	const titled = (html, title) => h2s(html).some((t) => textHas(t, title));
	const oldWall = '<section class="panel" data-prim="panel"><header><h2 class="title">Active Movement Adaptation</h2></header></section><section class="panel" data-prim="panel"><header><h2 class="title">City Signal Plans</h2></header></section>';
	const newWall = '<section class="ops-sec" data-prim="panel"><div class="sec-head"><svg class="ic"></svg><h2>Active movement adaptation</h2></div></section><section class="ops-sec" data-prim="panel"><div class="sec-head"><h2>City signal plans</h2></div></section>';
	const noWall = '<section data-prim="panel"><h2>Adaptation</h2></section>';
	ok('copy GE:504–509 /ops h2 titles case-insensitive (old + new; a different title refused)', titled(oldWall, COPY.amaTitle) && titled(oldWall, COPY.gateTitle) && titled(newWall, COPY.amaTitle) && titled(newWall, COPY.gateTitle) && !titled(noWall, COPY.amaTitle));
	// the guided tour control (gods-eye:545)
	const tourOld = new FakePage('<div class="ge-hud"><div class="hud-row"><button class="chip tour" title="Guided tour over the live city">▶ TOUR</button></div></div>');
	const tourNew = new FakePage('<div class="ge-hud"><div class="toolbar"><button class="chip" aria-label="Guided tour" title="Guided tour"><svg class="ic"></svg></button></div></div>');
	const tourNone = new FakePage('<div class="ge-hud"><button class="chip">Layers</button><button class="chip">Tourism layer</button></div>');
	ok('copy GE:545 the tour control: text, tooltip or label (old + new; none refused)', tourOld.run(tourControl) && tourNew.run(tourControl) && !tourNone.run(tourControl));
	ok('copy GE:545 tourControl inlines COPY.tour (an in-page function cannot import it)', tourControl.toString().includes(COPY.tour.source), COPY.tour.source);
}

// ─── 3. selectors over old and new markup ───────────────────────────────────

/** Today's markup (transcribed from the Svelte components, cited) and the redesign's (prototype, SPEC). */
const OLD = {
	// LiveRail.svelte:101-133 (the cockpit's right rail)
	liveRail: `<div class="rail-right open"><div class="rail"><section class="panel" data-prim="panel"><ul class="events">
		<li><button type="button" class="event" data-event-id="E1"><span class="ev-name" title="Puja immersion — smoke procession (EMULATED)">Puja immersion — smoke procession (EMULATED)</span><span class="ev-kind mono">procession <span class="ev-emu" data-testid="liverail-emulated">EMULATED</span></span><span class="badge">active</span></button></li>
		<li><button type="button" class="event" data-event-id="T1"><span class="ev-name">REHEARSAL smoke · Z protected movement</span><span class="ev-kind mono">protected_movement <span class="ev-test" data-testid="liverail-test" title="Test or rehearsal (kept out of counts): REHEARSAL smoke">TEST</span></span></button></li>
		<li><button type="button" class="event selected" data-event-id="P1"><span class="ev-name">PURSUIT — stolen MH47EM•••1</span><span class="ev-kind mono">vehicle_pursuit <span class="ev-focus tone-ok" title="camera held on PURSUIT — stolen MH47EM•••1">· LOCKED</span></span></button></li>
	</ul></section></div></div>`,
	// GodsEyeCanvas.svelte:2965-3060 (the legacy HUD row) + the pick card (3095-3115)
	hud: `<div class="ge-wrap"><div class="ge-canvas"><canvas></canvas><div class="cesium-viewer-bottom"></div></div><div class="ge-hud"><div class="hud-row">
		<button class="chip exit" title="Leave the cinematic view">⤡ EXIT</button><button class="chip sensor">▙ COMMAND</button><button class="chip share">⇪ SHARE</button><button class="chip tour">▶ TOUR</button>
		<button class="chip lock" title="camera held on PURSUIT — stolen MH47EM•••1 — click to release">⊕ LOCKED · RELEASE</button>
		<button class="chip layer" data-layer="flow" title="flow — 18 OSM-traced · 17 schematic (dashed) · SIMULATED FEED">FLOW <span class="n">35</span><span class="sim" data-testid="chip-simulated" title="SIMULATED FEED">SIM</span></button>
		<button class="chip layer off" data-layer="signals" title="signals">SIGNALS <span class="n">11</span></button>
		<button class="chip layer" data-layer="units" title="no units fielded">UNITS <span class="n">0</span></button>
		<button class="chip layer" data-layer="photoreal-3d" title="photoreal 3D — needs SAJAG_CESIUM_ION_TOKEN">3D <span class="n">0</span></button>
		<span class="chip ama" data-age-sec="12" title="AMA band">AMA AMBER <span class="n">·12s</span><span class="n dim">[city band · SIMULATED FEED]</span></span><span class="chip mode">OSM·DARK</span>
	</div><div class="ge-pick" data-pick-layer="events" role="status"><header><span class="pick-layer">events</span><button class="pick-x" aria-label="dismiss pick card">✕</button></header><p class="pick-text">PURSUIT — stolen MH47EM•••1 (FIR 4401/2026, Hare Street PS) — vehicle pursuit · planned</p><div class="pick-actions"><button class="chip lock" title="fly to this event">⊕ FOCUS</button></div></div></div></div>`,
	// CityVitals.svelte:341-610 (the City Command card)
	vitals: `<div class="vitals-panel"><div class="vitals" data-testid="city-vitals"><section class="v-sec posture-sec" data-testid="vitals-posture"><span class="pill sim" data-testid="vitals-posture-simulated">SIMULATED FEED</span><p class="p-held mono" data-testid="vitals-posture-held" data-held-sec="13800">held 3h50m · since 21:41 IST</p></section><section class="v-sec ethics" data-testid="vitals-ethics"><h3>ETHICS RAILS</h3></section><section class="v-sec" data-testid="vitals-feeds"><h3>FEEDS</h3><dl class="feeds mono"><dt>ingest</dt><dd>42/min · 2s <span class="pill sim">SIMULATED FEED</span></dd></dl></section></div></div>`,
	// CommandShell.svelte:45-86 + CommandBar.svelte:68-118
	shell: `<div class="shell" data-shell="command"><header class="bar" data-shell="command-bar"><span class="brand">SAJAG</span><span class="band-pending mono" data-band="pending">band —</span><input type="search" data-shell="command-search"><div class="lang"><button>EN</button></div><button class="share" type="button">SHARE VIEW</button></header><div class="frame"><nav class="rail"><ul><li><a href="/gods-eye">City Command</a></li><li><a href="/ops">Situation wall</a></li></ul><ul><li><a href="/citizen">Citizen advisory</a></li><li><a href="/driver">108 driver</a></li></ul></nav><main class="main"></main></div></div>`,
	// SignalGateCard.svelte:150-170, EmulatorPanel.svelte:155-280 (the Button primitive wraps a test-id span)
	buttons: `<div><button class="btn"><span data-testid="gate-restore">RESTORE</span></button><button class="btn"><span data-testid="gate-restore-all" data-armed="0">RESTORE ALL</span></button>
		<ul><li data-testid="emu-run" data-run-id="41" data-status="running"><button class="btn"><span data-testid="emu-stop">STOP</span></button></li><li data-testid="emu-run" data-run-id="40" data-status="completed"><button class="btn"><span data-testid="emu-replay">REPLAY</span></button></li></ul></div>`,
	// AMAModuleCard.svelte:158-162
	amaFloors: `<ul class="floors" data-testid="ama-floors"><li data-class="Z+" data-sec="180"><span class="cls mono">Z+</span><span class="sec mono">180s</span></li><li data-class="Z" data-sec="120"><span>Z</span></li><li data-class="Y" data-sec="60"><span>Y</span></li></ul>`,
	// Panel.svelte:130-140
	panels: `<div class="wall"><section class="panel" data-prim="panel"><header><h2 class="title">Corridor Operations Board</h2><span class="age" data-age-sec="4">updated 4s</span></header><article data-testid="event-card"></article></section><section class="panel" data-prim="panel"><header><h2 class="title">Decision Queue</h2></header></section><section class="panel" data-prim="panel"><header><h2 class="title">Pursuit &amp; Watchlist</h2></header></section><section class="panel" data-prim="panel"><header><h2 class="title">Civic Volunteers Dispatch</h2></header></section><section class="panel" data-prim="panel"><header><h2 class="title">City Signal Plans</h2></header></section><section class="panel" data-prim="panel"><header><h2 class="title">Active Movement Adaptation</h2></header></section><section class="panel" data-prim="panel"><header><h2 class="title">Decision-Audit Stream</h2></header></section></div>`,
	// DispatchTiles.svelte (a tile with its audit tail open)
	dispatch: `<div data-testid="dispatch-tile" data-dispatch-id="D2" data-waypoint="3"><button class="audit-toggle">audit</button><ul class="audit"><li>requested · intercept MH05CD•••8 at Howrah Bridge, Kolkata end</li></ul></div>`,
	// comms/+page.svelte:385-405
	comms: `<div data-testid="comms-trilingual" data-ready="yes"><article class="lang-col" data-lang="en" data-facts="{}"><p class="adv-text" data-adv-lang="en">Hold on Vidyasagar Setu</p></article><article class="lang-col" data-lang="hi"><p class="adv-text" data-adv-lang="hi">Vidyasagar Setu पर</p></article><article class="lang-col" data-lang="mr"><p class="adv-text" data-adv-lang="mr">Vidyasagar Setu પર</p></article></div>`,
};

const NEW = {
	// prototype workspace.js:90-95 (Explorer → Active events) + S6A ActiveEvents (a visible Test tag whose title carries the label)
	liveRail: `<ul class="tree" data-testid="active-events">
		<li class="tree-row" data-event-id="E1" data-select="event:E1"><span class="tree-icon"><svg class="ic" aria-hidden="true"></svg></span><span class="tree-label">Puja immersion — smoke procession</span><span class="tree-sec"><span class="tag prov compact" data-tip="Emulated: From the scenario emulator. Not a field reading." data-testid="liverail-emulated"><svg class="ic" aria-hidden="true"></svg><span class="sr">Emulated</span></span><button class="btn minimal small ev-focus icon-only" aria-label="Fly to and follow"><svg class="ic"></svg></button></span></li>
		<li class="tree-row" data-event-id="T1"><span class="tree-label">Z protected movement</span><span class="tree-sec"><span class="tag prov" data-testid="liverail-test" title="Rehearsal or test data: REHEARSAL smoke"><svg class="ic"></svg>Test</span><button class="btn minimal small ev-focus icon-only" aria-label="Fly to and follow"></button></span></li>
		<li class="tree-row is-selected" data-event-id="P1"><span class="tree-label">Pursuit of MH47EM•••1</span><span class="tree-sec"><button class="btn minimal small ev-focus icon-only" title="Following · Pursuit of MH47EM•••1" aria-label="Fly to and follow"></button></span></li>
	</ul>`,
	// SPEC §5.3 Map chrome (toolbar `.chip`s in `.ge-hud`, Follow = .chip.lock with aria-pressed) + LayerTree rows (prototype workspace.js:62-70, 129)
	hud: `<div class="map ge-wrap" data-pane="map"><div class="ge-canvas"><canvas></canvas><div class="cesium-viewer-bottom"></div></div><div class="ge-hud"><div class="toolbar">
		<button class="chip is-pressed" aria-pressed="true" aria-label="Select">S</button><button class="chip" aria-label="Layers">L</button>
		<button class="chip lock is-pressed" aria-pressed="true" aria-label="Follow selection" title="Follow selection">F</button><span class="chip mode">Live</span><button class="chip exit" aria-label="Exit map mode">Exit</button>
	</div></div></div>
	<ul class="tree layer-tree">
		<li class="tree-row" data-layer="flow"><span class="eye"></span><span class="tree-label">Traffic flow</span><span class="tree-sec"><span class="tag prov compact" data-testid="chip-simulated" data-tip="Simulated: Simulated traffic feed: synthetic observations."><svg class="ic"></svg><span class="sr">Simulated</span></span><span class="tag count">35</span></span></li>
		<li class="tree-row dim empty" data-layer="units" aria-pressed="false" title="no units fielded"><span class="eye off"></span><span class="tree-label">Units</span><span class="tree-sec">None now</span></li>
		<li class="tree-row" data-layer="signals" aria-pressed="true"><span class="eye"></span><span class="tree-label">Signals</span></li>
		<li class="tree-row" data-layer="photoreal-3d" title="Photoreal — needs SAJAG_CESIUM_ION_TOKEN"><span class="tree-label">Photoreal</span></li>
	</ul>
	<div class="insp" data-testid="entity-dossier" data-urn="event:P1"><div class="etitle"><div class="ttl">Pursuit of MH47EM•••1</div></div><p>God's Eye Morning: operator-opened pursuit of a FIR-named stolen vehicle</p></div>`,
	// prototype workspace.js:251-253 (the vitals card) + SPEC §6.2 Info tab (posture, ethics)
	vitals: `<div class="vitals" data-testid="city-vitals"><div class="row"><span class="h6">City</span></div><div class="vrow" data-testid="vitals-feeds"><span class="grow muted">Traffic feed</span><span class="tag prov sim" data-tip="Simulated: synthetic observations."><svg class="ic"></svg>Simulated</span></div></div>
		<section data-testid="vitals-posture"><span class="tag prov" data-testid="vitals-posture-simulated"><svg class="ic"></svg>Simulated</span><p data-testid="vitals-posture-held" data-held-sec="13800">Held 3 h 50 min · since 21:41 IST</p></section>`,
	// prototype shell.js:25-40 (navbar; band tag; officer input) + S5B view-header Share (data-share) + the More menu's public links
	shell: `<div class="app" data-shell="command"><header class="navbar" data-shell="command-bar"><a class="btn minimal mod is-pressed" href="/ops" aria-label="Situation"><span class="lbl">Situation</span></a><div class="omni-trigger input-group" data-shell="command-search"><input class="input has-left" readonly></div>
		<span class="ctag success interactive" data-testid="band-tag" data-band="GREEN" data-age-sec="9000"><span>Band</span><span>Green</span></span>
		<div class="input-group officer-input"><input class="input has-left" data-testid="duty-officer" placeholder="Duty officer"></div>
		<div class="menu" role="menu"><a href="/citizen" role="menuitem">Citizen advisory</a><a href="/driver" role="menuitem">108 driver</a></div></header>
		<div class="view-header"><h5>Situation · Kolkata · whole city</h5><button class="btn minimal small" data-share>Share</button></div></div>`,
	// prototype ui-core.js:100-114 btn({attrs:'data-testid=…'}) — the id rides on the button itself
	buttons: `<div><button class="btn" data-testid="gate-restore"><span>Restore</span></button><button class="btn" data-testid="gate-restore-all" data-armed="0"><span>Restore all</span></button>
		<table><tr data-testid="emu-run" data-run-id="41" data-status="running"><td><button class="btn small" data-testid="emu-stop"><span>Stop</span></button></td></tr><tr data-testid="emu-run" data-run-id="40"><td><button class="btn small" data-testid="emu-replay"><span>Replay</span></button></td></tr></table></div>`,
	// a rebuilt AMA section (table rows carrying the same data attributes)
	amaFloors: `<table class="props" data-testid="ama-floors"><tr data-class="Z+" data-sec="180"><td>Z+</td><td>180 s</td></tr><tr data-class="Z" data-sec="120"><td>Z</td></tr><tr data-class="Y" data-sec="60"><td>Y</td></tr></table>`,
	// prototype ops.js:95-214 (sections: <section class="ops-sec" data-prim="panel"><div class="sec-head">…<h2>…</h2>)
	panels: `<div class="wall"><section class="ops-sec fill" data-prim="panel"><div class="sec-head"><svg class="ic"></svg><h2>Decisions</h2><span class="sub" data-age-sec="3">Updated 3 s ago</span></div><table class="dt"><tbody data-testid="queue-card" data-kind="stolen-sighting"></tbody></table></section><section class="ops-sec" data-prim="panel"><div class="sec-head"><h2>Corridor operations</h2><button data-testid="preview-toggle">Board</button></div></section><section class="ops-sec" data-prim="panel"><div class="sec-head"><h2>City signal plans</h2></div><button data-testid="gate-restore-all">Restore all</button></section><section class="ops-sec" data-prim="panel"><div class="sec-head"><h2>Active movement adaptation</h2></div><span data-testid="ama-band" data-band="UNKNOWN"></span></section><section class="ops-sec" data-prim="panel"><div class="sec-head"><h2>Dispatch</h2></div><table><tr data-testid="dispatch-tile"></tr></table></section><section class="ops-sec" data-prim="panel"><div class="sec-head"><h2>Feeds and services</h2></div><table><tr data-testid="retention-health" data-healthy="1"></tr></table></section><section class="ops-audit audit-band"><div class="sec-head"><h2>Audit</h2></div><div class="sec-body" data-testid="audit-feed"></div></section></div>`,
	// a rebuilt dispatch table row
	dispatch: `<table><tr data-testid="dispatch-tile" data-dispatch-id="D2"><td><button class="audit-toggle">Audit</button><div class="audit"><p>Requested · intercept MH05CD•••8 at Howrah Bridge, Kolkata end</p></div></td></tr></table>`,
	// SPEC §6.5 (/comms rebuilt: the drafts side by side, data attributes kept)
	comms: `<div data-testid="comms-trilingual" data-ready="yes"><div class="draft" data-lang="en" data-facts="{}"><div class="draft-text" data-adv-lang="en">Hold on Vidyasagar Setu</div></div><div class="draft" data-lang="hi"><div data-adv-lang="hi">Vidyasagar Setu पर</div></div><div class="draft" data-lang="mr"><div data-adv-lang="mr">Vidyasagar Setu પર</div></div></div>`,
};

function selectors() {
	/** `keys` names the snippet; a final selector is run over the FINAL (redesign) markup only — the legacy one must NOT match. */
	const final = (name, key, sel, check = (els) => els.length > 0, detail = (els) => `${els.length} match(es)`, legacyKey = null) => {
		const doc = parseHTML(NEW[key]);
		const els = doc.querySelectorAll(sel);
		const legacy = legacyKey ? parseHTML(OLD[legacyKey]).querySelectorAll(sel).length : 0;
		ok(`selector ${name} matches the final markup${legacyKey ? ' and refuses the legacy markup' : ''}`, check(els, doc) && (!legacyKey || legacy === 0), `${detail(els, doc)}${legacyKey ? ` · legacy matches ${legacy}` : ''}`);
	};
	const all = (k) => ({ old: OLD[k], new: NEW[k] });

	// ops-wall:1414-1420 — the emulated marker, its hidden label and its row (the FINAL markup: ActiveEvents)
	{
		const doc = parseHTML(NEW.liveRail);
		const m = doc.querySelector(SEL.railMarker('E1', 'liverail-emulated'));
		ok(`selector OW:1414 railMarker(liverail-emulated) + /^Emulated$/ on the final markup (the legacy .rail markup refused)`, !!m && textMatches(m.textContent, COPY.liverailEmulated) && !!m.closest('[data-event-id]') && parseHTML(OLD.liveRail).querySelectorAll(SEL.railMarker('E1', 'liverail-emulated')).length === 0, m ? `'${m.textContent.trim()}' in row ${m.closest('[data-event-id]')?.getAttribute('data-event-id')}` : 'no marker');
		const t = doc.querySelector(SEL.railMarker('T1', 'liverail-test'));
		ok(`selector OW:1536 railMarker(liverail-test) + /^Test$/ + the label in its title`, !!t && textMatches(t.textContent, COPY.liverailTest) && (t.getAttribute('title') ?? '').includes('REHEARSAL smoke') && doc.querySelectorAll(SEL.railMarkers('liverail-test')).length === 1);
		const rows = doc.querySelectorAll(SEL.cockpitRows);
		const row = doc.querySelector(SEL.cockpitRow('P1'));
		const notes = doc.querySelectorAll(SEL.cockpitFocusNotes);
		ok('selector CU:457/CC:1244 cockpit rows, a row by id and its focus note on the final markup (the legacy .rail-right rows refused)', rows.length === 3 && rows.map((r) => r.getAttribute('data-event-id')).join() === 'E1,T1,P1' && !!row && !!row.querySelector('.ev-focus') && notes.length >= 1 && parseHTML(OLD.liveRail).querySelectorAll(SEL.cockpitRows).length === 0, `${rows.length} rows · ${notes.length} focus notes`);
	}
	final('CU:605 band age (the navbar band tag; the AMA chip retired)', 'shell', SEL.bandAge, (els) => els.length === 1 && Number.isFinite(Number(els[0].getAttribute('data-age-sec'))), (els) => `data-age-sec=${els[0]?.getAttribute('data-age-sec')}`, 'hud');
	{
		const doc = parseHTML(NEW.shell);
		const el = doc.querySelector(SEL.bandAge);
		ok('selector CU:605 band age matches the redesigned navbar band tag', !!el && el.getAttribute('data-testid') === 'band-tag' && el.getAttribute('data-age-sec') === '9000');
	}
	final('CU:434 the event pick (the inspector on event:; the legacy pick card refused)', 'hud', SEL.eventPick, (els) => els.length === 1, (els) => els[0]?.className ?? '—', 'hud');
	ok('selector CU:434 the event pick refuses an inspector on another kind', parseHTML('<div data-testid="entity-dossier" data-urn="vehicle:1b94e9d2-7e11-4174-a735-7dd3be3189cf"></div>').querySelectorAll(SEL.eventPick).length === 0);
	final('GE:399 the photoreal layer control (a LayerTree row — the attribute selector the legacy chip also matches)', 'hud', SEL.layer('photoreal-3d'), (els) => els.length === 1 && /needs SAJAG_CESIUM_ION_TOKEN/.test(els[0].getAttribute('title') ?? ''));
	final('CC:513 the flow layer simulated tag + /simulated/i on its text or tooltip', 'hud', SEL.flowSimulated, (els) => els.length === 1 && textMatches(`${els[0].textContent} ${els[0].getAttribute('title') ?? ''}`, COPY.simulated), (els) => `'${els[0]?.textContent.trim()}' title '${els[0]?.getAttribute('title') ?? ''}'`);
	final('CC:514 the vitals .sim tag + /simulated/i (§12.4: the vitals tag kept)', 'vitals', SEL.vitalsSimulated, (els) => els.length >= 1 && textMatches(els[0].textContent, COPY.simulated));
	{
		for (const [gen, html] of [['new', NEW.vitals], ['old', OLD.vitals]]) {
			const doc = parseHTML(html);
			const held = doc.querySelector('[data-testid="vitals-posture-held"]');
			const pill = doc.querySelector('[data-testid="vitals-posture-simulated"]');
			if (gen === 'new') ok('selector CC:832-849 the posture held line and simulated pill on the final markup', !!held && textMatches(held.textContent, COPY.heldLine) && !!pill && textMatches(pill.textContent, COPY.simulated), `${held?.textContent.trim()} · ${pill?.textContent.trim()}`);
			else ok('selector CC:832-849 the legacy held line and pill are REFUSED by the final pins', !textMatches(held?.textContent ?? '', COPY.heldLine), held?.textContent.trim());
		}
	}
	final('CZ:1093 Share (the view header; the legacy navbar share refused)', 'shell', SEL.share, (els) => els.length >= 1, undefined, 'shell');
	ok('selector CZ:1107 Share absent on a page without one', parseHTML('<div data-shell="command"><header data-shell="command-bar"><span data-testid="band-tag" data-band="pending"></span></header></div>').querySelectorAll(SEL.share).length === 0);
	final('CZ:1109 the shell link to /citizen (navbar or More menu; the legacy nav rail refused)', 'shell', SEL.shellLink('/citizen'), (els) => els.length >= 1 && els[0].getAttribute('href') === '/citizen');
	ok('selector CZ:1095 no /design link in the shell', parseHTML(NEW.shell).querySelectorAll(SEL.shellLink('/design')).length === 0);
	{
		// a link in the page body that [data-shell=command] wraps is NOT a shell link; a More menu portalled to the body is
		const body = parseHTML('<div class="shell" data-shell="command"><header class="navbar" data-shell="command-bar"><span data-testid="band-tag" data-band="GREEN"></span></header><main class="main"><p>Public advisory: <a href="/citizen">open the citizen page</a></p></main></div>');
		const portal = parseHTML('<div class="shell" data-shell="command"><header class="navbar" data-shell="command-bar"></header><main></main></div><div class="popover"><ul class="menu" role="menu"><li><a href="/citizen" role="menuitem">Citizen advisory</a></li></ul></div>');
		ok('selector CZ:1138 the shell link refuses a page-body link; accepts the navbar and a [role=menu]', body.querySelectorAll(SEL.shellLink('/citizen')).length === 0 && portal.querySelectorAll(SEL.shellLink('/citizen')).length === 1 && parseHTML(NEW.shell).querySelectorAll(SEL.shellLink('/citizen')).length === 1);
	}
	// btn(): both merged-deck forms — the id on the button, or the PlanPanel-style span inside it
	final('OW:1217 btn(gate-restore-all)', 'buttons', SEL.btn('gate-restore-all'), (els) => els.length === 1 && els[0].localName === 'button');
	ok('selector OW:1217 btn also matches the span-inside form (PlanPanel)', parseHTML(OLD.buttons).querySelectorAll(SEL.btn('gate-restore-all')).length === 1);
	final('OW:1297 btn(gate-restore)', 'buttons', SEL.btn('gate-restore'), (els) => els.length === 1 && els[0].localName === 'button');
	final('OW:1323 btnIn(emu-run 41, emu-stop)', 'buttons', SEL.btnIn('[data-testid="emu-run"][data-run-id="41"]', 'emu-stop'), (els) => els.length === 1 && els[0].localName === 'button');
	final('OW:1327 btnIn(emu-run 40, emu-replay)', 'buttons', SEL.btnIn('[data-testid="emu-run"][data-run-id="40"]', 'emu-replay'), (els) => els.length === 1);
	ok('selector OW:1323 btnIn refuses another run', parseHTML(NEW.buttons).querySelectorAll(SEL.btnIn('[data-testid="emu-run"][data-run-id="43"]', 'emu-stop')).length === 0);
	final('OW:1083 AMA floors (rows with data-class)', 'amaFloors', SEL.amaFloors, (els) => {
		const f = Object.fromEntries(els.map((e) => [e.getAttribute('data-class'), e.getAttribute('data-sec')]));
		return f['Z+'] === '180' && f.Z === '120' && f.Y === '60';
	});
	final('SV:164 panel titles ([data-prim=panel] h2)', 'panels', SEL.panelTitles, (els) => els.length >= 6);
	final('CU:635 panel ages', 'panels', SEL.panelAges, (els) => els.length >= 1 && Number.isFinite(Number(els[0].getAttribute('data-age-sec'))));
	final('OW:1075 the dispatch tile audit tail (the rebuilt .audit; the legacy ul.audit also matches the class)', 'dispatch', SEL.dispatchTail('D2'), (els) => els.length === 1 && els[0].textContent.includes('MH05CD•••8'));
	{
		const doc = parseHTML(NEW.comms);
		const cols = doc.querySelectorAll(SEL.commsCols);
		const texts = cols.map((c) => c.querySelector(SEL.commsText)?.textContent ?? '');
		ok('selector SV:388 /comms columns ([data-lang]) and their drafts on the final markup', cols.map((c) => c.getAttribute('data-lang')).join(',') === 'en,hi,mr' && texts.every((t) => t.length > 5), texts.join(' | '));
	}
	// screens-verify /ops key elements: the rebuilt titles or a section test id — the FINAL wall only
	{
		const doc = parseHTML(NEW.panels);
		const titles = doc.querySelectorAll(SEL.panelTitles).map((h) => h.textContent.trim());
		const present = Object.fromEntries(OPS_KEY_ELEMENTS.flatMap((k) => k.testids).map((id) => [id, !!doc.querySelector(`[data-testid="${id}"]`)]));
		const bad = OPS_KEY_ELEMENTS.filter((k) => !opsKeyElementOk(k, titles, present).ok);
		ok('SV:198-225 every /ops key element found on the final wall (the legacy-title wall refused)', bad.length === 0 && OPS_KEY_ELEMENTS.some((k) => !opsKeyElementOk(k, ['Corridor Operations Board', 'Pursuit & Watchlist'], {}).ok), bad.length ? `missing: ${bad.map((b) => b.key).join(' | ')}` : `${OPS_KEY_ELEMENTS.length} key elements`);
	}
	{
		const k = OPS_KEY_ELEMENTS.find((x) => x.titles.includes('City signal plans'));
		ok('SV:214 a key element is NOT found from an unrelated title', !opsKeyElementOk(k, ['City band'], {}).ok && opsKeyElementOk(k, ['city signal plans'], {}).ok);
	}
}

// ─── 4. in-page helpers ─────────────────────────────────────────────────────

function inPage() {
	ok('in-page isWorkspacePage: a page without the frame no, the frame yes', !new FakePage('<div class="stage"><div class="vitals-panel"></div></div>').run(isWorkspacePage) && new FakePage('<div class="ws" data-ws="frame"><aside data-dock="left" data-open="false"></aside></div>').run(isWorkspacePage));
	ok('in-page cameraLocked: the v2 pressed Follow chip', new FakePage(NEW.hud).run(cameraLocked));
	ok('in-page cameraLocked: a text-only LOCKED chip is NOT a lock (§12.4: aria-pressed only)', !new FakePage(OLD.hud).run(cameraLocked));
	ok('in-page cameraLocked: the pick card FOCUS chip is not a lock', !new FakePage('<div class="ge-hud"><div class="hud-row"><button class="chip sensor">▙ COMMAND</button></div><div class="ge-pick"><div class="pick-actions"><button class="chip lock">⊕ FOCUS</button></div></div></div>').run(cameraLocked));
	ok('in-page cameraLocked: an unpressed v2 Follow chip is not a lock', !new FakePage('<div class="ge-hud"><button class="chip lock" aria-pressed="false" aria-label="Follow selection"></button></div>').run(cameraLocked));
	ok('in-page openDocks', new FakePage('<div data-ws="frame"><aside data-dock="left" data-open="true"></aside><aside data-dock="right" data-open="false"></aside><section data-dock="bottom" data-open="true"></section></div>').run(openDocks).join() === 'left,bottom');
	ok('in-page rowMarked: .is-selected / aria-selected; a bare or .linked-only row refused (§12.4: the redesign marks its own selection)', new FakePage('<tr class="f-row is-selected" data-feed-id="a"></tr>').run(() => rowMarked('[data-feed-id="a"]')) && new FakePage('<tr class="f-row" aria-selected="true" data-feed-id="a"></tr>').run(() => rowMarked('[data-feed-id="a"]')) && !new FakePage('<tr class="f-row" data-feed-id="a"></tr>').run(() => rowMarked('[data-feed-id="a"]')));
	const offNew = new FakePage(NEW.hud).run(() => [layerOff('units'), layerOff('signals')]);
	ok('in-page layerOff: aria-pressed=false (LayerTree); on and absent told apart', offNew[0] === true && offNew[1] === false, JSON.stringify({ offNew }));
	const layerHint = (html, id) => parseHTML(html).querySelector(SEL.layer(id))?.getAttribute('title') ?? '';
	ok('CC:767 the empty-but-healthy units hint on the final markup', textIs(layerHint(NEW.hud, 'units'), COPY.noUnitsFielded));
	ok('CC:775 the flow hint counts, case-insensitively', textHas('Flow — 18 osm-traced · 17 Schematic (dashed)', '18 OSM-traced · 17 schematic (dashed)') && layerHint(NEW.hud, 'photoreal-3d').includes('SAJAG_CESIUM_ION_TOKEN'));
}

// ─── 5. verdicts (canvas-ux idle orbit, Esc / exit) — the FINAL rules ───────

function verdicts() {
	const quiet = (n, o = {}) => Array.from({ length: n }, () => ({ orbiting: false, selected: false, docksOpen: false, ...o }));
	ok('orbit: the workspace never orbits while something is selected or a dock is open', !orbitVerdict({ route: WORKSPACE, last: { orbiting: true }, turned: 30, samples: [{ orbiting: true, selected: true, docksOpen: false }] }).ok && !orbitVerdict({ route: WORKSPACE, last: { orbiting: true }, turned: 30, samples: [{ orbiting: true, selected: false, docksOpen: true }] }).ok);
	ok('orbit: / still (nothing selected, docks closed) passes; an idle orbit there is tolerated', orbitVerdict({ route: WORKSPACE, last: { orbiting: false }, turned: 0, samples: quiet(3) }).ok && orbitVerdict({ route: '/', last: { orbiting: true }, turned: 20, samples: quiet(3, { orbiting: true }) }).ok);
	ok('orbit: /ops orbit required (nothing selected, turned > 5°)', orbitVerdict({ route: '/ops', last: { orbiting: true }, turned: 12, samples: quiet(3) }).ok && !orbitVerdict({ route: '/ops', last: { orbiting: true }, turned: 2, samples: quiet(3) }).ok);
	ok('orbit: /gods-eye never orbits while something is selected; an idle orbit is fine', !orbitVerdict({ route: '/gods-eye', last: { orbiting: true }, turned: 30, samples: [{ orbiting: true, selected: true }] }).ok && orbitVerdict({ route: '/gods-eye', last: { orbiting: true }, turned: 30, samples: quiet(3, { orbiting: true }) }).ok);
	ok('orbit: /ops with something selected must not orbit; with nothing selected it must', !orbitVerdict({ route: '/ops', last: { orbiting: true, selected: true }, turned: 30, samples: [{ orbiting: true, selected: true }] }).ok && orbitVerdict({ route: '/ops', last: { orbiting: false, selected: true }, turned: 0, samples: [{ orbiting: false, selected: true }] }).ok);
	ok('exit: Esc never navigates and .chip.exit restores the docks on the same route', exitVerdict({ pathAfterEsc: '/gods-eye', docksBefore: [], docksAfterExit: ['left'], pathAfterExit: '/gods-eye' }).ok);
	ok('exit: an Esc that navigates, or an exit that restores nothing, fails', !exitVerdict({ pathAfterEsc: '/ops', docksBefore: [], docksAfterExit: ['left'], pathAfterExit: '/gods-eye' }).ok && !exitVerdict({ pathAfterEsc: '/gods-eye', docksBefore: [], docksAfterExit: [], pathAfterExit: '/gods-eye' }).ok);
}

// ─── 6. expandQueueItem ─────────────────────────────────────────────────────

/** Today's always-open cards (DecisionQueue.svelte:439-470 + DecisionCard.svelte:75-120). */
const OLD_QUEUE = `<div class="queue">
	<div class="card-wrap" data-testid="queue-card" data-kind="echallan" data-id="R3" data-stolen="" data-refused=""><article class="card k-echallan" data-prim="decision-card" data-kind="echallan"><header class="head"><span class="badge">E-CHALLAN</span><h3 class="title">MH01KL•••7 · read at 78 km/h</h3></header><div class="body"></div><footer class="foot"><span class="actions"><button class="btn commit">APPROVE</button><button class="btn reject">REJECT</button></span></footer></article></div>
	<div class="card-wrap" data-testid="queue-card" data-kind="stolen-sighting" data-id="V8" data-count="2" data-rec-ids="R6 R7"><article class="card" data-prim="decision-card"><p data-testid="stolen-note">e-challan withheld (vehicle reported stolen, FIR 120/2026)</p><footer><button class="btn">AUTHORISE PURSUIT</button><button class="btn">DISMISS</button></footer></article></div>
</div>`;

/** The redesign (prototype ops.js:66-75; SPEC §6.3: the item keeps a hidden body; UI-S5A: ProposalCard data-testid=proposal-card). */
const NEW_QUEUE = `<table class="dt">
	<tbody data-testid="queue-card" data-kind="echallan" data-id="R3" data-stolen="" data-refused=""><tr data-row-toggle aria-expanded="false" data-action="qopen"><td class="two"><div class="l1">E-challan · MH01KL•••7</div></td></tr><tr class="detail" hidden><td><div class="pcard" data-testid="proposal-card" data-prim="decision-card" data-kind="echallan" data-id="R3"><div class="pc-foot ap-actions"><button class="btn">Reject</button><button class="btn primary">Approve</button></div></div></td></tr></tbody>
	<tbody data-testid="queue-card" data-kind="echallan" data-id="R4"><tr data-action="qopen"><td><div class="l1">E-challan · MH01RS•••5</div></td></tr><tr class="detail" hidden><td><div data-testid="proposal-card" data-prim="decision-card"><button class="btn">Reject</button><button class="btn primary">Approve</button></div></td></tr></tbody>
	<tbody data-testid="queue-card" data-kind="stolen-sighting" data-id="V8" data-count="2" data-rec-ids="R6 R7"><tr data-row-toggle aria-expanded="false"><td>Authorise pursuit of MH01PQ•••0 · 2 sightings</td></tr><tr class="detail" hidden><td><div data-testid="proposal-card" data-prim="decision-card"><p data-testid="stolen-note">Evidence only: e-challan withheld (vehicle reported stolen, FIR 120/2026). One approval opens one pursuit.</p><div class="ap-actions"><button class="btn">Dismiss</button><button class="btn primary">Authorise pursuit</button></div><div data-testid="queue-card" data-kind="pursuit" data-id="V8" data-refusal="no-approved-recommendation"><button class="btn" disabled>Open pursuit</button></div></div></td></tr></tbody>
	<tbody data-testid="queue-card" data-kind="corridor-request" data-id="D1"><tr data-row-toggle aria-expanded="true"><td>108 Ambulance 108-14 → J5</td></tr><tr class="detail"><td><div data-testid="proposal-card" data-prim="decision-card"><button class="btn">Defer</button><button class="btn primary">Approve</button></div></td></tr></tbody>
</table>`;

/** The fake app: a row toggle expands its item a beat later (one open at a time). */
function queueApp(page) {
	return page.on(
		'[data-row-toggle], [data-action="qopen"]',
		(el) => {
			const item = el.closest('[data-testid="queue-card"]');
			for (const other of page.doc.querySelectorAll('tbody[data-testid="queue-card"]')) {
				if (other === item) continue;
				other.querySelector(':scope > tr[data-row-toggle]')?.setAttribute('aria-expanded', 'false');
				other.querySelector(':scope > tr.detail')?.setAttribute('hidden', '');
			}
			if (el.hasAttribute('aria-expanded')) el.setAttribute('aria-expanded', 'true');
			item.querySelector('tr.detail')?.removeAttribute('hidden');
		},
		{ delayMs: 30 },
	);
}

const buttonsShown = (page, sel) => page.run(() => [...document.querySelectorAll(`${sel} button`)].filter((b) => b.getClientRects().length > 0).map((b) => b.textContent.trim()));

async function queueChecks() {
	{
		const page = new FakePage(OLD_QUEUE);
		const st = page.run(() => queueItemState(document.querySelector('[data-testid="queue-card"][data-id="R3"]')));
		await expandQueueItem(page, '[data-testid="queue-card"][data-id="R3"]');
		await expandQueueItem(page, '[data-testid="queue-card"][data-kind="stolen-sighting"][data-id="V8"]');
		ok('expandQueueItem: a no-op on today\'s always-open cards (no click)', !st.collapsed && page.clicks.length === 0 && buttonsShown(page, '[data-testid="queue-card"][data-id="R3"]').join() === 'APPROVE,REJECT', `state ${st.reason} · ${page.clicks.length} clicks`);
	}
	{
		const page = queueApp(new FakePage(NEW_QUEUE));
		const sel = '[data-testid="queue-card"][data-id="R3"]';
		const before = buttonsShown(page, sel);
		await expandQueueItem(page, sel);
		const after = buttonsShown(page, sel);
		ok('expandQueueItem: a collapsed item (row toggle aria-expanded=false, hidden body) → ONE click on its row toggle, then its buttons show', before.length === 0 && page.clicks.length === 1 && /tr/.test(page.clicks[0]) && after.join() === 'Reject,Approve', `${page.clicks.join(' ')} · before [${before}] after [${after}]`);
		await expandQueueItem(page, sel);
		ok('expandQueueItem: …and a second call on the open item is a no-op', page.clicks.length === 1);
	}
	{
		const page = queueApp(new FakePage(NEW_QUEUE));
		await expandQueueItem(page, '[data-testid="queue-card"][data-id="R4"]');
		ok('expandQueueItem: a hidden body without aria-expanded → one click on the summary row', page.clicks.length === 1 && buttonsShown(page, '[data-testid="queue-card"][data-id="R4"]').length === 2, page.clicks.join(' '));
	}
	{
		const page = queueApp(new FakePage(NEW_QUEUE));
		await expandQueueItem(page, '[data-testid="queue-card"][data-id="D1"]');
		ok('expandQueueItem: an expanded item is a no-op', page.clicks.length === 0);
	}
	{
		const page = queueApp(new FakePage(NEW_QUEUE));
		const nested = '[data-testid="queue-card"][data-kind="pursuit"][data-id="V8"]';
		const st = page.run(() => queueItemState(document.querySelector(nested)));
		await expandQueueItem(page, nested);
		ok('expandQueueItem: an item nested in a collapsed item expands the outer one (one click), its button then shows', st.collapsed && st.depth === 1 && page.clicks.length === 1 && buttonsShown(page, nested).join() === 'Open pursuit', `depth ${st.depth} · ${page.clicks.join(' ')}`);
	}
	{
		const page = queueApp(new FakePage(NEW_QUEUE));
		await expandQueueItem(page, '[data-testid="queue-card"][data-id="R3"]');
		await expandQueueItem(page, '[data-testid="queue-card"][data-kind="stolen-sighting"][data-id="V8"]');
		const r3 = page.run(() => queueItemState(document.querySelector('[data-testid="queue-card"][data-id="R3"]')));
		await expandQueueItem(page, '[data-testid="queue-card"][data-id="R3"]');
		ok('expandQueueItem: one open at a time — re-expanding an item another opening collapsed clicks it again', r3.collapsed && page.clicks.length === 3 && buttonsShown(page, '[data-testid="queue-card"][data-id="R3"]').length === 2, page.clicks.join(' '));
	}
	{
		const page = queueApp(new FakePage(NEW_QUEUE));
		await expandQueueItem(page, '[data-testid="queue-card"][data-id="nope"]');
		ok('expandQueueItem: an absent item is a no-op (the caller reports the missing button)', page.clicks.length === 0);
	}
	{
		const page = new FakePage('<table><tbody data-testid="queue-card" data-id="X"><tr data-row-toggle aria-expanded="false"><td>row</td></tr><tr hidden><td><div data-prim="decision-card"><button>Approve</button></div></td></tr></tbody></table>');
		let threw = null;
		try {
			await expandQueueItem(page, '[data-testid="queue-card"][data-id="X"]', { timeout: 150 });
		} catch (err) {
			threw = String(err.message ?? err);
		}
		ok('expandQueueItem: a toggle that never opens the item throws (bounded wait), after one click', !!threw && /did not expand within 150 ms/.test(threw) && page.clicks.length === 1, threw ?? 'no error');
	}
}

// ─── 7. openIfCollapsed (plan X23) ──────────────────────────────────────────

async function labChecks() {
	const TOGGLE = '[data-testid=lab-toggle]';
	const SECTION = '[data-testid=lab-section]';
	{
		// today's /ops: no Lab section (EmulatorPanel.svelte mounted in the right column)
		const page = new FakePage('<div class="col col-right"><section class="panel" data-prim="panel"><select data-testid="emu-use-case"></select></section></div>');
		const clicked = await openIfCollapsed(page, TOGGLE, SECTION);
		ok('openIfCollapsed: no toggle (today\'s deck) → false, no click', clicked === false && page.clicks.length === 0);
	}
	{
		const page = new FakePage('<section class="ops-sec" data-testid="lab-section" data-open="true"><button class="section-head" data-testid="lab-toggle" aria-expanded="true">Lab and system</button><select data-testid="emu-use-case"></select></section>');
		const clicked = await openIfCollapsed(page, TOGGLE, SECTION);
		ok('openIfCollapsed: an open section → false, no click', clicked === false && page.clicks.length === 0);
	}
	{
		// prototype ops.js:214 + X23: collapsed by default; the emulator mounts when it opens
		const page = new FakePage('<section class="ops-sec" data-testid="lab-section" data-open="false"><button class="section-head interactive" data-testid="lab-toggle" aria-expanded="false">Lab and system</button></section>');
		page.on(
			TOGGLE,
			(el, p) => {
				el.setAttribute('aria-expanded', 'true');
				const sec = p.doc.querySelector(SECTION);
				sec.setAttribute('data-open', 'true');
				append(p, SECTION, '<div class="lab-body"><select data-testid="emu-use-case"><option value="metro_work_zone"></option></select><button data-testid="emu-launch-btn">Launch</button></div>');
			},
			{ delayMs: 40 },
		);
		const before = !!(await page.$('[data-testid="emu-use-case"]'));
		const clicked = await openIfCollapsed(page, TOGGLE, SECTION);
		const after = !!(await page.$('[data-testid="emu-use-case"]'));
		ok('openIfCollapsed: a collapsed section → true, exactly ONE click, then open (its emulator mounted)', clicked === true && page.clicks.length === 1 && !before && after && (await page.$(`${SECTION}[data-open="true"]`)) !== null, `${page.clicks.join(' ')} · emulator before ${before} after ${after}`);
		const again = await openIfCollapsed(page, TOGGLE, SECTION);
		ok('openIfCollapsed: …and calling it again is a no-op', again === false && page.clicks.length === 1);
	}
	{
		const page = new FakePage('<section data-testid="lab-section" data-open="false"><button data-testid="lab-toggle" aria-expanded="false">Lab</button></section>');
		let threw = false;
		try {
			await openIfCollapsed(page, TOGGLE, SECTION, { timeout: 100 });
		} catch {
			threw = true;
		}
		ok('openIfCollapsed: a toggle that never opens the section rejects after its timeout (one click)', threw && page.clicks.length === 1);
	}
}

// ─── 8. page helpers (no-op today, one step on the redesign) ────────────────

async function pageHelpers() {
	{
		const oldP = new FakePage('<div class="rail-left open"><form class="form"><select data-testid="planner-origin"></select><input data-testid="planner-label"><input data-testid="planner-officer"></form></div>');
		const newP = new FakePage('<div data-ws="frame"><nav class="rail"><button data-rail="explorer" aria-pressed="false"></button><button data-rail="plan" aria-pressed="false"></button></nav><aside data-dock="left" data-open="false"></aside></div>');
		newP.on('[data-rail="plan"]', (el, p) => append(p, '[data-dock="left"]', '<div class="plan"><select data-testid="planner-origin"></select><input data-testid="planner-label"><input data-testid="planner-officer"></div>'), { delayMs: 20 });
		const a = await ensurePlanner(oldP);
		const b = await ensurePlanner(newP);
		ok('ensurePlanner: today\'s planner → no click; the redesign → one click on [data-rail=plan], the planner mounts', a === false && oldP.clicks.length === 0 && b === true && newP.clicks.length === 1 && !!(await newP.$('[data-testid="planner-label"]')), newP.clicks.join(' '));
	}
	{
		const tabless = new FakePage('<section data-testid="fusion-rail"><div class="tabs"><button class="tab">Timeline</button><button class="tab">Audit</button></div><div class="bt-body"></div></section>');
		tabless.on('[data-testid="fusion-rail"] .tab:last-child', (el, p) => append(p, '.bt-body', '<div class="f-row" data-feed-id="b"></div>'));
		let threw = false;
		try {
			await ensureAuditRows(tabless);
		} catch {
			threw = true;
		}
		ok('ensureAuditRows: a dock with no audit tab and no rows FAILS LOUDLY (UI-S7B: the tab must exist)', threw);
	}
	{
		const oldP = new FakePage(OLD.vitals);
		const newP = new FakePage(`<div data-ws="frame"><nav><button data-rail="info"></button></nav><aside data-dock="left"></aside>${NEW.vitals.split('<section')[0]}</div>`);
		newP.on('[data-rail="info"]', (el, p) => append(p, '[data-dock="left"]', '<section data-testid="vitals-posture"></section><section data-testid="vitals-ethics"></section>'), { delayMs: 20 });
		const a = await ensureVitals(oldP, 'vitals-posture');
		const b = await ensureVitals(newP, 'vitals-posture');
		const c = await ensureVitals(newP, 'vitals-ethics');
		ok('ensureVitals: on the card → no click; map mode → one click on [data-rail=info]; then present → no click', a === false && oldP.clicks.length === 0 && b === true && c === false && newP.clicks.length === 1);
	}
	{
		const oldP = new FakePage('<div data-testid="entity-dossier" data-urn="vehicle:x" data-state="ok"><div class="rel-group" data-relation="sighting"><button class="rel-chip" data-urn="sighting:a">EM-CAM-03</button></div><ol><li class="a-row">approved</li></ol></div>');
		const newP = new FakePage('<div data-testid="entity-dossier" data-urn="vehicle:x" data-state="ok"><div class="tabs" role="tablist"><button role="tab" class="tab on">Properties</button><button role="tab" class="tab">Links <span class="tag count">51</span></button><button role="tab" class="tab">Activity <span class="tag count">7</span></button></div><div class="tab-body"></div></div>');
		newP.on('[data-testid="entity-dossier"] [role="tab"]', (el, p) => {
			const body = p.doc.querySelector('.tab-body');
			body.childNodes.length = 0;
			append(p, '.tab-body', /^Links/.test(el.textContent) ? '<div class="rel-group" data-relation="sighting"><button class="rel-chip" data-urn="sighting:a">EM-CAM-03</button></div>' : '<ol><li class="a-row">Approved</li></ol>');
		});
		const a = await ensureInspectorTab(oldP, 'links', '.rel-chip');
		const b = await ensureInspectorTab(newP, 'links', '.rel-chip');
		const c = await ensureInspectorTab(newP, 'activity', '.a-row');
		ok('ensureInspectorTab: today\'s dossier → no click; the inspector → one click per tab (Links, Activity)', a === false && oldP.clicks.length === 0 && b === true && c === true && newP.clicks.length === 2 && !!(await newP.$('[data-testid="entity-dossier"] .a-row')), newP.clicks.join(' '));
	}
	{
		const newP = new FakePage('<section class="bottom" data-dock="bottom" data-testid="fusion-rail"><div class="bt-head"><div class="tabs"><button class="tab on" data-bottom-tab="timeline">Timeline</button><button class="tab" data-bottom-tab="audit">Audit <span class="tag count">189</span></button></div></div><div class="bt-body"></div></section>');
		newP.on('[data-bottom-tab="audit"]', (el, p) => append(p, '.bt-body', '<table><tr class="f-row" data-prim="feed-item" data-feed-id="a" data-urn="event:x"></tr></table>'), { delayMs: 20 });
		const b = await ensureAuditRows(newP);
		ok('ensureAuditRows: [data-bottom-tab=audit] → one click, then the .f-row', b === true && newP.clicks.length === 1 && !!(await newP.$('[data-testid="fusion-rail"] .f-row')));
	}
	{
		const controlless = new FakePage('<section data-testid="fusion-rail"><div class="seg"><button class="on">Live</button></div></section>');
		const newP = new FakePage('<section data-testid="fusion-rail"><div class="seg"><button data-testid="replay-toggle" aria-pressed="true">Replay</button></div></section>');
		ok('leaveReplay: the Live/Replay control, or null when the page renders none', (await leaveReplay(controlless)) === null && (await leaveReplay(newP)) === 'replay-toggle');
	}
	{
		const newP = new FakePage('<table><tr data-testid="event-card" data-event-id="E" class="row"><td>Puja immersion</td></tr></table>');
		const absent = new FakePage('<table><tr data-testid="event-card" data-event-id="F" class="row"><td>…</td></tr></table>');
		const b = await selectEventRow(newP, '[data-testid="event-card"][data-event-id="E"]');
		const c = await selectEventRow(absent, '[data-testid="event-card"][data-event-id="E"]');
		ok('selectEventRow: a row click (§12.4); an absent row → null', b === 'row' && newP.clicks[0] === 'tr[event-card]' && c === null && absent.clicks.length === 0, `${newP.clicks} · absent ${c}`);
	}
	{
		const closedMenu = new FakePage('<div data-shell="command"><header class="navbar" data-shell="command-bar"><button aria-label="More">⋯</button></header></div>');
		const b = await shellNavigate(closedMenu, '/citizen');
		ok('shellNavigate: a closed More menu → a client-side anchor click', b === 'anchor');
	}
	{
		const gods = new FakePage('<div data-testid="entity-dossier"><input data-testid="dossier-officer"></div>');
		const ops = new FakePage(OLD.shell.replace('<button class="share"', '<input data-testid="duty-officer"><button class="share"'));
		const navbar = new FakePage(NEW.shell);
		const cockpit = new FakePage('<form class="form"><input data-testid="planner-officer"></form>');
		const none = new FakePage('<div></div>');
		const a = await officerField(gods, ['duty-officer', 'dossier-officer']);
		const b = await officerField(navbar, ['duty-officer', 'dossier-officer']);
		const c = await officerField(cockpit);
		const d = await officerField(none);
		const used = await nameOfficer(navbar, 'Duty Officer CC Smoke', { prefer: ['duty-officer', 'dossier-officer'] });
		const usedOps = await nameOfficer(ops, 'Insp. K. Joshi (smoke)');
		ok('officer field by test id: dossier-officer (today\'s /gods-eye), duty-officer (navbar, /ops), planner-officer (cockpit), none → null', a === 'input[data-testid="dossier-officer"]' && b === 'input[data-testid="duty-officer"]' && c === 'input[data-testid="planner-officer"]' && d === null && used === b && usedOps === 'input[data-testid="duty-officer"]' && (await officerValue(navbar)) === 'Duty Officer CC Smoke', `${a} · ${b} · ${c} · ${d}`);
	}
	{
		// only an editable element is an officer field: ConvoyHud's convoy-hud-proposal-officer is a <p> note
		const PREFER = ['planner-officer', 'duty-officer', 'convoy-hud-proposal-officer', 'decision-officer'];
		const card = new FakePage('<div data-testid="convoy-hud-proposal"><p class="ap-note" data-testid="convoy-hud-proposal-officer">name a duty officer to approve</p><div class="proposal-card" data-testid="proposal-card" data-kind="escort"><input data-testid="decision-officer"></div></div>');
		const noteOnly = new FakePage('<div><p data-testid="convoy-hud-proposal-officer">name a duty officer to approve</p></div>');
		const area = new FakePage('<form><textarea data-testid="decision-officer"></textarea></form>');
		const a = await officerField(card, PREFER);
		const b = await officerField(noteOnly, PREFER);
		const c = await officerField(area, ['decision-officer']);
		const threw = await nameOfficer(noteOnly, 'Insp. K. Joshi (smoke)', { prefer: PREFER }).then(() => false, (e) => /no editable duty-officer field/.test(e.message));
		ok('officer field: a <p> note carrying an officer id is never typed into (the decision card\'s input is); a page with only the note fails loudly', a === 'input[data-testid="decision-officer"]' && b === null && c === 'textarea[data-testid="decision-officer"]' && threw && noteOnly.typed.length === 0, `${a} · ${b} · ${c} · threw ${threw}`);
	}
}


// ─── 8b. more in-page and page helpers ─────────────────────────────────────

async function moreHelpers() {
	// CU:434 the event pick is the INSPECTOR opened on the event (the legacy pick card is gone)
	const inspector = new FakePage('<div data-testid="entity-dossier" data-urn="event:P1"><div class="ttl">Pursuit of MH47EM•••1</div></div>');
	ok('firstPresentText(EVENT_PICK): the inspector on event:; a page without one reads null', inspector.run(() => firstPresentText(EVENT_PICK)) === 'Pursuit of MH47EM•••1' && new FakePage('<div class="ge-hud"><div class="ge-pick"><p class="pick-text">On the map</p></div></div>').run(() => firstPresentText(EVENT_PICK)) === null);
	ok('lockTitle: the pressed Follow chip\'s title; a text-only LOCKED chip and the pick card\'s FOCUS chip are not locks', new FakePage(NEW.hud).run(lockTitle) === 'Follow selection' && new FakePage(OLD.hud).run(lockTitle) === null && new FakePage('<div class="ge-hud"><div class="ge-pick"><button class="chip lock" title="fly to this event">⊕ FOCUS</button></div></div>').run(lockTitle) === null);
	ok('maskMarks: the C6 mask over free text', maskMarks('PURSUIT — stolen MH47EM9001 (FIR 4401/2026)') === 'PURSUIT — stolen MH47EM•••1 (FIR 4401/2026)' && maskMarks('MH01 AB 1234 and MH05CD5678') === 'MH01 AB •••4 and MH05CD•••8' && maskMarks(null) === '');
	{
		const page = new FakePage('<div data-ws="frame"><nav><button data-rail="layers"></button></nav><aside data-dock="left"></aside></div>');
		page.on('[data-rail="layers"]', (el, p) => append(p, '[data-dock="left"]', NEW.hud.slice(NEW.hud.indexOf('<ul class="tree layer-tree">'), NEW.hud.indexOf('</ul>') + 5)), { delayMs: 10 });
		const b = await ensureLayers(page);
		const c = await ensureRail(page, 'layers', '[data-layer]');
		ok('ensureLayers / ensureRail: the LayerTree behind [data-rail=layers] → one click; then present → no click', b === true && c === false && page.clicks.length === 1 && !!(await page.$('[data-layer="flow"] [data-testid="chip-simulated"]')));
	}
	{
		const page = new FakePage('<div data-shell="command"><header class="navbar" data-shell="command-bar"><button class="btn minimal" aria-label="More">⋯</button></header></div>');
		page.on('[aria-label="More"]', (el, p) => append(p, '[data-shell="command-bar"]', '<div class="menu" role="menu"><a href="/citizen" role="menuitem">Citizen advisory</a></div>'), { delayMs: 10 });
		ok('shellNavigate: the redesign\'s More menu → one click on More, then its /citizen link', (await shellNavigate(page, '/citizen')) === 'more-menu' && page.clicks.length === 2, page.clicks.join(' '));
	}
	{
		// settleSpots: the home flight moves the spots three reads, then they hold
		let n = 0;
		const moving = new FakePage('<div></div>', { window: { __GODS_EYE__: { locate: () => [{ id: 'cam:EM-CAM-01', x: n < 3 ? 1300 - 100 * n++ : 1093, y: 533 }] } } });
		const t0 = Date.now();
		const settled = await settleSpots(moving, 'cam:EM-CAM', { timeout: 6000 });
		let m = 0;
		const flying = new FakePage('<div></div>', { window: { __GODS_EYE__: { locate: () => [{ id: 'cam:EM-CAM-01', x: 100 + 10 * m++, y: 1 }] } } });
		const never = await settleSpots(flying, 'cam:EM-CAM', { timeout: 1200 });
		ok('settleSpots: waits out a moving view, gives up (false) on one that never holds still', settled === true && Date.now() - t0 >= 1000 && never === false);
	}
	{
		// isViteDevServer against two loopback servers (one serving /@vite/client, one 404)
		const http = await import('node:http');
		const serve = (dev) =>
			new Promise((resolve) => {
				const srv = http.createServer((req, res) => {
					if (dev && req.url === '/@vite/client') {
						res.writeHead(200, { 'content-type': 'text/javascript' });
						res.end('export {}');
					} else {
						res.writeHead(404, { 'content-type': 'text/plain' });
						res.end('not found');
					}
				});
				srv.listen(0, '127.0.0.1', () => resolve(srv));
			});
		const dev = await serve(true);
		const prod = await serve(false);
		const at = (s) => `http://127.0.0.1:${s.address().port}`;
		const [d, p] = [await isViteDevServer(at(dev)), await isViteDevServer(at(prod))];
		dev.close();
		prod.close();
		const closed = await isViteDevServer('http://127.0.0.1:9');
		ok('isViteDevServer: a server serving /@vite/client is a vite dev server; a 404 or a closed port is not', d === true && p === false && closed === false);
	}
}

// ─── 8c. city-command geometry and pick dismissal; shell links; /citizen ────

/** Today's City Command at 1920×1080 (gods-eye/+page.svelte:236-248: the stage, three glass panels over the canvas). */
const OLD_CC = (dossier = true) => `<main class="city-command"><section class="stage" style="left:0px;top:0px;width:1920px;height:1080px">
	<div class="ge-wrap"><div class="ge-canvas" style="left:0px;top:0px;width:1920px;height:1080px"><canvas></canvas></div><div class="ge-hud"><div class="hud-row"><button class="chip exit">⤡ EXIT</button></div></div></div>
	<aside class="glass vitals-panel" style="left:12px;top:12px;width:300px;height:824px"><div class="vitals" data-testid="city-vitals"></div></aside>
	${dossier ? '<aside class="glass dossier-panel" style="left:1528px;top:12px;width:380px;height:824px"><div data-testid="entity-dossier" data-urn="junction:3" data-state="ok"></div></aside>' : ''}
	<section class="glass rail-panel" style="left:12px;top:848px;width:1896px;height:220px"><div data-testid="fusion-rail"></div></section></section></main>`;

/**
 * The redesign's /gods-eye in map mode (prototype workspace.js:515-525 frame, 251 vitals card; shot 07): the map
 * pane full-bleed under the navbar and the pane header, the vitals card floating top right inside it, the bottom
 * dock's 38 px header below it. `right` overlays an open right dock holding the inspector.
 */
const NEW_CC = ({ right = false, pane = true } = {}) => `<div class="app" data-shell="command"><header class="navbar" data-shell="command-bar" style="left:0px;top:0px;width:1920px;height:48px"></header>
	<div class="ws" data-ws="frame" data-template="convoy-command" style="left:0px;top:48px;width:1920px;height:1032px">
	<nav class="rail" style="left:0px;top:48px;width:44px;height:1032px"><button data-rail="explorer"></button><button data-rail="info"></button></nav>
	<aside class="dock left" data-dock="left" data-open="false" style="left:44px;top:48px;width:0px;height:1032px"></aside>
	<main class="center" style="left:44px;top:48px;width:1876px;height:1032px"><div class="pane-head" style="left:44px;top:48px;width:1876px;height:42px"></div>
	<div class="views" style="left:44px;top:90px;width:1876px;height:952px"><div class="map ge-wrap"${pane ? ' data-pane="map"' : ''} style="left:44px;top:90px;width:1876px;height:952px">
	<div class="ge-canvas" style="left:44px;top:90px;width:1876px;height:952px"><canvas></canvas></div><div class="ge-hud"><div class="toolbar"><button class="chip">S</button><button class="chip exit" aria-label="Exit map mode">Exit</button></div></div>
	<div class="vitals" data-testid="city-vitals" style="left:1660px;top:100px;width:250px;height:190px"><div class="vrow" data-testid="vitals-feeds"></div></div></div></div>
	<section class="bottom" data-dock="bottom" data-open="true" data-testid="fusion-rail" style="left:44px;top:1042px;width:1876px;height:38px"></section></main>
	${right ? '<aside class="dock right" data-dock="right" data-open="true" style="left:1520px;top:90px;width:400px;height:952px"><div class="insp" data-testid="entity-dossier" data-urn="junction:3" style="left:1520px;top:90px;width:400px;height:952px"></div></aside>' : '<aside class="dock right" data-dock="right" data-open="false" style="left:1920px;top:48px;width:0px;height:1032px"></aside>'}
	</div></div>`;

async function cityCommandHelpers() {
	{
		const same = (r, want) => !!r && Object.entries(want).every(([k, v]) => r[k] === v);
		const fmt = (r) => (r ? `${r.left}–${r.right} × ${r.top}–${r.bottom} (centre ${r.cx},${r.cy})` : 'null');
		const legacy = new FakePage(OLD_CC()).run(clearCanvasRegion);
		ok('CC:305 clearCanvasRegion: a page without the workspace frame → null (the legacy .stage layout is gone)', legacy === null, fmt(legacy));
		const mapMode = new FakePage(NEW_CC()).run(clearCanvasRegion);
		const inspector = new FakePage(NEW_CC({ right: true })).run(clearCanvasRegion);
		const canvasOnly = new FakePage(NEW_CC({ pane: false })).run(clearCanvasRegion);
		const inside = (r, x, y) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
		ok('CC:305 clearCanvasRegion, map mode: the map pane below its toolbar row minus the vitals card (the closed docks and the bottom dock below the pane do not count)', same(mapMode, { left: 44, right: 1660, top: 146, bottom: 1042, cx: 852, cy: 594 }) && same(canvasOnly, { left: 44, right: 1660, top: 146, bottom: 1042 }), `${fmt(mapMode)} · .ge-canvas fallback ${fmt(canvasOnly)}`);
		ok('CC:305 clearCanvasRegion, an open right dock with the inspector over the map: trimmed off, the centre clear of every obstacle', same(inspector, { left: 44, right: 1520, top: 146, bottom: 1042, cx: 782, cy: 594 }) && !inside({ left: 1660, right: 1910, top: 100, bottom: 290 }, inspector.cx, inspector.cy) && !inside({ left: 1520, right: 1920, top: 90, bottom: 1042 }, inspector.cx, inspector.cy), fmt(inspector));
		const holder = new FakePage(NEW_CC().replace('<div class="views"', '<div class="views" data-dock="center" data-open="true"')).run(clearCanvasRegion);
		const covered = new FakePage(NEW_CC().replace('data-dock="left" data-open="false" style="left:44px;top:48px;width:0px;height:1032px"', 'data-dock="left" data-open="true" style="left:44px;top:48px;width:1876px;height:1032px"')).run(clearCanvasRegion);
		const neither = new FakePage('<main><div class="ge-wrap"><div class="ge-canvas"></div></div></main>').run(clearCanvasRegion);
		ok('CC:305 clearCanvasRegion: a dock that holds the pane is no obstacle; a pane covered whole → null; neither layout → null', same(holder, { left: 44, right: 1660 }) && covered === null && neither === null, `${fmt(holder)} · ${fmt(covered)} · ${fmt(neither)}`);
	}
	{
		const g = (urn) => ({ __GODS_EYE__: { selection: { urn } } });
		// (a) today's wall / cockpit pick card: its ✕
		const card = new FakePage('<div class="ge-hud"><div class="ge-pick" data-pick-layer="events"><header><button class="pick-x" aria-label="dismiss pick card">✕</button></header><p class="pick-text">Metro work zone — Strand Road</p></div></div>', { window: g('event:W1') });
		card.on('.pick-x', (el, p) => p.doc.querySelector('.ge-pick').remove());
		const a = await dismissPick(card, { wantUrn: 'dispatch:D2', before: null });
		// (b) today's /gods-eye: a URN pick opens the dossier (no pick card); Esc clears the selection, the dossier goes
		const oldDossier = new FakePage(OLD_CC(), { window: g('junction:3') }).onKey((k, p) => {
			if (k !== 'Escape') return;
			p.window.__GODS_EYE__.selection.urn = null;
			p.doc.querySelector('.dossier-panel').remove();
		});
		const b = await dismissPick(oldDossier, { wantUrn: 'dispatch:D2', before: null });
		// (c) the redesign: the inspector opened on the neighbour; Esc closes it (the selection may stay: "closes, then clears")
		const newInspector = new FakePage(NEW_CC({ right: true }), { window: g('junction:3') }).onKey((k, p) => {
			if (k !== 'Escape') return;
			const dock = p.doc.querySelector('[data-dock="right"]');
			dock.setAttribute('data-open', 'false');
			dock.hidden = true;
		});
		const c = await dismissPick(newInspector, { wantUrn: 'dispatch:D2', before: null });
		ok('dismissPick: today\'s pick card → its ✕ (no key); today\'s dossier → one Esc, the selection clears; the redesign\'s inspector → one Esc, it closes', a === 'pick-x' && !card.doc.querySelector('.ge-pick') && card.keys.length === 0 && b === 'escape' && oldDossier.keys.join() === 'Escape' && !oldDossier.doc.querySelector('.dossier-panel') && c === 'escape' && newInspector.keys.join() === 'Escape', `${a} · ${b} (${oldDossier.keys}) · ${c} (${newInspector.keys})`);
		// never an Esc for the wanted object, a selection held before the click, or nothing selected (today's /gods-eye: Esc = EXIT)
		const wanted = new FakePage(NEW_CC({ right: true }).replace('junction:3', 'dispatch:D2'), { window: g('dispatch:D2') });
		const held = new FakePage(NEW_CC({ right: true }), { window: g('event:P1') });
		const nothing = new FakePage(OLD_CC(false), { window: g(null) });
		const d = await dismissPick(wanted, { wantUrn: 'dispatch:D2' });
		const e = await dismissPick(held, { wantUrn: 'dispatch:D2', before: 'event:P1' });
		const f = await dismissPick(nothing, { wantUrn: 'dispatch:D2' });
		ok('dismissPick: no Esc for the wanted object, for the selection held before the click, or with nothing selected', d === null && e === null && f === null && wanted.keys.length + held.keys.length + nothing.keys.length === 0, `${d} · ${e} · ${f}`);
		// an Esc that changes nothing is reported, bounded
		const stuck = new FakePage(NEW_CC({ right: true }), { window: g('junction:3') });
		const t0 = Date.now();
		const h = await dismissPick(stuck, { timeout: 300 });
		ok('dismissPick: an Esc that closes nothing → escape-held within the timeout', h === 'escape-held' && stuck.keys.length === 1 && Date.now() - t0 < 2000, h);
	}
	{
		const inMore = more(['/citizen', '/driver']);
		const notInMore = more(['/driver']);
		const bare = new FakePage('<div data-shell="command"><header data-shell="command-bar"></header><main><a href="/design">design sheet</a></main></div>');
		const b = await findShellLink(inMore, '/citizen', { timeout: 300 });
		const c = await findShellLink(notInMore, '/design', { timeout: 300 });
		const d = await findShellLink(bare, '/design', { timeout: 300 });
		await sleep(40); // the fake menu closes 10 ms after the click
		ok('findShellLink: the More menu → more-menu, opened and closed again; not in More → null (closed again); no shell link, no More → null (no click; a page-body link does not count)', b === 'more-menu' && inMore.clicks.length === 2 && !inMore.doc.querySelector('[role="menu"]') && c === null && notInMore.clicks.length === 2 && !notInMore.doc.querySelector('[role="menu"]') && d === null && bare.clicks.length === 0, `${b} (${inMore.clicks.length} clicks) · ${c} (${notInMore.clicks.length}) · ${d}`);
	}
	// the more() factory the two checks above share
	function more(links) {
		const page = new FakePage('<div data-shell="command"><header class="navbar" data-shell="command-bar"><button class="btn minimal icon-only" aria-label="More">⋯</button></header><main><a href="/citizen">a page link</a></main></div>');
		page.on('[aria-label="More"]', (el, p) => {
			const open = p.doc.querySelector('[role="menu"]');
			if (open) open.remove();
			else append(p, '[data-shell="command-bar"]', `<ul class="menu" role="menu">${links.map((h) => `<li><a href="${h}" role="menuitem">${h}</a></li>`).join('')}</ul>`);
		}, { delayMs: 10 });
		return page;
	}
	{
		const dev = isLiveDeckOrigin('http://127.0.0.1:5401');
		const live = isLiveDeckOrigin('http://127.0.0.1:5273');
		const v = (o) => citizenCardsVerdict({ holds: 0, feed: 'live', empty: false, ...o }).ok;
		ok('isLiveDeckOrigin: only :5273', live === true && dev === false && isLiveDeckOrigin('http://127.0.0.1:5262') === false && isLiveDeckOrigin('nonsense') === false);
		ok(
			'SV:312 citizenCardsVerdict: the live deck always needs a card; a non-live deck whose feed lists none needs the empty state and no card; otherwise cards > 0',
			!v({ live: true, listed: 0, cards: 0, empty: true }) && v({ live: true, listed: 0, cards: 2 }) && v({ live: false, listed: 0, cards: 0, empty: true }) && v({ live: false, listed: 0, cards: 0, empty: true, feed: 'stale' }) && !v({ live: false, listed: 0, cards: 0, empty: false }) && !v({ live: false, listed: 0, cards: 0, empty: true, feed: 'down' }) && !v({ live: false, listed: 0, cards: 1, empty: true }) && !v({ live: false, listed: 3, cards: 0, empty: true }) && v({ live: false, listed: 3, cards: 3 }) && !v({ live: false, listed: null, cards: 0, empty: true }),
		);
	}
}

// ─── 10. /comms (screens-verify): the draft columns, the public-event pick, the withheld verdict ──

/** The desk's copy (src/lib/i18n/strings.citizen.ts comms_withheld, adv_citizen_hold) on a pursuit and a procession. */
const WITHHELD = {
	en: 'Operator-only event kind — no citizen advisory is drafted for it.',
	hi: 'केवल-ऑपरेटर घटना प्रकार — इसके लिए नागरिक सलाह नहीं बनाई जाती।',
	mr: 'ફક્ત-ઓપરેટર ઘટના પ્રકાર — તેના માટે નાગરિક સલાહ તૈયાર થતી નથી.',
};
const DRAFTED = {
	en: 'Procession: ~3 min hold on the route from 10:05. Use Howrah Bridge instead. Roads reopen on time.',
	hi: 'शोभायात्रा: 10:05 से मार्ग पर ~3 मिनट का ठहराव। Howrah Bridge इस्तेमाल करें। सड़कें समय पर खुलेंगी।',
	mr: 'શોભાયાત્રા: 10:05 થી માર્ગ પર ~3 મિનિટનો અવરોધ. Howrah Bridge વાપરો. રસ્તા સમયસર ખૂલશે.',
};
const PURSUIT_FACTS = { kind: 'vehicle_pursuit', segment: 1015, road: 'Strand Road', minutes: null, alternate: 'Sahid Khudiram Bose Road / Indira Gandhi Sarani (Red Road)', anchorMs: 1 };
const PROC_FACTS = { kind: 'procession', segment: 1013, road: 'Strand Road', minutes: 3, alternate: 'Howrah Bridge', anchorMs: 1 };
const LANGS = ['en', 'hi', 'mr'];

/** One draft column as today's desk renders it (comms/+page.svelte:389-404); `copy` 'disabled' | 'enabled' | null (none). */
function oldCommsCol(lang, text, { withheld, facts, copy = withheld ? 'disabled' : 'enabled' }) {
	const f = facts === undefined ? '' : ` data-facts='${JSON.stringify(facts)}'`;
	const b = copy ? `<button class="copy" title="Copy"${copy === 'disabled' ? ' disabled=""' : ''}>Copy</button>` : '';
	return `<article class="lang-col" data-lang="${lang}" data-withheld="${withheld ? 'yes' : 'no'}"${f}><header><span class="lang-name">${lang}</span>${b}</header><p class="adv-text${withheld ? ' withheld' : ''}" data-adv-lang="${lang}" lang="${lang}">${text}</p></article>`;
}

/** The rebuilt desk's column (SPEC §6.5: the drafts side by side, a per-language Copy icon button; citizen-smoke's data attributes kept). */
function newCommsCol(lang, text, { withheld, facts, copy = withheld ? 'disabled' : 'enabled' }) {
	const f = facts === undefined ? '' : ` data-facts='${JSON.stringify(facts)}'`;
	const b = copy ? `<button class="btn sm" aria-label="Copy"${copy === 'disabled' ? ' disabled=""' : ''}><svg class="ic"></svg></button>` : '';
	return `<div class="draft" data-lang="${lang}" data-withheld="${withheld ? 'yes' : 'no'}"${f}><div class="draft-head"><span>${lang}</span>${b}</div><div class="draft-text" data-adv-lang="${lang}">${text}</div></div>`;
}

/** The withheld badge on the event's meta line (comms/+page.svelte): `reason` 'osint' | 'operator-kind'. */
const badgeHtml = (reason, text = reason === 'osint' ? 'Unverified OSINT — withheld from citizens and 108' : WITHHELD.en) =>
	`<span class="withheld-note" data-testid="comms-withheld-badge" data-withheld-reason="${reason}">${text}</span>`;

/** The desk: its event select (null: none), the withheld badge(s) (`badge`: a reason, a list of reasons, or null), today's template preview for an operator-only kind, and the drafts box. */
function commsDesk(cols, { options = ['P'], value = options?.[0], ready = 'yes', preview = false, badge = null } = {}) {
	const select = options ? `<select data-testid="comms-event-select" value="${value}">${options.map((v) => `<option value="${v}">${v}</option>`).join('')}</select>` : '';
	const badges = (badge == null ? [] : [].concat(badge)).map((r) => badgeHtml(r)).join('');
	const tpl = preview ? `<section class="tpl-centre" data-testid="comms-template-centre"><div class="trilingual">${LANGS.map((l) => `<article class="lang-col" data-template-lang="${l}"><p class="adv-text" lang="${l}">Procession: ~3 min hold on the route from 10:05.</p></article>`).join('')}</div></section>` : '';
	return `<div class="comms" data-screen="comms">${select}<p class="ev-meta">${badges}</p>${tpl}<div class="trilingual" data-testid="comms-trilingual" data-ready="${ready}">${cols.join('')}</div></div>`;
}

/**
 * The REAL operator-only arm, cut from the merged desk's own source
 * (src/routes/(deck)/comms/+page.svelte): its operator-kind badge and its
 * `<div class="trilingual withheld">` block, the `{#each SUPPORTED}` expanded
 * for en/hi/mr. `leak` writes text into the withheld draft line (audit E-S7B
 * mutant W1). Returns null when the markup is not found or a Svelte
 * expression is left unexpanded — the self-check then FAILS, so a reworked
 * desk makes this sample be revisited instead of silently testing nothing.
 */
const COMMS_SVELTE = new URL('../../src/routes/(deck)/comms/+page.svelte', import.meta.url);
function realOperatorOnlyDesk({ leak = null, preview = true } = {}) {
	const src = readFileSync(COMMS_SVELTE, 'utf8');
	const badge = src.match(/<span class="withheld-note" data-testid="comms-withheld-badge" data-withheld-reason="operator-kind">[\s\S]*?<\/span>/)?.[0];
	const tri = src.match(/<div class="trilingual withheld" data-testid="comms-trilingual" data-ready=\{facts \? 'yes' : 'no'\}>\s*\{#each SUPPORTED as s \(s\.code\)\}([\s\S]*?)\{\/each\}\s*<\/div>/);
	if (!badge || !tri) return null;
	let body = tri[1];
	const LINE = '<p class="adv-text withheld" lang={s.code}></p>';
	if (!body.includes(LINE)) return null;
	if (leak != null) body = body.replace(LINE, `<p class="adv-text withheld" lang={s.code}>${leak}</p>`);
	const LABEL = { en: 'English', hi: 'हिन्दी', mr: 'मराठी' };
	const cols = LANGS.map((l) => body.replaceAll('{s.code}', `"${l}"`).replaceAll('{s.label}', LABEL[l])).join('');
	const b = badge.replace(/<Icon [^>]*\/>/, '').replace("{citizenT(lang, 'comms_withheld')}", WITHHELD.en);
	const html = `<div class="comms" data-screen="comms"><select data-testid="comms-event-select" value="P"><option value="P">P</option></select><p class="ev-meta">${b}</p>${preview ? commsDesk([], { options: null, preview: true }).replace(/<div class="trilingual" data-testid="comms-trilingual"[\s\S]*$/, '') : ''}<div class="trilingual withheld" data-testid="comms-trilingual" data-ready="yes">${cols}</div></div>`;
	return /[{}]/.test(html.replace(/data-facts='[^']*'/g, '')) ? null : html;
}

const withheldCols = (col = oldCommsCol, edit = {}) => LANGS.map((l) => col(l, edit.text?.[l] ?? WITHHELD[l], { withheld: true, facts: PURSUIT_FACTS, ...(edit.opts?.[l] ?? {}) }));
const draftedCols = (col = oldCommsCol, edit = {}) => LANGS.map((l) => col(l, edit.text?.[l] ?? DRAFTED[l], { withheld: false, facts: PROC_FACTS, ...(edit.opts?.[l] ?? {}) }));

/** The fake desk: a select change drops the drafts (data-ready → no), and the new event's drafts land 10 ms later (never, with `answer` false). */
function commsApp(kinds, options, { first = options[0], answer = true } = {}) {
	const colsFor = (id) => (kinds[id] === 'public' ? draftedCols() : withheldCols());
	const page = new FakePage(commsDesk(colsFor(first), { options, value: first, badge: 'osint' }));
	page.onSelect((_el, value, pg) => {
		const box = pg.doc.querySelector('[data-testid="comms-trilingual"]');
		box.setAttribute('data-ready', 'no');
		for (const n of box.children) n.remove();
		if (!answer) return;
		setTimeout(() => pg.run(() => {
			for (const n of parseHTML(colsFor(value).join('')).childNodes) box.appendChild(n);
			box.setAttribute('data-ready', 'yes');
		}), 10);
	});
	return page;
}

async function commsChecks() {
	const read = (html) => new FakePage(html).run(() => commsDrafts(COMMS_DRAFTS));
	// the in-page reader over today's markup and the redesign's
	const oldW = read(commsDesk(withheldCols(), { preview: true }));
	const oldD = read(commsDesk(draftedCols(), { options: ['E'] }));
	const newW = read(commsDesk(withheldCols(newCommsCol)));
	const newD = read(commsDesk(draftedCols(newCommsCol), { options: ['E'] }));
	ok(
		'SV:/comms commsDrafts on the OSINT arm\'s withheld desk: the three draft columns (the template preview\'s data-template-lang columns excluded), withheld, their facts and a disabled Copy',
		oldW.langs.join() === 'en,hi,mr' && oldW.ready && oldW.event === 'P' && oldW.cols.every((c) => c.withheld === 'yes' && c.facts?.road === 'Strand Road' && c.copy?.disabled === true) && oldW.filled === 3 && oldW.facts.length === 0 && !oldW.sameRoad,
		JSON.stringify(oldW.cols.map((c) => [c.lang, c.withheld, c.facts?.road, c.copy?.disabled])),
	);
	ok(
		'SV:/comms commsDrafts on a public event (old + new markup): HEAD\'s Latin road reading — Howrah Bridge verbatim in all three; Copy enabled',
		[oldD, newD].every((d) => d.sameRoad && d.facts.join() === 'Howrah Bridge' && d.cols.every((c) => c.withheld === 'no' && c.copy?.disabled === false)),
		`${oldD.facts.join('|')} · ${newD.facts.join('|')}`,
	);
	ok(
		'SV:/comms commsDrafts on the rebuilt desk: the Copy icon button found by its label, disabled on withheld drafts',
		newW.langs.join() === 'en,hi,mr' && newW.cols.every((c) => c.withheld === 'yes' && c.copy?.disabled === true && c.text === WITHHELD[c.lang]),
	);
	ok('SV:/comms commsDrafts: a drafts box with data-ready="no" is not ready', read(commsDesk(withheldCols(), { ready: 'no' })).ready === false && read('<div data-screen="comms"></div>').ready === false);

	// MARK_IN_TEXT: raw and masked marks; never the desk's own copy, a segment, a FIR or a clock
	const marks = ['MH47EM9001', 'stolen MH 47 EM 9001 seen', 'MH-01-AB-1234', 'MH47EM•••1', 'plate •••1'];
	const clean = [...Object.values(WITHHELD), ...Object.values(DRAFTED), 'segment 1015 · FIR 4401/2026 · 10:05 IST', 'MH47 EM'];
	ok('SV:/comms MARK_IN_TEXT: raw and masked registration marks found; the desk\'s copy, segments, FIR numbers and clocks not', marks.every((m) => MARK_IN_TEXT.test(m)) && !clean.some((c) => MARK_IN_TEXT.test(c)), `${marks.filter((m) => !MARK_IN_TEXT.test(m)).join('|') || 'all marks found'} · ${clean.filter((c) => MARK_IN_TEXT.test(c)).join('|') || 'no false hit'}`);

	// the verdict. withheldCols() is the OSINT arm's shape (the notice, a
	// disabled Copy, data-facts kept); the operator-only arm is the REAL markup
	// cut from comms/+page.svelte (realOperatorOnlyDesk).
	const none = { listed: 1, tried: 0, picked: null, public: false };
	const v = (html, o = {}) => commsFactsVerdict({ live: false, pick: none, ...read(html), ...o });
	const osintDesk = (cols, o = {}) => commsDesk(cols, { badge: 'osint', ...o });
	ok('SV:/comms commsFactsVerdict: a public event\'s drafts pass on HEAD\'s assertion (live deck too); a road missing from one draft fails', v(commsDesk(draftedCols()), { pick: { listed: 3, tried: 1, picked: 'E', public: true } }).ok && v(commsDesk(draftedCols()), { live: true, pick: { listed: 3, tried: 0, picked: 'E', public: true } }).ok && !v(commsDesk(draftedCols(oldCommsCol, { text: { en: 'Procession: ~3 min hold on the route from 10:05. Roads reopen on time.' } }))).ok);
	ok('SV:/comms commsFactsVerdict: OSINT-withheld drafts (the notice, Copy disabled, the badge once) pass only off the live deck with no public event listed (old + new markup)', v(osintDesk(withheldCols())).ok && v(osintDesk(withheldCols(newCommsCol))).ok, v(osintDesk(withheldCols())).detail);
	// the REAL operator-only markup (no data-adv-lang on its draft line)
	{
		const real = realOperatorOnlyDesk();
		ok('SV:/comms the real operator-only arm is cut from comms/+page.svelte (badge + the trilingual withheld block, every Svelte expression expanded)', !!real, real ? `${real.length} chars` : 'markup not found or an expression left unexpanded — revisit realOperatorOnlyDesk');
		if (real) {
			const r = read(real);
			ok(
				'SV:/comms commsDrafts on the REAL operator-only arm: three draft columns (template preview excluded), each withheld, its draft line READ (.adv-text — no data-adv-lang there) and empty, no Copy, data-facts empty, the operator-kind badge once',
				r.langs.join() === 'en,hi,mr' && r.cols.every((c) => c.withheld === 'yes' && c.text === '' && c.copy === null && c.factsRaw === '') && r.badges.length === 1 && r.badges[0].reason === 'operator-kind',
				JSON.stringify({ cols: r.cols.map((c) => [c.lang, c.withheld, c.text, c.copy, c.factsRaw]), badges: r.badges }),
			);
			const good = v(real);
			ok('SV:/comms commsFactsVerdict ACCEPTS the real operator-only arm off the live deck with no public event listed', good.ok, good.detail);
			ok('SV:/comms withheldColumnsVerdict (citizen-smoke\'s pursuit check) accepts the real operator-only arm as operator-kind, refuses it as osint', withheldColumnsVerdict({ ...r, reason: 'operator-kind' }).ok && !withheldColumnsVerdict({ ...r, reason: 'osint' }).ok);
			// mutant W1: a leaked draft with a raw mark in the withheld column
			const leak = realOperatorOnlyDesk({ leak: 'Hold on Howrah Bridge for MH47EM9001 (leaked draft)' });
			const plain = realOperatorOnlyDesk({ leak: 'Procession: ~3 min hold on the route from 10:05.' });
			const lr = read(leak);
			const w1 = [v(leak), withheldColumnsVerdict({ ...lr, reason: 'operator-kind' }), v(plain)];
			ok('SV:/comms mutant W1 refused: a draft leaked into the real operator-only column (with a raw mark, or any text at all) fails both verdicts', lr.cols.every((c) => c.text.length > 0) && w1.every((x) => !x.ok), w1.map((x) => x.detail).join(' ‖ '));
			ok('SV:/comms the W1 refusal quotes the mark masked, never raw', !w1[0].detail.includes('MH47EM9001') && w1[0].detail.includes('MH47EM•••1'), w1[0].detail);
			// a Copy or data-facts sneaking back into the operator-only arm
			const withCopy = real.replace(/(<article class="lang-col" data-lang="mr"[^>]*>\s*<header>)/, '$1<button class="copy" data-copy="mr" disabled="">Copy</button>');
			const withFacts = real.replace('data-lang="hi" data-withheld="yes" data-facts=""', `data-lang="hi" data-withheld="yes" data-facts='${JSON.stringify(PURSUIT_FACTS)}'`);
			const twoBadges = real.replace('<p class="ev-meta">', `<p class="ev-meta">${badgeHtml('operator-kind')}`);
			const noBadge = real.replace(/<span class="withheld-note"[\s\S]*?<\/span>/, '');
			const opRef = [
				['a (disabled) Copy back in a column', withCopy],
				['data-facts carried by a column', withFacts],
				['the notice stated twice (two badges)', twoBadges],
				['the notice never stated (no badge)', noBadge],
			].map(([n, h]) => [n, v(h), h !== real]);
			const opPassed = opRef.filter(([, r2, changed]) => r2.ok || !changed).map(([n]) => n);
			ok('SV:/comms the operator-only contract refuses: a Copy control, data-facts, the badge twice or never', opPassed.length === 0, opPassed.length ? `accepted or not applied: ${opPassed.join(' | ')}` : opRef.map(([n, r2]) => `${n} → ${r2.detail}`).join(' ‖ '));
		}
	}
	const refusals = [
		['the live origin', v(osintDesk(withheldCols()), { live: true })],
		['a public event listed (picked, yet withheld)', v(osintDesk(withheldCols()), { pick: { listed: 3, tried: 1, picked: 'E', public: true } })],
		['the list not read in full', v(osintDesk(withheldCols()), { pick: { listed: null, tried: 0, picked: null, public: null } })],
		['a withheld draft naming the road (any case)', v(osintDesk(withheldCols(oldCommsCol, { text: { en: `${WITHHELD.en} (strand road)` } })))],
		['a withheld draft naming the alternate', v(osintDesk(withheldCols(oldCommsCol, { text: { mr: `${WITHHELD.mr} Indira Gandhi Sarani (Red Road)` } })))],
		['a withheld draft carrying a raw mark', v(osintDesk(withheldCols(oldCommsCol, { text: { hi: `${WITHHELD.hi} MH47EM9001` } })))],
		['a withheld draft carrying a masked mark', v(osintDesk(withheldCols(newCommsCol, { text: { en: `${WITHHELD.en} MH47EM•••1` } })))],
		['an enabled Copy', v(osintDesk(withheldCols(oldCommsCol, { opts: { mr: { copy: 'enabled' } } })))],
		['an osint column with no notice', v(osintDesk(withheldCols(oldCommsCol, { text: { hi: '' } })))],
		['an osint column with no Copy', v(osintDesk(withheldCols(oldCommsCol, { opts: { en: { copy: null } } })))],
		['no badge at all', v(commsDesk(withheldCols()))],
		['two badges', v(commsDesk(withheldCols(), { badge: ['osint', 'osint'] }))],
		['columns that disagree (two withheld, one drafted)', v(osintDesk([...withheldCols().slice(0, 2), draftedCols()[2]]))],
		['two columns only', v(osintDesk(withheldCols().slice(0, 2)))],
	];
	const passed = refusals.filter(([, r]) => r.ok).map(([n]) => n);
	const rawLeak = refusals.find(([n]) => n === 'a withheld draft carrying a raw mark')[1].detail;
	ok('SV:/comms commsFactsVerdict refuses: the live origin, a listed public event or an unread list, a withheld draft naming the road or its alternate or carrying a mark (raw or masked), an enabled Copy, an osint column without its notice or its disabled Copy, the badge missing or twice, disagreeing or missing columns', passed.length === 0, passed.length ? `accepted: ${passed.join(' | ')}` : refusals.map(([n, r]) => `${n} → ${r.detail}`).join(' ‖ '));
	ok('SV:/comms commsFactsVerdict quotes a raw mark masked, never raw', !rawLeak.includes('MH47EM9001') && rawLeak.includes('MH47EM•••1'), rawLeak);

	// the public-event pick on a fake desk
	{
		const a = commsApp({ P: 'op', E: 'public', X: 'op' }, ['P', 'E', 'X']);
		const ra = await pickPublicCommsEvent(a, { timeout: 500 });
		const after = a.run(() => commsDrafts(COMMS_DRAFTS));
		ok('pickPublicCommsEvent: the first event operator-only → the first public one picked (one select), its drafts read', ra.public === true && ra.picked === 'E' && ra.tried === 1 && a.selected.join() === 'E' && after.sameRoad && commsFactsVerdict({ live: true, pick: ra, ...after }).ok, `${JSON.stringify(ra)} · selects ${a.selected.join(',')}`);
	}
	{
		const b = commsApp({ P: 'op', X: 'op' }, ['P', 'X']);
		const rb = await pickPublicCommsEvent(b, { timeout: 500 });
		const after = b.run(() => commsDrafts(COMMS_DRAFTS));
		ok('pickPublicCommsEvent: every listed event operator-only → each tried, the desk put back on its first, public false; the withheld verdict then passes off the live deck only', rb.public === false && rb.listed === 2 && rb.tried === 1 && b.selected.join() === 'X,P' && after.event === 'P' && after.ready && commsFactsVerdict({ live: false, pick: rb, ...after }).ok && !commsFactsVerdict({ live: true, pick: rb, ...after }).ok, `${JSON.stringify(rb)} · selects ${b.selected.join(',')}`);
	}
	{
		const c = commsApp({ E: 'public', P: 'op' }, ['E', 'P']);
		const d = commsApp({ P: 'op' }, ['P']);
		const rc = await pickPublicCommsEvent(c, { timeout: 500 });
		const rd = await pickPublicCommsEvent(d, { timeout: 500 });
		ok('pickPublicCommsEvent: the first event public → no select; a single operator-only event → public false, no select', rc.public === true && rc.tried === 0 && rc.picked === 'E' && c.selected.length === 0 && rd.public === false && rd.listed === 1 && rd.tried === 0 && d.selected.length === 0, `${JSON.stringify(rc)} · ${JSON.stringify(rd)}`);
	}
	{
		const e = new FakePage(commsDesk(withheldCols(), { options: null }));
		const re = await pickPublicCommsEvent(e, { timeout: 200 });
		const f = commsApp({ P: 'op', X: 'op' }, ['P', 'X'], { answer: false });
		const rf = await pickPublicCommsEvent(f, { timeout: 150 });
		const g = commsApp({ P: 'op', X1: 'op', X2: 'op', X3: 'op' }, ['P', 'X1', 'X2', 'X3']);
		const rg = await pickPublicCommsEvent(g, { timeout: 500, max: 2 });
		ok('pickPublicCommsEvent: public null (the withheld fallback refused) with no <select>, a drafts box that never answers, or more events than it may try', re.public === null && e.selected.length === 0 && rf.public === null && rg.public === null && rg.tried === 2 && [re, rf, rg].every((r) => !commsFactsVerdict({ live: false, pick: r, ...read(commsDesk(withheldCols())) }).ok), `${JSON.stringify(re)} · ${JSON.stringify(rf)} · ${JSON.stringify(rg)}`);
	}
}

// ─── 9. defaultScreensDir ───────────────────────────────────────────────────

function screensDir() {
	const cases = [
		['http://127.0.0.1:5273', 'tests/artifacts/screens'],
		['http://localhost:5273/', 'tests/artifacts/screens'],
		['http://127.0.0.1:5401', 'tests/artifacts/screens-dev'],
		['http://127.0.0.1:5262', 'tests/artifacts/screens-dev'],
		['http://127.0.0.1:5199', 'tests/artifacts/screens-dev'],
		['http://127.0.0.1:52730', 'tests/artifacts/screens-dev'],
		['https://sajag.example', 'tests/artifacts/screens-dev'],
		['file:///tmp/x', 'tests/artifacts/screens-dev'],
		['not a url', 'tests/artifacts/screens-dev'],
		[undefined, 'tests/artifacts/screens-dev'],
	];
	const bad = cases.filter(([o, want]) => defaultScreensDir(o) !== want);
	ok('defaultScreensDir: only the live deck (:5273) defaults to the tracked tests/artifacts/screens; dev :5401, int3cl :5262 and any other origin → tests/artifacts/screens-dev', bad.length === 0, bad.map(([o]) => String(o)).join(', ') || `${cases.length} origins`);
	ok('isTrackedScreensDir', isTrackedScreensDir('tests/artifacts/screens') && isTrackedScreensDir('/x/services/command-deck/tests/artifacts/screens/') && !isTrackedScreensDir('tests/artifacts/screens-dev') && !isTrackedScreensDir('/tmp/evidence/UI-S7A/screens-x'));
}

// ─── run ────────────────────────────────────────────────────────────────────

export async function selfCheck() {
	textHelpers();
	copyPins();
	selectors();
	inPage();
	verdicts();
	await queueChecks();
	await labChecks();
	await pageHelpers();
	await moreHelpers();
	await cityCommandHelpers();
	await commsChecks();
	screensDir();
	console.log(failures ? `FAIL queue.mjs --self-check — ${failures} failure(s), ${passes} passed` : `ok   queue.mjs --self-check — all ${passes} checks passed (tolerant pins old + new, expandQueueItem, openIfCollapsed ×3, clear region + pick dismissal, the /comms verdict and pick, defaultScreensDir)`);
	return failures ? 1 : 0;
}
