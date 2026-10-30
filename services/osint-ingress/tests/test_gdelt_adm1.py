"""GDELT ADM1 for Maharashtra is the FIPS 10-4 code ``IN16`` (the census code 27 is not GDELT's), checked on a real
GDELT export read in place when the PoC's captures are present (they are global 15-minute slices, so they can hold
Mumbai rows); and the bulk parser reads only the export that ``lastupdate.txt`` names."""

from __future__ import annotations

import csv
import io
import shutil
import zipfile
from pathlib import Path

import pytest
from conftest import CAPTURE, POC_RAW, needs_poc

from osint_ingress.cache import Cache
from osint_ingress.connectors._area import GDELT_ADM1
from osint_ingress.connectors.base import CITY_BBOX, CITY_RE
from osint_ingress.connectors.gdelt import EVENT_COLUMNS, GdeltBulk
from osint_ingress.importer import import_capture

#: The real export the PoC's lastupdate.txt names (23:30 UTC on 23 Oct 2026): a global slice of 1,229 rows.
POC_2330 = POC_RAW / "20261023233000.export.CSV.zip"


def _rows(path: Path):
    with zipfile.ZipFile(path) as zf, zf.open(zf.namelist()[0]) as fh:
        yield from csv.reader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline=""),
                              delimiter="\t", quoting=csv.QUOTE_NONE)


@pytest.mark.skipif(not POC_2330.is_file(), reason="PoC capture 20261023233000.export.CSV.zip absent (CI)")
def test_every_mumbai_bbox_row_of_a_real_export_carries_in16():
    lat_i, lon_i, adm_i, name_i = (EVENT_COLUMNS[k] for k in (
        "action_geo_lat", "action_geo_long", "action_geo_adm1_code", "action_geo_fullname"))
    inside = []
    for row in _rows(POC_2330):
        if len(row) != 61 or not row[lat_i] or not row[lon_i]:
            continue
        lat, lon = float(row[lat_i]), float(row[lon_i])
        if CITY_BBOX[0] <= lat <= CITY_BBOX[1] and CITY_BBOX[2] <= lon <= CITY_BBOX[3]:
            inside.append((row[adm_i], row[name_i]))
    # every row inside the Greater Mumbai box is coded Maharashtra, and GDELT names the city "Bombay" or "Mumbai"
    assert all(adm == GDELT_ADM1 for adm, _name in inside), inside
    assert all(CITY_RE.search(name) for _adm, name in inside if name.count(",") >= 2), inside
    assert GDELT_ADM1 == "IN16"


def test_census_codes_are_never_used_as_gdelt_codes_in_the_source():
    """Maharashtra's census code is 27, but FIPS 10-4 ``IN27`` is not Maharashtra: GDELT's code for the state is
    IN16. (West Bengal's census 19 is FIPS ``IN19``, Karnataka: the second pack's trap.)"""
    src = Path(__file__).resolve().parents[1] / "src"
    for p in src.rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        assert "IN19" not in text and "IN27" not in text, p


def _extra_export(name: str) -> bytes:
    """A second export zip with a Mumbai row: present in the cache, but NOT named by lastupdate.txt."""
    row = [""] * 61
    row[0], row[26], row[28], row[51], row[52], row[53], row[54], row[56], row[57], row[59] = (
        "1399999999", "190", "19", "4", "Bombay, Maharashtra, India", "IN", "IN16", "18.975", "72.8258",
        "20261020114500")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name.removesuffix(".zip"), "\t".join(row) + "\n")
    return buf.getvalue()


def test_bulk_parser_reads_only_the_export_lastupdate_names(tmp_path, protect):
    src = tmp_path / "capture"
    shutil.copytree(CAPTURE, src)
    (src / "20261020114500.export.CSV.zip").write_bytes(_extra_export("20261020114500.export.CSV.zip"))
    import_capture(src, tmp_path / "cache")
    entry = Cache(tmp_path / "cache").latest("gdelt_events")
    assert entry.blobs == ("20261020120000.export.CSV.zip",)
    ids = {s.source_id for s in GdeltBulk().parse(entry, protect)}
    assert ids == {"1300000001", "1300000002"} and "1399999999" not in ids


@needs_poc
def test_a_real_export_yields_only_maharashtra_rows_with_their_levels(tmp_path, protect):
    """The PoC's lastupdate.txt names the 23:30 slice: whatever it holds of Maharashtra (IN16) is kept, the rows that
    name Mumbai as city hints, and no row of another state; the actor columns are never read (real shape, read in
    place)."""
    import_capture(POC_RAW, tmp_path / "cache")
    entry = Cache(tmp_path / "cache").latest("gdelt_events")
    assert entry.blobs == ("20261023233000.export.CSV.zip",)
    sigs = GdeltBulk().parse(entry, protect)
    assert {s.raw["action_geo_adm1_code"] for s in sigs} <= {"IN16"}
    city = [s for s in sigs if "area:mumbai" in s.category_hint]
    assert all("area:maharashtra" in s.category_hint for s in sigs if s not in city)
