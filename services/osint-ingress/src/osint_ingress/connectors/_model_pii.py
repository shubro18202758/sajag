"""Optional model check at parse: PII-Tracer spans from the embedding service, merged into the rule redaction.

OFF by default. ``OSINT_PII_MODEL=1`` and ``OSINT_PII_URL=http://127.0.0.1:<port>`` (the embedding service; loopback
only) turn it on. :func:`extra_spans` then sends one document's titles and texts (already bounded to 500 / 2000
characters) in one ``POST <OSINT_PII_URL>/pii/spans`` (``{"texts": [...]}`` → ``{"spans": [[{start, end, label}]]}``)
and turns the answer into extra spans for :func:`~._redact.redact_persons`:

* ``private_person`` → ``[PERSON]`` in every tier; ``private_email`` and ``private_phone`` → ``[CONTACT]`` in every
  tier but ``official`` (an official alert names public helplines); every other label is ignored.
* **The model only adds.** The rule spans are computed exactly as without it, then the two are merged; the rules
  stay primary and the result still passes ``osint_common.ethics.find_pii``.
* **Never a protected place.** The service already drops spans on Mumbai place names; this side clips every model
  span again against its own protected regions: multi-word phrases of the ingress protect-set (the gazetteer and the
  city pack) and the gazetteer's Marathi and Devanagari spellings (``osint_common.ethics.indic_place_forms``)
  occurring in the text, runs of name words that end in a place word ("Senapati Bapat Marg", "Acharya Atre Chowk",
  "Gokhale Bridge", "डॉ. आंबेडकर मार्गावर", "आचार्य अत्रे चौक", "लोकमान्य टिळक टर्मिनस"), and a
  span that is exactly a single-word gazetteer alias. What is left of a span after clipping is redacted; a
  fragment with no letter or digit is dropped.
* **Fail-open to the rules.** A refused URL, a connection error, a timeout, a redirect, a non-200 answer, an
  oversized or malformed body: the document is redacted by the rules alone and the outcome is logged (event
  ``pii_model``: the outcome and counts only, never a text, a name or a URL path). After a failure the model is not
  asked again for ``OSINT_PII_COOLDOWN_SEC`` (default 60 s), so a stopped service costs one timeout a minute, not
  one per document.

The client is a synchronous ``httpx.Client`` (``parse()`` is synchronous): ``trust_env=False`` (no proxy or netrc
from the environment, so no proxy ever sees the posts), no redirects, a loopback base URL checked by
``safe_http.check_oracle_url`` and re-checked per request by :class:`LoopbackSyncTransport`, a short timeout
(``OSINT_PII_TIMEOUT_SEC``, default 3 s, connect 0.5 s) and a bounded response (1 MiB). A call blocks the parse for
at most that timeout.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Protocol

import httpx
import structlog

from osint_common import ethics
from osint_ingress.connectors._redact import Span
from osint_ingress.safe_http import LOOPBACK_HOSTS, EgressRefused, check_oracle_url

__all__ = [
    "ENV_COOLDOWN",
    "ENV_FLAG",
    "ENV_TIMEOUT",
    "ENV_URL",
    "PII_PATH",
    "HttpPiiDetector",
    "LoopbackSyncTransport",
    "configured",
    "detector_from_env",
    "extra_spans",
    "model_spans",
    "protected_regions",
    "reset",
    "set_detector",
]

log = structlog.get_logger("osint_ingress.pii_model")

ENV_FLAG = "OSINT_PII_MODEL"
ENV_URL = "OSINT_PII_URL"
ENV_TIMEOUT = "OSINT_PII_TIMEOUT_SEC"
ENV_COOLDOWN = "OSINT_PII_COOLDOWN_SEC"
PII_PATH = "/pii/spans"
_TRUE = frozenset({"1", "true", "yes", "on"})
_MAX_TEXTS_PER_CALL = 64
_MAX_BODY = 1024 * 1024
_MAX_LABEL = 64
_USER_AGENT = "sajag-osint-ingress (parse-time PII check)"

#: Model label → redaction kind (``_redact`` tokens: ``name`` → ``[PERSON]``, ``contact`` → ``[CONTACT]``).
_KINDS: Mapping[str, str] = {"private_person": "name", "private_email": "contact", "private_phone": "contact"}
_OFFICIAL = "official"


class SpanSource(Protocol):
    """What :func:`extra_spans` needs: spans per text, or ``None`` when the model is unavailable."""

    def spans(self, texts: Sequence[str]) -> list[list[dict[str, Any]]] | None: ...


# ── the client ───────────────────────────────────────────────────────────────────────────────────────────────────


def _host(url: httpx.URL) -> str:
    return (url.host or "").strip("[]").lower()


class LoopbackSyncTransport(httpx.BaseTransport):
    """Refuses any request that does not go to a loopback host, before delegating (defence in depth)."""

    def __init__(self, inner: httpx.BaseTransport) -> None:
        self._inner = inner

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if _host(request.url) not in LOOPBACK_HOSTS:
            raise EgressRefused(f"egress refused: the PII model is loopback only ({_host(request.url)[:64]})")
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


class HttpPiiDetector:
    """``POST <base>/pii/spans`` with strict limits; :meth:`spans` returns ``None`` on any failure (fail-open)."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 3.0,
        cooldown_sec: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.base_url = check_oracle_url(base_url)  # loopback only, no credentials, no path
        timeout = min(10.0, max(0.2, float(timeout)))
        inner = transport or httpx.HTTPTransport(retries=0, trust_env=False)
        self._client = httpx.Client(
            base_url=self.base_url,
            transport=LoopbackSyncTransport(inner),
            trust_env=False,
            follow_redirects=False,
            headers={"User-Agent": _USER_AGENT},
            timeout=httpx.Timeout(timeout, connect=min(0.5, timeout)),
        )
        self.cooldown_sec = max(0.0, float(cooldown_sec))
        self._clock = clock
        self._down_until = 0.0
        self._lock = threading.Lock()
        self.outcomes: Counter[str] = Counter()

    def close(self) -> None:
        self._client.close()

    def _fail(self, outcome: str, n: int) -> None:
        self.outcomes[outcome] += 1
        self._down_until = self._clock() + self.cooldown_sec
        log.warning("pii_model", outcome=outcome, texts=n, fallback="rules_only")

    def spans(self, texts: Sequence[str]) -> list[list[dict[str, Any]]] | None:
        texts = list(texts)
        if not texts:
            return []
        with self._lock:
            if self._clock() < self._down_until:
                self.outcomes["cooldown"] += 1
                return None
            out: list[list[dict[str, Any]]] = []
            for i in range(0, len(texts), _MAX_TEXTS_PER_CALL):
                part = self._call(texts[i : i + _MAX_TEXTS_PER_CALL])
                if part is None:
                    return None
                out.extend(part)
            self.outcomes["ok"] += 1
            log.debug("pii_model", outcome="ok", texts=len(texts), spans=sum(len(s) for s in out))
            return out

    def _call(self, texts: list[str]) -> list[list[dict[str, Any]]] | None:
        try:
            resp = self._client.post(PII_PATH, json={"texts": texts})
        except EgressRefused:
            self._fail("refused", len(texts))
            return None
        except httpx.TimeoutException:
            self._fail("timeout", len(texts))
            return None
        except httpx.HTTPError as exc:
            self._fail(f"network_error:{type(exc).__name__}", len(texts))
            return None
        if resp.status_code != 200:
            self._fail(f"http_{resp.status_code}", len(texts))
            return None
        if len(resp.content) > _MAX_BODY:
            self._fail("oversized", len(texts))
            return None
        try:
            doc = json.loads(resp.content)
        except ValueError:
            self._fail("bad_json", len(texts))
            return None
        spans = _validate(doc, texts)
        if spans is None:
            self._fail("bad_response", len(texts))
        return spans


def _validate(doc: Any, texts: list[str]) -> list[list[dict[str, Any]]] | None:
    """The response's spans when every one is well formed, else ``None`` (the whole answer is refused)."""
    spans = doc.get("spans") if isinstance(doc, dict) else None
    if not isinstance(spans, list) or len(spans) != len(texts):
        return None
    out: list[list[dict[str, Any]]] = []
    for text, row in zip(texts, spans, strict=True):
        if not isinstance(row, list):
            return None
        good: list[dict[str, Any]] = []
        for s in row:
            if not isinstance(s, dict):
                return None
            start, end, label = s.get("start"), s.get("end"), s.get("label")
            if type(start) is not int or type(end) is not int or not isinstance(label, str):
                return None
            if not (0 <= start < end <= len(text)) or len(label) > _MAX_LABEL:
                return None
            good.append({"start": start, "end": end, "label": label})
        out.append(good)
    return out


# ── configuration ────────────────────────────────────────────────────────────────────────────────────────────────

_state: dict[str, Any] = {"loaded": False, "detector": None}
_state_lock = threading.Lock()


def _float_env(env: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(env.get(key, default))
    except (TypeError, ValueError):
        return default


def detector_from_env(env: Mapping[str, str] | None = None) -> HttpPiiDetector | None:
    """The detector the environment asks for, or ``None`` (OFF, the default; or a refused URL, logged)."""
    env = os.environ if env is None else env
    if str(env.get(ENV_FLAG, "")).strip().lower() not in _TRUE:
        return None
    try:
        det = HttpPiiDetector(
            str(env.get(ENV_URL, "")),
            timeout=_float_env(env, ENV_TIMEOUT, 3.0),
            cooldown_sec=_float_env(env, ENV_COOLDOWN, 60.0),
        )
    except ValueError as exc:
        log.warning("pii_model", outcome="refused_url", reason=str(exc)[:120], fallback="rules_only")
        return None
    log.info("pii_model", outcome="enabled", url=det.base_url)
    return det


def configured() -> SpanSource | None:
    """The process-wide detector: :func:`set_detector`'s, else :func:`detector_from_env` (read once)."""
    with _state_lock:
        if not _state["loaded"]:
            _state["detector"] = detector_from_env()
            _state["loaded"] = True
        return _state["detector"]


def set_detector(detector: SpanSource | None) -> None:
    """Use ``detector`` (``None``: the model check is off) instead of the environment's."""
    with _state_lock:
        _state["detector"] = detector
        _state["loaded"] = True


def reset() -> None:
    """Forget the configured detector (the environment is read again on next use)."""
    with _state_lock:
        det = _state["detector"]
        _state["detector"] = None
        _state["loaded"] = False
    if isinstance(det, HttpPiiDetector):
        det.close()


# ── the place guard ──────────────────────────────────────────────────────────────────────────────────────────────

_LATIN_ROAD = "road|rd|marg|avenue|ave|street|st|setu|lane|metro|sarani"
#: Mumbai's place nouns (and the second city pack's): "Chowk", "Naka", "Circle", "Udyan", "Baug", "Subway",
#: "Terminus", "Chowpatty", "Nagar" is not one (it is also a surname).
_LATIN_PLACE = (
    "Park|Bag|Baug|Udyan|Square|Chowk|Naka|Circle|Ghat|Bridge|Crossing|Station|Terminus|Airport|Sadan|Bhavan|Bhawan"
    "|Mandir|Market|Mandai|Bazar|Bazaar|Stadium|Hospital|College|Gardens|Maidan|Flyover|Subway|Chowpatty|Highway"
    "|Bypass|Causeway|Sea Link|Expressway"
)
_INDIC_PLACE = (
    "मार्ग|रोड|चौक|नाका|पथ|उद्यान|बाग|पूल|पुल|उड्डाणपूल|सेतू|सेतु|स्थानक|टर्मिनस|पार्क|मैदान|चौपाटी|रुग्णालय|हॉस्पिटल"
    "|विमानतळ|भवन|सदन|मंडई|बाजार|सबवे|महामार्ग"
    "|एवेन्यू|सरणी|स्ट्रीट|बाग़|लेन|स्क्वायर|घाट|ब्रिज|मेट्रो|हवाई|बाईपास|अस्पताल"
    "|রোড|সরণি|সরণী|স্ট্রিট|সেতু|পার্ক|সরোবর|বাগ|লেন|ঘাট|ব্রিজ|মেট্রো|বিমানবন্দর|ভবন|উড়ালপুল|বাইপাস"
)
_IL = "ऀ-ൿ‌‍"
#: Up to six capitalised words, then a road word (any case) or a capitalised place word: "Senapati Bapat Marg".
_LATIN_RUN_RE = re.compile(
    rf"(?<![\w])(?:[A-Z][\w'’.&-]*\s+){{1,6}}(?:(?i:{_LATIN_ROAD})|{_LATIN_PLACE})\.?(?![\w])"
    rf"(?:\s+(?i:{_LATIN_ROAD}|{_LATIN_PLACE})(?![\w]))*"
)
#: Up to three Marathi or Devanagari words, then a place word with any case ending: "आचार्य अत्रे चौकात".
_INDIC_RUN_RE = re.compile(
    rf"(?<![{_IL}])(?:[{_IL}]+[ \t]+){{1,3}}(?:{_INDIC_PLACE})[{_IL}]*(?:[ \t]+(?:{_INDIC_PLACE})[{_IL}]*)*"
)
_ASCII_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_INDIC_WORD_RE = re.compile(rf"[{_IL}]+")


def _ikey(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKC", word) if unicodedata.category(c) != "Cf")


def _same_indic(word: str, form: str) -> bool:
    """An Indic word is a place form with at most three more characters (a case ending) or its oblique form."""
    if word == form:
        return True
    if len(form) < 2 or len(word) - len(form) > 3:
        return False
    return word.startswith(form) or (len(form) >= 3 and word[: len(form) - 1] == form[:-1])


def protected_regions(text: str, protect: frozenset[str]) -> tuple[list[tuple[int, int]], set[tuple[int, int]]]:
    """``(regions, single_words)``: where ``text`` names a protected place (clipped out of any model span), and the
    single-word aliases (a model span that is exactly one is dropped)."""
    regions: list[tuple[int, int]] = []
    single: set[tuple[int, int]] = set()
    multi = {p for p in protect if " " in p}
    longest = max((p.count(" ") + 1 for p in multi), default=0)
    words = [(m.start(), m.end(), m.group(0).lower()) for m in _ASCII_WORD_RE.finditer(text)]
    for i, (s, e, w) in enumerate(words):
        if w in protect:
            single.add((s, e))
        for n in range(min(longest, len(words) - i), 1, -1):
            if " ".join(x[2] for x in words[i : i + n]) in multi:
                regions.append((s, words[i + n - 1][1]))
                break
    if not text.isascii():
        forms, phrases = ethics.indic_place_forms()
        iw = [(m.start(), m.end(), _ikey(m.group(0))) for m in _INDIC_WORD_RE.finditer(text)]
        for i, (s, e, k) in enumerate(iw):
            if any(_same_indic(k, f) for f in forms):
                single.add((s, e))
            for phrase in phrases.get(k, ()):
                n = len(phrase)
                if i + n <= len(iw) and all(iw[i + t][2] == phrase[t] for t in range(n - 1)) and _same_indic(
                    iw[i + n - 1][2], phrase[-1]
                ):
                    regions.append((s, iw[i + n - 1][1]))
                    break
    known_ends = {e: s for s, e in regions}
    for rx in (_LATIN_RUN_RE, _INDIC_RUN_RE):
        for m in rx.finditer(text):
            if m.end() in known_ends and known_ends[m.end()] > m.start():
                continue  # a known place name ends the run: the words before it are not taken
            regions.append((m.start(), m.end()))
    return regions, single


def _clip(text: str, start: int, end: int, regions: Iterable[tuple[int, int]], single: set[tuple[int, int]]
          ) -> list[tuple[int, int]]:
    pieces = [(start, end)]
    for rs, re_ in regions:
        nxt: list[tuple[int, int]] = []
        for s, e in pieces:
            if re_ <= s or rs >= e:
                nxt.append((s, e))
                continue
            if s < rs:
                nxt.append((s, rs))
            if re_ < e:
                nxt.append((re_, e))
        pieces = nxt
    out: list[tuple[int, int]] = []
    for s, e in pieces:
        while s < e and not (text[s].isalnum() or unicodedata.category(text[s])[0] == "M"):
            s += 1
        while e > s and not (text[e - 1].isalnum() or unicodedata.category(text[e - 1])[0] == "M"):
            e -= 1
        if e > s and any(c.isalnum() for c in text[s:e]) and (s, e) not in single:
            out.append((s, e))
    return out


def model_spans(text: str, found: Iterable[Mapping[str, Any]], tier: str, protect: frozenset[str]) -> tuple[Span, ...]:
    """The model's spans for one text as redaction spans: mapped labels only, clipped off every protected place."""
    wanted = [
        (int(d["start"]), int(d["end"]), _KINDS[d["label"]])
        for d in found
        if d.get("label") in _KINDS and not (tier == _OFFICIAL and _KINDS[d["label"]] == "contact")
    ]
    if not wanted:
        return ()
    regions, single = protected_regions(text, protect)
    out: list[Span] = []
    for s, e, kind in wanted:
        out.extend(Span(a, b, kind, "model") for a, b in _clip(text, s, e, regions, single))
    return tuple(out)


def extra_spans(texts: Sequence[str], tier: str, protect: frozenset[str]) -> list[tuple[Span, ...]]:
    """One document's model spans, one tuple per text (all empty when the model check is off or unavailable)."""
    empty: list[tuple[Span, ...]] = [() for _ in texts]
    detector = configured()
    if detector is None:
        return empty
    sent = [i for i, t in enumerate(texts) if t and t.strip()]
    if not sent:
        return empty
    asked = [texts[i] for i in sent]
    try:
        found = detector.spans(asked)
    except Exception as exc:  # noqa: BLE001 - a detector must never break a parse: rules only
        log.warning("pii_model", outcome=f"crashed:{type(exc).__name__}", fallback="rules_only")
        return empty
    if found is None:
        return empty
    checked = _validate({"spans": found}, asked)
    if checked is None:
        log.warning("pii_model", outcome="bad_response", texts=len(asked), fallback="rules_only")
        return empty
    out = list(empty)
    for i, spans in zip(sent, checked, strict=True):
        out[i] = model_spans(texts[i], spans, tier, protect)
    return out
