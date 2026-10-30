# The decider (strategic tier, `services/model-host`)

The brain's strategic tier asks a decider model **typed questions** (a choice among options, a probability, a
score) about the live state of a movement or an event, never free text. In Mumbai the questions are of this
kind: which course of action for a visarjan crowd building at Girgaon Chowpatty; how likely a protected
movement from Mantralaya to Airport T2 is to meet a waterlogged stretch at Kalanagar; how urgent an unverified
flooding report at Milan Subway is; which map tool to use first. Its answers are proposals: a named
officer approves every action, and the brain holds the current plan when no one answers.

Service: model-host on `127.0.0.1:8083` (`sajag-decider.service`), `POST /decide`.

## What is deployed (29 Oct 2026)

| | |
|---|---|
| Model | `perplexity-ai/pplx-decider-v1.2` (rev `cce0f3f`), a fine-tune of Qwen3.8-27B, Apache-2.0 |
| Weights | 48.6 GiB BF16, sha256-verified against the release manifest; 48.7 GiB of GPU memory resident |
| Protocol | v3 joint: one sequence holds the state and every question of a request, one readout per question (the card's recommendation for the 27B) |
| Calibration | the checkpoint's own temperature from `decision_config.json`, never overridden |
| Previous model | `pplx-decider-v1-27b` (protocol v1), kept in the cache; `switch_decider.sh rollback` returns to it in about 4 minutes |

## How it was switched

`services/model-host/switch_decider.sh` downloads the pinned snapshot, checks every file's sha256, runs a
preflight (code merged, unit reads `~/.config/sajag/decider.env`, enough memory), writes `decider.env`,
restarts the unit, waits for the load, warms it, and then replays the saved request set against the saved answers
of the previous model (`check`). The strategic tier was down only for the load; the brain served from Gemma and its
heuristic floor in the meantime and reconnected by itself.

## Check against the previous model (29 Oct 2026, 01:27 IST, live box)

The saved request set: 134 questions (59 choice, 35 probability, 40 score) from the scenarios of the **Kolkata
reference pack**, where the platform was first built (DSS courses of action, protected-movement checkpoints, escort
incidents, tool selection), 26 of them with a labelled right answer, sent over HTTP to the live service. The
check compares two models on the same questions; it is not a Mumbai result. The same check on a request set built
from the Mumbai scenarios: not yet re-run on the Mumbai scenarios.
Raw results: [`services/embedding-service/eval/decider/results/post-switch-20261029-0127.json`](../../services/embedding-service/eval/decider/results/post-switch-20261029-0127.json).

| | pplx-decider-v1-27b (before) | **pplx-decider-v1.2 (now)** |
|---|---|---|
| Labelled answers right | 23 / 26 | 22 / 26 |
| Wall time p50 / p95 | 1,292 / 2,098 ms | **739 / 1,048 ms** |
| Share below the brain's 0.45 confidence floor (held back for an officer) | 0.60 | 0.43 |
| Choice agreement with the previous model | — | 0.83 (tool selection 0.93) |

- **Where they differ on labelled cases.** v1.2 now gets a festival-night crowd at a busy crossing right (an
  aggressive course of action); it misses two that v1-27b got: a highlight tool for a named place (it chose a
  bounding-box query first) and an unverified flooding report (it chose the baseline over "gather
  information"). Both still miss a stadium egress and a neighbourhood fire, where the label is the aggressive course of
  action. In Mumbai the same kinds of case are a visarjan crowd at Girgaon Chowpatty, a flooded Hindmata, an
  unverified report at Milan Subway, Wankhede egress and a shop fire at Chembur.
- **Scale shifts to know about.** v1.2 rates its own tool-selection confidence much higher (mean 0.94 against
  0.44) and puts a lower probability on pre-movement urgency (0.38 against 0.54). The brain's floor (0.45) was
  kept; fewer answers are held back, and every action still needs an officer.
- **Verdict of the check script:** PASS (no errors, p95 below the brain's 3,000 ms degrade line, labelled
  accuracy within one of the reference).

## The smaller model that was not chosen

`pplx-decider-flash-v1.2` (4B, 8.9 GiB) is far faster (p95 0.1–0.4 s) and scores 22–23/26, but agrees with the
27B on only 76 % of the choice questions, and reading the disagreements showed weaker escort decisions. It stays
available (`switch_decider.sh switch flash`) for a box with less memory.
