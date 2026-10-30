# osint-common test fixtures — SYNTHETIC

Everything in this package's fixture kit is a **synthetic replica** (plan R13): the real feeds' structure, written
here, never copied from a capture. It covers the committed JSON files below and the canonical fixtures in
`src/osint_common/testing.py`, which every OSINT work package imports.

## `src/osint_common/testing.py` (the signal and state fixtures)

Mumbai (the city this deployment serves; place spellings as in `cities/mumbai/landmarks.json`; segment and
junction ids are synthetic, no Mumbai road graph is assumed):

| Fixture | What it is | Publisher |
|---|---|---|
| `weh_signals()` | 5 Google News RSS replicas: 4 reports of a multi-vehicle collision on the Western Express Highway near Andheri (synthetic segment 4101) and 1 report of a crowd assaulting the driver at the scene | `news-a.example`, `news-b.example` (fictional) |
| `dadar_robbery_signal()` | 1 Google News RSS replica: a reported robbery near Dadar TT Circle | `news-b.example` (fictional) |
| `social_ghatkopar_signal()` | 1 Reddit replica: a road closed for metro work near Ghatkopar on LBS Marg (a single social source, so it is held) | `social-a.example` (fictional host), community `example_city` (fictional) |
| `sachet_mumbai_signal()` | 1 NDMA SACHET CAP alert for Mumbai district (`LGD:MUMBAI`) | `sachet.ndma.gov.in` (the real public-domain publisher; the alert text is written here) |
| `sachet_maharashtra_signal()` | 1 Maharashtra state-wide SACHET nowcast (`LGD:MAHARASHTRA`) naming other districts (state-level, held) | `sachet.ndma.gov.in` (as above) |
| `live_state_dadar_pursuit()`, `weh_geocode()` | the live corridor state (a vehicle pursuit near Dadar) and one geocode, for the pipeline and attach tests | — |
| `weh_dss()` | the decision-support replica (below) | `news-a.example`, `news-b.example` |

The Kolkata pack (the second city pack) keeps its replicas under their old names (`em_bypass_signals()`,
`gariahat_robbery_signal()`, `social_single_signal()`, `sachet_district_signal()`, `sachet_state_signal()`,
`live_state_sealdah_pursuit()`, `em_bypass_geocode()`), because the oracle, osint-geo and osint-ingress suites still
replay them on the Kolkata road graph (EM Bypass segment 1035, Gariahat crossing junction 23).

- **Fictional publishers only.** Every Google News, GDELT and Reddit replica uses a reserved `*.example` host, so
  no fabricated text is ever attributed to a real outlet or community. The only real publisher is the
  public-domain NDMA SACHET CAP feed, and its alert texts are written here, not copied.
- **No real person's name anywhere.** The names and ages the replicas "had" are already redacted to `[PERSON]` /
  `[AGE]`, exactly as a connector emits them (`pii_redactions` counts them). The test files use invented names
  (for example in `tests/test_ethics.py`) only to prove that detection works.
- **No party, leader or election-symbol name anywhere.** The scope gate's party and symbol sets are hashes; the
  tests prove them with fictional names added at test time (`tests/test_scope.py`).
- `tests/test_types.py` (`test_fixtures_are_deterministic_and_synthetic`, both packs) asserts every publisher is
  `*.example` or SACHET and every URL is on a `*.example` host.

## `dss_weh.synthetic.json` (the decision-support fixture)

`dss_weh.synthetic.json` is `osint_common.testing.weh_dss()` dumped as JSON (`tests/test_dss_shapes.py` pins the
two equal; regenerate it with
`PYTHONPATH=src python -c "import json; from osint_common import testing; print(json.dumps(testing.weh_dss().model_dump(mode='json'), indent=2, ensure_ascii=False))" > tests/fixtures/dss_weh.synthetic.json`).
It is a **synthetic replica** with the structure of the proof-of-concept `dss_output.json` (here the Western
Express Highway `affray+collision` situation near Andheri at synthetic segment 4101) plus the C-U fields (`state`,
`seed`, `horizon_min`, `strategy_prior`, `provenance.wargame_method`, `human_gate`):

- the publishers are fictional (`news-a.example`, `news-b.example`); no real person's name appears anywhere,
  and the member reports' names and ages are already `[PERSON]` / `[AGE]`;
- the numbers (AHP weights, TOPSIS closeness, EVOI, feasibility) mirror the PoC run so the shape is realistic;
  they are not Mumbai measurements;
- it is labelled `SIMULATED` (its predicted outcomes are simulations) and `NEWS-REPORTED` (no official source).

## `mumbai_gazetteer.synthetic.json` (the ethics tests' place list)

A small Mumbai place list in the schema of `scripts/data/osint_gazetteer.json` (canonical names and English,
Marathi and Hindi surface forms, no coordinates). `tests/conftest.py` points `OSINT_GAZETTEER_PATH` at it, so the
place-protection tests read the same places whatever the generated repo gazetteer holds; the two tests about the
repo gazetteer itself clear the variable.

## The real proof-of-concept outputs

The real PoC outputs are never copied here: `tests/poc_parity.py` and `tests/test_poc_parity.py` read them in
place (`$OSINT_POC_DIR`, else the orchestration PoC directory) and skip when they are absent.
