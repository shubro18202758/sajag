"""osint_common — the canonical OSINT and decision-support shapes every Sajag OSINT package imports (X18).

Events are about PLACES and SITUATIONS, never persons. Modules:

* :mod:`osint_common.types` — the pydantic models (contracts C-T and C-U), ``extra="forbid"`` everywhere;
* :mod:`osint_common.ethics` — the person-key denylist and the surviving-PII detector, enforced by the models;
* :mod:`osint_common.kinds` — the shared vocabulary (event kinds in C3 lockstep, classes, source priors);
* :mod:`osint_common.pipeline` — the resolver, embedder and ``run_pipeline`` protocols;
* :mod:`osint_common.testing` — synthetic fixtures (fictional publishers ``*.example``, no real names).

Its only dependency is pydantic; consumers get it through ``PYTHONPATH`` (plan §4), so importing this package
imports nothing else.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
