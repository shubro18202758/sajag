# Decision-support test fixtures (OS-6) — SYNTHETIC

Both JSON files are **synthetic replicas** (plan R13, ethics rule 9). They carry no real person, no real
publisher and no real URL; the publishers are fictional (`news-a.example`, `news-b.example`) or the public-domain
official channel (`sachet.ndma.gov.in`), and the titles are written for these tests.

| File | What it is |
|---|---|
| `sector_v_dss_input.json` | The structure of the PoC's `out/dss_input.json`: the correlated `affray+collision` situation at segment 1045 (Sector V - New Town link, at Sector V, Salt Lake), credibility 0.65 `NEWS-REPORTED`, two independent fictional publishers, one source tier, an injury cue. Alongside it, what the PoC hard-coded: its arterial model (`segment_model`, the three-lane reference carriageway), the junction a signal hold uses, the advisory's place, the unit availability (ambulance 1 free, police 1 free — the second patrol is committed elsewhere) and the seed `20261024`. |
| `area_subject.json` | A district-level subject with **no road anchor** (no segment, no junction): an official district weather alert replica. Every dispatch, closure, diversion and signal-hold COA must be infeasible up front with the shortfall `no road anchor: area-level report`; the baseline, minimal and information COAs stay feasible. |
| `fakedss.py` | The offline backend of the DSS tests: the OS-5 fake store extended with the 022 tables, the dispatch channel, a small SYNTHETIC directed road graph around segment 1045 (pgRouting answered in Python; its other ids and its Salt Lake / New Town road names are local to the fake), a fake unit feed (`units:emulated:*`), and the `dss_backend` context that swaps in the int3c sandbox when `OSINT_TEST_DSN` is set. |

The engine's structure tests (`test_dss_generate.py`, `test_dss_mcda.py`, …) read only these files. The real PoC
files (`.sajag-orchestration/osint/prototype/out/`) are never copied into the repository: `test_dss_poc_parity.py`
reads them **in place**, and only when `OSINT_POC_DIR` points at them.
