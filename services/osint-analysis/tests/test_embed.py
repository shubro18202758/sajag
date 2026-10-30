"""HttpEmbedder: POST <base>/embed only (a read), batches of 64, None on ANY failure, never a redirect, never a write
endpoint. Every test runs on an httpx.MockTransport: no network, no embedding service."""

from __future__ import annotations

import json

import httpx
import numpy as np
import pytest

from osint_analysis.embed import EMBED_PATH, MAX_TEXT_CHARS, HttpEmbedder, unit_vectors

BASE = "http://127.0.0.1:59999"


def recorder(handler):
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    return httpx.MockTransport(wrapped), seen


def echo_vectors(request: httpx.Request) -> httpx.Response:
    texts = json.loads(request.content)["texts"]
    return httpx.Response(200, json={"vectors": [[float(len(t)), 1.0, 0.5] for t in texts]})


def test_posts_texts_to_the_embed_route_and_returns_vectors():
    transport, seen = recorder(echo_vectors)
    emb = HttpEmbedder(BASE, transport=transport)
    out = emb.embed(["alpha", "be"])
    assert out == [[5.0, 1.0, 0.5], [2.0, 1.0, 0.5]]
    assert len(seen) == 1
    req = seen[0]
    assert req.method == "POST" and req.url.path == EMBED_PATH == "/embed"
    assert json.loads(req.content) == {"texts": ["alpha", "be"]}
    assert "authorization" not in {k.lower() for k in req.headers}
    assert emb.url == BASE + "/embed"


def test_never_calls_a_write_endpoint_whatever_the_base_path():
    transport, seen = recorder(echo_vectors)
    HttpEmbedder(BASE + "/svc/", transport=transport).embed(["x"])
    assert [r.url.path for r in seen] == ["/svc/embed"]
    assert all("documents" not in r.url.path and "incidents" not in r.url.path for r in seen)


def test_batches_of_64():
    transport, seen = recorder(echo_vectors)
    out = HttpEmbedder(BASE, transport=transport).embed([f"t{i}" for i in range(130)])
    assert len(out) == 130 and [len(json.loads(r.content)["texts"]) for r in seen] == [64, 64, 2]


def test_texts_are_bounded():
    transport, seen = recorder(echo_vectors)
    HttpEmbedder(BASE, transport=transport).embed(["x" * (MAX_TEXT_CHARS + 500)])
    assert len(json.loads(seen[0].content)["texts"][0]) == MAX_TEXT_CHARS


def test_empty_input_needs_no_call():
    transport, seen = recorder(echo_vectors)
    assert HttpEmbedder(BASE, transport=transport).embed([]) == []
    assert seen == []


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, json={"detail": "Not Found"}),  # today's embedding service has no /embed route
        httpx.Response(500, text="boom"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"vectors": [[1.0, 2.0]]}),  # one vector for two texts
        httpx.Response(200, json={"vectors": [[1.0, 2.0], [1.0]]}),  # ragged
        httpx.Response(200, json={"vectors": [[1.0, "x"], [1.0, 2.0]]}),
        httpx.Response(200, json={"vectors": [[1.0, True], [1.0, 2.0]]}),
        httpx.Response(200, json={"vectors": [[], []]}),
        httpx.Response(200, json={"unexpected": []}),
        httpx.Response(307, headers={"location": BASE + "/embed/documents"}),  # never followed
    ],
)
def test_returns_none_on_any_bad_answer(response):
    transport, seen = recorder(lambda request: response)
    assert HttpEmbedder(BASE, transport=transport).embed(["a", "b"]) is None
    assert len(seen) == 1  # no retry, no redirect


def test_nan_in_the_body_is_refused():
    transport, _ = recorder(lambda r: httpx.Response(200, content=b'{"vectors": [[NaN, 1.0], [1.0, 2.0]]}'))
    assert HttpEmbedder(BASE, transport=transport).embed(["a", "b"]) is None


@pytest.mark.parametrize("exc", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow"), RuntimeError("odd")])
def test_returns_none_when_the_service_is_unreachable(exc):
    def raise_(request):
        raise exc

    assert HttpEmbedder(BASE, transport=httpx.MockTransport(raise_)).embed(["a"]) is None


def test_reads_the_alternative_response_shapes():
    for body in ({"embeddings": [[1.0, 0.0]]}, {"dense": [[1.0, 0.0]]}, [[1.0, 0.0]]):
        transport, _ = recorder(lambda r, body=body: httpx.Response(200, json=body))
        assert HttpEmbedder(BASE, transport=transport).embed(["a"]) == [[1.0, 0.0]]


@pytest.mark.parametrize(
    "base",
    ["127.0.0.1:8085", "ftp://127.0.0.1", "http://", "http://user:secret@127.0.0.1:8085", "http://127.0.0.1/?q=1",
     "http://127.0.0.1/#frag"],
)
def test_rejects_a_malformed_or_credentialed_base_url(base):
    with pytest.raises(ValueError):
        HttpEmbedder(base)


def test_satisfies_the_frozen_embedder_protocol():
    from osint_common.pipeline import Embedder

    assert isinstance(HttpEmbedder(BASE), Embedder)
    assert HttpEmbedder(BASE)._timeout == 3.0  # the contract's default


def test_rejects_a_silly_timeout():
    with pytest.raises(ValueError):
        HttpEmbedder(BASE, timeout=0)
    with pytest.raises(ValueError):
        HttpEmbedder(BASE, deadline=0)


def test_a_slow_but_answering_service_is_cut_off_at_the_deadline(monkeypatch):
    # each request "takes" 4 s on a fake clock: with the 10 s default deadline the third batch is never sent and
    # the call answers None (lexical fallback) instead of holding the ingest for 33 batches x 3 s
    import osint_analysis.embed as embed_mod

    clock = {"now": 1000.0}
    monkeypatch.setattr(embed_mod, "_monotonic", lambda: clock["now"])

    def slow(request: httpx.Request) -> httpx.Response:
        clock["now"] += 4.0
        return echo_vectors(request)

    transport, seen = recorder(slow)
    emb = HttpEmbedder(BASE, transport=transport)
    assert emb.embed([f"t{i}" for i in range(64 * 5)]) is None
    assert len(seen) == 3  # 0 s, 4 s, 8 s sent; at 12 s the deadline has passed
    # each request's own timeout never exceeds what is left of the deadline
    timeouts = [r.extensions["timeout"]["read"] for r in seen]
    assert timeouts[0] == 3.0 and timeouts[2] == pytest.approx(2.0)


def test_a_fast_service_finishes_well_inside_the_deadline(monkeypatch):
    import osint_analysis.embed as embed_mod

    monkeypatch.setattr(embed_mod, "_monotonic", lambda: 50.0)  # no time passes
    transport, seen = recorder(echo_vectors)
    out = HttpEmbedder(BASE, transport=transport, deadline=1.0).embed([f"t{i}" for i in range(200)])
    assert out is not None and len(out) == 200 and len(seen) == 4


def test_unit_vectors_normalises_and_fails_closed():
    class Fixed:
        def __init__(self, out):
            self.out = out

        def embed(self, texts):
            return self.out

    arr = unit_vectors(Fixed([[3.0, 4.0], [0.0, 2.0]]), ["a", "b"])
    assert np.allclose(arr, [[0.6, 0.8], [0.0, 1.0]])
    assert unit_vectors(Fixed([[0.0, 0.0], [1.0, 0.0]]), ["a", "b"]) is None  # a zero row
    assert unit_vectors(Fixed([[1.0, 0.0]]), ["a", "b"]) is None  # wrong count
    assert unit_vectors(Fixed(None), ["a"]) is None
    assert unit_vectors(None, ["a"]) is None
