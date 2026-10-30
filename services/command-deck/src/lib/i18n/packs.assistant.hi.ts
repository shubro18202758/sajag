/**
 * packs.assistant — the HI strings (FIX-E-PERF2): the ONE copy that runs. The
 * server render, vite dev and the node tests import it from ./packs.assistant.ts; the
 * production browser fetches it as its own chunk (lib/i18n/load.ts). Values
 * are byte-identical to the pre-split module (tests/perf2.unit.mjs pins the
 * key count and a content hash per module and language).
 */

type Pack = Record<string, string | ((...args: unknown[]) => string)>;

const s = (v: unknown) => String(v ?? '');
export const hi: Pack = {
	asst_tab: 'सहायक',
	asst_page_title: 'सहायक',
	asst_page_sub: 'यह शहर को पढ़ता है और सुझाव देता है। सुझाव वहीं खुलते हैं जहाँ कोई व्यक्ति उन्हें देखता है — यहाँ कुछ लागू नहीं होता।',
	asst_actor: 'सजग सहायक · केवल पठन',
	asst_context_title: 'संदर्भ',
	asst_context_none: 'कुछ चयनित नहीं',
	asst_context_hint: 'सहायक को इस पर केंद्रित करने के लिए कोई वस्तु चुनें',
	asst_decisions: 'निर्णय प्रतीक्षारत',
	asst_citations: 'संदर्भित वस्तुएँ',
	asst_clear: 'बातचीत साफ़ करें',

	asst_scope_prefix: '',
	asst_scope: (what: unknown) => `${s(what)} और इस दृश्य तक सीमित`,
	asst_scope_suffix: 'और इस दृश्य तक सीमित',
	asst_scope_view: 'इस दृश्य तक सीमित',

	asst_steps: 'चरण',
	asst_details: 'विवरण',
	asst_details_tools: 'टूल कॉल',
	asst_lookups_label: 'लुकअप में क्या मिला',
	asst_grounding_removed: (n) => `${String(n)} कथन हटाए गए: लुकअप में नहीं थे`,
	asst_details_model: 'मॉडल',
	asst_details_tier: 'स्तर',
	asst_details_session: 'सत्र',
	asst_steps_toggle: 'चरण दिखाएँ',
	asst_thoughts_toggle: 'तर्क दिखाएँ',

	asst_proposed_map: (what: unknown) => `नक्शे पर प्रस्तावित: ${s(what)}`,
	asst_review_map: 'इसे नक्शे पर देखें',
	asst_decision_card: 'निर्णय प्रतीक्षारत',

	asst_cite_select_map: 'नक्शे पर चुनें',

	asst_ev_state_planned: 'नियोजित',
	asst_ev_state_active: 'सक्रिय',
	asst_ev_state_completed: 'पूर्ण',
	asst_ev_state_cancelled: 'रद्द',
	asst_interrupted: 'रुका — उत्तर पूरा होने से पहले पैनल बंद हो गया।',

	asst_empty_title: 'सहायक से पूछें',
	asst_sample_note: 'समीक्षा के लिए बनाया गया नमूना चरण। कोई मॉडल नहीं चला।',

	asst_citizen_hold_one: 'नीचे 1 एम्युलेटेड ठहराव सूचीबद्ध है।',
	asst_citizen_hold_many: (n: unknown) => `नीचे ${n} एम्युलेटेड ठहराव सूचीबद्ध हैं।`,

	asst_driver_choose_stretch: 'पहले अपनी जगह चुनें — फिर कॉरिडोर की विनंती करें।',
};
