<script lang="ts">
	/**
	 * The Explorer's saved views (SPEC §5.3, §7.5): this browser's named
	 * views, newest first. The one in force is `.is-selected` and reads
	 * "edited" once the workspace moves away from it. Open, rename, delete;
	 * "+" saves the view as it is now.
	 *
	 * Masked egress: the store keeps a saved view as a share hash (URNs only)
	 * and a name with every registration mark masked, whoever is on console
	 * (saved-views.ts). Nothing here holds or shows a raw mark.
	 */
	import { tick } from 'svelte';
	import { Button, Icon, Input, Menu, Popover, Section, Tooltip } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.views';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { workspace } from '../../workspace.svelte';
	import { currentView } from './current-view.svelte';
	import { savedSignature, viewSignature } from './model';

	let { lang }: { lang: string } = $props();
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	let open = $state(true);
	let naming = $state(false);
	let draft = $state('');
	let nameEl = $state<HTMLInputElement | null>(null);
	let renaming = $state<string | null>(null);
	let renameDraft = $state('');
	let renameEl = $state<HTMLInputElement | null>(null);

	const views = $derived(workspace.savedViews);
	const nowSig = $derived(
		viewSignature({ view: workspace.view, timeWindow: workspace.timeWindow, filters: workspace.filters, items: selection.items, sel: selection.current }),
	);
	const edited = (hash: string) => savedSignature(hash) !== nowSig;

	async function startNaming() {
		open = true;
		naming = true;
		draft = '';
		await tick();
		nameEl?.focus();
	}

	function save(e?: Event) {
		e?.preventDefault();
		const name = draft.trim();
		if (!name) return;
		const v = workspace.saveView(name);
		currentView.set(v.id);
		naming = false;
		draft = '';
	}

	function apply(id: string) {
		workspace.applyView(id);
		currentView.set(id);
	}

	async function startRename(id: string, name: string) {
		renaming = id;
		renameDraft = name;
		await tick();
		renameEl?.focus();
		renameEl?.select();
	}

	function commitRename(e?: Event) {
		e?.preventDefault();
		if (renaming && renameDraft.trim()) workspace.renameView(renaming, renameDraft);
		renaming = null;
	}

	function remove(id: string) {
		workspace.deleteView(id);
		if (currentView.id === id) currentView.set(null);
	}

	function escapeKey(e: KeyboardEvent, cancel: () => void) {
		if (e.key !== 'Escape') return;
		e.preventDefault();
		e.stopPropagation();
		cancel();
	}
</script>

<Section title={L('vw_sv_title')} sub={views.length || null} collapsible bind:open data-explorer-section="saved-views">
	{#snippet right()}
		<Tooltip content={L('vw_sv_masked_hint')}>
			<button type="button" class="hint" aria-label={L('vw_sv_masked_hint')}><Icon name="lock" size={12} /></button>
		</Tooltip>
		<Button minimal small icon="plus" tooltip={L('vw_sv_save')} aria-label={L('vw_sv_save')} data-testid="saved-view-add" onclick={startNaming} />
	{/snippet}
	{#if naming}
		<form class="namer" onsubmit={save}>
			<Input
				small
				fill
				bind:value={draft}
				bind:inputEl={nameEl}
				placeholder={L('vw_sv_placeholder')}
				aria-label={L('vw_sv_placeholder')}
				maxlength={64}
				data-testid="saved-view-name"
				onkeydown={(e: KeyboardEvent) => escapeKey(e, () => (naming = false))}
			/>
			<Button small intent="primary" type="submit" disabled={!draft.trim()} data-testid="saved-view-save">{L('vw_sv_save_btn')}</Button>
		</form>
	{/if}
	{#if views.length}
		<ul class="list" data-testid="saved-views">
			{#each views as v (v.id)}
				{@const current = currentView.id === v.id}
				<li class={['row', current && 'is-selected']} data-view-id={v.id} data-current={current}>
					{#if renaming === v.id}
						<form class="namer inline" onsubmit={commitRename}>
							<Input
								small
								fill
								bind:value={renameDraft}
								bind:inputEl={renameEl}
								aria-label={L('vw_sv_rename')}
								maxlength={64}
								onkeydown={(e: KeyboardEvent) => escapeKey(e, () => (renaming = null))}
								onblur={() => commitRename()}
							/>
						</form>
					{:else}
						<button type="button" class="main" onclick={() => apply(v.id)}>
							<span class="glyph"><Icon name="bookmark" /></span>
							<span class="label">{v.name}</span>
							{#if current && edited(v.hash)}<span class="sec" data-testid="saved-view-edited">{L('vw_sv_edited')}</span>{/if}
						</button>
						<Popover placement="bottom-end">
							<Button minimal small icon="more" tooltip={L('vw_sv_more')} aria-label={L('vw_sv_more')} class="more-btn" />
							{#snippet content({ close })}
								<Menu
									label={L('vw_sv_more')}
									items={[
										{ id: 'open', label: L('vw_sv_open'), icon: 'folder-open', onclick: () => apply(v.id) },
										{ id: 'rename', label: L('vw_sv_rename'), icon: 'edit', onclick: () => void startRename(v.id, v.name) },
										{ id: 'divider', kind: 'divider' },
										{ id: 'delete', label: L('vw_sv_delete'), icon: 'trash', onclick: () => remove(v.id) },
									]}
									onselect={() => close()}
								/>
							{/snippet}
						</Popover>
					{/if}
				</li>
			{/each}
		</ul>
	{:else if !naming}
		<p class="empty">{L('vw_sv_empty')}</p>
	{/if}
</Section>

<style>
	.namer {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 0 12px 8px 16px;
	}

	.namer.inline {
		flex: 1 1 auto;
		padding: 0 8px 0 0;
	}

	.list {
		margin: 0;
		padding: 0 0 4px;
		list-style: none;
	}

	.row {
		position: relative;
		display: flex;
		align-items: center;
		height: 30px;
		padding: 0 4px 0 16px;
	}

	.row:hover {
		background: var(--v-row-hover);
	}

	.row.is-selected {
		background: var(--v-primary-veil);
		box-shadow: inset 2px 0 0 var(--v-primary-text);
	}

	.main {
		display: flex;
		flex: 1 1 auto;
		align-items: center;
		min-width: 0;
		height: 30px;
		margin: 0;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		font-size: var(--v-text-base);
		text-align: left;
		cursor: pointer;
	}

	.main:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.glyph {
		display: inline-flex;
		margin-right: 8px;
		color: var(--v-ink-2);
	}

	.label {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.sec {
		flex: 0 0 auto;
		padding-left: 8px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.row :global(.more-btn) {
		opacity: 0;
	}

	.row:hover :global(.more-btn),
	.row:focus-within :global(.more-btn),
	.row :global(.more-btn[aria-expanded='true']) {
		opacity: 1;
	}

	.empty {
		margin: 0;
		padding: 0 16px 12px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.hint {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 24px;
		height: 24px;
		margin: 0;
		padding: 0;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: transparent;
		color: var(--v-ink-2);
		cursor: help;
	}

	.hint:focus-visible {
		outline: 2px solid var(--v-focus);
	}

	.hint :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}
</style>
