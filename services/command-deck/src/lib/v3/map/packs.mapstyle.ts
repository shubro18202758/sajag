/**
 * The map-style strings (V3-P4C) — the few words of MapStyleSwitch, in all three languages in one tiny file because the
 * switch also sits in the header menu of every V3 page (so these cannot wait for the /map pack, packs.map3). Registered
 * additively (registerPack; first registration wins). Every key starts with `v3ms_`. Same copy rules as the /map pack:
 * sentence case, at most one " · " per string, and the honest label — satellite imagery is a photograph taken some time
 * ago, never a live image.
 */
import { registerPack } from '$lib/i18n/strings';

export const MAPSTYLE_PACKS = {
	en: {
		v3ms_label: 'Map style',
		v3ms_satellite: 'Satellite',
		v3ms_map: 'Map',
		v3ms_tip_satellite: 'Natural-colour satellite imagery · not a live image',
		v3ms_tip_map: 'The night map, drawn from OpenStreetMap',
		v3ms_needs_key: 'Needs the Cesium ion key on this deck',
		v3ms_paused: 'Satellite imagery is paused for this session. The map shows instead.',
		v3ms_hint: 'Applies to the maps on Home, Decide and the pages of a vehicle or a place.',
	},
	hi: {
		v3ms_label: 'मानचित्र शैली',
		v3ms_satellite: 'उपग्रह',
		v3ms_map: 'मानचित्र',
		v3ms_tip_satellite: 'प्राकृतिक रंगों में उपग्रह चित्र · लाइव चित्र नहीं',
		v3ms_tip_map: 'रात का मानचित्र, OpenStreetMap से बना',
		v3ms_needs_key: 'इस डेक पर Cesium ion कुंजी आवश्यक है',
		v3ms_paused: 'इस सत्र के लिए उपग्रह चित्र रुके हैं। इसके बदले मानचित्र दिखेगा।',
		v3ms_hint: 'होम, निर्णय और वाहन या स्थान के पन्नों के मानचित्रों पर लागू।',
	},
	mr: {
		v3ms_label: 'नकाशाची शैली',
		v3ms_satellite: 'उपग्रह',
		v3ms_map: 'नकाशा',
		v3ms_tip_satellite: 'नैसर्गिक रंगांतील उपग्रह प्रतिमा · थेट प्रतिमा नाही',
		v3ms_tip_map: 'रात्रीचा नकाशा, OpenStreetMap वरून काढलेला',
		v3ms_needs_key: 'यासाठी या डेकवर Cesium ion की आवश्यक आहे',
		v3ms_paused: 'या सत्रासाठी उपग्रह प्रतिमा थांबवल्या आहेत. त्याऐवजी नकाशा दिसेल.',
		v3ms_hint: 'होम, निर्णय आणि वाहन किंवा ठिकाणाच्या पानांवरील नकाशांना लागू.',
	},
} as const;

for (const [code, pack] of Object.entries(MAPSTYLE_PACKS)) registerPack(code, pack);
