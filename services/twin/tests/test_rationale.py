"""The LLM only explains: every number it writes must come from the twin metrics."""

from __future__ import annotations

import json
import threading

import httpx
import pytest

from sajag_twin.rationale import Explainer, facts_for, numbers_in, template_rationale, validate_numbers


def proposal(delay=-6.6, queue=-12.0, cross=13.1, net=-0.1) -> dict:
    return {
        "junctions": [{"junction_id": 20, "name": "Dadar TT Circle", "name_mr": "दादर टीटी सर्कल"}],
        "change": {
            "summary": "Give the main-road (through) movement at Dadar TT Circle 6 s more green for 30 min "
                       "(taken from the cross-street movement; cycle 110 s unchanged).",
            "summary_mr": "दादर टीटी सर्कल येथे मुख्य रस्त्याच्या सिग्नलला 30 मिनिटांसाठी 6 सेकंद अधिक हिरवा "
                          "(आडव्या रस्त्याच्या वेळेतून घेतलेला; चक्र 110 सेकंद, न बदलता)।",
        },
        "duration_min": 30.0,
        "twin_metrics": {"horizon_min": 45, "delay_change_pct": delay, "max_queue_change_m": queue,
                         "cross_street_delay_change_pct": cross, "network_delay_change_pct": net},
        "demand": {"label": "SIMULATED"},
    }


def test_numbers_in_reads_signs_decimals_and_marathi_digits():
    assert numbers_in("delay -6.6% and +13.1%, 45 min") == [6.6, 13.1, 45.0]
    assert numbers_in("विलंब ६.६% घट, ४५ मिनिटांत") == [6.6, 45.0]
    assert numbers_in("1,200 PCU") == [1200.0]
    assert numbers_in("no numbers here") == []


def test_validator_flags_numbers_not_in_the_metrics():
    allowed = facts_for(proposal()).allowed
    assert validate_numbers("Delay falls by 6.6% over 45 min; cross-street delay rises by 13.1%.", allowed) == []
    assert validate_numbers("Delay falls by 35% at Dadar TT.", allowed) == [35.0]
    assert validate_numbers("विलंब ७% घट", allowed) == [7.0]  # 6.6 rounded is still a new number
    assert validate_numbers("विलंब ६.६% घट", allowed) == []


@pytest.mark.parametrize("args", [(-6.6, -12.0, 13.1, -0.1), (-21.0, 0.0, -3.5, -1.2), (-3.0, 40.0, 0.0, 0.0)])
def test_template_uses_only_metric_numbers(args):
    p = proposal(*args)
    t = template_rationale(p)
    allowed = facts_for(p).allowed
    assert validate_numbers(t["en"], allowed) == []
    assert validate_numbers(t["mr"], allowed) == []
    assert "officer" in t["en"] and "अधिकारी" in t["mr"]


def _llm(replies: dict | str, status: int = 200, seen: list | None = None) -> httpx.MockTransport:
    """A fake OpenAI-compatible server: ``replies`` maps 'en'/'mr' to the text it returns."""
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        body = json.loads(request.content)
        lang = "mr" if "Marathi only" in body["messages"][0]["content"] else "en"
        content = replies if isinstance(replies, str) else replies.get(lang)
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})
    return httpx.MockTransport(handler)


def test_llm_text_is_used_when_every_number_is_in_the_metrics():
    seen: list = []
    good = {"en": "Six seconds more green for 30 min cuts delay by 6.6%; cross-street delay rises 13.1%.",
            "mr": "३० मिनिटांत विलंबात ६.६% घट; आडव्या रस्त्यावरील विलंबात १३.१% वाढ।"}
    ex = Explainer("http://llm.test", transport=_llm(good, seen=seen))
    r = ex.explain(proposal())
    assert r["source"] == {"en": "llm", "mr": "llm"} and r["en"] == good["en"]
    assert len(seen) == 2  # one short call per language, in turn
    for req in seen:
        assert req.method == "POST" and req.url.path == "/v1/chat/completions"
        body = json.loads(req.content)
        assert body["max_tokens"] <= 300 and len(body["messages"]) == 2
        assert "Never add, change or round a number" in body["messages"][0]["content"]


def test_llm_number_not_in_metrics_falls_back_to_template():
    bad = {"en": "Delay falls by 35% at Dadar TT Circle.", "mr": "विलंबात ६.६% घट।"}
    ex = Explainer("http://llm.test", transport=_llm(bad))
    r = ex.explain(proposal())
    assert r["source"] == {"en": "template", "mr": "llm"}
    assert "35" not in r["en"]
    assert "numbers not in the twin metrics" in r["llm"]


def test_a_json_envelope_is_unwrapped():
    wrapped = {"en": '{"response": "Delay falls by 6.6% over 45 min."}', "mr": '```\n{"answer": "विलंबात ६.६% घट।"}\n```'}
    r = Explainer("http://llm.test", transport=_llm(wrapped)).explain(proposal())
    assert r["source"] == {"en": "llm", "mr": "llm"}
    assert r["en"] == "Delay falls by 6.6% over 45 min." and r["mr"] == "विलंबात ६.६% घट।"


def test_marathi_with_stray_latin_or_another_script_is_rejected():
    mixed = {"en": "Delay falls by 6.6%.", "mr": "सर्वात kuyue बदल 6.6%"}
    r = Explainer("http://llm.test", transport=_llm(mixed)).explain(proposal())
    assert r["source"] == {"en": "llm", "mr": "template"} and "stray Latin" in r["llm"]
    cjk = {"en": "Delay falls by 6.6% 的.", "mr": "विलंबात ६.६% घट।"}
    r = Explainer("http://llm.test", transport=_llm(cjk)).explain(proposal())
    assert r["source"]["en"] == "template"
    names_ok = {"en": "Delay falls by 6.6%.", "mr": "Dadar TT Circle येथे विलंबात ६.६% घट।"}  # names from the facts are fine
    assert Explainer("http://llm.test", transport=_llm(names_ok)).explain(proposal())["source"]["mr"] == "llm"


def test_missing_language_and_errors_fall_back():
    ex = Explainer("http://llm.test", transport=_llm({"en": "Delay falls by 6.6%.", "mr": ""}))
    r = ex.explain(proposal())
    assert r["source"] == {"en": "llm", "mr": "template"}
    ex = Explainer("http://llm.test", transport=_llm("server error", status=500))
    assert ex.explain(proposal())["source"] == {"en": "template", "mr": "template"}

    def boom(request):
        raise httpx.ReadTimeout("slow", request=request)
    ex = Explainer("http://llm.test", transport=httpx.MockTransport(boom))
    r = ex.explain(proposal())
    assert r["source"] == {"en": "template", "mr": "template"} and "unavailable" in r["llm"]


def test_off_and_busy_never_call_the_llm():
    seen: list = []
    off = Explainer("http://llm.test", enabled=False, transport=_llm({"en": "x", "mr": "y"}, seen=seen))
    assert off.explain(proposal())["llm"] == "off"
    on = Explainer("http://llm.test", transport=_llm({"en": "x", "mr": "y"}, seen=seen))
    assert on.explain(proposal(), use_llm=False)["llm"] == "off"
    # one call at a time: while another call holds the lock, the template is used at once
    assert Explainer._lock.acquire(blocking=False)
    try:
        r = on.explain(proposal())
    finally:
        Explainer._lock.release()
    assert r["llm"].startswith("busy")
    assert seen == []
    assert isinstance(Explainer._lock, type(threading.Lock()))
