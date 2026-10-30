"""OSINT test fixtures for the oracle (OS-5): synthetic signals, a fake pipeline, a fake store
and the sandbox database guard. Synthetic replicas only (fictional publishers, no real names), on
Kolkata's places and road network.

Retired: the store parity with the proof-of-concept (``parity_store.py``, and ``replay.py``, the
pipeline that replayed the proof-of-concept's fused output into the store). Those outputs are the
previous city's captures, fused on its own gazetteer: their segment and junction ids name another
network (on Kolkata's, segment 1045 is the Sector V - New Town link and junction 11 is Babughat),
their points lie outside the city box, and their counts (3 surfaced situations, 7 held social ones)
cannot be reproduced by any Kolkata pipeline. Replaying them would only file another city's
incidents on unrelated Kolkata roads. What was city-independent is kept as a shape-only check in
``test_osint_pipeline_integration.py``: the capture passes the trust boundary and the real pipeline
and surfaces nothing in Kolkata. The Kolkata behaviour is pinned by the synthetic Kolkata fixtures
here and by the osint-geo and osint-analysis golden tests.
"""
