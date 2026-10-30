/**
 * packs.agent — the HI strings (FIX-E-PERF2): the ONE copy that runs. The
 * server render, vite dev and the node tests import it from ./packs.agent.ts; the
 * production browser fetches it as its own chunk (lib/i18n/load.ts). Values
 * are byte-identical to the pre-split module (tests/perf2.unit.mjs pins the
 * key count and a content hash per module and language).
 * ./packs.agent.ts keeps a never-registered text mirror of this block for
 * two AST-reading tests; tests/perf2.unit.mjs pins both copies.
 */

type Pack = Record<string, string | ((...args: unknown[]) => string)>;

export const hi: Pack = {
	agent_suggests: 'AI का सुझाव',
	agent_apply: 'लागू करें',
	agent_dismiss: 'खारिज करें',
	agent_applied: 'लागू किया',
	agent_dismissed: 'खारिज किया',
	agent_ack_failed: 'यहाँ लागू किया — ऑडिट पावती ब्रेन तक नहीं पहुँची',
	agent_proposal: 'केवल प्रस्ताव — मानव के लागू करने तक कुछ नहीं हिलता',
	agent_from: (tier) => `एजेंट से (${tier} स्तर)`,
	agent_more: (n) => `+${n} और`,
	agent_open_map: 'मानचित्र पर खोलें',
	agent_queue_note: 'AI सुझाव सिटी कमांड कैनवास पर प्रतीक्षा करते हैं',
	agent_verb_canvas_fly_to: 'यहाँ जाएँ',
	agent_verb_canvas_track_entity: 'ट्रैक करें',
	agent_verb_canvas_highlight: 'हाइलाइट करें',
	agent_verb_canvas_annotate: 'नोट',
	agent_verb_canvas_set_sensor: 'थर्मल-शैली दृश्य',
	agent_verb_canvas_toggle_layer: 'परत',
	agent_note_label: 'AI नोट',

	chat_suggest_title: 'आज़माएँ',
	chat_suggest_traffic: 'इस कॉरिडोर पर लाइव ट्रैफ़िक',
	chat_suggest_interception: 'इंटरसेप्शन योजना',
	chat_suggest_closures: 'बंद मार्गों की स्थिति',
	chat_suggest_map: 'मानचित्र पर दिखाएँ',
	chat_suggest_stolen: 'चोरी का वाहन मानचित्र पर दिखाएँ',
	chat_suggest_events: 'कौन-सी घटनाएँ सक्रिय हैं?',
	chat_suggest_units: 'यूनिट कहाँ हैं?',
	chat_cited: 'संदर्भ',
	chat_directives: 'मानचित्र पर प्रस्तावित',
	chat_open_city: 'सिटी कमांड में खोलें',

	pal_title: 'कमांड पैलेट',
	// FIX-E-LOOKUP: उदाहरण थर्मल-शैली दृश्य और उसके पैलेट का नाम बोलता है — कोई सेंसर नहीं
	pal_placeholder: 'fly to a plate or junction · show police units near CSMT · layer cameras off · थर्मल-शैली दृश्य: आयरनबो · ask …',
	pal_hint: '⌘K / Ctrl+K · ↑↓ चुनें · Enter चलाएँ · Esc बंद करें',
	pal_fly: 'यहाँ जाएँ',
	pal_units: 'यूनिट दिखाएँ',
	pal_layer: 'परत',
	pal_sensor: 'थर्मल-शैली दृश्य',
	pal_ask: 'एजेंट से पूछें',
	pal_no_match: 'कोई वाहन, जंक्शन, सड़क या इकाई मेल नहीं खाती',
	pal_vehicles_only: 'केवल वाहन (ANPR नंबर प्लेट) — किसी व्यक्ति की खोज नहीं होती',
	pal_sent: 'एजेंट को भेजा — उसके सुझाव इसी कैनवास पर आएँगे',
	pal_units_near: (n, road) => `${road} के पास ${n} यूनिट`,
	pal_none_near: (road) => `अभी ${road} के पास कोई यूनिट नहीं`,
	pal_unknown_road: 'नेटवर्क पर इस नाम की कोई सड़क नहीं',

	dossier_explain: 'इसे समझाएँ',
	dossier_explaining: 'समझा रहा है…',
	dossier_explain_cancel: 'रद्द करें',
	dossier_explain_masked: 'प्लेट छिपी हैं — नामित ड्यूटी अधिकारी उन्हें देखते हैं',
	dossier_explain_failed: 'एजेंट ने उत्तर नहीं दिया',
	dossier_explain_by: 'एजेंट का उत्तर',
	dossier_test: 'परीक्षण',
	dossier_session_officer: 'साइन-इन ड्यूटी अधिकारी',

	canvas_live_paused: 'लाइव रुका',
	canvas_live_paused_hint: 'रीप्ले कैनवास पर है — LIVE पर लाइव परतें फिर चलेंगी',
	canvas_ama_title:
		'सक्रिय मूवमेंट अनुकूलन — स्थिति → हिस्टेरिसिस → नीति सीमाएँ → ट्विन शैडो-जाँच (फ़ेल-क्लोज़्ड) → ऑडिटेड भंडारण। आयु = बैंड की सबसे नई रीडिंग के बाद का समय (घटना की ताज़ा स्थिति रीडिंग, या शहर बैंड का ताज़ा इंजन मूल्यांकन) — बैंड कितनी देर से टिका है, वह नहीं। STALE = 10 मिनट से कोई नई रीडिंग नहीं।',
};
