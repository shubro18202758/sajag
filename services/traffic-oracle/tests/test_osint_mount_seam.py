"""The OSINT / decision-support router-mount seam (coordination.py; plan R4).

* with neither router importable, the four stub paths answer a truthful 503 "not deployed";
* with a router module that RAISES at import, ``create_app()`` still builds, a warning
  names the error type, and the stubs still answer — a broken OSINT router can never stop
  the oracle from booting;
* with a (fake) router importable, its route wins over the stub.

Both real routers land in later waves (OS-5, OS-6); every case here forces its own import
outcome, so the test keeps its meaning after they merge.
"""

from __future__ import annotations

import asyncio
import importlib.abc
import importlib.machinery
import sys
import types

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from traffic_oracle import coordination

OSINT_ROUTER = "traffic_oracle.osint.router"
DSS_PACKAGE = "traffic_oracle.decision_support"
DSS_ROUTER = "traffic_oracle.decision_support.router"

OSINT_ID = "4f7a9c1e-0b5d-4c33-9e21-7d8a6b5c4e3f"
DSS_ID = "0d6c2a7e-5b1f-4e8a-9c3d-2f4e6a8b0c1d"
STUB_GETS = (
    "/api/v1/osint/events",
    f"/api/v1/osint/events/{OSINT_ID}",
    "/api/v1/osint/gazetteer/resolve?q=taratala",
    f"/api/v1/decision-support/{DSS_ID}",
)


class _RaisesAtImport(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """A module that exists but raises RuntimeError while it is imported."""

    def __init__(self, fullname: str) -> None:
        self.fullname = fullname

    def find_spec(self, fullname, path, target=None):  # noqa: ANN001
        if fullname == self.fullname:
            return importlib.machinery.ModuleSpec(fullname, self)
        return None

    def create_module(self, spec):  # noqa: ANN001
        return None

    def exec_module(self, module):  # noqa: ANN001
        raise RuntimeError("broken OSINT router (test): exploded at import")


class _Log:
    def __init__(self) -> None:
        self.records: list[tuple[str, str, dict]] = []

    def info(self, event, **kw):  # noqa: ANN001
        self.records.append(("info", event, kw))

    def warning(self, event, **kw):  # noqa: ANN001
        self.records.append(("warning", event, kw))


def _block(monkeypatch, *names: str) -> None:
    """``sys.modules[name] = None`` makes ``import name`` raise ModuleNotFoundError."""
    for name in names:
        monkeypatch.setitem(sys.modules, name, None)


def _get_all(app, paths=STUB_GETS):
    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            return [await c.get(p) for p in paths]

    return asyncio.run(run())


@pytest.fixture
def log(monkeypatch):
    rec = _Log()
    monkeypatch.setattr(coordination, "logger", rec)
    return rec


def test_frozen_stub_path_templates():
    assert coordination.OSINT_PATHS == (
        "/api/v1/osint/events",
        "/api/v1/osint/events/{osint_event_id}",
        "/api/v1/osint/gazetteer/resolve",
    )
    assert coordination.DECISION_SUPPORT_PATHS == ("/api/v1/decision-support/{dss_id}",)


def test_neither_router_importable_stubs_answer_503(monkeypatch, log):
    from traffic_oracle.__main__ import create_app

    _block(monkeypatch, OSINT_ROUTER, DSS_PACKAGE, DSS_ROUTER)
    app = create_app()
    for r in _get_all(app):
        assert r.status_code == 503 and r.json() == {"detail": "not deployed"}, r.request.url
    not_deployed = [rec for rec in log.records if rec[1] == "coordination.not_deployed"]
    assert {rec[2]["stream"] for rec in not_deployed} == {"osint", "decision_support"}
    assert all(rec[0] == "info" for rec in not_deployed)


def test_router_that_raises_at_import_never_stops_the_boot(monkeypatch, log):
    from traffic_oracle.__main__ import create_app

    monkeypatch.delitem(sys.modules, OSINT_ROUTER, raising=False)
    finder = _RaisesAtImport(OSINT_ROUTER)
    monkeypatch.setattr(sys, "meta_path", [finder, *sys.meta_path])
    _block(monkeypatch, DSS_PACKAGE, DSS_ROUTER)

    app = create_app()  # must not raise
    for r in _get_all(app):
        assert r.status_code == 503 and r.json() == {"detail": "not deployed"}, r.request.url
    failed = [rec for rec in log.records if rec[1] == "coordination.router_failed"]
    assert len(failed) == 1 and failed[0][0] == "warning"
    assert failed[0][2]["stream"] == "osint" and failed[0][2]["error_type"] == "RuntimeError"
    # the rest of the oracle is up: a core route answers (no pool → 503 from the route itself)
    (events_active,) = _get_all(app, ("/api/v1/events/active",))
    assert events_active.json() == {"detail": "database pool unavailable"}


def test_router_whose_include_fails_is_contained(monkeypatch, log):
    from traffic_oracle.__main__ import create_app

    broken = types.ModuleType(OSINT_ROUTER)
    broken.router = object()  # not a router: include_router raises
    monkeypatch.setitem(sys.modules, OSINT_ROUTER, broken)
    _block(monkeypatch, DSS_PACKAGE, DSS_ROUTER)
    app = create_app()
    assert all(r.status_code == 503 for r in _get_all(app))
    assert any(rec[1] == "coordination.router_failed" for rec in log.records)


def test_a_present_router_wins_over_the_stub(monkeypatch, log):
    from traffic_oracle.__main__ import create_app

    osint = APIRouter()

    @osint.get("/api/v1/osint/events")
    async def _events():
        return {"events": [], "fake": "osint"}

    @osint.get("/api/v1/osint/events/{osint_event_id}")
    async def _event(osint_event_id: str):
        return {"event": {"osint_event_id": osint_event_id}, "fake": "osint"}

    @osint.get("/api/v1/osint/gazetteer/resolve")
    async def _resolve(q: str = ""):
        return {"q": q, "candidates": [], "fake": "osint"}

    dss = APIRouter()

    @dss.get("/api/v1/decision-support/{dss_id}")
    async def _dss(dss_id: str):
        return {"dss_id": dss_id, "fake": "dss"}

    osint_module = types.ModuleType(OSINT_ROUTER)
    osint_module.router = osint
    dss_package = types.ModuleType(DSS_PACKAGE)
    dss_package.__path__ = []  # a package
    dss_module = types.ModuleType(DSS_ROUTER)
    dss_module.router = dss
    monkeypatch.setitem(sys.modules, OSINT_ROUTER, osint_module)
    monkeypatch.setitem(sys.modules, DSS_PACKAGE, dss_package)
    monkeypatch.setitem(sys.modules, DSS_ROUTER, dss_module)

    app = create_app()
    responses = _get_all(app)
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert [r.json()["fake"] for r in responses] == ["osint", "osint", "osint", "dss"]
    assert responses[1].json()["event"]["osint_event_id"] == OSINT_ID
    mounted = {rec[2]["stream"] for rec in log.records if rec[1] == "coordination.router_mounted"}
    assert {"osint", "decision_support"} <= mounted
    stubbed = ("osint", "decision_support")
    assert not [
        rec
        for rec in log.records
        if rec[1] == "coordination.stub_mounted" and rec[2]["stream"] in stubbed
    ]
