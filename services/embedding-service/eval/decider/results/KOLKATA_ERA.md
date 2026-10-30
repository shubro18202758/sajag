# Kolkata-era decider results (not re-measured on the Mumbai set)

Every file in this directory (`*.json`, `*.txt`) was measured on the earlier SIMULATED request set, written
with Kolkata places, on 28-29 Oct 2026, before `../requests.json` was rebuilt for Mumbai. The Mumbai set keeps
the same structure (60 requests; the same kinds and counts, question sets, option orders and expected labels), but
45 request ids that named a Kolkata place were renamed 1:1 (for example `pm-nabanna-airport-zplus` →
`pm-mantralaya-airport-zplus`, `dss-howrah-bridge-breakdown` → `dss-sea-link-breakdown`), and the probe's
corridor option keys changed (`ajc_bose_road` → `coastal_road`, still the light-flow option and still the
expected answer).

Why not re-run: these numbers come from the decider model itself (pplx-decider v1-27b, v1.2 and flash-v1.2),
served by the model host or loaded in-process. Re-measuring needs that model loaded on the shared box, which this
port did not do.

Before trusting a comparison again:

* Re-record the reference answers (`v1-27b-live.json`) on the Mumbai `requests.json` with the live decider.
  `services/model-host/switch_decider.sh` compares a candidate against that reference by request id, so with
  the Kolkata-era file it finds no matching ids for the renamed requests.
* Then re-run `run_eval.py` / `compare.py` for any candidate whose numbers are quoted (`summary.txt`,
  `docs/ai/decider.md`).
