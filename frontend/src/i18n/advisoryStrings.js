/**
 * Citizen Advisory Layer — trilingual string packs (EN / HI / MR).
 *
 * Public-facing copy only. Road names stay transliterated (as they appear on
 * city signage) across all languages. Add languages by appending a pack and
 * registering its code in SUPPORTED.
 */

export const SUPPORTED = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिंदी' },
  { code: 'mr', label: 'मराठी' },
];

const PACKS = {
  en: {
    brand: 'Corridor Alerts · Mumbai',
    tagline: 'Know before the barricade goes up.',
    updated: 'Updated live from the traffic control room',
    statusActive: 'Protected movement in progress',
    statusActiveSub: 'Rolling holds of ~2–3 minutes per stretch — not a full freeze.',
    statusClear: 'No active corridor restrictions',
    statusClearSub: 'Normal traffic across all city corridors.',
    statusDone: 'Movement completed — corridor released',
    statusDoneSub: 'Traffic returning to normal flow.',
    startDemo: 'Play a demo movement',
    freezeTitle: 'Where holds are expected',
    freezeZone: 'Stretch',
    freezeWindow: 'Hold window',
    freezeMinutes: (m) => `~${m} min`,
    alternate: 'Use instead',
    holdNow: 'Holding now',
    passed: 'Cleared',
    why: 'Why so short?',
    whyBody:
      'Closures are timed to the convoy’s live position (60–180 s ahead) using traffic forecasting — the corridor freezes only while the movement actually passes.',
    subscribeTitle: 'Get alerts on your phone',
    subscribeSub: 'SMS / WhatsApp, free, in your language.',
    phoneLabel: 'Mobile number',
    phonePlaceholder: '10-digit mobile',
    languageLabel: 'Alert language',
    subscribeBtn: 'Subscribe',
    demoBadge: 'Demo preview — no real SMS/WhatsApp is sent',
    previewTitle: 'You would receive:',
    subscribed: 'Subscribed (demo)',
    emergencyTitle: 'Driving an ambulance or fire vehicle?',
    emergencyBody:
      'Request a green-corridor window through the active movement — the control room answers in seconds.',
    emergencyCta: 'Request green corridor',
    backToOps: 'Operator console',
    footerNote:
      'Illustrative public advisory built on the VVIP Corridor Orchestration prototype. Alternate routes are indicative.',

    // ── Green-corridor driver flow (108) ──────────────────────────
    driverTitle: 'Green Corridor — 108 driver',
    driverSub: 'One tap. The control room answers in seconds.',
    driverBack: 'Citizen alerts',
    noMovement: 'No active corridor',
    noMovementSub: 'No protected movement right now — drive normally. Start the demo movement from the citizen page to try this flow.',
    atStretch: 'You are at',
    urgency: 'Patient urgency',
    urgCardiac: 'Cardiac',
    urgTrauma: 'Trauma',
    urgStroke: 'Stroke',
    urgOther: 'Other emergency',
    requestBtn: 'Request corridor window',
    evaluating: 'Evaluating corridor gap…',
    proposalTitle: 'Window proposed by the platform',
    convoyReachesIn: 'Convoy reaches your stretch in',
    crossBefore: 'Cross before',
    officerLabel: 'Duty officer (demo)',
    approveBtn: 'Approve · open window',
    deferBtn: 'Defer',
    windowOpen: 'WINDOW OPEN — CROSS NOW',
    windowClosesIn: 'Window closes in',
    minutesReturned: 'minutes returned to the golden hour',
    holdPosition: 'Hold position — next window at',
    baselineNote: 'Without a request channel: documented ambulance holds behind convoy corridors run 5–20 minutes.',
    openDriverView: 'Open the 108 driver view',
    demoNote: 'Demo flow driven by the scripted simulation — no real dispatch, no real patient data.',
  },

  hi: {
    brand: 'कॉरिडोर अलर्ट · कोलकाता',
    tagline: 'बैरिकेड लगने से पहले ही जानें।',
    updated: 'ट्रैफ़िक कंट्रोल रूम से सीधे अपडेट',
    statusActive: 'सुरक्षित वाहन काफ़िला चल रहा है',
    statusActiveSub: 'हर हिस्से पर ~2–3 मिनट के छोटे रोक — पूरी सड़क बंद नहीं।',
    statusClear: 'इस समय कोई सड़क प्रतिबंध नहीं',
    statusClearSub: 'शहर के सभी कॉरिडोर पर सामान्य यातायात।',
    statusDone: 'काफ़िला पार — कॉरिडोर खुल गया',
    statusDoneSub: 'यातायात सामान्य हो रहा है।',
    startDemo: 'डेमो काफ़िला चलाएँ',
    freezeTitle: 'कहाँ रोक संभावित है',
    freezeZone: 'सड़क हिस्सा',
    freezeWindow: 'रोक का समय',
    freezeMinutes: (m) => `~${m} मिनट`,
    alternate: 'इसके बदले चलें',
    holdNow: 'अभी रुका हुआ',
    passed: 'खुल गया',
    why: 'इतना छोटा रोक क्यों?',
    whyBody:
      'रोक काफ़िले की लाइव स्थिति (60–180 सेकंड पहले) और ट्रैफ़िक पूर्वानुमान से तय होती है — सड़क सिर्फ़ तब बंद रहती है जब काफ़िला सच में पास हो।',
    subscribeTitle: 'अपने फ़ोन पर अलर्ट पाएँ',
    subscribeSub: 'SMS / WhatsApp, निःशुल्क, आपकी भाषा में।',
    phoneLabel: 'मोबाइल नंबर',
    phonePlaceholder: '10 अंकों का नंबर',
    languageLabel: 'अलर्ट की भाषा',
    subscribeBtn: 'सब्सक्राइब करें',
    demoBadge: 'डेमो पूर्वावलोकन — कोई असली SMS/WhatsApp नहीं भेजा जाता',
    previewTitle: 'आपको मिलेगा:',
    subscribed: 'सब्सक्राइब हुआ (डेमो)',
    emergencyTitle: 'एम्बुलेंस या फ़ायर वाहन चला रहे हैं?',
    emergencyBody:
      'चालू काफ़िले से ग्रीन-कॉरिडोर समय माँगें — कंट्रोल रूम सेकंडों में जवाब देता है।',
    emergencyCta: 'ग्रीन कॉरिडोर का अनुरोध',
    backToOps: 'ऑपरेटर कंसोल',
    footerNote:
      'VVIP कॉरिडोर प्रोटोटाइप पर बना नमूना सूचना पटल। वैकल्पिक मार्ग सांकेतिक हैं।',

    // ── Green-corridor driver flow (108) ──────────────────────────
    driverTitle: 'ग्रीन कॉरिडोर — 108 ड्राइवर',
    driverSub: 'एक टैप। कंट्रोल रूम सेकंडों में जवाब देता है।',
    driverBack: 'नागरिक अलर्ट',
    noMovement: 'कोई कॉरिडोर सक्रिय नहीं',
    noMovementSub: 'अभी कोई सुरक्षित वाहन नहीं — सामान्य चलें। यह फ़्लो आज़माने के लिए नागरिक पेज से डेमो काफ़िला चलाएँ।',
    atStretch: 'आप यहाँ हैं',
    urgency: 'मरीज़ की तात्कालिकता',
    urgCardiac: 'हृदय',
    urgTrauma: 'दुर्घटना',
    urgStroke: 'स्ट्रोक',
    urgOther: 'अन्य आपात',
    requestBtn: 'कॉरिडोर समय का अनुरोध',
    evaluating: 'कॉरिडोर गैप आँका जा रहा है…',
    proposalTitle: 'प्लेटफ़ॉर्म का प्रस्तावित समय',
    convoyReachesIn: 'काफ़िला आपके हिस्से तक पहुँचेगा',
    crossBefore: 'इससे पहले पार करें',
    officerLabel: 'ड्यूटी अधिकारी (डेमो)',
    approveBtn: 'मंज़ूर · विंडो खोलें',
    deferBtn: 'टालें',
    windowOpen: 'विंडो खुली — अभी पार करें',
    windowClosesIn: 'विंडो बंद होगी',
    minutesReturned: 'मिनट गोल्डन आवर को लौटाए गए',
    holdPosition: 'रुकें — अगली विंडो',
    baselineNote: 'अनुरोध का कोई रास्ता न हो तो: दर्ज आँकड़ों में एम्बुलेंस 5–20 मिनट रुकती है।',
    openDriverView: '108 ड्राइवर व्यू खोलें',
    demoNote: 'स्क्रिप्टेड सिमुलेशन पर चलने वाला डेमो — कोई असली डिस्पैच नहीं।',
  },

  mr: {
    brand: 'कॉरिडॉर सूचना · मुंबई',
    tagline: 'बॅरिकेड लागण्याआधीच जाणून घ्या.',
    updated: 'वाहतूक नियंत्रण कक्षाकडून थेट अद्ययावत',
    statusActive: 'संरक्षित ताफा मार्गावर आहे',
    statusActiveSub: 'प्रत्येक टप्प्यावर ~2–3 मिनिटांचे टप्प्याटप्प्याने थांबे — संपूर्ण रस्ता बंद नाही.',
    statusClear: 'सध्या कोणतेही कॉरिडॉर निर्बंध नाहीत',
    statusClearSub: 'शहरातील सर्व कॉरिडॉरवर वाहतूक सुरळीत.',
    statusDone: 'ताफा पुढे गेला — कॉरिडॉर मोकळा',
    statusDoneSub: 'वाहतूक पूर्ववत होत आहे.',
    startDemo: 'एक डेमो ताफा चालवा',
    freezeTitle: 'कुठे थांबे अपेक्षित आहेत',
    freezeZone: 'रस्त्याचा टप्पा',
    freezeWindow: 'थांब्याची वेळ',
    freezeMinutes: (m) => `~${m} मिनिटे`,
    alternate: 'याऐवजी हा मार्ग घ्या',
    holdNow: 'आता थांबा',
    passed: 'मोकळा',
    why: 'इतका कमी वेळ का?',
    whyBody:
      'थांब्याची वेळ ताफ्याच्या थेट स्थानावरून (60–180 सेकंद आधी) आणि वाहतूक अंदाजावरून ठरते — ताफा प्रत्यक्ष जात असतानाच रस्ता थांबवला जातो.',
    subscribeTitle: 'तुमच्या फोनवर सूचना मिळवा',
    subscribeSub: 'SMS / WhatsApp, मोफत, तुमच्या भाषेत.',
    phoneLabel: 'मोबाइल नंबर',
    phonePlaceholder: '10 अंकी मोबाइल नंबर',
    languageLabel: 'सूचनेची भाषा',
    subscribeBtn: 'सबस्क्राइब करा',
    demoBadge: 'डेमो पूर्वावलोकन — कोणताही खरा SMS/WhatsApp पाठवला जात नाही',
    previewTitle: 'तुम्हाला मिळेल:',
    subscribed: 'सबस्क्राइब झाले (डेमो)',
    emergencyTitle: 'रुग्णवाहिका किंवा अग्निशमन वाहन चालवत आहात?',
    emergencyBody:
      'चालू ताफ्यातून ग्रीन कॉरिडॉरची वेळ मागा — नियंत्रण कक्ष काही सेकंदांत उत्तर देतो.',
    emergencyCta: 'ग्रीन कॉरिडॉरची विनंती',
    backToOps: 'ऑपरेटर कन्सोल',
    footerNote:
      'कॉरिडॉर व्यवस्थापनाच्या प्रोटोटाइपवर आधारित नमुना सार्वजनिक सूचना. पर्यायी मार्ग केवळ सूचक आहेत.',

    // ── Green-corridor driver flow (108) ──────────────────────────
    driverTitle: 'ग्रीन कॉरिडॉर — रुग्णवाहिका (108) चालक',
    driverSub: 'एक टॅप. नियंत्रण कक्ष काही सेकंदांत उत्तर देतो.',
    driverBack: 'नागरिक सूचना',
    noMovement: 'कोणताही कॉरिडॉर सक्रिय नाही',
    noMovementSub: 'सध्या कोणताही संरक्षित ताफा नाही — नेहमीप्रमाणे गाडी चालवा. ही प्रक्रिया पाहण्यासाठी नागरिक पानावरून डेमो ताफा सुरू करा.',
    atStretch: 'तुम्ही येथे आहात',
    urgency: 'रुग्णाची तातडी',
    urgCardiac: 'हृदयविकार',
    urgTrauma: 'अपघाती दुखापत',
    urgStroke: 'स्ट्रोक',
    urgOther: 'इतर आणीबाणी',
    requestBtn: 'कॉरिडॉरची वेळ मागा',
    evaluating: 'कॉरिडॉरमधील फट तपासली जात आहे…',
    proposalTitle: 'प्लॅटफॉर्मने सुचवलेली वेळ',
    convoyReachesIn: 'ताफा तुमच्या टप्प्यावर पोहोचेल',
    crossBefore: 'याआधी पार करा',
    officerLabel: 'ड्युटी अधिकारी (डेमो)',
    approveBtn: 'मंजूर करा · वेळ खुली करा',
    deferBtn: 'नंतर',
    windowOpen: 'वेळ खुली — आत्ताच पार करा',
    windowClosesIn: 'वेळ संपेल',
    minutesReturned: 'मिनिटे गोल्डन अवरला परत मिळाली',
    holdPosition: 'थांबा — पुढची वेळ',
    baselineNote: 'विनंतीचा मार्ग नसल्यास: नोंदीनुसार ताफ्याच्या कॉरिडॉरमागे रुग्णवाहिका 5–20 मिनिटे अडकते.',
    openDriverView: 'रुग्णवाहिका (108) चालकाचे दृश्य उघडा',
    demoNote: 'स्क्रिप्ट केलेल्या सिम्युलेशनवर चालणारा डेमो — कोणतीही खरी डिस्पॅच किंवा रुग्णाची माहिती नाही.',
  },
};

export function t(lang, key, ...args) {
  const pack = PACKS[lang] || PACKS.en;
  const val = pack[key];
  if (typeof val === 'function') return val(...args);
  return val != null ? val : key;
}

/**
 * Indic-script digits for the demo alert preview (authentic touch — Indian
 * SMS gateways deliver in the subscriber's script).
 */
const DIGITS = {
  en: '0123456789',
  hi: '०१२३४५६७८९',
  mr: '०१२३४५६७८९',
};

export function localizeNumber(n, lang) {
  const table = DIGITS[lang] || DIGITS.en;
  return String(n).replace(/[0-9]/g, (d) => table[+d]);
}
