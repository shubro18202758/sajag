/**
 * packs.ui — the HI strings (FIX-E-PERF2): the ONE copy that runs. The
 * server render, vite dev and the node tests import it from ./packs.ui.ts; the
 * production browser fetches it as its own chunk (lib/i18n/load.ts). Values
 * are byte-identical to the pre-split module (tests/perf2.unit.mjs pins the
 * key count and a content hash per module and language).
 */

import type { UiKey } from './packs.ui';
type Fn = (...args: unknown[]) => string;
export const hi: Record<UiKey, string | Fn> = {
	ui_close: 'बंद करें',
	ui_dismiss: 'हटाएँ',
	ui_remove: 'हटाएँ',
	ui_clear: 'साफ़ करें',
	ui_cancel: 'रद्द करें',
	ui_confirm: 'पुष्टि करें',
	ui_loading: 'लोड हो रहा है',
	ui_more: 'और',
	ui_err_404_title: 'पेज नहीं मिला',
	ui_err_404_body: 'इस पते पर कोई पेज नहीं है। बार से कोई मॉड्यूल खोलें, या कॉरिडोर वर्कस्पेस पर जाएँ।',
	ui_err_title: 'यह पेज नहीं दिखाया जा सका',
	ui_err_body: 'इसे लोड करते समय कुछ गड़बड़ हुई। पेज फिर से लोड करें, या कॉरिडोर वर्कस्पेस पर जाएँ।',
	ui_err_home: 'कॉरिडोर वर्कस्पेस खोलें',
	ui_expand: 'खोलें',
	ui_collapse: 'समेटें',
	ui_show_details: 'विवरण दिखाएँ',
	ui_hide_details: 'विवरण छिपाएँ',
	ui_sort_asc: 'आरोही क्रम',
	ui_sort_desc: 'अवरोही क्रम',
	ui_sort_by: (col: unknown) => `${String(col)} से क्रमबद्ध करें`,
	ui_table_empty: 'दिखाने को कुछ नहीं',
	ui_location: 'स्थान',
	ui_notifications: 'सूचनाएँ',
	ui_resize: 'आकार बदलें',
	ui_trend: 'रुझान',

	ui_masked: 'छिपा हुआ',
	ui_masked_tip: 'ड्यूटी अधिकारी का नाम दर्ज होने तक पंजीकरण संख्या छिपी है।',

	ui_prov_emulated: 'इम्युलेटेड',
	ui_prov_simulated: 'सिम्युलेटेड',
	ui_prov_test: 'परीक्षण',
	ui_prov_osint: 'खुला स्रोत',
	ui_prov_emulated_tip: 'परिदृश्य इम्युलेटर से। यह फ़ील्ड रीडिंग नहीं है।',
	ui_prov_simulated_tip: 'सिम्युलेटेड ट्रैफ़िक फ़ीड: कृत्रिम अवलोकन।',
	ui_prov_test_tip: 'अभ्यास या परीक्षण डेटा।',
	ui_prov_osint_tip: 'खुले स्रोतों से। अभी कोई सत्यापन स्थिति नहीं।',
	ui_prov_unknown: 'अज्ञात स्रोत',
	ui_prov_unknown_tip: 'इस पंक्ति का स्रोत यह कंसोल नहीं पहचानता।',
	ui_verif_unverified: 'असत्यापित OSINT',
	ui_verif_news: 'समाचार में रिपोर्ट',
	ui_verif_official: 'आधिकारिक, सत्यापित',
	ui_verif_confirmed: 'अधिकारी द्वारा पुष्ट',
	ui_verif_unverified_tip: 'खुले स्रोत की रिपोर्ट, समाचार या आधिकारिक स्रोत से पुष्ट नहीं।',
	ui_verif_news_tip: 'समाचार माध्यमों द्वारा रिपोर्ट। आधिकारिक स्रोत से सत्यापित नहीं।',
	ui_verif_official_tip: 'आधिकारिक स्रोत द्वारा जारी, जैसे सार्वजनिक चेतावनी।',
	ui_verif_confirmed_tip: 'नामित अधिकारी द्वारा पुष्ट।',

	ui_eye_show: 'दिखाएँ',
	ui_eye_hide: 'छिपाएँ',
	ui_eye_none: 'अभी कोई नहीं',

	ui_time_ist: 'IST',
	ui_time_hint: 'IST, 24-घंटे की घड़ी',
	ui_time_invalid: 'समय hh:mm के रूप में लिखें',
	ui_time_invalid_s: 'समय hh:mm:ss के रूप में लिखें',

	ui_now: 'अभी',
	ui_ago: (x: unknown) => `${String(x)} पहले`,
	ui_in: (x: unknown) => `${String(x)} में`,
	ui_unit_s: 'सेकंड',
	ui_unit_min: 'मिनट',
	ui_unit_h: 'घंटे',
	ui_unit_d: 'दिन',

	ui_hotkeys_title: 'कीबोर्ड शॉर्टकट',
	ui_hk_global: 'सामान्य',
	ui_hk_docks: 'पैनल',
	ui_hk_lists: 'सूचियाँ और तालिकाएँ',
	ui_hk_omnibar: 'वस्तुएँ और आदेश खोजें',
	ui_hk_search: 'खोज पर जाएँ',
	ui_hk_help: 'शॉर्टकट दिखाएँ',
	ui_hk_escape: 'बंद करें, फिर साफ़ करें',
	ui_hk_left_dock: 'बायाँ पैनल दिखाएँ या छिपाएँ',
	ui_hk_right_dock: 'दायाँ पैनल दिखाएँ या छिपाएँ',
	ui_hk_timeline: 'टाइमलाइन दिखाएँ या छिपाएँ',
	ui_hk_next: 'अगली प्रविष्टि',
	ui_hk_prev: 'पिछली प्रविष्टि',
	ui_hk_open: 'प्रविष्टि खोलें',
	ui_hk_rule: 'किसी एक कुंजी से मंज़ूरी, अनमास्क, दंड, डिस्पैच या प्रकाशन नहीं होता।',

	ui_fig_report: (n: unknown) => `${n} रिपोर्ट`,
	ui_fig_reports: (n: unknown) => `${n} रिपोर्टें`,
	ui_fig_context_note: 'ज़िला चेतावनी लागू'
};
