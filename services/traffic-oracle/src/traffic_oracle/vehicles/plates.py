"""Server-side registration-plate normalization (vehicles only — C6).

Every plate that enters the oracle — an earmark request's path parameter,
an ANPR read's body — goes through :func:`normalize_plate` BEFORE it
touches SQL, so 'MH 02 EM 9001', 'mh-02-em-9001' and 'MH02EM9001' all
resolve to the ONE corridor.vehicles row the ANPR plane writes (the
table's UNIQUE(plate) can no longer fork a vehicle on formatting).

Accepted shapes (after upper-casing and stripping spaces, hyphens, dots):
    * standard series  SS RR [AAA] NNNN — state code, 1-2 digit RTO code,
      0-3 letter series, 1-4 digit number   e.g. MH02EM9001, DL3CAB1234
    * Bharat (BH)      YY BH NNNN AA        e.g. 22BH1234AA

Anything else is refused (ValueError -> HTTP 422): the watchlist never
holds free text that merely looks like a plate.
"""

from __future__ import annotations

import re

__all__ = ["InvalidPlate", "normalize_plate", "PLATE_PATTERNS"]

_SEPARATORS = re.compile(r"[\s\-.]+")

PLATE_PATTERNS = (
    re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{1,4}$"),  # standard series
    re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$"),             # Bharat series
)

#: Longest raw input considered (spaces/hyphens included).
_MAX_RAW_LEN = 32


class InvalidPlate(ValueError):
    """The input is not a recognisable Indian registration plate."""


#: The refusal text, for BOTH raises: the FORMAT in words, never the input
#: and never a full mark — a near-mark is a mark in all but one character,
#: and a 422 that echoes input or names an example mark lets a caller
#: search the space (the audit's hash-reversal demo recovered the demo's
#: stolen plate in 0.47 ms).  vehicles/__init__.py's
#: LOOKUP_INVALID_PLATE_DETAIL keeps the same rule for the lookup route;
#: the example fragment 'MH 01 AB' is a prefix shape, never a full mark.
#: The number is 1-4 digits — what PLATE_PATTERNS accepts (audit E round 2:
#: the sentence used to say just "4-digit", off by one from the pattern it
#: describes).
_INVALID_PLATE_DETAIL = (
    "not a registration plate: expected a state code, a district number, an optional series and a "
    "1-4 digit number (for example 'MH 01 AB' then 1-4 digits), or a BH-series plate (the input is not "
    "echoed back)"
)


def normalize_plate(raw: str) -> str:
    """Canonical plate: upper case, separators stripped, pattern-checked.

    Pure.  Raises :class:`InvalidPlate` for anything that is not a
    standard-series or BH-series plate.  The message describes the format
    and never echoes the input (FIX-E-LOOKUP).
    """
    if not isinstance(raw, str) or not raw.strip() or len(raw) > _MAX_RAW_LEN:
        raise InvalidPlate(_INVALID_PLATE_DETAIL)
    plate = _SEPARATORS.sub("", raw.strip().upper())
    if not any(p.match(plate) for p in PLATE_PATTERNS):
        raise InvalidPlate(_INVALID_PLATE_DETAIL)
    return plate
