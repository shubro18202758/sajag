<script lang="ts">
	/**
	 * Button — the legacy action button, rebuilt on src/lib/ui's Button
	 * (SPEC §5.2), keeping its API and its gate:
	 *
	 * - `actor` gate (C6): a `primary` button is a human commit and NEVER
	 *   enables without a named officer — passing no `actor` renders it
	 *   disabled, with the officer hint as its reason (tooltip).
	 * - variants map onto the colour roles (SPEC §2.4): primary → the one
	 *   primary action (blue); secondary → default; ghost → minimal;
	 *   danger-outline (reject, abort) → default: a decision verb is never red.
	 * - sizes: sm → small (24), m → 30, citizen → the 44 px touch target.
	 * - busy: the spinner over the label (the width never changes, aria-busy),
	 *   disabled.
	 *
	 * `data-prim="button"` stays on the <button> (the citizen smoke clicks it
	 * and reads its `disabled`). The hint follows the language context (the
	 * shell's), unless `lang` is passed.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import UiButton from '$lib/ui/Button.svelte';
	import { uiLang } from '$lib/ui/lang';

	type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger-outline';
	type ButtonSize = 'sm' | 'm' | 'citizen';

	interface Props {
		variant?: ButtonVariant;
		size?: ButtonSize;
		busy?: boolean;
		disabled?: boolean;
		/** Named officer/operator identity; required to enable primary. */
		actor?: string | null;
		type?: 'button' | 'submit';
		title?: string;
		/** UI language for the hint (defaults to the language context). */
		lang?: string | null;
		onclick?: (e: MouseEvent) => void;
		children?: import('svelte').Snippet;
	}

	let {
		variant = 'secondary',
		size = 'm',
		busy = false,
		disabled = false,
		actor = null,
		type = 'button',
		title,
		lang = null,
		onclick,
		children
	}: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	/** The gate: a human-commit button cannot enable without an actor. */
	const commitLocked = $derived(variant === 'primary' && !actor);
	const reallyDisabled = $derived(disabled || busy || commitLocked);
	const reason = $derived(commitLocked ? t(L, 'officer_hint') : null);
</script>

<UiButton
	{type}
	intent={variant === 'primary' ? 'primary' : 'none'}
	minimal={variant === 'ghost'}
	small={size === 'sm'}
	large={size === 'citizen'}
	class={size === 'citizen' ? 'touch' : undefined}
	loading={busy}
	disabled={reallyDisabled}
	disabledReason={reason}
	tooltip={title ?? null}
	aria-disabled={reallyDisabled}
	{onclick}
	data-prim="button"
	data-variant={variant}
>
	{@render children?.()}
</UiButton>

<style>
	/* the public pages' touch target (WCAG 2.5.5): 44 px */
	:global(button[data-prim='button'].touch) {
		min-height: var(--v-ctl-touch);
	}
</style>
