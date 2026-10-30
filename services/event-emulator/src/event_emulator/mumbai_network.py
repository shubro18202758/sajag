"""The Mumbai network ids the emulator names — GENERATED, do not edit.

Written by ``tools/mumbai_library.py`` from the city road network
(``cities/mumbai/network.json``): the living city's sites (EN + Marathi names, the
landmarks.json place each sits at), its emulated field units' beats,
the signalised junctions (those with a signal program) and the segments
the profiles' own causes sit on.  Re-run the tool when the network is
regenerated; the emulator's network check (ambient.py) and its tests
(tests/data/mumbai_network_slim.json) catch any drift.
"""

from __future__ import annotations

#: (site_id, kind, EN name, MR name, segments, junctions, detail EN,
#:  detail MR, landmarks.json place, festival)
SITE_ROWS: tuple[tuple, ...] = (
    ('BD-1008', 'breakdown', 'Bandra–Worli Sea Link (northbound)', 'वांद्रे–वरळी सागरी सेतू (उत्तरेकडे)', (1008,), (28, 31), 'BEST bus breakdown', 'बेस्ट बस बंद पडली', 'sea_link', None),
    ('BD-1015', 'breakdown', 'Western Express Highway (Vakola–Sahar)', 'पश्चिम द्रुतगती महामार्ग (वाकोला–सहार)', (1015,), (39, 48), 'Container truck breakdown', 'कंटेनर ट्रक बंद पडला', None, None),
    ('BD-1044', 'breakdown', 'Eastern Express Highway (Sion–Chunabhatti)', 'पूर्व द्रुतगती महामार्ग (सायन–चुनाभट्टी)', (1044,), (63, 64), 'Goods tempo breakdown', 'मालवाहू टेम्पो बंद पडला', 'sion_circle', None),
    ('BD-1036', 'breakdown', 'JVLR (Powai–Gandhinagar)', 'जेव्हीएलआर (पवई–गांधीनगर)', (1036,), (55, 56), 'Kaali-peeli taxi breakdown', 'काळी-पिवळी टॅक्सी बंद पडली', 'powai', None),
    ('BD-1049', 'breakdown', 'Santacruz–Chembur Link Road (Kurla)', 'सांताक्रूझ–चेंबूर जोड रस्ता (कुर्ला)', (1049,), (39, 60), 'Truck breakdown', 'ट्रक बंद पडला', 'kurla', None),
    ('BD-1058', 'breakdown', 'Eastern Freeway (Orange Gate–Sewri)', 'पूर्व मुक्त मार्ग (ऑरेंज गेट–शिवडी)', (1058,), (71, 72), 'Stalled car', 'कार बंद पडली', 'atal_setu', None),
    ('BD-1085', 'breakdown', 'Peddar Road', 'पेडर रोड', (1085,), (8, 10), 'Stalled car', 'कार बंद पडली', 'haji_ali', None),
    ('BD-1041', 'breakdown', 'LBS Marg (Kamani–Ghatkopar)', 'लालबहादूर शास्त्री मार्ग (कमानी–घाटकोपर)', (1041,), (58, 62), 'Private bus breakdown', 'खासगी बस बंद पडली', 'ghatkopar', None),
    ('BD-1006', 'breakdown', 'Mumbai Coastal Road (northbound)', 'मुंबई किनारी रस्ता (उत्तरेकडे)', (1006,), (5, 28), 'App-cab breakdown', 'ॲप कॅब बंद पडली', None, None),
    ('BD-1032', 'breakdown', 'Andheri–Kurla Road (Marol)', 'अंधेरी–कुर्ला रस्ता (मरोळ)', (1032,), (50, 54), 'Tanker breakdown', 'टँकर बंद पडला', 'weh_andheri', None),
    ('BD-1055', 'breakdown', 'Sion–Panvel Highway (Chembur–Mankhurd)', 'सायन–पनवेल महामार्ग (चेंबूर–मानखुर्द)', (1055,), (68, 69), 'Container truck breakdown', 'कंटेनर ट्रक बंद पडला', 'chembur', None),
    ('BD-1028', 'breakdown', 'Gokhale Bridge (Andheri)', 'गोखले पूल (अंधेरी)', (1028,), (44, 46), 'BEST bus breakdown', 'बेस्ट बस बंद पडली', 'andheri', None),
    ('BD-1071', 'breakdown', 'Tilak Bridge (Dadar)', 'टिळक पूल (दादर)', (1071,), (20, 27), 'Auto-rickshaw breakdown', 'रिक्षा बंद पडली', 'dadar', None),
    ('BD-1061', 'breakdown', 'JJ Flyover (Mohammed Ali Road)', 'जे.जे. उड्डाणपूल (मोहम्मद अली रोड)', (1061,), (4, 13), 'Truck breakdown', 'ट्रक बंद पडला', 'jj_hospital', None),
    ('MK-1073', 'market_spillover', 'Dadar West market (Lady Jamshetji Road)', 'दादर पश्चिम बाजार (लेडी जमशेटजी रोड)', (1073,), (27, 33), '', '', 'dadar', None),
    ('MK-1061', 'market_spillover', 'Crawford Market (Mohammed Ali Road)', 'क्रॉफर्ड मार्केट (मोहम्मद अली रोड)', (1061,), (4, 13), '', '', 'police_hq', None),
    ('MK-1023', 'market_spillover', 'Bandra (Hill Road – SV Road)', 'वांद्रे (हिल रोड – एस. व्ही. रोड)', (1023,), (36, 40), '', '', 'bandra', None),
    ('MK-1064', 'market_spillover', 'Lalbaug market (Dr Ambedkar Road)', 'लालबाग बाजार (डॉ. आंबेडकर रोड)', (1064,), (16, 17), '', '', 'lalbaug', None),
    ('MK-1039', 'market_spillover', 'Kurla market (LBS Marg)', 'कुर्ला बाजार (एलबीएस मार्ग)', (1039,), (59, 61), '', '', 'kurla', None),
    ('MK-1026', 'market_spillover', 'Andheri West market (SV Road)', 'अंधेरी पश्चिम बाजार (एस. व्ही. रोड)', (1026,), (43, 44), '', '', 'andheri', None),
    ('MK-1021', 'market_spillover', 'Mahim (causeway market)', 'माहीम (कॉजवे बाजार)', (1021,), (33, 35), '', '', 'mahim_causeway', None),
    ('SE-1086', 'school_egress', 'Walkeshwar Road (Malabar Hill)', 'वाळकेश्वर रोड (मलबार हिल)', (1086,), (6, 9), '', '', None, None),
    ('SE-1084', 'school_egress', 'N S Patkar Marg – Hughes Road', 'ना. सी. पाटकर मार्ग – ह्यूजेस रोड', (1084,), (6, 8), '', '', None, None),
    ('SE-1078', 'school_egress', 'Keshavrao Khadye Marg (Jacob Circle)', 'केशवराव खाडये मार्ग (जेकब सर्कल)', (1078,), (11, 15), '', '', None, None),
    ('SE-1080', 'school_egress', 'Dr A R Nair Road (Mumbai Central)', 'डॉ. ए. आर. नायर रोड (मुंबई सेंट्रल)', (1080,), (11, 12), '', '', 'nair_hospital', None),
    ('SE-1074', 'school_egress', 'Pandurang Budhkar Marg (Worli)', 'पांडुरंग बुधकर मार्ग (वरळी)', (1074,), (24, 26), '', '', None, None),
    ('SE-1024', 'school_egress', 'SV Road (Santacruz)', 'एस. व्ही. रोड (सांताक्रूझ)', (1024,), (40, 41), '', '', None, None),
    ('OR-1005', 'office_rush', 'Veer Nariman Road – D N Road (CSMT)', 'वीर नरिमन रोड – दादाभाई नौरोजी रोड (सीएसएमटी)', (1005,), (3, 4), '', '', 'csmt', None),
    ('OR-1001', 'office_rush', 'Marine Drive (Churchgate–Nariman Point)', 'मरीन ड्राइव्ह (चर्चगेट–नरिमन पॉइंट)', (1001,), (1, 2), '', '', 'marine_drive', None),
    ('OR-1052', 'office_rush', 'Bandra Kurla Complex Road (Kalanagar–BKC)', 'वांद्रे कुर्ला संकुल रस्ता (कलानगर–बीकेसी)', (1052,), (37, 38), '', '', 'bkc', None),
    ('OR-1053', 'office_rush', 'Bandra Kurla Complex Road (BKC–Kurla)', 'वांद्रे कुर्ला संकुल रस्ता (बीकेसी–कुर्ला)', (1053,), (38, 59), '', '', 'bkc', None),
    ('OR-1072', 'office_rush', 'Senapati Bapat Marg (Lower Parel)', 'सेनापती बापट मार्ग (लोअर परळ)', (1072,), (26, 27), '', '', None, None),
    ('OR-1013', 'office_rush', 'Western Express Highway (Kalanagar)', 'पश्चिम द्रुतगती महामार्ग (कलानगर)', (1013,), (34, 37), '', '', 'kalanagar', None),
    ('OR-1076', 'office_rush', 'Annie Besant Road (Worli)', 'ॲनी बेझंट रोड (वरळी)', (1076,), (24, 25), '', '', 'worli_naka', None),
    ('OR-1007', 'office_rush', 'Mumbai Coastal Road (southbound)', 'मुंबई किनारी रस्ता (दक्षिणेकडे)', (1007,), (5, 29), '', '', None, None),
    ('IT-1034', 'it_shift_change', 'Saki Vihar Road (Powai)', 'साकी विहार रोड (पवई)', (1034,), (54, 55), '', '', 'powai', None),
    ('IT-1035', 'it_shift_change', 'JVLR (Jogeshwari–Powai)', 'जेव्हीएलआर (जोगेश्वरी–पवई)', (1035,), (51, 55), '', '', 'powai', None),
    ('IT-1033', 'it_shift_change', 'Andheri–Kurla Road (Saki Naka–Kurla)', 'अंधेरी–कुर्ला रस्ता (साकी नाका–कुर्ला)', (1033,), (54, 58), '', '', None, None),
    ('IT-1018', 'it_shift_change', 'Western Express Highway (Goregaon)', 'पश्चिम द्रुतगती महामार्ग (गोरेगाव)', (1018,), (51, 52), '', '', None, None),
    ('WL-1066', 'waterlogging', 'Dr Ambedkar Road (Hindmata)', 'डॉ. आंबेडकर रोड (हिंदमाता)', (1066,), (19, 20), '', '', 'hindmata', None),
    ('WL-1067', 'waterlogging', "Dr Ambedkar Road (King's Circle, Gandhi Market)", 'डॉ. आंबेडकर रोड (किंग्ज सर्कल, गांधी मार्केट)', (1067,), (20, 21), '', '', 'kings_circle', None),
    ('WL-1069', 'waterlogging', 'Dr Ambedkar Road (Sion)', 'डॉ. आंबेडकर रोड (सायन)', (1069,), (22, 23), '', '', 'sion_circle', None),
    ('WL-1027', 'waterlogging', 'Milan Subway road (Santacruz)', 'मिलन सबवे रस्ता (सांताक्रूझ)', (1027,), (41, 42), '', '', 'milan_subway', None),
    ('WL-1030', 'waterlogging', 'Andheri Subway approach (Sahar Road)', 'अंधेरी सबवे मार्ग (सहार रोड)', (1030,), (46, 47), '', '', 'andheri_subway', None),
    ('WL-1038', 'waterlogging', 'LBS Marg (Kurla, by the Mithi)', 'एलबीएस मार्ग (कुर्ला, मिठी नदीजवळ)', (1038,), (59, 63), '', '', 'mithi_kurla', None),
    ('WL-1065', 'waterlogging', 'Dr Ambedkar Road (Parel)', 'डॉ. आंबेडकर रोड (परळ)', (1065,), (17, 19), '', '', 'parel', None),
    ('WL-1044', 'waterlogging', 'Eastern Express Highway (Chunabhatti)', 'पूर्व द्रुतगती महामार्ग (चुनाभट्टी)', (1044,), (63, 64), '', '', None, None),
    ('WL-1063', 'waterlogging', 'Dr Ambedkar Road (Byculla)', 'डॉ. आंबेडकर रोड (भायखळा)', (1063,), (15, 16), '', '', None, None),
    ('WL-1053', 'waterlogging', 'Bandra Kurla Complex Road (Kurla end)', 'वांद्रे कुर्ला संकुल रस्ता (कुर्ला टोक)', (1053,), (38, 59), '', '', 'mithi_kurla', None),
    ('FC-1064', 'festival_crowd', 'Dr Ambedkar Road (Lalbaugcha Raja)', 'डॉ. आंबेडकर रोड (लालबागचा राजा)', (1064,), (16, 17), '', '', 'lalbaugcha_raja', 'puja'),
    ('FC-1065', 'festival_crowd', 'Dr Ambedkar Road (Parel)', 'डॉ. आंबेडकर रोड (परळ)', (1065,), (17, 19), '', '', 'parel', 'puja'),
    ('FC-1083', 'festival_crowd', 'Jagannath Shankarsheth Marg (Girgaon Chowpatty)', 'जगन्नाथ शंकरशेट मार्ग (गिरगाव चौपाटी)', (1083,), (6, 7), '', '', 'girgaon_chowpatty', 'puja'),
    ('FC-1068', 'festival_crowd', "Dr Ambedkar Road (GSB Seva Mandal, King's Circle)", 'डॉ. आंबेडकर रोड (जीएसबी सेवा मंडळ, किंग्ज सर्कल)', (1068,), (21, 22), '', '', 'gsb_kings_circle', 'puja'),
    ('FC-1062', 'festival_crowd', 'Sir JJ Road (JJ, visarjan route)', 'सर जे.जे. रोड (जे.जे., विसर्जन मार्ग)', (1062,), (13, 15), '', '', 'jj_hospital', 'puja'),
    ('FC-1063', 'festival_crowd', 'Dr Ambedkar Road (Byculla, visarjan route)', 'डॉ. आंबेडकर रोड (भायखळा, विसर्जन मार्ग)', (1063,), (15, 16), '', '', 'lalbaug', 'puja'),
    ('FC-1002', 'festival_crowd', 'Marine Drive (Churchgate–Marine Lines)', 'मरीन ड्राइव्ह (चर्चगेट–मरीन लाइन्स)', (1002,), (2, 5), '', '', 'marine_drive', 'year_end'),
    ('FC-1003', 'festival_crowd', 'Marine Drive (Marine Lines–Girgaon Chowpatty)', 'मरीन ड्राइव्ह (मरीन लाइन्स–गिरगाव चौपाटी)', (1003,), (5, 6), '', '', 'girgaon_chowpatty', 'year_end'),
    ('FC-1004', 'festival_crowd', 'Veer Nariman Road (Churchgate)', 'वीर नरिमन रोड (चर्चगेट)', (1004,), (2, 3), '', '', 'churchgate', 'year_end'),
    ('SF-J2', 'signal_fault', 'Marine Drive (Veer Nariman Road, Churchgate)', 'मरीन ड्राइव्ह (वीर नरिमन मार्ग, चर्चगेट)', (1001, 1002, 1004), (2,), '', '', None, None),
    ('SF-J3', 'signal_fault', 'Churchgate (Veer Nariman Road)', 'चर्चगेट (वीर नरिमन मार्ग)', (1004, 1005), (3,), '', '', 'churchgate', None),
    ('SF-J4', 'signal_fault', 'CSMT junction (D N Road)', 'सीएसएमटी जंक्शन (दादाभाई नौरोजी मार्ग)', (1005, 1060, 1061), (4,), '', '', 'csmt', None),
    ('SF-J5', 'signal_fault', 'Marine Drive (Coastal Road south end, Marine Lines)', 'मरीन ड्राइव्ह (सागरी किनारा मार्ग दक्षिण टोक, मरीन लाइन्स)', (1002, 1003, 1006, 1007), (5,), '', '', None, None),
    ('SF-J6', 'signal_fault', 'Girgaon Chowpatty (Marine Drive)', 'गिरगाव चौपाटी (मरीन ड्राइव्ह)', (1003, 1083, 1084, 1086), (6,), '', '', 'girgaon_chowpatty', None),
    ('SF-J10', 'signal_fault', 'Haji Ali junction', 'हाजी अली जंक्शन', (1075, 1085), (10,), '', '', 'haji_ali', None),
    ('SF-J11', 'signal_fault', 'Jacob Circle (Sant Gadge Maharaj Chowk)', 'जेकब सर्कल (संत गाडगे महाराज चौक)', (1078, 1079, 1080), (11,), '', '', None, None),
    ('SF-J14', 'signal_fault', 'Nagpada junction (Maulana Azad Road)', 'नागपाडा जंक्शन (मौलाना आझाद मार्ग)', (1081, 1082), (14,), '', '', None, None),
    ('SF-J16', 'signal_fault', 'Lalbaug (Dr Ambedkar Road)', 'लालबाग (डॉ. आंबेडकर मार्ग)', (1063, 1064, 1079), (16,), '', '', 'lalbaug', None),
    ('SF-J17', 'signal_fault', 'Parel (Dr Ambedkar Road)', 'परळ (डॉ. आंबेडकर मार्ग)', (1064, 1065), (17,), '', '', 'parel', None),
    ('SF-J19', 'signal_fault', 'Hindmata (Dadar East)', 'हिंदमाता (दादर पूर्व)', (1065, 1066, 1070), (19,), '', '', 'hindmata', None),
    ('SF-J20', 'signal_fault', 'Dadar TT Circle', 'दादर टीटी सर्कल', (1066, 1067, 1071), (20,), '', '', 'dadar_tt', None),
    ('SF-J22', 'signal_fault', 'Sion Hospital (LTMGH) junction', 'सायन रुग्णालय जंक्शन', (1068, 1069), (22,), '', '', 'sion_hospital', None),
    ('SF-J23', 'signal_fault', 'Sion Circle', 'सायन सर्कल', (1043, 1069), (23,), '', '', 'sion_circle', None),
    ('SF-J24', 'signal_fault', 'Worli Naka', 'वरळी नाका', (1074, 1076, 1077), (24,), '', '', 'worli_naka', None),
    ('SF-J25', 'signal_fault', 'Acharya Atre Chowk (Worli)', 'आचार्य अत्रे चौक (वरळी)', (1075, 1076), (25,), '', '', None, None),
    ('SF-J26', 'signal_fault', 'Lower Parel (Senapati Bapat Marg)', 'लोअर परळ (सेनापती बापट मार्ग)', (1072, 1074), (26,), '', '', None, None),
    ('SF-J27', 'signal_fault', 'Dadar West (Tilak Bridge, Senapati Bapat Marg)', 'दादर पश्चिम (टिळक पूल, सेनापती बापट मार्ग)', (1071, 1072, 1073), (27,), '', '', None, None),
    ('SF-J33', 'signal_fault', 'Mahim (Lady Jamshetji Road, causeway south end)', 'माहीम (लेडी जमशेटजी मार्ग, कॉजवे दक्षिण टोक)', (1021, 1073), (33,), '', '', None, None),
    ('SF-J36', 'signal_fault', 'Bandra (SV Road, Hill Road)', 'वांद्रे (स्वामी विवेकानंद मार्ग, हिल रोड)', (1022, 1023), (36,), '', '', None, None),
    ('SF-J38', 'signal_fault', 'BKC (Bandra Kurla Complex Road)', 'वांद्रे कुर्ला संकुल (बीकेसी मार्ग)', (1052, 1053), (38,), '', '', 'bkc', None),
    ('SF-J39', 'signal_fault', 'Vakola (Western Express Highway)', 'वाकोला (पश्चिम द्रुतगती महामार्ग)', (1014, 1015, 1049), (39,), '', '', None, None),
    ('SF-J40', 'signal_fault', 'Santacruz (SV Road, Juhu Tara Road)', 'सांताक्रूझ (स्वामी विवेकानंद मार्ग, जुहू तारा मार्ग)', (1023, 1024), (40,), '', '', None, None),
    ('SF-J41', 'signal_fault', 'Santacruz (SV Road, Linking Road, Milan Subway road)', 'सांताक्रूझ (स्वामी विवेकानंद मार्ग, लिंकिंग रोड, मिलन सबवे मार्ग)', (1024, 1025, 1027), (41,), '', '', None, None),
    ('SF-J43', 'signal_fault', 'Irla junction (SV Road, for Cooper Hospital)', 'इर्ला जंक्शन (स्वामी विवेकानंद मार्ग, कूपर रुग्णालयाकडे)', (1025, 1026), (43,), '', '', None, None),
    ('SF-J44', 'signal_fault', 'Andheri West (SV Road, Gokhale Bridge)', 'अंधेरी पश्चिम (स्वामी विवेकानंद मार्ग, गोखले पूल)', (1026, 1028), (44,), '', '', None, None),
    ('SF-J45', 'signal_fault', 'Andheri East (Andheri–Kurla Road, Teli Galli)', 'अंधेरी पूर्व (अंधेरी–कुर्ला मार्ग, तेली गल्ली)', (1029, 1031), (45,), '', '', None, None),
    ('SF-J50', 'signal_fault', 'Andheri (Western Express Highway, Andheri–Kurla Road)', 'अंधेरी (पश्चिम द्रुतगती महामार्ग, अंधेरी–कुर्ला मार्ग)', (1016, 1017, 1031, 1032), (50,), '', '', 'weh_andheri', None),
    ('SF-J55', 'signal_fault', 'Powai (JVLR, Saki Vihar Road)', 'पवई (जेव्हीएलआर, साकी विहार मार्ग)', (1034, 1035, 1036), (55,), '', '', 'powai', None),
    ('SF-J56', 'signal_fault', 'Gandhinagar (LBS Marg – JVLR, Powai)', 'गांधीनगर (एलबीएस मार्ग – जेव्हीएलआर, पवई)', (1036, 1037, 1042), (56,), '', '', None, None),
    ('SF-J57', 'signal_fault', 'Vikhroli (EEH – JVLR junction)', 'विक्रोळी (पू. द्रुतगती महामार्ग – जेव्हीएलआर जंक्शन)', (1037, 1048), (57,), '', '', None, None),
    ('SF-J59', 'signal_fault', 'Kurla (LBS Marg, BKC Road)', 'कुर्ला (एलबीएस मार्ग, बीकेसी मार्ग)', (1038, 1039, 1053), (59,), '', '', 'kurla', None),
    ('SF-J61', 'signal_fault', 'Kurla (LBS Marg, SCLR)', 'कुर्ला (एलबीएस मार्ग, सांताक्रूझ–चेंबूर जोड रस्ता)', (1039, 1040, 1051), (61,), '', '', None, None),
    ('SF-J64', 'signal_fault', 'Priyadarshini (EEH – Sion–Panvel Highway)', 'प्रियदर्शिनी (पू. द्रुतगती महामार्ग – सायन–पनवेल महामार्ग)', (1044, 1045, 1054), (64,), '', '', None, None),
    ('SF-J65', 'signal_fault', 'Amar Mahal junction (EEH, SCLR)', 'अमर महल जंक्शन (पू. द्रुतगती महामार्ग, एससीएलआर)', (1045, 1046, 1050), (65,), '', '', None, None),
    ('SF-J68', 'signal_fault', 'Chembur (Sion–Panvel Highway)', 'चेंबूर (सायन–पनवेल महामार्ग)', (1054, 1055), (68,), '', '', 'chembur', None),
    ('SF-J69', 'signal_fault', 'Mankhurd (Sion–Panvel Highway, GMLR)', 'मानखुर्द (सायन–पनवेल महामार्ग, जीएमएलआर)', (1055, 1056), (69,), '', '', None, None),
    ('SF-J70', 'signal_fault', 'Eastern Freeway north end (Chembur, GMLR)', 'पूर्व मुक्त मार्ग उत्तर टोक (चेंबूर, जीएमएलआर)', (1056, 1057, 1059), (70,), '', '', None, None),
    ('SF-J71', 'signal_fault', 'Eastern Freeway south end (P DMello Road, Orange Gate)', 'पूर्व मुक्त मार्ग दक्षिण टोक (पी. डिमेलो मार्ग, ऑरेंज गेट)', (1058, 1060), (71,), '', '', None, None),
)

#: (unit id, beat, connected segment chain)
PATROL_ROWS: tuple[tuple, ...] = (
    ('MTP-EM-LC1', 'Marine Drive–Churchgate–CSMT', (1001, 1004, 1005)),
    ('MTP-EM-LC2', 'WEH (Kalanagar–Andheri)', (1014, 1015, 1016)),
    ('MTP-EM-LC3', 'Dr Ambedkar Road (Byculla–Dadar TT)', (1063, 1064, 1065, 1066)),
    ('MTP-EM-LC4', 'Annie Besant Road (Haji Ali–Worli Naka)', (1075, 1076)),
    ('MTP-EM-LC5', 'SV Road (Bandra–Santacruz)', (1023, 1024)),
    ('MTP-EM-LC6', 'Dr Ambedkar Road (Dadar TT–Sion)', (1067, 1068, 1069)),
    ('MTP-EM-LC7', 'Senapati Bapat Marg (Lower Parel–Mahim)', (1072, 1073)),
    ('MTP-EM-LC8', 'LBS Marg (Kurla–Ghatkopar)', (1039, 1040, 1041)),
    ('MTP-EM-LC9', 'BKC Road (Kalanagar–Kurla)', (1052, 1053)),
    ('MTP-EM-LC10', 'EEH (Sion–Chembur)', (1043, 1044, 1054)),
    ('MTP-EM-LC11', 'Andheri–Kurla Road (Andheri–Saki Naka)', (1031, 1032)),
    ('MP-EM-PCR1', 'Hughes Road–Peddar Road (to Haji Ali)', (1084, 1085)),
    ('MP-EM-PCR2', 'JVLR (Powai–Vikhroli)', (1036, 1037)),
    ('MP-EM-PCR3', 'Mohammed Ali Road–Nagpada', (1061, 1081)),
    ('108-EM-LC1', 'Hindmata–KEM Hospital', (1066, 1070)),
    ('108-EM-LC2', 'Mahim Causeway–Bandra (SV Road)', (1021, 1022)),
    ('108-EM-LC3', 'SV Road (Irla–Andheri)', (1025, 1026)),
    ('108-EM-LC4', 'Nair Hospital–Jacob Circle–Byculla', (1080, 1078)),
)

#: Junctions with a signal program (corridor.signal_programs).
SIGNALISED_JUNCTIONS: frozenset[int] = frozenset({2, 3, 4, 5, 6, 10, 11, 14, 16, 17, 19, 20, 22, 23, 24, 25, 26, 27, 33, 36, 38, 39, 40, 41, 43, 44, 45, 50, 55, 56, 57, 59, 61, 64, 65, 68, 69, 70, 71})

#: The segments the profiles' own causes sit on, by role.
PROFILE_SEGMENTS: dict[str, int] = {
    'dn_road_csmt': 1005,  # Veer Nariman Road - D N Road
    'dr_ambedkar_hindmata': 1066,  # Dr Ambedkar Road (Hindmata - Dadar TT)
    'dr_ambedkar_sion': 1069,  # Dr Ambedkar Road
    'marine_drive_wankhede': 1002,  # Marine Drive
    'sweep_market_road': 1014,  # Western Express Highway
    'weh_vakola': 1015,  # Western Express Highway
}
