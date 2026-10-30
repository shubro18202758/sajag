<script lang="ts">
	/**
	 * Inbox (SPEC §5.3 Inbox, §7.3, §8.5; prototype workspace.js inboxHTML) —
	 * the right-dock tab on / and /gods-eye (and the navbar's Inbox button).
	 *
	 *   "Needs your decision"  one row per decision unit (units.ts), by
	 *                          deadline, then severity. An escort proposal
	 *                          shows its countdown and links to its home, the
	 *                          Movement tab (no buttons here); every other row
	 *                          shows "waiting 1 h 40 min" and opens the
	 *                          detail view.
	 *   "Updates"              watchlist reads, completed events, AI notices
	 *                          (a proposal that expired or was superseded) and
	 *                          feed notices. Watches add rows here; they never
	 *                          mute an interrupt.
	 *
	 * Unread rows are 600 weight; read state is kept per browser
	 * (localStorage; the page renders the same without it). Keys: J/K move,
	 * Enter opens, E marks all read, Esc returns from the detail view. The
	 * keys act only while focus is on the page body or inside this Inbox, so
	 * Enter on any other control (a dock tab, a navbar button) does what that
	 * control does. A focused row runs its own Enter (its click), and the J/K
	 * cursor follows row focus.
	 *
	 * The detail view REPLACES the list: "← Inbox", "1 of 2", up and down,
	 * and the unit's ProposalCard — the unit's ONE home on this route. A
	 * decided unit leaves the list; its outcome row stays in the detail view.
	 */
	import { onMount, untrack } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { frameContext } from '$lib/workspace/components/frame/context';
	import { useShellClock, shellClock } from '$lib/shell/clock.svelte';
	import { ACTION_ICON, ACTOR_ICON, PROVENANCE_ICON, eventKindIcon, kindIcon } from '$lib/design/icons';
	import { Button, Icon, NonIdealState, Plate, ProvenanceTag, Tag } from '$lib/ui';
	import { fmtDuration } from '$lib/ui/format/format';
	import { maskPlate } from '$lib/ops/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.decisions';
	import { decisionUnits, unitTitle, type Unit } from './units';
	import { homeOf, parseUnitKey } from './homes';
	import { ageOf, rowMeta, unitPlate } from './cards/meta';
	import { decisionOutcomes } from './cards/outcomes.svelte';
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';

	/** The open unit's card (FIX-E-PERF2): the list is the first paint; the card loads when a unit opens. */
	const loadProposalCard = () => import('./ProposalCard.svelte');
	import InboxRow from './InboxRow.svelte';

	let {
		route: routeProp = null,
		lang: langProp = null,
		open = $bindable<string | null>(null),
	}: {
		route?: '/' | '/gods-eye' | null;
		lang?: string | null;
		/** The unit whose detail view is open (`<kind>:<id>`), null for the list. */
		open?: string | null;
	} = $props();

	const frame = frameContext();
	const route = $derived(routeProp ?? (frame?.route() === '/gods-eye' ? '/gods-eye' : '/'));
	const lang = $derived(langProp ?? ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	$effect(() => useShellClock());
	const now = $derived(shellClock.now);

	const units = $derived(decisionUnits());
	const keyOf = (u: Unit) => `${u.kind}:${u.id}`;

	// ── read state (per browser) ───────────────────────────────────────────

	const READ_KEY = 'sajag.inbox.read.v1';
	let read = $state<Set<string>>(new Set());

	function loadRead() {
		try {
			const raw = localStorage.getItem(READ_KEY);
			const list = raw ? (JSON.parse(raw) as unknown) : [];
			read = new Set(Array.isArray(list) ? list.filter((x): x is string => typeof x === 'string').slice(-500) : []);
		} catch {
			read = new Set();
		}
	}

	function markRead(keys: string[]) {
		const next = new Set(read);
		let changed = false;
		for (const k of keys) {
			if (!next.has(k)) {
				next.add(k);
				changed = true;
			}
		}
		if (!changed) return;
		read = next;
		try {
			localStorage.setItem(READ_KEY, JSON.stringify([...next].slice(-500)));
		} catch {
			// private window or blocked storage: unread state lives for this page only
		}
	}

	// ── updates ────────────────────────────────────────────────────────────

	interface Update {
		key: string;
		icon: import('$lib/design/icons').IconName;
		tone: 'neutral' | 'warning' | 'danger' | 'ai';
		title: string;
		meta: string | null;
		at: number | null;
		select: string | null;
		plate?: string | null;
		test?: boolean;
	}

	const updates = $derived.by((): Update[] => {
		const out: Update[] = [];
		const cutoffRead = now - 30 * 60_000;
		for (const w of ops.watchlist) {
			const s = w.lastSighting;
			const at = s?.t ? Date.parse(s.t) : NaN;
			if (!s || !Number.isFinite(at) || at < cutoffRead) continue;
			out.push({
				key: `read:${w.vehicleId}:${s.t}`,
				icon: kindIcon('sighting'),
				tone: 'danger',
				title: L('dec_upd_watch_read'),
				meta: [s.speedKmh != null ? L('dec_kmh', Math.round(s.speedKmh)) : null, ops.text(w.earmarkReason) || null].filter(Boolean).join(' · ') || null,
				at,
				select: `vehicle:${w.vehicleId}`,
				plate: w.plate,
			});
		}
		const cutoffDone = now - 6 * 3_600_000;
		for (const e of ops.events) {
			if (e.source === 'offline-fixture' || e.state !== 'completed') continue;
			const end = Date.parse(e.windowEnd ?? '') || null;
			if (end != null && end < cutoffDone) continue;
			out.push({
				key: `done:${e.eventId}`,
				icon: eventKindIcon(e.eventKind),
				tone: 'neutral',
				title: L('dec_upd_event_done', ops.text(e.name)),
				meta: e.emulated ? L('dec_upd_emulated') : null,
				at: end,
				select: `event:${e.eventId}`,
			});
		}
		for (const lane of ops.escorts) {
			for (const o of lane.outcomes) {
				if ((o.status !== 'expired' && o.status !== 'superseded') || o.decidedAt == null || now - o.decidedAt > 3_600_000) continue;
				out.push({
					key: `esc:${o.approvalId}:${o.status}`,
					icon: ACTOR_ICON.ai,
					tone: 'ai',
					title: ops.escortOutcomeText(o),
					meta: ops.text(o.summary) || null,
					at: o.decidedAt,
					select: lane.eventId ? `event:${lane.eventId}` : null,
				});
			}
		}
		const feed = ops.trafficFeed;
		if (feed && feed.label === 'simulated') {
			out.push({
				key: 'feed:traffic-simulated',
				icon: PROVENANCE_ICON.simulated,
				tone: 'neutral',
				title: L('dec_upd_traffic_simulated', feed.segments),
				meta: L('dec_upd_traffic_meta'),
				at: null,
				select: null,
			});
		}
		return out.sort((a, b) => (b.at ?? 0) - (a.at ?? 0));
	});

	// ── list cursor and the detail view ────────────────────────────────────

	let cursor = $state(0);
	let root = $state<HTMLDivElement | null>(null);
	const rowKeys = $derived([...units.map(keyOf), ...updates.map((u) => u.key)]);
	const current = $derived(open ? (units.find((u) => keyOf(u) === open) ?? null) : null);
	const openIndex = $derived(current ? units.indexOf(current) : -1);
	const openOutcome = $derived.by(() => {
		if (!open || current) return null;
		const p = parseUnitKey(open);
		return p ? decisionOutcomes.of(p.kind, p.id, now) : null;
	});

	function openUnit(u: Unit) {
		const k = keyOf(u);
		markRead([k]);
		if (homeOf(u.kind, route) === 'movement') {
			// an escort proposal is decided in the movement card, its home
			workspace.rightTab = 'movement';
			workspace.setDock('right', true);
			return;
		}
		open = k;
	}

	function back() {
		open = null;
	}

	function step(delta: number) {
		if (!units.length) return;
		const i = openIndex < 0 ? 0 : (openIndex + delta + units.length) % units.length;
		const u = units[i];
		if (homeOf(u.kind, route) === 'movement') {
			open = keyOf(u);
			return;
		}
		markRead([keyOf(u)]);
		open = keyOf(u);
	}

	function selectUpdate(up: Update) {
		markRead([up.key]);
		if (up.select) selection.select(up.select, { fly: true, source: 'inbox' });
	}

	function markAllRead() {
		markRead(rowKeys);
	}

	// a link card's click (workspace.openDecisionHome) or a #inbox=<kind>:<id> link opens that unit
	let seenFocus = 0;
	$effect(() => {
		const f = workspace.focusDecision;
		if (!f || f.seq === seenFocus) return;
		seenFocus = f.seq;
		untrack(() => {
			if (homeOf(f.kind, route) === 'inbox') open = `${f.kind}:${f.id}`;
		});
	});

	onMount(() => {
		loadRead();
		const fromHash = () => {
			const params = new URLSearchParams(location.hash.replace(/^#/, ''));
			const p = parseUnitKey(params.get('inbox'));
			if (p) open = `${p.kind}:${p.id}`;
		};
		fromHash();
		window.addEventListener('hashchange', fromHash);
		return () => window.removeEventListener('hashchange', fromHash);
	});

	// ── keys: J/K/Enter/E, Esc back from the detail ─────────────────────────

	function typing(e: KeyboardEvent): boolean {
		const el = e.target as HTMLElement | null;
		return !!el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));
	}

	/** The Inbox's keys apply: nothing else has focus (the page body), or focus is inside this Inbox. */
	function ours(e: KeyboardEvent): boolean {
		const el = e.target as Node | null;
		if (!el || el === document.body || el === document.documentElement) return true;
		return !!root && root.contains(el);
	}

	/** Focus sits on a control inside the Inbox (a row, a button): its own Enter (a click) runs. */
	function onControl(e: KeyboardEvent): boolean {
		const el = e.target as HTMLElement | null;
		return !!el && el !== root && typeof el.closest === 'function' && !!el.closest('button, a[href], [role="button"], [role="tab"], [role="menuitem"], summary');
	}

	/** After J/K, keep keyboard focus on the cursor row when a row had focus. */
	function focusCursor() {
		const active = document.activeElement as HTMLElement | null;
		if (!root || !active || !root.contains(active) || !active.hasAttribute('data-cursor')) return;
		root.querySelector<HTMLElement>(`[data-cursor="${cursor}"]`)?.focus();
	}

	function onKey(e: KeyboardEvent) {
		if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || typing(e) || workspace.omnibar.open || !ours(e)) return;
		const k = e.key.toLowerCase();
		if (open) {
			if (k === 'j') step(1);
			else if (k === 'k') step(-1);
			else if (e.key === 'Escape') back();
			else return;
			e.preventDefault();
			return;
		}
		if (k === 'j') {
			cursor = Math.min(rowKeys.length - 1, cursor + 1);
			focusCursor();
		} else if (k === 'k') {
			cursor = Math.max(0, cursor - 1);
			focusCursor();
		} else if (e.key === 'Enter') {
			if (onControl(e)) return; // the focused row or button handles its own Enter
			const u = units[cursor];
			if (u) openUnit(u);
			else {
				const up = updates[cursor - units.length];
				if (up) selectUpdate(up);
			}
		} else if (k === 'e') markAllRead();
		else return;
		e.preventDefault();
	}

	const escortHome = (u: Unit) => homeOf(u.kind, route) === 'movement';
	const unreadCount = $derived(updates.filter((u) => !read.has(u.key)).length);
</script>

<svelte:window onkeydown={onKey} />

<div class="inbox" data-testid="inbox" data-view={open ? 'detail' : 'list'} bind:this={root}>
	{#if open && (current || openOutcome)}
		<div class="detail-head">
			<Button minimal small icon="arrow-left" tooltip={L('dec_back_tip')} onclick={back}>{L('dec_inbox')}</Button>
			<span class="grow"></span>
			{#if current}<span class="pos">{L('dec_n_of_m', openIndex + 1, units.length)}</span>{/if}
			<Button minimal small icon="chevron-up" tooltip={L('dec_prev_tip')} aria-label={L('dec_prev_tip')} disabled={units.length < 2} onclick={() => step(-1)} />
			<Button minimal small icon="chevron-down" tooltip={L('dec_next_tip')} aria-label={L('dec_next_tip')} disabled={units.length < 2} onclick={() => step(1)} />
		</div>
		{#if current && escortHome(current)}
			<div class="home-note">
				<NonIdealState icon={ACTION_ICON.inbox} iconSize={32} title={unitTitle(current, lang)} description={L('dec_escort_home_note')}>
					{#snippet action()}
						<Button small onclick={() => openUnit(current!)}>{L('dec_open_movement')}</Button>
					{/snippet}
				</NonIdealState>
			</div>
		{:else if current}
			{#key open}
				<LazyMount load={loadProposalCard} unit={current} {lang} />
			{/key}
		{:else if openOutcome}
			<div class="decided" data-testid="decision-outcome">
				<Icon name="tick-circle" size={16} />
				<span><b>{openOutcome.verb}</b> · {openOutcome.title}<br /><span class="muted">{L('dec_outcome_by', openOutcome.officer)}</span></span>
			</div>
		{/if}
	{:else}
		<div class="sec-head">
			<span>{L('dec_needs_decision')}</span>
			{#if units.length}<Tag intent="warning" round>{units.length}</Tag>{/if}
			<span class="grow"></span>
			<span class="hint">{L('dec_by_deadline')}</span>
		</div>
		{#each units as u, i (keyOf(u))}
			{@const age = ageOf(u, lang, now)}
			{@const plate = unitPlate(u)}
			{@const title = unitTitle(u, lang)}
			<InboxRow
				data-testid="inbox-row"
				data-kind={u.kind}
				data-id={u.id}
				data-home={homeOf(u.kind, route)}
				icon={kindIcon('recommendation')}
				tone="warning"
				{title}
				meta={escortHome(u) ? L('dec_meta_movement_card', rowMeta(u, lang, now)) : rowMeta(u, lang, now)}
				ageLabel={age.label}
				age={age.value}
				countdown={age.countdown}
				urgent={age.urgent}
				unread={!read.has(keyOf(u))}
				selected={cursor === i}
				data-cursor={i}
				onfocus={() => (cursor = i)}
				onopen={() => openUnit(u)}
			>
				{#snippet titleSnippet()}
					{@const shown = plate ? ops.plate(plate) : null}
					{@const at = shown ? title.indexOf(shown) : -1}
					{#if shown && at >= 0}<span class="t-pre">{title.slice(0, at)}</span><span class="t-mark"><Plate mark={shown} masked={!ops.officerOn} /></span><span class="t-post">{title.slice(at + shown.length)}</span>{:else}<span class="t-pre">{title}</span>{/if}
				{/snippet}
			</InboxRow>
		{:else}
			<p class="empty">{L('dec_none_waiting')}</p>
		{/each}

		<div class="sec-head upd">
			<span>{L('dec_updates')}</span>
			{#if unreadCount}<Tag round>{unreadCount}</Tag>{/if}
			<span class="grow"></span>
			<Button minimal small icon="tick" tooltip={L('dec_mark_read_tip')} aria-label={L('dec_mark_read_tip')} onclick={markAllRead} />
		</div>
		{#each updates as up, j (up.key)}
			<InboxRow
				data-testid="inbox-update"
				data-key={up.key}
				icon={up.icon}
				tone={up.tone}
				title={up.title}
				meta={up.meta}
				age={up.at != null ? fmtDuration((now - up.at) / 1000, lang) : L('dec_ongoing')}
				ageLabel={up.at != null ? L('dec_age_ago') : null}
				unread={!read.has(up.key)}
				selected={cursor === units.length + j}
				data-cursor={units.length + j}
				onfocus={() => (cursor = units.length + j)}
				onopen={() => selectUpdate(up)}
			>
				{#snippet titleSnippet()}
					{up.title}{#if up.plate}<Plate mark={ops.plate(up.plate) ?? maskPlate(up.plate)} masked={!ops.officerOn} />{/if}{#if up.meta && up.key.startsWith('done:') && up.meta === L('dec_upd_emulated')}<ProvenanceTag source="emulated" compact {lang} />{/if}
				{/snippet}
			</InboxRow>
		{:else}
			<p class="empty">{L('dec_nothing_new')}</p>
		{/each}
	{/if}
</div>

<style>
	.inbox {
		display: flex;
		flex-direction: column;
		min-height: 100%;
		background: var(--v-surface-1);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.sec-head {
		position: sticky;
		top: 0;
		z-index: 1;
		display: flex;
		align-items: center;
		gap: 8px;
		height: 32px;
		padding: 0 12px 0 16px;
		font-size: var(--v-text-xs);
		font-weight: 600;
		color: var(--v-ink-2);
		background: var(--v-surface-1);
		border-bottom: 1px solid var(--v-line-1);
	}

	.sec-head.upd {
		margin-top: 8px;
		border-top: 1px solid var(--v-line-1);
	}

	.hint {
		font-weight: 400;
	}

	.grow {
		flex: 1 1 auto;
	}

	.detail-head {
		position: sticky;
		top: 0;
		z-index: 2;
		display: flex;
		align-items: center;
		gap: 8px;
		height: 40px;
		padding: 0 8px;
		background: var(--v-surface-1);
		border-bottom: 1px solid var(--v-line-2);
		flex: 0 0 auto;
	}

	.pos {
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
	}

	.empty {
		margin: 0;
		padding: 12px 16px;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.home-note {
		padding: 32px 16px;
	}

	.decided {
		display: flex;
		gap: 8px;
		align-items: flex-start;
		margin: 16px;
		padding: 8px 12px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		background: var(--v-success-veil);
		border-radius: var(--v-radius-chip);
	}

	.decided :global(svg) {
		color: var(--v-success-text);
		flex: 0 0 auto;
	}

	.muted {
		color: var(--v-ink-2);
	}

	/* a title with a mark (F-29): the words wrap — a verb is never cut ("Authorise pursu…") — and the mark never breaks */
	.t-pre,
	.t-post {
		min-width: 0;
		white-space: normal;
	}

	.t-pre {
		flex: 0 1 auto;
	}

	.t-post {
		flex: 0 100 auto;
	}

	.t-mark {
		display: inline-flex;
		flex: 0 0 auto;
	}
</style>
