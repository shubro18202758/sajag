"""Mumbai's reference movements on the corridor network (City Pack
cities/mumbai/network.json, segment and junction ids as the store seeds them).

Two kinds of reference the brain reads when an operator names a place
instead of a segment:

* PROTECTED_MOVEMENTS — the protected-movement spines: Mantralaya to Airport
  T2 (the base case the corridor store seeds as profile ``vvip_convoy_base``)
  and its Raj Bhavan and BKC variants.  A spine is a legal directed path
  (one-ways honoured; the tests check every one against the network).  The
  plan for a real movement still comes from the router and a named officer
  approves it — these are the reference journeys, never a standing closure.
* GREEN_CORRIDORS — the hospitals an ambulance (108) green corridor ends at:
  the junction nearest each hospital on the network and the approach road,
  plus one reference approach path from a nearby arterial.  A green corridor
  is a PROPOSAL: signals along it are held only when a named officer
  approves; if no one answers, the current signal plan holds.

Ids are stable from network v1 (``net: network v1``).  Road data (c)
OpenStreetMap contributors, ODbL 1.0.
"""

from __future__ import annotations

from typing import Any

CITY = "mumbai"

#: protected-movement reference spines (segment ids, in travel order)
PROTECTED_MOVEMENTS: dict[str, dict[str, Any]] = {
    "mantralaya_airport_t2": {
        "name": "Mantralaya to Mumbai Airport T2",
        "origin_junction": "mantralaya",
        "destination_junction": "airport_t2",
        "via": "Marine Drive, Mumbai Coastal Road, Bandra-Worli Sea Link, "
               "Western Express Highway, Sahar Elevated Road",
        "spine": (1001, 1002, 1006, 1008, 1011, 1013, 1014, 1015, 1020),
        "profile_id": "vvip_convoy_base",
    },
    "raj_bhavan_airport_t2": {
        "name": "Raj Bhavan to Mumbai Airport T2",
        "origin_junction": "raj_bhavan",
        "destination_junction": "airport_t2",
        "via": "Walkeshwar Road, Marine Drive, Mumbai Coastal Road, Bandra-Worli Sea Link, "
               "Western Express Highway, Sahar Elevated Road",
        "spine": (1086, 1003, 1006, 1008, 1011, 1013, 1014, 1015, 1020),
        "profile_id": None,
    },
    "mantralaya_bkc": {
        "name": "Mantralaya to Bandra Kurla Complex",
        "origin_junction": "mantralaya",
        "destination_junction": "bkc",
        "via": "Marine Drive, Mumbai Coastal Road, Bandra-Worli Sea Link, "
               "Western Express Highway, Bandra Kurla Complex Road",
        "spine": (1001, 1002, 1006, 1008, 1011, 1013, 1052),
        "profile_id": None,
    },
}

#: ambulance (108) green-corridor ends: hospital -> its junction on the
#: network, the approach segment, and a reference approach path
GREEN_CORRIDORS: dict[str, dict[str, Any]] = {
    "kem": {"hospital": "KEM Hospital (Parel)", "junction": "kem", "approach_segment": 1070,
            "reference_path": (1066, 1070), "from_junction": "dadar_tt"},
    "sion_hospital": {"hospital": "Sion Hospital (LTMGH)", "junction": "sion_hospital",
                      "approach_segment": 1069, "reference_path": (1043, 1069),
                      "from_junction": "lbs_fork"},
    "jj_hospital": {"hospital": "JJ Hospital (Byculla)", "junction": "jj", "approach_segment": 1061,
                    "reference_path": (1061,), "from_junction": "csmt"},
    "nair_hospital": {"hospital": "Nair Hospital (Mumbai Central)", "junction": "nair",
                      "approach_segment": 1080, "reference_path": (1079, 1080),
                      "from_junction": "lalbaug"},
    "cooper_hospital": {"hospital": "Cooper Hospital (Vile Parle)", "junction": "vileparle_sv",
                        "approach_segment": 1026, "reference_path": (1031, 1029, 1028, 1026),
                        "from_junction": "weh_andheri"},
}


def protected_movement(key: str) -> dict[str, Any] | None:
    """The reference movement ``key`` (a copy), or None."""
    m = PROTECTED_MOVEMENTS.get(key)
    return dict(m) if m else None


def green_corridor(hospital_key: str) -> dict[str, Any] | None:
    """The green-corridor end for ``hospital_key`` (a copy), or None."""
    g = GREEN_CORRIDORS.get(hospital_key)
    return dict(g) if g else None


__all__ = ["CITY", "GREEN_CORRIDORS", "PROTECTED_MOVEMENTS", "green_corridor",
           "protected_movement"]
