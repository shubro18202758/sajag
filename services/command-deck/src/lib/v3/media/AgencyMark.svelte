<script module lang="ts">
	import { t as tm } from '$lib/i18n/strings';
	import type { Mark as MarkT } from './logos';

	const GROUP: Readonly<Record<string, string>> = {
		police: 'police',
		zone: 'police',
		patrol: 'police',
		mumbai_police: 'police',
		maha_police: 'police',
		kp: 'police',
		traffic: 'traffic',
		mtp: 'traffic',
		mtp_traffic: 'traffic',
		kp_traffic: 'traffic',
		ems: 'ems',
		'108': 'ems',
		amb108: 'ems',
		ambulance: 'ems',
		municipal: 'municipal',
		bmc: 'municipal',
		bmc_dm: 'municipal',
		kmc: 'municipal',
		disaster: 'disaster',
		msdma: 'disaster',
		wbsdma: 'disaster',
		sdrf: 'disaster',
		ndma: 'ndma',
		ndrf: 'ndma',
		sachet: 'ndma',
		imd: 'imd',
		weather: 'imd',
		metro: 'metro',
		best: 'wbtc',
		wbtc: 'wbtc',
		bus: 'wbtc',
		osm: 'osm',
		openstreetmap: 'osm',
		citizens: 'citizens',
	};

	/**
	 * The mark's owner in the reader's language (a known agency group), else the name on file. The mark on file decides
	 * whose name it is (a role can fall back to another body's mark: disaster → NDMA when the state authority has none on
	 * file); a traffic role keeps its own name under the police badge it shares.
	 */
	export function markName(role: string | null, m: MarkT | null | undefined, lang: string): string {
		const byRole = GROUP[(role ?? '').toLowerCase()];
		const byMark = m ? GROUP[m.key] : undefined;
		if (m && !byMark) return m.name;
		const g = byRole === 'traffic' && byMark === 'police' ? byRole : (byMark ?? byRole);
		return g ? tm(lang, `v3i_agency_${g}`) : (m?.name ?? '');
	}
</script>

<script lang="ts">
	/**
	 * AgencyMark — an agency's or a source's own mark, as-is on a light plate (it belongs to its owner; Sajag is not
	 * affiliated with or endorsed by it — the credit line says so where credits live). When no mark is on file it falls
	 * back to the generic agency tile, so a missing logo never leaves a hole.
	 */
	import { t } from '$lib/i18n/strings';
	import './packs.media';
	import { markFor, type Mark } from './logos';

	let {
		role,
		mark = undefined,
		lang,
		size = 32,
		fallback = '/illustrations/agencies/control_room.svg',
		decorative = false,
		class: cls = '',
	}: {
		/** police, traffic, 108, municipal, disaster, imd … or a city.json agency id (logos.ts ROLE). */
		role: string | null;
		/** A mark already resolved by the caller (sourceMark); `undefined` resolves `role`. */
		mark?: Mark | null;
		lang: string;
		size?: number;
		fallback?: string;
		/** The name is printed next to it: the mark is then decoration for a screen reader. */
		decorative?: boolean;
		class?: string;
	} = $props();

	const m = $derived(mark === undefined ? markFor(role) : mark);
	const name = $derived(markName(role, m, lang));
	const alt = $derived(decorative || !name ? '' : t(lang, 'v3i_mark_alt', name));
	/** A wide mark (a wordmark) keeps its height and grows sideways, up to 3.4 times the size. */
	const aspect = $derived(m ? Math.min(3.4, Math.max(1, m.w / m.h)) : 1);
</script>

{#if m}
	<span class={['mark', `plate-${m.plate}`, cls]} style:--sz={`${size}px`} style:--ar={aspect} data-testid="v3-agency-mark" data-mark={m.key}>
		<img src={m.src} {alt} width={m.w} height={m.h} loading="lazy" decoding="async" />
	</span>
{:else}
	<img class={['mark-fallback', cls]} src={fallback} {alt} width={size} height={size} loading="lazy" style:--sz={`${size}px`} data-testid="v3-agency-mark" data-mark="generic" />
{/if}

<style>
	.mark {
		display: inline-grid;
		flex: none;
		place-items: center;
		box-sizing: border-box;
		width: calc(var(--sz) * var(--ar));
		height: var(--sz);
		border-radius: calc(var(--sz) * 0.26);
		overflow: hidden;
	}

	.mark.plate-light {
		padding: calc(var(--sz) * 0.12);
		background: var(--v3-photo-ink);
		box-shadow: 0 0 0 1px var(--v3-line-2);
	}

	.mark.plate-dark {
		padding: calc(var(--sz) * 0.12);
		background: var(--v3-photo-scrim);
	}

	.mark img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: contain;
	}

	.mark-fallback {
		display: block;
		flex: none;
		width: var(--sz);
		height: var(--sz);
		border-radius: calc(var(--sz) * 0.26);
	}
</style>
