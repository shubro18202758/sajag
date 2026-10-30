<script lang="ts">
	/**
	 * HeaderMenu (colleague review, V3-P4B) — the top bar's ONE compact menu for the secondary items, so the bar
	 * itself carries only the title, the search, alerts and the duty officer:
	 *
	 *   this screen   the page's one-line status (v3Bar.sub: "Mumbai · Friday 30 Oct · 19:42 IST"), moved off the bar
	 *   language      EN · हिंदी · मराठी (`data-lang-code`, the sajag_lang cookie through the shell's onLangPick)
	 *   exercise data the v2 ExercisePanel with the page's exercise statement (commandBar.exercise), unchanged
	 *   data status   what the page reports in commandBar.dataStatus (every feed with its state, the decision model's
	 *                 posture) — the v2 Data panel's facts and words, drawn here (importing the v2 DataPanel would split
	 *                 it out of the v2 shell's chunk and cost every v2 route a request)
	 *
	 * Honest at a glance even while closed: when the console runs on exercise data the trigger carries the flask
	 * (`feed-provenance`, `data-label` = the feed's provenance word) and its accessible name says so; the trigger
	 * always shows the current language.
	 */
	import { SUPPORTED, langShort, t } from '$lib/i18n/strings';
	import Popover from '$lib/ui/Popover.svelte';
	import ExercisePanel from '$lib/shell/ExercisePanel.svelte';
	import type { DataStatus, ExerciseInfo } from '$lib/shell/command-bar.svelte';
	import Glyph from '../Glyph.svelte';
	import MapStyleSwitch from '../map/MapStyleSwitch.svelte';
	import '../packs.v3';
	import '../media/packs.media';

	let {
		lang,
		status = null,
		exercise = null,
		dataStatus = null,
		onLangPick,
	}: {
		lang: string;
		status?: string | null;
		exercise?: ExerciseInfo | null;
		dataStatus?: DataStatus | null;
		onLangPick: (code: string) => void;
	} = $props();

	let open = $state(false);

	const label = $derived(exercise ? `${t(lang, 'v3_menu')} · ${t(lang, 'v3_menu_exercise')}` : t(lang, 'v3_menu'));

	const FEED_KEY: Record<string, string> = { ok: 'shell_feed_ok', degraded: 'shell_feed_degraded', down: 'shell_feed_down', none: 'shell_feed_none' };
	/** A v2 word, or the raw value when the pack has none (never a raw key). */
	const word = (key: string, raw: string) => {
		const w = t(lang, key);
		return w === key ? raw : w;
	};
</script>

<Popover placement="bottom-end" class="v3-pop" bind:open aria-label={t(lang, 'v3_menu')}>
	<button
		type="button"
		class={['trigger', exercise && 'ex']}
		data-testid="v3-header-menu"
		data-exercise={exercise ? 'true' : 'false'}
		aria-label={label}
		title={t(lang, 'v3_menu_tip')}
	>
		{#if exercise}
			<span class="flask" data-testid="feed-provenance" data-label={exercise.label}><Glyph name="flask" size={16} /></span>
		{/if}
		<span class="code" lang={lang}>{langShort(lang)}</span>
		<span class="chev" aria-hidden="true"></span>
	</button>
	{#snippet content()}
		<div class="menu" data-v3="header-menu">
			{#if status}
				<section class="sec">
					<h2 class="h">{t(lang, 'v3_menu_screen')}</h2>
					<p class="status" data-v3="screen-status">{status}</p>
				</section>
			{/if}

			<section class="sec">
				<h2 class="h" id="v3-menu-lang">{t(lang, 'v3_menu_lang')}</h2>
				<div class="langs" role="group" aria-labelledby="v3-menu-lang">
					{#each SUPPORTED as l (l.code)}
						<button
							type="button"
							lang={l.code}
							class={['lang', lang === l.code && 'is-pressed']}
							aria-pressed={lang === l.code}
							data-lang-code={l.code}
							data-autofocus={lang === l.code ? '' : undefined}
							onclick={() => onLangPick(l.code)}
						>
							{l.label}
						</button>
					{/each}
				</div>
			</section>

			<section class="sec" data-v3="menu-map-style">
				<MapStyleSwitch {lang} />
			</section>

			{#if exercise}
				<section class="sec ex-sec" data-v3="menu-exercise">
					<ExercisePanel {exercise} {lang} />
				</section>
			{/if}

			{#if dataStatus}
				<section class="sec" data-v3="menu-data">
					<h2 class="h">{t(lang, 'v3_menu_data')}</h2>
					<ul class="feeds">
						{#each dataStatus.feeds as f (f.name)}
							<li data-feed={f.name} data-status={f.status}>
								<span class={['dot', `s-${f.status}`]} aria-hidden="true"></span>
								<span class="fn">{f.name}<small>{f.label}</small></span>
								<span class="fs">{word(FEED_KEY[f.status] ?? 'shell_feed_none', f.status)}</span>
							</li>
						{/each}
					</ul>
					<p class="model">
						{t(lang, 'shell_data_model')}: {word(`shell_decider_${dataStatus.decider}`, dataStatus.decider)}
						{#if dataStatus.p95 != null && Number.isFinite(dataStatus.p95)}<span>{t(lang, 'shell_data_p95', dataStatus.p95.toFixed(1))}</span>{/if}
						<span>{word(`shell_tier_${dataStatus.tier}`, dataStatus.tier)}</span>
					</p>
				</section>
			{/if}
			<!-- V3-P7: the imagery's credits, where credits live -->
			<section class="sec credits" data-v3="menu-credits">
				<p>{t(lang, 'v3i_art_credit')}</p>
				<p>{t(lang, 'v3i_photos_credit')} <a href="/photos/NOTICE.md" target="_blank" rel="noopener">{t(lang, 'v3i_photos_link')}</a></p>
				<p>{t(lang, 'v3i_marks_credit')}</p>
			</section>
		</div>
	{/snippet}
</Popover>

<style>
	.credits p {
		margin: 0 0 4px;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.credits a {
		color: var(--v3-brand-text);
	}

	/* a fixed width, flask or not, so the controls after it sit at the same pixels on every page */
	.trigger {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		width: 96px;
		height: var(--v3-ctl-lg);
		padding: 0 10px;
		border: 1px solid var(--v3-line-2);
		border-radius: 22px;
		background: var(--v3-s1);
		color: var(--v3-t2);
		font: inherit;
		font-size: 14px;
		font-weight: 650;
		white-space: nowrap;
		cursor: pointer;
	}

	.trigger:hover {
		border-color: var(--v3-line-3);
		color: var(--v3-t1);
	}

	.trigger:focus-visible,
	.lang:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	/* exercise data: the flask in a dashed ring — the honest provenance mark, visible while the menu is closed */
	.flask {
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		border: 1px dashed var(--v3-dashed);
		border-radius: 50%;
		color: var(--v3-t2);
	}

	.code {
		min-width: 18px;
		color: var(--v3-t1);
		text-align: center;
	}

	/* a small chevron, drawn (the glyph set has arrows, not chevrons) */
	.chev {
		width: 7px;
		height: 7px;
		margin: -4px 2px 0 0;
		border-right: 2px solid var(--v3-t3);
		border-bottom: 2px solid var(--v3-t3);
		transform: rotate(45deg);
	}

	.menu {
		display: flex;
		flex-direction: column;
		width: 340px;
		max-width: calc(100vw - 24px);
		padding: 6px 0;
	}

	.sec {
		padding: 12px 18px;
	}

	.sec + .sec {
		border-top: 1px solid var(--v3-line-1);
	}

	.h {
		margin: 0 0 8px;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 650;
	}

	.status {
		margin: 0;
		color: var(--v3-t1);
		font-size: 14px;
		line-height: 20px;
	}

	.langs {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 4px;
		padding: 3px;
		border: 1px solid var(--v3-line-2);
		border-radius: 20px;
		background: var(--v3-s1);
	}

	.lang {
		height: 34px;
		padding: 0 8px;
		border: 0;
		border-radius: 16px;
		background: transparent;
		color: var(--v3-t2);
		font: inherit;
		font-size: 14px;
		font-weight: 620;
		cursor: pointer;
	}

	.lang:hover {
		color: var(--v3-t1);
	}

	.lang.is-pressed {
		background: var(--v3-s4);
		color: var(--v3-t1);
	}

	.feeds {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.feeds li {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.dot {
		flex: none;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--v3-t3);
	}

	.dot.s-ok {
		background: var(--v3-ok);
	}

	.dot.s-degraded {
		background: var(--v3-decide);
	}

	.dot.s-down {
		background: var(--v3-t1);
		box-shadow: 0 0 0 2px var(--v3-line-3);
	}

	.fn {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
		color: var(--v3-t1);
	}

	.fn small {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}

	.fs {
		color: var(--v3-t2);
		font-weight: 600;
	}

	.model {
		display: flex;
		flex-wrap: wrap;
		gap: 4px 10px;
		margin: 10px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	/* the v2 exercise panel sits flush in its section */
	.ex-sec {
		padding: 0 2px;
	}

	.ex-sec :global([data-shell='exercise-panel']) {
		width: auto;
	}
</style>
