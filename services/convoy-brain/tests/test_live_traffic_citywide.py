"""get_live_traffic with no segment named reads the whole city (deck audit, 29 Oct).

The assistant was asked "Which roads in Mumbai are the most congested right
now?"; Gemma drafted ``get_live_traffic {"segment_ids": []}``, the oracle
answered nothing for nothing, and the answer said "no roads are congested"
while the live feed held 65 observations. An empty or missing list is now a
city-wide read, labelled as such, worst segments first; an empty city-wide
answer says congestion is UNKNOWN, never low.
"""

from __future__ import annotations

import json

import httpx
import pytest

from convoy_brain.llm.heuristics import heuristic_default_arguments, summarize_tool_result
from convoy_brain.mcp.server import (
    CITY_WIDE_LIVE_MAX_SEGMENTS,
    TOOL_DEFINITIONS,
    ToolExecutor,
    _most_congested,
)

pytestmark = pytest.mark.asyncio


def _obs(sid: int, cong: float, speed: float, name: str) -> dict:
    return {"segment_id": sid, "congestion_idx": cong, "speed_kmh": speed, "road_name": name,
            "data_quality": "synthetic", "origin": "live", "source": "government_traffic"}


def _oracle(segments: list[int], observations: list[dict], seen: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/spatial/segments":
            seen["bbox"] = dict(request.url.params)
            return httpx.Response(200, json={"segments": [{"segment_id": s} for s in segments]})
        if request.url.path == "/api/v1/traffic/live":
            seen.setdefault("live", []).append(json.loads(request.content))
            return httpx.Response(200, json={"observations": observations, "emulated_observations": []})
        return httpx.Response(404, json={"detail": "unexpected " + request.url.path})
    return ToolExecutor(
        traffic_oracle_url="http://oracle",
        client=httpx.AsyncClient(base_url="http://oracle", transport=httpx.MockTransport(handler)),
    )


@pytest.mark.parametrize("args", [{}, {"segment_ids": []}, {"segment_ids": None}])
async def test_no_segment_named_reads_every_city_segment(args):
    seen: dict = {}
    obs = [_obs(1001, 0.19, 34.7, "Howrah Bridge (Rabindra Setu)"),
           _obs(1004, 0.91, 8.0, "Strand Road"),
           _obs(1010, 0.75, 14.0, "Park Street")]
    ex = _oracle([1010, 1001, 1004], obs, seen)
    out = await ex.dispatch("get_live_traffic", args)
    await ex.close()
    assert seen["live"] == [{"segment_ids": [1001, 1004, 1010]}]
    assert set(seen["bbox"]) == {"min_lon", "min_lat", "max_lon", "max_lat"}
    assert out["scope"]["kind"] == "city" and out["scope"]["segments_asked"] == 3
    assert [r["segment_id"] for r in out["most_congested"]] == [1004, 1010, 1001]
    # the row's own labels ride along: a simulated feed is never shown as measured
    assert out["most_congested"][0]["data_quality"] == "synthetic"
    assert len(out["observations"]) == 3
    # the ranking leads the result (context caps lists and truncates the rendered tail)
    assert list(out)[:2] == ["scope", "most_congested"]


async def test_named_segments_are_sent_as_given():
    seen: dict = {}
    ex = _oracle([1001, 1004], [_obs(1004, 0.5, 20.0, "Strand Road")], seen)
    out = await ex.dispatch("get_live_traffic", {"segment_ids": [1004]})
    await ex.close()
    assert seen["live"] == [{"segment_ids": [1004]}]
    assert "bbox" not in seen and "scope" not in out


async def test_city_wide_read_is_capped():
    seen: dict = {}
    ex = _oracle(list(range(1, 500)), [], seen)
    out = await ex.dispatch("get_live_traffic", {})
    await ex.close()
    assert len(seen["live"][0]["segment_ids"]) == CITY_WIDE_LIVE_MAX_SEGMENTS
    assert out["most_congested"] == []


async def test_no_segments_at_all_never_posts_an_empty_list():
    seen: dict = {}
    ex = _oracle([], [], seen)
    out = await ex.dispatch("get_live_traffic", {})
    await ex.close()
    assert "live" not in seen
    assert out["scope"]["segments_asked"] == 0 and out["observations"] == []


def test_schema_no_longer_requires_ids_and_says_omit_for_city():
    tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "get_live_traffic")
    assert tool["inputSchema"]["required"] == []
    assert "WHOLE city" in tool["description"]


def test_default_arguments_without_ids_are_the_city_wide_read():
    assert heuristic_default_arguments("get_live_traffic", {}) == {"segment_ids": []}


def test_city_wide_summary_ranks_the_worst_and_keeps_the_label():
    result = {"observations": [_obs(1001, 0.19, 34.7, "Howrah Bridge (Rabindra Setu)"),
                               _obs(1004, 0.91, 8.0, "Strand Road")],
              "scope": {"kind": "city", "segments_asked": 65}}
    text = summarize_tool_result("get_live_traffic", {}, result)
    assert "city-wide, 2 of 65 segments observed" in text
    assert text.index("Strand Road (1004)") < text.index("Howrah Bridge")
    assert "SIMULATED FEED" in text


def test_empty_city_wide_answer_is_unknown_not_low():
    for args, result in (({}, {"observations": [], "scope": {"kind": "city", "segments_asked": 65}}),
                         ({"segment_ids": []}, {"observations": []})):
        text = summarize_tool_result("get_live_traffic", args, result)
        assert "UNKNOWN, not low" in text
        assert "segments []" not in text


def test_most_congested_skips_malformed_rows():
    rows = [{"segment_id": True, "congestion_idx": 0.9}, {"segment_id": 3, "congestion_idx": "x"},
            {"segment_id": 4, "congestion_idx": 0.4, "speed_kmh": None}, "junk"]
    assert [r["segment_id"] for r in _most_congested(rows)] == [4]
