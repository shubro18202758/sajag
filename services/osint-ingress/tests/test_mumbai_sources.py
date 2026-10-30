"""The Mumbai sources: the Maharashtra area filter of the official feeds, the outlets' own RSS feeds (``news_rss``),
IMD's CAP mirror, the script- and word-based language (Marathi vs Hindi in Devanagari), and the service's own
Mumbai constants."""

from __future__ import annotations

import ast
import json
import re
import unicodedata
from pathlib import Path

import httpx
import pytest
from conftest import CAPTURE, HOSTILE, PACKAGE, PAGES, POC_RAW, Recorder, needs_poc

from osint_common.kinds import SOURCE_NAMES
from osint_ingress.cache import Cache
from osint_ingress.config import CONNECTOR_NAMES, USER_AGENT
from osint_ingress.connectors._area import (
    CITY_CODE,
    GDELT_ADM1,
    STATE_CODE,
    SUBURBAN_CODE,
    area_hint,
    match_area,
)
from osint_ingress.connectors.base import CITY_BBOX, CITY_RE, ConnectorError, script_language, url_sha256
from osint_ingress.connectors.news_rss import FEEDS, ITEM_FIELDS, NewsRss, cut_latin_lead, names_city
from osint_ingress.connectors.official import Imd, Sachet
from osint_ingress.importer import import_capture
from osint_ingress.safe_http import RobotsCache, make_source_client

REPO = PACKAGE.parents[1]
BOTH = [CITY_CODE, SUBURBAN_CODE]


def _client(handler) -> httpx.AsyncClient:
    return make_source_client(user_agent=USER_AGENT, transport=httpx.MockTransport(handler))


# ── the Maharashtra area filter ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "codes"),
    [
        # IMD Mumbai's English nowcast, as SACHET carried it on 2026-10-30
        ("Light Rain is very likely to occur at isolated places over Mumbai, Mumbai Suburban in next 3 hours.", BOTH),
        ("Thunderstorm likely over Mumbai in the next 3 hours.", [CITY_CODE]),
        ("Heavy rain over Mumbai Suburban and Thane", [SUBURBAN_CODE]),
        ("Greater Mumbai: orange alert for heavy rain", BOTH),
        ("पुढील ३ तासांत मुंबईत मुसळधार पावसाची शक्यता", [CITY_CODE]),
        ("मुंबई उपनगरात जोरदार पाऊस", [SUBURBAN_CODE]),
        ("बृहन्मुंबई क्षेत्रात पाणी साचण्याची शक्यता", BOTH),
        ("Mumbai,Mumbai Suburban districts of Maharashtra", BOTH),
        # other Maharashtra districts only: the state level, Marathi oblique stems included
        ("पुढील ३ तासात ठाण्यातील काही ठिकाणी हलका पाऊस पडण्याची दाट शक्यता आहे.", [STATE_CODE]),
        ("पुढील ३ तासात अहिल्यानगर आणि नाशिकमधील काही ठिकाणी हलका पाऊस", [STATE_CODE]),
        ("Heavy rain over Raigad, Ratnagiri and Sindhudurg", [STATE_CODE]),
        ("Rain likely over Navi Mumbai and Panvel", [STATE_CODE]),  # Navi Mumbai is not Mumbai
        ("नवी मुंबईत पाणी साचले", [STATE_CODE]),
        ("Heat wave conditions over Vidarbha", [STATE_CODE]),
    ],
)
def test_area_levels(text, codes):
    m = match_area(text)
    assert m.in_area and m.admin_codes == codes


def test_the_sdma_sign_off_is_never_the_area():
    """Maharashtra SDMA signs every Marathi nowcast "मंत्रालय, मुंबई" (its office), whatever district it is for."""
    kolhapur = "पुढील ३ तासांत कोल्हापूर जिल्ह्यात विजा चमकण्याची शक्यता आहे. नागरिकांनी सतर्क रहावे, मंत्रालय, मुंबई."
    assert match_area(kolhapur).admin_codes == [STATE_CODE]
    nowhere = "पुढील ३ तासांत आपल्या जिल्ह्यात काही ठिकाणी हलका पाऊस. मंत्रालय. मुंबई"
    m = match_area(nowhere)
    assert not m.in_area and not m.other_state  # names nothing: the Maharashtra feed makes it the state
    assert match_area("Rain likely over the island city. Mantralaya, Mumbai").districts == ()


def test_lgd_district_codes_name_the_mumbai_districts():
    assert match_area("", lgd_codes=["482", "483"]).admin_codes == BOTH
    assert match_area("Light rain over your district", lgd_codes=["483"]).admin_codes == [SUBURBAN_CODE]
    assert match_area("", lgd_codes=["497"]).districts == ()  # Thane's code: not a Mumbai district


@pytest.mark.parametrize(
    "text",
    [
        "Squally weather along and off the Goa coast",
        "High waves along the Saurashtra and Kutch coast",
        "Heavy rain over coastal Karnataka",
        "A low pressure area over the Arabian Sea",  # the sea, not a state
        "",
    ],
)
def test_other_states_are_outside_the_area(text):
    m = match_area(text)
    assert not m.in_area and m.districts == () and area_hint(m) == []


def test_the_area_match_is_blind_to_format_characters_and_digits():
    zwj = "मुंबई\u200dत पाऊस"
    assert match_area(zwj).districts == match_area("मुंबईत पाऊस").districts == (CITY_CODE,)
    assert unicodedata.normalize("NFKC", "ठाणे") == "ठाणे"


def test_area_hints_name_the_level():
    assert area_hint(match_area("over Mumbai and Mumbai Suburban")) == ["area:mumbai", "area:mumbai_suburban"]
    assert area_hint(match_area("over Pune")) == ["area:maharashtra"]
    assert CITY_CODE == "LGD:MUMBAI" and SUBURBAN_CODE == "LGD:MUMBAI_SUBURBAN" and STATE_CODE == "LGD:MAHARASHTRA"
    assert GDELT_ADM1 == "IN16"  # FIPS 10-4 Maharashtra (West Bengal is IN28)


def test_script_language():
    assert script_language("मुंबईत पाणी साचले, वाहतूक कोंडी") == "mr"
    assert script_language("पुढील ३ तासात ठाण्यातील काही ठिकाणी हलका पाऊस पडण्याची शक्यता आहे.") == "mr"
    assert script_language("मुंबई में भारी बारिश, कई इलाकों में जलभराव") == "hi"
    assert script_language("Mumbai Rain: मुंबईत पाऊस") == "mr"  # a mixed headline counts by its Devanagari part
    # a short headline with no telling word follows its feed's language
    assert script_language("मुंबई लोकल", "mr") == "mr" and script_language("मुंबई लोकल", "hi") == "hi"
    assert script_language("কলকাতায় জল জমা") == "bn"  # the second city pack's script
    assert script_language("Waterlogging at Hindmata") == "en" and script_language("", "mr") == "mr"


# ── SACHET's Maharashtra feed and IMD's mirror ───────────────────────────────────────────────────────────────


@needs_poc
def test_a_real_sachet_capture_of_another_state_yields_nothing(tmp_path, protect):
    """The PoC's real SACHET capture (another state's alerts), read in place: nothing is a Mumbai district."""
    import_capture(POC_RAW, tmp_path / "cache")
    conn = Sachet()
    sigs = conn.parse(Cache(tmp_path / "cache").latest("sachet_cap"), protect)
    assert all(CITY_CODE not in s.raw_geo_hint.admin_codes for s in sigs)


async def test_imd_fetches_details_from_the_mirror_only_and_keeps_maharashtra(tmp_path, protect):
    rss = (PAGES / "imd_rss_synthetic.xml").read_bytes()
    details = {
        "/in-imd-en/2026-10-20-12-00-00-synthetic-0001.xml": (PAGES / "imd_cap_synthetic_0001.xml").read_bytes(),
        "/in-imd-en/2026-10-20-12-05-00-synthetic-0002.xml": (PAGES / "imd_cap_synthetic_0002.xml").read_bytes(),
    }
    rec = Recorder({
        "cap-sources.s3.amazonaws.com/in-imd-en/rss.xml": lambda r: httpx.Response(200, content=rss),
        "cap-sources.s3.amazonaws.com/in-imd-en/2026": lambda r: httpx.Response(200, content=details[r.url.path]),
    })
    conn = Imd()
    conn.detail_spacing_sec = 0
    cache = Cache(tmp_path)
    async with _client(rec) as client:
        entry = await conn.fetch(client, cache)
    assert set(rec.hosts) == {"cap-sources.s3.amazonaws.com"}  # the off-mirror link is never requested
    assert len(entry.blobs) == 2
    sigs = conn.parse(entry, protect)
    assert conn.last_dropped["outside_area"] == 1  # the Karnataka and Goa alert
    by_id = {s.source_id: s for s in sigs}
    mum = by_id["synthetic-imd-0001"]
    assert mum.raw_geo_hint.admin_codes == BOTH and mum.source == "imd"
    assert mum.publisher == "mausam.imd.gov.in"
    assert mum.url.startswith("https://cap-sources.s3.amazonaws.com/in-imd-en/")
    assert mum.provenance_label == "OFFICIAL-VERIFIED" and mum.license == "imd_terms" and not mum.redistributable
    assert "CAP_EVENT:Thunderstorm" in mum.category_hint and "mirror:wmo_alert_hub" in mum.category_hint
    assert mum.valid_until is not None or mum.raw["cap_expires"]
    # the off-mirror item names Mumbai in its own text: kept, but its link is not an official URL
    off = by_id["synthetic-0003"]
    assert off.url is None and off.raw_geo_hint.admin_codes == [CITY_CODE]
    blob = json.dumps([s.model_dump(mode="json") for s in sigs])
    assert "Contactwala" not in blob and "never be read" not in blob


async def test_an_empty_imd_feed_is_a_good_fetch_with_no_signal(tmp_path, protect):
    empty = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>'
             b"<link>https://cap-sources.s3.amazonaws.com/in-imd-en/rss.xml</link></channel></rss>")
    rec = Recorder({"cap-sources.s3.amazonaws.com/": lambda r: httpx.Response(200, content=empty)})
    async with _client(rec) as client:
        entry = await Imd().fetch(client, Cache(tmp_path))
    assert entry is not None and Imd().parse(entry, protect) == []


def test_sachet_prefers_the_english_cap_headline(tmp_path, protect):
    """A Marathi RSS title with a cached CAP detail: the English <info> headline (naming the districts) is the title."""
    rss = ("<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel><title>t</title><item>"
           "<title>पुढील ३ तासांत आपल्या जिल्ह्यात काही ठिकाणी हलका पाऊस. मंत्रालय, मुंबई</title>"
           "<link>https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1999000000000101</link>"
           "<guid isPermaLink='false'>1999000000000101</guid><pubDate>Tue, 20 Oct 2026 12:00:00 GMT</pubDate>"
           "<category>Met</category></item></channel></rss>").encode("utf-8")
    cache = Cache(tmp_path)
    cache.put_blob("sachet_cap", "cap-1999000000000101.xml", (PAGES / "cap_detail_synthetic.xml").read_bytes())
    entry = cache.put("sachet_cap", rss, "xml", blobs=["cap-1999000000000101.xml"])
    (s,) = Sachet().parse(entry, protect)
    assert s.title.startswith("Heavy rain likely at isolated places over Mumbai, Mumbai Suburban")
    assert s.language == "en" and s.raw_geo_hint.admin_codes == BOTH


# ── news_rss: the outlets' own feeds ─────────────────────────────────────────────────────────────────────────


def test_news_rss_capture_fields(capture_cache, protect):
    conn = NewsRss(RobotsCache())
    sigs = conn.parse(capture_cache.latest("news_rss"), protect)
    assert len(sigs) == 6 and dict(conn.last_dropped) == {"outside_section": 1, "foreign_link": 1}
    assert {s.publisher for s in sigs} == {"news-mr-a.example", "news-mr-b.example", "news-c.example"}
    assert sorted(s.language for s in sigs) == ["en", "en", "mr", "mr", "mr", "mr"]
    for s in sigs:
        assert s.source == "news_rss" and s.source_tier == "news_regional" and s.provenance_label == "SIMULATED"
        assert s.license == "publisher_rss_terms" and s.redistributable is False and s.credibility_prior == 0.60
        assert s.url is None and s.source_id.startswith("url-sha256:")
        assert any(h.startswith("url_sha256:") for h in s.category_hint)
        assert f"domain:{s.publisher}" in s.category_hint and any(h.startswith("feed:") for h in s.category_hint)
        assert set(s.raw) <= {"source_domain", "pub_date"}
        assert "The post " not in s.text  # WordPress's footer is cut
    blob = json.dumps([s.model_dump(mode="json") for s in sigs], ensure_ascii=False)
    # bylines and full text are never read; categories are never emitted
    assert "Reporterwala" not in blob and "never read" not in blob and "क्रीडा" not in blob
    # the Marathi headline's English search keyword is cut before redaction
    assert "Mumbai Rain" not in blob
    hindmata = [s for s in sigs if s.source_id == "url-sha256:" + url_sha256(
        "https://news-mr-b.example/mumbai/ambedkar-road-waterlogged-near-hindmata")]
    assert len(hindmata) == 1 and hindmata[0].title.startswith(("हिंदमाता", "[WITHHELD]"))
    assert all("area:mumbai" in s.category_hint for s in sigs)


def test_a_live_bundle_reads_only_reviewed_feeds(tmp_path, protect):
    """A live entry naming a feed that is not in FEEDS (or inlining its XML) is not read: only a hand-written
    capture may name fictional outlets, and only *.example ones."""
    doc = json.loads((CAPTURE / "news_rss_live.json").read_text(encoding="utf-8"))
    live = Cache(tmp_path / "a").put("news_rss", json.dumps(doc).encode(), "json")
    conn = NewsRss(RobotsCache())
    assert conn.parse(live, protect) == [] and conn.last_dropped["unknown_feed"] == 3
    doc["feeds"][0]["publisher"] = "real-outlet.in"
    synthetic = Cache(tmp_path / "b").put("news_rss", json.dumps(doc).encode(), "json", synthetic=True)
    assert {s.publisher for s in conn.parse(synthetic, protect)} == {"news-mr-b.example", "news-c.example"}
    assert conn.last_dropped["unknown_feed"] == 1


_TOI = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>synthetic toi replica</title><language>en-gb</language>
<item><title>Waterlogging at Andheri Subway after overnight rain</title>
<description><![CDATA[<a href="x"><img src="y"/></a>Traffic diverted to the Gokhale Bridge.]]></description>
<link>https://timesofindia.indiatimes.com/city/mumbai/waterlogging-at-andheri-subway/articleshow/1.cms</link>
<guid>https://timesofindia.indiatimes.com/city/mumbai/waterlogging-at-andheri-subway/articleshow/1.cms</guid>
<pubDate>Tue, 20 Oct 2026 12:00:00 +0530</pubDate><dc:creator>Synthetic Byline Reporterwala</dc:creator></item>
</channel></rss>"""
_MT = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>synthetic mt replica</title>
<language>mr</language>
<item><title>हिंदमाता येथे पाणी साचले</title>
<link>https://maharashtratimes.com/maharashtra/mumbai-news/hindmata-x/articleshow/2.cms</link>
<pubDate>Tue, 20 Oct 2026 12:00:00 +0530</pubDate></item>
<item><title>लालबागमध्ये गणेशोत्सवाची वाहतूक व्यवस्था</title>
<link>https://maharashtratimes.com/maharashtra/mumbai-news/lalbaug-y/articleshow/3.cms</link>
<pubDate>Tue, 20 Oct 2026 11:00:00 +0530</pubDate></item>
<item><title>देशातील बातमी</title><link>https://maharashtratimes.com/india-news/national-z/articleshow/4.cms</link>
<pubDate>Tue, 20 Oct 2026 10:00:00 +0530</pubDate></item>
</channel></rss>"""
_TV9HI = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>synthetic tv9 hindi replica</title>
<language>hi</language>
<item><title>मुंबई में भारी बारिश, लोकल ट्रेनें देर से चल रहीं</title>
<link>https://www.tv9hindi.com/state/maharashtra/mumbai-rain-local-trains-late-1.html</link>
<pubDate>Tue, 20 Oct 2026 12:00:00 +0530</pubDate></item>
<item><title>पुणे में सड़क पर जलभराव</title>
<link>https://www.tv9hindi.com/state/maharashtra/pune-waterlogging-2.html</link>
<pubDate>Tue, 20 Oct 2026 11:00:00 +0530</pubDate></item>
</channel></rss>"""


async def test_news_rss_fetches_each_feed_honours_robots_and_survives_a_refusal(tmp_path, protect):
    rec = Recorder({
        "timesofindia.indiatimes.com/robots.txt": lambda r: httpx.Response(
            200, text="User-agent: *\nDisallow: /feeds/\n"),
        "timesofindia.indiatimes.com/rssfeeds/": lambda r: httpx.Response(200, text=_TOI),
        "www.hindustantimes.com/robots.txt": lambda r: httpx.Response(404),
        "www.hindustantimes.com/feeds/": lambda r: httpx.Response(403),
        "maharashtratimes.com/robots.txt": lambda r: httpx.Response(200, text="User-agent: *\nAllow: /\n"),
        "maharashtratimes.com/maharashtra/": lambda r: httpx.Response(200, text=_MT),
        "marathi.abplive.com/robots.txt": lambda r: httpx.Response(
            200, text="User-agent: sajag-osint-ingress\nDisallow: /\n"),
        "www.tv9hindi.com/robots.txt": lambda r: httpx.Response(404),
        "www.tv9hindi.com/state/maharashtra/feed": lambda r: httpx.Response(200, text=_TV9HI),
        "": lambda r: httpx.Response(404 if r.url.path == "/robots.txt" else 503),
    })
    conn = NewsRss(RobotsCache())
    cache = Cache(tmp_path)
    async with _client(rec) as client:
        entry = await conn.fetch(client, cache)
    doc = json.loads(entry.read_bytes())
    assert [f["feed"] for f in doc["feeds"]] == ["toi_mumbai", "mt_mumbai", "tv9hindi_maharashtra"]
    failed = {f["feed"]: f["reason"] for f in doc["failed"]}
    assert failed["ht_mumbai"] == "HTTP 403" and failed["abpmajha_mumbai"] == "robots.txt disallows"
    assert failed["midday_mumbai"] == "HTTP 503" and len(failed) == len(FEEDS) - 3
    assert not any(r.url.host == "marathi.abplive.com" and r.url.path != "/robots.txt" for r in rec.requests)
    assert all(r.headers["user-agent"] == USER_AGENT for r in rec.requests)
    sigs = conn.parse(entry, protect)
    assert conn.last_dropped["outside_section"] == 1  # Maharashtra Times' national item
    assert conn.last_dropped["outside_city"] == 1  # the Hindi Maharashtra feed's Pune item
    by_pub = {}
    for s in sigs:
        by_pub.setdefault(s.publisher, []).append(s)
    assert len(by_pub["timesofindia.indiatimes.com"]) == 1 and len(by_pub["maharashtratimes.com"]) == 2
    assert {s.language for s in by_pub["maharashtratimes.com"]} == {"mr"}
    assert [s.language for s in by_pub["tv9hindi.com"]] == ["hi"]
    assert {s.provenance_label for s in sigs} == {"NEWS-REPORTED"}  # a live fetch is never synthetic
    toi = by_pub["timesofindia.indiatimes.com"][0]
    assert toi.title == "Waterlogging at Andheri Subway after overnight rain" and "Gokhale Bridge" in toi.text
    assert "area:mumbai" in toi.category_hint
    assert "Reporterwala" not in json.dumps(toi.model_dump(mode="json"))


async def test_news_rss_fails_only_when_every_feed_fails(tmp_path):
    rec = Recorder({"": lambda r: httpx.Response(404 if r.url.path == "/robots.txt" else 503)})
    async with _client(rec) as client:
        with pytest.raises(ConnectorError, match="every feed failed"):
            await NewsRss(RobotsCache()).fetch(client, Cache(tmp_path))
    assert Cache(tmp_path).latest("news_rss") is None


async def test_a_hostile_feed_is_refused_and_never_cached(tmp_path):
    hostile = (HOSTILE / "xxe.xml").read_bytes()
    rec = Recorder({
        "timesofindia.indiatimes.com/robots.txt": lambda r: httpx.Response(404),
        "timesofindia.indiatimes.com/": lambda r: httpx.Response(200, content=hostile),
        "": lambda r: httpx.Response(404 if r.url.path == "/robots.txt" else 503),
    })
    async with _client(rec) as client:
        with pytest.raises(ConnectorError, match="every feed failed"):
            await NewsRss(RobotsCache()).fetch(client, Cache(tmp_path))
    assert not list(Path(tmp_path).rglob("*.xml"))


def test_cut_latin_lead():
    assert cut_latin_lead("Fictus-Kalpit Meeting : मुंबईत बैठक") == "मुंबईत बैठक"
    assert cut_latin_lead("Mumbai Rain Update: 'नमुना' मुसळधार पाऊस") == "नमुना' मुसळधार पाऊस"
    assert cut_latin_lead("मुंबईत पाणी साचले: वाहतूक विस्कळीत") == "मुंबईत पाणी साचले: वाहतूक विस्कळीत"
    assert cut_latin_lead("Waterlogging: traffic hit at Hindmata") == "Waterlogging: traffic hit at Hindmata"


def test_names_city():
    assert names_city("मुंबईत पाऊस") and names_city("/states/maharashtra/mumbai-local-train-123")
    assert names_city("Heavy rain in Bombay") and names_city("बृहन्मुंबई महानगरपालिका")
    assert not names_city("नवी मुंबईत पाऊस") and not names_city("Navi Mumbai rain") and not names_city("Pune rain")


def test_the_news_rss_parser_never_reads_a_byline():
    assert not {"author", "creator", "dc:creator", "content", "encoded"} & set(ITEM_FIELDS)
    path = PACKAGE / "src" / "osint_ingress" / "connectors" / "news_rss.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    hits = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs and re.search(r"creator|author|encoded|purl\.org/dc", n.value)]
    assert not hits, hits


def test_the_reviewed_feeds():
    """The feeds verified from this box on 2026-10-30 (README "Sources"): English, Marathi and Hindi."""
    assert {f.id for f in FEEDS} == {
        "toi_mumbai", "ht_mumbai", "midday_mumbai", "indianexpress_mumbai", "thehindu_mumbai", "fpj_mumbai",
        "mt_mumbai", "abpmajha_mumbai", "tv9marathi_mumbai", "abplive_hi_maharashtra", "tv9hindi_maharashtra"}
    langs = {f.id: f.language for f in FEEDS}
    assert {langs[i] for i in ("mt_mumbai", "abpmajha_mumbai", "tv9marathi_mumbai")} == {"mr"}
    assert {langs[i] for i in ("abplive_hi_maharashtra", "tv9hindi_maharashtra")} == {"hi"}
    assert all(f.url.startswith("https://") for f in FEEDS)
    # a state-wide feed is kept to the items that name Mumbai; every other feed to its Mumbai section
    assert all(f.require_city == (langs[f.id] == "hi") for f in FEEDS)
    assert all(f.sections for f in FEEDS)


# ── the service's own constants ──────────────────────────────────────────────────────────────────────────────


def test_city_constants_follow_the_city_pack():
    city = json.loads((REPO / "cities" / "mumbai" / "city.json").read_text(encoding="utf-8"))
    box = city["bbox"]
    assert CITY_BBOX == (box["south"], box["north"], box["west"], box["east"])
    for name in ("Mumbai", "Bombay, Maharashtra, India", "Mumbai Suburban", "Greater Mumbai", "Brihanmumbai"):
        assert CITY_RE.search(name)
    for name in ("Navi Mumbai, Maharashtra, India", "Pune", "Bombay High Court"):
        assert not CITY_RE.search(name), name


def test_connectors_cover_every_source_and_the_user_agent_names_mumbai():
    assert set(CONNECTOR_NAMES) == set(SOURCE_NAMES)
    assert "Mumbai" in USER_AGENT and "sajag-osint-ingress/" in USER_AGENT


#: SHA-256 prefixes (16 hex) of the lower-cased words that must not appear in this service: the previous city and
#: state, its capital, the previous product's name, other companies' products and event words (kept as hashes so
#: this test does not write them either).
_BANNED_WORD_HASHES = frozenset({
    "0f31e6ebe465b032",
    "13ed070478ef62c3",
    "1fff55ae51b6ec52",
    "2cfc5335969c9228",
    "74c860f63661b29c",
    "866e67fdbbb6917d",
    "a56f3dbc3053cc78",
    "f5dd232ee6b02958",
})


def test_the_service_names_no_previous_city_or_other_product():
    import hashlib

    files = [*sorted((PACKAGE / "src").rglob("*.py")), *sorted((PACKAGE / "tests").rglob("*.py")),
             *sorted((PACKAGE / "tests" / "fixtures").rglob("*.json")), PACKAGE / "README.md",
             PACKAGE / "pyproject.toml"]
    hits = sorted({
        f"{p.relative_to(PACKAGE)}:{n}"
        for p in files
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        for word in re.findall(r"[A-Za-z]+", line)
        if hashlib.sha256(word.lower().encode()).hexdigest()[:16] in _BANNED_WORD_HASHES
    })
    assert not hits, hits


def test_a_mumbai_section_item_carries_the_city_area_hint():
    """An item filed in an outlet's Mumbai section is city evidence for the geo-resolver (area:mumbai); a
    Maharashtra section item is state-level (area:maharashtra); an article slug is not a section."""
    from osint_ingress.connectors.news_rss import section_area_hint

    assert section_area_hint("https://timesofindia.indiatimes.com/city/mumbai/x/articleshow/1.cms") == ["area:mumbai"]
    assert section_area_hint("https://www.hindustantimes.com/cities/mumbai-news/x-101.html") == ["area:mumbai"]
    assert section_area_hint("https://maharashtratimes.com/maharashtra/mumbai-news/x/articleshow/1.cms") == [
        "area:mumbai"]
    assert section_area_hint("https://www.abplive.com/states/maharashtra/x-123") == ["area:maharashtra"]
    assert section_area_hint("https://www.abplive.com/news/mumbai-rain-123") == []  # a slug, not a section
    assert section_area_hint("") == []


def test_the_protect_set_reads_the_city_pack():
    """The redactor's protect-set holds the city pack's place names (landmarks, and the gazetteer once it lands: the
    second pack shows that path) and Mumbai's places named after people; Marathi spellings stop the Indic cue rules."""
    from osint_ingress.connectors._protect import city_indic_places, city_pack_phrases

    mumbai = city_pack_phrases("mumbai")
    assert {"hindmata", "csmt", "chhatrapati shivaji maharaj terminus", "shivaji park", "senapati bapat marg",
            "bhulabhai desai road", "p d mello road"} <= mumbai
    kolkata = city_pack_phrases("kolkata")  # read from that pack's gazetteer.json "places"
    assert "behala" in kolkata and "hindmata" not in kolkata and "senapati bapat marg" not in kolkata
    assert {"दादर", "हिंदमाता"} <= city_indic_places("mumbai")
