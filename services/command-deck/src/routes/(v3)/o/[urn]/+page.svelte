<script lang="ts">
	/**
	 * /o/<urn> — the V3 object page (V3-SPEC §3.2, §6.3, §6.4; phase P3): one page per record the city picture
	 * holds, `<kind>:<id>` in the path (city-api's URN grammar; anything else is "not a record", never a fetch).
	 * Everything is in src/lib/v3/object; this route only reads the parameter and keeps the operator gate.
	 */
	import { page } from '$app/state';
	import { ops } from '$lib/ops/store.svelte';
	import { tOps } from '$lib/i18n/strings.ops';
	import OperatorSignIn from '$lib/shell/OperatorSignIn.svelte';
	import ObjectPage from '$lib/v3/object/ObjectPage.svelte';
	import { urnFromParam } from '$lib/v3/object/model';

	const urn = $derived(urnFromParam(page.params.urn));
</script>

{#if ops.signInRequired}
	<div class="signin" data-testid="cockpit-signin-required">
		<div class="signin-card">
			<h2>{tOps(ops.lang, 'opsSigninTitle')}</h2>
			<p>{tOps(ops.lang, 'cockpitSigninBody')}</p>
			<OperatorSignIn lang={ops.lang} inline />
		</div>
	</div>
{:else}
	{#key urn}<ObjectPage {urn} />{/key}
{/if}

<style>
	.signin {
		display: grid;
		place-items: center;
		min-height: 60vh;
		padding: 32px;
	}

	.signin-card {
		max-width: 420px;
		padding: 24px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}
</style>
