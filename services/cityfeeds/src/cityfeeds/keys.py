"""The free services that need a personal key, and how a key is read (never printed, logged or returned).

Each key is read from the process environment at call time (``~/.config/sajag/sajag.env`` reaches the service
through systemd's ``EnvironmentFile``), so a source goes live the moment its key is added and the service
restarts. Without its key a source makes no call at all and says ``needs <ENV_VAR>``.

A key never leaves this process except in the request to its own service: :func:`redact` scrubs every configured
key (and every URL query string) out of an error before it is stored or shown, and the ``httpx`` request log is kept
at WARNING so a URL carrying a key is never written to the journal.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

__all__ = ["KeyedSource", "KEYED", "key", "redact", "keyed_state"]

# the httpx INFO line prints the full request URL, which for WAQI, data.gov.in and FIRMS carries the key
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@dataclass(frozen=True)
class KeyedSource:
    id: str
    env: str
    what: str
    signup: str
    #: what runs without the key (None: the source is simply off)
    without_key: str | None = None


KEYED: dict[str, KeyedSource] = {k.id: k for k in (
    KeyedSource("waqi", "WAQI_TOKEN", "World Air Quality Index: observed AQI at the CPCB/MPCB stations it lists "
                "for Mumbai (US EPA scale, as WAQI publishes it)", "https://aqicn.org/data-platform/token/"),
    KeyedSource("openaq", "OPENAQ_API_KEY", "OpenAQ v3: the CPCB stations' own PM2.5 and PM10 (latest value and "
                "24-hour means); the indicative National AQI when data.gov.in has no key",
                "https://explore.openaq.org/register (then Account settings → API key)"),
    KeyedSource("cpcb", "DATA_GOV_IN_API_KEY", "data.gov.in, CPCB real-time air quality index: observed "
                "pollutant averages at every CAAQMS station in Mumbai (the National AQI's own inputs)",
                "https://data.gov.in/ (sign in; the key is under My Account)",
                without_key="OpenAQ carries the same CPCB station data (OPENAQ_API_KEY): the National AQI is taken "
                            "from its 24-hour means instead"),
    KeyedSource("firms", "FIRMS_MAP_KEY", "NASA FIRMS area API: the last 2 days of VIIRS and MODIS hotspots in the "
                "Mumbai box", "https://firms.modaps.eosdis.nasa.gov/api/map_key/",
                without_key="the public FIRMS South Asia 24-hour files (live, no key) are read instead"),
    KeyedSource("mapillary", "MAPILLARY_TOKEN", "Mapillary: a public street-level photo near a point "
                "(CC BY-SA 4.0; faces and plates blurred by Mapillary)", "https://www.mapillary.com/dashboard/developers"),
)}


def key(source: str) -> str | None:
    """The key for ``source`` from the environment, or ``None`` when it is unset or blank."""
    v = os.environ.get(KEYED[source].env, "").strip()
    return v or None


_QUERY = re.compile(r"(https?://[^\s'\"?]+)\?[^\s'\"]*")


def redact(text: str | None) -> str | None:
    """``text`` without any configured key and without URL query strings (an error may quote the URL)."""
    if not text:
        return text
    out = _QUERY.sub(r"\1?…", text)
    for ks in KEYED.values():
        v = os.environ.get(ks.env, "").strip()
        if len(v) >= 4:
            out = out.replace(v, f"<{ks.env}>")
    return out


def keyed_state(source: str, *, error: str | None = None, live: bool | None = None) -> str:
    """``needs <ENV>`` without a key; ``error: <reason>`` after a failure; ``live`` once it answered."""
    if key(source) is None:
        return f"needs {KEYED[source].env}"
    if error:
        return f"error: {redact(error)}"
    return "live" if live else "configured (no answer yet)"
