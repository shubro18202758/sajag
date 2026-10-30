<script lang="ts">
	/**
	 * Icon — one Blueprint glyph (SPEC §4). 16 px in chrome, 20 px for object
	 * titles (the 20 px drawing is used when the icon has one). Colour is
	 * currentColor unless an intent is given. Decorative by default
	 * (aria-hidden); a `title` makes it an image with that accessible name —
	 * never a <title> child, so a glyph adds no text to its parent's
	 * textContent.
	 *
	 * A glyph outside the first-paint half (lib/design/icons.ts, FIX-E-PERF2)
	 * may not be in yet when the icon first renders on the client: the icon
	 * asks for the deferred half and re-renders once it lands.
	 */
	import type { SVGAttributes } from 'svelte/elements';
	import { iconPaths, iconReady, isIconName, loadRestIcons, type IconName } from '$lib/design/icons';
	import type { TagIntent } from './types';

	interface Props extends Omit<SVGAttributes<SVGSVGElement>, 'name'> {
		name: IconName;
		size?: number;
		title?: string;
		intent?: TagIntent;
	}

	let { name, size = 16, title, intent = 'none', class: cls = '', ...rest }: Props = $props();

	let landed = $state(0);
	const icon = $derived.by(() => {
		void landed; // re-read once the deferred half lands
		return iconPaths(name, size);
	});
	$effect(() => {
		if (isIconName(name) && !iconReady(name)) {
			loadRestIcons().then(
				() => landed++,
				() => {}, // offline: the empty box stays; a later icon retries
			);
		}
	});
</script>

<svg
	data-ui="icon"
	data-icon={name}
	class={['ic', intent !== 'none' && `i-${intent}`, cls]}
	width={size}
	height={size}
	viewBox="0 0 {icon.grid} {icon.grid}"
	fill="currentColor"
	focusable="false"
	role={title ? 'img' : undefined}
	aria-hidden={title ? undefined : 'true'}
	aria-label={title}
	{...rest}
>
	{#each icon.paths as d, i (i)}
		<path {d} fill-rule="evenodd" />
	{/each}
</svg>

<style>
	.ic {
		display: inline-block;
		flex: 0 0 auto;
		vertical-align: middle;
	}

	.i-primary {
		color: var(--v-primary-text);
	}

	.i-success {
		color: var(--v-success-text);
	}

	.i-warning {
		color: var(--v-warning-text);
	}

	.i-danger {
		color: var(--v-danger-text);
	}

	.i-ai {
		color: var(--v-ai-text);
	}
</style>
