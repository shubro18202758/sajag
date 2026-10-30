/**
 * The sample stills a camera page can read (static/samples/cameras, credits in its NOTICE.md). No live CCTV frame
 * reaches Sajag, so every one is shown labelled "Sample still · not live" with its credit beside it. Faces and legible
 * plates are pixelated in the files themselves. tests/field.unit.mjs holds this list, the files and the notice equal.
 */
export interface SampleStill {
	id: string;
	src: string;
	/** What it shows, in English (the alt text and the board entry's note). */
	caption: string;
	author: string;
	licence: string;
	licenceUrl: string;
	source: string;
}

const COMMONS = 'https://commons.wikimedia.org/wiki/File:';

export const SAMPLE_STILLS: readonly SampleStill[] = [
	{
		id: 'waterlogged_mumbai_2017',
		src: '/samples/cameras/waterlogged_mumbai_2017.jpg',
		caption: 'Mumbai, August 2017: buses, autos and a truck wading through a flooded arterial',
		author: 'Paasikivi',
		licence: 'CC BY-SA 4.0',
		licenceUrl: 'https://creativecommons.org/licenses/by-sa/4.0',
		source: `${COMMONS}Flooding_in_Mumbai,_India_2017.jpg`,
	},
	{
		id: 'waterlogged_jvpd',
		src: '/samples/cameras/waterlogged_jvpd.jpg',
		caption: 'JVPD (Juhu–Vile Parle), June 2009: a junction under rainwater',
		author: 'Michael Kohli',
		licence: 'CC BY-SA 2.0',
		licenceUrl: 'https://creativecommons.org/licenses/by-sa/2.0',
		source: `${COMMONS}JVPD_Flooded.jpg`,
	},
	{
		id: 'jam_csmt',
		src: '/samples/cameras/jam_csmt.jpg',
		caption: 'Near CSMT, evening: BEST buses, taxis and cars queueing',
		author: 'Aleksandr Zykov',
		licence: 'CC BY-SA 2.0',
		licenceUrl: 'https://creativecommons.org/licenses/by-sa/2.0',
		source: `${COMMONS}Mumbai,_India_(21007866768).jpg`,
	},
	{
		id: 'tree_prabhadevi',
		src: '/samples/cameras/tree_prabhadevi.jpg',
		caption: 'Old Prabhadevi Road after Cyclone Tauktae (May 2021): a banyan across the road',
		author: 'Rudolph.A.furtado',
		licence: 'CC0',
		licenceUrl: 'https://creativecommons.org/publicdomain/zero/1.0',
		source: `${COMMONS}Banyan_tree_blocks_Old_Prabhadevi_Road.jpg`,
	},
	{
		id: 'jam_monsoon',
		src: '/samples/cameras/jam_monsoon.jpg',
		caption: 'A rain-hour gridlock of cars and kaali-peeli taxis on an arterial',
		author: 'Lakun.patra',
		licence: 'CC BY-SA 4.0',
		licenceUrl: 'https://creativecommons.org/licenses/by-sa/4.0',
		source: `${COMMONS}Traffic_Logger_jam_in_Mumbai.jpg`,
	},
	{
		id: 'clear_weh',
		src: '/samples/cameras/clear_weh.jpg',
		caption: 'Western Express Highway, light free-flowing traffic',
		author: 'Nicholas (Nichalp)',
		licence: 'CC BY-SA 3.0',
		licenceUrl: 'https://creativecommons.org/licenses/by-sa/3.0',
		source: `${COMMONS}Western_Express_Highway_1.jpg`,
	},
];

/** A sample per camera, stable for the camera (so a page always opens on the same still). */
export function sampleFor(cameraId: string | null | undefined): SampleStill {
	let h = 0;
	for (const ch of String(cameraId ?? '')) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
	return SAMPLE_STILLS[h % SAMPLE_STILLS.length];
}

/** What an officer might say, per spoken language (the sheet's "Try saying"; data, not UI copy). */
export const SPOKEN_EXAMPLES: Readonly<Record<'mr' | 'en' | 'hi', string>> = {
	mr: 'हिंदमाता येथे गुडघाभर पाणी, बस अडकली आहे.',
	en: 'Knee-deep water at Hindmata, a bus is stuck.',
	hi: 'हिंदमाता पर घुटनों तक पानी, बस फँसी है।',
};
