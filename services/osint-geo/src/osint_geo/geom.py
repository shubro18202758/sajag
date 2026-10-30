"""Line geometry that the gazetteer generator shares with the snap (stdlib only).

:func:`interior_point` is the network anchor of a segment, ``ST_PointOnSurface`` of its line. The generator puts each
road entry on it, and :mod:`osint_geo.snap` measures residuals to it. It lives here, apart from ``snap`` (which needs
shapely, pyproj and numpy), so that ``scripts/gen_osint_gazetteer.py --check`` runs on the standard library alone.
``osint_geo.snap.interior_point`` re-exports it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

__all__ = ["interior_point"]


def interior_point(line: Sequence[Sequence[float]]) -> tuple[float, float]:
    """``ST_PointOnSurface`` of a line given as ``[[lon, lat], ...]``: GEOS InteriorPointLine, ported line for line
    so the committed gazetteer never depends on the installed GEOS (a test pins it to shapely's
    ``point_on_surface``). The interior vertex nearest the line's length-weighted centroid, in the coordinates as
    given (as PostGIS computes it on ``geometry(4326)``); the first of equals wins; with no interior vertex, the
    nearer endpoint."""
    pts = [(float(p[0]), float(p[1])) for p in line]
    if not pts:
        raise ValueError("an empty line has no interior point")
    total = sx = sy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        seg = math.sqrt((x1 - x0) * (x1 - x0) + (y1 - y0) * (y1 - y0))
        if seg == 0.0:
            continue
        total += seg
        sx += seg * ((x0 + x1) / 2)
        sy += seg * ((y0 + y1) / 2)
    cx, cy = (sx / total, sy / total) if total > 0.0 else pts[0]
    candidates = pts[1:-1] or [pts[0], pts[-1]]
    best = candidates[0]
    best_d = math.sqrt((best[0] - cx) * (best[0] - cx) + (best[1] - cy) * (best[1] - cy))
    for p in candidates[1:]:
        d = math.sqrt((p[0] - cx) * (p[0] - cx) + (p[1] - cy) * (p[1] - cy))
        if d < best_d:
            best, best_d = p, d
    return best
