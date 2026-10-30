# osint-ingress (:8193)

Turns open sources into canonical, already-redacted `RawOsintSignal` records (`osint_common.types`, contract
X18) and posts them to the oracle's loopback machine-ingest route `POST /api/v1/osint/signals` (contract C-T).
Events are about places and situations, never persons.

## Run

```bash
PYTHONPATH=src:../osint-common/src:../osint-geo/src:../osint-analysis/src python -m osint_ingress serve
python -m osint_ingress once [--offline] [--cache-dir D] [--oracle URL] [--dry-run] [--report out.json] [--backfill] [--only a,b]
python -m osint_ingress import-poc <capture_dir> <cache_dir>
```

Exit codes: 0 ok, 2 usage (a non-loopback oracle URL or an unknown `--only` connector included; caught before
anything is built or probed), 3 pipeline libraries missing (`--dry-run`).
`once` probes the oracle first; when it is unreachable nothing is posted, the batches stay in the cache outbox,
the report says `publish: "skipped: oracle unreachable"` and the exit code is 0. `--dry-run` runs
`osint_analysis.pipeline.run_pipeline` with the `osint_geo` resolver in-process and prints `MACHINE_RESULT={...}`.

Environment: `OSINT_ORACLE_URL` (loopback only; unset: `http://127.0.0.1:9`, the discard port), `HOST` (`127.0.0.1`), `PORT` (`8193`),
`OSINT_CACHE_DIR` (`/var/cache/osint-ingress`), `OSINT_MODE` (`live` | `offline`), `OSINT_GAZETTEER_PATH`, `SAJAG_CITY` (the city pack whose place names the redactor protects; default `mumbai`),
`OSINT_CADENCE_<CONNECTOR>_SEC` (0 takes a connector off the schedule; values under 60 s are raised to 60 s).
The service reads no secret and writes nothing but its cache. `OSINT_ORACLE_URL` has no usable default: unset, it is
the discard port `:9`, so a run that names no oracle posts nowhere (its batches wait in the outbox) and never
reaches the live oracle by accident. The deployment names its oracle explicitly; a harness names a sandbox oracle.

## Routes

- `GET /health`: `{status, mode, version, oracle{host, reachable, last_post_at, last_post_status},
  connectors{<name>{enabled, cadence_sec, last_run_at, last_ok_at, fetch_mode, signals, error, cache_age_sec}},
  last_cycle{at, signals, accepted, rejected, geotagged, surfaced, pii_redactions}, egress_allowlist}`.
  `oracle.reachable` comes only from a `GET {oracle}/health` probe (start-up, then every 30 s). A connector its
  source disables ("robots.txt disallows") shows `enabled: false` with that `error`, and its cache is not served.
- `POST /cycle` (loopback callers only): one cycle now; returns the `last_cycle` object.

## Connectors and schedule

| source | cadence | endpoint |
|---|---|---|
| `sachet_cap` | 5 min | NDMA SACHET **Maharashtra** CAP RSS (`rss_maharashtra.xml`), area-matched to the Mumbai districts (below), plus the CAP 1.2 detail of new alerts of the state |
| `imd` | 10 min | IMD's CAP alerts via the WMO Alert Hub mirror (`cap-sources.s3.amazonaws.com/in-imd-en/`), all India, kept to Maharashtra |
| `google_news_rss` | 10 min | Google News RSS search: English (`hl=en-IN`), Marathi (`hl=mr`) and Hindi (`hl=hi`) Mumbai civic queries (waterlogging, local trains, traffic, accidents, fires, tree falls; pointer layer, never redistributed) |
| `news_rss` | 15 min | the outlets' own RSS feeds (Mumbai sections; English, Marathi and Hindi; pointer layer, never redistributed; robots.txt honoured per feed) |
| `gdelt_events` | 15 min | GDELT 2.1 `lastupdate.txt` and only the export zip it names (Greater Mumbai bbox, ADM1 `IN16`). The CDN at `data.gdeltproject.org` caches a 404 for an hour when someone asks for a file before its upload, so a 404 for the named export is retried once from GDELT's own bucket (`storage.googleapis.com/data.gdeltproject.org/gdeltv2/<stamp>.export.CSV.zip`, same MD5 check) |
| `gdelt_doc` | 30 min | GDELT DOC 2.0 ArtList, `(Mumbai OR Bombay) sourcecountry:IN` (≥ 5 s between requests). A 429, the throttle banner or a 60 s timeout backs it off: `Retry-After` honoured, else jittered exponential from the cadence, at most 2 h; no request meanwhile, and the last live answer is served with its real fetch time and age |
| `reddit_rss` | 15 min | r/mumbai newest-posts Atom feed (aggregate social signal only; the committed synthetic capture uses the fictional `r/example_city`) |
| `mumbai_police_scrape` | hourly | **Mumbai Traffic Police public notices** (`mtperp.mahatrafficechallan.gov.in/PublicNotice.htm`, linked as "अधिसूचना" from `trafficpolicemumbai.maharashtra.gov.in`): one signal per notice row (closures, diversions, parking restrictions, festival arrangements), the traffic division read from the notification's file name. The source id keeps the contract's name for the city traffic-police connector |
| `kmc_scrape` | off | disabled: the city civic body's portal (`portal.mcgm.gov.in`) is script-driven with no notice list in its HTML, and BMC's 1916 disaster control publishes no feed; not allow-listed |
| `wbsdma` | off | disabled: Maharashtra SDMA's alerts already arrive through SACHET (sender `Maharashtra-SDMA`); `sdma.maharashtra.gov.in` lists guidelines and orders, not live alerts; not allow-listed |
| `common_crawl` | never | backfill only (`once --backfill`; TOI Mumbai archive, `timesofindia.indiatimes.com/city/mumbai/*`) |

### Sources (checked 2026-10-30 from this box, one GET each, with the service's user agent)

`sajag-osint-ingress/<version> (Sajag corridor operations, Mumbai; open-source civic research)`, never a
browser user agent and never a bot-check workaround. A source that refuses is excluded, not worked around. Items are
the feed's item count on 2026-10-30; "kept" is what the connector kept in one live pass of the real code that day.

| outlet / office | URL | language | answer 2026-10-30 | kept |
|---|---|---|---|---|
| Times of India, Mumbai | `https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms` | en | 200, 20 items | yes (`news_rss`, 20) |
| Hindustan Times, Mumbai | `https://www.hindustantimes.com/feeds/rss/cities/mumbai-news/rssfeed.xml` | en | 200, 49 items | yes (`/cities/mumbai-news/` only, 47) |
| Mid-day, Mumbai | `https://www.mid-day.com/Resources/midday/rss/mumbai-news.xml` | en | 200, 30 items | yes (30) |
| Indian Express, Mumbai | `https://indianexpress.com/section/cities/mumbai/feed/` | en | 200, 200 items | yes (200) |
| The Hindu, Mumbai | `https://www.thehindu.com/news/cities/mumbai/feeder/default.rss` | en | 200, 60 items | yes (`/news/cities/mumbai/` only, 24) |
| Free Press Journal (whole site) | `https://www.freepressjournal.in/stories.rss` | en | 200, 109 items (a `?section=mumbai` query is ignored: 110) | yes (`/mumbai/` only, 5) |
| Maharashtra Times, Mumbai | `https://maharashtratimes.com/maharashtra/mumbai-news/rssfeed/2429656.xml` (the short `/rssfeed/2429656.xml` redirects here) | mr | 200, 50 items | yes (50) |
| ABP Majha, Mumbai | `https://marathi.abplive.com/news/mumbai/feed` | mr | 200, 10 items | yes (`/news/mumbai/` only, 3) |
| TV9 Marathi, Mumbai | `https://www.tv9marathi.com/mumbai/feed` | mr | 200, 59 items | yes (`/maharashtra/mumbai/` only, 6) |
| ABP Live (Hindi), Maharashtra | `https://www.abplive.com/states/maharashtra/feed` | hi | 200, 10 items | yes (items naming Mumbai only, 2) |
| TV9 Bharatvarsh (Hindi), Maharashtra | `https://www.tv9hindi.com/state/maharashtra/feed` | hi | 200, 30 items | yes (items naming Mumbai only, 3) |
| Google News search, English / Marathi / Hindi | `news.google.com/rss/search?…&hl=en-IN` / `hl=mr` / `hl=hi` | en, mr, hi | 200 each | yes (`google_news_rss`: 92 + 50 + 47 signals) |
| Reddit r/mumbai | `https://www.reddit.com/r/mumbai/new/.rss` | en | 429 at 14:46 IST, 200 (25 posts) at 15:20 | yes (`reddit_rss`; a refusal serves the cache) |
| NDMA SACHET, Maharashtra | `https://sachet.ndma.gov.in/cap_public_website/rss/rss_maharashtra.xml` | en, mr | 200, 10 items (6 days; one names Mumbai and Mumbai Suburban, LGD 482/483) | yes (`sachet_cap`, 10) |
| NDMA SACHET, all India | `https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml` | en, mr, … | 200, 100 items (about one day, every state) | no: the Maharashtra file holds the same alerts over a longer window |
| IMD CAP (WMO Alert Hub mirror) | `https://cap-sources.s3.amazonaws.com/in-imd-en/rss.xml` | en | 200, live and empty (0 items) | yes (`imd`) |
| Mumbai Traffic Police public notices | `https://mtperp.mahatrafficechallan.gov.in/PublicNotice.htm` | en | 200, 50 rows; robots.txt 404 (no restriction) | yes (`mumbai_police_scrape`, 49: one payment row is paperwork) |
| Mumbai Traffic Police site | `https://trafficpolicemumbai.maharashtra.gov.in/` | mr | 200; its notices page (`सूचना`) lists awards and RTI documents, its notifications link points to the portal above | no (the portal above is read) |
| Maharashtra SDMA | `https://sdma.maharashtra.gov.in/` | mr | 200; guidelines and orders; its alerts reach SACHET | no: `wbsdma` disabled |
| BMC portal | `https://portal.mcgm.gov.in/` | en | 302 to a script-driven page; robots.txt 404 | no: `kmc_scrape` disabled |
| Loksatta | `https://www.loksatta.com/mumbai/feed/`, `/feed/` | mr | 301 to the HTML section page (feeds switched off) | **excluded** |
| Lokmat | `https://www.lokmat.com/rss/`, `/rss/mumbai/` | mr | 403; `/rss-feeds/` redirects to the home page; `/mumbai/` timed out | **excluded** |
| Lokmat Times | `https://www.lokmattimes.com/rss/mumbai/` | en | 500 | **excluded** |
| Navbharat Times, Mumbai | `…/metro/mumbai/rssfeed/5722181.xml`, `…/state/maharashtra/mumbai/rssfeed/21239273.xml` (from its own RSS page), `rssfeedsection/` and `rssfeeds/` forms | hi | 404 (a Delhi feed from the same page: 404 too) | **excluded** |
| News18 Lokmat, Mumbai | `https://lokmat.news18.com/rss/mumbai.xml` | mr | redirects to a 404 page | **excluded** |
| Maharashtra Times, weather | `https://maharashtratimes.com/rssfeed/119111859.xml` | mr | 200, 5 items, none since July | **excluded** (stale) |
| Mid-day, alternative path | `https://www.mid-day.com/rss/mumbai-news.xml` | en | 404 | not needed (the `Resources` path answers) |

### Maharashtra and Mumbai filtering

SACHET's Maharashtra file carries every district's nowcasts and IMD's feed covers every state, so
`connectors/_area.py` reads each alert's own text (title, description, and the CAP headline, `areaDesc` and LGD
district codes when the detail is cached), after NFKC, with Devanagari digits as ASCII:

- naming a Mumbai district: `LGD:MUMBAI` (Mumbai City: "Mumbai", "Mumbai City", "मुंबई", "मुंबई शहर", LGD 482) and/or
  `LGD:MUMBAI_SUBURBAN` ("Mumbai Suburban", "मुंबई उपनगर", LGD 483); "Greater Mumbai" / "बृहन्मुंबई" names both;
  hints `area:mumbai`, `area:mumbai_suburban`. "Navi Mumbai" (नवी मुंबई) is never Mumbai;
- naming Maharashtra, a region (Konkan, Vidarbha, Marathwada, Madhya Maharashtra) or any other of its districts only
  (Thane, Palghar, Raigad, Pune … with Marathi oblique stems such as "ठाण्या-"): the state, `LGD:MAHARASHTRA`, hint
  `area:maharashtra`; the analysis holds it as outside the city;
- an item of the Maharashtra file naming no place at all ("आपल्या जिल्ह्यात", in your district) is the state, by the
  feed it came from; naming only another state (Goa, Karnataka …): not emitted, counted `outside_area`.

**The SDMA's sign-off is never the area.** Maharashtra SDMA ends every Marathi nowcast "मंत्रालय, मुंबई" (its office at
Mantralaya), whatever district it is for; it is cut before matching, so a Kolhapur nowcast stays state-level. When the
cached CAP detail carries an English headline (SACHET sends an English `<info>` beside the Marathi one), that headline
is the signal's title ("Light Rain is very likely to occur at isolated places over Mumbai, Mumbai Suburban in next 3
hours", language `en`).

The codes come from `osint_common.kinds` (`CITY_DISTRICTS`, `AREA_STATE_CODE_MAHARASHTRA`,
`GDELT_ADM1_MAHARASHTRA`). GDELT keeps a row inside the Greater Mumbai bbox of `cities/mumbai/city.json`
(18.89–19.28 N, 72.77–72.99 E), or with ADM1 `IN16`, or whose FullName names Mumbai or Bombay (GDELT's spelling),
never Navi Mumbai. `news_rss` keeps a whole-site feed to its Mumbai sections (`outside_section`), a Maharashtra-wide
Hindi feed to the items that name Mumbai (`outside_city`), and drops items linking off the outlet's site
(`foreign_link`); an item in a Mumbai section carries `area:mumbai`, one in a Maharashtra section `area:maharashtra`.

**Language.** Marathi and Hindi share Devanagari, so `base.script_language` decides by words: Marathi-only words and
endings (आहे, नाही, मध्ये, आणि, झाले, "-च्या", "-ांनी") and the letter "ळ" against Hindi function words (है, में,
और, नहीं, के); a tie follows the feed's language. Bengali script (the second city pack) is `bn`.

Each connector separates `fetch()` (raw bytes into the cache) from `parse()` (cache to signals). Offline mode, and
a failed live fetch, parse the newest cache entry and label the signals `cached-sample`, with `fetched_at` set to
the capture time. Retention: 72 h or 200 MB, whichever comes first; the newest entry of each connector is kept.
The cache root is created `0700` (files `0600`). A CAP `<expires>` days ahead is kept as `valid_until` (up to
31 days ahead); a publication time more than a day ahead is treated as unknown.

## Ethics rails in this service

- Names and ages are redacted at parse (`[PERSON]`, `[AGE]`; social contacts `[CONTACT]`); the result always passes
  `osint_common.ethics.find_pii`, which proves only that none of ITS patterns survived: it is the same pattern
  family the redactor uses, so it cannot see what they miss. **What the redactor does not promise**: no NER runs at
  parse, so a name with no cue, no known surname and no role noun, a single given name after an unlisted verb, or
  an ALL-CAPS headline can survive. The honest figure is the held-out recall (`tests/test_heldout_recall.py`): two
  **Mumbai** corpora of invented names (50 cases each; English, Marathi, Hindi and social) written blind on
  2026-10-30 by a separate agent that never saw the code, before the Mumbai rules; scored once after them, never
  tuned on: Latin name-word recall 0.958 / 0.878 (0.845 / 0.829 before the Mumbai rules), Indic 1.0 / 1.0, age
  markers 0.925 / 0.958, keep 0.731 / 0.703. The keep losses are mostly Marathi place and ordinary words that the
  shared lexicon and gazetteer do not hold yet (`[WITHHELD]`), and places after "Dr" until the shared gazetteer holds
  them. The second city pack's three blind corpora stay as a regression set. Known misses: ALL-CAPS headlines,
  cue-less names with an unlisted surname, a joined "-ji" (left unread: Shivaji, Sambhaji and Tanaji name Mumbai's
  parks, terminus and roads), "s/o" forms, initials without full stops, single given names in posts.
  Cue-less names are read through role and kin nouns ("Biker <Given> <Surname>", "husband <Given> <Surname>"), a
  common-surname list (Maharashtrian: Patil, Deshmukh, Jadhav, Pawar, Shinde, Kulkarni, Joshi, Gaikwad, Chavan,
  More …; Gujarati, East Indian and Goan, North Indian; "<Given> <Surname>": a surname alone, "Patil family", stays),
  honorific suffixes ("<Given>rao", "<Given>bhau", "<Given>-ji", "<Given>bhai"), address terms written apart
  ("<Name> saheb", "<Name> tai", "<Name> ji"), Marathi honorifics and Mumbai Police ranks ("Sau.", "Ku.", "Adv.",
  "PSI", "API", "PI", "ACP", "Hawaldar"), both sides of "alias"/"@", "<Given>, a <role>," and "<Name>'s
  body/family"; a surname written alone after a learned name in the same feed document ("<Surname> taught there")
  goes too.
- **Indic script**: a Marathi or Hindi (Devanagari) word that is neither a gazetteer place nor an ordinary word
  (`osint_common.ethics`) is withheld as `[WITHHELD]` in every tier (no Indic NER yet). Marathi and Hindi cues
  read names even when they are ordinary words: after an honorific (श्री, श्रीमती, सौ., कु., डॉ., प्रा., ॲड.; Hindi
  सुश्री) the next words are a name, unless a place noun follows them ("डॉ. आंबेडकर मार्ग" is a road); after a role
  cue (आरोपी, मृताचे नाव, जखमी, रहिवासी, रिक्षाचालक; मृतक, पीड़ित) the unknown words are a name; the word before an
  address term (साहेब, भाऊ, ताई, दादा, जी, शेठ) and a word with one written onto it ("शंकरराव", "<name>जी",
  "<name>बाई") are a name, unless the word is an ordinary word or a place ("तिचा भाऊ", her brother). Marathi and
  Hindi ages become `[AGE]`: "३५ वर्षीय", "४२ वर्षांचा", "वय ६०", "<name> (६०)", "<name>, ४५,", "28 वर्षीय",
  "45 साल के", "उम्र 60" (Devanagari or Western digits). A Marathi or Hindi outlet's English search keyword before a
  Devanagari headline ("<Keyword>: <headline>", often a person's name) is cut. The second city pack's Bengali cues
  and ages stay.
- A social post's age and sex shorthand ("F(28)", "22M", "27/F") is `[AGE]` (a bare "15M" in a post is redacted
  too: accepted over-redaction). Beyond the shared cue patterns, a cue-introduced name runs on over a 4th,
  initialled or hyphenated name word; "the victim, <Name>,", "the deceased as <Name>", "Mr.<Name>" and Title-Case
  "Accused <Name> <Name> Held" are read; and the name right before an age ("<Name>, [AGE]," / "<Name> ([AGE])")
  is redacted. A Reddit user mention or page (`u/<name>`, `/u/<name>`, `/user/<name>`, `r/u_<name>`,
  `reddit.com/u/<name>`) becomes `[PERSON]` in every tier, news, GDELT and official included. Social posts are
  redacted most aggressively: `@<name>` and "insta: <handle>" mentions too (in news an `@`-account, usually an
  outlet's or an office's, is kept), and every capitalised run (initials such as "K." included) that no
  gazetteer phrase covers and that is not a generic word (a place noun such as "Road" never vouches for the name
  before it).
- **Places named after people** (Mumbai has many: "Senapati Bapat Marg", "Bhulabhai Desai Road", "Lokmanya Tilak
  Terminus", "Acharya Atre Chowk", "Shivaji Park", "P D'Mello Road") survive only when the protect-set holds the
  whole phrase; otherwise the surname rule reads "<Given> <Surname>" and the place loses its name. The protect-set is
  the shared gazetteer plus the city pack (`cities/mumbai/landmarks.json`, and `gazetteer.json` once it lands: `en`
  names and `aka` aliases; `SAJAG_CITY`, default `mumbai`) plus `_protect.MUMBAI_EPONYMOUS_PLACES`. The contract's own
  check (`ethics.find_pii`, run again at validation and by the oracle) reads the shared gazetteer only, so a city-pack
  place it does not hold yet after a residence cue or an honorific ("resident of Dadar", "Dr. Ambedkar Road") is
  redacted by a last pass rather than letting validation refuse the whole signal; it survives once
  `scripts/data/osint_gazetteer.json` is regenerated for Mumbai.
- **Bylines are never read**: `news_rss` reads an item's title, link, guid, date, description and category only
  (never `dc:creator`, `author` or `content:encoded`); Google News keeps only the outlet's domain.
- Every URL written in a news or social title or text is redacted (a slug or a profile path can name a person):
  a Reddit user page becomes `[PERSON]`, any other URL `[URL]`. `pii_redactions` counts every replacement
  (`[PERSON]`, `[AGE]`, `[CONTACT]`, `[URL]`).
- Reddit poster blocks are never read, and the "submitted by" footer is cut; GDELT actor and person columns are
  never read; court-record portals (case captions name the parties) are dropped; the Google News display name
  (free text, maybe a blog's owner) is cut from titles and descriptions, and only the outlet's domain is kept.
- News- and social-tier URLs are never emitted, stored or logged: the signal keeps the outlet's domain and a
  `url_sha256:` hint of the canonical URL. Official sources keep their identifier URLs.
- `raw` is a scalar whitelist (`RAW_ALLOWED_KEYS`), never the source record.
- Egress goes only to an allow-list of exact hosts over https, with redirects checked hop by hop (plus
  `storage.googleapis.com` for one path shape only: a GDELT 2.0 export zip in GDELT's bucket, no query); the
  oracle is loopback only; every XML, RSS, CAP and Atom document is parsed with `defusedxml`.

## Optional model check at parse (PII-Tracer)

OFF by default. The rules above stay primary; a learned detector can be consulted as defence in depth and can only
ADD redactions (`src/osint_ingress/connectors/_model_pii.py`).

| variable | default | meaning |
|---|---|---|
| `OSINT_PII_MODEL` | unset (off) | `1` / `true` / `yes` / `on` turns the check on |
| `OSINT_PII_URL` | unset | the embedding service's base URL; loopback only (`127.0.0.1`, `localhost`, `::1`), no path |
| `OSINT_PII_TIMEOUT_SEC` | `3` | per request (clamped to 0.2–10 s; connect 0.5 s) |
| `OSINT_PII_COOLDOWN_SEC` | `60` | after a failure, the model is not asked again for this long |

- One `POST <OSINT_PII_URL>/pii/spans` per feed document (`{"texts": [...]}` → `{"spans": [[{start, end, label}]]}`),
  with the titles and texts already bounded (500 / 2000 characters). `private_person` → `[PERSON]`;
  `private_email` / `private_phone` → `[CONTACT]` in every tier but `official`; other labels are ignored. The spans
  join the rules' first pass, so the result still passes `osint_common.ethics.find_pii`.
- A model span never redacts a protected place: the embedding service drops spans on Mumbai place names, and this
  side clips every span again against the protect-set phrases, the gazetteer's Marathi and Devanagari spellings and
  runs of name words ending in a place word ("Senapati Bapat Marg", "Acharya Atre Chowk", "आचार्य अत्रे चौकात").
- Fail-open to the rules: a refused URL, connection error, timeout, redirect, non-200, oversized or malformed answer
  means the document is redacted by the rules alone, and a `pii_model` log event records the outcome (counts only,
  never a text or a name). The client never reads proxy settings from the environment (`trust_env=False`) and never
  follows a redirect. `parse()` is synchronous, so a call blocks it for at most the timeout.
- Measured earlier on the second city pack's SYNTHETIC set (120 sentences, kept under
  `services/embedding-service/eval/pii/`): person recall of the news-tier rules 0.84 → 0.94 with the model added, no
  protected place, office title or emergency number newly redacted; in Indic script the model was weaker (person F1
  about 0.7), so the `[WITHHELD]` rule stays. Not yet re-measured on Mumbai copy.

## Tests

`pytest` here; `tests/fixtures/README.md` gives the provenance of every fixture. `tests/fixtures/capture/` is the
synthetic sandbox seed (import-compatible; every file synthetic, its designed outcome in its README). Tests that read
the real PoC captures in place (absent in CI: skipped) use them for city-independent shape only: a real GDELT
export (global, so it can hold Mumbai rows), the real SACHET file of another state, a real
Reddit capture (no poster reaches a signal), and the PoC-name scan.
