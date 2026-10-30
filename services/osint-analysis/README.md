# osint-analysis

Sajag's OSINT analysis library (OS-4): it turns geocoded open-source signals into honest **situations about places,
never persons**. Pure and deterministic: no database, no network except an optional embedder.

```python
from osint_analysis.pipeline import run_pipeline   # (signals, *, resolver, live=None, embedder=None, now=None) -> PipelineResult
from osint_analysis.classify import classify       # classify(signal) -> Classification; never crime_incident
from osint_analysis.embed import HttpEmbedder      # HttpEmbedder(base_url, timeout=3.0); None on any failure
```

The shapes (`RawOsintSignal`, `Geocode`, `Classification`, `ResolvedEvent`, `LiveStateSnapshot`, `PipelineResult`, …)
and the vocabulary (`INCIDENT_CLASSES`, `RELATED_CLASSES`, `RESPONSE_PRIORITY`, …) are `osint_common`'s (X18). The
resolver is injected (`osint_geo.resolver.GazetteerResolver` in production); this package never imports `osint_geo`.

## Stages

| Stage | Module | Rule |
|---|---|---|
| Classify | `classify.py` | The SACHET rule (a CAP alert with a flood word, English, Marathi or Hindi, is `urban_flooding`, else `weather_hazard` with the alert's own event as subtype: `rain`, `thunderstorm`, `cyclone`, `heat`, `fog`, … from `cap_event` or the text, else `weather_advisory`, never "storm" for all); the lexicon in order, first row wins (the Indic rules are under "Marathi and Hindi" below); an English keyword matches a whole word (itself or a regular inflection: `mobs`, `mobbed`, `crashes`, `robberies`; a noun takes a plural only: `concerts`, never "concerted"), the derived words (`protesters`, `looters`, `chain snatchers`, `brawlers`, `marchers`, `gas leakage`, `oil spillage`; never "striker", "mobile", "Protestant", "accidental"), a stem list matching any continuation (`waterlog…`, `inundat…`, `flood…` but not "floodlights", `electrocut…`), and two context rules (the month "by March" is not a march; a "lightning strike" is not a labour strike); optional zero-shot against one exemplar per class (official and news tiers only); else `general_news`. Every rule reads the text without poster handles. A final check raises on `crime_incident` or `vehicle_pursuit`. |
| Stage 1 | `fusion.py` | Per realm × class: DBSCAN (haversine, 900 m) blocks for points, shared `segment_id` for roads (a neighbourhood blocks by its reference point: it has no segment), state areas only with the same state; a 6 h window for point incidents, 48 h for ongoing situations; inside a block, a link needs co-location, the window, and text similarity (embedder cosine ≥ 0.70, else token Jaccard ≥ 0.20). Links are taken strongest first, and none that would put two point reports more than 1.8 km apart in one cluster, or spread its REPORT times over twice its class window (a dense field of similar reports never chains across the city, an accident hotspot never into one day-long situation; a long validity never stops a 4-day warning from joining its re-issue). A district alert cluster then joins AT MOST ONE point cluster inside its district (the most similar, ties to the earliest), or stays its own: an area never merges two point clusters, and never joins a point cluster made only of social posts. The pair tests run as array operations, and a block no bound can split is clustered as plain connected components: 2 000 reports of one procession within 300 m take about 1 s (12.7 s pair by pair). |
| Stage 2 | `correlate.py` | Related classes co-located at the same level (point representatives within 1 200 m or on one road segment; the same district; the same state) and overlapping in time join into one situation, nearest first, never two clusters of one class (a clash report between two accidents joins one of them); primary class by response priority, ties by member count, then the earliest report. Only pairs a vectorised distance filter lets through are tested (the same result as testing every pair). |
| Credibility | `credibility.py` | Base = strongest prior; +0.15 per extra trust type (official, news, social); +0.05 per extra independent publisher within a type, capped at +0.10; independence by registrable publisher domain, never by URL; a single social source ≤ 0.30; ceiling 0.99. Cross-posts are one source: the posts of one community are one source, and two communities are one when a post of one near-duplicates a post of the other (content-token Jaccard ≥ 0.75 of the titles or of the whole texts, or every token of the shorter, at least 3, in the other; cross-post markers and `r/<community>` mentions removed). Syndicated copies are one source too: the same rule across every news tier, so one wire story carried by N outlets is one independent publisher, not N. `SIMULATED` and `EMULATED` pass through, never upgraded. |
| Attach | `attach.py` | Read-only: an ACTIVE live corridor event (`event:` URN) of a compatible kind (an accident ↔ `road_accident`, a crowd ↔ `mass_gathering`, …) within 900 m or on the situation's road segment, overlapping in time, is corroborated; else `novel`. Never a convoy, a `protected_movement` (that is a second-order effect), a `vehicle_pursuit` or a `crime_incident`. Area-level situations and chatter are always novel, and the pipeline checks surfaced situations only (a held social post is never linked to a live event). |
| Second order | `second_order.py` | `protected_corridor` (an active protected movement's route), `convoy` (a convoy in motion on the route or within 900 m), `ambulance_route` (an active ambulance (108) route), `closure` (a segment already closed); notes say "on or near segment N"; surfaced situations only. |

A situation surfaces (`is_event`) only for an incident or operational class, never from a single social post or
from the posts of one social community (one source: they may be one poster), and never when every geocode is
state-level; otherwise it is held with its reason and only counted. An area-level member is never corroboration
of a point-level social report: a district alert or district-level report never joins a point cluster made only
of social posts (it stays its own district situation), and the single-social rules are also applied to a
situation's point-level members, so a SACHET Mumbai alert can never lift one waterlogging post into an
"Official, verified" street event. An independent point-level news or official report of the same situation still
surfaces it.
An area member attached to a point situation is context, never verification: credibility, verification state,
cross-type corroboration, independence, source tiers, labels and the time window (which the live attach and the
second-order checks read) come from the point-level members only. A Dadar news report with a district SACHET alert
attached stays `NEWS-REPORTED` 0.60; `OFFICIAL-VERIFIED` needs an official source reporting the point-level
situation itself. The alert stays a member and a source, listed after the point-level sources with the role
`CONTEXT_ROLE` (`"context"` once OS-1's `SourceRole` has it; `"corroborating"` until then).
`fused_event_id = sha1("anchor:" + earliest member signal_id by (published_at, signal_id))` over the situation's
point-level members when it has any: a district alert that joined a point situation never anchors it, so the id
stays with its place when the alert re-attaches elsewhere in a later cycle. A district or state situation is
anchored on its earliest member.

Two kinds of member can never surface and are therefore held as aggregates rather than deduplicated as incidents:
`general_news` chatter (one aggregate per place and time window) and state-level alerts (one per state and class).

## Ethics in code

- No person field anywhere; `ResolvedEvent`, `SourceRef` and the counts are `osint_common` models (`extra="forbid"`).
- A poster handle is never a cue: `classify.strip_handles` removes Reddit's `submitted by /u/<name> [link]
  [comments]` trailer, any other `/u/<name>`, `u/<name>` or `reddit.com/user/<name>`, and the boilerplate inside
  `normalize_text`, the one text view the classifier, the similarity tokens and the embedder read. Two posts by one
  poster are never more alike than the same posts by two posters.
- Labels, summaries and source titles are fitted to their limits and re-checked with `ethics.find_pii` after the
  clip (a cut can leave the "Dr. <name>" of a protected place "Dr. <name> Road"); the same helper drops a stray
  handle trailer and turns any other handle into `[PERSON]`. No text can fail the output model and sink a batch.
- `SourceRef.url` is kept for official sources only (SACHET/NDMA, IMD, the state SDMA); news and social URLs, whose
  slugs can name a person, are `None` (the source stays verifiable by its `signal_id` and publisher).
- Reported crime comes only from reported text (`reported_crime`, `public_disorder`), never from a camera or image
  path, and never as `crime_incident`.
- `HttpEmbedder` posts only to `/embed` (a read); it never calls `/embed/documents` or `/incidents`, which write to
  the memory store, never follows a redirect and ignores proxy environment variables; one call ends within its
  `deadline` (10 s) however many batches it needs. Today's embedding service has no `/embed` route, so the client
  returns `None` and the pipeline uses lexical similarity.

## Mumbai

Areas are Mumbai's (`fusion.DISTRICT_ENVELOPES`): the city's two districts of `osint_common.kinds.AREA_DISTRICTS`
(Mumbai City and Mumbai Suburban; "mumbai" alone is the whole BMC box of `cities/mumbai/city.json`, 18.89-19.28 N,
72.77-72.99 E) as approximate bounding boxes, not boundaries; the Kolkata pack's four metro districts stay as the
second city pack. An area key reads the resolver's toponym ("Mumbai (district)", GDELT's "Mumbai, Maharashtra,
India") or the connector's code (`LGD:MUMBAI`, `LGD:MUMBAI_SUBURBAN`, `LGD:MAHARASHTRA`, `GDELT_ADM1:IN16`). A
district-level situation without a toponym is labelled "Mumbai district", a state-level one "Maharashtra state".
The sources are those of `osint_common.kinds.SOURCE_NAMES`: `news_rss` (Mumbai outlets' own feeds in Marathi,
English and Hindi), `imd`, `sachet_cap`, Google News, GDELT, Reddit and Common Crawl (the three official page
scrapes keep the Kolkata pack's connector ids). A suburban-rail stoppage ("लोकल सेवा ठप्प", "local train services
suspended") is an `infra_failure` row of its own (`rail_disruption`).

## Marathi and Hindi

Marathi text reaches the classifier AFTER the ingress redaction: every Marathi or Devanagari word that is neither a
gazetteer place nor an ordinary word of `osint_common.ethics.INDIC_COMMON_WORDS` (its Marathi half is
`osint_common.marathi_words`) is `[WITHHELD]` (no Indic NER runs at parse, so an unknown word may be a name). Every
cue word the lexicon relies on is therefore one of those ordinary words, and `tests/test_classify_marathi.py` pins
it. The only cues that match unredacted text alone are words that double as a given name ("अग्नि", "गुल"): they
stay withheld. Bengali is not read any more.

| Marathi (Hindi) | Class (subtype) |
|---|---|
| पाणी साचले / साचला / साचल्याने / तुंबले / तुंबल्याने, साचलेले पाणी, जलमय, पूर, पूरस्थिती, गुडघाभर / कमरेइतके पाणी, मुसळधार / अतिमुसळधार / जोरदार पाऊस, अतिवृष्टी, सखल भाग, भरती … पाणी (जलभराव, जलजमाव, बाढ़, भारी बारिश) | urban_flooding (waterlogging) |
| अपघात; with a vehicle in the clause: धडक, उलटला / उलटली, चिरडले, संघर्ष (दुर्घटना, हादसा, टक्कर) | road_accident (collision) |
| संघर्ष with no vehicle, हाणामारी, मारहाण, दगडफेक, राडा (पथराव, झड़प) | public_conflict (affray) |
| आग / आगीत, अग्नितांडव, अग्निशमन दल, जळून खाक (आग, अग्निकांड) | fire (structure_fire) |
| इमारत / भिंत / स्लॅब / छत / पूल / घर / सज्जा / चाळ … कोसळली / खचला, दरड, रस्ता … खचला, गॅस / वायू गळती, वीजपुरवठा खंडित, जलवाहिनी फुटली (पुल / इमारत … गिरा) | infra_failure (collapse) |
| लोकल / रेल्वे सेवा … ठप्प / विस्कळीत / खोळंबली, ओव्हरहेड वायर, सिग्नल … बिघाड, रुळाला तडा (लोकल / ट्रेन सेवा … ठप) | infra_failure (rail_disruption) |
| झाड / झाडाची / फांदी / वृक्ष … कोसळले / पडले / उन्मळून, झाडपडी (पेड़ … गिरा) | hazard (fallen_tree) |
| विजेचा धक्का, शॉक लागून, विजेची तार … तुटली, उघडी तार (करंट लगने) | hazard (live_wire) |
| रासायनिक … गळती, विषारी वायू, तेलगळती | hazard (spill) |
| गर्दी, जनसागर, जत्रा, मेळा, मेळावा, रॅली (रैली, भीड़, मेला) | public_gathering (mass_gathering) |
| मिरवणूक / मिरवणुका, विसर्जन (in a festival report or at a chowpatty or lake), पालखी, दिंडी, शोभायात्रा, पदयात्रा, पथसंचलन, परेड (जुलूस, रथयात्रा) | procession |
| आंदोलन, आंदोलक, मोर्चा, रास्ता रोको, रेल रोको, धरणे, उपोषण, संप, बंदची हाक, बंद पुकारला, कडकडीत बंद, घेराव, निदर्शने (धरना, चक्का जाम, हड़ताल) | unrest (protest) |
| रस्ता / पूल / मार्ग / सबवे / महामार्ग बंद, वाहतूक … बंद / वळवली, वाहतुकीत बदल, पर्यायी मार्ग, मेट्रोचे / दुरुस्तीचे काम, खोदकाम (रास्ता / सड़क बंद) | road_closure (closure) |
| चक्रीवादळ, वादळ / वादळी, विजांचा कडकडाट, वीज कोसळली, मेघगर्जना, गडगडाट, गारपीट, उष्णतेची लाट, सोसाट्याचा वारा, कमी दाबाचा पट्टा, ऑरेंज / रेड अलर्ट (चक्रवात, आंधी, आकाशीय बिजली) | weather_hazard (storm) |
| दरोडा, लूटमार, लुटले, सोनसाखळी चोरी, बंदुकीचा धाक, दुकान / घर / एटीएम … चोरी / फोडले (लूट, डकैती) | reported_crime (daylight_robbery) |

A Marathi word matches whole (a vowel sign is part of its word: "आग" is never read inside "आगमन", "पूर" never inside
"पूर्व") and with its case endings ("अपघातात", "रस्त्यावर", "पावसामुळे", "मिरवणुकीत"); verb forms are listed, never
guessed ("संप=" takes no ending, so "संपला", it ended, is no strike); a following negation ("नाही", "नाहीत", "नको")
cancels a cue. A traffic jam ("वाहतूक कोंडी", "जाम") is a consequence, as in English: it takes its cause's class
("मिरवणुकीमुळे वाहतूक कोंडी" is a procession) and alone it is `general_news` (congestion comes from the live traffic
feeds). Guards keep ambiguous words honest: "धडक मोर्चा" / "धडक कारवाई" (a march, a swift action: no vehicle),
"दरांना आग" (prices on fire), "आग ओकणारी गोलंदाजी" (a fire-spitting spell), "राजकीय वादळ" / "वादळ उठले" (a
figurative storm), "साचलेल्या पाण्यात डासांच्या अळ्या" (a dengue notice), "वोट लूट" (an electoral claim), "गर्दी
कमी" / "भीड़ कम" (a thin crowd), "विसर्जन" with no festival, "वाहनांची गर्दी" (congestion, not a crowd),
"पावसाने मोर्चा वळवला" (the rain moved on), "कड़ी
टक्कर" (a close contest). A bandh and "closed" are both "बंद": a bandh is read only from its call. A procession or a
rally is classified as the situation on the road, never by who marches or why. The similarity tokens read Marathi
words whole, strip one case ending (and the oblique "ा" before it), read Devanagari digits and number words as
digits, and never count the `[WITHHELD]` token.

## Checks

```bash
cd services/osint-analysis
python -m pytest -q -p no:cacheprovider
```

`tests/test_pipeline_golden.py` is the Kolkata pack's golden (the second city pack, on the committed gazetteer
and road graph, which are still Kolkata's): the Kolkata synthetic fixtures (`osint_common.testing`) and Hindi
reports (two fictional outlets, `news-hi-a.example` and `news-hi-b.example`, as ingress leaves them) through the
real resolver (`osint_geo`): the EM Bypass `affray+collision` on segment 1035, one `urban_flooding` situation at
Thanthania (segment 1058) from the two Hindi reports, the Gariahat robbery at junction 23 as `reported_crime`, the
district SACHET alert at district level, the state-wide nowcasts held as outside the city, the single social posts
held, and Hindi chatter held as `general_news`. A Mumbai golden follows once the Mumbai gazetteer and road graph are
generated into `scripts/data`.

The proof-of-concept parity run (a script and a test that replayed the previous city's proof-of-concept outputs,
read in place) is retired: those outputs are the other city's real captures, so no pipeline of this city can
reproduce them, and keeping the check would have kept that city's places, sources and expected numbers in this
package. The
golden above replaces it; the per-rule tests carry the behaviours the parity run used to pin.

Test fixtures are synthetic (fictional `*.example` publishers, no real names): `tests/analysis_fixtures.py` and
`osint_common.testing`. The Marathi classifier tests read Mumbai headlines and osint-common's synthetic Mumbai test
gazetteer; the fusion, correlation and attach tests still replay the Kolkata pack's geometry (coordinates, segment
and junction ids of the committed Kolkata network, `scripts/data/osm_network.json`, and gazetteer,
`scripts/data/osint_gazetteer.json`) until the Mumbai network is generated.
