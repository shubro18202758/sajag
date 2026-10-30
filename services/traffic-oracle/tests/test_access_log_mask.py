"""The access log never carries a registration mark raw (FIX-AUDIT-A, audit A S1).

uvicorn writes one ``uvicorn.access`` line per request with its query string:
``GET /api/v1/vehicles/lookup?plate=WB06EM9001`` — every lookup, the anonymous
409 probe included.  ``traffic_oracle.logfilters.MarkMaskingFilter`` masks it
on that logger with the oracle's own mask (``city.common.mask_plate``):

* the pure rule — every ``plate`` value (key matched percent-decoded, any
  case) becomes the mask of its canonical mark, or ``•••`` when it is not a
  mark; a mark in another query value or a path segment is masked too; text
  without one is untouched;
* the filter on a record shaped exactly like uvicorn's (5-tuple args, which
  ``AccessFormatter`` unpacks), and on a preformatted message;
* the install — idempotent, done by ``create_app``, and still in place after
  uvicorn's own ``dictConfig`` logging setup;
* end to end — a REAL uvicorn server (127.0.0.1, an ephemeral port, the real
  vehicles router, uvicorn's own logging config) answers an anonymous 409, an
  officer's 503 (no pool) and a malformed 422: the access lines it writes say
  ``plate=WB06EM•••1`` / ``plate=•••`` and never the mark.
"""

from __future__ import annotations

import http.client
import logging
import re
import threading
import time
from urllib.parse import quote, unquote_plus

import pytest
from fastapi import FastAPI

from traffic_oracle.city.common import mask_plate
from traffic_oracle.logfilters import (
    ACCESS_LOGGER,
    REDACTED,
    MarkMaskingFilter,
    install_access_log_filter,
    mask_marks_in_request_text,
)

uvicorn = pytest.importorskip("uvicorn")

MARK = "WB06EM9001"
MASKED = mask_plate(MARK)  # WB06EM•••1
LOOKUP = "/api/v1/vehicles/lookup"


#: The mark in any spelling (case, separators), once percent-decoded.
_RAW_MARK_RE = re.compile(r"wb\W{0,3}06\W{0,3}em\W{0,3}9001", re.I)


def _assert_no_raw_mark(text: str) -> None:
    assert not _RAW_MARK_RE.search(text), text
    assert not _RAW_MARK_RE.search(unquote_plus(text)), text


# ── the pure rule ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(("text", "masked"), [
    (f"{LOOKUP}?plate={MARK}", f"{LOOKUP}?plate={MASKED}"),
    (f"{LOOKUP}?plate=wb+06+em-9001", f"{LOOKUP}?plate={MASKED}"),
    (f"{LOOKUP}?plate=WB%2006%20EM%209001", f"{LOOKUP}?plate={MASKED}"),
    (f"{LOOKUP}?plate=wb.06.em.9001", f"{LOOKUP}?plate={MASKED}"),
    (f"{LOOKUP}?pl%61te={MARK}", f"{LOOKUP}?pl%61te={MASKED}"),  # the router binds it too
    (f"{LOOKUP}?PLATE={MARK}", f"{LOOKUP}?PLATE={MASKED}"),
    (f"{LOOKUP}?limit=5&plate={MARK}&x=1", f"{LOOKUP}?limit=5&plate={MASKED}&x=1"),
    (f"{LOOKUP}?plate={MARK}&plate=MH12AB3456", f"{LOOKUP}?plate={MASKED}&plate=MH12AB•••6"),
    (f"{LOOKUP}?plate=22BH1234AA", f"{LOOKUP}?plate={mask_plate('22BH1234AA')}"),
    # not a mark: the value is still never written as it arrived
    (f"{LOOKUP}?plate=NOT-A-PLATE", f"{LOOKUP}?plate={REDACTED}"),
    (f"{LOOKUP}?plate=WB06EM90011", f"{LOOKUP}?plate={REDACTED}"),  # a near-mark, 10 of 11 kept
    (f"{LOOKUP}?pl%61te=WB06EM90011", f"{LOOKUP}?pl%61te={REDACTED}"),  # key matched decoded
    (f"{LOOKUP}?Plate+=NOT-A-PLATE", f"{LOOKUP}?Plate+={REDACTED}"),  # any case, padded
    (f"{LOOKUP}?plate=WB06EM900", f"{LOOKUP}?plate={mask_plate('WB06EM900')}"),
    (f"{LOOKUP}?plate=WB06EM9001%21%21", f"{LOOKUP}?plate={MASKED}!!"),
    (f"{LOOKUP}?plate=", f"{LOOKUP}?plate="),
    # a mark elsewhere in the line: a path segment, another query value
    (f"/api/v1/vehicles/{MARK}/earmark", f"/api/v1/vehicles/{MASKED}/earmark"),
    ("/api/v1/vehicles/WB%2006%20EM%209001/earmark", f"/api/v1/vehicles/{MASKED}/earmark"),
    (f"/api/v1/city/search?q={MARK}", f"/api/v1/city/search?q={MASKED}"),
    (f"/api/v1/city/search?q=car+{MARK}+at+J11", f"/api/v1/city/search?q=car {MASKED} at J11"),
])
def test_the_mask_rule_case_by_case(text, masked):
    assert mask_marks_in_request_text(text) == masked
    _assert_no_raw_mark(mask_marks_in_request_text(text))


@pytest.mark.parametrize("text", [
    "/api/v1/vehicles/lookups?limit=50",
    "/api/v1/city/entity/osint_event/0b7e3c2a-dd12-3456-9a8b-5c6d7e8f9a0b",
    "/api/v1/vehicles/0b7e3c2a-1111-4d1e-9a8b-5c6d7e8f9a0b/sightings?limit=100",
    "/api/v1/traffic/historical?segment_id=1045&hours=24",
    "/health",
    "127.0.0.1:52344",
    "",
])
def test_a_line_without_a_mark_is_untouched(text):
    assert mask_marks_in_request_text(text) == text


# ── the filter on uvicorn-shaped records ────────────────────────────────────


def _uvicorn_record(path_with_query: str, status: int = 409) -> logging.LogRecord:
    """Exactly what uvicorn's h11/httptools protocol logs per request."""
    return logging.LogRecord(
        ACCESS_LOGGER, logging.INFO, __file__, 0, '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:52344", "GET", path_with_query, "1.1", status), None,
    )


def test_the_filter_masks_a_uvicorn_record_and_keeps_its_shape():
    from uvicorn.logging import AccessFormatter

    record = _uvicorn_record(f"{LOOKUP}?plate={MARK}")
    assert MarkMaskingFilter().filter(record) is True  # never drops a line
    assert record.args == ("127.0.0.1:52344", "GET", f"{LOOKUP}?plate={MASKED}", "1.1", 409)
    line = AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s',
                           use_colors=False).format(record)
    assert line == f'127.0.0.1:52344 - "GET {LOOKUP}?plate={MASKED} HTTP/1.1" 409 Conflict'
    _assert_no_raw_mark(line)


def test_the_filter_masks_a_preformatted_message_and_keeps_format_strings_whole():
    pre = logging.LogRecord(ACCESS_LOGGER, logging.INFO, __file__, 0,
                            f'127.0.0.1:1 - "GET {LOOKUP}?plate={MARK} HTTP/1.1" 409', None, None)
    MarkMaskingFilter().filter(pre)
    assert pre.getMessage() == f'127.0.0.1:1 - "GET {LOOKUP}?plate={MASKED} HTTP/1.1" 409'
    # with arguments the message is a format string: its %s survives
    fmt = logging.LogRecord(ACCESS_LOGGER, logging.INFO, __file__, 0,
                            "GET /x?plate=%s", (MARK,), None)
    MarkMaskingFilter().filter(fmt)
    assert fmt.getMessage() == f"GET /x?plate={MASKED}"
    mapping = logging.LogRecord(ACCESS_LOGGER, logging.INFO, __file__, 0,
                                "%(path)s", ({"path": f"{LOOKUP}?plate={MARK}"},), None)
    MarkMaskingFilter().filter(mapping)
    assert mapping.getMessage() == f"{LOOKUP}?plate={MASKED}"


# ── the install ─────────────────────────────────────────────────────────────


@pytest.fixture
def uvicorn_logging():
    """Snapshot and restore the uvicorn loggers (uvicorn's dictConfig and the
    filter install are process-global)."""
    names = ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi")
    saved = {n: (list(logging.getLogger(n).handlers), list(logging.getLogger(n).filters),
                 logging.getLogger(n).level, logging.getLogger(n).propagate,
                 logging.getLogger(n).disabled) for n in names}
    yield logging.getLogger(ACCESS_LOGGER)
    for n, (handlers, filters, level, propagate, disabled) in saved.items():
        lg = logging.getLogger(n)
        lg.handlers[:] = handlers
        lg.filters[:] = filters
        lg.setLevel(level)
        lg.propagate, lg.disabled = propagate, disabled


def _mask_filters(logger: logging.Logger) -> list:
    return [f for f in logger.filters if isinstance(f, MarkMaskingFilter)]


def test_install_is_idempotent_and_survives_uvicorns_logging_setup(uvicorn_logging):
    uvicorn_logging.filters[:] = [f for f in uvicorn_logging.filters
                                  if not isinstance(f, MarkMaskingFilter)]
    first = install_access_log_filter()
    assert install_access_log_filter() is first
    assert _mask_filters(uvicorn_logging) == [first]
    # what uvicorn.run does before serving: Config() runs dictConfig(LOGGING_CONFIG)
    uvicorn.Config(FastAPI(), log_level="info")
    assert _mask_filters(uvicorn_logging) == [first]
    assert uvicorn_logging.handlers, "uvicorn's access handler is configured"


def test_create_app_installs_the_filter(uvicorn_logging):
    from traffic_oracle.__main__ import create_app

    uvicorn_logging.filters[:] = [f for f in uvicorn_logging.filters
                                  if not isinstance(f, MarkMaskingFilter)]
    create_app()
    assert len(_mask_filters(uvicorn_logging)) == 1
    create_app()  # a second app in one process: still one filter
    assert len(_mask_filters(uvicorn_logging)) == 1


# ── end to end: a real uvicorn server, its own access log ───────────────────


def _vehicles_app() -> FastAPI:
    """The REAL vehicles router, no pool (an officer's lookup is a 503 after
    the gate and the plate checks) — nothing here touches a database."""
    from traffic_oracle.vehicles import router as vehicles_router

    app = FastAPI()
    app.include_router(vehicles_router)
    return app


def _get(port: int, path: str, headers: dict | None = None) -> int:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)  # no proxy, loopback
    try:
        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        resp.read()
        return resp.status
    finally:
        conn.close()


def test_a_real_uvicorn_access_log_never_carries_the_mark(uvicorn_logging, capsys, caplog):
    uvicorn_logging.filters[:] = [f for f in uvicorn_logging.filters
                                  if not isinstance(f, MarkMaskingFilter)]
    install_access_log_filter()
    config = uvicorn.Config(_vehicles_app(), host="127.0.0.1", port=0, log_level="info",
                            lifespan="off", access_log=True)
    uvicorn_logging.addHandler(caplog.handler)  # propagate is False on uvicorn.access
    caplog.set_level(logging.INFO, logger=ACCESS_LOGGER)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started, "uvicorn did not start"
        port = server.servers[0].sockets[0].getsockname()[1]
        officer = {"x-sajag-officer": "Duty%20Officer%20A"}
        statuses = [
            _get(port, f"{LOOKUP}?plate={MARK}"),                      # anonymous probe
            _get(port, f"{LOOKUP}?plate={quote('wb 06 em-9001')}"),    # anonymous, spaced
            _get(port, f"{LOOKUP}?plate={MARK}", officer),             # gate passed, no pool
            _get(port, f"{LOOKUP}?plate={MARK}%21%21", officer),       # malformed
            _get(port, f"{LOOKUP}?plate=NOT-A-PLATE&officer=Duty", None),
        ]
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    assert statuses == [409, 409, 503, 422, 409]
    lines = [r.getMessage() for r in caplog.records if r.name == ACCESS_LOGGER]
    assert len(lines) == 5, lines  # the access log is live: one line per request
    assert sum(f"plate={MASKED} " in line for line in lines) == 3
    assert any(f"plate={MASKED}!! " in line for line in lines)
    assert any(f"plate={REDACTED}&officer=Duty " in line for line in lines)
    printed = capsys.readouterr()
    for text in lines + [printed.out, printed.err]:
        _assert_no_raw_mark(text)
    assert f"plate={MASKED}" in printed.out  # uvicorn's own handler wrote the masked line
