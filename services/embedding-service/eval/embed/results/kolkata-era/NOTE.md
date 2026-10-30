# Kolkata-era embedding results

Every file here was measured (27-28 Oct 2026, GB10 GPU) on the earlier SYNTHETIC set written with Kolkata places
and Bengali-script text. The Mumbai set (`../../eval_set.synthetic.json`) keeps the same structure: 53 memory docs
(16 target families, 6 distractors, 12 hard negatives), 52 memory queries, 47 SOP queries and 55 OSINT headlines
in 32 events, with the same languages and gold sizes. One difference does not come from the port: the SOP corpus
is read from `docs/ai/*.md` and the deck's citizen packs when the set is built, and those files have grown since
(120 SOP documents then, 140 now).

These numbers are kept for comparison only. The current results are in `..` (`summary.md`). Candidates that were
not re-measured on the Mumbai set exist only here.
