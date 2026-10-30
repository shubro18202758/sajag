/**
 * Map chrome string pack (EN / HI / MR) — the canvas's toolbar, navigation,
 * readout, LayerTree, legend, map proposals and replay banner (SPEC §5.3,
 * chrome="v2"), plus the honest imagery chip's words (`ge_imagery_*`, moved
 * here from gods-eye/layers/basemap.ts and converted to sentence case with
 * their test, basemap.unit.mjs).
 *
 * Every new key starts with `map_`. EN is sentence case, no ALL-CAPS word
 * outside the acronym allowlist, at most one " · " per string, titles at
 * most 32 characters (tests/copy-lint.mjs; targets file
 * style-lint.targets/s3.json). Operational names stay Latin in every
 * language (OSM, Google, ion, 3D), like the deck's other codes. Registered
 * additively through registerPack(); the core packs stay untouched.
 *
 * Copy describes only what the system does (SPEC §9.1): FLIR is a
 * thermal-STYLE rendering of the visible scene, no thermal sensor exists;
 * a map proposal moves nothing until a person applies it.
 */
import { registerPack } from './strings';
import { langChunks } from './load';

type Fn = (...args: unknown[]) => string;
type MapPack = Record<string, string | Fn>;

const en = {
	// honest imagery chip (legacy chrome) and the base-map note (v2)
	ge_imagery_photoreal: 'Photoreal 3D · Google',
	ge_imagery_photoreal_loading: 'Photoreal 3D · loading',
	ge_imagery_ion: 'Ion aerial · 3D terrain',
	ge_imagery_osm: 'OSM · dark',
	ge_imagery_osm_fallback: 'OSM dark (fallback)',
	ge_imagery_offline: 'Offline schematic mode',

	// toolbar
	map_toolbar: 'Map tools',
	map_tool_select: 'Select',
	map_tool_shape: 'Select within a shape',
	map_tool_shape_menu: 'Shape options',
	map_tool_shape_select: 'Select within shape',
	map_tool_shape_filter: 'Filter to shape',
	map_tool_shape_clear: 'Clear the shape filter',
	map_tool_shape_hint: 'Click points on the map, then double-click to close the shape',
	map_tool_search_around: 'Search around the selection',
	map_tool_search_around_none: 'Select an object first',
	map_tool_measure: 'Measure distance',
	map_tool_measure_hint: 'Click points on the map; double-click or Esc to finish',
	map_tool_layers: 'Layers',
	map_tool_legend: 'Legend',
	map_tool_follow: 'Follow the selection',
	map_tool_follow_none: 'Select something to follow',
	map_tool_following: (name) => (name != null && name !== '' ? `Following ${String(name)}` : 'Following the selection'),
	map_follow_no_position: (name) =>
		name != null && name !== '' ? `${String(name)} has no position on the map to follow` : 'The selection has no position on the map to follow',
	map_tool_tour: 'Guided tour',
	map_tool_tour_stop: 'Stop the guided tour',
	map_tool_exit: 'Exit map mode',
	map_mode_live: 'Live',
	map_mode_window: 'Not live',
	map_mode_replay: (run) => (run != null ? `Replay · run ${String(run)}` : 'Replay'),
	map_mode_live_tip: 'Live. Open the timeline to set a window or play a replay.',
	map_mode_window_tip: 'A time window is set. Open the timeline to return to live.',
	map_mode_replay_tip: 'A recorded tape is playing on its own time axis.',

	// the thermal-STYLE view: a toolbar button of its own (SPEC §16.5,
	// confirmed the other way 2026-10-25 — one click away, never a sensor)
	map_tool_thermal: 'Thermal-style view',
	map_tool_thermal_tip: 'Thermal-style view — a visual filter, no thermal sensor',
	map_thermal_on: 'Thermal-style view (visual filter)',
	map_flir_note: 'Visual filter, no thermal sensor',
	map_flir_off: 'Normal colours',
	map_flir_whot: 'Thermal style, white hot',
	map_flir_bhot: 'Thermal style, black hot',
	map_flir_iron: 'Thermal style, ironbow',
	// FIX-E-LOOKUP: the palettes in words (the omnibar's sensor command names
	// the picked palette through these — never the raw flir-* id)
	map_pal_raw: 'normal colours',
	map_pal_whot: 'white hot',
	map_pal_bhot: 'black hot',
	map_pal_iron: 'ironbow',

	// navigation and readout
	map_zoom_in: 'Zoom in',
	map_zoom_out: 'Zoom out',
	map_reset_north: 'Reset north',
	map_rule_note: 'Vehicles only · penalties need a named officer',
	map_rule_note_short: 'Vehicles only',
	map_imagery_not_live: 'not a live image',
	map_scale: 'Scale',
	map_cursor: 'Position',

	// LayerTree
	map_layers_title: 'Layers',
	map_basemap_title: 'Base map',
	map_basemap_photoreal: 'Photoreal',
	map_basemap_streets: 'Streets',
	map_basemap_dark: 'Dark',
	map_basemap_needs_key: 'Needs the Cesium ion key on this deck',
	map_group_traffic: 'Traffic',
	map_group_enforcement: 'Enforcement',
	map_group_response: 'Response',
	map_group_corridors: 'Corridors',
	map_group_intelligence: 'Reported events',
	map_layer_flow: 'Traffic flow',
	map_layer_signals: 'Junctions and signals',
	map_layer_anomalies: 'Feed anomalies',
	map_layer_traces: 'Watchlisted vehicles',
	map_layer_enforcement: 'Decisions waiting',
	map_layer_cameras: 'ANPR cameras',
	map_layer_units: 'Units',
	map_layer_dispatch: 'Dispatches',
	map_layer_events: 'Events and routes',
	map_layer_convoy: 'Convoy',
	map_layer_photoreal: 'Photoreal 3D city',
	map_layer_paused: 'Paused while the replay plays',
	map_layer_feed_down: 'Feed problem',

	// legend
	map_legend_title: 'Legend',
	map_legend_flow: 'Traffic flow: free → jammed',
	map_legend_flow_simulated: 'Traffic flow (simulated): free → jammed',
	map_legend_markers: 'Markers',
	map_legend_alert: 'Watchlisted vehicle and its reads',
	map_legend_decision: 'A decision is waiting',
	map_legend_selected: 'Selected',
	map_legend_neutral: 'Other objects: type by glyph',
	map_legend_cluster: 'Co-located markers',
	map_legend_route: 'Convoy and its route',
	map_legend_event: 'Corridor events',
	map_legend_close: 'Close the legend',

	// clusters and labels
	map_cluster_list: (n) => `${String(n)} objects here`,
	map_cluster_spread: 'Click to spread them out',

	// map proposals (the home of map proposals, SPEC §5.4)
	map_proposal_head: (label) => `Proposed on the map · ${String(label)}`,
	map_proposal_tier: (tier) => `${String(tier)} tier`,
	map_proposal_note: 'Nothing moves until you apply it',

	// replay banner (SPEC §7.3, §9: a replay names its provenance — an
	// emulator tape is an emulated recording; a live capture is never so
	// labelled)
	map_replay_banner: (run) => (run != null ? `Replay · run ${String(run)}` : 'Replay'),
	map_replay_emulated: 'Emulated',
	map_live_paused: 'live layers paused',
	map_live_paused_hint: 'The live layers stand down while the tape plays. The inbox and the live strip stay live.',

	// shape and measure results
	map_measure_total: (km) => `Distance ${String(km)}`,
	map_shape_selected: (n) => `${String(n)} selected in the shape`,
	map_shape_filtered: (n) => `${String(n)} shown inside the shape`,
} satisfies MapPack;

export type MapKey = keyof typeof en;

const hi: Record<MapKey, string | Fn> = {
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

const mr: Record<MapKey, string | Fn> = {
	ge_imagery_photoreal: 'फोटोरिअल 3D · Google',
	ge_imagery_photoreal_loading: 'फोटोरिअल 3D · लोड होत आहे',
	ge_imagery_ion: 'Cesium ion हवाई छायाचित्र · 3D भूभाग',
	ge_imagery_osm: 'OSM · गडद',
	ge_imagery_osm_fallback: 'OSM गडद (पर्याय)',
	ge_imagery_offline: 'ऑफलाइन रेखाचित्र मोड',
	map_toolbar: 'नकाशाची साधने',
	map_tool_select: 'निवडा',
	map_tool_shape: 'आकाराच्या आत निवडा',
	map_tool_shape_menu: 'आकाराचे पर्याय',
	map_tool_shape_select: 'आकाराच्या आत निवडा',
	map_tool_shape_filter: 'आकारापुरते गाळा',
	map_tool_shape_clear: 'आकाराचा फिल्टर पुसा',
	map_tool_shape_hint: 'नकाशावर बिंदू निवडा, मग आकार बंद करण्यासाठी डबल-क्लिक करा',
	map_tool_search_around: 'निवडीभोवती शोधा',
	map_tool_search_around_none: 'आधी एखादी वस्तू निवडा',
	map_tool_measure: 'अंतर मोजा',
	map_tool_measure_hint: 'नकाशावर बिंदू निवडा; संपवण्यासाठी डबल-क्लिक करा किंवा Esc दाबा',
	map_tool_layers: 'स्तर',
	map_tool_legend: 'संकेतसूची',
	map_tool_follow: 'निवडीचा पाठपुरावा करा',
	map_tool_follow_none: 'पाठपुराव्यासाठी काहीतरी निवडा',
	map_tool_following: (name) => (name != null && name !== '' ? `${String(name)} चा पाठपुरावा सुरू` : 'निवडीचा पाठपुरावा सुरू'),
	map_follow_no_position: (name) =>
		name != null && name !== '' ? `पाठपुराव्यासाठी ${String(name)} चे नकाशावर स्थान नाही` : 'पाठपुराव्यासाठी निवडीचे नकाशावर स्थान नाही',
	map_tool_tour: 'मार्गदर्शित फेरी',
	map_tool_tour_stop: 'मार्गदर्शित फेरी थांबवा',
	map_tool_exit: 'नकाशा मोडमधून बाहेर पडा',
	map_mode_live: 'लाइव्ह',
	map_mode_window: 'लाइव्ह नाही',
	map_mode_replay: (run) => (run != null ? `रीप्ले · फेरी ${String(run)}` : 'रीप्ले'),
	map_mode_live_tip: 'लाइव्ह. वेळेची खिडकी ठरवण्यासाठी किंवा रीप्ले चालवण्यासाठी कालरेषा उघडा.',
	map_mode_window_tip: 'वेळेची खिडकी ठरवली आहे. लाइव्हवर परत जाण्यासाठी कालरेषा उघडा.',
	map_mode_replay_tip: 'नोंदलेली टेप तिच्या स्वतःच्या वेळेनुसार चालू आहे.',
	map_tool_thermal: 'थर्मल-शैलीचे दृश्य',
	map_tool_thermal_tip: 'थर्मल-शैलीचे दृश्य — व्हिज्युअल फिल्टर, थर्मल सेन्सर नाही',
	map_thermal_on: 'थर्मल-शैलीचे दृश्य (व्हिज्युअल फिल्टर)',
	map_flir_note: 'व्हिज्युअल फिल्टर, थर्मल सेन्सर नाही',
	map_flir_off: 'नेहमीचे रंग',
	map_flir_whot: 'थर्मल शैली, पांढरे उष्ण',
	map_flir_bhot: 'थर्मल शैली, काळे उष्ण',
	map_flir_iron: 'थर्मल शैली, आयर्नबो',
	map_pal_raw: 'नेहमीचे रंग',
	map_pal_whot: 'पांढरे उष्ण',
	map_pal_bhot: 'काळे उष्ण',
	map_pal_iron: 'आयर्नबो',
	map_zoom_in: 'जवळ करा',
	map_zoom_out: 'दूर करा',
	map_reset_north: 'उत्तर दिशा पुन्हा वर',
	map_rule_note: 'फक्त वाहने · दंडासाठी नावाने ओळखले जाणारे अधिकारी लागतात',
	map_rule_note_short: 'फक्त वाहने',
	map_imagery_not_live: 'लाइव्ह प्रतिमा नाही',
	map_scale: 'प्रमाण',
	map_cursor: 'स्थान',
	map_layers_title: 'स्तर',
	map_basemap_title: 'मूळ नकाशा',
	map_basemap_photoreal: 'फोटोरिअल',
	map_basemap_streets: 'रस्ते',
	map_basemap_dark: 'गडद',
	map_basemap_needs_key: 'या डेकवर Cesium ion की आवश्यक',
	map_group_traffic: 'वाहतूक',
	map_group_enforcement: 'अंमलबजावणी',
	map_group_response: 'प्रतिसाद',
	map_group_corridors: 'कॉरिडॉर',
	map_group_intelligence: 'नोंदवलेल्या घटना',
	map_layer_flow: 'वाहतुकीचा प्रवाह',
	map_layer_signals: 'जंक्शन आणि सिग्नल',
	map_layer_anomalies: 'फीडमधील विसंगती',
	map_layer_traces: 'वॉचलिस्टवरील वाहने',
	map_layer_enforcement: 'प्रतीक्षेतील निर्णय',
	map_layer_cameras: 'ANPR कॅमेरे',
	map_layer_units: 'पथके',
	map_layer_dispatch: 'रवानगी',
	map_layer_events: 'घटना आणि मार्ग',
	map_layer_convoy: 'ताफा',
	map_layer_photoreal: 'फोटोरिअल 3D शहर',
	map_layer_paused: 'रीप्ले चालू असताना थांबवलेले',
	map_layer_feed_down: 'फीडमध्ये अडचण',
	map_legend_title: 'संकेतसूची',
	map_legend_flow: 'वाहतुकीचा प्रवाह: मोकळा → कोंडी',
	map_legend_flow_simulated: 'वाहतुकीचा प्रवाह (सिम्युलेटेड): मोकळा → कोंडी',
	map_legend_markers: 'खुणा',
	map_legend_alert: 'वॉचलिस्टवरील वाहन आणि त्याची वाचने',
	map_legend_decision: 'एक निर्णय प्रतीक्षेत आहे',
	map_legend_selected: 'निवडलेले',
	map_legend_neutral: 'इतर वस्तू: चिन्हानुसार प्रकार',
	map_legend_cluster: 'एकाच ठिकाणच्या खुणा',
	map_legend_route: 'ताफा आणि त्याचा मार्ग',
	map_legend_event: 'कॉरिडॉर घटना',
	map_legend_close: 'संकेतसूची बंद करा',
	map_cluster_list: (n) => `येथे ${String(n)} वस्तू`,
	map_cluster_spread: 'पसरवण्यासाठी क्लिक करा',
	map_proposal_head: (label) => `नकाशावर प्रस्तावित · ${String(label)}`,
	map_proposal_tier: (tier) => `${String(tier)} स्तर`,
	map_proposal_note: 'आपण लागू करेपर्यंत काहीही हलत नाही',
	map_replay_banner: (run) => (run != null ? `रीप्ले · फेरी ${String(run)}` : 'रीप्ले'),
	map_replay_emulated: 'एम्युलेटेड',
	map_live_paused: 'लाइव्ह स्तर थांबवलेले',
	map_live_paused_hint: 'टेप चालू असताना लाइव्ह स्तर थांबतात. इनबॉक्स आणि लाइव्ह पट्टी लाइव्हच राहतात.',
	map_measure_total: (km) => `अंतर ${String(km)}`,
	map_shape_selected: (n) => `आकारात ${String(n)} निवडलेले`,
	map_shape_filtered: (n) => `आकाराच्या आत ${String(n)} दाखवलेले`,
};

registerPack('en', en);

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: Record<string, string | Fn>): void {
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): the HI and MR strings that RUN live ONLY in
 * ./packs.map.hi.ts and ./packs.map.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.map.hi')).hi);
	adopt('mr', (await import('./packs.map.mr')).mr);
} else {
	await langChunks('packs.map', (code) =>
		code === 'hi' ? import('./packs.map.hi').then((c) => adopt('hi', c.hi)) : import('./packs.map.mr').then((c) => adopt('mr', c.mr)),
	);
}

/*
 * TEXT MIRROR — not a source, never registered, never shipped. The `hi` and
 * `mr` literals above are a byte-identical copy of ./packs.map.hi.ts and
 * ./packs.map.mr.ts kept ONLY because two tests outside this work package
 * (tests/thermal-toolbar.unit.mjs, tests/omnibar-lookup.unit.mjs) read the
 * HI/MR strings as TypeScript AST off `registerPack('hi'|'mr', …)` calls in
 * THIS file. This function is never called (every bundle drops it and the
 * literals with it); tests/perf2.unit.mjs pins this copy and the shipped
 * copy, each on its own, to the reviewed golden, so the two can never drift.
 * Delete it once those tests read the per-language modules (FIX-E-PERF2
 * report, blocked request).
 */
function astTextMirror(): void {
	registerPack('hi', hi);
	registerPack('mr', mr);
}

/** Every key of the pack (tests check HI and MR cover each one). */
export const MAP_PACK_KEYS: readonly MapKey[] = Object.keys(en) as MapKey[];
