<script lang="ts">
	/**
	 * Alert — a confirmation (Blueprint Alert): a 40 px intent glyph beside
	 * the message, then Cancel and the confirm action. No outside-click
	 * close; Escape cancels (unless canEscapeKeyClose is false). The confirm
	 * button takes the intent: primary (the default) for a decision; warning
	 * or danger only where SPEC §2.4's colour roles allow it (a decision verb
	 * is never red). Focus opens on Cancel (or the panel without one): no
	 * single key confirms.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import { INTENT_ICON, type IconName } from '$lib/design/icons';
	import Button from './Button.svelte';
	import Icon from './Icon.svelte';
	import { uiLang, ut } from './lang';
	import { portal, pushLayer, trapFocus } from './overlay';
	import type { Intent } from './types';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		open?: boolean;
		intent?: Intent;
		icon?: IconName | null;
		confirmLabel?: string;
		cancelLabel?: string | null;
		loading?: boolean;
		canEscapeKeyClose?: boolean;
		onconfirm?: () => void;
		oncancel?: () => void;
		lang?: string;
		children?: Snippet;
	}

	let {
		open = $bindable(false),
		intent = 'primary',
		icon = undefined,
		confirmLabel,
		cancelLabel = undefined,
		loading = false,
		canEscapeKeyClose = true,
		onconfirm,
		oncancel,
		lang,
		children,
		class: cls = '',
		...rest
	}: Props = $props();

	const uid = $props.id();
	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	const glyph = $derived(icon === null ? null : (icon ?? INTENT_ICON[intent]));
	let container: HTMLDivElement | undefined = $state();

	function cancel() {
		open = false;
		oncancel?.();
	}

	function confirm() {
		onconfirm?.();
	}

	$effect(() => {
		if (!open) return;
		return pushLayer(cancel, () => canEscapeKeyClose && !loading, () => container);
	});
</script>

{#if open}
	<div class="container" data-ui-overlay="modal" bind:this={container} use:portal>
		<div class="backdrop" aria-hidden="true"></div>
		<div
			data-ui="alert"
			role="alertdialog"
			aria-modal="true"
			aria-describedby="{uid}-msg"
			class={['alert', cls]}
			data-focus-self
			use:trapFocus
			{...rest}
		>
			<div class="body">
				{#if glyph}<span class="glyph i-{intent}"><Icon name={glyph} size={40} /></span>{/if}
				<div class="msg" id="{uid}-msg">{@render children?.()}</div>
			</div>
			<footer class="foot">
				{#if cancelLabel !== null}
					<Button onclick={cancel} disabled={loading} data-autofocus>{cancelLabel ?? ut(L, 'ui_cancel')}</Button>
				{/if}
				<Button intent={intent === 'none' ? 'primary' : intent} {loading} onclick={confirm}
					>{confirmLabel ?? ut(L, 'ui_confirm')}</Button
				>
			</footer>
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
		padding: 16vh 16px 16px;
	}

	.backdrop {
		position: fixed;
		inset: 0;
		background: var(--v-backdrop);
	}

	.alert {
		position: relative;
		width: 400px;
		max-width: 100%;
		padding: 20px;
		border-radius: var(--v-radius-modal);
		background: var(--v-surface-1);
		box-shadow: var(--v-elev-3);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 6px);
		outline: 0;
	}

	.body {
		display: flex;
		align-items: flex-start;
		gap: 16px;
	}

	/* neutral glyph for a primary (decision) alert: blue belongs to its one
	   primary button, not to decoration (SPEC §2.4); only the warning,
	   danger and success roles tint the glyph */
	.glyph {
		display: inline-flex;
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.i-success {
		color: var(--v-success-text);
	}

	.i-warning {
		color: var(--v-warning-text);
	}

	.i-danger {
		color: var(--v-danger-text);
	}

	.msg {
		min-width: 0;
		padding-top: 8px;
	}

	.msg :global(p) {
		margin: 0 0 8px;
	}

	.foot {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
		margin-top: 20px;
	}
</style>
