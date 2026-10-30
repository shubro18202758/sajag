<script lang="ts">
	/**
	 * The Policies popover (SPEC §9.1, §9.3): what this console will never do,
	 * in honest copy. "Full marks show on this console only while a duty
	 * officer is named. Naming one is attribution, not sign-in; every decision
	 * records the name." is verbatim; with the operator gate on, one line says
	 * the name on console is then the signed-in officer's.
	 */
	import type { IconName } from '$lib/design/icons';
	import { t } from '$lib/i18n/strings';
	import Icon from '$lib/ui/Icon.svelte';
	import {
		EMULATED_ICON,
		HISTORY_ICON,
		MASKED_ICON,
		NO_FINE_ICON,
		OFFICER_ICON,
		POLICIES_ICON,
		PURSUIT_ICON
	} from './icons';
	import { operatorSession } from './session.svelte';

	let { lang }: { lang: string } = $props();

	const ITEMS: readonly { id: string; icon: IconName }[] = [
		{ id: 'vehicles', icon: POLICIES_ICON },
		{ id: 'masked', icon: MASKED_ICON },
		{ id: 'people', icon: OFFICER_ICON },
		{ id: 'nofine', icon: NO_FINE_ICON },
		{ id: 'pursuit', icon: PURSUIT_ICON },
		{ id: 'retention', icon: HISTORY_ICON },
		{ id: 'exercise', icon: EMULATED_ICON }
	];
</script>

<div class="panel" data-shell="policies-panel">
	<div class="head">{t(lang, 'shell_policies_title')}</div>
	<ul class="items">
		{#each ITEMS as it (it.id)}
			<li class="item" data-policy={it.id}>
				<Icon name={it.icon} size={16} />
				<div class="text">
					<div class="title">{t(lang, `pol_${it.id}_title`)}</div>
					<div class="body">{t(lang, `pol_${it.id}_body`)}</div>
					{#if it.id === 'masked' && operatorSession.gate === true}
						<div class="body">{t(lang, 'pol_masked_gate')}</div>
					{/if}
				</div>
			</li>
		{/each}
	</ul>
</div>

<style>
	.panel {
		box-sizing: border-box;
		width: 380px;
		max-width: calc(100vw - 16px);
		padding: 12px 16px 8px;
		font-family: var(--v-font-ui);
	}

	.head {
		margin-bottom: 4px;
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: calc(var(--v-text-base) + 2px);
	}

	.items {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.item {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		padding: 8px 0;
		border-bottom: 1px solid var(--v-line-1);
	}

	.item:last-child {
		border-bottom: 0;
	}

	.item > :global([data-ui='icon']) {
		margin-top: 1px;
		color: var(--v-ink-2);
	}

	.text {
		min-width: 0;
	}

	.title {
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: calc(var(--v-text-base) + 4px);
	}

	.body {
		margin-top: 2px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}
</style>
