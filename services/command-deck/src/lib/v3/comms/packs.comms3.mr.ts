/** packs.comms3 — the MR strings (see ./packs.comms3.ts). Nothing here says a draft was sent. */
import type { CommsKey } from './packs.comms3';

type Fn = (...args: unknown[]) => string;
const s = (v: unknown) => String(v ?? '');

export const mr: Record<CommsKey, string | Fn> = {
	v3c_sub: 'अधिकाऱ्याने कॉपी करून पाठवण्यासाठी मसुदे',
	v3c_events: 'घटना',
	v3c_events_aria: 'ज्या घटनांसाठी सूचना लिहिता येते',
	v3c_map_alt: (title: unknown) => `${s(title)} साठी ठिकाणाचा नकाशा`,
	v3c_no_place: 'या घटनेचे नकाशावरील स्थान अजून नाही',
	v3c_open_event: 'घटना उघडा',
	v3c_row_withheld: 'नागरिकांपासून राखून ठेवलेले',
	v3c_facts_used: 'वापरलेली तथ्ये',
	v3c_f_kind: 'घटनेचा प्रकार',
	v3c_f_road: 'रस्त्याचा टप्पा',
	v3c_f_hold: 'रोख',
	v3c_f_when: 'पासून',
	v3c_f_alt: 'पर्यायी मार्ग',
	v3c_f_unknown: 'नमूद नाही',
	v3c_sheet_aria: 'मसुद्यांची नोंद आणि पाठवणीचे धागे',
	v3c_close: 'बंद करा',
	v3c_copy_lang: (name: unknown) => `${s(name)} मसुदा कॉपी करा`,
	v3c_copied_inline: 'कॉपी केले',
	v3c_tpl_hint: 'अशा घटनेसाठी नागरिकाला काय वाचायला मिळेल',
	v3c_withheld_pick: 'त्याचे मसुदे पाहण्यासाठी दुसरा श्रोतृवर्ग निवडा',
};
