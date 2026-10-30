/**
 * Decision items, collapsible sections and tolerant text for the S7-owned
 * smokes (UI-S7A; contracts in .sajag-orchestration/impl/UI-S7A.md and plan X23).
 *
 * Today's /ops decision queue renders every card open, its buttons in view.
 * The redesign (SPEC §6.3, UI-S5A) renders each decision unit as a
 * collapsible item: a two-line row, and the ProposalCard inside the SAME
 * `queue-card` element, kept in the DOM with a `hidden` body while
 * collapsed. A smoke that clicks a button inside an item first calls
 * `expandQueueItem`, which is a no-op on today's always-open cards.
 *
 *   expandQueueItem(page, selector, {timeout = 4000})          → Promise<void>
 *       Resolves the item (and every queue-card containing it, outermost
 *       first); when its body is hidden, clicks its row toggle once and
 *       waits for the body. No-op when the item is absent or already open.
 *       The row toggle, in order: `[data-row-toggle]`; an element carrying
 *       `aria-expanded` outside the body; the prototype's
 *       `[data-action="qopen"]` row; `<summary>`; the item's first child that
 *       is not the body. "Collapsed" is read, in order, from the item's own
 *       `data-open` / `aria-expanded`, the toggle's `aria-expanded`, then
 *       whether its body (`[data-testid=proposal-card]` / `[data-prim=decision-card]`,
 *       else its own buttons) is laid out.
 *   openIfCollapsed(page, toggleSel, sectionSel, {timeout = 6000}) → Promise<boolean>
 *       Plan X23 (the /ops Lab section, UI-S5B): a no-op when `toggleSel`
 *       is absent (today's deck) or `${sectionSel}[data-open="true"]` is
 *       already present; otherwise ONE click on the toggle, then a wait for
 *       `${sectionSel}[data-open="true"]`. True when it clicked. `sectionSel`
 *       is one compound selector (no comma list).
 *   textIs(text, ...alternatives)   case- and whitespace-insensitive equality
 *                                   with any alternative (a RegExp alternative
 *                                   is tested against the whitespace-collapsed text)
 *   textMatches(text, re)           `re` against the whitespace-collapsed text
 *   textIsLoose(text, ...alts)      textIs that also ignores punctuation and
 *                                   symbols ('deterministic rule — no model'
 *                                   = 'Deterministic rule, no model')
 *   normText(text), looseText(text) the normalisers
 *
 *   node tests/lib/queue.mjs --self-check
 *       runs every tolerant matcher (tests/lib/tolerant.mjs), these helpers
 *       and tests/lib/screens-out.mjs against old and new sample copy and
 *       markup (today's Svelte markup and the redesign prototype's) over a
 *       minimal DOM (tests/lib/minidom.mjs) — no browser, no network.
 */

import { realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// ─── tolerant text ──────────────────────────────────────────────────────────

/** Lower-cased, whitespace-collapsed, trimmed text ('' for null/undefined). */
export function normText(text) {
	return String(text ?? '')
		.replace(/\s+/g, ' ')
		.trim()
		.toLowerCase();
}

/** normText without punctuation and symbols (·, —, -, :, comma, brackets …). */
export function looseText(text) {
	return normText(text)
		.replace(/[\p{P}\p{S}]+/gu, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

const collapsed = (text) => String(text ?? '').replace(/\s+/g, ' ').trim();

/** True when `text` equals any alternative, ignoring case and whitespace (a RegExp alternative is tested instead). */
export function textIs(text, ...alternatives) {
	const t = normText(text);
	return alternatives.flat().some((a) => (a instanceof RegExp ? testRe(a, collapsed(text)) : normText(a) === t));
}

/** True when `re` matches the whitespace-collapsed `text`. */
export function textMatches(text, re) {
	if (!(re instanceof RegExp)) throw new TypeError('textMatches(text, re): re must be a RegExp');
	return testRe(re, collapsed(text));
}

/** textIs, punctuation- and symbol-tolerant as well. */
export function textIsLoose(text, ...alternatives) {
	const t = looseText(text);
	return alternatives.flat().some((a) => (a instanceof RegExp ? testRe(a, collapsed(text)) : looseText(a) === t));
}

function testRe(re, s) {
	re.lastIndex = 0; // a /g or /y regex keeps state between calls
	return re.test(s);
}

// ─── queue items ────────────────────────────────────────────────────────────

/**
 * In-page (serialised by puppeteer, so self-contained): the collapse state of
 * `item` and of every queue-card that contains it. `depth` is the outermost
 * collapsed container (0 = the item itself, 1 = its queue-card parent …).
 */
export function queueItemState(item) {
	const QC = '[data-testid="queue-card"]';
	const BODY = '[data-testid="proposal-card"], [data-prim="decision-card"]';
	const shown = (n) => n.getClientRects().length > 0;
	const own = (c, n) => n.closest(QC) === c;
	const toggleOf = (c) => {
		const rt = [...c.querySelectorAll('[data-row-toggle]')].find((n) => own(c, n));
		if (rt) return rt;
		return [...c.querySelectorAll('[aria-expanded]')].find((n) => own(c, n) && !n.closest(BODY)) ?? null;
	};
	const isOpen = (c) => {
		if (c.hasAttribute('data-open')) return c.getAttribute('data-open') !== 'false';
		if (c.hasAttribute('aria-expanded')) return c.getAttribute('aria-expanded') !== 'false';
		const t = toggleOf(c);
		if (t && t.hasAttribute('aria-expanded')) return t.getAttribute('aria-expanded') !== 'false';
		const bodies = [...c.querySelectorAll(BODY)].filter((b) => own(c, b));
		if (bodies.length) return bodies.some(shown);
		const buttons = [...c.querySelectorAll('button')].filter((b) => own(c, b) && b !== t);
		if (buttons.length) return buttons.some(shown);
		return true; // nothing to reveal
	};
	const chain = [];
	for (let n = item; n; n = n.parentElement ? n.parentElement.closest(QC) : null) chain.push(n);
	for (let d = chain.length - 1; d >= 0; d--) {
		if (!isOpen(chain[d])) return { collapsed: true, depth: d, reason: chain[d].hasAttribute('data-open') ? 'data-open' : 'body hidden' };
	}
	return { collapsed: false, depth: -1, reason: 'open' };
}

/** In-page (self-contained): the row toggle of the container `depth` levels above `item` (0 = the item). */
export function queueItemToggle(item, depth) {
	const QC = '[data-testid="queue-card"]';
	const BODY = '[data-testid="proposal-card"], [data-prim="decision-card"]';
	const shown = (n) => n.getClientRects().length > 0;
	let c = item;
	for (let i = 0; i < depth && c; i++) c = c.parentElement ? c.parentElement.closest(QC) : null;
	if (!c) return null;
	const own = (n) => n.closest(QC) === c;
	const usable = (n) => own(n) && shown(n);
	const pick = (sel, extra = () => true) => [...c.querySelectorAll(sel)].find((n) => usable(n) && extra(n)) ?? null;
	return (
		pick('[data-row-toggle]') ??
		pick('[aria-expanded]', (n) => !n.closest(BODY)) ??
		pick('[data-action="qopen"]') ??
		pick('summary') ??
		[...c.children].find((n) => shown(n) && !n.matches(BODY) && !n.querySelector(BODY)) ??
		(shown(c) ? c : null)
	);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Expand the decision item at `selector` (and any collapsed queue-card around
 * it) before its buttons are clicked. A no-op on today's always-open cards and
 * when the item is absent (the caller's button lookup reports that).
 */
export async function expandQueueItem(page, selector, { timeout = 4000 } = {}) {
	for (let round = 0; round < 4; round++) {
		const item = await page.$(selector);
		if (!item) return;
		const state = await item.evaluate(queueItemState);
		if (!state.collapsed) return;
		const handle = await item.evaluateHandle(queueItemToggle, state.depth);
		const toggle = handle.asElement ? handle.asElement() : handle;
		if (!toggle) throw new Error(`expandQueueItem: ${selector} is collapsed (${state.reason}) but has no row toggle`);
		await toggle.click();
		const deadline = Date.now() + timeout;
		let now = state;
		while (Date.now() < deadline) {
			const el = await page.$(selector);
			now = el ? await el.evaluate(queueItemState) : { collapsed: false, depth: -1 };
			if (!now.collapsed || now.depth < state.depth) break;
			await sleep(100);
		}
		if (now.collapsed && now.depth >= state.depth) throw new Error(`expandQueueItem: ${selector} did not expand within ${timeout} ms`);
	}
}

// ─── collapsible sections (plan X23) ────────────────────────────────────────

/**
 * Open a collapsible section before its controls are used: a no-op when the
 * toggle is absent (today's deck) or the section is already open; otherwise
 * one click on the toggle and a wait for `${sectionSel}[data-open="true"]`.
 * Resolves true when it clicked.
 */
export async function openIfCollapsed(page, toggleSel, sectionSel, { timeout = 6000 } = {}) {
	const toggle = await page.$(toggleSel);
	if (!toggle) return false;
	if (await page.$(`${sectionSel}[data-open="true"]`)) return false;
	await toggle.click();
	await page.waitForSelector(`${sectionSel}[data-open="true"]`, { timeout });
	return true;
}

// ─── --self-check ───────────────────────────────────────────────────────────

// No top-level await here: self-check.mjs imports this module, and a pending
// top-level await on that cycle would deadlock (node exits 13).
if (process.argv[1] && fileURLToPath(import.meta.url) === realpathSync(process.argv[1]) && process.argv.includes('--self-check')) {
	import('./self-check.mjs')
		.then(({ selfCheck }) => selfCheck())
		.then(
			(code) => process.exit(code),
			(err) => {
				console.error(`FAIL queue.mjs --self-check — harness error: ${err?.stack ?? err}`);
				process.exit(1);
			},
		);
}
