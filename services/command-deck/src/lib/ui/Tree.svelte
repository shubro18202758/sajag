<script lang="ts">
	/**
	 * Tree — nested rows (the layer tree, the explorer). 30 px rows, a 30 px
	 * caret box, an optional glyph, a label that ellipsises, a secondary
	 * label and an `end` snippet per row (an EyeToggle, a count). A selected
	 * row uses .is-selected (the data active-state rule); a `dim` row reads
	 * as empty (e.g. "None now").
	 *
	 * Expansion: `node.expanded` seeds it; the tree keeps its own state and
	 * reports with ontoggle. Keyboard: one tab stop (roving tabindex: the
	 * focused row, else the selected row in view, else the first row); Up/Down
	 * move, Right expands or enters, Left collapses or goes to the parent,
	 * Enter/Space selects.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import Icon from './Icon.svelte';
	import { uiLang, ut } from './lang';
	import type { TreeNode } from './types';

	interface Props extends Omit<HTMLAttributes<HTMLUListElement>, 'ontoggle'> {
		nodes: readonly TreeNode[];
		onnodeclick?: (node: TreeNode, e: MouseEvent | KeyboardEvent) => void;
		ontoggle?: (node: TreeNode, expanded: boolean) => void;
		end?: Snippet<[TreeNode]>;
		label?: string;
		lang?: string;
	}

	let { nodes, onnodeclick, ontoggle, end, label, lang, class: cls = '', ...rest }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	let open = $state<Record<string, boolean>>({});
	let root: HTMLUListElement | undefined = $state();

	const isOpen = (n: TreeNode) => open[n.id] ?? !!n.expanded;

	// ── one tab stop ─────────────────────────────────────────────────────
	let focusedId = $state<string | null>(null);
	/** The rows in view, in order (children of collapsed nodes are not rendered). */
	function shown(list: readonly TreeNode[], out: TreeNode[] = []): TreeNode[] {
		for (const n of list) {
			out.push(n);
			if (n.childNodes?.length && isOpen(n)) shown(n.childNodes, out);
		}
		return out;
	}
	const tabStop = $derived.by(() => {
		const rows = shown(nodes);
		if (focusedId && rows.some((n) => n.id === focusedId)) return focusedId;
		return (rows.find((n) => n.selected && !n.disabled) ?? rows[0])?.id ?? null;
	});

	function toggle(n: TreeNode, e?: Event) {
		e?.stopPropagation();
		const next = !isOpen(n);
		open[n.id] = next;
		ontoggle?.(n, next);
	}

	function rows(): HTMLElement[] {
		return root ? Array.from(root.querySelectorAll<HTMLElement>('[data-tree-row]')) : [];
	}

	function onKey(e: KeyboardEvent, n: TreeNode, parentId: string | null) {
		const list = rows();
		const i = list.indexOf(e.currentTarget as HTMLElement);
		const hasKids = !!n.childNodes?.length;
		if (e.key === 'ArrowDown') list[i + 1]?.focus();
		else if (e.key === 'ArrowUp') list[i - 1]?.focus();
		else if (e.key === 'ArrowRight' && hasKids) {
			if (!isOpen(n)) toggle(n);
			else list[i + 1]?.focus();
		} else if (e.key === 'ArrowLeft') {
			if (hasKids && isOpen(n)) toggle(n);
			else if (parentId) list.find((r) => r.dataset.treeRow === parentId)?.focus();
		} else if (e.key === 'Enter' || e.key === ' ') {
			if (!n.disabled) onnodeclick?.(n, e);
		} else return;
		e.preventDefault();
	}
</script>

{#snippet branch(list: readonly TreeNode[], depth: number, parentId: string | null)}
	{#each list as n (n.id)}
		{@const kids = !!n.childNodes?.length}
		<li role="none">
			<div
				role="treeitem"
				aria-level={depth + 1}
				aria-expanded={kids ? isOpen(n) : undefined}
				aria-selected={n.selected ? 'true' : 'false'}
				aria-disabled={n.disabled || undefined}
				tabindex={n.id === tabStop ? 0 : -1}
				data-tree-row={n.id}
				class={['row', n.selected && 'is-selected', n.dim && 'dim', n.disabled && 'disabled']}
				style:padding-left="{depth * 20}px"
				onclick={(e) => !n.disabled && onnodeclick?.(n, e)}
				onkeydown={(e) => onKey(e, n, parentId)}
				onfocus={() => (focusedId = n.id)}
				{...n.attrs}
			>
				{#if kids}
					<button
						type="button"
						class="caret"
						tabindex="-1"
						aria-label={ut(L, isOpen(n) ? 'ui_collapse' : 'ui_expand')}
						onclick={(e) => toggle(n, e)}
					>
						<Icon name={isOpen(n) ? 'chevron-down' : 'chevron-right'} size={16} />
					</button>
				{:else}
					<span class="caret none" aria-hidden="true"></span>
				{/if}
				{#if n.icon}<span class="glyph"><Icon name={n.icon} size={16} /></span>{/if}
				<span class="label">{n.label}</span>
				{#if n.secondaryLabel}<span class="sec">{n.secondaryLabel}</span>{/if}
				{#if end}<span class="end">{@render end(n)}</span>{/if}
			</div>
			{#if kids && isOpen(n)}
				<ul role="group" class="tree">{@render branch(n.childNodes ?? [], depth + 1, n.id)}</ul>
			{/if}
		</li>
	{/each}
{/snippet}

<ul data-ui="tree" role="tree" aria-label={label} class={['tree', cls]} bind:this={root} {...rest}>
	{@render branch(nodes, 0, null)}
</ul>

<style>
	.tree {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.row {
		position: relative;
		display: flex;
		align-items: center;
		height: 30px;
		padding-right: 8px;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		cursor: pointer;
		outline: 0;
	}

	.row:hover {
		background: var(--v-row-hover);
	}

	.row:focus-visible {
		box-shadow: inset 0 0 0 2px var(--v-focus);
	}

	.row.is-selected {
		background: var(--v-primary-veil);
		box-shadow: inset 2px 0 0 var(--v-primary-text);
	}

	.caret {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		justify-content: center;
		width: 30px;
		height: 30px;
		margin: 0;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--v-ink-2);
		cursor: pointer;
	}

	.caret:hover {
		color: var(--v-ink-1);
	}

	.caret.none {
		cursor: default;
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
		white-space: nowrap;
	}

	.end {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 4px;
		padding-left: 4px;
	}

	.dim,
	.dim .glyph {
		color: var(--v-ink-disabled);
	}

	.disabled {
		color: var(--v-ink-disabled);
		cursor: not-allowed;
	}
</style>
