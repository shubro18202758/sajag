/**
 * The deck proxy's limits (src/hooks.server.ts), pure enough to unit-test
 * (tests/deck-fixes.unit.mjs): the per-path upstream budget (F-CONN-05) and
 * the client-abort watch (F-CONN-04).
 */

/**
 * The upstream time budget of one proxied request (F-CONN-05). Brain
 * workflows are heavyweight by design (the pre-movement plan runs the
 * decider checkpoint + corridor assessment + Gemma narration — the original
 * template budgeted a 5-minute axios timeout for exactly this call). The
 * oracle's long computations — the twin run, the twin comparison and a
 * decision-support generation — are waited on by the deck for 120 s
 * (ops/client.ts), so the proxy gives them 130 s: a 60 s proxy cut them off
 * while the client still waited. Everything else keeps the 60 s budget.
 */
export const PROXY_BUDGET_MS = { brain: 300_000, long: 130_000, default: 60_000 } as const;
const LONG_ORACLE_PATHS = [/^\/api\/v1\/simulate\/twin(?:\/compare)?\/?$/, /^\/api\/v1\/decision-support\/[^/]+\/generate\/?$/];

export function proxyBudgetMs(prefix: string, pathname: string): number {
	if (prefix === '/api/convoy') return PROXY_BUDGET_MS.brain;
	if (LONG_ORACLE_PATHS.some((re) => re.test(pathname))) return PROXY_BUDGET_MS.long;
	return PROXY_BUDGET_MS.default;
}

/**
 * A signal that aborts when the client goes away (F-CONN-04). The adapter's
 * own request signal fires only while a request BODY is still arriving, so
 * the connection is watched too (adapter-node hands the IncomingMessage over
 * as platform.req): its socket closing means nobody will read the answer.
 * `release` stops the watch (a keep-alive socket serves later requests).
 */
export function clientAbort(event: { request: Request; platform?: unknown }): { signal: AbortSignal; release: () => void } {
	const ac = new AbortController();
	const abort = () => ac.abort(new DOMException('the client went away', 'AbortError'));
	if (event.request.signal.aborted) abort();
	else event.request.signal.addEventListener('abort', abort, { once: true });
	const req = (event.platform as { req?: { socket?: { destroyed?: boolean; once?: (e: string, f: () => void) => void; off?: (e: string, f: () => void) => void } } } | undefined)?.req;
	const socket = req?.socket;
	if (socket?.destroyed) abort();
	else socket?.once?.('close', abort);
	return {
		signal: ac.signal,
		release: () => {
			socket?.off?.('close', abort);
			event.request.signal.removeEventListener('abort', abort);
		},
	};
}
