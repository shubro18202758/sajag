"""Sajag decision support (contract C-U; OSINT SPEC §1.7, slice 6) — a real DSS, not a recommendation list.

For any event — a reported OSINT situation (``osint_event:<uuid>``) or a corridor event (``event:<uuid>``) — it
produces ONE ``DecisionSupport``: a small set of courses of action from real Sajag actuators (always a do-nothing
baseline and an information COA), each war-gamed (the seeded corridor twin, unchanged, for the closure and
diversion COAs, plus a net-new DSS-layer cascade model; a seeded Monte-Carlo surrogate when the twin cannot
answer), checked for resource feasibility against the live unit plane, filtered by a non-compensatory lexical
veto BEFORE scoring, scored by TOPSIS with AHP weights (consistency ratio reported, zero-variance criteria
reported as gate-passed) and Dirichlet sensitivity, with a real expected value of information, a recommendation
and an explicit dissent.

The DSS writes NO action.  A named duty officer approves exactly one COA (``router.py``); the approval creates
dispatch REQUESTS in Sajag's existing human-gated channel (each then decided on its own) and, when the COA needs a
corridor event and the subject is an unpromoted OSINT report, promotes that report with the same officer.  Every
other verb is a next step in its own home.  Places and situations, never persons.

Modules: ``router`` (the three routes), ``engine`` (orchestration and scoring), ``coa``, ``wargame``,
``cascade``, ``feasibility``, ``mcda``, ``voi``, ``dissent``, ``store`` (the 022 tables).
"""

from __future__ import annotations

__all__: list[str] = []
