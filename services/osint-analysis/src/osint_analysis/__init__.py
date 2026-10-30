"""Sajag OSINT analysis (OS-4): turn geocoded open-source signals into honest situations about PLACES, never persons.

The stages, each in its own module, all pure and deterministic:

* :mod:`osint_analysis.classify` — a fine event class and a Sajag kind per signal (an English, Marathi and Hindi
  lexicon, the SACHET rule, an optional zero-shot fallback through an embedder). It never emits ``crime_incident``.
* :mod:`osint_analysis.fusion` — Stage 1: deduplicate within a class (space × time × text) into base clusters.
* :mod:`osint_analysis.correlate` — Stage 2: join co-located, time-overlapping base clusters of related classes
  into one situation (``road_accident`` + ``public_conflict`` → ``affray+collision``).
* :mod:`osint_analysis.credibility` — independence-aware credibility and an honest verification state.
* :mod:`osint_analysis.attach` — read-only attach to the live corridor state (corroborates or novel).
* :mod:`osint_analysis.second_order` — protected-corridor, convoy, ambulance (108) route and closure flags.
* :mod:`osint_analysis.pipeline` — ``run_pipeline(...)``, the one entry point (OS-5, OS-2 ``--dry-run``, OS-INT).
* :mod:`osint_analysis.embed` — ``HttpEmbedder``, the optional dense embedder; the pipeline never depends on it.

Import the entry points from their modules (``from osint_analysis.pipeline import run_pipeline``); this package
module stays import-light.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
