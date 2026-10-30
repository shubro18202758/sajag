# OSINT deck fixtures (OS-DECK-A) — SYNTHETIC

Synthetic replicas (plan R13) of the wire shapes `GET /api/v1/city/entities`
serves for the OSINT kinds (contract C-C extension): fictional `*.example`
publishers plus the public-domain NDMA SACHET sample text, the same toponyms
and class cues as the sandbox's synthetic capture. Every summary carries the
parse-time redactions (`[PERSON]`, `[AGE]`) — never a real person, plate,
handle or author.

| File | What |
|---|---|
| `correlated.json` | The Sector V - New Town link correlated crash (segment 1045): a proposed, unexpired decision-support summary; a district SACHET alert attached as CONTEXT (never corroboration). |
| `district.json` | The SACHET Kolkata district alert: area-level, official, OFFICIAL-VERIFIED. |
| `robbery.json` | The Babughat robbery (junction 11): one second-order flag ("On a 108 route"). |
| `place.json` | A gazetteer place (landmark) with EN + MR surface forms. |
| `poisoned.json` | The correlated shape with a PLANTED `author` / `byline` pair and an EXPIRED decision-support summary — the negative fixture for the section's whitelist and the decision-dot rule. Used by tests only; the `/design/osint` harness never loads it. |

No fixture here is live data. The real PoC captures are never committed
(R13); nothing in this directory names a person.
