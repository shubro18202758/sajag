"""osint_ingress — Sajag's OSINT ingress service (:8193).

It turns open sources into canonical, already-redacted :class:`osint_common.types.RawOsintSignal` records and
posts them to the oracle's machine-ingest route (contract C-T). Events are about PLACES and SITUATIONS, never
persons:

* every connector separates ``fetch()`` (raw bytes into the local cache) from ``parse()`` (cache to signals), so
  the edge box runs offline from its cache;
* person names and ages are redacted at parse (``[PERSON]``, ``[AGE]``); Reddit authors and handles are never
  read; GDELT actor and person columns are never read; ``raw`` is a scalar whitelist;
* news- and social-tier URLs are never emitted (their slugs can name a person): the signal keeps the outlet's
  domain and a ``url_sha256:`` hint of the canonical URL; official sources keep their identifier URLs;
* egress goes to an allow-list of exact hosts, and posting goes to a loopback oracle only.

Modules: :mod:`.config`, :mod:`.safe_http`, :mod:`.cache`, :mod:`.connectors`, :mod:`.publish`,
:mod:`.runner`, :mod:`.scheduler`, :mod:`.service` and the CLI in :mod:`.__main__`.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
