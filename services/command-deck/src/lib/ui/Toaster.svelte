<script lang="ts">
	/**
	 * Toaster — THE primitive: it renders the toasts it is given and owns no
	 * store (the shell wires a store to it). Outcome feedback only — never
	 * a refusal, never a system chatter line. Top centre under the navbar,
	 * at most `max` visible (3), newest first; each toast may auto-dismiss
	 * after `timeout` ms (paused while hovered) and may carry one action.
	 * `position="inline"` renders in flow (the /design gallery).
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { INTENT_ICON } from '$lib/design/icons';
	import Button from './Button.svelte';
	import Icon from './Icon.svelte';
	import { uiLang, ut } from './lang';
	import type { ToastSpec } from './types';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		toasts: readonly ToastSpec[];
		ondismiss?: (id: ToastSpec['id']) => void;
		max?: number;
		position?: 'top' | 'bottom' | 'inline';
		lang?: string;
	}

	let { toasts, ondismiss, max = 3, position = 'top', lang, class: cls = '', ...rest }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	const shown = $derived(toasts.slice(0, Math.max(0, max)));

	const timers = new Map<ToastSpec['id'], ReturnType<typeof setTimeout>>();
	let hovered = $state<ToastSpec['id'] | null>(null);

	$effect(() => {
		const live = new Set(shown.map((t) => t.id));
		for (const [id, h] of timers) {
			if (!live.has(id) || hovered === id) {
				clearTimeout(h);
				timers.delete(id);
			}
		}
		for (const t of shown) {
			if (!t.timeout || t.timeout <= 0 || timers.has(t.id) || hovered === t.id) continue;
			timers.set(
				t.id,
				setTimeout(() => {
					timers.delete(t.id);
					ondismiss?.(t.id);
				}, t.timeout)
			);
		}
	});

	$effect(() => () => {
		for (const h of timers.values()) clearTimeout(h);
		timers.clear();
	});
</script>

<div
	data-ui="toaster"
	class={['toaster', position, cls]}
	role="region"
	aria-live="polite"
	aria-label={ut(L, 'ui_notifications')}
	{...rest}
>
	{#each shown as t (t.id)}
		<div
			data-ui="toast"
			data-intent={t.intent ?? 'none'}
			class={['toast', t.intent && t.intent !== 'none' && `i-${t.intent}`]}
			role="status"
			onpointerenter={() => (hovered = t.id)}
			onpointerleave={() => (hovered = null)}
		>
			{#if t.icon || (t.intent && t.intent !== 'none')}
				<Icon name={t.icon ?? INTENT_ICON[t.intent ?? 'none']} size={16} />
			{/if}
			<span class="msg">{t.message}</span>
			{#if t.action}
				<Button minimal small onclick={t.action.onclick}>{t.action.label}</Button>
			{/if}
			<Button minimal small icon="small-cross" tooltip={ut(L, 'ui_dismiss')} onclick={() => ondismiss?.(t.id)} />
		</div>
	{/each}
</div>

<style>
	.toaster {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		pointer-events: none;
	}

	.top,
	.bottom {
		position: fixed;
		left: 50%;
		z-index: var(--v-z-toast);
		transform: translateX(-50%);
	}

	.top {
		top: calc(var(--v-ws-navbar) + 8px);
	}

	.bottom {
		bottom: 16px;
		flex-direction: column-reverse;
	}

	.inline {
		align-items: flex-start;
	}

	.toast {
		display: flex;
		align-items: center;
		gap: 8px;
		box-sizing: border-box;
		min-width: 300px;
		max-width: min(520px, calc(100vw - 32px));
		min-height: 40px;
		padding: 4px 4px 4px 12px;
		border-radius: var(--v-radius-modal);
		background: var(--v-surface-3);
		box-shadow: var(--v-elev-3);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		pointer-events: auto;
	}

	.toast > :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.i-primary > :global([data-ui='icon']) {
		color: var(--v-primary-text);
	}

	.i-success > :global([data-ui='icon']) {
		color: var(--v-success-text);
	}

	.i-warning > :global([data-ui='icon']) {
		color: var(--v-warning-text);
	}

	.i-danger > :global([data-ui='icon']) {
		color: var(--v-danger-text);
	}

	.msg {
		flex: 1 1 auto;
		min-width: 0;
		padding: 4px 0;
	}
</style>
