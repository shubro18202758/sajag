<script lang="ts">
	/**
	 * TimeField — an IST wall time, 24-hour, typed (never the browser's
	 * locale picker, which can show 12-hour). Accepts "9:5", "0905",
	 * "09:05" and normalises to "09:05" (or "09:05:30" with `seconds`) on
	 * blur or Enter; ArrowUp/ArrowDown step a minute (Shift: an hour).
	 * An invalid entry keeps the last good value, marks the field and says
	 * how to write it. An "IST" tag sits at the right.
	 *
	 * `value` ("hh:mm" | "hh:mm:ss" | null) is bindable; onchange fires with
	 * each committed value. istTimeToMs() in format.ts turns it into an
	 * instant on a given IST day. `...rest` goes on the <input>.
	 */
	import type { HTMLInputAttributes } from 'svelte/elements';
	import Input from './Input.svelte';
	import { uiLang, ut } from './lang';
	import { parseIstTime } from './format/format';

	interface Props extends Omit<HTMLInputAttributes, 'value' | 'size' | 'onchange'> {
		value?: string | null;
		seconds?: boolean;
		small?: boolean;
		fill?: boolean;
		onchange?: (value: string | null) => void;
		lang?: string;
	}

	let {
		value = $bindable(null),
		seconds = false,
		small = false,
		fill = false,
		onchange,
		disabled = false,
		placeholder,
		lang,
		class: cls = '',
		...rest
	}: Props = $props();

	const uid = $props.id();
	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	let text = $state('');
	let invalid = $state(false);
	let synced: string | null | undefined = undefined;

	$effect.pre(() => {
		if (value !== synced) {
			synced = value;
			text = value ?? '';
			invalid = false;
		}
	});

	function commit() {
		const raw = text.trim();
		if (raw === '') {
			invalid = false;
			if (value !== null) {
				value = null;
				synced = null;
				onchange?.(null);
			}
			return;
		}
		const parsed = parseIstTime(raw, seconds);
		if (!parsed) {
			invalid = true;
			return;
		}
		invalid = false;
		text = parsed;
		if (parsed !== value) {
			value = parsed;
			synced = parsed;
			onchange?.(parsed);
		}
	}

	function step(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			commit();
			return;
		}
		if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
		const base = parseIstTime(text || value || '00:00', true);
		if (!base) return;
		e.preventDefault();
		const [h, m, s] = base.split(':').map(Number);
		const delta = (e.key === 'ArrowUp' ? 1 : -1) * (e.shiftKey ? 60 : 1);
		const total = (((h * 60 + m + delta) % 1440) + 1440) % 1440;
		const p = (n: number) => String(n).padStart(2, '0');
		text = seconds ? `${p(Math.floor(total / 60))}:${p(total % 60)}:${p(s)}` : `${p(Math.floor(total / 60))}:${p(total % 60)}`;
		commit();
	}
</script>

{#snippet ist()}<span class="ist">{ut(L, 'ui_time_ist')}</span>{/snippet}

<span data-ui="time-field" class={['tf', fill && 'fill', cls]}>
	<Input
		{...rest}
		bind:value={text}
		{small}
		{fill}
		{disabled}
		intent={invalid ? 'danger' : 'none'}
		inputmode="numeric"
		autocomplete="off"
		spellcheck="false"
		placeholder={placeholder ?? (seconds ? 'hh:mm:ss' : 'hh:mm')}
		aria-describedby={invalid ? `${uid}-err` : undefined}
		onblur={commit}
		onkeydown={step}
		rightElement={ist}
		class="tf-input"
	/>
	{#if invalid}
		<span class="err" id="{uid}-err" role="alert">{ut(L, seconds ? 'ui_time_invalid_s' : 'ui_time_invalid')}</span>
	{/if}
</span>

<style>
	.tf {
		display: inline-flex;
		flex-direction: column;
		gap: 4px;
		vertical-align: middle;
	}

	.fill {
		display: flex;
		width: 100%;
	}

	.tf :global(.tf-input input) {
		font-variant-numeric: tabular-nums;
	}

	.tf:not(.fill) :global(.tf-input) {
		width: 120px;
	}

	.ist {
		padding: 0 4px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.err {
		color: var(--v-danger-text);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}
</style>
