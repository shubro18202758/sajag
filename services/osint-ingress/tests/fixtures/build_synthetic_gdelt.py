#!/usr/bin/env python3
"""Rebuild the SYNTHETIC GDELT files of ``capture/`` (deterministic): ``20261020120000.export.CSV.zip`` (3 rows
in the real 61-column GDELT 2.0 Events schema) and ``gdelt_lastupdate_live.txt`` (naming that zip with its real
size and MD5, plus mentions/GKG lines that point at nothing).

Every value is synthetic. The actor columns carry SENTINEL strings that the parser must never read (Actor1/Actor2
names, codes and geographies); ``test_connectors.py`` asserts no sentinel reaches a signal. The rows:

1. a Mumbai row (``ActionGeo_FullName`` "Bombay, Maharashtra, India", GDELT's own spelling: a city hint; ADM1
   ``IN16``, inside the Greater Mumbai bbox) — kept;
2. a Pune row (ADM1 ``IN16``, outside the Mumbai bbox: a state hint only) — kept;
3. a Kolkata row (ADM1 ``IN28``, another state, outside the bbox) — filtered out.

Usage: ``python tests/fixtures/build_synthetic_gdelt.py [--check]`` (``--check`` exits 1 when the committed files
differ from what this script builds).
"""

from __future__ import annotations

import hashlib
import io
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPTURE = HERE / "capture"
STAMP = "20261020120000"
EXPORT_NAME = f"{STAMP}.export.CSV.zip"
SENTINELS = ("SENTINEL ACTOR ALPHA", "SENTINEL ACTOR BETA", "Sentinel Actorpur One", "Sentinel Actorpur Two")


def _row(
    event_id: str,
    *,
    code: str,
    root: str,
    quad: str,
    goldstein: str,
    tone: str,
    geo_type: str,
    fullname: str,
    adm1: str,
    lat: str,
    lon: str,
    feature: str,
    url: str,
) -> list[str]:
    r = [""] * 61
    r[0], r[1], r[2], r[3], r[4] = event_id, "20261020", "202610", "2026", "2026.7973"
    # Actor1 (5-14) and Actor2 (15-24): SENTINELS, never read by the parser
    r[5], r[6], r[7], r[12] = "INDGOV", SENTINELS[0], "IND", "GOV"
    r[15], r[16], r[17], r[22] = "INDCVL", SENTINELS[1], "IND", "CVL"
    r[25], r[26], r[27], r[28], r[29], r[30] = "1", code, code[:3], root, quad, goldstein
    r[31], r[32], r[33], r[34] = "4", "2", "4", tone
    # Actor1Geo (35-42) and Actor2Geo (43-50): SENTINELS too
    r[35:43] = ["4", f"{SENTINELS[2]}, Maharashtra, India", "IN", "IN16", "", "19.0", "72.8", "-1"]
    r[43:51] = ["4", f"{SENTINELS[3]}, Maharashtra, India", "IN", "IN16", "", "19.1", "72.9", "-2"]
    # ActionGeo (51-58), DATEADDED (59), SOURCEURL (60)
    r[51:59] = [geo_type, fullname, "IN", adm1, "", lat, lon, feature]
    r[59], r[60] = f"{STAMP}", url
    return r


ROWS = [
    _row("1300000001", code="010", root="01", quad="1", goldstein="0.0", tone="-1.5", geo_type="4",
         fullname="Bombay, Maharashtra, India", adm1="IN16", lat="18.975", lon="72.8258", feature="-2097130",
         url="https://news-a.example/city/mumbai/civic-statement-synthetic"),
    _row("1300000002", code="040", root="04", quad="1", goldstein="1.0", tone="0.8", geo_type="4",
         fullname="Pune, Maharashtra, India", adm1="IN16", lat="18.5196", lon="73.8553", feature="-2108361",
         url="https://news-b.example/state/pune-consultation-synthetic"),
    _row("1300000003", code="043", root="04", quad="1", goldstein="2.8", tone="1.2", geo_type="4",
         fullname="Calcutta, West Bengal, India", adm1="IN28", lat="22.5697", lon="88.3697", feature="-2103872",
         url="https://news-a.example/national/another-city-meeting-synthetic"),
]


def export_csv() -> bytes:
    return ("".join("\t".join(r) + "\n" for r in ROWS)).encode("utf-8")


def export_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo(f"{STAMP}.export.CSV", date_time=(2026, 10, 20, 12, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = 0o644 << 16
        zf.writestr(info, export_csv())
    return buf.getvalue()


def lastupdate(zip_bytes: bytes) -> str:
    md5 = hashlib.md5(zip_bytes, usedforsecurity=False).hexdigest()
    fake = {k: hashlib.md5(f"synthetic-{k}".encode(), usedforsecurity=False).hexdigest() for k in ("m", "g")}
    return (
        f"{len(zip_bytes)} {md5} http://data.gdeltproject.org/gdeltv2/{EXPORT_NAME}\n"
        f"1024 {fake['m']} http://data.gdeltproject.org/gdeltv2/{STAMP}.mentions.CSV.zip\n"
        f"2048 {fake['g']} http://data.gdeltproject.org/gdeltv2/{STAMP}.gkg.csv.zip\n"
    )


def main(argv: list[str]) -> int:
    check = "--check" in argv
    zpath, lpath = CAPTURE / EXPORT_NAME, CAPTURE / "gdelt_lastupdate_live.txt"
    if check:
        with zipfile.ZipFile(zpath) as zf:
            same_csv = zf.read(f"{STAMP}.export.CSV") == export_csv()
        same_lu = lpath.read_text(encoding="utf-8") == lastupdate(zpath.read_bytes())
        print("synthetic GDELT capture:", "ok" if (same_csv and same_lu) else "DIFFERS")
        return 0 if (same_csv and same_lu) else 1
    data = export_zip()
    zpath.write_bytes(data)
    lpath.write_text(lastupdate(data), encoding="utf-8")
    print(f"wrote {zpath.name} ({len(data)} bytes) and {lpath.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
