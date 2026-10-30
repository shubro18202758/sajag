"""The canonical OSINT shapes, re-exported from ``osint_common.types`` (X18; plan
§4) so the spec's import path ``traffic_oracle.osint.types`` keeps working. There
is exactly one definition: ``osint_common``.

Importing this module needs ``osint_common`` on the path (pytest ``pythonpath``;
the gb10 image's PYTHONPATH, OS-INT). Nothing in the oracle core imports it.
"""

from osint_common.types import *  # noqa: F403 — a deliberate re-export of the canonical module
from osint_common.types import __all__ as __all__  # noqa: PLC0414
