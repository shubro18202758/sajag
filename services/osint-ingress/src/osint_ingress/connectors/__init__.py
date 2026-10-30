"""The connectors: one per ``RawOsintSignal.source``, each with ``fetch(client, cache)`` and
``parse(entry, protect)``.

=========================== ======================== ===================================================
source                      module                   endpoint (egress allow-list)
=========================== ======================== ===================================================
``sachet_cap``              :mod:`.official`         sachet.ndma.gov.in (the Maharashtra CAP RSS,
                                                     area-matched to the Mumbai districts, + CAP detail)
``imd``                     :mod:`.official`         cap-sources.s3.amazonaws.com (IMD CAP, WMO Alert Hub
                                                     mirror, kept to Maharashtra)
``google_news_rss``         :mod:`.google_news`      news.google.com (RSS search: English, Marathi, Hindi)
``news_rss``                :mod:`.news_rss`         the outlets' own feeds (TOI, HT, Mid-day, Indian
                                                     Express, The Hindu, FPJ, Maharashtra Times, ABP
                                                     Majha, TV9 Marathi, ABP Live, TV9 Bharatvarsh)
``gdelt_events``            :mod:`.gdelt`            data.gdeltproject.org (lastupdate.txt + export zip)
``gdelt_doc``               :mod:`.gdelt`            api.gdeltproject.org (DOC 2.0 ArtList, >= 5 s spacing)
``reddit_rss``              :mod:`.reddit`           www.reddit.com (r/mumbai Atom)
``kmc_scrape``              :mod:`.official`         disabled: the BMC portal has no notice list
``wbsdma``                  :mod:`.official`         disabled: Maharashtra SDMA alerts arrive via SACHET
``mumbai_police_scrape``   :mod:`.official`         mtperp.mahatrafficechallan.gov.in (Mumbai Traffic
                                                     Police public notices)
``common_crawl``            :mod:`.common_crawl`     index.commoncrawl.org + data.commoncrawl.org (backfill)
=========================== ======================== ===================================================
"""

from __future__ import annotations

from osint_ingress.connectors.base import Connector, ConnectorError
from osint_ingress.connectors.common_crawl import CommonCrawl
from osint_ingress.connectors.gdelt import GdeltBulk, GdeltDoc
from osint_ingress.connectors.google_news import GoogleNews
from osint_ingress.connectors.news_rss import NewsRss
from osint_ingress.connectors.official import BmcPage, Imd, MsdmaPage, MtpNotices, Sachet
from osint_ingress.connectors.reddit import Reddit
from osint_ingress.safe_http import RobotsCache

__all__ = ["Connector", "ConnectorError", "build_connectors"]


def build_connectors(*, robots: RobotsCache | None = None) -> dict[str, Connector]:
    """Every connector, keyed by source name, in the order a cycle runs them (official first)."""
    robots = robots or RobotsCache()
    conns: list[Connector] = [
        Sachet(),
        Imd(),
        GoogleNews(),
        NewsRss(robots),
        GdeltBulk(),
        GdeltDoc(),
        Reddit(),
        BmcPage(robots),
        MsdmaPage(robots),
        MtpNotices(robots),
        CommonCrawl(),
    ]
    return {c.name: c for c in conns}
