/**
 * Where tests/screens-verify.mjs writes when it is given no output directory.
 *
 * `tests/artifacts/screens/` holds TRACKED evidence of record (the PNGs and
 * screens_manifest.json that the repo's release-consistency script reads),
 * regenerated only on the live deck (live gate LG 21). Only the live deck's
 * origin — port 5273 — may default there. Every other origin (a vite dev deck
 * such as :5401, a sandbox deck such as int3cl's :5262, a :5199 preview, an
 * unparseable origin) defaults to the untracked, gitignored
 * `tests/artifacts/screens-dev/`, and screens-verify says so. A WP always
 * passes its own evidence directory as the second argument anyway.
 *
 *   defaultScreensDir('http://127.0.0.1:5273')  → 'tests/artifacts/screens'
 *   defaultScreensDir('http://127.0.0.1:5401')  → 'tests/artifacts/screens-dev'
 *
 * The path is relative to services/command-deck.
 */

/** The live deck's port (sajag-command-deck). */
export const LIVE_DECK_PORT = '5273';
export const TRACKED_SCREENS_DIR = 'tests/artifacts/screens';
export const DEV_SCREENS_DIR = 'tests/artifacts/screens-dev';

/** The default output directory for `origin` (pure; never throws). */
export function defaultScreensDir(origin) {
	let port = null;
	try {
		const u = new URL(String(origin));
		if (u.protocol === 'http:' || u.protocol === 'https:') port = u.port || (u.protocol === 'https:' ? '443' : '80');
	} catch {
		port = null;
	}
	return port === LIVE_DECK_PORT ? TRACKED_SCREENS_DIR : DEV_SCREENS_DIR;
}

/**
 * True when `origin` is the live deck (port 5273) — the deck whose screens are
 * the evidence of record. Live-only rules key on this (screens-verify keeps
 * its live assertions there, e.g. /citizen must show an event card).
 */
export function isLiveDeckOrigin(origin) {
	return defaultScreensDir(origin) === TRACKED_SCREENS_DIR;
}

/** True when `dir` (relative to services/command-deck) is the tracked evidence of record. */
export function isTrackedScreensDir(dir) {
	return String(dir).replace(/\\/g, '/').replace(/\/+$/, '').endsWith(TRACKED_SCREENS_DIR);
}
