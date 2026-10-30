"""Build ``pii_eval_set.synthetic.json``: a SYNTHETIC, hand-labelled set of short Mumbai news-style sentences for
measuring person-name redaction (and the place names it must never touch).

Every sentence below is invented for this evaluation. The person names are fictional combinations of common
Marathi, Hindi and other Indian given names and surnames; they refer to no real individual. The places are real
public Mumbai places (many named after historical figures), which is the point: a redactor must leave them alone.
Phone numbers are invented and e-mail addresses use the reserved ``example.com`` / ``example.in`` domains.

Markup: ``[[TAG|text]]`` marks a labelled span. Tags:

* ``P``  a private person's name (gold PII)            * ``PH`` a phone number (gold PII)
* ``EM`` an e-mail address (gold PII)                  * ``A``  an age (informational: the rules redact ages)
* ``L``  a place name that must NOT be redacted        * ``O``  a public-office title, no name (must NOT be redacted)
* ``N``  a public emergency number (must NOT be redacted)
* ``V``  a vehicle plate (informational: plates are masked by a separate rule, not by name redaction)

Languages: ``en`` English, ``mr`` Marathi (Marathi script), ``hi`` Hindi (Devanagari), ``mr-Latn`` romanised
Marathi and Marathi-English code-mixing.

Run: ``python3 build_eval_set.py`` (stdlib only) rewrites the JSON next to this file.
"""

# ruff: noqa: E501  (the sentences are data)
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().with_name("pii_eval_set.synthetic.json")

TAGS = {
    "P": "person",
    "PH": "phone",
    "EM": "email",
    "A": "age",
    "L": "place",
    "O": "office",
    "N": "public_number",
    "V": "plate",
}

# fmt: off
SENTENCES: dict[str, list[str]] = {
    "en": [
        "Waterlogging on [[L|Dr Babasaheb Ambedkar Road]] after two hours of rain; [[O|the BMC Commissioner]] said pumps were running.",
        "A bus broke down on [[L|Senapati Bapat Marg]] near [[L|Shivaji Park]]; driver [[P|Sunil Jadhav]] was unhurt.",
        "Local resident Mrs [[P|Sunita Patil]], [[A|54]], said the drains on [[L|Lady Jamshedji Road]] were choked again.",
        "Traffic was diverted from [[L|Netaji Subhash Chandra Bose Road]] to [[L|Jagannath Shankarshet Road]] for the procession.",
        "[[P|Amit Pawar]], a vegetable vendor, was injured when a tree fell on [[L|Annie Besant Road]].",
        "Morning walkers at [[L|Jijamata Udyan]] reported a fallen branch blocking the eastern gate.",
        "A cultural programme at [[L|Ravindra Natya Mandir]] will end at 9 pm; expect slow traffic on [[L|Veer Nariman Road]].",
        "Heavy vehicles are barred from [[L|Gokhale Bridge]] between 8 am and 11 am on Sunday.",
        "Flights at [[L|Chhatrapati Shivaji Maharaj International Airport]] were delayed by up to 40 minutes after the storm.",
        "Dr [[P|Aniket Mhatre]] of [[L|KEM Hospital]] said the injured pedestrian was stable.",
        "A water main burst on [[L|Tulsi Pipe Road]]; BMC crews were on site by noon.",
        "Signals on [[L|Pherozeshah Mehta Road]] failed for an hour during the downpour.",
        "[[L|Mahatma Gandhi Road]] will stay closed for the marathon rehearsal, [[O|the Deputy Commissioner of Police (Traffic)]] said.",
        "Commuters on [[L|Eastern Express Highway]] faced a long queue near the Mulund toll plaza.",
        "A transformer fire was reported at [[L|Dadasaheb Phalke Chitranagari]] late on Tuesday; no one was hurt.",
        "Shopkeeper [[P|Prashant Sawant]] said water entered his shop near [[L|Five Gardens]].",
        "[[L|Jamshedji Tata Road]] is one-way towards [[L|Churchgate]] until Friday.",
        "A truck carrying bricks overturned on [[L|Dr E Moses Road]]; the cleaner [[P|Rakesh Yadav]], [[A|31]], was taken to hospital.",
        "Office traffic around [[L|Hutatma Chowk]] eased by 7 pm.",
        "Biker [[P|Siddharth More]] dies after his scooter skidded on [[L|Pandurang Budhkar Marg]].",
        "Contact the ward office at [[PH|98200 41526]] or write to [[EM|gnward.help@example.in]] to report a blocked drain.",
        "A car, [[V|MH 01 AB 1234]], hit the divider on [[L|Senapati Bapat Marg]]; call [[N|112]] for emergencies.",
        "Ambulance ([[N|108]]) crews were stuck for 20 minutes on [[L|Dr Babasaheb Ambedkar Road]].",
        "[[O|The Senior Inspector of Shivaji Park police station]] said the junction near [[L|Siddhivinayak]] metro would reopen soon.",
        "[[P|Pooja Shinde]]'s family said she had left for [[L|Churchgate]] at 6 pm.",
        "[[P|Mahesh Gaikwad]] and [[P|Snehal Kadam]] were rescued from a waterlogged lane off [[L|Lady Jamshedji Road]].",
        "[[O|A BMC storm-water drains engineer]] said the [[L|Haji Ali]] pumping station was running at full capacity.",
        "Police seized a motorcycle, [[V|MH 02 K 5678]], abandoned near [[L|Acharya Atre Chowk]] metro station.",
        "Passengers alighting at [[L|Lokmanya Tilak Terminus]] were held back during the signal failure.",
        "The pandal near [[L|Nana Chowk]] drew large crowds on the fifth day of Ganeshotsav.",
        "Retired teacher [[P|Vijay Kulkarni]], [[A|67]], told reporters the footpath on [[L|Senapati Bapat Marg]] was broken.",
        "Water stood knee-deep at [[L|Hindmata]] and on [[L|Dr Babasaheb Ambedkar Road]] at high tide.",
        "Mr [[P|Kiran Bhosale]], who runs a tea stall on [[L|Ranade Road]], said sales had halved.",
        "Fire tenders reached [[L|Kalbadevi Road]] within 15 minutes, [[O|the fire brigade]] said.",
        "Volunteers led by [[P|Manasi Joshi]] distributed water at [[L|Oval Maidan]].",
        "[[P|Tushar Salunkhe]] ([[A|29]]) was arrested for rash driving on [[L|Western Express Highway]].",
        "For lost property call [[PH|+91 90040 23418]]; the counter at [[L|Dadar station]] is open all night.",
        "Students of a school on [[L|Gokhale Road]] were sent home early because of the rain.",
        "[[O|The Commissioner of Police]] reviewed crowd arrangements at [[L|Wankhede Stadium]] ahead of the match.",
        "Smt [[P|Shubhangi Ghadge]] said the queue at the [[L|CSMT]] taxi stand stretched to the subway.",
    ],
    "mr": [
        "[[L|डॉ. आंबेडकर मार्गावर]] पाणी साचले, स्थानिक रहिवासी [[P|सुनील जाधव]] यांनी सांगितले.",
        "[[L|सेनापती बापट मार्गावर]] बस बंद पडली, चालक [[P|अमित पवार]] जखमी.",
        "[[L|ॲनी बेझंट मार्गावर]] वाहतूक कोंडी, [[O|वाहतूक विभागाचे पोलीस उपायुक्त]] यांनी सांगितले की दुपारपर्यंत वाहतूक सुरळीत होईल.",
        "[[L|नेताजी सुभाषचंद्र बोस मार्गावर]] एक झाड कोसळले, कोणीही जखमी झाले नाही.",
        "[[L|महात्मा गांधी मार्गावरून]] मिरवणूक जाणार आहे, त्यामुळे वाहतूक [[L|जगन्नाथ शंकरशेट मार्गावरून]] वळवली आहे.",
        "[[L|डॉ. आंबेडकर मार्गावर]] गुडघाभर पाणी, दुकानदार [[P|प्रशांत सावंत]] म्हणाले दुकानात पाणी शिरले.",
        "[[L|जिजामाता उद्यानात]] सकाळी फिरायला आलेल्यांना तुटलेली फांदी दिसली.",
        "[[L|रवींद्र नाट्य मंदिरात]] कार्यक्रम रात्री नऊ वाजता संपेल.",
        "[[L|गोखले पुलावर]] रविवारी सकाळी अवजड वाहनांना बंदी असेल.",
        "वादळानंतर [[L|छत्रपती शिवाजी महाराज आंतरराष्ट्रीय विमानतळावरून]] विमाने उशिरा सुटली.",
        "[[L|तुळशी पाईप रोडवर]] जलवाहिनी फुटली, महापालिकेचे कर्मचारी काम करत आहेत.",
        "[[L|फिरोजशहा मेहता मार्गावर]] सिग्नल एक तास बंद होते.",
        "सरावासाठी [[L|महात्मा गांधी मार्ग]] बंद राहील, असे [[O|पोलीस आयुक्तांनी]] सांगितले.",
        "[[L|पूर्व द्रुतगती महामार्गावर]] टोल नाक्याजवळ लांब रांग.",
        "[[L|दादासाहेब फाळके चित्रनगरीत]] मंगळवारी रात्री ट्रान्सफॉर्मरला आग लागली, कोणीही जखमी झाले नाही.",
        "[[L|शिवाजी पार्कजवळ]] दुकानात पाणी शिरल्याचे व्यापारी [[P|तुषार साळुंखे]] यांनी सांगितले.",
        "शुक्रवारपर्यंत [[L|जमशेदजी टाटा मार्ग]] एकमार्गी राहील.",
        "[[L|डॉ. ई. मोझेस मार्गावर]] विटांनी भरलेला ट्रक उलटला, क्लीनर [[P|राकेश यादव]] रुग्णालयात.",
        "संध्याकाळी सातनंतर [[L|हुतात्मा चौकात]] वाहतूक कोंडी कमी झाली.",
        "[[A|४५ वर्षांच्या]] [[P|पूजा शिंदे]] [[L|हिंदमाता चौकात]] अपघातात जखमी झाल्या.",
        "श्रीमती [[P|रीता सावंत]] यांनी सांगितले की [[L|लेडी जमशेदजी मार्गावरील]] गटार पुन्हा तुंबले.",
        "डॉ. [[P|अनिकेत म्हात्रे]] म्हणाले की जखमी पादचाऱ्याची प्रकृती स्थिर आहे.",
        "[[P|महेश गायकवाड]] आणि [[P|स्नेहल कदमची]] पाणी साचलेल्या गल्लीतून सुटका करण्यात आली.",
        "गटार तुंबल्यास [[PH|९८२०० ४१५२६]] या क्रमांकावर फोन करा.",
        "आपत्कालीन परिस्थितीत [[N|११२]] क्रमांकावर फोन करा, रुग्णवाहिकेसाठी [[N|१०८]].",
        "[[L|चर्चगेटला]] निघाल्यापासून [[P|पायल देसाई]] यांचा पत्ता लागत नसल्याचे कुटुंबीयांनी सांगितले.",
        "निवृत्त शिक्षक [[P|विजय कुलकर्णी]] यांनी सांगितले की [[L|सेनापती बापट मार्गावरील]] पदपथ तुटलेला आहे.",
        "[[L|परळमध्ये]] आणि [[L|डॉ. आंबेडकर मार्गावर]] भरतीच्या वेळी गुडघाभर पाणी.",
        "[[L|आचार्य अत्रे चौक]] मेट्रो स्थानकाजवळ एक बेवारस मोटारसायकल सापडली.",
        "[[L|लोकमान्य टिळक टर्मिनसवर]] सिग्नल बिघाडामुळे प्रवासी अडकून पडले.",
        "स्वयंसेविका [[P|श्रेया मोरे]] यांनी [[L|ओव्हल मैदानावर]] पाणी वाटप केले.",
        "[[L|वानखेडे स्टेडियमसमोर]] सामन्यानंतर गर्दी, असे [[O|मुंबई पोलिसांच्या एका अधिकाऱ्याने]] सांगितले.",
        "बेदरकारपणे गाडी चालवल्याप्रकरणी [[P|सौरभ नाईकला]] अटक करण्यात आली.",
        "[[L|दादर स्थानकात]] हरवलेल्या वस्तूंचा कक्ष रात्रभर उघडा असतो.",
        "[[O|महापालिका आयुक्तांनी]] सांगितले की [[L|हाजी अली]] येथील पंप पूर्ण क्षमतेने सुरू आहेत.",
        "[[L|रानडे रोडवर]] चहाची टपरी चालवणारे [[P|किरण भोसले]] म्हणाले की विक्री निम्म्यावर आली आहे.",
        "[[L|पश्चिम द्रुतगती महामार्गावर]] झालेल्या अपघातात [[P|विश्वजीत घाडगे]] ([[A|३८]]) जखमी.",
        "[[L|गोखले रोडवरील]] एका शाळेने पावसामुळे लवकर सुट्टी दिली.",
    ],
    "hi": [
        "[[L|डॉ. आंबेडकर रोड]] पर जलभराव, स्थानीय निवासी [[P|सुनीता शर्मा]] ने बताया कि नाली जाम है।",
        "[[L|सेनापति बापट मार्ग]] पर बस खराब, ड्राइवर [[P|राकेश यादव]] घायल।",
        "[[L|एनी बेसेंट रोड]] पर जाम, [[O|यातायात उपायुक्त]] ने कहा दोपहर तक सामान्य होगा।",
        "[[L|नेताजी सुभाष चंद्र बोस रोड]] पर पेड़ गिरा, कोई घायल नहीं।",
        "[[L|महात्मा गांधी रोड]] पर जुलूस के कारण यातायात [[L|जगन्नाथ शंकरशेट रोड]] की ओर मोड़ा गया।",
        "[[L|गोखले पुल]] पर रविवार सुबह भारी वाहनों पर रोक रहेगी।",
        "तूफ़ान के बाद [[L|छत्रपति शिवाजी महाराज अंतरराष्ट्रीय हवाई अड्डे]] पर उड़ानें देर से चलीं।",
        "दुकानदार [[P|मनोज गुप्ता]] ने कहा [[L|हुतात्मा चौक]] के पास दुकान में पानी घुस गया।",
        "[[A|45 वर्षीय]] [[P|पूजा सिंह]] [[L|बांद्रा–वर्ली सी लिंक]] पर हादसे में घायल हुईं।",
        "[[P|इमरान अंसारी]] और [[P|सलमा खातून]] को [[L|जिजामाता उद्यान]] के पास जलमग्न गली से निकाला गया।",
        "नाली जाम होने पर [[PH|98200 41526]] पर फ़ोन करें।",
        "आपात स्थिति में [[N|112]] पर कॉल करें, एम्बुलेंस के लिए [[N|108]]।",
        "[[O|पुलिस आयुक्त]] ने [[L|वानखेड़े स्टेडियम]] में भीड़ प्रबंधन की समीक्षा की।",
        "डॉ. [[P|अनिल वर्मा]] ने कहा घायल पैदल यात्री की हालत स्थिर है।",
        "[[L|पूर्वी एक्सप्रेस हाईवे]] पर टोल प्लाज़ा के पास लंबी कतार।",
        "[[L|दादर]] स्टेशन पर टैक्सी की कतार में खड़े [[P|विकास तिवारी]] ने बताया कि एक घंटा लगा।",
    ],
    "mr-Latn": [
        "[[L|Ambedkar Road]] la paani bharla, [[P|Sunil]] dada mhanale 2 foot paani aahe.",
        "[[L|Senapati Bapat Marg]] var bus band padli, driver [[P|Bapu Jadhav]] jakhmi.",
        "[[L|Annie Besant Road]] la traffic jam, amchi vahini [[P|Sunita Patil]] 1 taas adkun aahe.",
        "[[L|Hindmata]] junction la accident, [[P|Ananya Desai]] chya scooty la eka taxi ne dhakka dila.",
        "Aaj [[L|Jijamata Udyan]] cha gate band, morning walk la jaata yenar nahi.",
        "[[L|Chhatrapati Shivaji Maharaj International Airport]] var flight delay, [[P|Rina Sawant]] mhanalya 2 taas wait kartoy.",
        "[[L|Gokhale Bridge]] var heavy jam, office la jayla ushir honar.",
        "[[L|Mahatma Gandhi Road]] varun miravnuk jaanar, mhanun [[L|JSS Road]] varun traffic valavla aahe.",
        "Ganpati chi gardi [[L|Shivaji Park]] samor, [[P|Tejas Shinde]] bhetla.",
        "[[L|Pherozeshah Mehta Road]] var signal band, traffic police haatane control kartayt.",
        "[[L|Eastern Express Highway]] var long queue, [[P|Jaydeep Kale]] mhanala toll naka var 30 min.",
        "Contact [[P|Sudhir]] dada for flood relief: [[PH|9820015577]].",
        "Kay paristhiti aahe [[L|Netaji Subhash Chandra Bose Road]] var? Marathon rehearsal mule band aahe ka?",
        "[[L|Dadasaheb Phalke Chitranagari]] madhe transformer la aag lagli, koni jakhmi nahi.",
        "[[L|Jamshedji Tata Road]] one-way, [[L|Churchgate]] kade jaata yenar nahi.",
        "[[L|Dr E Moses Road]] var truck ulatla, cleaner [[P|Raju Shinde]] hospital madhe.",
        "[[L|Hutatma Chowk]] la sandhyakali 7 nantar traffic kami jhala.",
        "Amcha shejari [[P|Rohan Kulkarni]] [[L|Dr Babasaheb Ambedkar Road]] var adkun aahe, gudghabhar paani.",
        "Email [[EM|tushar.more84@example.com]] if you found a blue bag near [[L|Dadar]].",
        "[[V|MH 47 C 4321]] number chi car [[L|Bandra–Worli Sea Link]] var breakdown.",
        "[[L|Ravindra Natya Mandir]] madhe program aahe, [[L|Prabhadevi]] junction la slow traffic.",
        "[[P|Pritam]] bhau mhanala [[L|Kurla]] la paani nahi, [[L|Western Express Highway]] clear.",
        "[[L|Tulsi Pipe Road]] var pipe burst, BMC che lok kaam kartayt.",
        "[[L|Pandurang Budhkar Marg]] var signal fail, ek taas zhala.",
        "Tai [[P|Swapna Naik]] [[L|Girgaon Chowpatty]] varun mhanalya ki samudrache paani var yetay.",
        "[[O|BMC Commissioner]] mhanale [[L|Haji Ali]] la pump purna kshamatene chalu aahet.",
    ],
}
# fmt: on

_MARK = re.compile(r"\[\[(?P<tag>[A-Z]{1,2})\|(?P<body>[^\]]+)\]\]")


def parse(marked: str) -> tuple[str, list[dict]]:
    """Strip the markup; return the plain text and its labelled spans (character offsets into the plain text)."""
    out: list[str] = []
    spans: list[dict] = []
    pos = 0
    plain_len = 0
    for m in _MARK.finditer(marked):
        before = marked[pos : m.start()]
        out.append(before)
        plain_len += len(before)
        body = m.group("body")
        tag = m.group("tag")
        if tag not in TAGS:
            raise ValueError(f"unknown tag {tag!r} in {marked!r}")
        spans.append({"start": plain_len, "end": plain_len + len(body), "type": TAGS[tag], "text": body})
        out.append(body)
        plain_len += len(body)
        pos = m.end()
    out.append(marked[pos:])
    text = "".join(out)
    if "[[" in text or "]]" in text:
        raise ValueError(f"unbalanced markup in {marked!r}")
    for s in spans:
        assert text[s["start"] : s["end"]] == s["text"]
    return text, spans


def build() -> dict:
    items = []
    for lang, sentences in SENTENCES.items():
        for i, marked in enumerate(sentences, 1):
            text, spans = parse(marked)
            items.append({"id": f"{lang}-{i:03d}", "lang": lang, "text": text, "spans": spans})
    return {
        "schema": "sajag.pii_eval/1",
        "synthetic": True,
        "label": "SYNTHETIC",
        "note": (
            "SYNTHETIC evaluation set: every sentence is invented; person names are fictional combinations of "
            "common given names and surnames and refer to no real individual; places are real public Mumbai "
            "places; phone numbers are invented; e-mail addresses use reserved example domains. Gold PII types: "
            "person, phone, email. Must-not-redact types: place, office, public_number. Informational: age, plate."
        ),
        "gold_pii_types": ["person", "phone", "email"],
        "protected_types": ["place", "office", "public_number"],
        "informational_types": ["age", "plate"],
        "items": items,
    }


if __name__ == "__main__":
    doc = build()
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    from collections import Counter

    langs = Counter(it["lang"] for it in doc["items"])
    types = Counter(s["type"] for it in doc["items"] for s in it["spans"])
    print(f"wrote {OUT.name}: {len(doc['items'])} sentences {dict(langs)}; spans {dict(types)}")
