<script lang="ts">
	/**
	 * OptionCard (V3-SPEC §5.3, §6.2) — one decision-support course of action as a ride-type row: its glyph,
	 * its name, "Recommended" on the engine's pick, one plain line of what it does, and the ONE figure that
	 * matters (time to the scene; "no units" / "no action"). Closeness, rank and the criteria live in Analyst.
	 *
	 * A radio (role="radio", roving tabindex inside the group): choosing it selects the course of action the
	 * Approve button names and the writer posts. A vetoed or under-resourced option is never offered here —
	 * BlockedOption states it, with what it needs.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.dss';
	import type { DssCoa } from '$lib/ops/client';
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import './packs.decide';
	import { coaFigure, coaGlyph } from './model';

	let {
		coa,
		selected,
		recommended = false,
		index,
		lang,
		onselect,
		onkeynav,
	}: {
		coa: DssCoa;
		selected: boolean;
		recommended?: boolean;
		index: number;
		lang: string;
		onselect: (coaId: string) => void;
		onkeynav?: (e: KeyboardEvent) => void;
	} = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const fig = $derived(coaFigure(coa));

	/** One plain line of what the option does, from its actions (the engine's verbs, in words). */
	const line = $derived.by(() => {
		const parts: string[] = [];
		for (const a of coa.actions) {
			if (a.verb === 'dispatch') {
				const key = `dss_agency_${typeof a.params.agency === 'string' ? a.params.agency : ''}`;
				const agency = L(key) === key ? String(a.params.agency ?? '') : L(key);
				const n = typeof a.params.count === 'number' && Number.isFinite(a.params.count) ? a.params.count : 1;
				parts.push(L('v3d_opt_dispatch', agency, n));
			} else {
				const key = `dss_verb_${a.verb}`;
				const v = L(key);
				if (v !== key && !parts.includes(v)) parts.push(v);
			}
		}
		return parts.length ? parts.join(', ') : L('v3d_opt_nothing');
	});
</script>

<div
	class="opt"
	class:is-selected={selected}
	role="radio"
	aria-checked={selected}
	tabindex={selected ? 0 : -1}
	data-testid="v3-option"
	data-coa-id={coa.coaId}
	data-recommended={recommended ? 'true' : 'false'}
	onclick={() => onselect(coa.coaId)}
	onkeydown={(e) => {
		if (e.key === ' ' || e.key === 'Enter') {
			e.preventDefault();
			e.stopPropagation();
			onselect(coa.coaId);
		} else onkeynav?.(e);
	}}
>
	<span class="ic"><Glyph name={coaGlyph(coa)} size={20} /></span>
	<span class="body">
		<span class="nm">
			<span class="label">{coa.label}</span>
			{#if recommended}<V3Tag tone="ok" glyph="check" size="sm">{L('v3d_opt_recommended')}</V3Tag>{/if}
		</span>
		<span class="ds">{line}</span>
	</span>
	<span class="eta">
		<b>{fig.value}</b>
		<span>{L(fig.labelKey)}</span>
	</span>
	{#if index < 4}<kbd class="key" aria-hidden="true">{index + 1}</kbd>{/if}
</div>

<style>
	.opt {
		position: relative;
		display: grid;
		grid-template-columns: 44px minmax(0, 1fr) auto;
		gap: 14px;
		align-items: center;
		padding: 14px 16px;
		border: 1.5px solid var(--v3-line-2);
		border-radius: 16px;
		color: var(--v3-t1);
		cursor: pointer;
		transition:
			border-color var(--v3-dur-1) var(--v3-ease),
			background-color var(--v3-dur-1) var(--v3-ease);
	}

	.opt:hover {
		background: var(--v3-s2);
	}

	.opt.is-selected {
		border-color: var(--v3-t1);
		background: var(--v3-s2);
	}

	.opt:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.ic {
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		border-radius: 12px;
		background: var(--v3-s3);
	}

	.body {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.nm {
		display: flex;
		flex-wrap: wrap;
		gap: 4px 8px;
		align-items: center;
		font-size: 16px;
		line-height: 22px;
		font-weight: 650;
	}

	.ds {
		margin-top: 2px;
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		color: var(--v3-t2);
	}

	.eta {
		text-align: right;
		white-space: nowrap;
	}

	.eta b {
		display: block;
		font-size: 17px;
		line-height: 24px;
		font-weight: 650;
		font-variant-numeric: tabular-nums;
	}

	.eta span {
		font-size: var(--v3-text-micro);
		font-weight: 600;
		color: var(--v3-t3);
	}

	.key {
		position: absolute;
		top: 6px;
		right: 8px;
		font-family: inherit;
		font-size: 11px;
		line-height: 1;
		color: var(--v3-t3);
		opacity: 0;
	}

	.opt:focus-visible .key,
	.opt:hover .key {
		opacity: 1;
	}

	@media (max-width: 1500px) {
		.opt {
			padding: 12px 14px;
			gap: 12px;
		}
	}
</style>
