<script lang="ts">
	/**
	 * FusionRail — the bottom dock root (SPEC §5.3, §12.2; `fusion-rail`): the
	 * analysis dock of `$lib/analysis` in its standalone variant, with its own
	 * tabs (`data-bottom-tab`: Timeline, Audit, AI trace), its own size and
	 * the Live/Replay control (`replay-toggle`).
	 *
	 *   Timeline   the city feed (GET /api/v1/city/feed, hud/feed.svelte.ts)
	 *              as a histogram and seven lanes over a range, brushable;
	 *              Live ⇔ no time window (the workspace store's)
	 *   Audit      the same rows as an audit table: City or the selection;
	 *              a row click selects its object and flies the camera to it,
	 *              and the rows naming the selection stay marked
	 *   AI trace   the model rows, with phase, tier and confidence
	 *   Replay     one recorded emulator tape on its own (tape-time) axis
	 *              (ReplayBar), never mixed with live rows
	 *
	 * Today's /gods-eye mounts it in its glass rail; the redesigned pages use
	 * it as the bottom dock. `poll={false}` leaves the feed to whoever seeded
	 * it (the /design harness).
	 */
	import AnalysisDock from '$lib/analysis/dock/AnalysisDock.svelte';

	let { poll = true, replayBlocked = null, lang }: { poll?: boolean; replayBlocked?: string | null; lang?: string } = $props();
</script>

<AnalysisDock variant="standalone" {poll} {replayBlocked} {lang} />
