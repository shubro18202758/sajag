# osint-ingress test fixtures: provenance

Plan R13: real captures are read in place, never copied into the repo. Every fixture here is a synthetic replica
of a real feed's schema, with fictional publishers (`*.example`), fictional identifiers and fictional names,
labelled synthetic. The real PoC captures (`.orchestration/osint/prototype/out/`) and live captures are read in
place by the tests that need them (they skip when the directory is absent, as in CI). No real person's name appears
in any fixture; `tests/test_pii_redaction.py` scans every file of this package for the names the redactor replaces
in the real PoC captures, in memory, and reports only SHA-256 prefixes.

| path | provenance | purpose |
|---|---|---|
| `capture/` | 7 **synthetic** files | The sandbox seed, laid out like a PoC raw capture directory. Per-file provenance and the designed outcome in [`capture/README.md`](capture/README.md). |
| `build_synthetic_gdelt.py` | script | Rebuilds the synthetic GDELT export zip and `lastupdate.txt` in `capture/` deterministically; `--check` compares. |
| `heldout_names_mumbai.json`, `heldout_names_mumbai_blind2.json` | **synthetic**, written blind | Held-out recall corpora for the person redactor on Mumbai copy (English, Marathi, Hindi and social items; 50 each; every person invented, places real Mumbai places). Written on 2026-10-30 by a separate agent that read only the city pack's landmarks and city files and never saw the redaction code; scored by `tests/test_heldout_recall.py`, never tuned on. One road spelling was changed after writing (to its official long form, "Swatantryaveer Savarkar Marg"); no label was touched. |
| `heldout_names.json`, `heldout_names_blind.json`, `heldout_names_blind2.json` | **synthetic**, written blind | The second city pack's held-out corpora (Kolkata English, Bengali, Hindi and social items; every person invented), written blind the same way on 2026-10-28; kept as the regression set of that pack's rules. |
| `hostile/xxe.xml` | **synthetic**, hostile | An RSS document with an external entity reading a local file (XXE). `defusedxml` must refuse it. |
| `hostile/billion_laughs.xml` | **synthetic**, hostile | Exponential entity expansion ("billion laughs"). `defusedxml` must refuse it. |
| `hostile/external_dtd.xml` | **synthetic**, hostile | A DOCTYPE that points at a remote DTD. Refused (`forbid_dtd`). |
| `hostile/xxe_atom.rss` | **synthetic**, hostile | An Atom feed with an external parameter entity. Refused. |
| `pages/bmc_home_synthetic.html` | **synthetic** | A municipal portal page replica for the generic notice-link scraper: notice links (kept), paperwork links (tenders, payments: dropped), navigation, script-injected, external, image and mail links (ignored), and a fictional officer name (redacted). |
| `pages/mtp_notices_synthetic.html` | **synthetic** | A replica of the Mumbai Traffic Police public notices table (fictional notice numbers, record ids and file names): three notices (a road closure in the Mulund division, a visarjan arrangement at Girgaon, a parking restriction), one paperwork row (dropped), a commented-out row and a script-held row (never read). |
| `pages/sachet_rss_synthetic.xml` | **synthetic** | A SACHET Maharashtra CAP RSS replica with fictional identifiers (`1999...`): a Mumbai, Mumbai Suburban and Thane alert, a Marathi state-level nowcast (Pune and Satara) signed "मंत्रालय, मुंबई", and another states' coast alert (whose CAP detail is never requested). |
| `pages/cap_detail_synthetic.xml` | **synthetic** | A CAP 1.2 alert replica (fictional identifier, contact and note; the public LGD district codes of Mumbai City 482, Mumbai Suburban 483 and Thane 497), for the CAP-detail parser; its `contact` and `note` must never be read. |
| `pages/imd_rss_synthetic.xml`, `pages/imd_cap_synthetic_000{1,2}.xml` | **synthetic** | The WMO Alert Hub mirror of IMD's CAP feed: an RSS with generic titles, one Mumbai alert, one coastal Karnataka and Goa alert and one link off the mirror (never requested). |

Common Crawl CDX lines and WARC records, robots.txt files, outlet feeds and oracle answers are built inside the
tests.
