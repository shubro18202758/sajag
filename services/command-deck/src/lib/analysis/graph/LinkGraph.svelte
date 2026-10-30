<script lang="ts">
	/**
	 * LinkGraph (SPEC §5.3 "LinkGraph [S4]", §8.3) — the focus object and its
	 * links, laid out radially by link type (graph.ts, layout.ts).
	 *
	 * - Nodes are a neutral ring with the type glyph (focus 20 px, cameras 14,
	 *   reads and recommendations 8–9); state is a dot (orange pending, green
	 *   approved) or a red ring (watchlisted or stolen); the selection is a
	 *   blue ring with a halo.
	 * - More than 8 links of one type to one node merge into one node with a
	 *   count ("14 rejected"); Expand merged reverses it.
	 * - Edges are 1 px neutral with arrows; an invisible 9 px hit line names
	 *   the link type on hover. Only edges touching a selected non-focus node
	 *   are highlighted.
	 * - Labels are drawn last, with a 4 px canvas halo, by greedy collision
	 *   avoidance (layout.ts): priority focus, selection, merged nodes,
	 *   events, cameras; satellites only when selected.
	 * - The toolbar is its own 40 px bar: Search around ▾ (one link type at a
	 *   time), Find paths (needs exactly two selected objects), Expand merged,
	 *   Layout ▾ (radial, force, hierarchical), Fit; the stats "51 linked ·
	 *   14 merged".
	 * - Click selects (replace); Shift-click adds; Ctrl/Cmd-click toggles.
	 * - SVG up to 300 nodes, Canvas2D beyond; the layout runs synchronously up
	 *   to 80 nodes, else in a blob: worker, cached per focus and filter set;
	 *   it runs again on resize and on Fit.
	 */
	import { untrack } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.analysis';
	import { Button, Icon, Menu, NonIdealState, Popover } from '$lib/ui';
	import { fmtStamp, svgLabel } from '$lib/ui/format/format';
	import { ACTION_ICON, iconPaths } from '$lib/design/icons';
	import type { MenuItemSpec } from '$lib/ui';
	import { canvasFont, cssVar } from '$lib/gods-eye/theme';
	import { kindOne, stateWord } from '$lib/workspace/kinds/generic';
	import { liveWorld, selectors } from '$lib/workspace/world.svelte';
	import { buildGraph, findPath, linkTypes, type GNode, type GraphSource } from './graph';
	import type { LayoutMode, LayoutOut } from './layout';
	import { clearLayoutCache, layoutGraph } from './worker';

	interface Props {
		focus: string;
		selectionItems: readonly string[];
		layout: LayoutMode;
		onselect(urn: string, mode: 'replace' | 'add' | 'toggle'): void;
		/** The object model (default: the live world's). */
		graph?: GraphSource;
		/** The workspace's time window: objects outside it fade (protected ones never). */
		window?: readonly [number, number] | null;
		/** The layout control changed the layout. */
		onlayout?: (mode: LayoutMode) => void;
		lang?: string;
		[k: string]: unknown;
	}

	let { focus, selectionItems, layout, onselect, graph, window: win = null, onlayout, lang = 'en', ...rest }: Props = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	/** SVG up to this many nodes; Canvas2D beyond. */
	const SVG_MAX = 300;

	let mode = $state<LayoutMode>('radial');
	$effect(() => {
		mode = layout;
	});
	let expandMerged = $state(false);
	let expansions = $state.raw<Map<string, Set<string>>>(new Map());
	let path = $state.raw<string[] | null>(null);
	let pathNote = $state<string | null>(null);
	let fitSeq = $state(0);

	// a new focus starts clean
	let lastFocus = '';
	$effect(() => {
		if (focus === lastFocus) return;
		lastFocus = focus;
		untrack(() => {
			expansions = new Map();
			path = null;
			pathNote = null;
		});
	});

	const src = $derived<GraphSource>(graph ?? liveWorld.graph());
	const model = $derived(
		focus
			? buildGraph(src, focus, {
					lang,
					expandMerged,
					keep: selectionItems,
					expansions,
					paths: path ? [path] : [],
				})
			: null,
	);

	// ── layout (cached per focus and filter set; again on resize and Fit) ──
	let W = $state(0);
	let H = $state(0);
	let out = $state.raw<LayoutOut | null>(null);
	let busy = $state(false);
	let via = $state('');
	let token = 0;

	function signature(): string {
		if (!model) return '';
		let h = 2166136261;
		for (const n of model.nodes) {
			const s = `${n.id}|${n.role}|${n.parent ?? ''}|${n.order}|${n.labelW}|${n.wantLabel ? 1 : 0}|${n.priority};`;
			for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
		}
		return `${model.focus}|${model.nodes.length}|${(h >>> 0).toString(36)}`;
	}

	const sig = $derived(signature());

	$effect(() => {
		const m = model;
		const w = Math.round(W);
		const h = Math.round(H);
		const key = `${sig}|${mode}|${w}x${h}|${fitSeq}`;
		if (!m || w < 120 || h < 120) return;
		const my = ++token;
		busy = m.nodes.length > 80;
		const t0 = performance.now();
		void layoutGraph({
			key,
			mode,
			W: w,
			H: h,
			focus: m.focus,
			nodes: m.nodes.map((n) => ({ id: n.id, role: n.role, parent: n.parent, r: n.r, order: n.order, labelW: n.labelW, shortW: n.shortW, wantLabel: n.wantLabel, priority: n.priority })),
			edges: m.edges.map((e) => ({ a: e.a, b: e.b })),
		}).then((ans) => {
			if (my !== token) return;
			out = ans.out;
			via = ans.via;
			busy = false;
			const total = performance.now() - t0;
			if (typeof window !== 'undefined') {
				(window as unknown as Record<string, unknown>).__LINK_GRAPH__ = { nodes: m.nodes.length, edges: m.edges.length, mode, via: ans.via, layoutMs: Math.round(ans.out.ms * 100) / 100, endToEndMs: Math.round(total * 100) / 100, labels: Object.keys(ans.out.labels).length, W: w, H: h };
			}
		});
	});

	function fit() {
		clearLayoutCache();
		fitSeq++;
	}

	// ── selection, dimming, the window ───────────────────────────────────
	const selSet = $derived(new Set(selectionItems));
	const selOther = $derived(selectionItems.filter((u) => u !== focus));
	const near = $derived.by(() => {
		if (!model || !selOther.length) return null;
		const s = new Set<string>([model.focus, ...selOther]);
		for (const e of model.edges) {
			if (selSet.has(e.a)) s.add(e.b);
			if (selSet.has(e.b)) s.add(e.a);
		}
		return s;
	});
	const faded = (n: GNode) => !!win && !!n.row && !selectors.inWindow(n.row, win);

	function pick(n: GNode, e: MouseEvent) {
		if (n.agg) {
			expandMerged = true;
			return;
		}
		if (!n.urn) return;
		const m = e.shiftKey ? 'add' : e.ctrlKey || e.metaKey ? 'toggle' : 'replace';
		onselect(n.urn, m);
	}

	// ── toolbar ───────────────────────────────────────────────────────────
	const subject = $derived(selOther.length ? selOther[selOther.length - 1] : focus);
	const subjectLabel = $derived(model?.nodes.find((n) => n.id === subject)?.labelText ?? subject);
	const present = $derived(new Set(model?.nodes.map((n) => n.id) ?? []));
	const typeItems = $derived.by((): MenuItemSpec[] => {
		if (!model) return [];
		const types = linkTypes(src, subject, present, lang);
		const have = expansions.get(subject) ?? new Set<string>();
		const head: MenuItemSpec = { id: 'h', kind: 'header', label: L('an_g_search_from', subjectLabel) };
		if (!types.length) return [head, { id: 'none', label: L('an_g_search_none'), disabled: true }];
		return [
			head,
			...types.map((ty) => ({
				id: `rel:${ty.relation}`,
				label: ty.label,
				icon: 'search-around' as const,
				rightLabel: ty.added >= ty.count || have.has(ty.relation) ? `${ty.count} ${L('an_g_search_added')}` : String(ty.count),
				disabled: ty.added >= ty.count || have.has(ty.relation),
				onclick: () => {
					const next = new Map(expansions);
					next.set(subject, new Set([...(next.get(subject) ?? []), ty.relation]));
					expansions = next;
				},
			})),
		];
	});
	const layoutItems = $derived<MenuItemSpec[]>(
		(['radial', 'force', 'hierarchical'] as const).map((m) => ({
			id: `layout:${m}`,
			label: L(`an_g_layout_${m}`),
			icon: m === 'radial' ? ('layout-circle' as const) : m === 'force' ? ('graph' as const) : ('layout-hierarchy' as const),
			selected: mode === m,
			onclick: () => {
				mode = m;
				onlayout?.(m);
			},
		})),
	);
	let searchOpen = $state(false);
	let layoutOpen = $state(false);
	const canFind = $derived(selectionItems.length === 2);

	function findPaths() {
		if (!canFind) return;
		const p = findPath(src, selectionItems[0], selectionItems[1]);
		path = p;
		pathNote = p ? L('an_g_path', p.length - 1) : L('an_g_path_none');
	}

	// ── geometry helpers ─────────────────────────────────────────────────
	const pos = (id: string) => out?.pos[id] ?? null;
	const glyphSize = (r: number) => (r >= 18 ? 20 : r >= 13 ? 16 : 12);
	function seg(aId: string, bId: string): { x1: number; y1: number; x2: number; y2: number } | null {
		const a = pos(aId);
		const b = pos(bId);
		const na = byId.get(aId);
		const nb = byId.get(bId);
		if (!a || !b || !na || !nb) return null;
		const d = Math.hypot(b.x - a.x, b.y - a.y) || 1;
		return {
			x1: a.x + ((b.x - a.x) / d) * na.r,
			y1: a.y + ((b.y - a.y) / d) * na.r,
			x2: b.x - ((b.x - a.x) / d) * (nb.r + 2),
			y2: b.y - ((b.y - a.y) / d) * (nb.r + 2),
		};
	}
	const byId = $derived(new Map((model?.nodes ?? []).map((n) => [n.id, n])));
	const placedNodes = $derived(model && out ? model.nodes.filter((n) => out!.pos[n.id]) : []);
	const useCanvas = $derived((model?.nodes.length ?? 0) > SVG_MAX);

	// ── hover ─────────────────────────────────────────────────────────────
	let tip = $state<{ x: number; y: number; text: string } | null>(null);
	let paneEl: HTMLDivElement | null = $state(null);

	function at(e: PointerEvent): { x: number; y: number } {
		const r = paneEl?.getBoundingClientRect();
		return r ? { x: e.clientX - r.left, y: e.clientY - r.top } : { x: 0, y: 0 };
	}

	function nodeTip(n: GNode): string {
		if (n.agg) return L('an_g_merged_tip', n.agg.count, n.labelText.replace(/^\d+\s+/, ''));
		const row = n.row;
		if (!row) return n.labelText;
		const parts = [row.label, kindOne(row.kind, lang)];
		const st = stateWord(row.state, lang);
		if (st) parts.push(st);
		if (row.t != null) parts.push(`${fmtStamp(row.t)} IST`);
		return parts.join(' · ');
	}

	// ── canvas (beyond 300 nodes) ─────────────────────────────────────────
	let canvasEl: HTMLCanvasElement | null = $state(null);
	$effect(() => {
		if (!useCanvas || !canvasEl || !model || !out) return;
		const dpr = typeof devicePixelRatio === 'number' ? devicePixelRatio : 1;
		canvasEl.width = Math.round(W * dpr);
		canvasEl.height = Math.round(H * dpr);
		const g = canvasEl.getContext('2d');
		if (!g) return;
		g.setTransform(dpr, 0, 0, dpr, 0, 0);
		g.clearRect(0, 0, W, H);
		const c = (k: string, f: string) => cssVar(k) ?? f;
		g.lineWidth = 1;
		// edges in the theme's ink (the SVG's ink-2 at 45 %), so the daylight theme draws dark edges on its light canvas
		const edgeInk = c('--v-ink-2', 'gray');
		for (const e of model.edges) {
			const s = seg(e.a, e.b);
			if (!s) continue;
			const hl = e.path || selSet.has(e.a) || selSet.has(e.b);
			g.strokeStyle = hl ? c('--v-map-select', 'blue') : edgeInk;
			g.globalAlpha = hl ? 1 : 0.45;
			g.beginPath();
			g.moveTo(s.x1, s.y1);
			g.lineTo(s.x2, s.y2);
			g.stroke();
		}
		g.globalAlpha = 1;
		for (const n of model.nodes) {
			const p = out.pos[n.id];
			if (!p) continue;
			g.globalAlpha = (near && !near.has(n.id)) || faded(n) ? 0.35 : 1;
			g.beginPath();
			g.arc(p.x, p.y, n.r, 0, Math.PI * 2);
			g.fillStyle = c('--v-map-marker-fill', 'black');
			g.fill();
			g.lineWidth = n.alert ? 2 : 1.5;
			g.strokeStyle = selSet.has(n.id) ? c('--v-map-select', 'blue') : n.alert ? c('--v-map-alert', 'red') : c('--v-map-marker', 'gray');
			g.stroke();
			const gs = glyphSize(n.r);
			const ip = iconPaths(n.icon, gs >= 20 ? 20 : 16);
			g.save();
			g.translate(p.x - gs / 2, p.y - gs / 2);
			g.scale(gs / ip.grid, gs / ip.grid);
			g.fillStyle = c('--v-ink-1', 'white');
			for (const d of ip.paths) g.fill(new Path2D(d), 'evenodd');
			g.restore();
		}
		g.globalAlpha = 1;
		g.font = canvasFont('12px var(--v-font-ui)');
		g.textBaseline = 'alphabetic';
		for (const n of model.nodes) {
			const b = out.labels[n.id];
			if (!b) continue;
			const text = b.short && n.shortLabel ? n.shortLabel.map((q) => ('text' in q ? q.text : 'id' in q ? q.id : '')).join(' ') : n.labelText;
			g.lineWidth = 4;
			g.strokeStyle = c('--v-canvas', 'black');
			g.strokeText(text, b.x + 2, b.y + 12);
			g.fillStyle = c('--v-ink-1', 'white');
			g.fillText(text, b.x + 2, b.y + 12);
		}
	});

	function canvasNodeAt(x: number, y: number): GNode | null {
		if (!model || !out) return null;
		let best: GNode | null = null;
		let bd = Infinity;
		for (const n of model.nodes) {
			const p = out.pos[n.id];
			if (!p) continue;
			const d = Math.hypot(p.x - x, p.y - y);
			if (d <= n.r + 3 && d < bd) {
				bd = d;
				best = n;
			}
		}
		return best;
	}
</script>

<div class="lg" data-testid="link-graph" data-layout={mode} data-nodes={model?.nodes.length ?? 0} data-layout-via={via} data-layout-ms={out ? out.ms.toFixed(1) : ''} {...rest}>
	<div class="gbar" role="toolbar" aria-label={L('an_g_label')}>
		<Popover bind:open={searchOpen} placement="bottom-start" role="menu">
			<Button small minimal icon={ACTION_ICON.search_around} rightIcon="caret-down" disabled={!model}>{L('an_g_search_around')}</Button>
			{#snippet content({ close })}
				<Menu
					items={typeItems}
					autofocus
					label={L('an_g_search_around')}
					onselect={() => {
						close();
					}}
				/>
			{/snippet}
		</Popover>
		<span class="sep" aria-hidden="true"></span>
		<Button
			small
			minimal
			icon={ACTION_ICON.find_paths}
			disabled={!canFind}
			disabledReason={L('an_g_find_paths_need')}
			tooltip={L('an_g_find_paths')}
			aria-label={L('an_g_find_paths')}
			data-testid="graph-find-paths"
			onclick={findPaths}
		/>
		<Button
			small
			minimal
			icon={expandMerged ? 'collapse-all' : 'expand-all'}
			pressed={expandMerged}
			disabled={!model || (!model.stats.mergeable && !expandMerged)}
			tooltip={expandMerged ? L('an_g_collapse') : L('an_g_expand_tip')}
			aria-label={expandMerged ? L('an_g_collapse') : L('an_g_expand')}
			data-testid="graph-expand-merged"
			onclick={() => (expandMerged = !expandMerged)}
		/>
		<Popover bind:open={layoutOpen} placement="bottom-start" role="menu">
			<Button small minimal icon={mode === 'hierarchical' ? 'layout-hierarchy' : mode === 'force' ? 'graph' : 'layout-circle'} rightIcon="caret-down" tooltip={L('an_g_layout')} aria-label={L('an_g_layout')} />
			{#snippet content({ close })}
				<Menu items={layoutItems} autofocus label={L('an_g_layout')} onselect={() => close()} />
			{/snippet}
		</Popover>
		<Button small minimal icon="zoom-to-fit" tooltip={L('an_g_fit')} aria-label={L('an_g_fit')} onclick={fit} />
		{#if pathNote}
			<span class="path-chip" class:none={!path}>
				<Icon name={ACTION_ICON.find_paths} size={12} />{pathNote}
				<button type="button" class="x" aria-label={L('an_g_path_clear')} onclick={() => ((path = null), (pathNote = null))}><Icon name="small-cross" size={16} /></button>
			</span>
		{/if}
		<span class="grow"></span>
		{#if busy}<span class="stat">{L('an_g_laying_out', model?.nodes.length ?? 0)}</span>{/if}
		{#if model}
			<span class="stat" data-testid="graph-stats">{L('an_g_stats_linked', model.stats.linked)}{#if model.stats.merged}{' · '}{L('an_g_stats_merged', model.stats.merged)}{/if}</span>
		{/if}
	</div>

	<div class="pane" bind:this={paneEl} bind:clientWidth={W} bind:clientHeight={H}>
		{#if !focus}
			<div class="nis"><NonIdealState icon="graph" iconSize={48} title={L('an_g_empty')} description={L('an_g_empty_hint')} /></div>
		{:else if !model}
			<div class="nis"><NonIdealState icon="graph-remove" iconSize={48} title={L('an_g_missing')} /></div>
		{:else if useCanvas}
			<canvas
				bind:this={canvasEl}
				style:width="{W}px"
				style:height="{H}px"
				onpointermove={(e) => {
					const p = at(e);
					const n = canvasNodeAt(p.x, p.y);
					tip = n ? { ...p, text: nodeTip(n) } : null;
				}}
				onpointerleave={() => (tip = null)}
				onclick={(e) => {
					const r = paneEl?.getBoundingClientRect();
					const n = r ? canvasNodeAt(e.clientX - r.left, e.clientY - r.top) : null;
					if (n) pick(n, e);
				}}
			></canvas>
		{:else if out}
			<svg width={W} height={H} role="img" aria-label={L('an_g_label')}>
				<defs>
					<marker id="lg-arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path class="arr" d="M0,0 L8,4 L0,8 z" /></marker>
					<marker id="lg-arr-hl" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path class="arr hl" d="M0,0 L8,4 L0,8 z" /></marker>
				</defs>
				<g class="edges">
					{#each model.edges as e (e.id)}
						{@const s = seg(e.a, e.b)}
						{#if s}
							{@const hl = e.path || (selOther.length > 0 && (selSet.has(e.a) || selSet.has(e.b)) && !(e.a === focus && !selSet.has(e.b)))}
							<line
								class="ehit"
								x1={s.x1}
								y1={s.y1}
								x2={s.x2}
								y2={s.y2}
								role="presentation"
								onpointerenter={(ev) => (tip = { ...at(ev), text: L('an_g_edge_tip', e.label) })}
								onpointermove={(ev) => (tip = { ...at(ev), text: L('an_g_edge_tip', e.label) })}
								onpointerleave={() => (tip = null)}
							/>
							<line class="edge" class:hl class:path={e.path} class:dim={!!near && !hl} x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} marker-end={hl ? 'url(#lg-arr-hl)' : 'url(#lg-arr)'} />
						{/if}
					{/each}
				</g>
				<g class="nodes">
					{#each placedNodes as n (n.id)}
						{@const p = out.pos[n.id]}
						{@const sel = selSet.has(n.id)}
						{@const gs = glyphSize(n.r)}
						<g
							class="node"
							class:is-selected={sel}
							class:alert={n.alert}
							class:focus={n.role === 'focus'}
							class:agg={!!n.agg}
							class:dim={(!!near && !near.has(n.id)) || faded(n)}
							data-node={n.id}
							data-role={n.role}
							transform="translate({p.x},{p.y})"
							role="button"
							tabindex="-1"
							aria-label={nodeTip(n)}
							onclick={(e) => pick(n, e)}
							onkeydown={(e) => {
								if (e.key === 'Enter') pick(n, e as unknown as MouseEvent);
							}}
							onpointerenter={(ev) => (tip = { ...at(ev), text: nodeTip(n) })}
							onpointerleave={() => (tip = null)}
						>
							{#if sel}<circle class="halo" r={n.r + 6} />{/if}
							<circle class="ring" r={n.r} />
							{#if sel}<circle class="sel-ring" r={n.r + 2.5} />{/if}
							<g transform="translate({-gs / 2},{-gs / 2})"><Icon name={n.icon} size={gs} /></g>
						</g>
					{/each}
				</g>
				<g class="badges" aria-hidden="true">
					{#each placedNodes as n (n.id)}
						{@const p = out.pos[n.id]}
						{#if n.dot}
							<circle class="dot {n.dot}" cx={p.x + n.r * 0.72} cy={p.y - n.r * 0.72} r="4" />
						{/if}
						{#if n.agg}
							<g transform="translate({p.x + 11},{p.y - 11})">
								<circle class="chip" r="8" />
								<text class="chip-t" y="3.5">{n.agg.count}</text>
							</g>
						{/if}
					{/each}
				</g>
				<g class="labels" aria-hidden="true">
					{#each placedNodes as n (n.id)}
						{@const b = out.labels[n.id]}
						{#if b}
							<text class="glabel" class:sel={selSet.has(n.id) && n.role !== 'focus'} class:dim={!!near && !near.has(n.id)} x={b.x + 2} y={b.y + 12} data-short={b.short ? '' : undefined}>{@html svgLabel(b.short && n.shortLabel ? n.shortLabel : n.label)}</text>
						{/if}
					{/each}
				</g>
			</svg>
		{/if}

		{#if model}
			<div class="legend" aria-hidden="true">
				<span><i class="lg-ring"></i>{L('an_g_legend_watch')}</span>
				<span><i class="lg-dot pending"></i>{L('an_g_legend_pending')}</span>
				<span><i class="lg-dot approved"></i>{L('an_g_legend_approved')}</span>
				<span><Icon name="info-sign" size={12} />{L('an_g_legend_glyph')}</span>
			</div>
		{/if}

		{#if tip}
			<div class="tip" role="tooltip" style:left="{Math.min(W - 280, Math.max(8, tip.x + 14))}px" style:top="{Math.max(4, tip.y - 32)}px">{tip.text}</div>
		{/if}
	</div>
</div>

<style>
	.lg {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		min-width: 0;
		background: var(--v-canvas);
		color: var(--v-ink-1);
		font-size: 12px;
	}

	.gbar {
		display: flex;
		align-items: center;
		gap: 4px;
		flex: 0 0 auto;
		height: 40px;
		padding: 0 12px 0 8px;
		border-bottom: 1px solid var(--v-line-1);
		background: var(--v-surface-1);
		white-space: nowrap;
		overflow: hidden;
	}

	.sep {
		width: 1px;
		height: 20px;
		margin: 0 4px;
		background: var(--v-line-2);
	}

	.grow {
		flex: 1 1 auto;
	}

	.stat {
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
	}

	.path-chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 22px;
		margin-left: 8px;
		padding: 0 2px 0 8px;
		border-radius: var(--v-radius-chip);
		background: var(--v-primary-veil);
		color: var(--v-primary-text);
	}

	.path-chip.none {
		background: var(--v-neutral-veil);
		color: var(--v-ink-2);
	}

	.path-chip .x {
		display: inline-flex;
		padding: 0;
		border: 0;
		background: transparent;
		color: inherit;
		cursor: pointer;
	}

	.pane {
		position: relative;
		flex: 1 1 auto;
		min-height: 0;
		overflow: hidden;
	}

	.nis {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
		padding: 24px;
	}

	svg,
	canvas {
		display: block;
	}

	canvas {
		cursor: pointer;
	}

	.arr {
		fill: color-mix(in srgb, var(--v-ink-2) 50%, transparent);
	}

	.arr.hl {
		fill: var(--v-primary-text);
	}

	.ehit {
		stroke: transparent;
		stroke-width: 9;
		pointer-events: stroke;
	}

	.edge {
		stroke: color-mix(in srgb, var(--v-ink-2) 45%, transparent);
		stroke-width: 1;
		pointer-events: none;
	}

	.edge.hl {
		stroke: var(--v-primary-text);
		stroke-width: 1.5;
	}

	.edge.path {
		stroke: var(--v-map-select);
		stroke-width: 2;
	}

	.edge.dim {
		opacity: 0.35;
	}

	.node {
		cursor: pointer;
		color: var(--v-ink-1);
	}

	.node:focus {
		outline: 0;
	}

	.ring {
		fill: var(--v-map-marker-fill);
		stroke: var(--v-map-marker);
		stroke-width: 1.5;
	}

	.node:hover .ring {
		stroke: var(--v-ink-1);
	}

	.node.alert .ring {
		stroke: var(--v-map-alert);
		stroke-width: 2;
	}

	.node.focus .ring {
		stroke-width: 2.5;
	}

	.halo {
		fill: color-mix(in srgb, var(--v-map-select) 22%, transparent);
	}

	.sel-ring {
		fill: none;
		stroke: var(--v-map-select);
		stroke-width: 2;
	}

	.node.agg .ring {
		stroke-dasharray: 3 2;
	}

	.node.dim {
		opacity: 0.35;
	}

	/* labels and badges never take the pointer: the discs and the edges' hit lines under them do */
	.labels,
	.badges {
		pointer-events: none;
	}

	.dot {
		stroke: var(--v-canvas);
		stroke-width: 1.5;
	}

	.dot.pending {
		fill: var(--v-map-decision);
	}

	.dot.approved {
		fill: var(--v-success-text);
	}

	.chip {
		fill: var(--v-surface-4);
		stroke: var(--v-canvas);
		stroke-width: 2;
	}

	.chip-t {
		fill: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: 10px;
		font-weight: 600;
		text-anchor: middle;
	}

	/* labels last, on top, with a 4 px canvas-coloured halo */
	.glabel {
		fill: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: 12px;
		paint-order: stroke;
		stroke: var(--v-canvas);
		stroke-width: 4px;
		stroke-linejoin: round;
	}

	.glabel.sel {
		fill: var(--v-primary-text);
		font-weight: 600;
	}

	.glabel.dim {
		opacity: 0.45;
	}

	.legend {
		position: absolute;
		left: 8px;
		bottom: 8px;
		display: flex;
		gap: 14px;
		align-items: center;
		height: 26px;
		padding: 0 10px;
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-1);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
		color: var(--v-ink-2);
		font-size: 12px;
		pointer-events: none;
	}

	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.lg-ring {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		box-shadow: inset 0 0 0 2px var(--v-map-alert);
	}

	.lg-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
	}

	.lg-dot.pending {
		background: var(--v-map-decision);
	}

	.lg-dot.approved {
		background: var(--v-success-text);
	}

	.tip {
		position: absolute;
		z-index: 2;
		max-width: 320px;
		padding: 4px 8px;
		border-radius: var(--v-radius-chip);
		background: var(--v-tooltip-bg);
		color: var(--v-tooltip-ink);
		font-size: 12px;
		line-height: 16px;
		pointer-events: none;
		box-shadow: var(--v-elev-2);
	}
</style>
