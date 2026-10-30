/**
 * packs.osint — the HI strings (FIX-E-PERF2): the ONE copy that runs. The
 * server render, vite dev and the node tests import it from ./packs.osint.ts; the
 * production browser fetches it as its own chunk (lib/i18n/load.ts). Values
 * are byte-identical to the pre-split module (tests/perf2.unit.mjs pins the
 * key count and a content hash per module and language).
 */

type Fn = (...args: unknown[]) => string;
type OsintPack = Record<string, string | Fn>;
export const hi: OsintPack = {
	kind_reported_crime: 'रिपोर्ट किया गया अपराध',
	kind_public_disorder: 'सार्वजनिक अव्यवस्था',
	kind_road_accident: 'सड़क दुर्घटना',
	kind_hazard: 'खतरा',
	kind_flooding: 'जलभराव',
	kind_infra_failure: 'बुनियादी ढांचे की विफलता',

	os_group_situation: 'स्थिति',
	os_group_verification: 'सत्यापन',
	os_group_location: 'स्थान',
	os_group_sources: 'स्रोत',
	os_group_live: 'वर्तमान स्थिति',
	os_group_place: 'स्थान',

	os_class: 'वर्ग',
	os_subtype: 'उपप्रकार',
	os_correlated: 'सहसंबद्ध वर्ग',
	os_summary: 'सारांश',
	os_event_kind_reported_crime: 'रिपोर्ट किया गया अपराध',
	os_event_kind_public_disorder: 'सार्वजनिक अव्यवस्था',
	os_event_kind_road_accident: 'सड़क दुर्घटना',
	os_event_kind_hazard: 'खतरा',
	os_event_kind_flooding: 'जलभराव',
	os_event_kind_infra_failure: 'बुनियादी ढांचे की विफलता',
	os_event_kind_other: 'गलियारा घटना',

	os_independent_publishers: 'स्वतंत्र प्रकाशक',
	os_cross_type: 'पार-प्रकार पुष्टि',
	os_yes: 'हाँ',
	os_no: 'नहीं',

	os_toponym: 'स्थान',
	os_road: 'सड़क',
	os_junction: 'चौक',
	os_geocode: 'भू-स्थान विश्वसनीयता',
	os_bucket_high: 'उच्च',
	os_bucket_medium: 'मध्यम',
	os_bucket_low: 'निम्न',
	os_area_note: 'ज़िला-स्तर की रिपोर्ट: कोई गली-स्तर का स्थान नहीं',

	os_source_link_withheld: 'स्रोत लिंक सुरक्षित (उसमें किसी व्यक्ति का नाम हो सकता है)',
	os_context_official: 'ज़िला चेतावनी लागू',
	os_context_report: 'ज़िला-स्तर की रिपोर्ट लागू',
	os_fig_context_official: 'ज़िला चेतावनी लागू',
	os_fig_context_report: 'ज़िला-स्तर की रिपोर्ट लागू',
	os_fetch_cached: 'कैश किया नमूना',
	os_tier_official: 'आधिकारिक',
	os_tier_aggregator: 'समाचार एकत्रकर्ता',
	os_tier_news_regional: 'क्षेत्रीय समाचार',
	os_tier_news_national: 'राष्ट्रीय समाचार',
	os_tier_social_unverified: 'असत्यापित सामाजिक',

	os_pick_reported: 'रिपोर्ट किया गया',
	os_pick_credibility: 'विश्वसनीयता',
	os_pick_street: 'प्रतिक्रिया के लिए रिपोर्ट की गई स्थिति।',
	os_pick_district: 'ज़िला-स्तर की रिपोर्ट, ज़िले के संदर्भ बिंदु पर दिखाई गई। रिपोर्ट पूरे ज़िले की है, इस जगह की नहीं।',
	os_pick_area_ring: 'ज़िले के संदर्भ बिंदु के चारों ओर एक चिह्न-घेरा, रिपोर्ट का क्षेत्र नहीं।',
	os_pick_never_people: 'रिपोर्ट की गई स्थितियाँ स्थानों के बारे में हैं, कभी लोगों के बारे में नहीं।',
	os_layer_held_one: 'एकल-पोस्ट सामाजिक रिपोर्ट पूरे शहर में रोकी गई (कभी नहीं दिखाई गई)',
	os_layer_down: 'सिटी फ्यूज़न सेवा उपलब्ध नहीं — रिपोर्ट की गई स्थितियाँ नहीं दिखाई गईं',
	os_layer_on_canvas: (n: unknown) => `मानचित्र पर ${n} रिपोर्ट की गई स्थितियाँ`,
	os_layer_area: (n: unknown) => `${n} क्षेत्र-स्तरीय`,
	os_layer_waiting: (n: unknown) => `${n} निर्णय की प्रतीक्षा में`,
	os_layer_unmapped: (n: unknown) => `${n} बिना शहर-बिंदु के`,
	os_pick_at: (place: unknown) => `${place} पर`,
	os_layer_held_many: 'एकल-पोस्ट सामाजिक रिपोर्टें पूरे शहर में रोकी गईं (कभी नहीं दिखाई गईं)',

	os_attach: 'स्थिति',
	os_attach_novel: 'नई स्थिति (पहली रिपोर्ट)',
	os_corroborates: 'किसी लाइव वस्तु की पुष्टि करता है',
	os_promoted_to: 'गलियारा घटना में बढ़ाया गया',

	os_place_name: 'नाम',
	os_place_type: 'विशेषता',
	os_surface_forms: 'अन्य नाम',
	os_place_reports: 'जुड़ी रिपोर्ट',

	os_rule_note: 'प्रतिक्रिया के लिए रिपोर्ट की गई स्थिति। सजग कभी लोगों की पहचान नहीं करता।',

	os_act_search_around: 'इस स्थान के आस-पास खोजें',
	os_act_sources: 'स्रोत सूची खोलें',

	os_state_surfaced: 'उभरी हुई',
};
