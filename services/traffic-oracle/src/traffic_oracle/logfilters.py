"""Log hygiene — no registration mark leaves the oracle's logs raw (C6).

uvicorn's access logger (``uvicorn.access``) writes one line per request,
query string included: ``GET /api/v1/vehicles/lookup?plate=MH02EM9001``
— for every lookup, the anonymous 409 probe included (audit A, S1).  The
route itself never logs the mark; the SERVER did.  :class:`MarkMaskingFilter`
sits on that logger and rewrites each record before any handler formats
it, with the oracle's own mask (``city.common``):

    * the value of every ``plate`` query parameter (the key matched after
      percent-decoding, any case — the router binds ``pl%61te`` too):
      a registration mark becomes ``mask_plate`` of its canonical form
      (``MH02EM•••1``); anything else becomes ``•••`` — the value is never
      written as it arrived, valid mark or not;
    * any other query value or path segment that carries a mark once
      percent-decoded (``/vehicles/WB%2006%20EM%209001/earmark``) is masked
      the same way;
    * then :func:`~traffic_oracle.city.common.mask_plates_in_text` over the
      whole string, the superset pass every city text gets.

The record keeps its shape (uvicorn's ``AccessFormatter`` unpacks
``record.args`` as a 5-tuple): each string argument is rewritten in
place.  The filter never drops a record — request accounting stays whole.

:func:`install_access_log_filter` puts it on the logger (idempotent).
``create_app`` calls it, so every server built from the app factory —
``python -m traffic_oracle`` included — is covered; uvicorn's own logging
setup (``logging.config.dictConfig``) replaces a logger's handlers but
keeps its filters, so it survives ``uvicorn.run``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from urllib.parse import unquote, unquote_plus

from traffic_oracle.city.common import mask_plate, mask_plates_in_text
from traffic_oracle.vehicles.plates import InvalidPlate, normalize_plate

__all__ = [
    "ACCESS_LOGGER",
    "MarkMaskingFilter",
    "REDACTED",
    "install_access_log_filter",
    "mask_marks_in_request_text",
]

#: The logger uvicorn writes its request lines to.
ACCESS_LOGGER = "uvicorn.access"

#: The query parameter that is ALWAYS a registration mark (vehicles router).
PLATE_PARAM = "plate"

#: A ``plate`` value that is not a mark at all: written as the mask alone.
REDACTED = "•••"

#: ``?key=value`` / ``&key=value`` inside any text (a request line, a URL).
_QUERY_PAIR_RE = re.compile(r"([?&;])([^=&#?;\s\"]*)=([^&#;\s\"]*)")

#: One path segment (between slashes, up to the query string).
_PATH_SEGMENT_RE = re.compile(r"(?<=/)([^/?#\s\"]+)")


def _masked_mark(text: str) -> str | None:
    """``text`` masked when it IS, or carries, a registration mark; else None."""
    try:
        return mask_plate(normalize_plate(text))
    except InvalidPlate:
        pass
    masked = mask_plates_in_text(text)
    return masked if masked != text else None


def _mask_pair(m: re.Match[str]) -> str:
    sep, key, value = m.group(1), m.group(2), m.group(3)
    decoded = unquote_plus(value)
    if unquote_plus(key).strip().lower() == PLATE_PARAM:
        if not value:
            return m.group(0)
        return f"{sep}{key}={_masked_mark(decoded) or REDACTED}"
    masked = _masked_mark(decoded)
    return m.group(0) if masked is None else f"{sep}{key}={masked}"


def _mask_segment(m: re.Match[str]) -> str:
    masked = _masked_mark(unquote(m.group(1)))
    return m.group(1) if masked is None else masked


def mask_marks_in_request_text(text: str) -> str:
    """``text`` with no registration mark left raw (the rules above).

    Pure; text without a mark or a ``plate`` parameter comes back equal.
    """
    if not text:
        return text
    out = _QUERY_PAIR_RE.sub(_mask_pair, text)
    head, sep, query = out.partition("?")
    out = _PATH_SEGMENT_RE.sub(_mask_segment, head) + sep + query
    return mask_plates_in_text(out)


class MarkMaskingFilter(logging.Filter):
    """Masks registration marks in a record's message and arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple):
            record.args = tuple(
                mask_marks_in_request_text(a) if isinstance(a, str) else a for a in args
            )
        elif isinstance(args, Mapping):
            record.args = {
                k: mask_marks_in_request_text(v) if isinstance(v, str) else v
                for k, v in args.items()
            }
        if isinstance(record.msg, str):
            # with arguments the message is a format string: only the mark
            # pass may touch it (a rewritten ``plate=%s`` would lose its %s)
            record.msg = (
                mask_plates_in_text(record.msg) if args
                else mask_marks_in_request_text(record.msg)
            )
        return True


def install_access_log_filter(name: str = ACCESS_LOGGER) -> MarkMaskingFilter:
    """Put :class:`MarkMaskingFilter` on logger ``name`` once; returns it."""
    logger = logging.getLogger(name)
    for existing in logger.filters:
        if isinstance(existing, MarkMaskingFilter):
            return existing
    installed = MarkMaskingFilter()
    logger.addFilter(installed)
    return installed
