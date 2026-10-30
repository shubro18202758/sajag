/**
 * The city strings the deck's own city components print (the public pages' emergency numbers, the map's line for a
 * report in a script the reader does not read), EN / MR / HI. Agency
 * names come from the City Pack ($lib/city agencyName), never from here. Registered additively (first registration
 * wins); every key starts with `city_`.
 */
import { registerPack } from '$lib/i18n/strings';

type Fn = (...args: unknown[]) => string;
const s = (v: unknown) => String(v ?? '');

const en = {
	city_emergency_title: 'Emergency numbers',
	city_emergency_note: 'A call goes straight to the service. Sajag takes no calls.',
	city_emergency_call: (n: unknown) => `Call ${s(n)}`,
	city_text_brief_other: 'In another script: open it for the original text',
};

export type CityKey = keyof typeof en;

const mr: Record<CityKey, string | Fn> = {
	city_emergency_title: 'आपत्कालीन क्रमांक',
	city_emergency_note: 'कॉल थेट त्या सेवेकडे जातो. सजग कॉल घेत नाही.',
	city_emergency_call: (n: unknown) => `${s(n)} वर कॉल करा`,
	city_text_brief_other: 'दुसऱ्या लिपीत: मूळ मजकुरासाठी उघडा',
};

const hi: Record<CityKey, string | Fn> = {
	city_emergency_title: 'आपातकालीन नंबर',
	city_emergency_note: 'कॉल सीधे उसी सेवा को जाता है। सजग कोई कॉल नहीं लेता।',
	city_emergency_call: (n: unknown) => `${s(n)} पर कॉल करें`,
	city_text_brief_other: 'दूसरी लिपि में: मूल पाठ के लिए खोलें',
};

export const CITY_PACKS = { en, mr, hi } as const;

registerPack('en', en);
registerPack('mr', mr);
registerPack('hi', hi);
