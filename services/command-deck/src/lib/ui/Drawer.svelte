<script lang="ts">
	/**
	 * Drawer — a panel that slides over the page from an edge (right by
	 * default): a 40 px header with the title and close, a scrolling body, an
	 * optional footer. Modal (backdrop, focus trap, Escape) unless
	 * `hasBackdrop` is false: then it is a non-modal panel (no aria-modal,
	 * Tab may leave it, [data-ui-overlay="panel"]) that still closes on
	 * Escape and returns focus. `size` is a CSS length (width, or height for
	 * the bottom edge). Docked panes are not drawers: a Drawer is for a
	 * transient task over the workspace.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/design/icons';
	import Button from './Button.svelte';
	import Icon from './Icon.svelte';
	import { uiLang, ut } from './lang';
	import { portal, pushLayer, trapFocus } from './overlay';

	interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
		open?: boolean;
		title?: string | null;
		icon?: IconName;
		position?: 'right' | 'left' | 'bottom';
		size?: string;
		hasBackdrop?: boolean;
		canOutsideClickClose?: boolean;
		onclose?: () => void;
		footer?: Snippet;
		lang?: string;
		children?: Snippet;
	}

	let {
		open = $bindable(false),
		title = null,
		icon,
		position = 'right',
		size = '400px',
		hasBackdrop = true,
		canOutsideClickClose = true,
		onclose,
		footer,
		lang,
		children,
		class: cls = '',
		...rest
	}: Props = $props();

	const uid = $props.id();
	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	let container: HTMLDivElement | undefined = $state();

	function close() {
		open = false;
		onclose?.();
	}

	$effect(() => {
		if (!open) return;
		return pushLayer(close, () => true, () => container);
	});
</script>

{#if open}
	<div
		class={['container', !hasBackdrop && 'pass']}
		data-ui-overlay={hasBackdrop ? 'modal' : 'panel'}
		bind:this={container}
		use:portal
	>
		{#if hasBackdrop}
			<div class="backdrop" aria-hidden="true" onclick={() => canOutsideClickClose && close()}></div>
		{/if}
		<div
			data-ui="drawer"
			role="dialog"
			aria-modal={hasBackdrop ? 'true' : undefined}
			aria-labelledby={title ? `${uid}-title` : undefined}
			class={['drawer', position, cls]}
			style:width={position === 'bottom' ? undefined : size}
			style:height={position === 'bottom' ? size : undefined}
			data-focus-self
			use:trapFocus={{ trap: hasBackdrop }}
			{...rest}
		>
			<header class="head">
				{#if icon}<Icon name={icon} size={16} />{/if}
				<h2 class="title" id="{uid}-title">{title ?? ''}</h2>
				<Button minimal small icon="small-cross" tooltip={ut(L, 'ui_close')} onclick={close} />
			</header>
			<div class="body">{@render children?.()}</div>
			{#if footer}<footer class="foot">{@render footer()}</footer>{/if}
		</div>
	</div>
{/if}

<style>
	.container {
		position: fixed;
		inset: 0;
		z-index: var(--v-z-dialog);
	}

	.container.pass {
		pointer-events: none;
	}

	.container.pass .drawer {
		pointer-events: auto;
	}

	.backdrop {
		position: absolute;
		inset: 0;
		background: var(--v-backdrop);
	}

	.drawer {
		position: absolute;
		display: flex;
		flex-direction: column;
		max-width: 100vw;
		max-height: 100vh;
		background: var(--v-surface-1);
		box-shadow: var(--v-elev-4);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		outline: 0;
	}

	.right {
		top: 0;
		right: 0;
		bottom: 0;
	}

	.left {
		top: 0;
		left: 0;
		bottom: 0;
	}

	.bottom {
		left: 0;
		right: 0;
		bottom: 0;
	}

	.head {
		display: flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 8px;
		min-height: 40px;
		padding: 0 4px 0 16px;
		border-bottom: 1px solid var(--v-line-2);
	}

	.head :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.title {
		flex: 1 1 auto;
		min-width: 0;
		margin: 0;
		overflow: hidden;
		font-size: var(--v-text-base);
		font-weight: 600;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.body {
		flex: 1 1 auto;
		min-height: 0;
		padding: 16px;
		overflow: auto;
	}

	.foot {
		display: flex;
		flex: 0 0 auto;
		justify-content: flex-end;
		gap: 8px;
		padding: 12px 16px;
		border-top: 1px solid var(--v-line-2);
	}
</style>
