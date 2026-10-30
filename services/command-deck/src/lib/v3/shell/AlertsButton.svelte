<script lang="ts">
	/**
	 * AlertsButton (V3-SPEC §5.1, §7.3) — the bell: an orange dot while something is unread; its popover
	 * lists the alerts of this visit (newest first, Today / Earlier), each a link to where it is decided,
	 * "Mark all read", and the alert chime switch (ON by default, soft, remembered in this browser; the
	 * rule for emulated and test decisions is stated under the switch — alerts.svelte.ts holds it).
	 *
	 * The shell feeds it: V3Shell passes the page's decision list (v3Bar.decisions, masked titles) and the
	 * console's exercise statement (commandBar.exercise) to v3Alerts.syncDecisions. Never a modal, never
	 * a toast for a decision.
	 */
	import { t } from '$lib/i18n/strings';
	import '../packs.v3';
	import Popover from '$lib/ui/Popover.svelte';
	import { fmtStamp } from '$lib/ui/format/format';
	import Glyph from '../Glyph.svelte';
	import { v3Alerts } from './alerts.svelte';

	let { lang }: { lang: string } = $props();

	const unread = $derived(v3Alerts.unread);
	const label = $derived(unread > 0 ? t(lang, 'v3_alerts_new', unread) : t(lang, 'v3_alerts'));
	const readSet = $derived(new Set(v3Alerts.read));
	const startOfDay = $derived.by(() => {
		const d = new Date();
		d.setHours(0, 0, 0, 0);
		return d.getTime();
	});
	const today = $derived(v3Alerts.items.filter((i) => i.at >= startOfDay));
	const earlier = $derived(v3Alerts.items.filter((i) => i.at < startOfDay));
</script>

{#snippet list(items: typeof v3Alerts.items, head: string)}
	{#if items.length}
		<div class="grp">{head}</div>
		<ul>
			{#each items as a (a.key)}
				<li class={[!readSet.has(a.key) && 'unread']}>
					<a href={a.href}>
						<span class="dot" aria-hidden="true"></span>
						<span class="txt"><b>{t(lang, 'v3_alert_decision')}</b><span>{a.title}</span></span>
						<span class="at">{fmtStamp(a.at, Date.now())}</span>
					</a>
				</li>
			{/each}
		</ul>
	{/if}
{/snippet}

<Popover placement="bottom-end" class="v3-pop" aria-label={t(lang, 'v3_alerts_title')} onopenchange={(o) => o || v3Alerts.markAllRead()}>
	<button type="button" class="bell" aria-label={label} title={label} data-testid="v3-alerts" data-unread={unread}>
		<Glyph name="bell" size={22} />
		{#if unread > 0}<span class="badge" aria-hidden="true"></span>{/if}
	</button>
	{#snippet content()}
		<div class="panel" data-v3="alerts-panel">
			<div class="head">
				<span class="h">{t(lang, 'v3_alerts_title')}</span>
				{#if unread > 0}<button type="button" class="link" onclick={() => v3Alerts.markAllRead()}>{t(lang, 'v3_alerts_read')}</button>{/if}
			</div>
			{#if v3Alerts.items.length}
				{@render list(today, t(lang, 'v3_alerts_today'))}
				{@render list(earlier, t(lang, 'v3_alerts_earlier'))}
			{:else}
				<p class="empty">{t(lang, 'v3_alerts_empty')}</p>
			{/if}
			<div class="chime">
				<div class="row">
					<span class="ic"><Glyph name="volume" size={18} /></span>
					<span class="lbl" id="v3-chime-lbl">{t(lang, 'v3_chime')}</span>
					<button
						type="button"
						role="switch"
						class={['sw', v3Alerts.chime && 'on-state']}
						aria-checked={v3Alerts.chime}
						aria-labelledby="v3-chime-lbl"
						title={t(lang, v3Alerts.chime ? 'v3_chime_toggle_off' : 'v3_chime_toggle_on')}
						data-testid="v3-chime"
						onclick={() => v3Alerts.setChime(!v3Alerts.chime)}
					>
						<span class="knob" aria-hidden="true"></span>
						<span class="sw-txt">{t(lang, v3Alerts.chime ? 'v3_chime_on' : 'v3_chime_off')}</span>
					</button>
				</div>
				<p>{t(lang, 'v3_chime_help')}</p>
				<p class="rule">{t(lang, 'v3_chime_rule')}</p>
			</div>
		</div>
	{/snippet}
</Popover>

<style>
	.bell {
		position: relative;
		display: grid;
		place-items: center;
		width: var(--v3-ctl-lg);
		height: var(--v3-ctl-lg);
		border: 0;
		border-radius: 22px;
		background: transparent;
		color: var(--v3-t2);
		cursor: pointer;
	}

	.bell:hover {
		background: var(--v3-s2);
		color: var(--v3-t1);
	}

	.bell:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.badge {
		position: absolute;
		top: 9px;
		right: 10px;
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: var(--v3-decide);
		box-shadow: 0 0 0 2px var(--v3-bg);
	}

	.panel {
		display: flex;
		flex-direction: column;
		gap: 10px;
		width: 360px;
		padding: 16px 16px 14px;
	}

	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.h {
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 620;
	}

	.link {
		padding: 0;
		border: 0;
		background: none;
		color: var(--v3-brand-text);
		font: inherit;
		font-size: var(--v3-text-meta);
		font-weight: 600;
		cursor: pointer;
	}

	.grp {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
	}

	ul {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	li a {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		padding: 8px 8px;
		border-radius: var(--v3-radius-s);
		color: var(--v3-t1);
		text-decoration: none;
	}

	li a:hover {
		background: var(--v3-s3);
	}

	.dot {
		flex: none;
		width: 8px;
		height: 8px;
		margin-top: 6px;
		border-radius: 50%;
		background: transparent;
	}

	li.unread .dot {
		background: var(--v3-decide);
	}

	.txt {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-width: 0;
		font-size: 14px;
		line-height: 19px;
	}

	.txt b {
		font-weight: 620;
	}

	.txt span {
		color: var(--v3-t2);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.at {
		flex: none;
		color: var(--v3-t3);
		font-size: 12px;
	}

	.empty {
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
		line-height: 20px;
	}

	.chime {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding-top: 12px;
		border-top: 1px solid var(--v3-line-1);
	}

	.chime p {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 18px;
	}

	.chime p.rule {
		color: var(--v3-t3);
	}

	.row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.ic {
		display: grid;
		color: var(--v3-t2);
	}

	.lbl {
		flex: 1;
		font-size: 14px;
		font-weight: 600;
	}

	.sw {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 30px;
		padding: 0 12px 0 4px;
		border: 1px solid var(--v3-line-2);
		border-radius: 15px;
		background: var(--v3-s1);
		color: var(--v3-t2);
		font: inherit;
		font-size: 13px;
		font-weight: 650;
		cursor: pointer;
	}

	.knob {
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: var(--v3-s4);
	}

	.sw.on-state {
		color: var(--v3-ok-text);
	}

	.sw.on-state .knob {
		background: var(--v3-ok);
	}

	.sw:focus-visible,
	.link:focus-visible,
	li a:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}
</style>
