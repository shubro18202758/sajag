"""Image intake: type check, downscale, re-encode without metadata.

Only JPEG and PNG are accepted (magic bytes, not the Content-Type header).
With Pillow installed the image is decoded, downscaled to ``max_side`` and
re-encoded as a fresh JPEG, which also drops EXIF (camera serials, GPS).
Without Pillow (the offline test environment) a JPEG passes through as is.
Nothing is written to disk.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

__all__ = ["ImageError", "Prepared", "sniff", "prepare"]


class ImageError(ValueError):
    pass


@dataclass(frozen=True)
class Prepared:
    jpeg: bytes
    width: int | None
    height: int | None
    source_format: str
    resized: bool


def sniff(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    return "unknown"


def prepare(data: bytes, max_side: int = 1024) -> Prepared:
    if not data:
        raise ImageError("empty image")
    fmt = sniff(data)
    if fmt == "unknown":
        raise ImageError("send a JPEG or PNG image")
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        if fmt != "jpeg":
            raise ImageError("PNG needs Pillow on the server; send a JPEG") from None
        return Prepared(data, None, None, fmt, False)
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageError(f"could not decode image: {exc}") from exc
    if img.width * img.height > 80_000_000:
        raise ImageError("image too large")
    img = img.convert("RGB")
    resized = False
    if max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                         Image.LANCZOS)
        resized = True
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return Prepared(buf.getvalue(), img.width, img.height, fmt, resized)
