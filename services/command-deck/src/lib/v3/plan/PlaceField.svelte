<script lang="ts">
	/**
	 * PlaceField — "From" / "To" with a place search (V3-SPEC §6.6): a combobox over the planner's own places
	 * (the corridor's PLAN_POIS, each on the city's road network). Typing filters (matchPlaces: name start, word
	 * start, then contains); ↑ / ↓ move, Enter picks, Escape closes and restores the chosen name. Focusing clears the
	 * field for a new search (the chosen place stays as its placeholder); it shows the chosen name otherwise. ARIA 1.2 combobox: the input owns the listbox through
	 * aria-controls and aria-activedescendant.
	 */
	import { tick } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import { matchPlaces } from './model';
	import './packs.plan';

	let {
		id,
		label,
		placeholder,
		value = $bindable(),
		places,
		lang,
		mark,
		disabled = false,
		testid,
	}: {
		id: string;
		label: string;
		placeholder: string;
		value: number;
		places: readonly { name: string }[];
		lang: string;
		/** The start is a dot, the destination a square (the "Where to?" pair). */
		mark: 'from' | 'to';
		disabled?: boolean;
		testid: string;
	} = $props();

	let query = $state('');
	let typing = $state(false);
	let open = $state(false);
	let active = $state(0);
	let input = $state<HTMLInputElement | null>(null);

	const shown = $derived(typing ? query : (places[value]?.name ?? ''));
	const matches = $derived(matchPlaces(typing ? query : '', places));
	const listId = $derived(`${id}-list`);
	const optId = (i: number) => `${id}-opt-${i}`;

	function openList() {
		if (disabled) return;
		open = true;
		const at = matches.indexOf(value);
		active = at >= 0 ? at : 0;
	}

	function pick(idx: number) {
		value = idx;
		typing = false;
		query = '';
		open = false;
		// the chosen name is selected, so typing straight after a pick starts a new search
		void tick().then(() => {
			if (document.activeElement === input) input?.select();
		});
	}

	function close() {
		open = false;
		typing = false;
		query = '';
	}

	function onkeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
			e.preventDefault();
			if (!open) return openList();
			const n = matches.length;
			if (!n) return;
			active = (active + (e.key === 'ArrowDown' ? 1 : n - 1)) % n;
			document.getElementById(optId(active))?.scrollIntoView({ block: 'nearest' });
		} else if (e.key === 'Enter') {
			if (open && matches.length) {
				e.preventDefault();
				pick(matches[Math.min(active, matches.length - 1)]);
			}
		} else if (e.key === 'Escape') {
			if (open || typing) {
				e.preventDefault();
				e.stopPropagation();
				close();
			}
		} else if (e.key === 'Tab') {
			close();
		}
	}
</script>

<div class={['field', `m-${mark}`, open && 'open']}>
	<span class="mark" aria-hidden="true"></span>
	<label class="lbl" for={id}>{label}</label>
	<input
		bind:this={input}
		{id}
		class="inp"
		type="text"
		role="combobox"
		autocomplete="off"
		spellcheck={false}
		aria-autocomplete="list"
		aria-expanded={open}
		aria-controls={listId}
		aria-activedescendant={open && matches.length ? optId(Math.min(active, matches.length - 1)) : undefined}
		data-testid={testid}
		data-value={value}
		placeholder={typing && places[value] ? places[value].name : placeholder}
		{disabled}
		value={shown}
		onfocus={() => {
			// the ride-search pattern: focusing clears the field for a new search (the chosen place stays as the
			// placeholder, and comes back on Escape or when the field is left without a pick)
			typing = true;
			query = '';
			openList();
		}}
		onclick={() => {
			if (!typing) {
				typing = true;
				query = '';
			}
			if (!open) openList();
		}}
		oninput={(e) => {
			query = (e.currentTarget as HTMLInputElement).value;
			typing = true;
			open = true;
			active = 0;
		}}
		onblur={() => setTimeout(close, 120)}
		{onkeydown}
	/>
	{#if open}
		<ul class="list" id={listId} role="listbox" aria-label={label}>
			{#each matches as idx, i (idx)}
				<li
					id={optId(i)}
					role="option"
					class={['opt', i === active && 'is-selected']}
					aria-selected={idx === value}
					data-testid="v3-plan-place"
					data-idx={idx}
					onmousedown={(e) => {
						e.preventDefault();
						pick(idx);
					}}
					onmousemove={() => (active = i)}
				>
					<span class="pin" aria-hidden="true"></span>
					<span class="nm">{places[idx].name}</span>
				</li>
			{:else}
				<li class="none" role="presentation">{t(lang, 'v3p_no_match', places.length)}</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.field {
		position: relative;
		display: grid;
		grid-template-columns: 28px minmax(0, 1fr);
		grid-template-rows: auto auto;
		align-items: center;
		column-gap: 6px;
		padding: 8px 14px 10px 10px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		box-shadow: inset 0 0 0 1px var(--v3-line-1);
		transition: box-shadow var(--v3-dur-1) var(--v3-ease), background var(--v3-dur-1) var(--v3-ease);
	}

	.field:focus-within {
		background: var(--v3-s3);
		box-shadow: inset 0 0 0 2px var(--v3-brand);
	}

	.mark {
		grid-row: 1 / span 2;
		justify-self: center;
		width: 12px;
		height: 12px;
		border: 3px solid var(--v3-brand-text);
		border-radius: 50%;
	}

	.m-to .mark {
		border-color: var(--v3-route);
		border-radius: 3px;
		background: var(--v3-route);
	}

	.lbl {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 650;
	}

	.inp {
		min-width: 0;
		height: 28px;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--v3-t1);
		font: inherit;
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 600;
		outline: 0;
		text-overflow: ellipsis;
	}

	.inp::placeholder {
		color: var(--v3-t3);
		font-weight: 500;
	}

	.inp:disabled {
		color: var(--v3-t2);
	}

	.list {
		position: absolute;
		z-index: 20;
		top: calc(100% + 6px);
		left: 0;
		right: 0;
		max-height: 300px;
		margin: 0;
		padding: 6px;
		overflow: auto;
		list-style: none;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		box-shadow:
			0 0 0 1px var(--v3-line-2),
			var(--v3-elev-2);
		scrollbar-width: thin;
	}

	.opt {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: 40px;
		padding: 0 12px;
		border-radius: var(--v3-radius-s);
		color: var(--v3-t1);
		font-size: var(--v3-text-body);
		cursor: pointer;
	}

	.opt.is-selected {
		background: var(--v3-s4);
	}

	.opt[aria-selected='true'] .nm {
		font-weight: 650;
	}

	.pin {
		flex: none;
		width: 0;
		height: 0;
		border: 4px solid var(--v3-t3);
		border-radius: 50%;
	}

	.opt[aria-selected='true'] .pin {
		border-color: var(--v3-brand-text);
	}

	.none {
		padding: 10px 12px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}
</style>
