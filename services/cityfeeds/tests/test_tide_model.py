"""The vendored tide model stays a byte-for-byte copy of the hydro service's, and it is the Apollo Bunder station."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from cityfeeds.tide_model import LABEL, TideModel

HERE = Path(__file__).resolve().parents[1] / "src" / "cityfeeds" / "tide_model.py"
HYDRO = Path(__file__).resolve().parents[2] / "hydro" / "src" / "hydro" / "tide.py"


def test_tide_model_is_a_copy_of_hydro():
    if HYDRO.is_file():  # the image ships cityfeeds alone
        assert HERE.read_text(encoding="utf-8") == HYDRO.read_text(encoding="utf-8"), \
            "cityfeeds/tide_model.py must stay a copy of services/hydro/src/hydro/tide.py"


def test_default_station_and_label():
    m = TideModel()
    assert m.station == "apollo_bunder" and LABEL == "MODELLED (approximate)"
    hw = [e for e in m.extremes(datetime(2025, 6, 26, 6, 0, tzinfo=ZoneInfo("Asia/Kolkata")), 12) if e.kind == "high"]
    assert hw and abs(hw[0].level_m - 4.75) <= 0.1  # the BMC's 26 June 2025 high water, 4.75 m at 12:55 IST
