/**
 * packs.map — the HI strings (FIX-E-PERF2): the ONE copy that runs. The
 * server render, vite dev and the node tests import it from ./packs.map.ts; the
 * production browser fetches it as its own chunk (lib/i18n/load.ts). Values
 * are byte-identical to the pre-split module (tests/perf2.unit.mjs pins the
 * key count and a content hash per module and language).
 * ./packs.map.ts keeps a never-registered text mirror of this block for
 * two AST-reading tests; tests/perf2.unit.mjs pins both copies.
 */

import type { MapKey } from './packs.map';
type Fn = (...args: unknown[]) => string;
type Pack = Record<string, string | ((...args: unknown[]) => string)>;

export const hi: Record<MapKey, string | Fn> = {
	ge_imagery_photoreal: 'यथार्थ 3D शहर · Google',
	ge_imagery_photoreal_loading: 'यथार्थ 3D · लोड हो रहा है',
	ge_imagery_ion: 'ion हवाई चित्र · 3D भू-भाग',
	ge_imagery_osm: 'OSM · डार्क',
	ge_imagery_osm_fallback: 'OSM डार्क (वैकल्पिक)',
	ge_imagery_offline: 'ऑफ़लाइन योजनाबद्ध मोड',

	map_toolbar: 'मानचित्र उपकरण',
	map_tool_select: 'चुनें',
	map_tool_shape: 'आकृति के भीतर चुनें',
	map_tool_shape_menu: 'आकृति विकल्प',
	map_tool_shape_select: 'आकृति के भीतर चुनें',
	map_tool_shape_filter: 'आकृति तक सीमित करें',
	map_tool_shape_clear: 'आकृति फ़िल्टर हटाएँ',
	map_tool_shape_hint: 'मानचित्र पर बिंदु चुनें, फिर आकृति बंद करने के लिए डबल-क्लिक करें',
	map_tool_search_around: 'चयन के आसपास खोजें',
	map_tool_search_around_none: 'पहले कोई वस्तु चुनें',
	map_tool_measure: 'दूरी मापें',
	map_tool_measure_hint: 'मानचित्र पर बिंदु चुनें; समाप्त करने के लिए डबल-क्लिक या Esc',
	map_tool_layers: 'परतें',
	map_tool_legend: 'संकेत-सूची',
	map_tool_follow: 'चयन का अनुसरण करें',
	map_tool_follow_none: 'अनुसरण के लिए कुछ चुनें',
	map_tool_following: (name) => (name != null && name !== '' ? `${String(name)} का अनुसरण` : 'चयन का अनुसरण'),
	map_follow_no_position: (name) =>
		name != null && name !== ''
			? `${String(name)} की मानचित्र पर कोई स्थिति नहीं है, अनुसरण संभव नहीं`
			: 'चयन की मानचित्र पर कोई स्थिति नहीं है, अनुसरण संभव नहीं',
	map_tool_tour: 'निर्देशित भ्रमण',
	map_tool_tour_stop: 'निर्देशित भ्रमण रोकें',
	map_tool_exit: 'मानचित्र मोड से बाहर',
	map_mode_live: 'लाइव',
	map_mode_window: 'लाइव नहीं',
	map_mode_replay: (run) => (run != null ? `रीप्ले · रन ${String(run)}` : 'रीप्ले'),
	map_mode_live_tip: 'लाइव। समय-सीमा या रीप्ले के लिए टाइमलाइन खोलें।',
	map_mode_window_tip: 'समय-सीमा लगी है। लाइव पर लौटने के लिए टाइमलाइन खोलें।',
	map_mode_replay_tip: 'एक रिकॉर्ड की गई टेप अपनी समय-अक्ष पर चल रही है।',

	// FIX-E-LOOKUP: "दृश्य … (दृश्य फ़िल्टर)" नहीं — दृश्य शब्द एक बार; फ़िल्टर विज़ुअल फ़िल्टर
	map_tool_thermal: 'थर्मल-शैली दृश्य',
	map_tool_thermal_tip: 'थर्मल-शैली दृश्य — केवल एक विज़ुअल फ़िल्टर, कोई थर्मल सेंसर नहीं',
	map_thermal_on: 'थर्मल-शैली दृश्य (विज़ुअल फ़िल्टर)',
	map_flir_note: 'विज़ुअल फ़िल्टर, कोई थर्मल सेंसर नहीं',
	map_flir_off: 'सामान्य रंग',
	map_flir_whot: 'थर्मल शैली, सफ़ेद गर्म',
	map_flir_bhot: 'थर्मल शैली, काला गर्म',
	map_flir_iron: 'थर्मल शैली, आयरनबो',
	map_pal_raw: 'सामान्य रंग',
	map_pal_whot: 'सफ़ेद गर्म',
	map_pal_bhot: 'काला गर्म',
	map_pal_iron: 'आयरनबो',

	map_zoom_in: 'ज़ूम इन',
	map_zoom_out: 'ज़ूम आउट',
	map_reset_north: 'उत्तर दिशा पर लौटें',
	map_rule_note: 'केवल वाहन · दंड के लिए नामित अधिकारी आवश्यक',
	map_rule_note_short: 'केवल वाहन',
	map_imagery_not_live: 'लाइव तस्वीर नहीं',
	map_scale: 'पैमाना',
	map_cursor: 'स्थिति',

	map_layers_title: 'परतें',
	map_basemap_title: 'आधार मानचित्र',
	map_basemap_photoreal: 'यथार्थ',
	map_basemap_streets: 'सड़कें',
	map_basemap_dark: 'डार्क',
	map_basemap_needs_key: 'इस डेक पर Cesium ion कुंजी आवश्यक है',
	map_group_traffic: 'यातायात',
	map_group_enforcement: 'प्रवर्तन',
	map_group_response: 'प्रतिक्रिया',
	map_group_corridors: 'कॉरिडोर',
	map_group_intelligence: 'रिपोर्ट की गई घटनाएँ',
	map_layer_flow: 'यातायात प्रवाह',
	map_layer_signals: 'जंक्शन और सिग्नल',
	map_layer_anomalies: 'फ़ीड विसंगतियाँ',
	map_layer_traces: 'निगरानी सूची के वाहन',
	map_layer_enforcement: 'निर्णय प्रतीक्षित',
	map_layer_cameras: 'ANPR कैमरे',
	map_layer_units: 'इकाइयाँ',
	map_layer_dispatch: 'प्रेषण',
	map_layer_events: 'घटनाएँ और मार्ग',
	map_layer_convoy: 'काफ़िला',
	map_layer_photoreal: 'यथार्थ 3D शहर',
	map_layer_paused: 'रीप्ले चलते समय रुका हुआ',
	map_layer_feed_down: 'फ़ीड में समस्या',

	map_legend_title: 'संकेत-सूची',
	map_legend_flow: 'यातायात प्रवाह: मुक्त → जाम',
	map_legend_flow_simulated: 'यातायात प्रवाह (सिम्युलेटेड): मुक्त → जाम',
	map_legend_markers: 'चिह्न',
	map_legend_alert: 'निगरानी सूची का वाहन और उसकी रीडिंग',
	map_legend_decision: 'एक निर्णय प्रतीक्षित है',
	map_legend_selected: 'चयनित',
	map_legend_neutral: 'अन्य वस्तुएँ: प्रकार चिह्न से',
	map_legend_cluster: 'एक ही स्थान के चिह्न',
	map_legend_route: 'काफ़िला और उसका मार्ग',
	map_legend_event: 'कॉरिडोर घटनाएँ',
	map_legend_close: 'संकेत-सूची बंद करें',

	map_cluster_list: (n) => `यहाँ ${String(n)} वस्तुएँ`,
	map_cluster_spread: 'फैलाने के लिए क्लिक करें',

	map_proposal_head: (label) => `मानचित्र पर प्रस्ताव · ${String(label)}`,
	map_proposal_tier: (tier) => `${String(tier)} स्तर`,
	map_proposal_note: 'लागू करने तक कुछ नहीं बदलता',

	map_replay_banner: (run) => (run != null ? `रीप्ले · रन ${String(run)}` : 'रीप्ले'),
	map_replay_emulated: 'इम्यूलेटेड',
	map_live_paused: 'लाइव परतें रुकी हुई',
	map_live_paused_hint: 'टेप चलते समय लाइव परतें रुकती हैं। इनबॉक्स और लाइव पट्टी लाइव रहती हैं।',

	map_measure_total: (km) => `दूरी ${String(km)}`,
	map_shape_selected: (n) => `आकृति में ${String(n)} चयनित`,
	map_shape_filtered: (n) => `आकृति के भीतर ${String(n)} दिखाए गए`,
};
