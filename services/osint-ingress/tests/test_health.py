"""``/health``: the contract shape and the ok/degraded rules; ``oracle.reachable`` follows the GET probe, not the
last post; ``once`` against an unreachable oracle posts nothing and exits 0 within 5 s; ``POST /cycle`` is
loopback only."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from conftest import CAPTURE, DEAD_ORACLE, PACKAGE

from osint_ingress.config import CONNECTOR_NAMES, Settings, cadences_from_env
from osint_ingress.importer import import_capture
from osint_ingress.safe_http import ALLOWED_HOSTS, EGRESS_HOSTS
from osint_ingress.service import create_app

ISO_OR_NULL = (str, type(None))


class OracleDouble:
    def __init__(self) -> None:
        self.health_up = True
        self.post_status = 200
        self.posts = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            if not self.health_up:
                raise httpx.ConnectError("refused")
            return httpx.Response(200, json={"status": "ok"})
        self.posts += 1
        if self.post_status == 503:
            return httpx.Response(503, json={"detail": "osint pipeline not deployed"})
        body = json.loads(request.content)
        return httpx.Response(200, json={"accepted": len(body["signals"]), "duplicates": 0, "rejected": [],
                                         "geotagged": 5, "resolved": [], "counts": {"surfaced": 3}})


def _offline_settings(tmp_path: Path, *, imported: bool = True) -> Settings:
    if imported:
        import_capture(CAPTURE, tmp_path / "cache")
    return Settings(cache_dir=tmp_path / "cache", oracle_url="http://127.0.0.1:8162", mode="offline")


async def _call(app, method: str, path: str, client=("127.0.0.1", 40000)) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, client=client)
    async with httpx.AsyncClient(transport=transport, base_url="http://osint-ingress") as c:
        return await c.request(method, path)


async def test_health_shape_after_a_cycle(tmp_path):
    oracle = OracleDouble()
    app = create_app(_offline_settings(tmp_path), oracle_transport=httpx.MockTransport(oracle), background=False)
    async with app.router.lifespan_context(app):
        r = await _call(app, "POST", "/cycle")
        assert r.status_code == 200
        assert set(r.json()) == {"at", "signals", "accepted", "rejected", "geotagged", "surfaced", "pii_redactions"}
        h = (await _call(app, "GET", "/health")).json()
    assert set(h) == {"status", "mode", "version", "oracle", "connectors", "last_cycle", "egress_allowlist"}
    assert h["status"] == "ok" and h["mode"] == "offline" and h["version"] == "0.1.0"
    assert h["oracle"] == {"host": "127.0.0.1:8162", "reachable": True, "last_post_at": h["oracle"]["last_post_at"],
                           "last_post_status": "200 ok"}
    assert isinstance(h["oracle"]["last_post_at"], str)
    assert set(h["connectors"]) == set(CONNECTOR_NAMES)
    for name, c in h["connectors"].items():
        assert set(c) == {"enabled", "cadence_sec", "last_run_at", "last_ok_at", "fetch_mode", "signals", "error",
                          "cache_age_sec"}, name
        assert isinstance(c["enabled"], bool) and isinstance(c["cadence_sec"], int) and isinstance(c["signals"], int)
        assert isinstance(c["last_run_at"], ISO_OR_NULL) and isinstance(c["error"], ISO_OR_NULL)
    assert h["connectors"]["sachet_cap"]["fetch_mode"] == "cached-sample" and h["connectors"]["sachet_cap"]["signals"] == 7
    assert h["connectors"]["sachet_cap"]["cadence_sec"] == 300 and h["connectors"]["google_news_rss"]["cadence_sec"] == 600
    assert h["connectors"]["common_crawl"]["enabled"] is False and h["connectors"]["common_crawl"]["cadence_sec"] == 0
    for off in ("wbsdma", "kmc_scrape"):  # Maharashtra SDMA (via SACHET) and the BMC portal (no notice list)
        assert h["connectors"][off]["enabled"] is False and h["connectors"][off]["error"].startswith("disabled:")
    assert h["connectors"]["mumbai_police_scrape"]["enabled"] is True
    assert h["connectors"]["mumbai_police_scrape"]["cadence_sec"] == 3600
    lc = h["last_cycle"]
    assert lc["signals"] == 32 and lc["accepted"] == 32 and lc["surfaced"] == 3 and lc["pii_redactions"] > 0
    # every host the service may contact: the exact hosts plus the path-restricted GDELT bucket host
    assert h["egress_allowlist"] == sorted(EGRESS_HOSTS) == sorted(ALLOWED_HOSTS | {"storage.googleapis.com"})


async def test_degraded_when_the_oracle_is_unreachable(tmp_path):
    oracle = OracleDouble()
    oracle.health_up = False
    app = create_app(_offline_settings(tmp_path), oracle_transport=httpx.MockTransport(oracle), background=False)
    async with app.router.lifespan_context(app):
        await _call(app, "POST", "/cycle")
        h = (await _call(app, "GET", "/health")).json()
    assert h["status"] == "degraded" and h["oracle"]["reachable"] is False and oracle.posts == 0


async def test_degraded_before_the_first_cycle_and_when_every_connector_failed(tmp_path):
    oracle = OracleDouble()
    app = create_app(_offline_settings(tmp_path, imported=False), oracle_transport=httpx.MockTransport(oracle),
                     background=False)
    async with app.router.lifespan_context(app):
        h = (await _call(app, "GET", "/health")).json()
        assert h["status"] == "degraded" and h["last_cycle"]["at"] is None
        await _call(app, "POST", "/cycle")  # offline with an empty cache: every connector fails
        h = (await _call(app, "GET", "/health")).json()
    assert h["oracle"]["reachable"] is True and h["status"] == "degraded"
    assert all(c["error"] for c in h["connectors"].values() if c["enabled"])


async def test_reachable_follows_the_probe_not_the_last_post(tmp_path):
    oracle = OracleDouble()
    oracle.post_status = 503
    app = create_app(_offline_settings(tmp_path), oracle_transport=httpx.MockTransport(oracle), background=False)
    async with app.router.lifespan_context(app):
        await _call(app, "POST", "/cycle")
        h = (await _call(app, "GET", "/health")).json()
        # the post failed (503), yet the oracle answers its /health: reachable
        assert h["oracle"]["reachable"] is True and h["oracle"]["last_post_status"].startswith("503")
        engine = app.state.runtime.engine
        oracle.post_status, oracle.health_up = 200, True
        await engine.cycle()
        assert (await _call(app, "GET", "/health")).json()["oracle"]["last_post_status"] == "200 ok"
        # now the probe fails: reachable goes false although the last post succeeded
        oracle.health_up = False
        await engine.publisher.probe()
        h = (await _call(app, "GET", "/health")).json()
    assert h["oracle"]["reachable"] is False and h["oracle"]["last_post_status"] == "200 ok"
    assert h["status"] == "degraded"


async def test_cycle_is_loopback_only(tmp_path):
    app = create_app(_offline_settings(tmp_path), oracle_transport=httpx.MockTransport(OracleDouble()),
                     background=False)
    async with app.router.lifespan_context(app):
        r = await _call(app, "POST", "/cycle", client=("10.0.0.5", 40000))
        assert r.status_code == 403 and r.json() == {"detail": "loopback callers only"}
        assert (await _call(app, "POST", "/cycle", client=("::1", 40000))).status_code == 200
        assert (await _call(app, "GET", "/docs")).status_code == 404  # no extra surface
        assert (await _call(app, "GET", "/openapi.json")).status_code == 404


def test_once_against_an_unreachable_oracle_posts_nothing_and_exits_0_fast(tmp_path):
    import_capture(CAPTURE, tmp_path / "cache")
    report = tmp_path / "report.json"
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(
        str(PACKAGE / p) for p in ("src", "../osint-common/src")
    ))
    env.pop("OSINT_ORACLE_URL", None)
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "osint_ingress", "once", "--offline", "--cache-dir", str(tmp_path / "cache"),
         "--oracle", DEAD_ORACLE, "--report", str(report)],
        cwd=PACKAGE, env=env, capture_output=True, text=True, timeout=60,
    )
    elapsed = time.monotonic() - t0
    assert proc.returncode == 0, proc.stderr[-2000:]
    rep = json.loads(report.read_text())
    # the brief's 5 s bounds the run itself (probe, parse, outbox, skip): no retry loop, no backoff. The process
    # wall time adds interpreter start-up and imports, which a loaded box stretches, so it gets a wide margin.
    assert rep["elapsed_sec"] < 5.0, rep["elapsed_sec"]
    assert elapsed < 20.0, elapsed
    assert rep["publish"] == "skipped: oracle unreachable" and rep["oracle_reachable"] is False
    assert rep["publish_detail"]["batches"]["sent"] == 0 and rep["publish_detail"]["batches"]["pending"] >= 1
    assert len(list((tmp_path / "cache" / "_outbox").glob("*.json"))) == rep["publish_detail"]["batches"]["pending"]
    assert rep["signals"] == 32 and rep["checks"]["validated"] == 32 and rep["checks"]["find_pii_clean"] == 32
    # counts only: no title or text of any signal is printed
    assert "Ruby crossing" not in proc.stdout and "Ruby crossing" not in proc.stderr


@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (["once", "--oracle", "http://10.0.0.5:8091", "--offline"], 2),
        (["nonsense"], 2),
        (["once", "--offline", "--oracle", DEAD_ORACLE, "--only", "no_such_connector"], 2),
        (["once", "--offline", "--oracle", DEAD_ORACLE, "--only", " , "], 2),
    ],
)
def test_cli_usage_errors_exit_2(argv, code, tmp_path):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(PACKAGE / p) for p in ("src", "../osint-common/src")),
               OSINT_CACHE_DIR=str(tmp_path))
    proc = subprocess.run([sys.executable, "-m", "osint_ingress", *argv], cwd=PACKAGE, env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == code, proc.stderr[-1000:]


def test_an_unknown_only_connector_is_refused_before_anything_runs(tmp_path):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(PACKAGE / p) for p in ("src", "../osint-common/src")))
    env.pop("OSINT_ORACLE_URL", None)
    cache = tmp_path / "cache"
    proc = subprocess.run(
        [sys.executable, "-m", "osint_ingress", "once", "--offline", "--cache-dir", str(cache),
         "--oracle", DEAD_ORACLE, "--only", "sachet_cap,no_such_connector", "--report", str(tmp_path / "r.json")],
        cwd=PACKAGE, env=env, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 2, proc.stderr[-1000:]
    assert "unknown connector(s): no_such_connector" in proc.stderr and "Traceback" not in proc.stderr
    assert not cache.exists() and not (tmp_path / "r.json").exists()  # nothing was built, probed or written


def test_settings_read_the_contract_variables(monkeypatch, tmp_path):
    monkeypatch.setenv("OSINT_ORACLE_URL", "http://127.0.0.1:8162")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "8193")
    monkeypatch.setenv("OSINT_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("OSINT_MODE", "OFFLINE")
    monkeypatch.setenv("OSINT_CADENCE_SACHET_CAP_SEC", "120")
    monkeypatch.setenv("OSINT_CADENCE_REDDIT_RSS_SEC", "0")
    s = Settings()
    assert (s.oracle_url, s.port, s.cache_dir, s.mode) == ("http://127.0.0.1:8162", 8193, tmp_path, "offline")
    assert s.cadence_sec["sachet_cap"] == 120 and s.cadence_sec["reddit_rss"] == 0
    defaults = Settings(oracle_url="http://127.0.0.1:8091")
    assert defaults.host == "127.0.0.1"


def test_cadence_defaults_floor_and_garbage():
    c = cadences_from_env({"OSINT_CADENCE_GDELT_DOC_SEC": "5", "OSINT_CADENCE_GOOGLE_NEWS_RSS_SEC": "abc",
                           "OSINT_CADENCE_COMMON_CRAWL_SEC": "600"})
    assert c["gdelt_doc"] == 60  # raised to the polite floor
    assert c["google_news_rss"] == 600  # garbage ignored
    assert (c["sachet_cap"], c["gdelt_events"], c["reddit_rss"], c["kmc_scrape"]) == (300, 900, 900, 3600)
    assert (c["imd"], c["google_news_rss"], c["news_rss"]) == (600, 600, 900)
    assert c["common_crawl"] == 600  # parsed, yet never scheduled: the connector is backfill-only


async def test_common_crawl_is_never_scheduled_even_with_a_cadence(tmp_path, monkeypatch):
    monkeypatch.setenv("OSINT_CADENCE_COMMON_CRAWL_SEC", "600")
    app = create_app(_offline_settings(tmp_path), oracle_transport=httpx.MockTransport(OracleDouble()),
                     background=False)
    async with app.router.lifespan_context(app):
        engine = app.state.runtime.engine
        assert "common_crawl" not in engine.scheduled_names()
        assert "mumbai_police_scrape" in engine.scheduled_names()  # the MTP notices host, verified on 2026-10-30
        assert "wbsdma" not in engine.scheduled_names() and "kmc_scrape" not in engine.scheduled_names()


def test_the_oracle_url_never_defaults_to_the_live_oracle(monkeypatch, tmp_path):
    # F-CONN-09: unset, the CLI and the service posted to the LIVE oracle (:8091); now to the discard port :9
    from osint_ingress.config import UNSET_ORACLE_URL

    monkeypatch.delenv("OSINT_ORACLE_URL", raising=False)
    s = Settings(cache_dir=tmp_path)
    assert s.oracle_url == UNSET_ORACLE_URL == "http://127.0.0.1:9"
    assert ":8091" not in s.oracle_url and ":8162" not in s.oracle_url


def test_once_without_an_oracle_posts_nowhere(tmp_path):
    import_capture(CAPTURE, tmp_path / "cache")
    report = tmp_path / "report.json"
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(PACKAGE / p) for p in ("src", "../osint-common/src")))
    env.pop("OSINT_ORACLE_URL", None)
    proc = subprocess.run(
        [sys.executable, "-m", "osint_ingress", "once", "--offline", "--cache-dir", str(tmp_path / "cache"),
         "--report", str(report)],
        cwd=PACKAGE, env=env, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    rep = json.loads(report.read_text())
    assert rep["publish"] == "skipped: oracle unreachable" and rep["oracle_reachable"] is False
