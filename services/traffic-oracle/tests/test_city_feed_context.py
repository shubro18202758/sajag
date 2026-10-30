"""Reports vs district context in the surfaced-situation row (FIX-C).

A situation's C-T ``source_count`` counts EVERY member — a district-level
alert attached to a point situation (source role ``context``, migration 023)
included.  Context is shown to the operator, never counted as corroboration:

    * the feed row counts REPORTS — ``source_count`` minus the context
      members ("1 report", "2 reports") — and, when the provenance carries
      context publishers, appends the area alert BESIDE the count
      (" · district warning in effect"), never inside it;
    * a situation with no context member reads exactly as before, bar the
      report wording;
    * the read supplies the context count as its own additive column
      (``context_members``), so the C-T contract itself never moves.

Pure converter tests: synthetic rows shaped like _SQL_FEED_OSINT_SURFACED,
no database, no network.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from traffic_oracle.city import common
from traffic_oracle.city import feed as feed_mod

NOW = datetime.now(timezone.utc)


def _surfaced(source_count: int, context_members: int = 0,
              context_publishers: list[str] | None = None,
              context_official: bool = True, **kw: Any) -> dict:
    """One synthetic _SQL_FEED_OSINT_SURFACED row: a point situation standing
    on ``source_count`` members, ``context_members`` of them district alerts
    (role 'context')."""
    row = {
        "osint_event_id": "2f0c1b4e-1111-4222-8333-444455556666",
        "label": "Road accident",
        "event_class": "road_accident",
        "sajag_event_kind": "road_accident",
        "verification_state": "NEWS-REPORTED",
        "credibility": 0.65,
        "source_count": source_count,
        "toponym": "Sector V, Salt Lake",
        "segment_id": 1045,
        "junction_id": None,
        "promoted_event_id": None,
        "created_at": NOW,
        "geocode_confidence": 0.719,
        "second_order": None,
        "area_level": False,
        "context_members": context_members,
        "source_feeds": ["google_news_rss", "sachet_cap"],
        "publishers": ["news-a.example"],
        "links_withheld": 0,
        "geocoder": "gazetteer_exact",
        "context_publishers": context_publishers,
        "context_official": bool(context_publishers) and context_official,
    }
    row.update(kw)
    return row


class TestSurfacedContext:
    def test_one_report_plus_a_context_alert_says_so(self):
        item = feed_mod.osint_surfaced_item(
            _surfaced(2, context_members=1, context_publishers=["sdma.example"])
        )
        assert item["text"] == (
            "Situation surfaced: Road accident · News-reported · "
            "1 report · district warning in effect"
        )
        prov = item["props"]["provenance"]
        assert prov["context_publishers"] == ["sdma.example"]
        assert prov["context_note"] == common.OSINT_CONTEXT_NOTE
        assert item["props"]["source_count"] == 1  # reports only

    def test_two_reports_without_context_read_plainly(self):
        item = feed_mod.osint_surfaced_item(_surfaced(2))
        assert item["text"] == (
            "Situation surfaced: Road accident · News-reported · 2 reports"
        )
        assert "context_publishers" not in item["props"]["provenance"]
        assert "context_note" not in item["props"]["provenance"]
        assert item["props"]["source_count"] == 2

    def test_context_is_never_counted_as_a_report(self):
        # two reports + one context alert: the count stays 2, the alert rides
        # beside it (the non-official wording: a district-level REPORT)
        item = feed_mod.osint_surfaced_item(
            _surfaced(3, context_members=1, context_publishers=["imd.example"],
                      context_official=False)
        )
        assert item["text"].endswith("· 2 reports · district-level report in effect")
        assert item["props"]["source_count"] == 2

    def test_a_row_without_the_column_counts_every_member(self):
        # a pre-FIX row (or an older reader): no context_members column —
        # the count degrades to source_count, never below one report
        row = _surfaced(2)
        del row["context_members"]
        assert feed_mod.osint_surfaced_item(row)["props"]["source_count"] == 2

    def test_the_read_counts_context_members_in_its_own_column(self):
        sql = feed_mod._SQL_FEED_OSINT_SURFACED
        assert ("(SELECT count(*) FROM osint.event_sources es WHERE "
                "es.osint_event_id = r.osint_event_id AND es.role = 'context') "
                "AS context_members") in sql
        assert " AS context_members, " + common.OSINT_PROVENANCE_COLUMNS in sql
