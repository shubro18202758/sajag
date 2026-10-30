# Workspace selector fixture

`captured.json` is the fixture of `tests/workspace.unit.mjs` (the canonical selectors, the object graph, the
display layer and the omnibar search are reconciled against it). It is committed so the test runs in CI, where the
redesign prototype does not exist.

## What it is

It is derived from the redesign prototype's capture (`redesign/prototype/data/live-data.js`, `window.SAJAG_DATA`):
read-only GETs of an **emulated** scenario, with registration marks masked at capture. It is reduced to what the
selector tests read:

- the watchlisted vehicle `MH47EM•••1` and every object linked to it: its snapshot row, its dossier (50 related
  objects) and the one other dossier that links a 51st object (a read) to it. That gives **51 linked objects**: 21
  reads, 6 cameras, 22 recommendations and 2 pursuits;
- the city feed of the six hours before the capture (189 rows, 19 of them watchlist reads). Rows about the vehicle
  and its linked objects keep their text; the other rows keep only what the selectors read (time, kind, URNs, actor
  kind, source);
- a dossier audit entry written as a string is the id of the feed row that carries it in full.

## Ethics

- **Marks stay masked.** Only `plate_masked` and masked labels (`MH47EM•••1`) appear; the `plate` field is dropped
  everywhere, so no raw-mark field survives.
- **No person's name.** Every human actor and every officer field (`decided_by`, `requested_by`, `opened_by`) is the
  fictional "Sandbox Officer", and the same names are replaced inside every text. System and machine actors (the
  rules engine, the cameras, the AI) keep their names. Officer notes are dropped.
- No key matches the person-key denylist (`author`, `person`, `handle`, …). `workspace.unit.mjs` asserts all three.

## How it was made

`node tests/fixtures/workspace/derive.mjs <redesign/prototype dir>` re-makes it from the same capture. The script
reads the capture as JSON (it never executes it), collects the human values at run time (no name is written in the
script) and refuses to write a file in which one survives.
