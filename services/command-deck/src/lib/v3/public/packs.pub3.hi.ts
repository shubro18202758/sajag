/** packs.pub3 — the HI strings (see ./packs.pub3.ts). */
import type { PubKey } from './packs.pub3';

type Fn = (...args: unknown[]) => string;
const s = (v: unknown) => String(v ?? '');

export const hi: Record<PubKey, string | Fn> = {
	v3p_skip: 'पृष्ठ पर जाएँ',
	v3p_logo: 'Sajag',
	v3p_lang_short_en: 'EN',
	v3p_lang_short_hi: 'हिं',
	v3p_lang_short_mr: 'मरा',
	v3p_hold_map_alt: 'इस घटना के लिए रुकने वाली सड़कों का मानचित्र',
	v3p_step: (n: unknown) => `चरण ${s(n)}`,
	v3p_sat_credit: 'मानचित्र डेटा © OpenStreetMap योगदानकर्ता',
	v3p_map_title: 'कॉरिडोर का मानचित्र',
	v3p_open_driver: 'ड्राइवर पृष्ठ खोलें',
	v3p_view_tabs: 'सार्वजनिक पृष्ठ',
};
