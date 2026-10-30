"""traffic_oracle.osint — the oracle's OSINT surfaces (contract C-T): places and
situations, never persons.

Modules (each lands in its own work package; until then coordination.py answers
503 "not deployed"):

* ``types`` — a re-export of ``osint_common.types`` (the canonical shapes, X18);
* ``router``, ``store``, ``promote``, ``ingest``, ``live_state`` — ingest, surfaced
  events, the dossier, the named-officer promotion to a corridor event, and the
  gazetteer resolve (OS-5).

This package imports nothing on purpose: the oracle core (``events/``, ``city/``)
never imports ``osint_*`` (X20), and ``coordination.py`` mounts
``traffic_oracle.osint.router`` only when it (and the OSINT libraries) import, so
an image without them still boots.
"""
