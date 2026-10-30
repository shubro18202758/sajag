<script lang="ts">
	/**
	 * BlockedOption (V3-SPEC §5.3, §6.2; osint SPEC §1.7) — a course of action that cannot be approved, said
	 * plainly and never hidden: the lock, what it is, why (what it needs and what is free, or the engine's
	 * veto reason, verbatim), and — for the resource-blocked BEST response — "Request a unit".
	 *
	 * "Request a unit" files NOTHING from here: it opens Dispatch (its Request-unit form, officer-gated
	 * there) on the corridor event the units would be requested against — the v2 BestBlockedBanner's rule.
	 * A report not yet promoted to a corridor event has none; the line says so instead of a dead link.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.dss';
	import type { DssCoa } from '$lib/ops/client';
	import Glyph from '../Glyph.svelte';
	import './packs.decide';

	let {
		coa,
		reason,
		best = false,
		request = null,
		lang,
	}: {
		coa: DssCoa;
		reason: string;
		best?: boolean;
		/** Open Dispatch on the subject's corridor event; null = no event yet (said in words). */
		request?: (() => void) | null;
		lang: string;
	} = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
</script>

<div class="blocked" data-testid="v3-blocked-option" data-coa-id={coa.coaId} data-best={best ? 'true' : 'false'}>
	<Glyph name="lock" size={18} />
	<p>
		<b>{best ? L('v3d_blocked_best') : L('v3d_blocked')}</b>
		{coa.label}. {reason}
	</p>
	{#if best}
		{#if request}
			<button type="button" class="link" onclick={() => request?.()}>{L('v3d_request_unit')}</button>
		{:else}
			<span class="hint">{L('v3d_request_after')}</span>
		{/if}
	{/if}
</div>

<style>
	.blocked {
		display: flex;
		gap: 12px;
		align-items: center;
		padding: 12px 16px;
		border: 1px dashed var(--v3-line-3);
		border-radius: 14px;
		background: var(--v3-s1);
		font-size: 14px;
		line-height: 20px;
		color: var(--v3-t2);
	}

	.blocked > :global(svg) {
		flex: none;
		color: var(--v3-t2);
	}

	p {
		flex: 1;
		min-width: 0;
		margin: 0;
	}

	b {
		color: var(--v3-t1);
		font-weight: 600;
	}

	.link {
		flex: none;
		padding: 0;
		border: 0;
		background: none;
		color: var(--v3-brand-text);
		font: inherit;
		font-weight: 600;
		white-space: nowrap;
		cursor: pointer;
	}

	.link:hover {
		text-decoration: underline;
	}

	.link:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
		border-radius: 4px;
	}

	.hint {
		flex: 0 1 40%;
		font-size: var(--v3-text-meta);
		color: var(--v3-t3);
	}
</style>
