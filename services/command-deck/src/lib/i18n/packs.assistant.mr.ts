/**
 * packs.assistant — the MR strings (FIX-E-PERF2): the ONE copy that runs. The server render, vite dev and the node
 * tests import it from ./packs.assistant.ts; the production browser fetches it as its own chunk (lib/i18n/load.ts).
 * tests/perf2.unit.mjs pins the key count and a content hash per module and language.
 * Marathi in Devanagari; Western digits; sentences end with a full stop.
 */

type Pack = Record<string, string | ((...args: unknown[]) => string)>;

const s = (v: unknown) => String(v ?? '');

export const mr: Pack = {
	asst_tab: 'सहाय्यक',
	asst_page_title: 'सहाय्यक',
	asst_page_sub: 'तो शहर वाचतो आणि प्रस्ताव देतो. प्रस्ताव जिथे एखादी व्यक्ती तपासते तिथे उघडतात — येथे काहीही लागू होत नाही.',
	asst_actor: 'सजग सहाय्यक · फक्त वाचन',
	asst_context_title: 'संदर्भ',
	asst_context_none: 'काहीही निवडलेले नाही',
	asst_context_hint: 'सहाय्यकाला एखाद्या वस्तूपुरते मर्यादित करण्यासाठी ती निवडा',
	asst_decisions: 'प्रतीक्षेतील निर्णय',
	asst_citations: 'संदर्भित वस्तू',
	asst_clear: 'संभाषण पुसा',
	asst_scope_prefix: 'मर्यादा:',
	asst_scope: (what: unknown) => `मर्यादा: ${s(what)} आणि हे दृश्य`,
	asst_scope_suffix: 'आणि हे दृश्य',
	asst_scope_view: 'मर्यादा: हे दृश्य',
	asst_steps: 'पायऱ्या',
	asst_details: 'तपशील',
	asst_details_tools: 'टूल कॉल',
	asst_lookups_label: 'शोधांनी काय परत दिले',
	asst_grounding_removed: (n: unknown) => (Number(n) === 1 ? '1 विधान काढले: शोधांमध्ये नाही' : `${s(n)} विधाने काढली: शोधांमध्ये नाहीत`),
	asst_details_model: 'मॉडेल',
	asst_details_tier: 'स्तर',
	asst_details_session: 'सत्र',
	asst_steps_toggle: 'पायऱ्या दाखवा',
	asst_thoughts_toggle: 'विचारमांडणी दाखवा',
	asst_proposed_map: (what: unknown) => `नकाशावर प्रस्तावित: ${s(what)}`,
	asst_review_map: 'नकाशावर तपासा',
	asst_decision_card: 'निर्णय प्रतीक्षेत',
	asst_cite_select_map: 'नकाशावर निवडा',
	asst_ev_state_planned: 'नियोजित',
	asst_ev_state_active: 'सक्रिय',
	asst_ev_state_completed: 'पूर्ण',
	asst_ev_state_cancelled: 'रद्द',
	asst_interrupted: 'थांबले — उत्तर पूर्ण होण्यापूर्वी पॅनेल बंद झाले.',
	asst_empty_title: 'सहाय्यकाला विचारा',
	asst_sample_note: 'तपासणीसाठी तयार केलेला लेबल लावलेला नमुना. कोणतेही मॉडेल वापरले नाही.',
	asst_citizen_hold_one: 'खाली 1 एम्युलेटेड होल्ड दिला आहे.',
	asst_citizen_hold_many: (n: unknown) => `खाली ${n} एम्युलेटेड होल्ड दिले आहेत.`,
	asst_driver_choose_stretch: 'आधी आपले स्थान निवडा — मग कॉरिडॉरची विनंती करा.',
};
