<script lang="ts">
	/**
	 * The City map tile of the wall (SPEC §6.3 col 2): God's-eye with the v2
	 * chrome in the `.ge-wrap` the canvas renders, `hud="wall"` (its omnibar
	 * is the page's only one, plan X25), at least 420 px tall; it orbits
	 * after 30 s idle only while nothing is selected. Below it a compact
	 * legend strip says what the few hues mean (SPEC §1.4) and that the map
	 * shows vehicles only. "Open in workspace" carries the selection to `/`
	 * in a share hash (URNs only, never a mark): the operator's pick, else
	 * the object the docked inspector shows (`focusUrn`).
	 *
	 * The toolbar's Mode chip ("Live") opens the workspace's timeline: the
	 * wall's map is always live, and setting a window or playing a replay is
	 * the workspace's job (SPEC §7.4), so the chip goes to `/` with the same
	 * selection and the bottom dock open on the Timeline tab.
	 *
	 * `timeWindow` is deliberately not passed: the header range scopes the
	 * band chart and the closed event lists only, never the live map
	 * (a window on the wall's map would hide live vehicles from the duty
	 * officer and turn its Mode chip to "Not live").
	 */
	import { goto } from '$app/navigation';
	import { ACTION_ICON } from '$lib/design/icons';
	import { Button, Icon, Section } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import GodsEyeCanvas from '$lib/gods-eye/GodsEyeCanvas.svelte';
	import { buildShareHash } from '$lib/gods-eye/share-link';
	import { GODS_EYE_LAYER_IDS } from '$lib/gods-eye/layers';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { selectors } from '$lib/workspace/world.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { WORKSPACE_URL } from '$lib/shell/root-flip';
	import { WALL_VIEW, carriedUrn } from './share';

	interface Props {
		lang: string;
		/** The traffic flow is a simulated feed (the legend says so). */
		simulatedFlow: boolean;
		/** The object the page shows without an operator pick (the docked inspector's): carried when nothing is selected. */
		focusUrn?: string | null;
	}

	let { lang, simulatedFlow, focusUrn = null }: Props = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	/** SPEC §7.3: objects a window, a filter or a dimming never hides (the canonical selector). */
	const protectedSet = $derived(selectors.protectedUrns());
	const items = $derived(selection.items.length > 1 ? selection.items : null);

	function onlasso(urns: string[]) {
		selection.selectMany(urns, { source: 'lasso' });
	}

	function openInWorkspace() {
		const hash = buildShareHash({ ...WALL_VIEW, selected: carriedUrn(selection.current, focusUrn) }, GODS_EYE_LAYER_IDS);
		void goto(`${WORKSPACE_URL}#${hash}`);
	}

	/** The Mode chip: the workspace's timeline (a window or a replay is set there), with the same selection. */
	function openTimeline() {
		workspace.bottomTab = 'timeline';
		if (workspace.docks.bottom === 'off') workspace.setBottom('compact');
		openInWorkspace();
	}
</script>

{#snippet right()}
	<Button minimal small icon="maximize" tooltip={L('wall_open_workspace_tip')} onclick={openInWorkspace}>{L('wall_open_workspace')}</Button>
{/snippet}

<Section title={L('wall_city')} icon="map" level={2} {right} data-prim="panel" data-wall="city">
	<div class="tile">
		<GodsEyeCanvas hud="wall" chrome="v2" idleOrbit protected={protectedSet} selectionItems={items} {onlasso} onTimeline={openTimeline} />
	</div>
	<div class="legend" aria-label={L('wall_legend')}>
		<span class="item"><Icon name="shield" size={12} />{L('wall_legend_vehicles')}</span>
		<span class="item"><i class="dot decision" aria-hidden="true"></i>{L('wall_legend_decision')}</span>
		<span class="item"><i class="dot alert" aria-hidden="true"></i>{L('wall_legend_watch')}</span>
		<span class="item"><i class="line route" aria-hidden="true"></i>{L('wall_legend_route')}</span>
		<span class="item"><i class="line event" aria-hidden="true"></i>{L('wall_legend_event')}</span>
		{#if simulatedFlow}<span class="item"><Icon name={ACTION_ICON.simulated} size={12} />{L('wall_legend_simulated')}</span>{/if}
		<!-- the anomaly diamonds flag the FEED, not the road (the metric tile says the same) -->
		<span class="item"><i class="dot anomaly" aria-hidden="true"></i>{L('wall_legend_anomalies')}</span>
	</div>
</Section>

<style>
	/* 420 px (SPEC §6.3; canvas-ux pins ≥ 400): a taller tile pushes Corridor operations below the fold */
	.tile {
		position: relative;
		display: flex;
		height: 420px;
		min-width: 0;
		background: var(--v-canvas);
	}

	.tile > :global(.ge-wrap) {
		flex: 1 1 auto;
		min-width: 0;
		border-radius: 0;
	}

	/* items that do not fit wrap onto a hidden second line: never a word cut in half */
	.legend {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		column-gap: 16px;
		min-width: 0;
		/* the legend wraps to a second row rather than hiding an entry ("Simulated flow" and "Corridor event" were cut off) */
		min-height: 28px;
		padding: 4px 16px;
		row-gap: 2px;
		border-top: 1px solid var(--v-line-1);
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		white-space: nowrap;
	}

	.item {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 6px;
		height: 28px;
	}

	.dot {
		display: inline-block;
		width: 9px;
		height: 9px;
		border-radius: 50%;
		box-sizing: border-box;
	}

	.dot.decision {
		background: var(--v-map-decision);
	}

	.dot.alert {
		border: 2px solid var(--v-map-alert);
	}

	/* the map's anomaly mark: a small neutral diamond */
	.dot.anomaly {
		width: 7px;
		height: 7px;
		border-radius: 1px;
		transform: rotate(45deg);
		background: var(--v-ink-3);
	}

	.line {
		display: inline-block;
		width: 14px;
		height: 3px;
		border-radius: 1px;
	}

	.line.route {
		background: var(--v-map-route);
	}

	.line.event {
		background: var(--v-map-event);
	}
</style>
