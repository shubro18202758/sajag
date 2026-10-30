"""Rebuild the road-state test images from Wikimedia Commons.

    python prepare_fixtures.py            # needs network and Pillow

Downloads each source file's 1280 px rendition, pixelates every visible face
and legible number plate (boxes below, as fractions of width/height), resizes
to at most 1024 px wide and writes ``<id>.jpg`` next to this script. EXIF is
not copied. ``labels.json`` holds the expected road state and the credit for
each image; NOTICE.md is the human-readable credit list.

The masking is ours: the originals are unchanged on Commons. Nothing here is
used at test time except the resulting JPEGs and labels.json.
"""

from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "SajagTestFixtures/0.1 (on-prem road-state tests; https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)"}


def _get(url: str, timeout: float = 60) -> bytes:
    for attempt in range(6):  # Commons rate-limits bursts (HTTP 429)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 5:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def _thumb_url(title: str) -> str:
    q = {"action": "query", "titles": title, "prop": "imageinfo", "iiprop": "url",
         "iiurlwidth": 1280, "format": "json"}
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q)
    page = next(iter(json.loads(_get(url, 30))["query"]["pages"].values()))
    return page["imageinfo"][0]["thumburl"]


def _pixelate(img, box_frac, block: int = 10):
    w, h = img.size
    x0, y0, x1, y1 = (int(box_frac[0] * w), int(box_frac[1] * h),
                      int(box_frac[2] * w), int(box_frac[3] * h))
    region = img.crop((x0, y0, x1, y1))
    small = region.resize((max(1, (x1 - x0) // block), max(1, (y1 - y0) // block)))
    img.paste(small.resize(region.size), (x0, y0))


def main() -> None:
    from PIL import Image

    labels = json.loads((HERE / "labels.json").read_text(encoding="utf-8"))
    force = "--force" in sys.argv
    for item in labels["images"]:
        if (HERE / item["file"]).exists() and not force:
            continue
        img = Image.open(io.BytesIO(_get(_thumb_url(item["title"])))).convert("RGB")
        time.sleep(2)
        for box in item.get("masked", []):
            _pixelate(img, box)
        if img.width > 1024:
            img = img.resize((1024, round(img.height * 1024 / img.width)), Image.LANCZOS)
        img.save(HERE / item["file"], "JPEG", quality=85, optimize=True)
        print(item["file"], img.size)


if __name__ == "__main__":
    main()
