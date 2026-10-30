<script lang="ts">
	/**
	 * A section's one time word (SPEC §3.5): how long ago its source last
	 * answered, "8 s ago", ticking at 1 Hz on the shell's shared clock.
	 * `data-age-sec` carries the seconds (canvas-ux-smoke reads the panel ages
	 * tick). Nothing renders before the first answer.
	 */
	import { fmtDuration, fmtFull } from '$lib/ui/format/format';
	import { shellClock, useShellClock } from '$lib/shell/clock.svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';

	interface Props {
		/** Epoch ms of the last answer (0 or null: none yet). */
		at: number | null;
		lang: string;
	}

	let { at, lang }: Props = $props();

	$effect(() => useShellClock());

	const sec = $derived(at ? Math.max(0, Math.floor((shellClock.now - at) / 1000)) : null);
</script>

{#if at && sec != null}
	<span class="age" data-age-sec={sec} title={t(lang, 'wall_updated_at', fmtFull(at))}>{t(lang, 'wall_age', fmtDuration(sec, lang))}</span>
{/if}

<style>
	.age {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
</style>
