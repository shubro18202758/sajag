<script lang="ts">
	/**
	 * The mark beside an Advisories audience (V3-P7): zone officers carry the city police's mark, 108 control the 108
	 * service's, the municipality the corporation's; citizens the deck's own generic badge. Decoration: the audience's
	 * name is printed beside it. A missing mark falls back to the generic badge.
	 */
	import AgencyMark from '../media/AgencyMark.svelte';

	let { audience, lang }: { audience: string; lang: string } = $props();

	const ROLE: Readonly<Record<string, string>> = { zones: 'police', ambulance108: '108', municipal: 'municipal' };
	const FALLBACK: Readonly<Record<string, string>> = {
		citizens: '/illustrations/agencies/volunteers.svg',
		zones: '/illustrations/agencies/police.svg',
		ambulance108: '/illustrations/agencies/ems.svg',
		municipal: '/illustrations/agencies/municipal.svg',
	};
</script>

<AgencyMark role={ROLE[audience] ?? null} {lang} size={22} fallback={FALLBACK[audience] ?? '/illustrations/agencies/control_room.svg'} decorative class="aud-mark" />
