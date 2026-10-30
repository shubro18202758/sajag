/**
 * The few field strings the first paint needs everywhere they appear: the top bar's "Report by voice" entry (every V3
 * page) and the two honest tags an object page shows on a board entry sent from a field report or a camera reading.
 * EN, HI and MR together (five keys, so no per-language chunk); registered additively. The rest of the field copy is
 * ./packs.field.ts, loaded with the sheet and the panels.
 */
import { registerPack } from '$lib/i18n/strings';

const en = {
	fld_entry: 'Report',
	fld_entry_aria: 'Report by voice',
	fld_tag_unverified: 'Unverified field report',
	fld_tag_camera: 'Unverified camera reading',
	fld_not_action: 'This is a claim, not an action. A named officer confirms, edits or dismisses it.',
};

const hi = {
	fld_entry: 'रिपोर्ट',
	fld_entry_aria: 'बोलकर रिपोर्ट करें',
	fld_tag_unverified: 'फ़ील्ड रिपोर्ट · जाँच नहीं हुई',
	fld_tag_camera: 'कैमरे का पाठ · जाँच नहीं हुई',
	fld_not_action: 'यह एक दावा है, कोई कार्रवाई नहीं। नामित अधिकारी इसकी पुष्टि करेंगे, बदलेंगे या ख़ारिज करेंगे।',
};

const mr = {
	fld_entry: 'अहवाल',
	fld_entry_aria: 'बोलून अहवाल द्या',
	fld_tag_unverified: 'फील्ड अहवाल · पडताळणी झालेली नाही',
	fld_tag_camera: 'कॅमेऱ्याची नोंद · पडताळणी झालेली नाही',
	fld_not_action: 'हा एक दावा आहे, कृती नाही. नामनिर्दिष्ट अधिकारी तो निश्चित करतील, बदलतील किंवा फेटाळतील.',
};

registerPack('en', en);
registerPack('hi', hi);
registerPack('mr', mr);

export const FIELD_CORE_PACKS = { en, hi, mr };
