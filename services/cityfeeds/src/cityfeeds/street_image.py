"""A public street-level photograph near a junction (Mapillary), for the road-state feature's stills.

With ``MAPILLARY_TOKEN`` (free: https://www.mapillary.com/dashboard/developers, a client token) the Mapillary Graph
API is asked for the images within a 150 m box round a point (``/images?bbox=…``); the nearest one is returned with
its thumbnail URL, capture time, compass angle and the attribution its licence requires. Without the token no call
is made and the answer says ``needs MAPILLARY_TOKEN``.

* **Licence.** Mapillary images are CC BY-SA 4.0. The attribution returned is "© Mapillary contributors, CC BY-SA
  4.0" with the image's own page on mapillary.com, where the contributor is credited; the contributor's user name
  is not fetched (places, not people).
* **Privacy.** Mapillary blurs faces and number plates before it publishes an image. Sajag stores nothing: the
  answer is a link to Mapillary's own thumbnail.
* **Honest label.** A Mapillary image is a past photograph, labelled "Reference photo · not live" with its capture
  date. This module never calls the vision model; the road-state feature decides what to do with the still.
* **Polite.** Lookups are cached per point (rounded to ~100 m) for 24 hours, at most 500 calls a day.
* **The photo's bytes** (:meth:`StreetImages.photo`, for ``GET /feeds/street-image.jpg``). The deck's pages load
  images from their own origin only, so the road-state panel gets the photo through here, fetched server-side under
  fixed rules: only the ``thumb_1024_url`` the Graph API returned; only over https from Mapillary's CDN hosts
  (``PHOTO_HOST``, Meta's ``scontent…fbcdn.net``); redirects followed by hand, at most two, and only to those hosts;
  at most ``PHOTO_MAX_BYTES``; ``image/jpeg`` or ``image/png`` whose leading bytes match; 8 s in all; never the
  token (it rides only on the Graph API request). The bytes stay in memory: the last 12 photos for 30 minutes,
  nothing on disk, at most 500 photo fetches a day.
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from cityfeeds.geo import haversine_km

__all__ = ["GRAPH_URL", "PHOTO_HOST", "PHOTO_MAX_BYTES", "SEARCH_HALF_SIDE_M", "PhotoRefused", "StreetImages", "fetch_photo",
           "parse_images", "photo_host_ok"]

GRAPH_URL = "https://graph.mapillary.com/images"
_FIELDS = "id,thumb_1024_url,thumb_256_url,captured_at,compass_angle,computed_geometry,geometry,is_pano"
#: half the side of the box searched round a point: in Mumbai 16 of 18 sampled modelled camera sites had a public photo
#: within 150 m (most within 20 m; measured 30 Oct 2026); the panel shows how far the photo is
SEARCH_HALF_SIDE_M = 150.0
#: the Graph API returns a box's images in no particular order, so ask for enough to hold the nearest
_SEARCH_LIMIT = 500
_TTL_SEC = 24 * 3600
_MAX_PER_DAY = 500
_MAX_CACHE = 500

#: Mapillary serves its thumbnails from Meta's CDN: scontent-<pop>.xx.fbcdn.net or scontent.<pop>.fna.fbcdn.net
PHOTO_HOST = re.compile(r"scontent(?:[.-][a-z0-9-]+)*\.fbcdn\.net")
PHOTO_MAX_BYTES = 4 * 1024 * 1024
_PHOTO_DEADLINE_SEC = 8.0
_PHOTO_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
_PHOTO_MAX_REDIRECTS = 2
_PHOTO_TTL_SEC = 30 * 60
_PHOTO_MAX_CACHE = 12
_MAX_PHOTOS_PER_DAY = 500
#: the only types passed on, each with the leading bytes its body must start with
_MAGIC = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n"}


def _bbox(lat: float, lon: float, half_m: float = SEARCH_HALF_SIDE_M) -> str:
    dlat = half_m / 111_320.0
    dlon = half_m / (111_320.0 * max(0.1, math.cos(math.radians(lat))))
    return f"{lon - dlon:.6f},{lat - dlat:.6f},{lon + dlon:.6f},{lat + dlat:.6f}"


def parse_images(body: dict[str, Any] | None, lat: float, lon: float) -> dict[str, Any] | None:
    """The nearest non-panoramic image (a panorama does not show one approach), as the public answer."""
    best = None
    for im in (body or {}).get("data") or []:
        if not isinstance(im, dict) or im.get("is_pano") or not im.get("thumb_1024_url"):
            continue
        g = im.get("computed_geometry") or im.get("geometry") or {}
        try:
            ilon, ilat = float(g["coordinates"][0]), float(g["coordinates"][1])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        d = haversine_km(lat, lon, ilat, ilon) * 1000
        if best is None or d < best[0]:
            best = (d, im, ilat, ilon)
    if best is None:
        return None
    d, im, ilat, ilon = best
    cap = im.get("captured_at")
    captured = datetime.fromtimestamp(cap / 1000, UTC).isoformat() if isinstance(cap, (int, float)) else None
    iid = str(im.get("id"))
    return {
        "id": iid, "thumb_url": im.get("thumb_1024_url"), "thumb_small_url": im.get("thumb_256_url"),
        "captured_at": captured, "compass_angle": im.get("compass_angle"),
        "lat": round(ilat, 6), "lon": round(ilon, 6), "distance_m": round(d),
        "page_url": f"https://www.mapillary.com/app/?pKey={iid}",
        "label": "Reference photo · not live",
        "attribution": "© Mapillary contributors, CC BY-SA 4.0 (faces and number plates blurred by Mapillary)",
        "licence": "CC BY-SA 4.0", "licence_url": "https://creativecommons.org/licenses/by-sa/4.0/",
    }


class PhotoRefused(RuntimeError):
    """The CDN gave nothing this service passes on (host, redirect, status, size, type); ``status`` is the CDN's
    HTTP status when it answered with an error."""

    def __init__(self, reason: str, status: int | None = None) -> None:
        super().__init__(reason)
        self.status = status


def _url(url: str) -> httpx.URL | None:
    try:
        return httpx.URL(url)
    except (TypeError, ValueError, httpx.InvalidURL):
        return None


def photo_host_ok(url: str) -> bool:
    """https, the default port, no user info, and a Mapillary CDN host (``PHOTO_HOST``, matched in full)."""
    u = _url(url)
    return (u is not None and u.scheme == "https" and u.port in (None, 443) and not u.userinfo
            and bool(PHOTO_HOST.fullmatch(u.host)))


async def fetch_photo(client: httpx.AsyncClient, url: str) -> tuple[bytes, str]:
    """One thumbnail under the rules in the module docstring: ``(body, content_type)``, or :class:`PhotoRefused`
    (never a partial or unchecked body)."""
    try:
        async with asyncio.timeout(_PHOTO_DEADLINE_SEC):
            for _hop in range(_PHOTO_MAX_REDIRECTS + 1):
                if not photo_host_ok(url):
                    u = _url(url)
                    raise PhotoRefused(f"not a Mapillary CDN address ({u.scheme}://{u.host})" if u and u.host
                                       else "not a Mapillary CDN address")
                async with client.stream("GET", url, follow_redirects=False, timeout=_PHOTO_TIMEOUT,
                                         headers={"accept": "image/jpeg, image/png"}) as r:
                    if r.is_redirect:
                        loc = r.headers.get("location")
                        if not loc:
                            raise PhotoRefused("a redirect without a location", r.status_code)
                        url = str(r.url.join(loc))
                        continue
                    if r.status_code != 200:
                        raise PhotoRefused(f"HTTP {r.status_code} from the Mapillary CDN", r.status_code)
                    ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
                    if ctype not in _MAGIC:
                        raise PhotoRefused(f"not a JPEG or PNG ({ctype or 'no content type'})")
                    size = r.headers.get("content-length", "")
                    if size.isdigit() and int(size) > PHOTO_MAX_BYTES:
                        raise PhotoRefused(f"larger than {PHOTO_MAX_BYTES} bytes")
                    buf = bytearray()
                    async for chunk in r.aiter_bytes():
                        buf += chunk
                        if len(buf) > PHOTO_MAX_BYTES:
                            raise PhotoRefused(f"larger than {PHOTO_MAX_BYTES} bytes")
                    if not buf.startswith(_MAGIC[ctype]):
                        raise PhotoRefused(f"the body is not a {ctype}")
                    return bytes(buf), ctype
            raise PhotoRefused(f"more than {_PHOTO_MAX_REDIRECTS} redirects")
    except TimeoutError:
        raise PhotoRefused(f"no complete answer within {_PHOTO_DEADLINE_SEC:.0f} s") from None


class StreetImages:
    """Per-point cache in front of the Graph API, and the short photo cache (module docstring)."""

    def __init__(self, clock=time.time) -> None:
        self._cache: dict[tuple[float, float], tuple[float, dict[str, Any] | None]] = {}
        self._photos: dict[str, tuple[float, bytes, str]] = {}
        self._clock = clock
        self._day = ""
        self._calls = {"lookup": 0, "photo": 0}

    def _admit(self, kind: str, cap: int) -> None:
        day = datetime.fromtimestamp(self._clock(), UTC).date().isoformat()
        if day != self._day:
            self._day, self._calls = day, {"lookup": 0, "photo": 0}
        if self._calls[kind] >= cap:
            raise RuntimeError(f"daily cap reached ({cap} Mapillary {kind}s)")
        self._calls[kind] += 1

    async def near(self, client: httpx.AsyncClient, token: str, lat: float, lon: float,
                   fresh: bool = False) -> dict[str, Any]:
        """The nearest image to a point (cached 24 h per point; ``fresh`` asks again past the cache)."""
        k = (round(lat, 3), round(lon, 3))
        now = self._clock()
        hit = self._cache.get(k)
        if hit and now - hit[0] < _TTL_SEC and not fresh:
            return {"image": hit[1], "cached": True}
        self._admit("lookup", _MAX_PER_DAY)
        r = await client.get(GRAPH_URL, params={"bbox": _bbox(lat, lon), "fields": _FIELDS, "limit": _SEARCH_LIMIT},
                             headers={"Authorization": f"OAuth {token}"})
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} from Mapillary")
        img = parse_images(r.json(), lat, lon)
        if len(self._cache) >= _MAX_CACHE and k not in self._cache:
            self._cache.pop(next(iter(self._cache)))
        self._cache[k] = (now, img)
        return {"image": img, "cached": False}

    async def photo(self, client: httpx.AsyncClient, image: dict[str, Any]) -> dict[str, Any]:
        """The bytes of ``image`` (a :func:`parse_images` answer), from the photo cache or :func:`fetch_photo`."""
        iid = str(image.get("id"))
        now = self._clock()
        hit = self._photos.get(iid)
        if hit and now - hit[0] < _PHOTO_TTL_SEC:
            return {"body": hit[1], "content_type": hit[2], "cached": True}
        self._admit("photo", _MAX_PHOTOS_PER_DAY)
        body, ctype = await fetch_photo(client, str(image.get("thumb_url") or ""))
        for old in [i for i, v in self._photos.items() if now - v[0] >= _PHOTO_TTL_SEC or i == iid]:
            del self._photos[old]
        while len(self._photos) >= _PHOTO_MAX_CACHE:
            self._photos.pop(next(iter(self._photos)))
        self._photos[iid] = (now, body, ctype)
        return {"body": body, "content_type": ctype, "cached": False}
