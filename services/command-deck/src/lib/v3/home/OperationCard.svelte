<script lang="ts">
	/**
	 * OperationCard (V3-SPEC §5.2) — one running operation: state pill (teal Live for a protected
	 * movement, red Open for a pursuit, neutral Active otherwise — always with its word, the live dot
	 * pulses unless reduced motion), the map with its route / trail, the next step, and the progress bar
	 * only when the feed reports progress.
	 */
	import { t } from '$lib/i18n/strings';
	import '../packs.v3';
	import V3Tag from '../ui/V3Tag.svelte';
	import type { LonLat } from '../map/mercator';
	import CardFrame from './CardFrame.svelte';
	import type { OpVM } from './view';

	let { vm, lang, roads = null }: { vm: OpVM; lang: string; roads?: readonly (readonly LonLat[])[] | null } = $props();
</script>

<CardFrame
	{lang}
	cover={vm.cover}
	href={vm.href}
	aria={t(lang, 'v3_card_aria', `${vm.state.text}, ${vm.kindLine}`, vm.title)}
	thumb={vm.thumb}
	art={vm.art}
	kind={vm.kindLine}
	title={vm.title}
	{roads}
	testid="v3-op-card"
	data={{ key: vm.key }}
>
	{#snippet badge()}
		<V3Tag tone={vm.state.tone} glass><span class={['live-dot', `d-${vm.state.tone}`]} aria-hidden="true"></span>{vm.state.text}</V3Tag>
		{#if vm.prov}<V3Tag tone="dashed" glyph={vm.prov.glyph} title={vm.prov.title} glass>{vm.prov.text}</V3Tag>{/if}
	{/snippet}
	{#if vm.meta}<span class="meta">{vm.meta}</span>{/if}
	{#if vm.progress != null}
		<span class="prog" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={vm.progress} aria-label={t(lang, 'v3_op_progress', vm.progress)}
			><i style:width="{vm.progress}%"></i></span
		>
	{/if}
	{#snippet foot()}
		<span class={['next', vm.decisions > 0 && 'decide']}>{vm.next}</span>
	{/snippet}
</CardFrame>

<style>
	.meta {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		font-weight: 500;
	}

	.prog {
		display: block;
		height: 4px;
		margin-top: 4px;
		overflow: hidden;
		border-radius: 2px;
		background: var(--v3-s3);
	}

	.prog i {
		display: block;
		height: 100%;
		border-radius: 2px;
		background: var(--v3-route);
	}

	.next {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.next.decide {
		color: var(--v3-decide-text);
		font-weight: 600;
	}

	.live-dot {
		flex: none;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--v3-t2);
	}

	.live-dot.d-route {
		background: var(--v3-route);
		animation: pulse 2.4s infinite;
	}

	.live-dot.d-alert {
		background: var(--v3-alert);
		animation: pulse-a 2.4s infinite;
	}

	@keyframes pulse {
		0% {
			box-shadow: 0 0 0 0 var(--v3-route-veil);
		}
		70% {
			box-shadow: 0 0 0 8px transparent;
		}
		100% {
			box-shadow: 0 0 0 0 transparent;
		}
	}

	@keyframes pulse-a {
		0% {
			box-shadow: 0 0 0 0 var(--v3-alert-veil);
		}
		70% {
			box-shadow: 0 0 0 8px transparent;
		}
		100% {
			box-shadow: 0 0 0 0 transparent;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.live-dot.d-route,
		.live-dot.d-alert {
			animation: none;
		}
	}
</style>
