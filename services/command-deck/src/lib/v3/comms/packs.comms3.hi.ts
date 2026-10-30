/** packs.comms3 — the HI strings (see ./packs.comms3.ts). Nothing here says a draft was sent. */
import type { CommsKey } from './packs.comms3';

type Fn = (...args: unknown[]) => string;
const s = (v: unknown) => String(v ?? '');

export const hi: Record<CommsKey, string | Fn> = {
	v3c_sub: 'अधिकारी के कॉपी करके भेजने के लिए ड्राफ़्ट',
	v3c_events: 'घटनाएँ',
	v3c_events_aria: 'जिन घटनाओं की सलाह लिखी जा सकती है',
	v3c_map_alt: (title: unknown) => `${s(title)} की जगह का मानचित्र`,
	v3c_no_place: 'इस घटना की अभी कोई मानचित्र-स्थिति नहीं है',
	v3c_open_event: 'घटना खोलें',
	v3c_row_withheld: 'नागरिकों से रोकी गई',
	v3c_facts_used: 'उपयोग किए गए तथ्य',
	v3c_f_kind: 'घटना का प्रकार',
	v3c_f_road: 'खंड',
	v3c_f_hold: 'ठहराव',
	v3c_f_when: 'से',
	v3c_f_alt: 'वैकल्पिक मार्ग',
	v3c_f_unknown: 'नहीं बताया गया',
	v3c_sheet_aria: 'ड्राफ़्ट का रिकॉर्ड और डिस्पैच थ्रेड',
	v3c_close: 'बंद करें',
	v3c_copy_lang: (name: unknown) => `${s(name)} ड्राफ़्ट कॉपी करें`,
	v3c_copied_inline: 'कॉपी हो गया',
	v3c_tpl_hint: 'इस तरह की घटना पर नागरिक यह पढ़ेंगे',
	v3c_withheld_pick: 'इसके ड्राफ़्ट देखने के लिए कोई दूसरा श्रोता चुनें',
};
