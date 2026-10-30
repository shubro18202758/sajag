"""Publishing (an httpx MockTransport oracle): batches ≤ 200 with a run_id; a 503 keeps the batch cached;
rejected reasons are logged without text; retries with backoff; a 422 drops only the signals it names (else the
batch), re-posts the rest, and nothing it dropped is queued again."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
import structlog

from osint_common.testing import em_bypass_signals
from osint_common.types import RawGeoHint, RawOsintSignal, signal_id_for
from osint_ingress.cache import Cache
from osint_ingress.config import USER_AGENT
from osint_ingress.publish import INGEST_PATH, Publisher
from osint_ingress.safe_http import make_oracle_client


def _signals(n: int) -> list[RawOsintSignal]:
    out = []
    for i in range(n):
        sid = f"synthetic:publish-{i}"
        out.append(RawOsintSignal(
            signal_id=signal_id_for("google_news_rss", sid), source="google_news_rss", source_id=sid,
            source_tier="aggregator", publisher="news-a.example", url=None,
            title=f"Synthetic headline number {i} near Sealdah", text=f"Synthetic body {i}", language="en",
            published_at=None, fetched_at=datetime(2026, 10, 20, 15, tzinfo=UTC), valid_until=None,
            fetch_mode="cached-sample", pii_redactions=0, raw_geo_hint=RawGeoHint(), category_hint=[],
            tone=None, provenance_label="NEWS-REPORTED", credibility_prior=0.6, license="google_news_personal_use",
            redistributable=False, raw={},
        ))
    return out


class Oracle:
    """A scripted oracle: ``answers`` is consumed per POST (the last one repeats)."""

    def __init__(self, *answers) -> None:
        self.answers = list(answers)
        self.posts: list[dict] = []
        self.health_status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(self.health_status, json={"status": "ok"})
        assert request.url.path == INGEST_PATH and request.method == "POST"
        body = json.loads(request.content)
        self.posts.append(body)
        ans = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return ans(body) if callable(ans) else ans


def _ok(body: dict) -> httpx.Response:
    n = len(body["signals"])
    return httpx.Response(200, json={"accepted": n, "duplicates": 0, "rejected": [], "geotagged": n // 2,
                                     "resolved": [], "counts": {"surfaced": 3}})


def _publisher(tmp_path, oracle: Oracle, **kw) -> Publisher:
    client = make_oracle_client("http://127.0.0.1:8162", user_agent=USER_AGENT, transport=httpx.MockTransport(oracle))
    return Publisher(client, Cache(tmp_path), oracle_host="127.0.0.1:8162", backoff_sec=0, **kw)


async def test_batches_are_at_most_200_with_a_run_id(tmp_path):
    oracle = Oracle(_ok)
    pub = _publisher(tmp_path, oracle)
    assert pub.enqueue(_signals(450), "osint-run-1") == 3
    res = await pub.flush()
    assert [len(p["signals"]) for p in oracle.posts] == [200, 200, 50]
    assert {p["run_id"] for p in oracle.posts} == {"osint-run-1"}
    assert res.status == "ok" and res.accepted == 450 and res.batches_sent == 3 and res.batches_pending == 0
    assert res.surfaced == 3 and res.geotagged == 100 + 100 + 25
    assert pub.status.last_post_status == "200 ok" and pub.status.last_post_at is not None
    # everything the oracle answered for is not queued again
    assert pub.enqueue(_signals(450), "osint-run-2") == 0


async def test_503_not_deployed_keeps_the_batch_cached(tmp_path):
    oracle = Oracle(httpx.Response(503, json={"detail": "osint pipeline not deployed"}))
    pub = _publisher(tmp_path, oracle)
    pub.enqueue(_signals(10), "osint-run-1")
    res = await pub.flush()
    assert len(oracle.posts) == 1  # a definitive 503: recorded, not retried
    assert res.status == "pending: osint pipeline not deployed" and res.batches_pending == 1
    assert pub.status.last_post_status == "503 osint pipeline not deployed"
    assert len(pub.cache.outbox_pending()) == 1
    # the next cycle delivers it once the pipeline is deployed
    oracle.answers = [_ok]
    res = await pub.flush()
    assert res.status == "ok" and res.accepted == 10 and not pub.cache.outbox_pending()


async def test_retries_with_backoff_on_connection_errors_and_5xx(tmp_path):
    calls = {"n": 0}

    def flaky(body: dict) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("refused")
        if calls["n"] == 2:
            return httpx.Response(502, json={"detail": "bad gateway"})
        return _ok(body)

    pub = _publisher(tmp_path, Oracle(flaky), retries=3)
    pub.enqueue(_signals(3), "osint-run-1")
    res = await pub.flush()
    assert calls["n"] == 3 and res.status == "ok" and res.accepted == 3


async def test_connection_failure_keeps_the_batch(tmp_path):
    def down(body: dict) -> httpx.Response:
        raise httpx.ConnectError("refused")

    pub = _publisher(tmp_path, Oracle(down), retries=2)
    pub.enqueue(_signals(3), "osint-run-1")
    res = await pub.flush()
    assert res.status == "pending: oracle connection failed" and res.batches_pending == 1
    assert pub.status.last_post_status.startswith("connection failed")


async def test_rejected_reasons_are_logged_without_text(tmp_path):
    sigs = em_bypass_signals()

    def rejecting(body: dict) -> httpx.Response:
        ids = [s["signal_id"] for s in body["signals"]]
        return httpx.Response(200, json={
            "accepted": len(ids) - 2, "duplicates": 0, "geotagged": 0, "resolved": [], "counts": {},
            "rejected": [{"signal_id": ids[0], "reason": "pii_unredacted"}, {"signal_id": ids[1], "reason": "invalid"}],
        })

    pub = _publisher(tmp_path, Oracle(rejecting))
    pub.enqueue(sigs, "osint-run-1")
    with structlog.testing.capture_logs() as logs:
        res = await pub.flush()
    assert res.rejected == 2 and dict(res.rejected_reasons) == {"pii_unredacted": 1, "invalid": 1}
    rejected = [entry for entry in logs if entry["event"] == "signal_rejected"]
    assert [e["signal_id"] for e in rejected] == [sigs[0].signal_id, sigs[1].signal_id]
    logged = json.dumps(logs)
    for s in sigs:  # no title, text or publisher text in any log line
        assert s.title not in logged and s.text[:40] not in logged


async def test_422_drops_a_poison_batch_and_continues(tmp_path):
    oracle = Oracle(httpx.Response(422, json={"detail": "malformed"}), _ok)
    pub = _publisher(tmp_path, oracle, batch_size=5)
    pub.enqueue(_signals(10), "osint-run-1")
    res = await pub.flush()
    assert len(oracle.posts) == 2 and res.accepted == 5 and res.batches_pending == 0
    assert res.status == "ok" and res.batches_dropped == 1 and res.as_dict()["batches"]["dropped"] == 1


def _fastapi_422(*locs: list) -> httpx.Response:
    """A 422 in FastAPI's validation shape (``detail``: one error per ``loc``)."""
    return httpx.Response(422, json={"detail": [{"type": "missing", "loc": loc, "msg": "Field required"}
                                                for loc in locs]})


async def test_422_naming_signals_drops_only_those_and_reposts_the_rest_first(tmp_path):
    """Review-r2: one bad signal never sinks its batch-mates, and nothing dropped is queued again next cycle."""
    oracle = Oracle(_fastapi_422(["body", "signals", 1, "title"], ["body", "signals", 3]), _ok)
    pub = _publisher(tmp_path, oracle, batch_size=5)
    sigs = _signals(10)
    assert pub.enqueue(sigs, "osint-run-1") == 2
    res = await pub.flush()
    # batch 1 (5) refused, its 3 good signals re-posted at once (before batch 2), then batch 2 (5)
    assert [len(p["signals"]) for p in oracle.posts] == [5, 3, 5]
    assert [s["signal_id"] for s in oracle.posts[1]["signals"]] == [sigs[i].signal_id for i in (0, 2, 4)]
    assert {p["run_id"] for p in oracle.posts} == {"osint-run-1"}
    assert res.accepted == 8 and res.signals_dropped == 2 and res.batches_dropped == 1 and res.batches_pending == 0
    assert res.status == "ok" and res.as_dict()["signals_dropped"] == 2
    # the next cycle queues nothing: 8 were accepted and the 2 refused ones are remembered
    assert pub.enqueue(sigs, "osint-run-2") == 0
    assert len(oracle.posts) == 3


async def test_422_about_the_envelope_drops_the_batch_and_never_requeues_it(tmp_path):
    oracle = Oracle(_fastapi_422(["body", "run_id"]))
    pub = _publisher(tmp_path, oracle, batch_size=5)
    sigs = _signals(5)
    pub.enqueue(sigs, "osint-run-1")
    res = await pub.flush()
    assert len(oracle.posts) == 1 and res.batches_dropped == 1 and res.signals_dropped == 5
    assert res.status == "dropped: malformed batch (422)" and not pub.cache.outbox_pending()
    assert pub.status.last_post_status == "422 malformed batch (dropped)"
    assert pub.enqueue(sigs, "osint-run-2") == 0  # remembered: not posted and dropped every cycle
    res = await pub.flush()
    assert res.status == "nothing new" and len(oracle.posts) == 1


async def test_422_remainder_that_cannot_be_written_keeps_the_whole_batch(tmp_path, monkeypatch):
    pub = _publisher(tmp_path, Oracle(_fastapi_422(["body", "signals", 0])), batch_size=5)
    pub.enqueue(_signals(5), "osint-run-1")

    def unwritable(name: str, payload: bytes):  # noqa: ARG001
        raise OSError("read-only cache volume")

    monkeypatch.setattr(pub.cache, "outbox_put", unwritable)
    res = await pub.flush()
    assert res.status == "pending: cache outbox not writable" and res.batches_pending == 1 and res.signals_dropped == 0


@pytest.mark.parametrize("detail", ["malformed", [], [{"loc": ["body", "signals", 9]}], [{"loc": ["query", "x"]}],
                                    [{"loc": ["body", "signals", True]}]])
async def test_422_detail_that_names_no_valid_signal_refuses_the_whole_batch(tmp_path, detail):
    pub = _publisher(tmp_path, Oracle(httpx.Response(422, json={"detail": detail})), batch_size=5)
    pub.enqueue(_signals(5), "osint-run-1")
    res = await pub.flush()
    assert res.signals_dropped == 5 and res.batches_pending == 0


@pytest.mark.parametrize(("status", "reachable"), [(200, True), (404, True), (503, False)])
async def test_probe_is_a_get_of_health(tmp_path, status, reachable):
    oracle = Oracle(_ok)
    oracle.health_status = status
    pub = _publisher(tmp_path, oracle)
    assert await pub.probe() is reachable and pub.status.reachable is reachable and oracle.posts == []


async def test_probe_unreachable_never_raises(tmp_path):
    pub = Publisher(make_oracle_client("http://127.0.0.1:9", user_agent=USER_AGENT), Cache(tmp_path),
                    oracle_host="127.0.0.1:9", probe_timeout_sec=2.0)
    try:
        assert await pub.probe() is False
    finally:
        await pub.client.aclose()
