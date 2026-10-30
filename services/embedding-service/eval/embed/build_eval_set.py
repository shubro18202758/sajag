"""Build the embedding eval set (SYNTHETIC) from the repo's own material.

Three of Sajag's real retrieval jobs, each in Marathi, English, Hindi and code-mixed (romanised Marathi) text:

* ``memory``  — decision memory: a new situation (a brain state document, or an officer's free text) → the past
  decisions / incidents / scenario runs / after-action notes about the same place and kind of situation. Documents
  use the exact shapes the brain (``convoy_brain.decider._record_decision_memory``: ``TRIGGER: …`` state docs) and
  the embedding service's ``IncidentIngestor`` (incident and scenario-run bodies) write.
* ``sop``     — SOP / advisory retrieval: a question → the paragraph that answers it. Corpus: every paragraph of 25+
  words in ``docs/ai/*.md``, the deck's citizen advisory packs (``strings.citizen{,.mr,.hi}.ts``, the same key in
  three languages) and advisory/proposal texts rendered from the hydro and forecast templates.
* ``osint``   — OSINT dedup/clustering: headlines (Marathi, English, Hindi, romanised) about the same Mumbai event
  must cluster; hard negatives share a place or an event kind. Plus one English cluster taken from the OSINT
  test fixtures (``services/osint-common/tests/fixtures/dss_sg_highway.synthetic.json``, synthetic, another city).

Everything here is SYNTHETIC: invented situations and headlines written for this eval, with real Mumbai place
names (``cities/mumbai/landmarks.json`` spellings). No real person is named; no real statistic is claimed.

Run: ``python build_eval_set.py`` (stdlib only) → ``eval_set.synthetic.json`` next to this file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = HERE / "eval_set.synthetic.json"

# ─────────────────────────────────────────────────────────────────────────────
# (a) decision memory
# ─────────────────────────────────────────────────────────────────────────────


def _decision(fam: str, n: int, trigger: str, summary: str, **ctx: object) -> dict:
    """A kind=decision doc exactly as the brain's decision-memory feeder writes it."""
    lines = [f"TRIGGER: {trigger}", summary.strip()] + [f"{k}: {v}" for k, v in ctx.items()]
    return {"id": f"m:{fam}:d{n}", "family": fam, "kind": "decision",
            "title": f"decider {trigger} checkpoint", "body": "\n".join(lines)}


def _incident(fam: str, n: int, kind: str, severity: str, summary: str) -> dict:
    """A kind=incident doc as IncidentIngestor.ingest_live_incident writes it."""
    return {"id": f"m:{fam}:i{n}", "family": fam, "kind": "incident",
            "title": f"Incident {kind} ({severity})", "body": summary}


def _scenario(fam: str, n: int, sc: str, route: str, dvh: float, q: int, clo: int, segs: int, risk: float,
              transit: int) -> dict:
    """A kind=scenario_run doc as IncidentIngestor.ingest_scenario_run writes it."""
    body = (f"Simulation scenario run {sc} on route {route}. Predicted disruption {dvh} vehicle-hours; "
            f"max queue {q} m; average closure {clo} s; segments affected {segs}; complaints risk {risk}; "
            f"convoy transit {transit} s.")
    return {"id": f"m:{fam}:s{n}", "family": fam, "kind": "scenario_run",
            "title": f"Scenario run {sc}: {route}", "body": body}


def _aar(fam: str, n: int, title: str, body: str) -> dict:
    return {"id": f"m:{fam}:a{n}", "family": fam, "kind": "aar", "title": f"After-action: {title}", "body": body}


MEMORY_DOCS: list[dict] = [
    # F1 waterlogging at high tide, island city (Hindmata / Dadar TT / Dr Ambedkar Road)
    _decision("tide_hindmata", 1, "waterlogging_alert",
              "Cloudburst over the island city during a high tide; sea outfalls closed. Water rising at Hindmata "
              "and Dadar TT; Dr Ambedkar Road northbound slowing.",
              rain_mm_last_hour=62, tide_m=4.6, gates="closed", risk_class=2,
              ambulance_route="Sion Hospital via the Eastern Express Highway"),
    _incident("tide_hindmata", 2, "weather", "high",
              "Waterlogging 20-30 cm at Hindmata junction and on Dr Ambedkar Road after heavy rain at high tide; "
              "small vehicles stalled; dewatering pumps at Hindmata working against closed outfalls."),
    _aar("tide_hindmata", 3, "Hindmata waterlogging at high tide",
         "Diversion of Dr Ambedkar Road traffic to Senapati Bapat Marg held for 95 minutes until the tide fell and "
         "the outfalls reopened. Ambulances to Sion Hospital used the Eastern Express Highway; one live-wire report "
         "was passed to the power utility."),
    # F2 Ganeshotsav visarjan (Lalbaug -> Girgaon Chowpatty)
    _decision("visarjan_lalbaug", 1, "crowd_density",
              "Anant Chaturdashi night: the Lalbaugcha Raja procession and devotees spilling onto the road at "
              "Lalbaug; Bharat Mata junction gridlocked on the way to Girgaon Chowpatty.",
              crowd_level="very high", pandals="Lalbaugcha Raja, GSB Seva Mandal",
              one_way="Dr Ambedkar Road southbound only", goods_vehicle_ban="active"),
    _scenario("visarjan_lalbaug", 2, "sc-visarjan-07", "Lalbaug - Bharat Mata - Girgaon Chowpatty (visarjan night)",
              48.2, 1350, 420, 9, 0.62, 0),
    _aar("visarjan_lalbaug", 3, "Visarjan night, Lalbaug to Girgaon",
         "Metering devotees at the Lalbaug flyover approach and holding vehicles at Bharat Mata junction for "
         "6-minute waves kept the procession moving; an ambulance (108) reached KEM Hospital via a cleared lane on "
         "Dr Ambedkar Road."),
    # F3 Bandra-Worli Sea Link breakdown
    _incident("sea_link", 1, "route_blockage", "high",
              "A BEST bus broke down in the northbound lanes of the Bandra–Worli Sea Link at 18:10; queue back to "
              "the Worli end; Worli Seaface approach slow."),
    _decision("sea_link", 2, "route_blockage",
              "Stalled bus on the Sea Link northbound during the evening peak; tow truck 20 minutes away. "
              "Spill-back onto the Worli end interchange.",
              blocked_lane="northbound kerb lane", alternate="Mahim Causeway", tow_eta_min=20),
    _aar("sea_link", 3, "Sea Link breakdown",
         "Diverting Bandra-bound traffic to Mahim Causeway and opening a contraflow lane cleared the Sea Link queue "
         "in 40 minutes after the bus was towed."),
    # F4 protected movement Mantralaya -> airport
    _decision("vip_mantralaya", 1, "pre_movement",
              "Protected movement planned from Mantralaya to Mumbai Airport T2 at 16:30 via Marine Drive, the "
              "Coastal Road, the Sea Link and the Western Express Highway.",
              route_options="primary: Coastal Road-Sea Link-WEH; alternate: Dr Ambedkar Road-Sion-SCLR-WEH",
              expected_hold_min=12),
    _scenario("vip_mantralaya", 2, "sc-vip-mtr-03", "Mantralaya - Coastal Road - Sea Link - WEH - Airport T2",
              31.4, 980, 210, 14, 0.41, 1980),
    # F5 Wankhede egress
    _scenario("wankhede_egress", 1, "sc-wankhede-11", "Wankhede Stadium egress - Marine Drive - Churchgate",
              22.7, 760, 300, 7, 0.35, 0),
    _decision("wankhede_egress", 2, "egress_surge",
              "Night match ends at Wankhede Stadium; about 30,000 spectators leaving towards Churchgate, Marine "
              "Lines and CSMT; BEST buses queued on Marine Drive.",
              crowd_level="high", rail="Churchgate station crowded", exits_metered="yes"),
    # F6 cyclone tree fall
    _incident("cyclone_marinedrive", 1, "weather", "critical",
              "Cyclone gusts uprooted trees across Marine Drive and Worli Seaface; both carriageways blocked; BMC "
              "tree-cutting team called."),
    _decision("cyclone_marinedrive", 2, "cyclone_recovery",
              "Post-landfall recovery: tree falls on Marine Drive and Babulnath Road; evacuation route to JJ "
              "Hospital must be restored first.",
              blocked_segments=4, priority="JJ Hospital access", crews_available=3),
    # F7 ambulance corridor Worli Naka -> KEM
    _decision("amb_kem", 1, "ambulance_request",
              "Ambulance (108) requests a green corridor from Worli Naka to KEM Hospital through evening traffic "
              "on Dr E Moses Road.",
              unit_eta_min=14, window_sec=120, junctions=6),
    _aar("amb_kem", 2, "Green corridor Worli Naka to KEM",
         "The window opened 90 seconds ahead of the ambulance at each of six junctions on Dr E Moses Road; the unit "
         "reached KEM Hospital in 11 minutes."),
    # F8 signal failure Sion Circle
    _incident("signal_sion", 1, "signal_failure", "medium",
              "Signal controller at Sion Circle dark after a power cut; Eastern Express Highway northbound queue "
              "600 m; manual control by traffic constables."),
    _decision("signal_sion", 2, "signal_failure",
              "Sion Circle junction signals out; Sion-Panvel highway and Eastern Express Highway flows conflicting. "
              "Propose manual control and a fixed-time plan once power returns.",
              queue_m=600, constables_on_site=2),
    # F9 Mount Mary fair at Bandra
    _scenario("mount_mary", 1, "sc-mtmary-02", "Bandra station - Hill Road - Mount Mary (fair week)",
              18.9, 640, 180, 6, 0.28, 0),
    _decision("mount_mary", 2, "mass_gathering",
              "Pilgrims arriving for the Mount Mary fair in Bandra; BEST special buses loading at Bandra station; "
              "pedestrian surge on Hill Road.",
              crowd_level="high", buses_waiting=40),
    # F10 Mumbai Marathon
    _scenario("marathon", 1, "sc-marathon-01", "CSMT - Marine Drive - Sea Link (Mumbai Marathon)",
              26.1, 820, 3600, 11, 0.47, 0),
    _decision("marathon", 2, "race",
              "Mumbai Marathon morning: Marine Drive, Haji Ali and the Sea Link closed until the last runner passes; "
              "Sunday church traffic near Churchgate to be held.",
              closure_until="10:30", detour="Dr Ambedkar Road"),
    # F11 Dahi Handi crowd at Worli (a festival gathering; no political events in this set)
    _incident("dahihandi_worli", 1, "other", "medium",
              "Dahi Handi pyramids at Jambori Maidan, Worli draw a large crowd; Pandurang Budhkar Marg and "
              "Ganpatrao Kadam Marg closed for 2 hours; BEST buses diverted."),
    _decision("dahihandi_worli", 2, "mass_gathering",
              "Dahi Handi crowd assembling at Worli; Pandurang Budhkar Marg and Ganpatrao Kadam Marg blocked; BEST "
              "buses held.",
              expected_duration_min=120, detour="Dr Annie Besant Road"),
    # F12 Dadar station surge when locals stop
    _incident("dadar_surge", 1, "congestion_spike", "high",
              "Local trains suspended after tracks flooded at Sion and Kurla; passenger surge out of Dadar station "
              "onto Ranade Road and Tilak Bridge; taxis and BEST buses overwhelmed."),
    _decision("dadar_surge", 2, "egress_surge",
              "Dadar station crowd spilling onto the road after the suspension; more buses requested from BEST; "
              "Tilak Bridge approach jammed.",
              crowd_level="high", extra_buses_requested=15),
    # F13 New Year on Marine Drive
    _decision("newyear_marinedrive", 1, "crowd_density",
              "New Year's Eve crowd on Marine Drive; vehicle entry closed from the Churchgate end; pedestrians only "
              "after 21:00.",
              crowd_level="very high", closure="Marine Drive, NCPA to Girgaon Chowpatty"),
    _aar("newyear_marinedrive", 2, "New Year's Eve Marine Drive",
         "Closing Marine Drive to vehicles at 21:00 and routing cars via Veer Nariman Road kept ambulance access to "
         "the crowd; the crowd dispersed by 01:30."),
    # F14 Gokhale Bridge / SV Road congestion, Andheri
    _incident("gokhale_bridge", 1, "congestion_spike", "medium",
              "Gokhale Bridge approach in Andheri congested from SV Road; east-west traffic at 8 km/h; school buses "
              "delayed."),
    _decision("gokhale_bridge", 2, "congestion",
              "Heavy congestion on Gokhale Bridge and SV Road towards the Western Express Highway; propose more "
              "green for the bridge approach at SV Road.",
              vc_ratio=0.93, speed_kmh=8),
    # F15 waterlogging, western suburbs (Milan Subway / Santacruz)
    _decision("milan_subway", 1, "waterlogging_alert",
              "Heavy rain over the western suburbs; water rising in Milan Subway and at Santacruz; SV Road and the "
              "Vile Parle approach slowing.",
              rain_mm_last_hour=55, risk_class=3, gates="open"),
    _incident("milan_subway", 2, "weather", "high",
              "Knee-deep water in Milan Subway and at Vile Parle; BEST buses stalled on SV Road; Irla pumping "
              "station at full capacity."),
    # F16 BKC evening peak
    _decision("bkc_peak", 1, "congestion",
              "Evening office peak in Bandra Kurla Complex; office exits jammed onto the BKC connector and the "
              "Kalanagar approach.",
              vc_ratio=0.88, speed_kmh=12),
    _scenario("bkc_peak", 2, "sc-bkc-04", "BKC - Kalanagar - Western Express Highway", 14.3, 520, 0, 5, 0.22, 0),
    # distractors (no query targets them)
    _incident("x_workzone", 1, "other", "low",
              "Metro work narrows SV Road near Jogeshwari to one lane for a week."),
    _incident("x_port_trucks", 1, "congestion_spike", "low",
              "Container trucks queue at a Mumbai Port gate near Wadala; P D'Mello Road slow in the morning."),
    _decision("x_borivali_school", 1, "congestion",
              "School-hour congestion near Borivali station; parents' cars parked on SV Road.",
              vc_ratio=0.71),
    _incident("x_airport_haze", 1, "weather", "low",
              "Morning haze at Mumbai Airport delays departures; Sahar Road light traffic."),
    _scenario("x_chembur", 1, "sc-chembur-09", "Chembur - Ghatkopar - Vikhroli", 9.8, 310, 0, 4, 0.15, 0),
    _decision("x_gateway", 1, "crowd_density",
              "Winter Sunday crowd at the Gateway of India and Colaba Causeway; parking spilling onto P J "
              "Ramchandani Marg.",
              crowd_level="moderate"),
    # hard negatives: the SAME place as a family but a different situation (a model that matches on place
    # names alone ranks these first)
    _decision("x_hindmata_festival", 1, "crowd_density",
              "Ganeshotsav night crowd at the Hindmata pandals on Dr Ambedkar Road; vehicles slowed near Dadar TT.",
              crowd_level="high", rain_mm_last_hour=0),
    _decision("x_sealink_vip", 1, "pre_movement",
              "Protected movement to cross the Sea Link at 07:00 towards Worli; 6-minute hold planned.",
              expected_hold_min=6),
    _incident("x_lalbaug_signal", 1, "signal_failure", "medium",
              "Cable cut darkens the signals at Lalbaug junction; manual control on Dr Ambedkar Road."),
    _incident("x_worlinaka_shopping", 1, "congestion_spike", "medium",
              "Festive shopping crowd at Worli Naka; BEST buses slow on Dr E Moses Road; no ambulance request "
              "pending."),
    _decision("x_marinedrive_parade", 1, "ceremonial",
              "Navy Day display rehearsal on Marine Drive; Marine Drive closed 06:00-09:00; Veer Nariman Road "
              "diversion.",
              closure_until="09:00"),
    _incident("x_dadar_rain", 1, "weather", "medium",
              "Water under the Dadar TT flyover after a short shower; Dr Ambedkar Road southbound slow; trains on "
              "time."),
    _decision("x_milan_festival", 1, "crowd_density",
              "Ganeshotsav pandals draw crowds near Milan Subway on SV Road in Santacruz; no rain.",
              crowd_level="high"),
    _incident("x_sion_water", 1, "weather", "low",
              "Shallow water under the Sion flyover after rain; signals working; Eastern Express Highway moving."),
    _incident("x_sealink_toll", 1, "congestion_spike", "low",
              "Toll plaza queue on the Bandra–Worli Sea Link towards Worli; no movement planned; Bandra side slow."),
    _incident("x_pedder_tree", 1, "weather", "medium",
              "A tree fell on Pedder Road after a squall; one lane blocked near Kemps Corner."),
    _incident("x_bandra_hillroad", 1, "other", "low",
              "Hill Road in Bandra narrowed for two hours for drain repairs; no crowd."),
    _scenario("x_wankhede_day", 1, "sc-wankhede-02", "Wankhede Stadium - Churchgate (day match, light crowd)",
              4.1, 150, 60, 2, 0.08, 0),
]

MEMORY_QUERIES: list[dict] = [
    # F1
    {"lang": "en", "family": "tide_hindmata", "text": "TRIGGER: waterlogging_alert\nHeavy rain at high tide, "
     "outfalls shut; water rising at Hindmata and Dadar TT. Ambulance route to Sion Hospital at risk."},
    {"lang": "mr", "family": "tide_hindmata", "text": "भरतीच्या वेळी मुसळधार पाऊस, समुद्राकडची मुखे बंद. हिंदमाता "
     "आणि दादर टीटीला पाणी वाढत आहे, सायन रुग्णालयाकडे जाणाऱ्या रुग्णवाहिकेचा मार्ग धोक्यात."},
    {"lang": "hi", "family": "tide_hindmata", "text": "ज्वार के समय भारी बारिश, आउटफ़ॉल बंद। हिंदमाता और दादर टीटी पर "
     "जलभराव बढ़ रहा है, सायन अस्पताल जाने वाली एम्बुलेंस का रास्ता खतरे में।"},
    {"lang": "mixed", "family": "tide_hindmata", "text": "Hindmata la high tide chya veli heavy rain, paani "
     "bharat aahe, Ambedkar Road slow, ambulance Sion Hospital la kashi jaanar?"},
    # F2
    {"lang": "en", "family": "visarjan_lalbaug", "text": "Visarjan night crowds at Lalbaug around Lalbaugcha Raja "
     "spilling onto the road; Bharat Mata junction jammed."},
    {"lang": "mr", "family": "visarjan_lalbaug", "text": "अनंत चतुर्दशीच्या रात्री लालबागचा राजा परिसरात भाविकांची "
     "प्रचंड गर्दी, भारतमाता चौकात वाहने अडकली."},
    {"lang": "mixed", "family": "visarjan_lalbaug", "text": "Visarjan chi gardi Lalbaug la, Bharat Mata junction la "
     "gaadi halat nahi, miravnuk raastyavar"},
    # F3
    {"lang": "en", "family": "sea_link", "text": "TRIGGER: route_blockage\nTruck broken down on the Sea Link "
     "towards Bandra in the evening rush; queue back to the Worli end."},
    {"lang": "mr", "family": "sea_link", "text": "संध्याकाळच्या गर्दीत वांद्रे–वरळी सागरी सेतूवर एक बस बंद पडली, "
     "वरळीच्या टोकापर्यंत लांब रांग."},
    {"lang": "hi", "family": "sea_link", "text": "शाम के समय बांद्रा–वर्ली सी लिंक पर बस खराब, वर्ली छोर तक लंबा जाम।"},
    # F4
    {"lang": "en", "family": "vip_mantralaya", "text": "TRIGGER: pre_movement\nProtected movement from Mantralaya "
     "to the airport this afternoon via the Coastal Road and the Sea Link."},
    {"lang": "mr", "family": "vip_mantralaya", "text": "आज दुपारी मंत्रालय ते विमानतळ व्हीआयपी ताफा, कोस्टल रोड आणि "
     "सागरी सेतूमार्गे."},
    {"lang": "hi", "family": "vip_mantralaya", "text": "मंत्रालय से मुंबई हवाई अड्डे तक वीआईपी काफ़िला, कोस्टल रोड और "
     "सी लिंक से।"},
    # F5
    {"lang": "en", "family": "wankhede_egress", "text": "Match over at Wankhede, crowd heading to Churchgate and "
     "Marine Lines stations; buses stuck on Marine Drive."},
    {"lang": "mr", "family": "wankhede_egress", "text": "वानखेडे स्टेडियममध्ये सामना संपला, प्रेक्षक चर्चगेट आणि मरीन "
     "लाइन्स स्थानकांकडे निघाले."},
    # F6
    {"lang": "en", "family": "cyclone_marinedrive", "text": "Cyclone aftermath: fallen trees blocking Marine Drive; "
     "access to JJ Hospital must be cleared."},
    {"lang": "mr", "family": "cyclone_marinedrive", "text": "चक्रीवादळानंतर मरीन ड्राइव्हवर झाडे पडून रस्ता बंद, जे.जे. "
     "रुग्णालयाकडे जाणारा मार्ग मोकळा करायला हवा."},
    {"lang": "mixed", "family": "cyclone_marinedrive", "text": "Cyclone mule Marine Drive var jhaad padla, JJ "
     "Hospital la janyacha rasta block"},
    # F7
    {"lang": "en", "family": "amb_kem", "text": "TRIGGER: ambulance_request\nAmbulance (108) needs a green "
     "corridor from Worli Naka to KEM on Dr E Moses Road."},
    {"lang": "mr", "family": "amb_kem", "text": "वरळी नाका ते केईएम रुग्णालयापर्यंत रुग्णवाहिकेसाठी ग्रीन कॉरिडॉर "
     "हवा."},
    {"lang": "hi", "family": "amb_kem", "text": "वर्ली नाका से केईएम अस्पताल तक एम्बुलेंस के लिए ग्रीन कॉरिडोर चाहिए।"},
    # F8
    {"lang": "en", "family": "signal_sion", "text": "Traffic lights dead at Sion Circle after a power cut; Eastern "
     "Express Highway queue growing."},
    {"lang": "mr", "family": "signal_sion", "text": "सायन सर्कलला वीज गेल्याने सिग्नल बंद, पूर्व द्रुतगती महामार्गावर "
     "रांग वाढत आहे."},
    # F9
    {"lang": "en", "family": "mount_mary", "text": "Mount Mary fair pilgrims crowding Bandra station; BEST buses "
     "loading for Hill Road."},
    {"lang": "hi", "family": "mount_mary", "text": "माउंट मेरी मेले के लिए श्रद्धालुओं की भीड़ बांद्रा स्टेशन पर, हिल रोड "
     "पर बसें।"},
    # F10
    {"lang": "en", "family": "marathon", "text": "Mumbai Marathon this Sunday; Marine Drive and the Sea Link closed "
     "until the last runner."},
    {"lang": "mr", "family": "marathon", "text": "रविवारी मुंबई मॅरेथॉन, मरीन ड्राइव्ह आणि सागरी सेतू बंद राहणार."},
    # F11
    {"lang": "en", "family": "dahihandi_worli", "text": "Huge Dahi Handi crowd at Worli; Pandurang Budhkar Marg "
     "closed, buses diverted."},
    {"lang": "mr", "family": "dahihandi_worli", "text": "वरळीत दहीहंडीला मोठी गर्दी, पांडुरंग बुधकर मार्ग बंद."},
    # F12
    {"lang": "en", "family": "dadar_surge", "text": "Locals suspended, huge crowd coming out of Dadar station "
     "onto Tilak Bridge."},
    {"lang": "mixed", "family": "dadar_surge", "text": "Dadar la local band, station madhun gardi baher, Tilak "
     "Bridge jam"},
    # F13
    {"lang": "en", "family": "newyear_marinedrive", "text": "New Year's Eve: Marine Drive packed with people, "
     "close it to vehicles?"},
    {"lang": "mr", "family": "newyear_marinedrive", "text": "नववर्षाच्या स्वागताच्या रात्री मरीन ड्राइव्हवर प्रचंड "
     "गर्दी, वाहने बंद करायची का?"},
    # F14
    {"lang": "en", "family": "gokhale_bridge", "text": "SV Road crawling in Andheri; Gokhale Bridge approach "
     "backed up."},
    {"lang": "hi", "family": "gokhale_bridge", "text": "गोखले पुल पर भारी जाम, अंधेरी में एस वी रोड पर धीमी रफ़्तार।"},
    # F15
    {"lang": "en", "family": "milan_subway", "text": "Water rising in Milan Subway and at Santacruz after a "
     "downpour; buses stalled on SV Road."},
    {"lang": "mr", "family": "milan_subway", "text": "मिलन सबवे आणि सांताक्रूझमध्ये पावसाचे पाणी साचत आहे, बस अडकल्या."},
    {"lang": "mixed", "family": "milan_subway", "text": "Milan Subway madhe gudghabhar paani, SV Road var bus "
     "adaklya"},
    # F16
    {"lang": "en", "family": "bkc_peak", "text": "Office rush in BKC; exits jammed towards Kalanagar."},
    {"lang": "mr", "family": "bkc_peak", "text": "वांद्रे कुर्ला संकुलात ऑफिस सुटण्याची गर्दी, कलानगरकडे कोंडी."},
    # harder: alternate names, no exact place string, the situation (not the place) decides
    {"lang": "en", "family": "tide_hindmata", "text": "TRIGGER: waterlogging_alert\nTide above 4.5 m, outfalls "
     "shut, cloudburst over the Parel-Dadar stretch; Dr Ambedkar Road slowing.\nrisk_class: 2"},
    {"lang": "mr", "family": "tide_hindmata", "text": "समुद्राला भरती, मुखे बंद; परळ-दादर पट्ट्यात गुडघाभर पाणी, "
     "डॉ. आंबेडकर मार्ग संथ."},
    {"lang": "en", "family": "sea_link", "text": "TRIGGER: route_blockage\nBreakdown on the cable-stayed bridge "
     "across Mahim Bay during the evening peak; tow vehicle requested; Worli Seaface backing up."},
    {"lang": "en", "family": "dahihandi_worli", "text": "TRIGGER: mass_gathering\nGovinda pyramids are drawing a "
     "big crowd at Jambori Maidan; Ganpatrao Kadam Marg blocked; BEST buses held."},
    {"lang": "hi", "family": "dahihandi_worli", "text": "वर्ली में दही हंडी की भारी भीड़, पांडुरंग बुधकर मार्ग बंद, बसें "
     "मोड़ी गईं।"},
    {"lang": "en", "family": "amb_kem", "text": "TRIGGER: ambulance_request\nPatient transfer by 108 from the Worli "
     "junction to King Edward Memorial Hospital in Parel; six signals on the way.\nwindow_sec: 120"},
    {"lang": "mr", "family": "cyclone_marinedrive", "text": "वादळानंतर क्वीन्स नेकलेसवर मोठी झाडे पडून रस्ता बंद, "
     "सर जे.जे. रुग्णालयात पोहोचण्याचा मार्ग आधी मोकळा करायला हवा."},
    {"lang": "en", "family": "marathon", "text": "TRIGGER: race\nSunday morning road race from CSMT along Marine "
     "Drive and over the Sea Link; stretch closed until the last runner clears."},
    {"lang": "mr", "family": "milan_subway", "text": "पश्चिम उपनगरांत मुसळधार पाऊस, मिलन सबवेत पाणी साचून बस बंद, "
     "इर्ला उदंचन केंद्र पूर्ण क्षमतेने सुरू."},
    {"lang": "mixed", "family": "signal_sion", "text": "Sion Circle la light geli, signal band, Eastern Express "
     "Highway var line vadhtey, constable manual control kartayt"},
    {"lang": "en", "family": "dadar_surge", "text": "TRIGGER: egress_surge\nSuburban services suspended at the "
     "Central-Western interchange station; passengers spilling onto Ranade Road; BEST asked for extra buses."},
    {"lang": "en", "family": "visarjan_lalbaug", "text": "TRIGGER: crowd_density\nAnant Chaturdashi night in Parel, "
     "devotees thronging the procession from the Lalbaug market towards the sea; Dr Ambedkar Road one-way in "
     "force."},
]

# ─────────────────────────────────────────────────────────────────────────────
# (b) SOP / advisory
# ─────────────────────────────────────────────────────────────────────────────

DOC_FILES = ("hydro", "forecast", "speech", "vision", "twin")
PACK_KEYS = (
    "strip_watch", "strip_hold", "strip_severe", "consequence_procession", "consequence_mass_gathering",
    "consequence_race", "consequence_ceremonial", "consequence_egress_surge", "consequence_work_zone",
    "consequence_vehicle_pursuit", "consequence_unknown", "card_alt_none", "card_alt_unavailable",
    "citizen_feed_offline", "doctrine_note", "driver_deferred_body", "driver_window_unpublished",
    "comms_session_only",
)
PACK_DIR = REPO / "services/command-deck/src/lib/i18n"

# Advisory and proposal texts rendered from services/hydro/src/hydro/proposals.py and
# services/forecast/src/forecast/proposals.py templates (place values chosen for the eval).
RENDERED = {
    "r:hy_adv_en": "Traffic advisory (draft): waterlogging is likely within the next 90 minutes at these places: "
                   "Hindmata, King's Circle, Dr Ambedkar Road. Please avoid these roads if you can. Do not touch "
                   "electric poles or wires in standing water. Emergency: 112; ambulance (108).",
    "r:hy_adv_mr": "वाहतूक सूचना (मसुदा): पुढील 90 मिनिटांत या ठिकाणी पाणी साचण्याची शक्यता आहे: हिंदमाता, किंग्ज "
                   "सर्कल, डॉ. आंबेडकर मार्ग. शक्य असल्यास हे रस्ते टाळा. साचलेल्या पाण्यात विजेचे खांब किंवा तारा "
                   "यांना हात लावू नका. आपत्कालीन क्रमांक 112; रुग्णवाहिका (108).",
    "r:hy_wire": "Live-wire hazard — Hindmata (Dr Ambedkar Road): waterlogging risk 2 (15–30 cm). Propose asking the "
                 "power utility (BEST / Adani Electricity / Tata Power) to inspect and, where needed, isolate "
                 "street-light and overhead supply along this road.",
    "r:hy_amb": "Ambulance (108) note — King's Circle (Dr Ambedkar Road): passable for about 35 min more; use "
                "Senapati Bapat Marg → Mahim Causeway.",
    "r:hy_reroute": "Hindmata (Dr Ambedkar Road): waterlogging risk 2 (15–30 cm), deep water in about 60 min; "
                    "propose diverting traffic via Senapati Bapat Marg → Tilak Bridge.",
    "r:fc_adv": "Heavy traffic expected near Sion Circle in about 45 minutes. Please plan ahead.",
}

# The questions are place-neutral where their gold paragraph still describes the previous city's hydrology, so the
# set measures retrieval, not a city mismatch. Gold ids are paragraph positions in docs/ai/*.md as of commit 88ac858
# (paragraph ids shift when a doc is edited, and build() only checks that every id exists): when the Mumbai rewrite
# of docs/ai lands, re-map each gold to the paragraph that answers its question, rebuild, and re-run the eval.
SOP_QUERIES: list[dict] = [
    {"lang": "en", "text": "What tide level closes the storm-water outfall gates?", "gold": ["d:hydro:6"]},
    {"lang": "mr", "text": "भरतीची पातळी किती मीटरवर गेल्यावर आउटफॉलचे दरवाजे बंद केले जातात?", "gold": ["d:hydro:6"]},
    {"lang": "hi", "text": "ज्वार कितने मीटर पर पहुँचने पर आउटफ़ॉल गेट बंद होते हैं?", "gold": ["d:hydro:6"]},
    {"lang": "en", "text": "Are the municipal pumping station readings real or emulated?",
     "gold": ["d:hydro:10", "d:hydro:11"]},
    {"lang": "mr", "text": "पंपिंग स्टेशनची माहिती खरी आहे की एम्युलेटेड?", "gold": ["d:hydro:10", "d:hydro:11"]},
    {"lang": "mixed", "text": "Pumping station cha data real feed madhun yeto ka?",
     "gold": ["d:hydro:10", "d:hydro:11"]},
    {"lang": "en", "text": "What proposals does the waterlogging service draft for a flagged road?",
     "gold": ["d:hydro:1", "d:hydro:12", "d:hydro:13"]},
    {"lang": "mr", "text": "पाणी साचण्याचा धोका असलेल्या रस्त्यासाठी कोणते प्रस्ताव तयार होतात?",
     "gold": ["d:hydro:1", "d:hydro:12", "d:hydro:13"]},
    {"lang": "en", "text": "How much rain fell in the peak hour on 23 September 2025?", "gold": ["d:hydro:14"]},
    {"lang": "mr", "text": "२३ सप्टेंबर २०२५ रोजी सर्वाधिक पाऊस कोणत्या तासात पडला?", "gold": ["d:hydro:14"]},
    {"lang": "en", "text": "Why did the gridded rain archive miss the September 2025 storm?",
     "gold": ["d:hydro:16", "d:hydro:17"]},
    {"lang": "en", "text": "Which bridges and flyovers are treated as elevated in the susceptibility score?",
     "gold": ["d:hydro:9"]},
    {"lang": "hi", "text": "जलभराव के हिसाब से कौन से पुल और फ्लाईओवर ऊँचे माने जाते हैं?", "gold": ["d:hydro:9"]},
    {"lang": "en", "text": "Is the tide at the river gauge measured or modelled?",
     "gold": ["d:hydro:2", "d:hydro:3", "d:hydro:4", "d:hydro:5"]},
    {"lang": "en", "text": "When does the corridor forecast raise a pre-emptive diversion proposal?",
     "gold": ["d:forecast:0"]},
    {"lang": "mr", "text": "वाहतूक कोंडी होण्याआधीच वळवण्याचा (डायव्हर्जन) प्रस्ताव कधी दिला जातो?",
     "gold": ["d:forecast:0"]},
    {"lang": "mixed", "text": "Sion Circle var V/C 0.8 cross jhala tar diversion propose hoto ka?",
     "gold": ["d:forecast:0", "d:forecast:9"]},
    {"lang": "en", "text": "How accurate is Chronos-2 against the seasonal-naive baseline in the backtest?",
     "gold": ["d:forecast:10", "d:forecast:11"]},
    {"lang": "en", "text": "Is the corridor forecast based on real traffic data?", "gold": ["d:forecast:14"]},
    {"lang": "mr", "text": "वाहतूक कोंडीचा अंदाज खऱ्या वाहतुकीच्या माहितीवर आधारित आहे का?", "gold": ["d:forecast:14"]},
    {"lang": "en", "text": "When is the forecasting model freed from GPU memory?", "gold": ["d:forecast:12"]},
    {"lang": "en", "text": "How is the detour chosen for a forecast diversion?", "gold": ["d:forecast:8"]},
    {"lang": "hi", "text": "सिंथेटिक ट्रैफ़िक इतिहास में सुबह और शाम की भीड़ कब होती है?", "gold": ["d:forecast:6"]},
    {"lang": "mr", "text": "फील्ड अधिकाऱ्याने मराठीत बोलून अहवाल दिला तर काय होते?", "gold": ["d:speech:0"]},
    {"lang": "hi", "text": "फ़ील्ड अधिकारी मराठी में बोलकर रिपोर्ट दे तो क्या होता है?", "gold": ["d:speech:0"]},
    {"lang": "en", "text": "What word error rate and place accuracy did the Marathi voice reports reach?",
     "gold": ["d:speech:9", "d:speech:5"]},
    {"lang": "mixed", "text": "Marathi voice report sathi whisper turbo ka nahi ghetla?", "gold": ["d:speech:6"]},
    {"lang": "mr", "text": "कॅमेऱ्याच्या फोटोवरून रस्त्याच्या कोणत्या स्थिती ओळखता येतात?", "gold": ["d:vision:0"]},
    {"lang": "en", "text": "How accurate was the camera road-state reader in its evaluation?", "gold": ["d:vision:3"]},
    {"lang": "en", "text": "Why test a signal-timing change in a twin before proposing it?",
     "gold": ["d:twin:0", "d:twin:2"]},
    {"lang": "mr", "text": "सिग्नलच्या वेळेतील बदलाचा प्रस्ताव कधी रद्द केला जातो?", "gold": ["d:twin:2", "d:twin:3"]},
    {"lang": "en", "text": "Does the language model choose the signal timing?", "gold": ["d:twin:6"]},
    {"lang": "en", "text": "Which baselines are signal proposals compared against?", "gold": ["d:twin:5"]},
    {"lang": "mr", "text": "रुग्णवाहिका पोहोचण्याच्या किती आधी ग्रीन कॉरिडॉर उघडतो?", "gold": ["p:doctrine_note"]},
    {"lang": "en", "text": "How early does the green corridor open before an ambulance reaches a junction?",
     "gold": ["p:doctrine_note"]},
    {"lang": "hi", "text": "मैराथन के दौरान सड़क कब तक बंद रहती है?", "gold": ["p:consequence_race"]},
    {"lang": "mr", "text": "स्टेडियममधून गर्दी बाहेर पडताना वाहने कशी सोडली जातात?",
     "gold": ["p:consequence_egress_surge"]},
    {"lang": "en", "text": "What should I do if there is no signed alternate route?", "gold": ["p:card_alt_none"]},
    {"lang": "mr", "text": "कंट्रोल रूमने विनंती स्थगित ठेवली तर रुग्णवाहिका चालकाने काय करावे?",
     "gold": ["p:driver_deferred_body"]},
    {"lang": "en", "text": "Are the advisory drafts sent out automatically?", "gold": ["p:comms_session_only"]},
    {"lang": "mr", "text": "मिरवणूक जात असताना चौक बंद असतो का?", "gold": ["p:consequence_procession"]},
    {"lang": "hi", "text": "शिवाजी पार्क की परेड के समय ट्रैफ़िक कैसे रोका जाता है?", "gold": ["p:consequence_ceremonial"]},
    {"lang": "mixed", "text": "Road work chalu aahe, ek lane madhun gaadi jail ka?", "gold": ["p:consequence_work_zone"]},
    {"lang": "mr", "text": "साचलेल्या पाण्यात विजेच्या खांबांबाबत कोणती खबरदारी घ्यावी?",
     "gold": ["r:hy_adv_mr", "r:hy_adv_en", "r:hy_wire", "d:hydro:23"]},
    {"lang": "mixed", "text": "Paani saachla asel tar electric pole la haat lavu naka, advisory madhe kay lihila aahe?",
     "gold": ["r:hy_adv_mr", "r:hy_adv_en", "r:hy_wire", "d:hydro:23"]},
    {"lang": "en", "text": "Who is asked to isolate the street-light supply on a waterlogged road?",
     "gold": ["r:hy_wire"]},
    {"lang": "hi", "text": "जलभराव वाली सड़क से एम्बुलेंस कितनी देर और निकल सकती है?",
     "gold": ["r:hy_amb", "d:hydro:13"]},
]

# ─────────────────────────────────────────────────────────────────────────────
# (c) OSINT dedup / clustering (headline sets; same ``event`` = must cluster)
# ─────────────────────────────────────────────────────────────────────────────

OSINT: list[tuple[str, str, str]] = [  # (event, lang, headline)
    ("e01", "en", "Waterlogging at Hindmata after overnight downpour, traffic crawls on Dr Ambedkar Road"),
    ("e01", "mr", "रात्रभर पावसाने हिंदमाता परिसरात पाणी साचले, डॉ. आंबेडकर मार्गावर वाहतूक मंदावली"),
    ("e01", "mixed", "Hindmata la paani bharla, Ambedkar Road var gaadi pudhe jat nahi"),
    ("e02", "en", "Bus breaks down on Bandra–Worli Sea Link, long queues in evening rush"),
    ("e02", "mr", "वांद्रे–वरळी सागरी सेतूवर बस बंद पडली, संध्याकाळी मोठी वाहतूक कोंडी"),
    ("e02", "hi", "बांद्रा–वर्ली सी लिंक पर बस खराब, शाम को लंबा जाम"),
    ("e03", "en", "Fire breaks out at a godown near Kalbadevi; ten fire tenders rushed"),
    ("e03", "mr", "काळबादेवीजवळ गोदामाला आग, घटनास्थळी अग्निशमन दलाचे दहा बंब"),
    ("e04", "en", "Tree uprooted on Marine Drive after storm, both carriageways blocked"),
    ("e04", "mr", "वादळात मरीन ड्राइव्हवर झाड उन्मळून पडले, दोन्ही बाजूंचे रस्ते बंद"),
    ("e05", "en", "Signal failure at Sion Circle causes long tailback on Eastern Express Highway"),
    ("e05", "mr", "सायन सर्कलला सिग्नल बिघडला, पूर्व द्रुतगती महामार्गावर लांब रांगा"),
    ("e06", "en", "Local trains suspended after tracks flood; crowds swell at Dadar station"),
    ("e06", "mr", "रुळांवर पाणी साचल्याने लोकल सेवा ठप्प, दादर स्थानकात प्रचंड गर्दी"),
    ("e06", "hi", "पटरियों पर पानी भरने से लोकल ट्रेनें बंद, दादर स्टेशन पर भारी भीड़"),
    ("e07", "en", "Ganeshotsav crowd: Lalbaugcha Raja sees record footfall on the weekend"),
    ("e07", "mr", "आठवड्याच्या शेवटी लालबागचा राजाच्या दर्शनाला विक्रमी गर्दी"),
    ("e08", "en", "Heavy vehicles barred from city roads on visarjan day, says traffic police"),
    ("e08", "mr", "विसर्जनाच्या दिवशी शहरातील रस्त्यांवर अवजड वाहनांना बंदी, वाहतूक पोलिसांची माहिती"),
    ("e09", "en", "Gokhale Bridge approach jammed as SV Road crawls in Andheri"),
    ("e09", "mr", "गोखले पुलाच्या तोंडाशी कोंडी, अंधेरीत एस. व्ही. रोडवर वाहनांच्या लांब रांगा"),
    ("e10", "en", "Knee-deep water in Milan Subway; buses stranded on SV Road"),
    ("e10", "mr", "मिलन सबवेत गुडघाभर पाणी, एस. व्ही. रोडवर बस अडकल्या"),
    ("e11", "en", "Mumbai Marathon on Sunday: Marine Drive, Sea Link closed till 10.30 am"),
    ("e11", "mr", "रविवारी मुंबई मॅरेथॉन, सकाळी साडेदहापर्यंत मरीन ड्राइव्ह व सागरी सेतू बंद"),
    ("e12", "en", "Devotees throng Mount Mary in Bandra as the fair begins"),
    ("e12", "mr", "जत्रा सुरू होताच वांद्र्यातील माउंट मेरी परिसरात भाविकांची गर्दी"),
    ("e12", "hi", "मेला शुरू होते ही बांद्रा के माउंट मेरी में श्रद्धालुओं की भीड़"),
    ("e13", "en", "Metro services hit between Acharya Atre Chowk and Siddhivinayak after power disruption"),
    ("e13", "mr", "वीजपुरवठा खंडित झाल्याने आचार्य अत्रे चौक ते सिद्धिविनायकदरम्यान मेट्रो सेवा विस्कळीत"),
    ("e14", "en", "Heavy rain at high tide: BMC outfalls shut, pumps run at full capacity"),
    ("e14", "mr", "भरतीच्या वेळी मुसळधार पाऊस, महापालिकेने मुखे बंद केली, पंप पूर्ण क्षमतेने सुरू"),
    ("e15", "en", "Crowds on Marine Drive for New Year's Eve; vehicles stopped after 9 pm"),
    ("e15", "mr", "नववर्षाच्या स्वागतासाठी मरीन ड्राइव्हवर जनसागर, रात्री नऊनंतर वाहतूक बंद"),
    ("e16", "en", "Overturned truck on Western Express Highway near Vile Parle slows airport traffic"),
    ("e16", "mr", "विलेपार्लेजवळ पश्चिम द्रुतगती महामार्गावर ट्रक उलटल्याने विमानतळाकडील वाहतूक मंदावली"),
    # hard negatives: same place, different event / same kind, different place
    ("n01", "en", "Bandra–Worli Sea Link to get new LED lighting, says MSRDC"),
    ("n02", "en", "Fire at a shop near Santacruz market brought under control"),
    ("n03", "mr", "दादर स्थानकात नवा सरकता जिना सुरू"),
    ("n04", "en", "Waterlogging at Andheri Subway after heavy rain; SV Road affected"),
    ("n05", "en", "Signal upgrade work at Sion Circle to begin next month"),
    ("n06", "mr", "मरीन ड्राइव्हवर नौदल दिनाच्या संचलनाची रंगीत तालीम"),
    ("n07", "en", "Acharya Atre Chowk junction to be redesigned, BMC approves plan"),
    ("n08", "en", "Tree falls on Pedder Road after squall, one lane blocked"),
    ("n09", "mr", "लालबाग परिसरात रस्ते दुरुस्तीचे काम सुरू"),
    ("n10", "en", "Truck overturns on Eastern Express Highway near Mulund, Thane-bound traffic hit"),
    ("n11", "en", "Bus breaks down on the Eastern Freeway, Wadala-bound traffic slow"),
    ("n12", "mr", "लालबाग चौकात सिग्नल बिघडला, डॉ. आंबेडकर मार्गावर कोंडी"),
    ("n13", "mr", "नाताळच्या संध्याकाळी मरीन ड्राइव्हवर गर्दी, रोषणाई पाहण्यासाठी लोकांचा ओघ"),
    ("n14", "en", "CSMT crowds swell after local trains cancelled on the Harbour line"),
    ("n15", "hi", "लालबाग के गणेश पंडाल के पास दुकान में आग, कोई घायल नहीं"),
    # OSINT test fixture cluster (services/osint-common/tests/fixtures, synthetic, another city)
    ("f01", "en", "Car crashes into three vehicles near Karnavati Club on SG Highway; 3 injured"),
    ("f01", "en", "Multi-vehicle crash on SG Highway near Prahlad Nagar leaves three injured"),
    ("f01", "en", "SG Highway accident: vehicles collided near Prahlad Nagar, one lane blocked"),
    ("f01", "en", "Three injured after car rammed vehicles on SG Highway near Karnavati Club"),
]


# ─────────────────────────────────────────────────────────────────────────────


def doc_paragraphs() -> list[dict]:
    """Every paragraph of 25+ words in docs/ai/*.md (ids d:<file>:<n>, stable for a given doc revision)."""
    out: list[dict] = []
    for name in DOC_FILES:
        text = (REPO / "docs/ai" / f"{name}.md").read_text(encoding="utf-8")
        head = ""
        n = 0
        for block in re.split(r"\n\s*\n", text):
            b = block.strip()
            if b.startswith("#"):
                head = b.splitlines()[0].lstrip("# ").strip()
                b = "\n".join(b.splitlines()[1:]).strip()
                if not b:
                    continue
            if b.startswith(("```", "|", "<")) or len(b.split()) < 25:
                continue
            out.append({"id": f"d:{name}:{n}", "source": f"docs/ai/{name}.md", "title": head,
                        "body": " ".join(b.split()), "lang": "en"})
            n += 1
    return out


def pack_strings() -> list[dict]:
    """The deck's citizen advisory pack strings: the same key in en / mr / hi (ids p:<key>:<lang>)."""
    out: list[dict] = []
    for lang, suffix in (("en", ""), ("mr", ".mr"), ("hi", ".hi")):
        src = (PACK_DIR / f"strings.citizen{suffix}.ts").read_text(encoding="utf-8")
        for key in PACK_KEYS:
            m = re.search(rf"^\s*{key}:\s*\n?\s*'((?:[^'\\]|\\.)*)'", src, re.M)
            if not m:
                raise SystemExit(f"pack key {key} missing in strings.citizen{suffix}.ts")
            out.append({"id": f"p:{key}:{lang}", "source": f"strings.citizen{suffix}.ts", "title": key,
                        "body": m.group(1).replace("\\'", "'"), "lang": lang})
    return out


def build() -> dict:
    sop_docs = doc_paragraphs() + pack_strings() + [
        {"id": k, "source": "rendered from hydro/forecast proposal templates", "title": "", "body": v,
         "lang": "mr" if k.endswith("_mr") else "en"} for k, v in RENDERED.items()]
    ids = {d["id"] for d in sop_docs}
    sop_queries = []
    for i, q in enumerate(SOP_QUERIES):
        gold: list[str] = []
        for g in q["gold"]:
            if g.startswith("p:"):
                gold += [f"{g}:{lang}" for lang in ("en", "mr", "hi")]
            else:
                gold.append(g)
        missing = [g for g in gold if g not in ids]
        if missing:
            raise SystemExit(f"sop query {i} gold ids missing from the corpus: {missing}")
        sop_queries.append({"id": f"sq{i:02d}", "lang": q["lang"], "text": q["text"], "gold": gold})

    families = {d["family"] for d in MEMORY_DOCS}
    mem_queries = []
    for i, q in enumerate(MEMORY_QUERIES):
        if q["family"] not in families:
            raise SystemExit(f"memory query {i}: unknown family {q['family']}")
        gold = [d["id"] for d in MEMORY_DOCS if d["family"] == q["family"]]
        mem_queries.append({"id": f"mq{i:02d}", "lang": q["lang"], "text": q["text"], "gold": gold})

    osint = [{"id": f"h{i:02d}", "event": ev, "lang": lang, "text": text} for i, (ev, lang, text) in enumerate(OSINT)]
    return {
        "label": "SYNTHETIC",
        "note": ("Invented situations, questions and headlines with real Mumbai place names, written for this "
                 "eval from the repo's own material. Not real events; no real person; no real statistic."),
        "memory": {"docs": MEMORY_DOCS, "queries": mem_queries},
        "sop": {"docs": sop_docs, "queries": sop_queries},
        "osint": {"headlines": osint},
    }


def main() -> None:
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    m, s, o = data["memory"], data["sop"], data["osint"]
    langs = lambda qs: {k: sum(1 for q in qs if q["lang"] == k) for k in ("en", "mr", "hi", "mixed")}  # noqa: E731
    print(f"memory: {len(m['docs'])} docs, {len(m['queries'])} queries {langs(m['queries'])}")
    print(f"sop:    {len(s['docs'])} docs, {len(s['queries'])} queries {langs(s['queries'])}")
    events = {h['event'] for h in o['headlines']}
    print(f"osint:  {len(o['headlines'])} headlines, {len(events)} events")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
