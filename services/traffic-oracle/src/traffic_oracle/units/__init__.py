"""Agency units & dispatch channel — package surface (signalling-janrakshak).

Civic Volunteers (agency code ``jan_rakshak``) are a FIRST-CLASS agency
actor: they appear in the agency registry (``agencies.py``), can be
dispatched through the approve/defer channel (``router.py``), and their
emulated units move deterministically along the corridor graph
(``projection.py``) for the ops board / canvas.
"""

from traffic_oracle.units.agencies import AGENCIES, JAN_RAKSHAK

__all__ = ["AGENCIES", "JAN_RAKSHAK"]
