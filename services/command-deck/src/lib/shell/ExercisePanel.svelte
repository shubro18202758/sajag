<script lang="ts">
	/**
	 * The Exercise-data popover (SPEC §5.3, §9.2): the console-wide statement
	 * the page supplied (commandBar.exercise.text), the feed's provenance word,
	 * and the labelling rule, stated once.
	 */
	import { t } from '$lib/i18n/strings';
	import Note from '$lib/ui/Note.svelte';
	import type { ExerciseInfo } from './command-bar.svelte';
	import { EMULATED_ICON } from './icons';

	let { exercise, lang }: { exercise: ExerciseInfo; lang: string } = $props();

	const word = $derived(exercise.label ? exercise.label.charAt(0).toLocaleUpperCase() + exercise.label.slice(1) : '—');
</script>

<div class="panel" data-shell="exercise-panel">
	<div class="head">{t(lang, 'shell_exercise')}</div>
	{#if exercise.text}<p class="lead">{exercise.text}</p>{/if}
	<div class="row">
		<span class="k">{t(lang, 'shell_exercise_feed')}</span>
		<span class="v">{word}</span>
	</div>
	<div class="rule"><Note icon={EMULATED_ICON} text={t(lang, 'shell_exercise_rule')} /></div>
</div>

<style>
	.panel {
		box-sizing: border-box;
		width: 340px;
		max-width: calc(100vw - 16px);
		padding: 12px 16px;
		font-family: var(--v-font-ui);
	}

	.head {
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: calc(var(--v-text-base) + 2px);
	}

	.lead {
		margin: 8px 0 0;
		color: var(--v-ink-1);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) * 1.5);
	}

	.row {
		display: flex;
		align-items: baseline;
		gap: 12px;
		margin-top: 8px;
		padding: 6px 0;
		border-top: 1px solid var(--v-line-1);
		border-bottom: 1px solid var(--v-line-1);
	}

	.k {
		flex: 0 0 36%;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.v {
		color: var(--v-ink-1);
		font-size: var(--v-text-base);
	}

	.rule {
		margin-top: 12px;
	}
</style>
