"""Plain-English and Marathi rationale for a proposal.

The twin and the ranking choose the timing. The local LLM only explains a
result that is already fixed, and every number it writes must come from the
facts it was given (``validate_numbers``). If the LLM is off, busy,
unreachable, slow (20 s timeout) or writes a number that is not in the
facts, a template rationale is used instead and the response says so.

The LLM server is shared with a live system: the twin makes at most one
call at a time (a non-blocking lock; a second request gets the template
rather than queueing behind the first): one short call for English, then
one for Marathi, each with a small token budget. Each language is checked
on its own (numbers, length, and for Marathi the script: no stray Latin
words beyond the place names in the facts, no other script).
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass

import httpx

log = logging.getLogger("sajag_twin.rationale")

__all__ = ["Explainer", "facts_for", "numbers_in", "template_rationale", "validate_numbers"]

_MR_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_SIMPLE_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    """Every number written in ``text`` (Western or Marathi digits), as abs floats."""
    t = text.translate(_MR_DIGITS).replace(",", "")
    return [abs(float(m)) for m in _SIMPLE_NUM_RE.findall(t)]


def validate_numbers(text: str, allowed: set[float]) -> list[float]:
    """Numbers in ``text`` that are not in ``allowed`` (empty list = valid)."""
    bad = []
    for x in numbers_in(text):
        if not any(abs(x - a) < 1e-9 for a in allowed):
            bad.append(x)
    return bad


@dataclass
class Facts:
    text: str  # the facts block given to the LLM (and the source of allowed numbers)
    allowed: set[float]
    fields: dict


def _fmt(x: float) -> str:
    x = float(x)
    return str(int(round(x))) if abs(x - round(x)) < 1e-9 else f"{x:.1f}"


def facts_for(proposal: dict) -> Facts:
    """The numbers and names a rationale may use, from the proposal object only."""
    m = proposal["twin_metrics"]
    names = ", ".join(x["name"] for x in proposal.get("junctions", []))
    names_mr = ", ".join(x.get("name_mr") or x["name"] for x in proposal.get("junctions", []))
    fields = {
        "junction": names,
        "junction_mr": names_mr,
        "change": proposal["change"]["summary"],
        "change_mr": proposal["change"].get("summary_mr") or proposal["change"]["summary"],
        "delay_change_pct": _fmt(m["delay_change_pct"]),
        "max_queue_change_m": _fmt(m["max_queue_change_m"]),
        "cross_street_delay_change_pct": _fmt(m["cross_street_delay_change_pct"]),
        "network_delay_change_pct": _fmt(m["network_delay_change_pct"]),
        "horizon_min": _fmt(m["horizon_min"]),
        "duration_min": _fmt(proposal["duration_min"]),
        "demand_label": proposal.get("demand", {}).get("label", "SIMULATED"),
    }
    text = (
        f"Junction: {fields['junction']} ({fields['junction_mr']}).\n"
        f"Change: {fields['change']}\n"
        f"Change (Marathi): {fields['change_mr']}\n"
        f"Twin result over {fields['horizon_min']} min, change against doing nothing (negative = better):\n"
        f"- change in delay at the junction: {fields['delay_change_pct']}%\n"
        f"- change in the longest queue: {fields['max_queue_change_m']} m\n"
        f"- change in cross-street delay: {fields['cross_street_delay_change_pct']}%\n"
        f"- change in delay across the network: {fields['network_delay_change_pct']}%\n"
        f"Demand: {fields['demand_label']}. Result: MODELLED (traffic model, not measured).\n"
        "A named officer decides; if no one decides, the current plan holds."
    )
    return Facts(text=text, allowed=set(numbers_in(text)), fields=fields)


def _dir_en(v: str, up: str, down: str) -> str:
    x = float(v)
    if abs(x) < 1e-9:
        return "does not change"
    return f"{up if x > 0 else down} by {_fmt(abs(x))}"


def _dir_mr(v: str, unit: str) -> str:
    x = float(v)
    if abs(x) < 1e-9:
        return "बदल नाही"
    return f"{_fmt(abs(x))}{unit} {'वाढ' if x > 0 else 'घट'}"


def template_rationale(proposal: dict) -> dict:
    f = facts_for(proposal).fields
    en = (
        f"{f['change']} In the twin (a traffic model, {f['demand_label']} demand) over {f['horizon_min']} min, "
        f"delay at {f['junction']} {_dir_en(f['delay_change_pct'], 'rises', 'falls')}%, the longest queue "
        f"{_dir_en(f['max_queue_change_m'], 'grows', 'shrinks')} m and cross-street delay "
        f"{_dir_en(f['cross_street_delay_change_pct'], 'rises', 'falls')}%. "
        "A named officer decides; if no one decides, the current plan holds."
    ).replace("does not change m", "does not change").replace("does not change%", "does not change")
    mr = (
        f"{f['change_mr']} ट्विन मॉडेलमध्ये ({f['demand_label']} मागणी) {f['horizon_min']} मिनिटांत {f['junction_mr']} येथे विलंब: "
        f"{_dir_mr(f['delay_change_pct'], '%')}, सर्वात लांब रांग: {_dir_mr(f['max_queue_change_m'], ' मीटर')}, "
        f"आडव्या रस्त्यावरील विलंब: {_dir_mr(f['cross_street_delay_change_pct'], '%')}। "
        "निर्णय एक नामनिर्दिष्ट अधिकारी घेतील; कोणीही निर्णय न घेतल्यास सध्याची योजना कायम राहील।"
    )
    return {"en": en, "mr": mr, "source": {"en": "template", "mr": "template"}, "validated": True}


_RULES = (
    "You explain a traffic-signal proposal to a Mumbai Traffic Police duty officer. "
    "Use ONLY the facts given. Never add, change or round a number; copy numbers exactly as written. "
    "Do not say the change has been made: it is a proposal awaiting a named officer's decision. "
)
_SYSTEM = {
    "en": _RULES + "Reply in plain English: at most two short sentences, no lists, no JSON.",
    "mr": _RULES
    + "Reply in Marathi only (standard Marathi in Devanagari script, Western digits): at most two short sentences, "
    "no lists, no JSON, no English words except place names. Words to use: twin = ट्विन मॉडेल, proposal = प्रस्ताव, "
    "queue = रांग, delay = विलंब, cross street = आडवा रस्ता, signal = सिग्नल, green = हिरवा, officer = अधिकारी.",
}
_LIMIT = {"en": 800, "mr": 1000}
_LATIN_WORD = re.compile(r"[A-Za-z]{3,}")
_FOREIGN_SCRIPT = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff]")


def script_problem(text: str, lang: str, facts_text: str) -> str | None:
    """Why a reply is not clean text in its language (None = clean)."""
    if _FOREIGN_SCRIPT.search(text):
        return "contains another script"
    if lang == "mr":
        if not re.search(r"[\u0900-\u097f]", text):
            return "not Marathi"
        known = {w.lower() for w in _LATIN_WORD.findall(facts_text)}
        stray = [w for w in _LATIN_WORD.findall(text) if w.lower() not in known]
        if stray:
            return f"stray Latin words {stray[:3]}"
    return None


def _clean(content: str) -> str:
    """The reply's text: code fences dropped, and a one-string JSON envelope
    (``{"response": "..."}``, as some local models answer) unwrapped."""
    t = (content or "").strip()
    t = re.sub(r"^```\w*\s*|\s*```$", "", t).strip()
    if t.startswith("{") and t.endswith("}"):
        try:
            obj = json.loads(t)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            strings = [v for v in obj.values() if isinstance(v, str) and v.strip()]
            if len(strings) == 1:
                t = strings[0].strip()
    return t.strip('"').strip()


class Explainer:
    """Rationale via the local OpenAI-compatible LLM, with a template fallback."""

    _lock = threading.Lock()  # process-wide: one LLM call at a time

    def __init__(self, base_url: str | None, *, enabled: bool = True, timeout_s: float = 20.0,
                 transport: httpx.BaseTransport | None = None, model: str | None = None):
        self.base_url = (base_url or "").rstrip("/")
        self.enabled = enabled and bool(self.base_url)
        self.timeout_s = timeout_s
        self._transport = transport
        self.model = model

    def explain(self, proposal: dict, *, use_llm: bool = True) -> dict:
        tpl = template_rationale(proposal)
        if not (use_llm and self.enabled):
            tpl["llm"] = "off"
            return tpl
        facts = facts_for(proposal)
        if not self._lock.acquire(blocking=False):
            tpl["llm"] = "busy: one call at a time; template used"
            return tpl
        # one short call per language, in turn, under the same lock
        try:
            replies = {lang: self._call(facts.text, lang) for lang in ("en", "mr")}
        finally:
            self._lock.release()
        if all(v is None for v in replies.values()):
            tpl["llm"] = "unavailable; template used"
            return tpl
        # each language is validated on its own; a missing or invalid one falls back to the template
        result: dict = {"source": {}, "validated": True, "llm": "ok"}
        notes = []
        for lang in ("en", "mr"):
            txt = _clean(replies[lang] or "")
            why = None
            if not txt:
                why = "missing"
            elif len(txt) > _LIMIT[lang]:
                why = "too long"
            else:
                bad = validate_numbers(txt, facts.allowed)
                if bad:
                    why = f"numbers not in the twin metrics {sorted(set(bad))[:5]}"
                else:
                    why = script_problem(txt, lang, facts.text)
            if why is None:
                result[lang], result["source"][lang] = txt, "llm"
            else:
                result[lang], result["source"][lang] = tpl[lang], "template"
                notes.append(f"{lang}: {why}")
        if notes:
            result["llm"] = "partly used; template for " + "; ".join(notes) if len(notes) < 2 else "rejected; template used (" + "; ".join(notes) + ")"
        return result

    def _call(self, facts_text: str, lang: str) -> str | None:
        body: dict = {
            "messages": [
                {"role": "system", "content": _SYSTEM[lang]},
                {"role": "user", "content": facts_text},
            ],
            "temperature": 0.2,
            "max_tokens": 300,
        }
        if self.model:
            body["model"] = self.model
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout_s, transport=self._transport) as c:
                r = c.post("/v1/chat/completions", json=body)
            if r.status_code != 200:
                return None
            content = r.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            log.info("rationale LLM call failed: %s", type(exc).__name__)
            return None
        return content if isinstance(content, str) else None
