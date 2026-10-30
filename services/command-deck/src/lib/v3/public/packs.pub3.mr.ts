/** packs.pub3 — the MR strings (see ./packs.pub3.ts). */
import type { PubKey } from './packs.pub3';

type Fn = (...args: unknown[]) => string;
const s = (v: unknown) => String(v ?? '');

export const mr: Record<PubKey, string | Fn> = {
	v3p_skip: 'मुख्य पानावर जा',
	v3p_logo: 'सजग',
	v3p_lang_short_en: 'EN',
	v3p_lang_short_hi: 'हिं',
	v3p_lang_short_mr: 'मरा',
	v3p_hold_map_alt: 'या घटनेसाठी रोखल्या जाणाऱ्या रस्त्यांचा नकाशा',
	v3p_step: (n: unknown) => `टप्पा ${s(n)}`,
	v3p_sat_credit: 'नकाशाचा डेटा © OpenStreetMap योगदानकर्ते',
	v3p_map_title: 'कॉरिडॉरचा नकाशा',
	v3p_open_driver: 'चालकाचे पान उघडा',
	v3p_view_tabs: 'सार्वजनिक पाने',
};
