"""osint_geo — Sajag's offline geo-resolver for open-source signals about Mumbai (OSINT SPEC §1.4; plan X18/X19).

A :class:`~osint_common.types.RawOsintSignal` becomes a :class:`~osint_common.types.Geocode` snapped to a real
``segment_id`` or ``junction_id`` of the OpenStreetMap network Sajag routes on, with a calibrated confidence, or an
honest ``None``. Places only: nothing here reads, stores or returns a person.

Modules:

* :mod:`osint_geo.gazetteer` — the X19 gazetteer: load (places only), normalise, the longest-match index and the
  place protect-set (stdlib only);
* :mod:`osint_geo.translit` — the Marathi and Hindi aliases and transliterations (stdlib only);
* :mod:`osint_geo.grammar` — the regex place grammar ("near X", "X more", "X setu", "X thana", PIN ``700xxx``);
* :mod:`osint_geo.geom` — a segment's network anchor, ``ST_PointOnSurface`` of its line (stdlib only, for the
  generator);
* :mod:`osint_geo.snap` — the 65-segment / 49-junction network and the snap onto it (shapely, pyproj);
* :mod:`osint_geo.confidence` — the geocode confidence formula and buckets;
* :mod:`osint_geo.resolver` — :class:`~osint_geo.resolver.GazetteerResolver` (``osint_common.pipeline.GeoResolver``)
  and ``resolve_text`` for ``GET /osint/gazetteer/resolve``.

Offline and deterministic: no I/O beyond reading ``scripts/data/osint_gazetteer.json`` and
``scripts/data/osm_network.json``; both are loaded once per process and are read-only (thread-safe) afterwards.
Importing this package imports nothing else.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
