/**
 * The shell's one 1 Hz wall clock: the LiveStrip's IST clock and countdown and
 * the band tag's ticking age read it. A single interval, started by the first
 * reader and stopped with the last one (ref-counted from component effects).
 *
 *   $effect(() => useShellClock());   // subscribe while mounted
 *   shellClock.now                    // epoch ms, updated every second
 */
export const shellClock = $state({ now: Date.now() });

let users = 0;
let timer: ReturnType<typeof setInterval> | null = null;

function align(): void {
	shellClock.now = Date.now();
}

/** Subscribe to the clock; returns the unsubscribe (an $effect teardown). */
export function useShellClock(): () => void {
	users += 1;
	if (!timer && typeof setInterval === 'function') {
		align();
		timer = setInterval(align, 1000);
	}
	return () => {
		users -= 1;
		if (users <= 0 && timer) {
			clearInterval(timer);
			timer = null;
			users = 0;
		}
	};
}
