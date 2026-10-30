<script lang="ts">
	/**
	 * The gate's one sign-in state for a page (F-10): with the operator gate on
	 * and nobody signed in, every operator read is refused (403), so a page
	 * shows this card instead of mounting panels that would each fail. The
	 * cockpit (/), City command and the wall have their own; /chat and /comms
	 * use this one.
	 */
	import OperatorSignIn from './OperatorSignIn.svelte';

	let { title, body, lang, testid }: { title: string; body: string; lang: string; testid: string } = $props();
</script>

<div class="signin-wall" data-testid={testid}>
	<div class="signin-card">
		<h2>{title}</h2>
		<p>{body}</p>
		<OperatorSignIn {lang} inline />
	</div>
</div>

<style>
	.signin-wall {
		flex: 1;
		min-height: 0;
		height: 100%;
		display: grid;
		place-items: center;
		padding: 16px;
	}

	.signin-card {
		width: min(440px, 100%);
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 20px;
		background: var(--v-surface-1);
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-panel);
	}

	.signin-card h2 {
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
		color: var(--v-ink-1);
	}

	.signin-card p {
		margin: 0;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}
</style>
