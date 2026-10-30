/**
 * Alerts and the alert chime (V3-SPEC §7.3; user decision 26 Oct: the chime is ON by default, soft and
 * mutable).
 *
 * The bell keeps the last 50 alerts of this visit, newest first, with read state per browser
 * (localStorage `sajag.v3.alerts.read`). In P1 an alert is raised for one thing only: a decision unit that
 * STARTS waiting while the console is open. The first sync after a page load only primes the list (the
 * decisions already waiting are on the page in front of the officer — nothing chimes for them).
 *
 * THE CHIME RULE (decided here; `chimeAllowed` is the one place it lives, unit-tested):
 *   - the chime is on unless this browser turned it off (`sajag.v3.chime` = 'off');
 *   - it plays once per sync that brings at least one new waiting decision, never per alert (a burst of
 *     five new units is one chime);
 *   - a unit flagged EMULATED (or test) chimes only while the console declares that it runs on exercise
 *     data — the Exercise data tag in the top bar (commandBar.exercise) is that declaration. Without it an
 *     emulated unit still lands in the bell list, silently: the chime must never train officers to react
 *     to rehearsal traffic on a console that is not in an exercise.
 *   - the chime is a soft two-note sine (WebAudio, −24 dB, 0.5 s), no file, no network; a browser that
 *     blocks audio before the first interaction simply stays silent.
 *
 * Titles in the list are the unit's stored, MASKED title (never unmasked, whoever is on duty).
 */

export interface AlertItem {
	key: string;
	title: string;
	href: string;
	at: number;
	emulated: boolean;
}

export interface DecisionAlertInput {
	key: string;
	title: string;
	href: string;
	emulated: boolean;
}

const CHIME_KEY = 'sajag.v3.chime';
const READ_KEY = 'sajag.v3.alerts.read';
const MAX_ITEMS = 50;

/** May a sync that brought `fresh` units chime? Pure: the rule above. */
export function chimeAllowed(fresh: readonly { emulated: boolean }[], enabled: boolean, exerciseDeclared: boolean): boolean {
	if (!enabled || fresh.length === 0) return false;
	return fresh.some((u) => !u.emulated || exerciseDeclared);
}

function readStore(key: string): string | null {
	try {
		return localStorage.getItem(key);
	} catch {
		return null;
	}
}

function writeStore(key: string, value: string): void {
	try {
		localStorage.setItem(key, value);
	} catch {
		// storage unavailable (private mode): the choice holds for this visit
	}
}

class V3Alerts {
	items = $state<AlertItem[]>([]);
	chime = $state(true);
	read = $state<string[]>([]);
	/** Chimes played this visit (tests read it through the page hook). */
	played = $state(0);

	#seen = new Set<string>();
	#primed = false;
	#loaded = false;
	#ctx: AudioContext | null = null;

	get unread(): number {
		const r = new Set(this.read);
		return this.items.filter((i) => !r.has(i.key)).length;
	}

	/** Load the per-browser choices (once, in the browser). */
	load(): void {
		if (this.#loaded || typeof window === 'undefined') return;
		this.#loaded = true;
		this.chime = readStore(CHIME_KEY) !== 'off';
		try {
			const r = JSON.parse(readStore(READ_KEY) ?? '[]');
			if (Array.isArray(r)) this.read = r.filter((x): x is string => typeof x === 'string').slice(-MAX_ITEMS);
		} catch {
			this.read = [];
		}
	}

	setChime(on: boolean): void {
		this.chime = on;
		writeStore(CHIME_KEY, on ? 'on' : 'off');
		if (on) this.#unlock();
	}

	markAllRead(): void {
		const keys = new Set([...this.read, ...this.items.map((i) => i.key)]);
		this.read = [...keys].slice(-MAX_ITEMS);
		writeStore(READ_KEY, JSON.stringify(this.read));
	}

	/**
	 * The page's decision units (masked titles). The first call primes; later calls raise an alert for
	 * each unit not seen before and chime by the rule.
	 */
	syncDecisions(units: readonly DecisionAlertInput[], exerciseDeclared: boolean, now = Date.now()): void {
		if (!this.#primed) {
			for (const u of units) this.#seen.add(u.key);
			this.#primed = true;
			return;
		}
		const fresh = units.filter((u) => !this.#seen.has(u.key));
		if (!fresh.length) return;
		for (const u of fresh) this.#seen.add(u.key);
		this.items = [...fresh.map((u) => ({ key: u.key, title: u.title, href: u.href, at: now, emulated: u.emulated })), ...this.items].slice(0, MAX_ITEMS);
		if (chimeAllowed(fresh, this.chime, exerciseDeclared)) this.#play();
	}

	/** Forget the priming (a page that unmounts; the next page primes again). */
	reset(): void {
		this.#primed = false;
		this.#seen.clear();
	}

	/** Browsers allow audio after a user gesture: the shell calls this on the first pointer or key. */
	unlockAudio(): void {
		this.#unlock();
	}

	#unlock(): void {
		if (typeof window === 'undefined') return;
		try {
			const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
			if (!Ctx) return;
			this.#ctx ??= new Ctx();
			if (this.#ctx.state === 'suspended') void this.#ctx.resume().catch(() => {});
		} catch {
			this.#ctx = null;
		}
	}

	#play(): void {
		this.played++;
		this.#unlock();
		const ctx = this.#ctx;
		if (!ctx || ctx.state !== 'running') return;
		try {
			const t0 = ctx.currentTime + 0.02;
			// two soft notes, a fourth apart (E5 → A5), each with a gentle attack and a quick decay
			for (const [freq, at] of [
				[659.25, 0],
				[880, 0.16],
			] as const) {
				const osc = ctx.createOscillator();
				const gain = ctx.createGain();
				osc.type = 'sine';
				osc.frequency.value = freq;
				gain.gain.setValueAtTime(0, t0 + at);
				gain.gain.linearRampToValueAtTime(0.06, t0 + at + 0.02);
				gain.gain.exponentialRampToValueAtTime(0.0001, t0 + at + 0.34);
				osc.connect(gain).connect(ctx.destination);
				osc.start(t0 + at);
				osc.stop(t0 + at + 0.36);
			}
		} catch {
			// audio refused: the alert is still in the list
		}
	}
}

export const v3Alerts = new V3Alerts();
