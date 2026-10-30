<script lang="ts">
	/**
	 * HotkeysDialog — the shortcuts sheet (`?`). Groups of key combinations
	 * and what they do; with no `groups` it shows the deck's global set
	 * (SPEC §1.9) and its rule: no single key approves, unmasks, penalises,
	 * dispatches or publishes. Built on Dialog (Escape closes, focus trapped).
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import Dialog from './Dialog.svelte';
	import Kbd from './Kbd.svelte';
	import Note from './Note.svelte';
	import { uiLang, ut } from './lang';
	import type { HotkeyGroup } from './types';

	interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
		open?: boolean;
		groups?: readonly HotkeyGroup[] | null;
		onclose?: () => void;
		lang?: string;
	}

	let { open = $bindable(false), groups = null, onclose, lang, ...rest }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());

	const defaults = $derived<HotkeyGroup[]>([
		{
			title: ut(L, 'ui_hk_global'),
			keys: [
				{ combo: ['Ctrl', 'K'], label: ut(L, 'ui_hk_omnibar') },
				{ combo: ['/'], label: ut(L, 'ui_hk_search') },
				{ combo: ['?'], label: ut(L, 'ui_hk_help') },
				{ combo: ['Esc'], label: ut(L, 'ui_hk_escape') }
			]
		},
		{
			title: ut(L, 'ui_hk_docks'),
			keys: [
				{ combo: ['['], label: ut(L, 'ui_hk_left_dock') },
				{ combo: [']'], label: ut(L, 'ui_hk_right_dock') },
				{ combo: ['\\'], label: ut(L, 'ui_hk_timeline') }
			]
		},
		{
			title: ut(L, 'ui_hk_lists'),
			keys: [
				{ combo: ['J'], label: ut(L, 'ui_hk_next') },
				{ combo: ['K'], label: ut(L, 'ui_hk_prev') },
				{ combo: ['Enter'], label: ut(L, 'ui_hk_open') }
			]
		}
	]);
	const list = $derived(groups ?? defaults);
</script>

<Dialog bind:open title={ut(L, 'ui_hotkeys_title')} icon="key-command" width={640} {onclose} lang={L} data-ui-kind="hotkeys" {...rest}>
	<div class="groups" data-ui="hotkeys-dialog">
		{#each list as g (g.title)}
			<section class="group">
				<h3 class="gt">{g.title}</h3>
				<dl>
					{#each g.keys as k (k.label)}
						<div class="row">
							<dt><Kbd keys={k.combo} /></dt>
							<dd>{k.label}</dd>
						</div>
					{/each}
				</dl>
				{#if g.note}<Note icon="info-sign" text={g.note} />{/if}
			</section>
		{/each}
	</div>
	{#if !groups}<div class="rule"><Note icon="shield" text={ut(L, 'ui_hk_rule')} /></div>{/if}
</Dialog>

<style>
	.groups {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px 24px;
	}

	.gt {
		margin: 0 0 8px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 600;
		line-height: calc(var(--v-text-xs) + 4px);
	}

	dl {
		margin: 0;
	}

	.row {
		display: grid;
		grid-template-columns: 72px minmax(0, 1fr);
		align-items: center;
		gap: 12px;
		min-height: 28px;
		border-bottom: 1px solid var(--v-line-1);
	}

	dt,
	dd {
		margin: 0;
	}

	dd {
		font-size: var(--v-text-base);
	}

	.rule {
		margin-top: 16px;
	}
</style>
