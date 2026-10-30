<script lang="ts">
	/**
	 * Id — an identifier in the mono face at max(12px, 0.9em), so it sits
	 * level inside 14 px prose and never falls under the 12 px floor in a
	 * 12 px cell. Identifiers only: camera, junction, unit and recommendation
	 * ids, URNs. Registration marks use Plate (masking), times use Time.
	 */
	import type { HTMLAttributes } from 'svelte/elements';

	interface Props extends HTMLAttributes<HTMLSpanElement> {
		value: string | number | null | undefined;
	}

	let { value, class: cls = '', ...rest }: Props = $props();
</script>

<span data-ui="id" class={['id', cls]} {...rest}>{value ?? '—'}</span>

<style>
	.id {
		font-family: var(--v-font-mono);
		font-size: max(12px, 0.9em);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
</style>
