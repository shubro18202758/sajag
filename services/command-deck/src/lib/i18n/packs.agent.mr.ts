/**
 * packs.agent — the MR strings (FIX-E-PERF2): the ONE copy that runs. The server render, vite dev and the node tests
 * import it from ./packs.agent.ts; the production browser fetches it as its own chunk (lib/i18n/load.ts).
 * tests/perf2.unit.mjs pins the key count and a content hash per module and language.
 * ./packs.agent.ts keeps a never-registered text mirror of this block for
 * two AST-reading tests; tests/perf2.unit.mjs pins both copies.
 * Marathi in Devanagari; Western digits; sentences end with a full stop. The palette's command examples stay
 * typeable English (the ⌘K grammar is English).
 */

type Pack = Record<string, string | ((...args: unknown[]) => string)>;

export const mr: Pack = {
	agent_suggests: 'एआयची सूचना',
	agent_apply: 'लागू करा',
	agent_dismiss: 'बाजूला करा',
	agent_applied: 'लागू केले',
	agent_dismissed: 'बाजूला केले',
	agent_ack_failed: 'येथे लागू केले — ऑडिटची पोचपावती ब्रेनपर्यंत पोहोचली नाही',
	agent_proposal: 'एक प्रस्ताव — माणूस लागू करेपर्यंत काहीही हलत नाही',
	agent_from: (tier) => `एजंटकडून (${tier} स्तर)`,
	agent_more: (n) => `आणखी +${n}`,
	agent_open_map: 'नकाशावर उघडा',
	agent_queue_note: 'एआयच्या सूचना शहर नियंत्रणाच्या कॅनव्हासवर प्रतीक्षेत असतात',
	agent_verb_canvas_fly_to: 'तिथे जा',
	agent_verb_canvas_track_entity: 'मागोवा घ्या',
	agent_verb_canvas_highlight: 'ठळक करा',
	agent_verb_canvas_annotate: 'टीप',
	agent_verb_canvas_set_sensor: 'थर्मल-शैलीचे दृश्य',
	agent_verb_canvas_toggle_layer: 'स्तर',
	agent_note_label: 'एआय टीप',
	chat_suggest_title: 'हे करून पाहा',
	chat_suggest_traffic: 'या कॉरिडॉरवरील लाइव्ह वाहतूक',
	chat_suggest_interception: 'अडवणूक योजना',
	chat_suggest_closures: 'बंद रस्त्यांची स्थिती',
	chat_suggest_map: 'नकाशावर दाखवा',
	chat_suggest_stolen: 'चोरीचे वाहन नकाशावर दाखवा',
	chat_suggest_events: 'कोणत्या घटना सक्रिय आहेत?',
	chat_suggest_units: 'पथके कुठे आहेत?',
	chat_cited: 'संदर्भित',
	chat_directives: 'नकाशावर प्रस्तावित',
	chat_open_city: 'शहर नियंत्रणात उघडा',
	pal_title: 'आदेश पॅलेट',
	pal_placeholder: 'fly to a plate or junction, show police units near CSMT, layer cameras off, थर्मल-शैलीचे दृश्य: आयर्नबो, ask …',
	pal_hint: '⌘K किंवा Ctrl + K · ↑↓ निवडा, Enter चालवते, Esc बंद करते',
	pal_fly: 'तिथे जा',
	pal_units: 'पथके दाखवा',
	pal_layer: 'स्तर',
	pal_sensor: 'थर्मल-शैलीचे दृश्य',
	pal_ask: 'एजंटला विचारा',
	pal_no_match: 'कोणतेही वाहन, जंक्शन, रस्ता किंवा वस्तू जुळत नाही',
	pal_vehicles_only: 'फक्त वाहने (ANPR नंबर प्लेट) — व्यक्तींचा शोध नाही',
	pal_sent: 'एजंटला पाठवले — त्याच्या सूचना या कॅनव्हासवर येतील',
	pal_units_near: (n, road) => `${road} जवळ ${n} पथके`,
	pal_none_near: (road) => `सध्या ${road} जवळ कोणतेही पथक नाही`,
	pal_unknown_road: 'जाळ्यावर त्या नावाचा रस्ता नाही',
	dossier_explain: 'हे समजावून सांगा',
	dossier_explaining: 'समजावत आहे…',
	dossier_explain_cancel: 'रद्द करा',
	dossier_explain_masked: 'नंबर प्लेट लपवलेल्या — नावाने ओळखले जाणारे ड्युटी अधिकारी त्या पाहतात',
	dossier_explain_failed: 'एजंटने उत्तर दिले नाही',
	dossier_explain_by: 'एजंटचे उत्तर',
	dossier_test: 'चाचणी',
	dossier_session_officer: 'साइन इन केलेले ड्युटी अधिकारी',
	canvas_live_paused: 'लाइव्ह थांबवले',
	canvas_live_paused_hint: 'कॅनव्हासवर रीप्ले चालू आहे — लाइव्ह दाबल्यावर लाइव्ह स्तर पुन्हा सुरू होतात',
	canvas_ama_title: 'सक्रिय ताफ्याचे अनुकूलन — परिस्थिती → हिस्टेरेसिस → धोरणाच्या किमान मर्यादा → ट्विन छाया-मूल्यमापन (अपयशी झाल्यास बंद) → ऑडिट केलेली नोंद. वय = पट्ट्याच्या सर्वात नव्या वाचनापासूनचा वेळ (घटनेचे सर्वात नवे परिस्थिती-वाचन, किंवा शहर-पट्ट्याचे इंजिनचे सर्वात नवे मूल्यमापन) — पट्टा किती वेळ कायम आहे तो नाही. जुने = 10 min नवे वाचन नाही.',
};
