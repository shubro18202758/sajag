/**
 * packs.corridor — the HI strings (FIX-E-PERF2): the ONE copy that runs. The
 * server render, vite dev and the node tests import it from ./packs.corridor.ts; the
 * production browser fetches it as its own chunk (lib/i18n/load.ts). Values
 * are byte-identical to the pre-split module (tests/perf2.unit.mjs pins the
 * key count and a content hash per module and language).
 */

type Pack = Record<string, string | ((...args: unknown[]) => string)>;

const s = (v: unknown) => String(v ?? '');
const n = (v: unknown) => Number(v);
export const hi: Pack = {
	cor_tab_plan: 'योजना',
	cor_tab_layers: 'परतें',
	cor_tab_movement: 'मूवमेंट',

	cor_plan_section: 'गलियारा की योजना',
	cor_plan_from: 'से',
	cor_plan_to: 'तक',
	cor_plan_class: 'वर्ग',
	cor_plan_departure: 'प्रस्थान (IST)',
	cor_plan_label: 'लेबल',
	cor_label_placeholder: 'जैसे गणेशोत्सव विसर्जन मार्ग का पूर्वाभ्यास',
	cor_plan_label_hint: 'परीक्षण / रिहर्सल लेबल मूवमेंट के शीर्षक के रूप में जाता है — इसे असली मूवमेंट कभी नहीं दिखाया जाता',
	cor_plan_officer: 'ड्यूटी अधिकारी',
	cor_plan_btn: 'गलियारा योजना',
	cor_plan_btn_busy: 'योजना बन रही है…',
	cor_plan_none: 'अभी कोई योजना नहीं — स्रोत और गंतव्य चुनकर योजना बनाएँ।',

	cor_status_approved: 'सुरक्षा अनुरूप',
	cor_status_conditional: 'सशर्त',
	cor_status_hold: 'होल्ड',
	cor_status_no_route: 'कोई मार्ग नहीं',
	cor_status_unknown: 'योजनाबद्ध',

	cor_waiver: 'मैं इस योजना के सूचीबद्ध लेन-फ़्लोर उल्लंघन स्वीकार करता/करती हूँ',
	cor_waiver_stamped: (who: unknown) => `${s(who)} ने लेन-फ़्लोर उल्लंघन स्वीकार किए`,

	cor_hold_replan: (at: unknown) => `${s(at)} के बाद फिर योजना बनाएँ`,
	cor_hold_note: 'डिसाइडर ने प्रस्थान टाला। यह योजना लॉन्च नहीं हो सकती।',

	cor_no_route_note: 'इस जोड़ी और वर्ग के लिए योजनाकार को कोई मार्ग नहीं मिला।',
	cor_no_route_next: 'अगला कदम: दूसरा स्रोत या गंतव्य, या निचला सुरक्षा वर्ग चुनकर फिर योजना बनाएँ।',

	cor_launch: 'एस्कॉर्ट शुरू करें',
	cor_launch_starting: 'शुरू हो रहा है…',
	cor_launch_criteria: (cls: unknown, dest: unknown) => `${s(cls)} मूवमेंट को नामित ड्यूटी अधिकारी के अधीन ${s(dest)} तक एस्कॉर्ट करता है`,
	cor_launch_locked_waiver: 'पहले लेन-फ़्लोर उल्लंघन स्वीकार करें — योजना सशर्त है।',
	cor_launch_locked_hold: 'डिसाइडर ने योजना रोक दी — बाद के प्रस्थान के लिए फिर योजना बनाएँ।',
	cor_launch_locked_officer: 'लॉन्च के लिए ड्यूटी अधिकारी का नाम दें।',
	cor_launch_locked_no_plan: 'पहले गलियारे की योजना बनाएँ।',
	cor_stop: 'एस्कॉर्ट रोकें',
	cor_stopping: 'रुक रहा है…',
	cor_clear: 'साफ़ करें',
	cor_clearing: 'साफ़ हो रहा है…',
	cor_clear_hint: 'क्लीयरेंस के बाद की बहाली: बंदी हटाना, सिग्नल कार्यक्रम बहाल, गलियारा इवेंट बंद',

	cor_cand_primary: 'प्राथमिक',
	cor_cand_alternate: (k: unknown) => `वैकल्पिक ${s(k)}`,
	cor_cand_adds: (roads: unknown) => `${s(roads)} जोड़ता है`,
	cor_cand_compliant: 'लेन फ़्लोर पूरा',
	cor_cand_violations: (c: unknown) => `${n(c)} लेन-फ़्लोर उल्लंघन`,
	cor_cand_ai_pick: (conf: unknown) => `Sajag AI की पसंद · विश्वास ${s(conf)}`,
	cor_cand_tactical_pick: 'टैक्टिकल प्राथमिक',
	cor_cand_rejected: (c: unknown) => `अस्वीकृत मार्ग (${n(c)})`,
	cor_cand_adds_none: 'कोई नया रास्ता नहीं जोड़ता',
	cor_cand_roads: (c: unknown) => `${n(c)} सड़क${n(c) === 1 ? '' : 'ें'}`,

	cor_proposal_link: (title: unknown) => `एस्कॉर्ट प्रस्ताव प्रतीक्षित: ${s(title)}`,
	cor_proposal_open: 'मूवमेंट टैब में निर्णय लें',

	cor_hud_escort_live: 'एस्कॉर्ट चल रहा है',
	cor_hud_planned: 'एस्कॉर्ट योजनाबद्ध',
	cor_hud_completed: 'एस्कॉर्ट पूर्ण',
	cor_hud_stopped: 'एस्कॉर्ट रुका',
	cor_hud_failed: 'एस्कॉर्ट विफल',
	cor_hud_speed: 'गति',
	cor_hud_speed_corridor: 'गलियारा औसत',
	cor_hud_progress: 'प्रगति',
	cor_hud_eta: 'ETA',
	cor_hud_eta_planned: 'योजनानुसार',
	cor_hud_hold: 'होल्ड',
	cor_hud_hold_none: 'कोई नहीं',
	cor_hud_hold_yes: 'रोका गया',
	cor_hud_next_junction: (name: unknown, t: unknown) => `अगला जंक्शन ${s(name)} · ${s(t)} में`,
	cor_hud_awaiting_gps: 'GPS की प्रतीक्षा',
	cor_hud_destination: 'गंतव्य',
	cor_hud_min: (m: unknown) => `${n(m)} मिनट`,
	cor_hud_sec: (v: unknown) => `${n(v)} सेकंड`,
	cor_hud_legacy_brain: 'यह ब्रेन एस्कॉर्ट नियंत्रण से पहले का है — उसने अपना लूप तुरंत चलाकर समाप्त किया।',
	cor_hud_officer_note: 'ड्यूटी अधिकारी का नाम ही एस्कॉर्ट तय करता है; AI कभी कुछ भी अपने आप लागू नहीं करता।',
	cor_hud_nofigures: 'इस कंसोल पर कोई लाइव आंकड़ा नहीं — मूवमेंट टैब खोलें',

	cor_events_none: 'कोई लाइव गलियारा इवेंट नहीं',
	cor_events_focus: 'नक्शे पर दिखाएँ',
	cor_events_focus_locked: 'लॉक',
	cor_events_focus_locating: 'खोज रहे हैं…',
	cor_events_no_spine: 'कैनवास पर कोई स्पाइन नहीं',
	cor_events_no_canvas: 'कैनवास उपलब्ध नहीं',
	cor_events_test_tip: (label: unknown) => `लेबल वाला परीक्षण / रिहर्सल मूवमेंट — असली मूवमेंट नहीं: ${s(label)}`,
	cor_events_promoted: 'खुले स्रोत की रिपोर्ट से बढ़ाया गया',
	cor_events_test: 'परीक्षण',

	cor_tab_failed: 'इस पैनल को लोड नहीं किया जा सका।'
};
