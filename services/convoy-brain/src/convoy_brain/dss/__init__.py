"""Brain-side decision-support seam (OSINT slice 6, plan §5.2 C-U).

The brain contributes to decision support without ever deciding: it asks the
27B decider which COA *strategy* fits a reported situation — the same typed
choice / noul / score questions as the pre-movement checkpoint, generalised —
and the answer becomes the oracle DSS's ``strategy_prior``: a recorded,
labelled opinion that never changes the MCDA and never acts.  The COA set,
its ranking and the officer gate live in the oracle; the generate endpoint is
compute-only (R2) and a named duty officer decides in the deck.
"""

from convoy_brain.dss.coa_generator import COA_KINDS, dss_questions, strategy_prior

__all__ = ["COA_KINDS", "dss_questions", "strategy_prior"]
