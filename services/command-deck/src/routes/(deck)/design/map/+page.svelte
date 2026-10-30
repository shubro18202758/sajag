<script lang="ts">
	/**
	 * /design/map — the map-chrome harness (plan R18, X16; dev only, not in
	 * navigation; UI-S7B deletes it). GodsEyeCanvas with chrome="v2" against
	 * whatever backend serves this deck (the sandbox for a dev deck), so the
	 * redesign's map chrome and symbology can be seen and screenshotted
	 * before a route opts in (S5B /ops, S6A / and /gods-eye).
	 *
	 * URL state:
	 *   ?legacy=1              the legacy chrome (the invariance comparison)
	 *   ?window=HHMM-HHMM      a time window in IST (the latest such span):
	 *                          time-bearing objects outside it fade, protected
	 *                          ones never do
	 *   ?sel=<urn>             select (and fly to) an object once the city answers
	 *   ?mode=map              map mode: full bleed, "Exit map mode" in the toolbar
	 *   ?dock=1                the LayerTree in a page dock (the canvas's onLayers)
	 *   ?kinds=camera,vehicle  a kind filter
	 *
	 * The page computes the protected set the way the workspace will (SPEC
	 * §7.3): the active movement's convoy and route, every open pursuit and
	 * its vehicle, every object with a waiting decision, every watchlisted
	 * vehicle read in the last 30 min. The canvas mounts the one omnibar
	 * (hud 'full', plan X25); this page mounts none.
	 */
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import GodsEyeCanvas from '$lib/gods-eye/GodsEyeCanvas.svelte';
	import LayerTree from '$lib/gods-eye/hud/map/LayerTree.svelte';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { parseUrn } from '$lib/gods-eye/city-api';
	import { decisionUrns, stolenVehicles } from '$lib/gods-eye/layers/enforcement';
	import { ops } from '$lib/ops/store.svelte';
	import { commandBar, resetCommandBar } from '$lib/shell/command-bar.svelte';
	import { provideUiLang } from '$lib/ui';
	import Tag from '$lib/ui/Tag.svelte';
	import { fmtRange } from '$lib/ui/format/format';

	const IST_OFFSET_MS = 330 * 60_000;
	const LIVE_READ_MS = 30 * 60_000;

	const q = $derived(page.url.searchParams);
	const legacy = $derived(q.get('legacy') === '1');
	const mapMode = $derived(q.get('mode') === 'map');
	const docked = $derived(q.get('dock') === '1');
	const selParam = $derived(q.get('sel'));

	/** "0120-0142" → the latest such IST span that has begun, as epoch ms. */
	function parseWindow(raw: string | null): readonly [number, number] | null {
		const m = raw ? /^(\d{2})(\d{2})-(\d{2})(\d{2})$/.exec(raw) : null;
		if (!m) return null;
		const [h0, m0, h1, m1] = m.slice(1).map(Number);
		if (h0 > 23 || h1 > 23 || m0 > 59 || m1 > 59) return null;
		const nowIst = new Date(Date.now() + IST_OFFSET_MS);
		const day = Date.UTC(nowIst.getUTCFullYear(), nowIst.getUTCMonth(), nowIst.getUTCDate());
		let a = day + (h0 * 60 + m0) * 60_000 - IST_OFFSET_MS;
		let b = day + (h1 * 60 + m1) * 60_000 - IST_OFFSET_MS;
		if (b <= a) b += 86_400_000;
		if (a > Date.now()) {
			a -= 86_400_000;
			b -= 86_400_000;
		}
		return [a, b];
	}

	const timeWindow = $derived(parseWindow(q.get('window')));
	const kindFilter = $derived.by(() => {
		const raw = q.get('kinds');
		return raw ? new Set(raw.split(',').map((k) => k.trim()).filter(Boolean)) : null;
	});

	/** SPEC §7.3: the objects a window, a filter or a dimming never hides. */
	const protectedSet = $derived.by(() => {
		void cityRegistry.version;
		const out = new Set<string>();
		for (const c of cityRegistry.byKind('convoy')) out.add(c.urn);
		for (const e of cityRegistry.byKind('event')) {
			const open = e.state !== 'completed' && e.state !== 'cancelled';
			const kind = e.props.event_kind;
			if (!open || (kind !== 'vehicle_pursuit' && kind !== 'protected_movement')) continue;
			out.add(e.urn);
			const meta = (e.props.metadata ?? {}) as Record<string, unknown>;
			if (typeof meta.vehicle_id === 'string') out.add(`vehicle:${meta.vehicle_id}`);
		}
		for (const urn of decisionUrns(cityRegistry.byKind('recommendation'), stolenVehicles())) out.add(urn);
		for (const d of cityRegistry.byKind('dispatch')) if (d.state === 'requested') out.add(d.urn);
		// a vehicle with a WATCHLIST read in the last 30 min: an active earmark (watch, flagged, a lawful basis) or a
		// read that hit a list — not every vehicle the registry carries (an ended earmark keeps its row)
		const now = Date.now();
		for (const v of cityRegistry.byKind('vehicle')) {
			const earmark = v.props.earmark_state ?? v.state;
			const watchlisted = earmark === 'watch' || earmark === 'flagged' || typeof v.props.lawful_basis === 'string' || typeof v.props.matched_plate_hit === 'string';
			if (watchlisted && v.t != null && now - v.t <= LIVE_READ_MS) out.add(v.urn);
		}
		return out;
	});

	let selectionItems = $state<string[] | null>(null);

	/** A shape or Search around: the page owns the multi-selection (selectMany once the workspace provides it). */
	function onlasso(urns: string[]) {
		const multi = selection as unknown as { selectMany?: (u: string[], o: { source: string }) => void };
		if (typeof multi.selectMany === 'function') multi.selectMany(urns, { source: 'lasso' });
		else if (urns[0] && parseUrn(urns[0])) selection.select(urns[0], { fly: false, source: 'map' });
		selectionItems = urns;
	}

	$effect(() => {
		// a new primary selection made elsewhere ends the lasso's multi-selection
		const cur = selection.current;
		if (selectionItems && cur && !selectionItems.includes(cur)) selectionItems = null;
		if (!cur) selectionItems = null;
	});

	let dockOpen = $state(false);
	let selApplied = false;

	$effect(() => {
		const want = selParam;
		if (!want || selApplied || cityRegistry.status !== 'ok' || !parseUrn(want)) return;
		selApplied = true;
		selection.select(want, { fly: true, source: 'share' });
	});

	function exitMapMode() {
		const url = new URL(page.url);
		url.searchParams.delete('mode');
		void goto(`${url.pathname}${url.search}${url.hash}`, { replaceState: true, noScroll: true, keepFocus: true });
	}

	onMount(() => {
		commandBar.lang = ops.lang;
		commandBar.onLangChange = (l: string) => (ops.lang = l);
		return () => resetCommandBar();
	});
	$effect(() => {
		commandBar.lang = ops.lang;
	});
	provideUiLang(() => ops.lang);
</script>

<svelte:head><title>Map harness · Sajag</title></svelte:head>

<div class="harness" class:map-mode={mapMode} data-harness="map" data-chrome={legacy ? 'legacy' : 'v2'}>
	{#if !mapMode}
		<header class="pane-head">
			<span class="title">City map</span>
			<Tag>{legacy ? 'Legacy chrome' : 'Chrome v2'}</Tag>
			{#if timeWindow}<Tag>Window {fmtRange(timeWindow[0], timeWindow[1])} IST · faded outside</Tag>{/if}
			<span class="grow"></span>
			<span class="note">Map harness · sandbox data · not in navigation</span>
		</header>
	{/if}
	<div class="body">
		{#if docked && dockOpen && !legacy}
			<aside class="dock" data-dock="left" data-open="true"><LayerTree lang={ops.lang} onclose={() => (dockOpen = false)} /></aside>
		{/if}
		<div class="map" data-pane="map">
			{#key legacy}
				<GodsEyeCanvas
					hud="full"
					chrome={legacy ? 'legacy' : 'v2'}
					onexit={mapMode ? exitMapMode : undefined}
					{timeWindow}
					protected={protectedSet}
					{kindFilter}
					{selectionItems}
					idleOrbit={false}
					onLayers={docked ? () => (dockOpen = !dockOpen) : undefined}
					{onlasso}
				/>
			{/key}
		</div>
	</div>
</div>

<style>
	.harness {
		display: flex;
		flex-direction: column;
		/* V3-P6B: the page fills the frame the V3 shell gives it (the v2 navbar's 50 px is gone) */
		height: 100%;
		min-height: 480px;
		background: var(--v-canvas);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.pane-head {
		display: flex;
		align-items: center;
		gap: 8px;
		height: 40px;
		padding: 0 12px 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
		flex: 0 0 auto;
	}

	.title {
		font-size: var(--v-text-base);
		font-weight: 600;
	}

	.grow {
		flex: 1 1 auto;
	}

	.note {
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.body {
		display: flex;
		flex: 1 1 auto;
		min-height: 0;
	}

	.dock {
		display: flex;
		flex-direction: column;
		width: 300px;
		flex: 0 0 auto;
		border-right: 1px solid var(--v-line-2);
		min-height: 0;
	}

	.dock > :global(*) {
		flex: 1 1 auto;
		min-height: 0;
	}

	.map {
		position: relative;
		flex: 1 1 auto;
		min-width: 0;
		min-height: 0;
	}

	.map :global(.ge-wrap) {
		border-radius: 0;
	}
</style>
