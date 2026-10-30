<script lang="ts">
	/**
	 * Dialog — a modal panel (Blueprint): a 40 px header on surface-2 with
	 * the title and a close button, a body, an optional footer of actions
	 * (right-aligned; at most one primary, Cancel or Reject to its left).
	 * Backdrop --v-backdrop; Escape and an outside click close it (each can
	 * be turned off); focus is trapped inside and returns to the opener.
	 * Portalled to <body> with the declaring subtree's theme.
	 *
	 * `open` is bindable; onclose fires on every close request.
	 * `...rest` goes on the dialog panel ([data-ui="dialog"]).
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
		onclose?: () => void;
		width?: number | string;
		canEscapeKeyClose?: boolean;
		canOutsideClickClose?: boolean;
		/** Hide the header's close button (an Alert-like dialog). */
		closeButton?: boolean;
		footer?: Snippet;
		/** Left side of the footer (a Reason, a helper). */
		footerLeft?: Snippet;
		headerRight?: Snippet;
		lang?: string;
		children?: Snippet;
	}

	let {
		open = $bindable(false),
		title = null,
		icon,
		onclose,
		width = 480,
		canEscapeKeyClose = true,
		canOutsideClickClose = true,
		closeButton = true,
		footer,
		footerLeft,
		headerRight,
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
		return pushLayer(close, () => canEscapeKeyClose, () => container);
	});
</script>

{#if open}
	<div class="container" data-ui-overlay="modal" bind:this={container} use:portal>
		<div
			class="backdrop"
			aria-hidden="true"
			onclick={() => canOutsideClickClose && close()}
		></div>
		<div
			data-ui="dialog"
			role="dialog"
			aria-modal="true"
			aria-labelledby={title ? `${uid}-title` : undefined}
			class={['dialog', cls]}
			style:width={typeof width === 'number' ? `${width}px` : width}
			data-focus-self
			use:trapFocus
			{...rest}
		>
			{#if title || closeButton}
				<header class="head">
					{#if icon}<Icon name={icon} size={16} />{/if}
					<h2 class="title" id="{uid}-title">{title ?? ''}</h2>
					{#if headerRight}{@render headerRight()}{/if}
					{#if closeButton}
						<Button minimal small icon="small-cross" tooltip={ut(L, 'ui_close')} onclick={close} />
					{/if}
				</header>
			{/if}
			<div class="body">{@render children?.()}</div>
			{#if footer || footerLeft}
				<footer class="foot">
					{#if footerLeft}<div class="foot-left">{@render footerLeft()}</div>{/if}
					<div class="actions">{@render footer?.()}</div>
				</footer>
			{/if}
		</div>
	</div>
{/if}

<style>
	.container {
		position: fixed;
		inset: 0;
		z-index: var(--v-z-dialog);
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding: 12vh 16px 16px;
		overflow: auto;
	}

	.backdrop {
		position: fixed;
		inset: 0;
		background: var(--v-backdrop);
	}

	.dialog {
		position: relative;
		display: flex;
		flex-direction: column;
		max-width: 100%;
		max-height: calc(100vh - 12vh - 32px);
		border-radius: var(--v-radius-modal);
		background: var(--v-canvas);
		box-shadow: var(--v-elev-3);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		outline: 0;
	}

	.head {
		display: flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 8px;
		min-height: 40px;
		padding: 0 4px 0 16px;
		border-radius: var(--v-radius-modal) var(--v-radius-modal) 0 0;
		background: var(--v-surface-2);
		box-shadow: inset 0 -1px 0 var(--v-line-1);
	}

	.head :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.title {
		flex: 1 1 auto;
		min-width: 0;
		margin: 0;
		overflow: hidden;
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: calc(var(--v-text-md) + 4px);
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
		align-items: center;
		gap: 8px;
		padding: 0 16px 16px;
	}

	.foot-left {
		min-width: 0;
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-left: auto;
	}
</style>
