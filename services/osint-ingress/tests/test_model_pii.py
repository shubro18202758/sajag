"""The optional parse-time model check (connectors/_model_pii.py): off by default, loopback only, strict client,
fail-open to the rules, adds names and never redacts a protected place.

Every name here is fictional and every sentence SYNTHETIC. No real HTTP: ``httpx.MockTransport`` only.
"""

from __future__ import annotations

import json
import re

import httpx
import pytest
from conftest import parse_cache

from osint_common import ethics
from osint_ingress.connectors import _model_pii
from osint_ingress.connectors._model_pii import (
    ENV_FLAG,
    ENV_URL,
    PII_PATH,
    HttpPiiDetector,
    LoopbackSyncTransport,
    detector_from_env,
    extra_spans,
    model_spans,
    protected_regions,
)
from osint_ingress.connectors._redact import DocumentRedactor, redact_persons
from osint_ingress.safe_http import EgressRefused

BASE = "http://127.0.0.1:8205"


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    monkeypatch.delenv(ENV_FLAG, raising=False)
    monkeypatch.delenv(ENV_URL, raising=False)
    _model_pii.reset()
    yield
    _model_pii.reset()


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakeSource:
    """Spans for every occurrence of the configured strings; records what it was asked."""

    def __init__(self, found: dict[str, str] | None = None, *, fail: bool = False) -> None:
        self.found = found or {}
        self.fail = fail
        self.asked: list[list[str]] = []

    def spans(self, texts):
        self.asked.append(list(texts))
        if self.fail:
            return None
        out = []
        for t in texts:
            row = []
            for needle, label in self.found.items():
                i = t.find(needle)
                while i >= 0:
                    row.append({"start": i, "end": i + len(needle), "label": label})
                    i = t.find(needle, i + 1)
            out.append(row)
        return out


def _detector(handler, **kw) -> HttpPiiDetector:
    return HttpPiiDetector(BASE, transport=httpx.MockTransport(handler), **kw)


def _ok(spans):
    return lambda request: httpx.Response(200, json={"spans": spans, "model": "fake", "labels": []})


# ── configuration ────────────────────────────────────────────────────────────────────────────────────────────────


def test_off_by_default_and_no_request():
    assert detector_from_env({}) is None
    assert _model_pii.configured() is None
    assert extra_spans(["Subrata Mondal says the drains are choked."], "news_regional", frozenset()) == [()]


@pytest.mark.parametrize("flag", ["0", "", "no", "off", "false"])
def test_flag_values_that_keep_it_off(flag):
    assert detector_from_env({ENV_FLAG: flag, ENV_URL: BASE}) is None


def test_flag_and_loopback_url_turn_it_on(monkeypatch):
    det = detector_from_env({ENV_FLAG: "1", ENV_URL: "http://localhost:8205/"})
    assert isinstance(det, HttpPiiDetector) and det.base_url == "http://localhost:8205"
    det.close()
    monkeypatch.setenv(ENV_FLAG, "true")
    monkeypatch.setenv(ENV_URL, BASE)
    _model_pii.reset()
    assert isinstance(_model_pii.configured(), HttpPiiDetector)


@pytest.mark.parametrize(
    "url",
    ["", "http://10.0.0.5:8205", "https://example.com", "http://user:pw@127.0.0.1:8205", f"{BASE}/pii/spans",
     "file:///etc/passwd"],
)
def test_non_loopback_or_odd_urls_are_refused(url):
    assert detector_from_env({ENV_FLAG: "1", ENV_URL: url}) is None


def test_client_ignores_the_environment_and_never_follows_redirects():
    det = HttpPiiDetector(BASE, timeout=99)
    try:
        c = det._client
        assert c.trust_env is False and c.follow_redirects is False
        assert c.timeout.read == 10.0 and c.timeout.connect == 0.5  # clamped
    finally:
        det.close()


def test_transport_refuses_a_non_loopback_host():
    t = LoopbackSyncTransport(httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(EgressRefused):
        t.handle_request(httpx.Request("POST", "http://example.com/pii/spans"))
    assert t.handle_request(httpx.Request("POST", f"{BASE}{PII_PATH}")).status_code == 200


# ── the client ───────────────────────────────────────────────────────────────────────────────────────────────────


def test_spans_round_trip():
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"spans": [[{"start": 0, "end": 5, "label": "private_person", "score": 0.9}],
                                                   []]})

    det = _detector(handler)
    assert det.spans(["Rumpa came home.", "Nothing here."]) == [
        [{"start": 0, "end": 5, "label": "private_person"}],
        [],
    ]
    (req,) = seen
    assert req.method == "POST" and req.url.path == PII_PATH and req.url.host == "127.0.0.1"
    assert json.loads(req.content) == {"texts": ["Rumpa came home.", "Nothing here."]}
    assert det.outcomes == {"ok": 1}


def test_large_documents_are_sent_in_parts():
    calls: list[int] = []

    def handler(request):
        n = len(json.loads(request.content)["texts"])
        calls.append(n)
        return httpx.Response(200, json={"spans": [[] for _ in range(n)]})

    assert _detector(handler).spans(["a"] * 150) == [[]] * 150
    assert calls == [64, 64, 22]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"detail": "boom"}),
        httpx.Response(307, headers={"Location": "http://127.0.0.1:9/pii/spans"}),
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, json={"spans": []}),  # wrong length
        httpx.Response(200, json={"spans": [[{"start": 0, "end": 99, "label": "private_person"}]]}),
        httpx.Response(200, json={"spans": [[{"start": True, "end": 2, "label": "private_person"}]]}),
        httpx.Response(200, json={"spans": [[{"start": 3, "end": 3, "label": "private_person"}]]}),
        httpx.Response(200, json={"spans": [[{"start": 0, "end": 2}]]}),
        httpx.Response(200, json={"nope": 1}),
        httpx.Response(200, content=b"[" + b" " * (1024 * 1024) + b"]"),
    ],
)
def test_bad_answers_fail_open(response):
    requests: list[httpx.Request] = []

    def handler(request):
        requests.append(request)
        return response

    det = _detector(handler)
    assert det.spans(["Rumpa came home."]) is None
    assert len(requests) == 1  # a redirect is never followed
    assert sum(det.outcomes.values()) == 1 and "ok" not in det.outcomes


def test_timeout_fails_open_then_cools_down():
    clock = Clock()
    calls: list[int] = []

    def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=request)

    det = _detector(handler, cooldown_sec=60, clock=clock)
    assert det.spans(["x"]) is None and len(calls) == 1
    clock.now += 30
    assert det.spans(["x"]) is None and len(calls) == 1  # cooling down: not asked
    clock.now += 31
    assert det.spans(["x"]) is None and len(calls) == 2
    assert det.outcomes["timeout"] == 2 and det.outcomes["cooldown"] == 1


def test_connection_error_fails_open():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    det = _detector(handler)
    assert det.spans(["x"]) is None
    assert det.outcomes == {"network_error:ConnectError": 1}


# ── the merge ────────────────────────────────────────────────────────────────────────────────────────────────────

NEWS = "news_regional"


def test_model_adds_a_name_the_rules_miss_and_never_a_place(protect):
    text = "Mrinmoy Shee says Senapati Bapat Marg and Acharya Atre Chowk are flooded."
    rules_only, n0 = redact_persons(text, NEWS, protect)
    assert "Mrinmoy Shee" in rules_only  # no cue, no listed surname: the rules alone miss it (the Marathi surname list now catches "Mondal")
    _model_pii.set_detector(FakeSource({"Mrinmoy Shee": "private_person", "Senapati": "private_person",
                                        "Acharya Atre Chowk": "private_person"}))
    (extra,) = extra_spans([text], NEWS, protect)
    out, n = redact_persons(text, NEWS, protect, extra=extra)
    assert out == "[PERSON] says Senapati Bapat Marg and Acharya Atre Chowk are flooded."
    assert n == n0 + 1
    assert ethics.find_pii(out) == []


def test_place_guard_on_marathi_and_hindi(protect):
    for text, place, name in (
        ("आचार्य अत्रे चौकात बस बंद पडली, चालक अमित पवार जखमी.", "आचार्य अत्रे", "अमित पवार"),
        ("सेनापति बापट मार्ग पर जलभराव, निवासी सुनीता शर्मा ने बताया।", "सेनापति बापट", "सुनीता शर्मा"),
    ):
        found = [
            {"start": text.index(place), "end": text.index(place) + len(place), "label": "private_person"},
            {"start": text.index(name), "end": text.index(name) + len(name), "label": "private_person"},
        ]
        spans = model_spans(text, found, NEWS, protect)
        assert [text[s.start : s.end] for s in spans] == [name]


def test_a_known_place_after_a_name_keeps_the_name(protect):
    text = "Majha neighbour Rohan Sawant Keshavrao Khadye Marg var adakla."
    protect = protect | {"keshavrao khadye marg"}
    found = [{"start": text.index("Rohan"), "end": text.index(" Marg"), "label": "private_person"}]
    assert [text[s.start : s.end] for s in model_spans(text, found, NEWS, protect)] == ["Rohan Sawant"]


def test_gazetteer_phrases_and_aliases_are_protected():
    protect = frozenset({"esplanade", "victoria memorial"})
    text = "Crowds near Victoria Memorial and Esplanade after the parade."
    found = [
        {"start": text.index("Victoria"), "end": text.index("Victoria") + 8, "label": "private_person"},
        {"start": text.index("Esplanade"), "end": text.index("Esplanade") + 9, "label": "private_person"},
    ]
    assert model_spans(text, found, NEWS, protect) == ()
    assert protected_regions(text, protect)[1] == {(text.index("Esplanade"), text.index("Esplanade") + 9)}


def test_contacts_are_redacted_outside_the_official_tier_only(protect):
    text = "For flood relief call 98300 41526 or write to relief.desk@example.in today."
    _model_pii.set_detector(FakeSource({"98300 41526": "private_phone", "relief.desk@example.in": "private_email",
                                        "flood": "private_address"}))
    (news,) = extra_spans([text], NEWS, protect)
    assert redact_persons(text, NEWS, protect, extra=news)[0] == (
        "For flood relief call [CONTACT] or write to [CONTACT] today."
    )
    (official,) = extra_spans([text], "official", protect)
    assert official == ()


def test_unavailable_or_broken_model_means_rules_only(protect):
    text = "Subrata Mondal says the drains are choked."
    _model_pii.set_detector(FakeSource({"Subrata Mondal": "private_person"}, fail=True))
    assert extra_spans([text], NEWS, protect) == [()]

    class Crashing:
        def spans(self, texts):
            raise RuntimeError("boom")

    class Malformed:
        def spans(self, texts):
            return [[{"start": 0, "end": 999, "label": "private_person"}] for _ in texts]

    for bad in (Crashing(), Malformed()):
        _model_pii.set_detector(bad)
        assert extra_spans([text, ""], NEWS, protect) == [(), ()]


def test_empty_texts_are_not_sent(protect):
    src = FakeSource()
    _model_pii.set_detector(src)
    assert extra_spans(["", "  ", "Rain at Dadar."], NEWS, protect) == [(), (), ()]
    assert src.asked == [["Rain at Dadar."]]


def test_document_redactor_passes_extra_to_the_first_pass_only(protect):
    text = "Subrata Mondal, 45, says the drains are choked."
    _model_pii.set_detector(FakeSource({"Subrata Mondal": "private_person"}))
    (extra,) = extra_spans([text], NEWS, protect)
    red = DocumentRedactor(NEWS, protect)
    red.learn(text)
    out, n = red.redact(text, extra)
    assert out.startswith("[PERSON], [AGE], says") and n == 2
    assert ethics.find_pii(out) == []


# ── parse ────────────────────────────────────────────────────────────────────────────────────────────────────────


def _dump(results: dict) -> list[tuple]:
    return [(s.signal_id, s.title, s.text, s.pii_redactions) for sigs in results.values() for s in sigs]


def test_parse_with_the_model_down_equals_rules_only(capture_cache, connectors, protect):
    base = _dump(parse_cache(capture_cache, connectors, protect))
    calls: list[int] = []

    def handler(request):
        calls.append(1)
        raise httpx.ConnectError("down", request=request)

    _model_pii.set_detector(_detector(handler, cooldown_sec=0))
    assert _dump(parse_cache(capture_cache, connectors, protect)) == base
    assert calls  # it was asked, failed, and the rules ran alone


def test_parse_asks_once_per_document_and_only_adds(capture_cache, connectors, protect):
    base = parse_cache(capture_cache, connectors, protect)
    src = FakeSource({})
    _model_pii.set_detector(src)
    same = parse_cache(capture_cache, connectors, protect)
    assert _dump(same) == _dump(base)  # an empty answer changes nothing
    assert len(src.asked) == len(base)  # one request per parsed document (one document per connector here)
    assert all(t.strip() and len(t) <= 2000 for batch in src.asked for t in batch)


def test_parse_with_a_model_answer_adds_redactions(capture_cache, connectors, protect):
    base = parse_cache(capture_cache, connectors, protect)

    def unprotected_word(title: str) -> str | None:
        regions, single = protected_regions(title, protect)
        for m in re.finditer(r"\b[A-Z][a-z]{3,}\b", title):
            if title.count(m.group(0)) == 1 and (m.start(), m.end()) not in single and not any(
                a < m.end() and m.start() < b for a, b in regions
            ):
                return m.group(0)
        return None

    sig, word = next((s, w) for sigs in base.values() for s in sigs if (w := unprotected_word(s.title)))
    _model_pii.set_detector(FakeSource({word: "private_person"}))
    after = {s.signal_id: s for sigs in parse_cache(capture_cache, connectors, protect).values() for s in sigs}
    again = after[sig.signal_id]
    assert word not in again.title and "[PERSON]" in again.title
    assert again.pii_redactions > sig.pii_redactions
    for s in after.values():
        assert ethics.find_pii(s.title) == [] and ethics.find_pii(s.text) == []
