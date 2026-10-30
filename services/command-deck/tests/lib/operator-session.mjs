/**
 * The deck smokes' handle on the operator PIN gate: the one shared helper in scripts/lib/deck_session.mjs
 * (reads the PIN at runtime, one sign-in attempt, never logs it).
 *
 *   import { signIn, puppeteerCookies } from './lib/operator-session.mjs';
 *   const session = await signIn(origin, 'Gods-eye smoke (automated check)');
 *   await page.setCookie(...puppeteerCookies(session));
 *
 * The duty-officer field (C6: a named officer unmasks registration marks and is recorded with each decision)
 * is found by TEST ID, never by its container: today it is the /ops masthead's `duty-officer` (and the
 * City Command dossier's `dossier-officer`, the cockpit planner's `planner-officer`); the redesign moves it
 * to the navbar's `duty-officer` input (SPEC §5.3, §12.2; plan X12), which stays an input when a name is set.
 *
 *   const sel = await nameOfficer(page, 'Duty Officer A', { prefer: ['duty-officer', 'dossier-officer'] });
 */
export { readPin, signIn, deckFetch, puppeteerCookies, signOut } from '../../../../scripts/lib/deck_session.mjs';

/** The order the smokes look for an officer field in, unless they say otherwise. */
export const OFFICER_FIELDS = ['duty-officer', 'dossier-officer', 'planner-officer'];

/**
 * The selector of the first officer FIELD in `prefer` that this page renders, or null. Only an
 * editable element counts — an <input> or <textarea> carrying the test id — so an id that names a
 * note or a tag (ConvoyHud's `convoy-hud-proposal-officer` is a <p>) is never typed into in silence.
 */
export async function officerField(page, prefer = OFFICER_FIELDS) {
	for (const id of prefer) {
		for (const tag of ['input', 'textarea']) {
			const sel = `${tag}[data-testid="${id}"]`;
			if (await page.$(sel)) return sel;
		}
	}
	return null;
}

/** Type `name` into the page's officer field (the first of `prefer` present); returns the selector used. */
export async function nameOfficer(page, name, { prefer = OFFICER_FIELDS, delay = 4 } = {}) {
	const sel = await officerField(page, prefer);
	if (!sel) throw new Error(`no editable duty-officer field (an input or textarea with test id ${prefer.join(', ')}) on this page`);
	await page.type(sel, name, { delay });
	return sel;
}

/** The value of the page's officer field (the first of `prefer` present), '' when there is none. */
export async function officerValue(page, prefer = OFFICER_FIELDS) {
	const sel = await officerField(page, prefer);
	return sel ? page.$eval(sel, (el) => el.value ?? '') : '';
}
