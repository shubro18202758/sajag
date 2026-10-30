<script lang="ts">
	/**
	 * NowPanel (V3-SPEC §5.6, §6.5, §7.7) — "Now": the accessible equivalent of the map. The same four groups as
	 * the chips (a hidden group leaves the list too), each row an object on the map: art, title (a mark masked
	 * with its lock), one meta line, and on the right its state (Live / Open / Active) or, for a decision, the
	 * time left (or how long it has waited). Selecting a row selects the object everywhere and focuses the map on
	 * it; the selected row is marked (aria-current). The header carries the live clock and Replay — which waits,
	 * with its reason, while a movement is live or a pursuit is open (v2 §7.3).
	 */
	import { t } from '$lib/i18n/strings';
	import { fmtDuration } from '$lib/ui/format/format';
	import Glyph from '../Glyph.svelte';
	import PlateChip from '../ui/PlateChip.svelte';
	import { countdownText } from '../home/model';
	import { GROUP_IDS, GROUP_KEY, type GroupId, type NowItem } from './model';
	import './packs.map3';
	import { smallArt } from '../media/art';

	/** V3-P7: a row's small picture — the vehicle's studio shot or the kind's key art (16:9); agency tiles stay. */
	const nowArt = smallArt;

	let {
		items,
		on,
		selKey,
		now,
		clock,
		lang,
		replaying,
		replayBlocked,
		onselect,
		onreplay,
		onlive,
	}: {
		items: readonly NowItem[];
		on: Readonly<Record<GroupId, boolean>>;
		selKey: string | null;
		now: number;
		/** "19:42:06" IST. */
		clock: string;
		lang: string;
		replaying: boolean;
		/** The reason replay waits (a pack key), or null. */
		replayBlocked: string | null;
		onselect: (item: NowItem) => void;
		onreplay: () => void;
		onlive: () => void;
	} = $props();

	const groups = $derived(GROUP_IDS.filter((g) => on[g]).map((g) => ({ g, rows: items.filter((i) => i.group === g) })));

	function timer(i: NowItem): string {
		if (i.deadline != null && i.deadline > now) return countdownText(i.deadline - now, lang);
		if (i.since != null) return t(lang, 'v3m_waiting', fmtDuration((now - i.since) / 1000, lang));
		return '';
	}
</script>

<aside class="now v3-glass" aria-label={t(lang, 'v3m_now_list')} data-testid="v3-now" data-ge-keepout>
	<header>
		<span class={['dot', replaying && 'replay']} aria-hidden="true"></span>
		<h2>{t(lang, 'v3m_now')}</h2>
		<span class="meta">{replaying ? t(lang, 'v3m_now_replay') : t(lang, 'v3m_now_live', clock)}</span>
		{#if replaying}
			<button type="button" class="link" data-testid="v3-now-live" onclick={onlive}>{t(lang, 'v3m_replay_back')}</button>
		{:else}
			<button
				type="button"
				class="link"
				data-testid="v3-now-replay"
				aria-disabled={replayBlocked ? 'true' : undefined}
				title={replayBlocked ? t(lang, replayBlocked) : undefined}
				onclick={() => {
					if (!replayBlocked) onreplay();
				}}>{t(lang, 'v3m_replay')}</button
			>
		{/if}
	</header>
	{#if replayBlocked && !replaying}<p class="why" data-testid="v3-replay-why">{t(lang, replayBlocked)}</p>{/if}
	<div class="list">
		{#each groups as { g, rows } (g)}
			<section class={['grp', `g-${g}`]} aria-labelledby={`v3-now-${g}`} data-group={g}>
				<h3 id={`v3-now-${g}`}><span class="sw" aria-hidden="true"></span>{t(lang, GROUP_KEY[g])}</h3>
				{#if rows.length === 0}
					<p class="empty">{t(lang, 'v3m_now_empty')}</p>
				{:else}
					<ul>
						{#each rows as i (i.key)}
							{@const tm = i.group === 'decide' ? timer(i) : ''}
							<li>
								<button
									type="button"
									class={['li', selKey === i.key && 'is-selected']}
									aria-current={selKey === i.key ? 'true' : undefined}
									data-testid="v3-now-row"
									data-key={i.key}
									data-group={i.group}
									data-urn={i.urn ?? ''}
									onclick={() => onselect(i)}
								>
									<img class={['art', nowArt(i.art) !== i.art && 'wide']} src={nowArt(i.art)} alt="" width="40" height="40" loading="lazy" />
									<span class="tx">
										<span class="tt">{i.title}{#if i.plate}&nbsp;<PlateChip mark={i.plate.mark} masked={i.plate.masked} {lang} />{/if}</span>
										<span class="mm">{i.meta}{#if i.prov}&nbsp;· <span class="prov" title={i.prov.title}>{i.prov.text}</span>{/if}</span>
									</span>
									{#if i.right}
										<span class={['rt', `tone-${i.right.tone}`]}>{i.right.text}</span>
									{:else if tm}
										<span class={['rt', 'tone-decide', 'timer', i.deadline == null || i.deadline <= now ? 'waited' : null]}>{tm}</span>
									{:else if i.decisions > 0}
										<span class="rt tone-decide"><Glyph name="clock" size={14} /></span>
									{/if}
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</section>
		{/each}
	</div>
</aside>

<style>
	.now {
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
		border: 1px solid var(--v3-glass-border);
		border-radius: var(--v3-radius-l);
		background: var(--v3-glass-surface);
		box-shadow: var(--v3-elev-2);
		pointer-events: auto;
	}

	header {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 16px 18px 8px;
	}

	h2 {
		margin: 0;
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 650;
	}

	.dot {
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: var(--v3-ok);
		animation: pulse 2.4s var(--v3-ease) infinite;
	}

	.dot.replay {
		background: var(--v3-t3);
		animation: none;
	}

	@keyframes pulse {
		50% {
			opacity: 0.35;
		}
	}

	.meta {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		min-width: 0;
	}

	.link {
		margin-left: auto;
		border: 0;
		background: none;
		padding: 4px 0;
		color: var(--v3-brand-text);
		font: inherit;
		font-size: 15px;
		font-weight: 650;
		white-space: nowrap;
		cursor: pointer;
	}

	.link[aria-disabled='true'] {
		color: var(--v3-t3);
		cursor: not-allowed;
	}

	.link:focus-visible,
	.li:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.why {
		margin: 0 18px 6px;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.list {
		flex: 1;
		min-height: 0;
		overflow: auto;
		padding: 0 10px 12px;
		scrollbar-width: thin;
		scrollbar-color: var(--v3-s4) transparent;
	}

	h3 {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 12px 8px 4px;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 700;
	}

	.sw {
		width: 8px;
		height: 8px;
		border-radius: 4px;
		background: var(--v3-t3);
	}

	.g-live .sw {
		background: var(--v3-route);
	}

	.g-decide .sw {
		background: var(--v3-decide);
	}

	.g-reported .sw {
		background: var(--v3-t2);
	}

	ul {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.empty {
		margin: 2px 8px 6px;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
	}

	.li {
		display: grid;
		grid-template-columns: 40px minmax(0, 1fr) auto;
		gap: 12px;
		align-items: center;
		width: 100%;
		padding: 9px 8px;
		border: 0;
		border-radius: var(--v3-radius-m);
		background: none;
		color: var(--v3-t1);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.li:hover {
		background: var(--v3-s2);
	}

	.li.is-selected {
		background: var(--v3-s3);
	}

	.art {
		flex: none;
		width: 40px;
		height: 40px;
		border-radius: 11px;
	}

	.art.wide {
		width: 64px;
		height: 40px;
		object-fit: cover;
		border-radius: var(--v3-radius-s);
		background: var(--v3-s3);
	}

	.tx {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.tt {
		font-size: 14px;
		line-height: 19px;
		font-weight: 640;
		overflow-wrap: anywhere;
	}

	.mm {
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: 17px;
		overflow: hidden;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
	}

	.prov {
		color: var(--v3-t3);
	}

	.rt {
		align-self: center;
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		font-weight: 700;
		text-align: right;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}

	/* "waiting 10 h 35 min" (in Marathi, a long phrase) wraps in its own narrow column: the title keeps its width */
	.rt.waited {
		max-width: 7.5em;
		white-space: normal;
		line-height: 15px;
	}

	.tone-route {
		color: var(--v3-route-text);
	}

	.tone-alert {
		color: var(--v3-alert-text);
	}

	.tone-decide {
		color: var(--v3-decide-text);
	}

	:global(:lang(hi)) .tt,
	:global(:lang(mr)) .tt {
		font-size: 15px;
		line-height: 1.6;
	}

	@media (prefers-reduced-motion: reduce) {
		.dot {
			animation: none;
		}
	}
</style>
