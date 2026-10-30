<script lang="ts">
	/**
	 * VehicleShot — the studio shot of a vehicle CLASS (an original illustration, never the vehicle itself, never a
	 * camera image): a car, an auto-rickshaw, the 108 ambulance, the convoy … Vehicles only; no person anywhere.
	 */
	import { t } from '$lib/i18n/strings';
	import './packs.media';
	import { VEHICLE_SHOT, vehicleShot, vehicleShotClass } from './art';

	let {
		cls,
		lang,
		width = 160,
		decorative = false,
		class: klass = '',
	}: { cls: string | null; lang: string; width?: number; decorative?: boolean; class?: string } = $props();

	const k = $derived(vehicleShotClass(cls));
	const alt = $derived(
		decorative ? '' : k === 'convoy' ? t(lang, 'v3i_convoy_alt') : k.startsWith('convoy_') ? t(lang, 'v3i_art_alt', t(lang, `v3i_cls_${k}`)) : t(lang, 'v3i_vehicle_alt', t(lang, `v3i_cls_${k}`)),
	);
</script>

<img
	class={['shot', klass]}
	src={vehicleShot(k)}
	{alt}
	width={width}
	height={Math.round((width * VEHICLE_SHOT.h) / VEHICLE_SHOT.w)}
	loading="lazy"
	decoding="async"
	data-testid="v3-vehicle-shot"
	data-class={k}
/>

<style>
	.shot {
		display: block;
		flex: none;
		max-width: 100%;
		height: auto;
		object-fit: contain;
	}
</style>
