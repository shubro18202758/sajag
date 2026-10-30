"""Each parser over its fixture: counts and fields; defusedxml refuses hostile XML; GDELT never reads the actor
or person columns; the live fetch paths (through the real allow-list transport over a MockTransport)."""

from __future__ import annotations

import gzip
import json
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from conftest import CAPTURE, DEAD_ORACLE, HOSTILE, PAGES, Recorder, parse_cache

from osint_ingress.cache import Cache
from osint_ingress.connectors import build_connectors
from osint_ingress.connectors._area import CITY_CODE, GDELT_ADM1, STATE_CODE, SUBURBAN_CODE
from osint_ingress.config import Settings
from osint_ingress.connectors.base import (
    MAX_VALID_AHEAD,
    ConnectorDisabled,
    ConnectorError,
    canonical_url,
    parse_when,
    parse_xml,
    url_sha256,
)
from osint_ingress.connectors.common_crawl import CommonCrawl
from osint_ingress.connectors.gdelt import EVENT_COLUMNS, GdeltBulk, GdeltDoc, _Spacer
from osint_ingress.connectors.google_news import GoogleNews, without_display_name
from osint_ingress.connectors.official import BmcPage, MsdmaPage, MtpNotices, Sachet, cap_fields
from osint_ingress.connectors.reddit import Reddit
from osint_ingress.safe_http import ALLOWED_HOSTS, RobotsCache, make_source_client
from osint_ingress.service import build_runtime

SENTINEL = re.compile(r"sentinel", re.IGNORECASE)
IST = timezone(timedelta(hours=5, minutes=30))


def _client(handler) -> httpx.AsyncClient:
    return make_source_client(user_agent="sajag-osint-ingress/test", transport=httpx.MockTransport(handler))


# ── the synthetic capture, connector by connector ─────────────────────────────────────────────────────────────


def test_capture_counts_per_connector(capture_cache, connectors, protect):
    got = parse_cache(capture_cache, connectors, protect)
    assert {k: len(v) for k, v in got.items()} == {
        "sachet_cap": 7,
        "google_news_rss": 8,
        "news_rss": 6,
        "gdelt_events": 2,
        "gdelt_doc": 5,
        "reddit_rss": 4,
    }


def test_sachet_fields_and_area_levels(capture_cache, connectors, protect):
    conn = connectors["sachet_cap"]
    sigs = conn.parse(capture_cache.latest("sachet_cap"), protect)
    district = [s for s in sigs if s.raw_geo_hint.admin_codes == [CITY_CODE, SUBURBAN_CODE]]
    state = [s for s in sigs if s.raw_geo_hint.admin_codes == [STATE_CODE]]
    assert len(district) == 1 and len(state) == 6 and len(sigs) == 7
    assert conn.last_dropped["outside_area"] == 3  # Goa, the Saurashtra and Kutch coast, coastal Karnataka: not emitted
    assert "Mumbai, Mumbai Suburban" in district[0].title
    assert district[0].raw_geo_hint.place_names == ["Mumbai City", "Mumbai Suburban"]
    assert all(s.raw_geo_hint.place_names == ["Maharashtra"] for s in state)
    # the SDMA's sign-off "मंत्रालय, मुंबई" (the issuing office) never makes a Thane or Kolhapur nowcast a Mumbai one
    assert all("mumbai" not in (s.title + s.text).lower() for s in state)
    # the replica writes three nowcasts in Marathi, as Maharashtra SDMA does: the script and words set the language
    assert sorted(s.language for s in sigs) == ["en", "en", "en", "en", "mr", "mr", "mr"]
    for s in sigs:
        # the replica is synthetic: SIMULATED, never OFFICIAL-VERIFIED (F-HONEST OSINT-5)
        assert s.source_tier == "official" and s.provenance_label == "SIMULATED"
        assert s.credibility_prior == 0.95 and s.license == "public_domain" and s.redistributable is True
        assert s.publisher == "sachet.ndma.gov.in"
        # official tier keeps its identifier URL
        assert s.url and s.url.startswith("https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=")
        assert s.raw["cap_identifier"] == s.source_id and s.raw["cap_category"] == "Met"
        assert "CAP" in s.category_hint and "CAP:Met" in s.category_hint
        assert s.published_at is not None and s.fetch_mode == "cached-sample"
    assert {"area:mumbai", "area:mumbai_suburban"} <= set(district[0].category_hint)
    assert all("area:maharashtra" in s.category_hint for s in state)
    # the item that names no place ("in your district") is the state, by the Maharashtra feed it came from
    assert "1999000000000206" in {s.source_id for s in state}


def test_google_news_fields(capture_cache, connectors, protect):
    sigs = connectors["google_news_rss"].parse(capture_cache.latest("google_news_rss"), protect)
    assert {s.publisher for s in sigs} == {"news-a.example", "news-b.example"}
    for s in sigs:
        # the capture's news feed is developer-written: SIMULATED, never NEWS-REPORTED (F-HONEST OSINT-5)
        assert s.source_tier == "aggregator" and s.provenance_label == "SIMULATED"
        assert s.redistributable is False and s.license == "google_news_personal_use"
        assert s.url is None and s.raw_geo_hint.polygon_url is None  # news tier: link never emitted
        assert any(h.startswith("url_sha256:") for h in s.category_hint)
        # the <source> display name is never a hint (a personal blog's display name would be a person)
        assert not any(h.startswith("publisher:") for h in s.category_hint)
        assert s.source_id.startswith("SYNTHETIC-GNEWS-") and s.published_at is not None
        assert set(s.raw) <= {"source_domain", "pub_date"}
        # the <source> display name ("News A") is cut from the title and the description's <font> label
        assert not s.title.endswith((" - News A", " - News B"))
        assert "News A" not in s.title + s.text and "News B" not in s.title + s.text
    em = [s for s in sigs if "Western Express Highway" in s.title]
    assert len(em) == 5 and {s.language for s in sigs} == {"en"}


def test_google_news_display_name_is_cut_only_when_it_is_the_source_text():
    assert without_display_name("Fire near Kurla - Outlet C", "Outlet C") == "Fire near Kurla"
    assert without_display_name("Fire near Kurla  -  Outlet  C", " Outlet C ") == "Fire near Kurla"
    assert without_display_name("Fire near Kurla - Outlet D", "Outlet C") == "Fire near Kurla - Outlet D"
    assert without_display_name("Fire near Kurla", "") == "Fire near Kurla"


def test_google_news_display_name_never_reaches_a_signal(tmp_path, protect):
    # a fictional blog named after a (fictional) person: no cue word would reveal it, so it must not be emitted
    name = "Fictus Dummyvala Diaries"
    link = "https://news.google.com/rss/articles/SYNTHETIC-GNEWS-9001?oc=5"
    headline = "Waterlogging near Hindmata after heavy rain"
    desc = (f'&lt;a href="{link}" target="_blank"&gt;{headline}&lt;/a&gt;&amp;nbsp;&amp;nbsp;'
            f'&lt;font color="#6f6f6f"&gt;{name}&lt;/font&gt;')
    rss = f"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>synthetic</title>
<item><title>{headline} - {name}</title><link>{link}</link>
<guid isPermaLink="false">SYNTHETIC-GNEWS-9001</guid><pubDate>Tue, 20 Oct 2026 13:40:00 GMT</pubDate>
<description>{desc}</description>
<source url="https://outlet-c.example">{name}</source></item></channel></rss>"""
    entry = Cache(tmp_path).put("google_news_rss", rss.encode("utf-8"), "xml")
    (s,) = GoogleNews().parse(entry, protect)
    blob = json.dumps(s.model_dump(mode="json"), ensure_ascii=False)
    assert "Fictus" not in blob and "Dummyvala" not in blob and "Diaries" not in blob
    assert s.title == "Waterlogging near Hindmata after heavy rain" and s.publisher == "outlet-c.example"
    assert s.text == "Waterlogging near Hindmata after heavy rain. Waterlogging near Hindmata after heavy rain"


def test_google_news_guid_that_encodes_a_url_is_never_the_source_id(tmp_path, protect):
    """Review-r2 hardening: an old-format guid base64-encodes the publisher URL (a slug can name a person), so the
    link's url-sha256 stands in for it. Opaque guids (today's CBMi…AU_yqL… and the synthetic ones) are kept."""
    import base64

    from osint_ingress.connectors.base import url_sha256
    from osint_ingress.connectors.google_news import guid_embeds_url

    slug_url = b"https://news-a.example/2026/10/fictus-dummyvala-arrested"  # fictional
    old_guid = base64.urlsafe_b64encode(b"\x08\x13\x22" + bytes([len(slug_url)]) + slug_url).decode().rstrip("=")
    opaque = base64.urlsafe_b64encode(b"\x08\x13\x22\x10AU_yqLsyntheticId").decode().rstrip("=")
    assert guid_embeds_url(old_guid) and guid_embeds_url("https://news-a.example/x")
    assert not guid_embeds_url(opaque) and not guid_embeds_url("SYNTHETIC-GNEWS-0001")
    link = f"https://news.google.com/rss/articles/{old_guid}?oc=5"
    rss = f"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>synthetic</title>
<item><title>Waterlogging near Hindmata after heavy rain - Outlet A</title><link>{link}</link>
<guid isPermaLink="false">{old_guid}</guid><pubDate>Tue, 20 Oct 2026 13:40:00 GMT</pubDate>
<description>Waterlogging near Hindmata</description><source url="https://news-a.example">Outlet A</source></item>
<item><title>Fire near Kurla - Outlet A</title><link>https://news.google.com/rss/articles/{opaque}?oc=5</link>
<guid isPermaLink="false">{opaque}</guid><pubDate>Tue, 20 Oct 2026 13:41:00 GMT</pubDate>
<description>Fire near Kurla</description><source url="https://news-a.example">Outlet A</source></item>
</channel></rss>"""
    entry = Cache(tmp_path).put("google_news_rss", rss.encode("utf-8"), "xml")
    first, second = GoogleNews().parse(entry, protect)
    assert first.source_id == f"url-sha256:{url_sha256(link)}"
    assert old_guid not in json.dumps(first.model_dump(mode="json"))
    assert second.source_id == opaque


def test_gdelt_bulk_rows_and_levels(capture_cache, connectors, protect):
    sigs = connectors["gdelt_events"].parse(capture_cache.latest("gdelt_events"), protect)
    by_id = {s.source_id: s for s in sigs}
    assert set(by_id) == {"1300000001", "1300000002"}  # the Kolkata row (IN28, another state) is filtered out
    mum, pune = by_id["1300000001"], by_id["1300000002"]
    assert mum.raw_geo_hint.admin_codes == [f"GDELT_ADM1:{GDELT_ADM1}"] == ["GDELT_ADM1:IN16"]
    assert "area:mumbai" in mum.category_hint  # city hint: the FullName names Bombay (GDELT's spelling)
    assert "area:maharashtra" in pune.category_hint  # state hint only
    assert mum.raw_geo_hint.points == [(18.975, 72.8258)] and mum.raw_geo_hint.bbox_hit is True
    assert pune.raw_geo_hint.bbox_hit is False
    assert mum.url is None and mum.publisher == "news-a.example"
    assert mum.raw["action_geo_adm1_code"] == "IN16" and mum.raw["event_root_code"] == "01"
    assert mum.raw["source_url_domain"] == "news-a.example" and mum.tone == -1.5
    assert mum.source_tier == "news_wire" and mum.credibility_prior == 0.60


def test_gdelt_never_reads_actor_or_person_columns(capture_cache, connectors, protect):
    actor_columns = set(range(5, 25)) | set(range(35, 51))
    assert not set(EVENT_COLUMNS.values()) & actor_columns
    sigs = connectors["gdelt_events"].parse(capture_cache.latest("gdelt_events"), protect)
    blob = json.dumps([s.model_dump(mode="json") for s in sigs])
    # the fixture's actor names, codes and geographies are SENTINEL strings; none may reach a signal
    assert not SENTINEL.search(blob)
    assert "INDGOV" not in blob and "INDCVL" not in blob


def test_gdelt_doc_fields(capture_cache, connectors, protect):
    sigs = connectors["gdelt_doc"].parse(capture_cache.latest("gdelt_doc"), protect)
    assert len(sigs) == 5
    for s in sigs:
        assert s.source_id.startswith("url-sha256:") and len(s.source_id) == len("url-sha256:") + 64
        assert s.url is None and s.publisher in {"news-a.example", "news-b.example"}
        assert s.raw["source_country"] == "India" and "mumbai" in s.raw_geo_hint.place_names
    assert sorted(s.language for s in sigs) == ["en", "en", "en", "hi", "mr"]


def test_gdelt_doc_drops_court_record_portals(tmp_path, protect):
    doc = {"articles": [
        {"url": "https://indiankanoon.org/doc/1/", "title": "Placeholder caption (synthetic test item)",
         "seendate": "20261020T100000Z", "domain": "indiankanoon.org", "language": "English",
         "sourcecountry": "India"},
        {"url": "https://news-a.example/city/mumbai/x", "title": "Synthetic civic item in Mumbai",
         "seendate": "20261020T100000Z", "domain": "news-a.example", "language": "English",
         "sourcecountry": "India"},
    ]}
    cache = Cache(tmp_path)
    conn = GdeltDoc()
    sigs = conn.parse(cache.put("gdelt_doc", json.dumps(doc).encode(), "json"), protect)
    assert [s.publisher for s in sigs] == ["news-a.example"]
    assert conn.last_dropped["person_record_domain"] == 1


def test_reddit_fields(capture_cache, connectors, protect):
    sigs = connectors["reddit_rss"].parse(capture_cache.latest("reddit_rss"), protect)
    assert len(sigs) == 4
    for s in sigs:
        # synthetic posts: SIMULATED, in a fictional community, never attributed to r/mumbai (OSINT-5)
        assert s.source_tier == "social_unverified" and s.provenance_label == "SIMULATED"
        assert s.credibility_prior == 0.25 and s.redistributable is False
        assert s.publisher == "reddit.com/r/example_city" and s.category_hint[0] == "subreddit:example_city"
        assert s.url is None and s.raw["subreddit"] == "example_city" and s.source_id.startswith("t3_syn")
        assert "submitted by" not in s.text and "[link]" not in s.text and "[comments]" not in s.text


# ── hostile XML ───────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", ["xxe.xml", "billion_laughs.xml", "external_dtd.xml", "xxe_atom.rss"])
def test_defusedxml_refuses_hostile_documents(name):
    with pytest.raises(ConnectorError, match="XML refused"):
        parse_xml((HOSTILE / name).read_bytes())


@pytest.mark.parametrize(
    ("connector", "name"),
    [("google_news_rss", "xxe.xml"), ("sachet_cap", "billion_laughs.xml"), ("reddit_rss", "xxe_atom.rss")],
)
def test_connector_parse_refuses_hostile_cache_entry(tmp_path, protect, connector, name):
    cache = Cache(tmp_path)
    entry = cache.put(connector, (HOSTILE / name).read_bytes(), "xml")
    with pytest.raises(ConnectorError, match="XML refused"):
        build_connectors()[connector].parse(entry, protect)


async def test_live_fetch_refuses_hostile_feed_before_caching(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=(HOSTILE / "xxe.xml").read_bytes())

    cache = Cache(tmp_path)
    async with _client(handler) as client:
        with pytest.raises(ConnectorError, match="XML refused"):
            await GoogleNews().fetch(client, cache)
    assert cache.latest("google_news_rss") is None  # never cached as a good entry


# ── SACHET CAP detail and the official pages ──────────────────────────────────────────────────────────────────


def test_cap_detail_fields_never_read_contact_or_note():
    f = cap_fields((PAGES / "cap_detail_synthetic.xml").read_bytes())
    assert f["event"] == "Heavy Rain" and f["severity"] == "Severe" and f["lgd_codes"] == ["482", "483", "497"]
    assert f["polygon_url"].startswith("https://sachet.ndma.gov.in/cap_public_website/FetchPolygonXMLFile")
    assert "Contactwala" not in json.dumps(f) and "never be read" not in json.dumps(f)


async def test_sachet_fetch_caches_cap_details_and_parse_enriches(tmp_path, protect):
    rss = (PAGES / "sachet_rss_synthetic.xml").read_bytes()
    cap = (PAGES / "cap_detail_synthetic.xml").read_bytes()
    rec = Recorder({
        "sachet.ndma.gov.in/cap_public_website/rss/": lambda r: httpx.Response(200, content=rss),
        "sachet.ndma.gov.in/cap_public_website/FetchXMLFile": lambda r: (
            httpx.Response(200, content=cap) if r.url.params.get("identifier") == "1999000000000101"
            else httpx.Response(500)
        ),
    })
    cache = Cache(tmp_path)
    conn = Sachet()
    conn.detail_spacing_sec = 0
    async with _client(rec) as client:
        entry = await conn.fetch(client, cache)
    assert entry is not None and entry.fetch_mode == "live" and entry.blobs == ("cap-1999000000000101.xml",)
    # every Maharashtra alert gets a detail request: the Goa and Karnataka coast alert (...103) is never asked for
    asked = [r.url.params.get("identifier") for r in rec.requests if "FetchXMLFile" in r.url.path]
    assert asked == ["1999000000000101", "1999000000000102"]
    sigs = {s.source_id: s for s in conn.parse(entry, protect)}
    assert set(sigs) == {"1999000000000101", "1999000000000102"} and conn.last_dropped["outside_area"] == 1
    heavy = sigs["1999000000000101"]
    assert heavy.valid_until is not None and heavy.raw["cap_severity"] == "Severe"
    assert heavy.raw["cap_area_code"] == "482,483,497" and heavy.raw["cap_polygon_id"] == "1999000000000101"
    assert heavy.raw_geo_hint.polygon_url
    # Thane names the state too, but the Mumbai districts are named: the district level wins
    assert heavy.raw_geo_hint.admin_codes == [CITY_CODE, SUBURBAN_CODE]
    assert "CAP_EVENT:Heavy Rain" in heavy.category_hint and "Waterlogging" in heavy.text
    assert {"area:mumbai", "area:mumbai_suburban"} <= set(heavy.category_hint)
    mr = sigs["1999000000000102"]  # a Marathi state-wide nowcast (Pune and Satara), signed "मंत्रालय, मुंबई"
    assert mr.raw_geo_hint.admin_codes == [STATE_CODE] and mr.language == "mr"
    blob = json.dumps([s.model_dump(mode="json") for s in sigs.values()])
    assert "Contactwala" not in blob and "Synthetic Issuer" not in blob and "control-room" not in blob


def _sachet_entry_expiring(tmp_path, expires: datetime):
    """The synthetic SACHET RSS with the synthetic CAP detail of alert ...101, its <expires> set to ``expires``."""
    cap = (PAGES / "cap_detail_synthetic.xml").read_text(encoding="utf-8")
    stamp = expires.astimezone(IST).isoformat(timespec="seconds")
    cap = re.sub(r"<cap:expires>[^<]*</cap:expires>", f"<cap:expires>{stamp}</cap:expires>", cap)
    cache = Cache(tmp_path)
    cache.put_blob("sachet_cap", "cap-1999000000000101.xml", cap.encode("utf-8"))
    rss = (PAGES / "sachet_rss_synthetic.xml").read_bytes()
    return cache.put("sachet_cap", rss, "xml", blobs=["cap-1999000000000101.xml"]), stamp


@pytest.mark.parametrize("hours", [30, 48, 72, 24 * 7])
def test_a_cap_expiry_days_ahead_is_kept_as_valid_until(tmp_path, protect, hours):
    """Multi-day official warnings keep their real end (OS-4 spans the situation window to it)."""
    expires = (datetime.now(UTC) + timedelta(hours=hours)).replace(microsecond=0)
    entry, stamp = _sachet_entry_expiring(tmp_path, expires)
    sigs = {s.source_id: s for s in Sachet().parse(entry, protect)}
    heavy = sigs["1999000000000101"]
    assert heavy.valid_until == expires and heavy.raw["cap_expires"] == stamp
    assert heavy.published_at is not None and heavy.published_at < heavy.valid_until
    assert sigs["1999000000000102"].valid_until is None  # no CAP detail cached: the expiry is unknown


def test_a_malformed_far_future_cap_expiry_is_unknown(tmp_path, protect):
    expires = (datetime.now(UTC) + timedelta(days=400)).replace(microsecond=0)
    entry, _ = _sachet_entry_expiring(tmp_path, expires)
    sigs = {s.source_id: s for s in Sachet().parse(entry, protect)}
    assert sigs["1999000000000101"].valid_until is None


def test_parse_when_bounds_publication_times_and_validity_ends_separately():
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)
    in_3_days = "2026-10-27T17:30:00+05:30"
    assert parse_when(in_3_days, now=now) is None  # a publication time 3 days ahead: a malformed feed
    assert parse_when(in_3_days, max_ahead=MAX_VALID_AHEAD, now=now) == datetime(2026, 10, 27, 12, tzinfo=UTC)
    assert parse_when("2026-10-25T06:00:00Z", now=now) == datetime(2026, 10, 25, 6, tzinfo=UTC)  # within a day
    assert parse_when("2026-12-31T00:00:00Z", max_ahead=MAX_VALID_AHEAD, now=now) is None  # beyond a month
    assert parse_when("Tue, 20 Oct 2026 12:00:00 GMT", now=now) == datetime(2026, 10, 20, 12, tzinfo=UTC)
    assert parse_when("20261020120000", now=now) == datetime(2026, 10, 20, 12, tzinfo=UTC)
    assert parse_when("1989-12-31T00:00:00Z", now=now) is None and parse_when("garbage", now=now) is None


async def test_a_cap_detail_redirect_off_the_allow_list_does_not_abort_the_fetch(tmp_path, protect):
    rss = (PAGES / "sachet_rss_synthetic.xml").read_bytes()
    rec = Recorder({
        "sachet.ndma.gov.in/cap_public_website/rss/": lambda r: httpx.Response(200, content=rss),
        "sachet.ndma.gov.in/cap_public_website/FetchXMLFile": lambda r: httpx.Response(
            302, headers={"location": "https://cap-mirror.example/alert.xml"}),
    })
    cache = Cache(tmp_path)
    conn = Sachet()
    conn.detail_spacing_sec = 0
    async with _client(rec) as client:
        entry = await conn.fetch(client, cache)
    assert entry is not None and entry.fetch_mode == "live" and entry.blobs == ()
    assert cache.latest("sachet_cap") is not None  # the RSS itself was cached
    assert "cap-mirror.example" not in rec.hosts  # the redirect target was refused before connecting
    # each Maharashtra detail tried once (the other states' alert's never)
    assert len([r for r in rec.requests if "FetchXMLFile" in r.url.path]) == 2
    assert {s.source_id for s in conn.parse(entry, protect)} == {"1999000000000101", "1999000000000102"}


def _page_entry(tmp_path, html: bytes, name: str = "kmc_scrape"):
    return Cache(tmp_path).put(name, html, "html")


def test_official_page_notices(tmp_path, protect):
    """The generic notice-link scraper (kept for a civic portal that lists notices in its HTML), on a synthetic
    BMC-style page: place notices kept, paperwork and person notices dropped, a script-injected link never read."""
    conn = BmcPage(RobotsCache())
    sigs = conn.parse(_page_entry(tmp_path, (PAGES / "bmc_home_synthetic.html").read_bytes()), protect)
    titles = sorted(s.title for s in sigs)
    assert len(sigs) == 4, titles
    assert any("Dadar TT stretch closed" in t for t in titles)  # toponym kept
    assert any(t.startswith("Shri [PERSON] reviews pumping station") for t in titles)  # officer name redacted
    assert not any("injected" in t or "Tender" in t or "another site" in t or "Photo" in t or "Payment" in t
                   for t in titles)
    # the tender form (no place in it) and the payment page (paperwork) are not notices
    assert conn.last_dropped["paperwork_link"] == 1 and conn.last_dropped["not_about_a_place"] == 1
    for s in sigs:
        assert s.publisher == "portal.mcgm.gov.in" and s.url.startswith("https://portal.mcgm.gov.in/portal/")
        assert s.raw_geo_hint.admin_codes == [CITY_CODE, SUBURBAN_CODE] and s.provenance_label == "OFFICIAL-VERIFIED"
        assert s.raw["page_url_domain"] == "portal.mcgm.gov.in" and len(s.raw["page_hash"]) == 64


def test_civic_page_keeps_place_notices_and_drops_notices_about_persons(tmp_path, protect):
    page = (
        '<a href="/portal/downloads/Public_Guidelines_Ganeshotsav_Immersions_2026.pdf">Public Guidelines for '
        'Ganeshotsav Immersions, 2026</a>'
        '<a href="/portal/downloads/Weekly_Nullah_Desilting_Chart.pdf">Weekly Nullah Desilting Chart</a>'
        '<a href="/portal/downloads/Hearing_Intimation.pdf">Hearing Intimation to Political Parties</a>'
        '<a href="/portal/downloads/Notification_BCW.pdf">Enhancement of Compensation for Sewer Deaths &amp; '
        'Disabilities</a>'
        '<a href="/portal/downloads/CM_Circular26.pdf">Chief Manager(Personal)\'s Circular No.26 of 2021-22</a>'
        '<a href="/portal/jsp/CM_Circular.jsp">Office Order/Circular</a>'
    ).encode()
    conn = BmcPage(RobotsCache())
    titles = sorted(s.title for s in conn.parse(_page_entry(tmp_path, page), protect))
    assert titles == ["Public Guidelines for Ganeshotsav Immersions, 2026", "Weekly Nullah Desilting Chart"]
    # the hearing list, the HR circular and the menu name no place; the sewer-deaths notice is about persons
    assert conn.last_dropped["about_persons"] == 1 and conn.last_dropped["not_about_a_place"] == 3


def test_official_page_reads_a_latin1_page(tmp_path, protect):
    """A portal served as ISO-8859-1: a byte that is not UTF-8 does not lose the page."""
    page = (PAGES / "bmc_home_synthetic.html").read_bytes().replace(b"What's New", b"What\xe2s New \xa9")
    assert len(BmcPage(RobotsCache()).parse(_page_entry(tmp_path, page), protect)) == 4


def test_mtp_notices_rows(tmp_path, protect):
    """The Mumbai Traffic Police notices table: one signal per row, the division from the file name, the validity
    as valid_until, paperwork and commented-out or script-held rows never read."""
    conn = MtpNotices(RobotsCache())
    entry = _page_entry(tmp_path, (PAGES / "mtp_notices_synthetic.html").read_bytes(), "mumbai_police_scrape")
    sigs = {s.source_id: s for s in conn.parse(entry, protect)}
    assert set(sigs) == {"mtp-notice:990001", "mtp-notice:990002", "mtp-notice:990003"}
    assert conn.last_dropped["not_a_notice"] == 1  # the e-challan payment row is paperwork
    closed, visarjan, parking = sigs["mtp-notice:990001"], sigs["mtp-notice:990002"], sigs["mtp-notice:990003"]
    assert closed.title == "Road closed for traffic and Alternate Route"
    assert closed.raw_geo_hint.place_names == ["Mulund", "Mumbai"] and "traffic_division:mulund" in closed.category_hint
    assert visarjan.raw_geo_hint.place_names == ["Girgaon", "Mumbai"] and "visarjan" in visarjan.title
    assert visarjan.valid_until is not None and visarjan.valid_until.date().isoformat() == "2026-11-06"
    assert parking.raw_geo_hint.place_names == ["Mumbai"] and parking.valid_until is None  # "Till Next Order"
    for s in sigs.values():
        assert s.source == "mumbai_police_scrape" and s.source_tier == "official"
        assert s.provenance_label == "OFFICIAL-VERIFIED" and s.publisher == "mtperp.mahatrafficechallan.gov.in"
        assert s.url.startswith("https://mtperp.mahatrafficechallan.gov.in/GetPublicNotice/") and " " not in s.url
        assert s.raw_geo_hint.admin_codes == [CITY_CODE, SUBURBAN_CODE] and s.published_at is not None
        assert "area:mumbai" in s.category_hint and "notice:traffic" in s.category_hint
    blob = json.dumps([s.model_dump(mode="json") for s in sigs.values()])
    assert "Injected" not in blob and "withdrawn" not in blob


async def test_official_page_robots_disallow_disables_it(tmp_path):
    rec = Recorder({
        "mtperp.mahatrafficechallan.gov.in/robots.txt": lambda r: httpx.Response(
            200, text="User-agent: *\nDisallow: /\n"),
        "mtperp.mahatrafficechallan.gov.in/": lambda r: httpx.Response(200, text="<html></html>"),
    })
    async with _client(rec) as client:
        with pytest.raises(ConnectorDisabled, match="robots.txt disallows"):
            await MtpNotices(RobotsCache()).fetch(client, Cache(tmp_path))
    assert [r.url.path for r in rec.requests] == ["/robots.txt"]  # the page itself was never requested


def _mtp_runtime(tmp_path, robots_answer):
    """A live-mode runtime whose MTP notices page was cached earlier (while allowed); robots.txt answers per call."""
    page = (PAGES / "mtp_notices_synthetic.html").read_bytes()
    Cache(tmp_path / "cache").put("mumbai_police_scrape", page, "html")
    rec = Recorder({
        "mtperp.mahatrafficechallan.gov.in/robots.txt": lambda r: robots_answer(),
        "mtperp.mahatrafficechallan.gov.in/": lambda r: httpx.Response(200, content=page,
                                                                       headers={"content-type": "text/html"}),
    })
    settings = Settings(cache_dir=tmp_path / "cache", oracle_url=DEAD_ORACLE, mode="live")
    rt = build_runtime(settings, source_transport=httpx.MockTransport(rec))
    clock = [0.0]
    rt.engine.connectors["mumbai_police_scrape"].robots = RobotsCache(clock=lambda: clock[0])
    return rt, rec, clock


async def test_a_robots_disallow_disables_the_page_and_never_serves_its_cache(tmp_path):
    rules = {"text": "User-agent: *\nDisallow: /\n"}
    rt, rec, clock = _mtp_runtime(tmp_path, lambda: httpx.Response(200, text=rules["text"]))
    name = "mumbai_police_scrape"
    try:
        signals, st = await rt.engine.run_connector(name)
        assert signals == [] and st.fetch_mode is None and st.cache_age_sec is None
        assert st.error == "robots.txt disallows" and st.disabled_by == "robots.txt disallows"
        health = rt.engine.health()["connectors"][name]
        assert health["enabled"] is False and health["error"] == "robots.txt disallows" and health["signals"] == 0
        assert [r.url.path for r in rec.requests] == ["/robots.txt"]  # the page itself was never requested
        assert name in rt.engine.scheduled_names()  # still scheduled, so robots.txt is read again
        # a day later the site allows it again: the connector re-enables itself and fetches live
        rules["text"] = "User-agent: *\nAllow: /\n"
        clock[0] += 86401
        signals, st = await rt.engine.run_connector(name)
        assert len(signals) == 3 and st.error is None and st.fetch_mode == "live" and st.disabled_by is None
        assert rt.engine.health()["connectors"][name]["enabled"] is True
    finally:
        await rt.aclose()


async def test_an_unreachable_robots_txt_is_a_failure_that_serves_the_cache(tmp_path):
    rt, rec, _clock = _mtp_runtime(tmp_path, lambda: httpx.Response(503))
    try:
        signals, st = await rt.engine.run_connector("mumbai_police_scrape")
    finally:
        await rt.aclose()
    assert len(signals) == 3 and st.fetch_mode == "cached-sample" and st.disabled_by is None
    assert st.error.startswith("robots.txt unreachable (HTTP 503)") and "serving the last live answer" in st.error
    assert [r.url.path for r in rec.requests] == ["/robots.txt"]  # nothing crawled (RFC 9309 complete disallow)


def test_the_civic_and_sdma_page_connectors_are_disabled_and_not_allow_listed():
    """BMC's portal has no notice list in its HTML; Maharashtra SDMA's alerts arrive through SACHET (2026-10-30)."""
    for conn in (BmcPage(), MsdmaPage()):
        assert not conn.enabled and (conn.disabled_reason or "").startswith("disabled:")
        assert conn.host not in ALLOWED_HOSTS


def test_the_traffic_police_connector_is_enabled_on_its_verified_host():
    conn = MtpNotices()
    assert conn.enabled and conn.disabled_reason is None and conn.host in ALLOWED_HOSTS


# ── Common Crawl (backfill) ───────────────────────────────────────────────────────────────────────────────────


def _warc(url: str, html: str) -> bytes:
    body = html.encode("utf-8")
    http = (b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: "
            + str(len(body)).encode() + b"\r\n\r\n" + body)
    warc = (b"WARC/1.0\r\nWARC-Type: response\r\nWARC-Target-URI: " + url.encode()
            + b"\r\nContent-Length: " + str(len(http)).encode() + b"\r\n\r\n" + http + b"\r\n\r\n")
    return gzip.compress(warc, mtime=0)


async def test_common_crawl_backfill_fetch_and_parse(tmp_path, protect):
    url = "https://news-a.example/city/mumbai/synthetic-archived-report"
    html = ('<html><head><title>Synthetic archived report: Mr Testa Archivewala opens a reading room</title>'
            '<meta name="description" content="A 70-year-old resident joined the opening.">'
            '<meta property="article:published_time" content="2026-10-01T08:00:00+05:30"></head></html>')
    record = _warc(url, html)
    cdx = json.dumps({"url": url, "digest": "ABCDEFGHIJKLMNOPQRSTUVWX234567AB", "status": "200",
                      "mime": "text/html", "languages": "eng", "offset": "100", "length": str(len(record)),
                      "filename": "crawl-data/CC-MAIN-2026-43/segments/1/warc/synthetic-00001.warc.gz"})
    rec = Recorder({
        "index.commoncrawl.org/collinfo.json": lambda r: httpx.Response(200, json=[{"id": "CC-MAIN-2026-43"}]),
        "index.commoncrawl.org/CC-MAIN-2026-43-index": lambda r: httpx.Response(200, text=cdx + "\n"),
        "data.commoncrawl.org/crawl-data/": lambda r: httpx.Response(206, content=record),
    })
    conn = CommonCrawl()
    conn.spacing_sec = 0
    assert conn.scheduled is False  # backfill only
    async with _client(rec) as client:
        entry = await conn.fetch(client, Cache(tmp_path))
    ranged = [r for r in rec.requests if r.url.host == "data.commoncrawl.org"]
    assert ranged and ranged[0].headers["range"] == f"bytes=100-{100 + len(record) - 1}"
    (s,) = conn.parse(entry, protect)
    assert s.source == "common_crawl" and s.source_id == "ABCDEFGHIJKLMNOPQRSTUVWX234567AB"
    assert s.title.startswith("Synthetic archived report: Mr [PERSON] opens") and "[AGE]" in s.text
    assert s.url is None and s.publisher == "news-a.example" and s.raw["cc_index"] == "CC-MAIN-2026-43"
    assert s.raw["http_status"] == 200 and s.language == "en" and s.published_at is not None


# ── live fetch paths ──────────────────────────────────────────────────────────────────────────────────────────


async def test_gdelt_bulk_fetches_only_the_export_it_names(tmp_path, protect):
    import hashlib

    zipped = (CAPTURE / "20261020120000.export.CSV.zip").read_bytes()
    md5 = hashlib.md5(zipped, usedforsecurity=False).hexdigest()
    lastupdate = (
        f"{len(zipped)} {md5} http://data.gdeltproject.org/gdeltv2/20261020120000.export.CSV.zip\n"
        "5 0123456789abcdef0123456789abcdef http://data.gdeltproject.org/gdeltv2/20261020120000.mentions.CSV.zip\n"
        "9 0123456789abcdef0123456789abcdef http://data.gdeltproject.org/gdeltv2/20261020120000.gkg.csv.zip\n"
    )
    rec = Recorder({
        "data.gdeltproject.org/gdeltv2/lastupdate.txt": lambda r: httpx.Response(200, text=lastupdate),
        "data.gdeltproject.org/gdeltv2/20261020120000.export": lambda r: httpx.Response(200, content=zipped),
    })
    cache = Cache(tmp_path)
    async with _client(rec) as client:
        entry = await GdeltBulk().fetch(client, cache)
        again = await GdeltBulk().fetch(client, cache)  # the slice is cached: not downloaded twice
    paths = [r.url.path for r in rec.requests]
    assert paths.count("/gdeltv2/20261020120000.export.CSV.zip") == 1
    assert not any("mentions" in p or "gkg" in p for p in paths)
    assert all(r.url.scheme == "https" for r in rec.requests)  # upgraded from the http:// that lastupdate lists
    assert len(GdeltBulk().parse(entry, protect)) == 2 and again is not None


async def test_gdelt_bulk_refuses_md5_mismatch(tmp_path):
    lastupdate = "10 00000000000000000000000000000000 http://data.gdeltproject.org/gdeltv2/20261020120000.export.CSV.zip\n"
    rec = Recorder({
        "data.gdeltproject.org/gdeltv2/lastupdate.txt": lambda r: httpx.Response(200, text=lastupdate),
        "data.gdeltproject.org/gdeltv2/2026": lambda r: httpx.Response(200, content=b"not the right bytes"),
    })
    async with _client(rec) as client:
        with pytest.raises(ConnectorError, match="MD5"):
            await GdeltBulk().fetch(client, Cache(tmp_path))


async def test_gdelt_doc_429_raises_for_cache_fallback(tmp_path):
    rec = Recorder({"api.gdeltproject.org/api/v2/doc/doc": lambda r: httpx.Response(429, text="slow down")})
    async with _client(rec) as client:
        with pytest.raises(ConnectorError, match="429"):
            await GdeltDoc(_Spacer(0)).fetch(client, Cache(tmp_path))
    banner = Recorder({"api.gdeltproject.org/api/v2/doc/doc": lambda r: httpx.Response(
        200, text="Please limit requests to one every 5 seconds")})
    async with _client(banner) as client:
        with pytest.raises(ConnectorError, match="throttled"):
            await GdeltDoc(_Spacer(0)).fetch(client, Cache(tmp_path))


async def test_doc_requests_are_spaced(monkeypatch):
    import osint_ingress.connectors.gdelt as gdelt

    clock = [1000.0]
    slept: list[float] = []

    async def fake_sleep(delay: float) -> None:
        slept.append(delay)
        clock[0] += delay

    monkeypatch.setattr(gdelt.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(gdelt.asyncio, "sleep", fake_sleep)
    spacer = _Spacer(5.0)
    await spacer.wait()
    clock[0] += 1.0
    await spacer.wait()
    assert slept == [pytest.approx(4.0)]  # ≥ 5 s between two DOC requests


_MR_GNEWS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>synthetic mr</title>
<language>mr</language>
<item><title>Mumbai Rain: हिंदमाता येथे पाणी साचले - वार्ता क</title>
<link>https://news.google.com/rss/articles/SYNTHETIC-GNEWS-MR01?oc=5</link>
<guid isPermaLink="false">SYNTHETIC-GNEWS-MR01</guid><pubDate>Tue, 20 Oct 2026 12:40:00 GMT</pubDate>
<description>हिंदमाता येथे पाणी साचले</description><source url="https://news-mr-a.example">वार्ता क</source></item>
</channel></rss>"""


async def test_reddit_and_google_news_fetch_through_allow_list(tmp_path, protect):
    def gnews(r: httpx.Request) -> httpx.Response:
        hl = r.url.params.get("hl")
        assert r.url.params.get("ceid") == {"mr": "IN:mr", "hi": "IN:hi"}.get(hl, "IN:en")
        if hl == "hi":
            return httpx.Response(200, content=b'<?xml version="1.0"?><rss version="2.0"><channel><title>s</title>'
                                               b"</channel></rss>")
        return httpx.Response(200, content=_MR_GNEWS.encode() if hl == "mr" else (CAPTURE / "gnews_live.xml").read_bytes())

    rec = Recorder({
        # the live community's feed: the capture's posts under r/mumbai (the capture itself is r/example_city)
        "www.reddit.com/r/mumbai/new/.rss": lambda r: httpx.Response(
            200, content=(CAPTURE / "reddit_live.rss").read_bytes().replace(b"example_city", b"mumbai")),
        "news.google.com/rss/search": gnews,
    })
    cache = Cache(tmp_path)
    async with _client(rec) as client:
        r_entry = await Reddit().fetch(client, cache)
        g_entry = await GoogleNews().fetch(client, cache)
    assert {r.url.host for r in rec.requests} == {"www.reddit.com", "news.google.com"}
    assert rec.requests[0].headers["user-agent"].startswith("sajag-osint-ingress")
    # one cycle reads the English, Marathi and Hindi searches, cached as one bundle
    assert [r.url.params.get("hl") for r in rec.requests if r.url.host == "news.google.com"] == ["en-IN", "mr", "hi"]
    assert len(g_entry.blobs) == 3
    live = Reddit().parse(r_entry, protect)
    assert len(live) == 4 and all(s.fetch_mode == "live" for s in live)
    # a live fetch is never synthetic: the real community, the source's own label
    assert {(s.publisher, s.provenance_label) for s in live} == {("reddit.com/r/mumbai", "UNVERIFIED-OSINT")}
    gsigs = GoogleNews().parse(g_entry, protect)
    assert {s.provenance_label for s in gsigs} == {"NEWS-REPORTED"} and len(gsigs) == 9
    (mr,) = [s for s in gsigs if s.language == "mr"]
    # the Marathi headline's Latin search keyword and Google's display name are both cut
    assert "Mumbai Rain" not in mr.title and "वार्ता क" not in mr.title and mr.publisher == "news-mr-a.example"


def test_canonical_url_and_hash_are_stable():
    a = "https://WWW.News-A.example:443/city/mumbai/x?utm_source=feed&id=7&oc=5#top"
    b = "https://www.news-a.example/city/mumbai/x?id=7"
    assert canonical_url(a) == canonical_url(b) == "https://www.news-a.example/city/mumbai/x?id=7"
    assert url_sha256(a) == url_sha256(b) and len(url_sha256(a)) == 64
    # a Reddit thread's slug (the unredacted title) is not part of its canonical form
    r1 = "https://www.reddit.com/r/mumbai/comments/syn0001/some_title_slug/"
    r2 = "https://www.reddit.com/r/mumbai/comments/syn0001/"
    assert canonical_url(r1) == r2 and url_sha256(r1) == url_sha256(r2)
    assert canonical_url("ftp://x.example/") is None and url_sha256(None) is None


def test_every_capture_file_is_known_to_import(tmp_path):
    from osint_ingress.importer import CAPTURE_FILES, capture_target

    names = {p.name for p in CAPTURE.iterdir() if p.is_file() and p.name != "README.md"}
    zips = {n for n in names if n.endswith(".export.CSV.zip")}
    assert all(capture_target(n) for n in names - zips) and len(zips) == 1
    assert set(CAPTURE_FILES) <= names  # every fixed name has its file here; SACHET goes by its state pattern
    assert capture_target("sachet_maharashtra_synthetic.xml") == ("sachet_cap", "xml")


def test_cache_paths_never_escape(tmp_path):
    from osint_ingress.cache import CacheError

    cache = Cache(tmp_path)
    for bad in ("../x", "a/b", "..", ".hidden", "x" * 200):
        with pytest.raises(CacheError):
            cache.put_blob("gdelt_events", bad, b"x")
    with pytest.raises(CacheError):
        cache.put("../evil", b"x", "txt")
    assert not any(Path(tmp_path).parent.glob("evil*"))


def test_news_and_social_urls_are_withheld_with_a_stable_verifiable_hash(capture_cache, connectors, protect):
    """Orchestrator decision (binding): news/social URLs are never emitted; the url_sha256 hint lets an auditor
    verify a source by hashing a candidate URL; official tiers keep their identifier URLs."""
    first = parse_cache(capture_cache, connectors, protect)
    again = parse_cache(capture_cache, build_connectors(), protect)
    for name, sigs in first.items():
        for s, t in zip(sigs, again[name], strict=True):
            hint = [h for h in s.category_hint if h.startswith("url_sha256:")]
            if s.source_tier == "official":
                assert s.url and not hint
                continue
            assert s.url is None and s.raw_geo_hint.polygon_url is None
            assert len(hint) == 1 and hint == [h for h in t.category_hint if h.startswith("url_sha256:")]
    # an auditor holding the candidate URL reproduces the hint
    gn = {s.source_id: s for s in first["google_news_rss"]}["SYNTHETIC-GNEWS-0001"]
    candidate = "https://news.google.com/rss/articles/SYNTHETIC-GNEWS-0001?oc=5"
    assert f"url_sha256:{url_sha256(candidate)}" in gn.category_hint
    rd = {s.source_id: s for s in first["reddit_rss"]}["t3_syn0001"]
    thread = "https://www.reddit.com/r/example_city/comments/syn0001/any-slug-at-all/"
    assert f"url_sha256:{url_sha256(thread)}" in rd.category_hint
    doc = first["gdelt_doc"][0]
    article = "https://news-a.example/city/mumbai/library-wing-opens-at-dadar"
    assert doc.source_id == f"url-sha256:{url_sha256(article)}"
