<script lang="ts">
	/**
	 * The Sajag landing page (/welcome): the public front door that says what Sajag is and leads into it.
	 *
	 * Night theme (the console's ground and type), one idea per section. The first 1920 × 1080 viewport is a poster:
	 * the Sea Link or Marine Drive at night (a reference photo, labelled and credited on the picture), the Sajag lockup, the
	 * tagline in the reader's language ("Not by stopping. By steering."), one sub-line, the two doors and the console
	 * itself in a window (a screenshot, captioned "Console screenshot · exercise data"). Then the city in photographs,
	 * the problem and three modelled figures, See / Decide / Act, the four seats, the principles, what it is built on
	 * with the agencies' marks, a closing band and the footer.
	 *
	 * Neutral black, white and grey; colour only for meaning and the one accent blue. English unless the reader picked
	 * another language. PUBLIC and STATIC: no sign-in, no API call, no store and no operator code — only the V3 tokens, the imagery
	 * layer (photos, key art, marks), the glyphs and this page's string pack. Links into the console load a new document
	 * (data-sveltekit-reload), because the console runs under its own content-security policy. Every picture carries its
	 * honest label: a reference photo is drawn by Cover (always "Reference photo · not live" + credit, on the picture),
	 * key art is captioned as an illustration, the marks belong to their owners.
	 */
	import { t } from '$lib/i18n/strings';
	import '../media/packs.media';
	import './packs.landing';
	import Glyph from '../Glyph.svelte';
	import AgencyMark, { markName } from '../media/AgencyMark.svelte';
	import Cover from '../media/Cover.svelte';
	import { KEY_ART } from '../media/art';
	import LangSwitch from './LangSwitch.svelte';
	import { AUDIENCES, BUILT, HERO_SHOT, HREF, MARK_ROW, OPERATOR_HREFS, PRINCIPLES, SHOTS, STEPS, TODO_IMPACT, cityPhotos, endPhoto, heroPhoto, marks } from './content';

	let { lang, onpick }: { lang: string; onpick: (code: string) => void } = $props();

	const hero = heroPhoto();
	const end = endPhoto();
	const city = cityPhotos();
	const win = SHOTS[HERO_SHOT];
	const row = marks(MARK_ROW);
	const reload = (href: string) => (OPERATOR_HREFS.includes(href) ? '' : undefined);
</script>

<div class="land" data-landing data-testid="landing" {lang}>
	<a class="skip" href="#land-main">{t(lang, 'v3l_skip')}</a>

	<!-- ── 1 · the poster ─────────────────────────────────────────────────── -->
	<header class="hero" data-testid="land-hero">
		<div class="hero-photo" data-testid="land-hero-photo">
			<Cover art="" alt="" photo={hero} {lang} sizes="(max-width: 900px) 200vw, 76vw" eager class="land-cover" />
		</div>

		<nav class="nav wrap-wide" aria-label={t(lang, 'v3l_nav')}>
			<a class="nav-mark" href="#land-main" aria-label={t(lang, 'v3l_logo')}>
				<img src="/brand/sajag-mark.svg" alt="" width="40" height="40" />
			</a>
			<div class="nav-links">
				<a href="#how">{t(lang, 'v3l_nav_how')}</a>
				<a href="#principles">{t(lang, 'v3l_nav_rules')}</a>
				<a href={HREF.citizen}>{t(lang, 'v3l_nav_citizen')}</a>
				<a href={HREF.driver}>{t(lang, 'v3l_nav_driver')}</a>
			</div>
			<LangSwitch {lang} label={t(lang, 'v3l_lang')} {onpick} />
			<a class="btn btn-primary btn-sm nav-cta" href={HREF.console} data-sveltekit-reload data-testid="land-nav-console">{t(lang, 'v3l_open_console')}</a>
		</nav>

		<div class="hero-body wrap-wide">
			<div class="hero-copy">
				<p class="eyebrow">{t(lang, 'v3l_hero_eyebrow')}</p>
				<h1 class="lockup">
					<img src="/brand/sajag-lockup.svg" alt={t(lang, 'v3l_logo')} width="192" height="64" />
				</h1>
				<p class="tagline" data-testid="land-tagline">
					<span class="t-lead">{t(lang, 'v3l_tagline_lead')}</span>
					<span class="t-turn">{t(lang, 'v3l_tagline_turn')}</span>
				</p>
				<p class="sub" data-testid="land-promise">{t(lang, 'v3l_hero_sub')}</p>
				<div class="ctas">
					<a class="btn btn-primary" href={HREF.console} data-sveltekit-reload data-testid="land-cta-console">
						{t(lang, 'v3l_open_console')}<Glyph name="arrowR" size={20} />
					</a>
					<a class="btn btn-ghost" href={HREF.citizen} data-testid="land-cta-road">{t(lang, 'v3l_check_road')}</a>
				</div>
				<p class="rule"><Glyph name="shield" size={18} />{t(lang, 'v3l_hero_rule')}</p>
			</div>
		</div>

		<figure class="window" data-testid="land-hero-shot">
			<img src={win.src} srcset={win.srcset} sizes="(max-width: 1100px) 92vw, 640px" alt={t(lang, win.alt)} width={win.w} height={win.h} loading="eager" decoding="async" />
			<figcaption class="shot-tag" data-testid="land-shot-caption">{t(lang, 'v3l_shot_tag')}</figcaption>
		</figure>
	</header>

	<main id="land-main" tabindex="-1">
		<!-- ── 2 · the city ─────────────────────────────────────────────────── -->
		<section class="sec city wrap" aria-labelledby="land-city">
			<div class="city-head">
				<p class="kicker">{t(lang, 'v3l_city_kicker')}</p>
				<h2 class="heading" id="land-city">{t(lang, 'v3l_city_heading')}</h2>
				<p class="lead">{t(lang, 'v3l_city_lead')}</p>
			</div>
			<ul class="city-strip" data-testid="land-city">
				{#each city as p (p.slug)}
					<li><Cover art="" alt="" photo={p} {lang} sizes="(max-width: 640px) 92vw, (max-width: 1100px) 46vw, 20vw" compact class="city-cover" /></li>
				{/each}
			</ul>
		</section>

		<!-- ── 3 · the problem ─────────────────────────────────────────────── -->
		<section class="sec problem wrap" aria-labelledby="land-problem">
			<p class="kicker" id="land-problem">{t(lang, 'v3l_problem_kicker')}</p>
			<p class="statement">{t(lang, 'v3l_problem_line')}</p>
			<p class="lead">{t(lang, 'v3l_problem_rule')}</p>
			<ul class="figures" data-testid="land-figures" data-pending={TODO_IMPACT.pending ? '' : undefined}>
				{#each TODO_IMPACT.figures as f (f.key)}
					<li class="figure" data-figure={f.key}>
						{#if f.value}
							<span class="fig-value">{f.value}</span>
						{:else}
							<span class="fig-value fig-pending">{t(lang, 'v3l_fig_pending')}</span>
						{/if}
						<span class="fig-label">{t(lang, `v3l_fig_${f.key}_label`)}</span>
					</li>
				{/each}
			</ul>
			<p class="modelled" data-testid="land-modelled">
				<span class="tag-dashed">{t(lang, 'v3l_modelled')}</span>
				<span>{t(lang, 'v3l_modelled_note')}{#if TODO_IMPACT.pending}{' '}{t(lang, 'v3l_modelled_todo')}{/if}</span>
			</p>
		</section>

		<!-- ── 4 · how it works ────────────────────────────────────────────── -->
		<section class="sec how wrap" id="how" aria-labelledby="land-how">
			<p class="kicker">{t(lang, 'v3l_how_kicker')}</p>
			<h2 class="heading" id="land-how">{t(lang, 'v3l_how_heading')}</h2>
			<p class="lead">{t(lang, 'v3l_how_lead')}</p>
			<ol class="steps">
				{#each STEPS as s (s.key)}
					<li class="step" data-step={s.key}>
						<figure class="frame">
							<img src={s.art} alt={t(lang, 'v3i_art_alt', t(lang, `v3l_${s.key}_title`))} width={KEY_ART.w} height={KEY_ART.h} loading="lazy" decoding="async" />
							<figcaption class="cap" data-testid="land-step-caption">{t(lang, 'v3l_illustration')}</figcaption>
						</figure>
						<p class="step-n"><span class="num">{s.n}</span>{t(lang, `v3l_${s.key}`)}</p>
						<h3 class="step-title">{t(lang, `v3l_${s.key}_title`)}</h3>
						<p class="step-body">{t(lang, `v3l_${s.key}_body`)}</p>
					</li>
				{/each}
			</ol>
		</section>

		<!-- ── 5 · for everyone ─────────────────────────────────────────────── -->
		<section class="sec who wrap" aria-labelledby="land-who">
			<p class="kicker">{t(lang, 'v3l_who_kicker')}</p>
			<h2 class="heading" id="land-who">{t(lang, 'v3l_who_heading')}</h2>
			<ul class="people">
				{#each AUDIENCES as a (a.key)}
					<li class="person" data-audience={a.key}>
						<div class="art">
							<img src={a.art} alt={t(lang, 'v3i_art_alt', t(lang, `v3l_who_${a.key}`))} width={KEY_ART.w} height={KEY_ART.h} loading="lazy" decoding="async" />
						</div>
						<div class="person-text">
							<p class="seat">{t(lang, a.seat === 'console' ? 'v3l_seat_console' : 'v3l_seat_public')}</p>
							<h3 class="person-title">
								<a href={a.href} data-sveltekit-reload={reload(a.href)} data-testid="land-audience-link">{t(lang, `v3l_who_${a.key}`)}<Glyph name="arrowR" size={18} /></a>
							</h3>
							<p class="person-body">{t(lang, `v3l_who_${a.key}_body`)}</p>
						</div>
					</li>
				{/each}
			</ul>
		</section>

		<!-- ── 6 · principles ───────────────────────────────────────────────── -->
		<section class="sec rules wrap" id="principles" aria-labelledby="land-rules">
			<p class="kicker">{t(lang, 'v3l_rules_kicker')}</p>
			<h2 class="heading" id="land-rules">{t(lang, 'v3l_rules_heading')}</h2>
			<ul class="principles" data-testid="land-principles">
				{#each PRINCIPLES as p (p.key)}
					<li class="principle" data-principle={p.key}>
						<span class="badge"><Glyph name={p.sign} size={24} /></span>
						<h3 class="principle-title">{t(lang, `v3l_rule_${p.key}`)}</h3>
						<p class="principle-body">{t(lang, `v3l_rule_${p.key}_body`)}</p>
					</li>
				{/each}
			</ul>
		</section>

		<!-- ── 7 · built on ─────────────────────────────────────────────────── -->
		<section class="sec built wrap" aria-labelledby="land-built">
			<p class="kicker">{t(lang, 'v3l_built_kicker')}</p>
			<h2 class="heading" id="land-built">{t(lang, 'v3l_built_heading')}</h2>
			<ul class="bases">
				{#each BUILT as b (b.key)}
					<li class="base" data-base={b.key}>
						<div class="base-marks">
							{#each marks(b.marks) as m (m.key)}
								<AgencyMark role={m.key} mark={m} {lang} size={40} />
							{/each}
							{#if b.sign}<span class="badge"><Glyph name={b.sign} size={22} /></span>{/if}
						</div>
						<h3 class="base-title">{t(lang, `v3l_built_${b.key}`)}</h3>
						<p class="base-body">{t(lang, `v3l_built_${b.key}_body`)}</p>
					</li>
				{/each}
			</ul>
			<div class="marks" data-testid="land-marks">
				<h3 class="marks-title">{t(lang, 'v3l_marks_heading')}</h3>
				<ul class="mark-row">
					{#each row as m (m.key)}
						<li title={markName(m.key, m, lang)}><AgencyMark role={m.key} mark={m} {lang} size={48} /></li>
					{/each}
				</ul>
				<p class="marks-credit" data-testid="land-marks-credit">{t(lang, 'v3i_marks_credit')}</p>
			</div>
		</section>

		<!-- ── 8 · the closing band ─────────────────────────────────────────── -->
		<section class="end" aria-labelledby="land-end">
			<div class="end-photo" data-testid="land-end-photo">
				<Cover art="" alt="" photo={end} {lang} sizes="100vw" class="land-cover" />
			</div>
			<div class="end-body wrap">
				<img class="end-mark" src="/brand/sajag-mark.svg" alt="" width="64" height="64" />
				<h2 class="heading" id="land-end">{t(lang, 'v3l_end_heading')}</h2>
				<p class="end-tagline">{t(lang, 'v3l_tagline_lead')} <span class="t-turn">{t(lang, 'v3l_tagline_turn')}</span></p>
				<p class="lead">{t(lang, 'v3l_end_body')}</p>
				<div class="ctas">
					<a class="btn btn-primary" href={HREF.console} data-sveltekit-reload>{t(lang, 'v3l_open_console')}<Glyph name="arrowR" size={20} /></a>
					<a class="btn btn-ghost" href={HREF.citizen}>{t(lang, 'v3l_check_road')}</a>
				</div>
				<a class="text-link" href={HREF.driver}>{t(lang, 'v3l_driver_page')}<Glyph name="arrowR" size={16} /></a>
			</div>
		</section>
	</main>

	<!-- ── 9 · footer ───────────────────────────────────────────────────────── -->
	<footer class="foot wrap" data-testid="land-footer">
		<div class="foot-top">
			<img class="foot-lockup" src="/brand/sajag-lockup.svg" alt={t(lang, 'v3l_logo')} width="114" height="38" />
			<LangSwitch {lang} label={t(lang, 'v3l_lang')} {onpick} />
		</div>
		<div class="foot-cols">
			<nav class="foot-col" aria-label={t(lang, 'v3l_foot_pages')}>
				<h2 class="foot-h">{t(lang, 'v3l_foot_pages')}</h2>
				<a href={HREF.console} data-sveltekit-reload>{t(lang, 'v3l_foot_console')}</a>
				<a href={HREF.citizen}>{t(lang, 'v3l_foot_citizen')}</a>
				<a href={HREF.driver}>{t(lang, 'v3l_foot_driver')}</a>
				<a href={HREF.source} rel="noopener noreferrer" data-testid="land-source">{t(lang, 'v3l_foot_source')}</a>
			</nav>
			<div class="foot-col foot-credits" data-testid="land-credits">
				<h2 class="foot-h">{t(lang, 'v3l_foot_credits')}</h2>
				<p>{t(lang, 'v3l_foot_osm')} {t(lang, 'v3l_foot_code')}</p>
				<p>{t(lang, 'v3i_photos_credit')} <a href={HREF.photoCredits}>{t(lang, 'v3i_photos_link')}</a></p>
				<p>{t(lang, 'v3i_art_credit')}</p>
				<p>{t(lang, 'v3i_marks_credit')}</p>
				<p>{t(lang, 'v3l_foot_proto')}</p>
			</div>
		</div>
	</footer>
</div>

<style>
	/* ── the page ───────────────────────────────────────────────────────────── */
	.land {
		--gut: 64px;
		position: relative;
		min-height: 100vh;
		overflow-x: clip;
		background: var(--v3-bg);
		color: var(--v3-t1);
		font-family: var(--v-font-ui);
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
		font-feature-settings: 'cv11', 'ss01';
		-webkit-font-smoothing: antialiased;
	}

	/* the root layout pins html/body for the console's full-height shells; this page scrolls as a document */
	:global(html:has([data-landing])),
	:global(body:has([data-landing])) {
		height: auto;
		overflow: visible auto;
		background: var(--v3-bg);
	}

	.land:lang(hi),
	.land:lang(mr) {
		line-height: 1.7;
	}

	/* Devanagari and Marathi carry marks above and below the line: the poster type needs the room */
	.land:lang(hi) .heading,
	.land:lang(mr) .heading,
	.land:lang(hi) .statement,
	.land:lang(mr) .statement {
		line-height: 1.2;
	}

	.wrap {
		width: min(100% - 2 * var(--gut), var(--v3-land-max));
		margin-inline: auto;
	}

	.wrap-wide {
		width: min(100% - 2 * var(--gut), calc(var(--v3-land-max) + 240px));
		margin-inline: auto;
	}

	.skip {
		position: absolute;
		left: 12px;
		top: -64px;
		z-index: 30;
		padding: 10px 16px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		font-weight: 650;
		text-decoration: none;
	}

	.skip:focus {
		top: 12px;
	}

	main:focus {
		outline: 0;
	}

	a:focus-visible,
	.btn:focus-visible {
		outline: 2px solid var(--v3-brand-text);
		outline-offset: 3px;
	}

	/* ── buttons (the console's pill: 56 px, radius 28) ─────────────────────── */
	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		height: var(--v3-ctl-xl);
		padding: 0 28px;
		border-radius: 28px;
		font-size: 17px;
		font-weight: 650;
		text-decoration: none;
		white-space: nowrap;
		transition:
			background var(--v3-dur-1),
			box-shadow var(--v3-dur-1),
			transform var(--v3-dur-1);
	}

	.btn-primary {
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
	}

	.btn-primary:hover {
		background: var(--v3-primary-hover);
	}

	.btn-ghost {
		background: var(--v3-glass);
		box-shadow: inset 0 0 0 1px var(--v3-line-3);
		color: var(--v3-t1);
	}

	.btn-ghost:hover {
		box-shadow: inset 0 0 0 1px var(--v3-t2);
	}

	.btn-sm {
		height: var(--v3-ctl-lg);
		padding: 0 20px;
		border-radius: 22px;
		font-size: var(--v3-text-body);
	}

	/* ── 1 · the poster ─────────────────────────────────────────────────────── */
	.hero {
		position: relative;
		display: flex;
		flex-direction: column;
		height: 100vh;
		height: 100svh;
		min-height: 700px;
		max-height: 1200px;
		overflow: hidden;
		isolation: isolate;
	}

	/* the reference photo (drawn by Cover, which captions it on the picture); on wide screens it is placed against the
	   whole hero (.hero-body stays static), on phones against the words */
	.hero-photo {
		position: absolute;
		inset: 0 0 0 auto;
		z-index: -2;
		width: 78%;
		animation: land-drift 1.8s var(--v3-ease) both;
	}

	.hero-photo :global(figure.land-cover),
	.end-photo :global(figure.land-cover) {
		height: 100%;
		background: var(--v3-bg);
	}

	/* the photo calmed towards the neutral ground: the bridge's steel stays, its coloured lamps go quiet */
	.hero-photo :global(figure.land-cover > img) {
		object-position: 64% 38%;
		filter: saturate(0.35) contrast(1.05) brightness(0.92);
	}

	/* the photo melts into the night ground: from the left (under the words) and at the foot — over the picture, under
	   its caption (Cover lifts the caption above) */
	.hero-photo::after,
	.end-photo::after {
		content: '';
		position: absolute;
		inset: 0;
		pointer-events: none;
	}

	.hero-photo::after {
		background:
			linear-gradient(90deg, var(--v3-bg) 0%, var(--v3-scrim-mid) 18%, var(--v3-scrim-soft) 42%, var(--v3-scrim-none) 68%),
			linear-gradient(180deg, var(--v3-scrim-soft) 0%, var(--v3-scrim-none) 22%),
			linear-gradient(0deg, var(--v3-bg) 0%, var(--v3-scrim-soft) 16%, var(--v3-scrim-none) 34%);
	}

	/* Cover's caption, on one line at the picture's foot, aligned with the page's right edge */
	.hero-photo :global(figure.land-cover .ref),
	.end-photo :global(figure.land-cover .ref) {
		flex-direction: row;
		flex-wrap: wrap;
		justify-content: flex-end;
		gap: 0 8px;
		padding: 0 max(var(--gut), calc((100vw - var(--v3-land-max) - 240px) / 2)) 28px var(--gut);
		background: none;
	}

	.nav {
		position: relative;
		z-index: 2;
		display: flex;
		flex: none;
		align-items: center;
		gap: 20px;
		padding-top: 28px;
	}

	.nav-mark {
		display: inline-flex;
		flex: none;
		margin-right: auto;
		border-radius: var(--v3-radius-s);
	}

	.nav-mark img {
		display: block;
		width: 40px;
		height: 40px;
	}

	.nav-links {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.nav-links a {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		padding: 0 14px;
		border-radius: 22px;
		color: var(--v3-t2);
		font-size: var(--v3-text-body);
		font-weight: 600;
		text-decoration: none;
		white-space: nowrap;
	}

	.nav-links a:hover {
		color: var(--v3-t1);
	}

	.hero-body {
		display: flex;
		flex: 1;
		align-items: center;
		min-height: 0;
	}

	.hero-copy {
		max-width: 760px;
		padding-bottom: 72px;
	}

	.hero-copy > * {
		animation: land-rise 900ms var(--v3-ease) both;
	}

	.hero-copy > :nth-child(2) {
		animation-delay: 60ms;
	}

	.hero-copy > :nth-child(3) {
		animation-delay: 120ms;
	}

	.hero-copy > :nth-child(4) {
		animation-delay: 180ms;
	}

	.hero-copy > :nth-child(n + 5) {
		animation-delay: 240ms;
	}

	.eyebrow {
		margin: 0 0 22px;
		color: var(--v3-t2);
		font-size: var(--v3-text-body);
		font-weight: 600;
		line-height: var(--v3-lh-body);
	}

	.lockup {
		margin: 0;
		line-height: 0;
	}

	.lockup img {
		display: block;
		width: auto;
		height: var(--v3-land-lockup);
		/* the lockup's own side bearing: the road's round end starts 10/64 in */
		margin-left: calc(var(--v3-land-lockup) * -0.1);
	}

	/* the tagline is the poster, in the reader's language: the lead in grey, the turn in white (no colour: type only) */
	.tagline {
		margin: 40px 0 0;
		font-size: clamp(52px, 5.2vw, var(--v3-land-hero));
		font-weight: 650;
		line-height: 1.04;
	}

	.tagline > span {
		display: block;
	}

	.t-lead {
		color: var(--v3-t3);
	}

	.t-turn {
		color: var(--v3-t1);
	}

	.land:lang(hi) .tagline,
	.land:lang(mr) .tagline {
		line-height: 1.24;
	}

	/* the console itself, in a window over the photo; its honest caption sits on the picture */
	.window {
		position: absolute;
		right: max(var(--gut), calc((100% - var(--v3-land-max) - 240px) / 2));
		bottom: 96px;
		z-index: 1;
		width: clamp(440px, 38vw, 720px);
		margin: 0;
		aspect-ratio: 16 / 10;
		overflow: hidden;
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
		box-shadow:
			0 0 0 1px var(--v3-line-3),
			var(--v3-elev-2);
		animation: land-rise 1.1s 280ms var(--v3-ease) both;
	}

	.window img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: 0 0;
	}

	.shot-tag {
		position: absolute;
		left: 12px;
		bottom: 12px;
		padding: 4px 10px;
		border-radius: 12px;
		background: var(--v3-glass);
		box-shadow: inset 0 0 0 1px var(--v3-line-2);
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		font-weight: 600;
		line-height: var(--v3-lh-micro);
	}

	.sub {
		max-width: 600px;
		margin: 28px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-land-lead);
		line-height: var(--v3-land-lh-lead);
		text-wrap: pretty;
	}

	.ctas {
		display: flex;
		flex-wrap: wrap;
		gap: 14px;
		margin-top: 40px;
	}

	.rule {
		display: flex;
		align-items: center;
		gap: 10px;
		margin: 28px 0 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.rule :global(.v3-glyph) {
		color: var(--v3-t2);
	}

	.cap {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	/* ── the sections ──────────────────────────────────────────────────────── */
	.sec {
		padding: 168px 0 0;
	}

	.kicker {
		margin: 0 0 20px;
		color: var(--v3-brand-text);
		font-size: var(--v3-text-sub);
		font-weight: 650;
		line-height: var(--v3-lh-sub);
	}

	.heading {
		max-width: 920px;
		margin: 0;
		font-size: var(--v3-land-section);
		font-weight: 600;
		line-height: var(--v3-land-lh-section);
		text-wrap: balance;
	}

	.lead {
		max-width: 720px;
		margin: 24px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-land-lead);
		line-height: var(--v3-land-lh-lead);
		text-wrap: pretty;
	}

	ul,
	ol {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	/* 2 · the city */
	.city {
		padding-top: 72px;
	}

	.city-head {
		max-width: 920px;
	}

	.city-strip {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		gap: 16px;
		margin-top: 48px;
	}

	.city-strip :global(figure.city-cover) {
		aspect-ratio: 4 / 5;
		border-radius: var(--v3-radius-l);
		box-shadow: 0 0 0 1px var(--v3-line-2);
	}

	/* the whole credit, never cut short */
	.city-strip :global(figure.city-cover .credit) {
		white-space: normal;
	}

	.end-tagline {
		margin: 20px 0 0;
		color: var(--v3-t3);
		font-size: var(--v3-land-section);
		font-weight: 650;
		line-height: 1.25;
	}

	/* 3 · the problem */
	.statement {
		max-width: 1120px;
		margin: 0;
		font-size: var(--v3-land-section);
		font-weight: 600;
		line-height: var(--v3-land-lh-section);
		text-wrap: balance;
	}

	.figures {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 48px;
		margin-top: 96px;
	}

	.figure {
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding-top: 28px;
		border-top: 1px solid var(--v3-line-3);
	}

	.fig-value {
		font-size: var(--v3-land-figure);
		font-weight: 600;
		line-height: var(--v3-land-lh-figure);
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}

	.fig-value.fig-pending {
		align-self: flex-start;
		padding: 6px 16px;
		border: 1px dashed var(--v3-dashed);
		border-radius: 24px;
		color: var(--v3-t2);
		font-size: var(--v3-text-title);
		line-height: var(--v3-lh-title);
		white-space: normal;
	}

	.fig-label {
		max-width: 360px;
		color: var(--v3-t2);
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
	}

	.modelled {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px 14px;
		max-width: 980px;
		margin: 40px 0 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.tag-dashed {
		display: inline-flex;
		align-items: center;
		min-height: 28px;
		padding: 2px 12px;
		border: 1px dashed var(--v3-dashed);
		border-radius: 14px;
		color: var(--v3-t2);
		font-weight: 650;
	}

	/* 3 · how it works */
	.steps {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 32px;
		margin-top: 72px;
	}

	.step {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.frame {
		display: flex;
		flex-direction: column;
		gap: 12px;
		margin: 0 0 28px;
	}

	.frame img {
		display: block;
		width: 100%;
		height: auto;
		aspect-ratio: 16 / 9;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
		box-shadow:
			0 0 0 1px var(--v3-line-2),
			var(--v3-elev-1);
	}

	.step-n {
		display: flex;
		align-items: center;
		gap: 12px;
		margin: 0;
		color: var(--v3-brand-text);
		font-size: var(--v3-text-sub);
		font-weight: 650;
		line-height: var(--v3-lh-sub);
	}

	.num {
		display: inline-grid;
		place-items: center;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		background: var(--v3-brand-veil);
		color: var(--v3-t1);
		font-size: var(--v3-text-meta);
		font-variant-numeric: tabular-nums;
	}

	.step-title,
	.person-title,
	.principle-title,
	.base-title {
		margin: 14px 0 0;
		font-size: var(--v3-text-title);
		font-weight: 600;
		line-height: var(--v3-lh-title);
	}

	.step-body,
	.person-body,
	.principle-body,
	.base-body {
		text-wrap: pretty;
		margin: 12px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
	}

	/* 4 · for everyone */
	.people {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 24px;
		margin-top: 72px;
	}

	.person {
		position: relative;
		display: flex;
		flex-direction: column;
		min-width: 0;
		overflow: hidden;
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
		box-shadow: inset 0 0 0 1px var(--v3-line-1);
		transition: box-shadow var(--v3-dur-2);
	}

	.person:hover,
	.person:focus-within {
		box-shadow: inset 0 0 0 1px var(--v3-line-3);
	}

	.art {
		aspect-ratio: 16 / 9;
		overflow: hidden;
		background: var(--v3-s2);
	}

	.art img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
		transition: transform var(--v3-dur-3) var(--v3-ease);
	}

	.person:hover .art img {
		transform: scale(1.03);
	}

	.person-text {
		display: flex;
		flex-direction: column;
		flex: 1;
		padding: 24px 24px 28px;
	}

	.seat {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		font-weight: 600;
		line-height: var(--v3-lh-meta);
	}

	.person-title {
		margin-top: 6px;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
	}

	.person-title a {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		color: var(--v3-t1);
		text-decoration: none;
	}

	/* the whole card is the link's target */
	.person-title a::after {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: inherit;
	}

	.person-title :global(.v3-glyph) {
		color: var(--v3-t3);
		transition:
			transform var(--v3-dur-2) var(--v3-ease),
			color var(--v3-dur-2);
	}

	.person:hover .person-title :global(.v3-glyph) {
		color: var(--v3-t1);
		transform: translateX(3px);
	}

	.person-body {
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
	}

	/* 5 · principles */
	.principles {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 56px 48px;
		margin-top: 72px;
	}

	.principle {
		min-width: 0;
		padding-top: 28px;
		border-top: 1px solid var(--v3-line-2);
	}

	.badge {
		display: inline-grid;
		flex: none;
		place-items: center;
		width: 48px;
		height: 48px;
		border-radius: 50%;
		background: var(--v3-s2);
		box-shadow: inset 0 0 0 1px var(--v3-line-2);
		color: var(--v3-t1);
	}

	.principle-title {
		margin-top: 20px;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
	}

	.principle-body {
		max-width: 400px;
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
	}

	/* 6 · built on */
	.bases {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 24px;
		margin-top: 72px;
	}

	.base {
		display: flex;
		flex-direction: column;
		min-width: 0;
		padding: 28px;
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
		box-shadow: inset 0 0 0 1px var(--v3-line-1);
	}

	.base-marks {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: 48px;
	}

	.base-title {
		margin-top: 22px;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
	}

	.base-body {
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
	}

	.marks {
		margin-top: 72px;
		padding-top: 40px;
		border-top: 1px solid var(--v3-line-2);
	}

	.marks-title {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-sub);
		font-weight: 600;
		line-height: var(--v3-lh-sub);
	}

	.mark-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 16px 28px;
		margin-top: 28px;
	}

	.mark-row li {
		display: inline-flex;
	}

	.marks-credit {
		max-width: 720px;
		margin: 24px 0 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	/* 7 · the closing band */
	.end {
		position: relative;
		display: flex;
		align-items: center;
		min-height: 680px;
		margin-top: 96px;
		overflow: hidden;
		isolation: isolate;
	}

	.end-photo {
		position: absolute;
		inset: 0;
		z-index: -1;
	}

	.end-photo :global(figure.land-cover > img) {
		object-position: 50% 58%;
	}

	.end-photo::after {
		background:
			linear-gradient(180deg, var(--v3-bg) 0%, var(--v3-scrim-mid) 10%, var(--v3-scrim-soft) 26%, var(--v3-scrim-none) 48%, var(--v3-scrim-none) 74%, var(--v3-bg) 100%),
			linear-gradient(90deg, var(--v3-photo-scrim) 0%, var(--v3-photo-scrim) 24%, var(--v3-photo-scrim-soft) 52%, var(--v3-photo-scrim-none) 78%);
	}

	.end-body {
		padding: 120px 0;
	}

	.end-body .lead {
		max-width: 600px;
	}

	.end-mark {
		display: block;
		width: 56px;
		height: 56px;
		margin: 0 0 28px -9px;
	}

	.text-link {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 44px;
		margin-top: 18px;
		color: var(--v3-t2);
		font-weight: 600;
		text-decoration: none;
	}

	.text-link:hover {
		color: var(--v3-t1);
	}

	/* 8 · footer */
	.foot {
		padding: 72px 0 64px;
	}

	.foot-top {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 24px;
		padding-bottom: 40px;
		border-bottom: 1px solid var(--v3-line-2);
	}

	.foot-lockup {
		display: block;
		width: auto;
		height: 36px;
		margin-left: -6px;
	}

	.foot-cols {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
		gap: 48px;
		padding-top: 40px;
	}

	.foot-col {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 4px;
		min-width: 0;
	}

	.foot-h {
		margin: 0 0 12px;
		color: var(--v3-t1);
		font-size: var(--v3-text-body);
		font-weight: 650;
		line-height: var(--v3-lh-body);
	}

	.foot-col a {
		display: inline-flex;
		align-items: center;
		min-height: 36px;
		color: var(--v3-t2);
		text-decoration: none;
	}

	.foot-col a:hover {
		color: var(--v3-t1);
	}

	.foot-credits p {
		max-width: 760px;
		margin: 0 0 10px;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.foot-credits a {
		display: inline;
		min-height: 0;
		color: var(--v3-brand-text);
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	/* ── motion (subtle; none for readers who ask for less) ─────────────────── */
	@keyframes land-rise {
		from {
			opacity: 0;
			transform: translateY(18px);
		}
		to {
			opacity: 1;
			transform: none;
		}
	}

	@keyframes land-drift {
		from {
			opacity: 0;
			transform: scale(1.06);
		}
		to {
			opacity: 1;
			transform: none;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.hero-photo,
		.hero-copy > *,
		.window {
			animation: none;
		}

		.art img,
		.person-title :global(.v3-glyph),
		.btn {
			transition: none;
		}

		.person:hover .art img {
			transform: none;
		}
	}

	/* ── 1366-class: the console's compact step (the tokens step down too) ──── */
	@media (max-width: 1500px) {
		.land {
			--gut: 48px;
		}

		.sec {
			padding-top: 136px;
		}

		.hero-copy {
			max-width: 680px;
		}

		.window {
			width: clamp(420px, 40vw, 600px);
			bottom: 80px;
		}

		.people {
			gap: 20px;
		}

		.person-text {
			padding: 20px 20px 24px;
		}
	}

	/* ── short laptop screens (1366 × 768): the poster tightens to fit one view ─ */
	@media (max-height: 860px) and (min-width: 1101px) {
		.lockup img {
			height: 48px;
		}

		.tagline {
			margin-top: 24px;
			font-size: 68px;
		}

		.window {
			width: clamp(400px, 36vw, 560px);
			bottom: 64px;
		}

		.sub {
			margin-top: 20px;
		}

		.ctas {
			margin-top: 28px;
		}

		.rule {
			margin-top: 18px;
		}

		.hero-copy {
			padding-bottom: 40px;
		}
	}

	/* ── tablets and small laptops: the window joins the flow ───────────────── */
	@media (max-width: 1100px) {
		.nav-links {
			display: none;
		}

		.hero {
			height: auto;
			max-height: none;
			min-height: 0;
		}

		/* the photo now sits behind the words only, edge to edge (and up behind the bar) */
		.hero-body {
			position: relative;
			isolation: isolate;
			padding-top: 120px;
		}

		.hero-photo {
			inset: -100px calc(-1 * var(--gut)) 0;
			z-index: -1;
			width: auto;
		}

		/* the photo runs one gutter past each edge: its caption keeps the page's gutter, inside the screen */
		.hero-photo :global(figure.land-cover .ref) {
			justify-content: flex-start;
			padding: 0 calc(2 * var(--gut)) 16px;
		}

		.hero-copy {
			padding-bottom: 40px;
		}

		.window {
			position: relative;
			right: auto;
			bottom: auto;
			width: min(100% - 2 * var(--gut), 760px);
			margin: 8px auto 0;
		}

		.city-strip {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.steps,
		.principles {
			grid-template-columns: minmax(0, 1fr);
			gap: 56px;
		}

		.people,
		.bases {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.figures {
			grid-template-columns: minmax(0, 1fr);
			gap: 32px;
			margin-top: 64px;
		}
	}

	/* ── phones ─────────────────────────────────────────────────────────────── */
	@media (max-width: 640px) {
		.land {
			--gut: 16px;
		}

		.nav {
			gap: 10px;
			padding-top: 16px;
		}

		.nav-cta {
			display: none;
		}

		/* on a phone the words sit over the whole photo: the lattice dims behind them */
		.hero-photo::after {
			background:
				linear-gradient(180deg, var(--v3-bg) 0%, var(--v3-scrim-soft) 18%, var(--v3-scrim-mid) 52%, var(--v3-bg) 100%),
				linear-gradient(90deg, var(--v3-scrim-soft) 0%, var(--v3-scrim-none) 100%);
		}

		.hero-body {
			padding-top: 72px;
		}

		.lockup img {
			height: 40px;
		}

		.tagline {
			margin-top: 24px;
			font-size: 40px;
		}

		.city-strip {
			grid-template-columns: minmax(0, 1fr);
		}

		.end-tagline {
			font-size: 34px;
		}

		.sub {
			margin-top: 20px;
			font-size: var(--v3-text-sub);
			line-height: var(--v3-lh-sub);
		}

		.ctas {
			flex-direction: column;
			align-items: stretch;
			margin-top: 28px;
		}

		.sec {
			padding-top: 104px;
		}

		.heading,
		.statement {
			font-size: 34px;
			line-height: 42px;
		}

		.lead {
			font-size: var(--v3-text-sub);
			line-height: var(--v3-lh-sub);
		}

		.fig-value {
			font-size: 56px;
			line-height: 60px;
		}

		.fig-value.fig-pending {
			font-size: var(--v3-text-heading);
			line-height: var(--v3-lh-heading);
		}

		.steps,
		.people,
		.principles,
		.bases {
			grid-template-columns: minmax(0, 1fr);
			margin-top: 48px;
		}

		.end {
			min-height: 560px;
			margin-top: 104px;
		}

		.end-body {
			padding: 88px 0 120px;
		}

		.foot-cols {
			grid-template-columns: minmax(0, 1fr);
			gap: 32px;
		}
	}
</style>
