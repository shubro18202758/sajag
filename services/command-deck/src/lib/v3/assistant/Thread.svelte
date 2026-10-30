<script lang="ts">
	/**
	 * Thread (V3-SPEC §5.7) — the conversation at an 820 px measure: the officer's bubbles on the right, the
	 * assistant's turns (BotTurn) on the left, and the empty state when nothing was asked yet (the assistant
	 * illustration, what it reads, that it cannot approve). The page follows the newest turn as it streams.
	 */
	import BotTurn from './BotTurn.svelte';
	import type { TurnVM } from './view';
	import type { Chip } from './model';
	import { sceneFor, sceneSrc } from '../media/art';

	let {
		turns,
		L,
		chipOf,
		onopen,
		onshowmap,
		roads = null,
	}: {
		turns: readonly TurnVM[];
		L: (key: string, ...args: unknown[]) => string;
		chipOf: (c: Chip) => { glyph: string; decide: boolean };
		onopen: (urn: string) => void;
		onshowmap: (urn: string | null) => void;
		roads?: readonly (readonly (readonly [number, number])[])[] | null;
	} = $props();

	// V3-P7: the empty conversation opens on the city at this hour (an illustration)
	const hour = Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Asia/Kolkata' }).format(Date.now()));
</script>

<div class="col" data-testid="v3-thread">
	{#if turns.length === 0}
		<div class="empty" data-testid="v3-assistant-empty">
			<img class="scene" src={sceneSrc(sceneFor(hour))} alt="" width="960" height="320" loading="eager" decoding="async" />
			<h2>{L('v3a_empty_title')}</h2>
			<p>{L('v3a_empty_body')}</p>
		</div>
	{:else}
		{#each turns as turn (turn.id)}
			{#if turn.role === 'user'}
				<p class="you" data-testid="v3-you">{turn.text}</p>
			{:else}
				<BotTurn {turn} {L} {chipOf} {onopen} {onshowmap} {roads} />
			{/if}
		{/each}
	{/if}
</div>

<style>
	.col {
		display: flex;
		flex-direction: column;
		gap: 22px;
		max-width: 820px;
		margin: 0 auto;
		padding: 0 32px;
	}

	.you {
		align-self: flex-end;
		max-width: 70%;
		margin: 0;
		padding: 12px 18px;
		border-radius: 20px 20px 6px 20px;
		background: var(--v3-s3);
		font-size: 16px;
		line-height: 24px;
		overflow-wrap: anywhere;
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		margin-top: 8vh;
		text-align: center;
	}

	.empty .scene {
		display: block;
		width: 100%;
		max-width: 760px;
		height: 210px;
		object-fit: cover;
		border-radius: var(--v3-radius-xl);
		box-shadow: var(--v3-elev-1);
	}

	.empty h2 {
		margin: 8px 0 0;
		font-size: var(--v3-text-title);
		line-height: var(--v3-lh-title);
		font-weight: 650;
	}

	.empty p {
		max-width: 520px;
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-body);
		line-height: var(--v3-lh-body);
	}

	@media (max-width: 1500px) {
		.col {
			padding: 0 24px;
		}
	}
</style>
