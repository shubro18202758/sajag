from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from forecast.config import Settings
from forecast.models import QuantileForecast, SeasonalNaive, SeriesInput
from forecast.network import load_network

#: a fixed origin inside the SIMULATED history (a Wednesday evening, IST 18:00)
ORIGIN = datetime(2026, 10, 28, 12, 30, tzinfo=UTC)


class RampModel:
    """A deterministic stand-in for the foundation model: the median ramps from the last value by +0.03 a
    step; a ±0.05 band."""

    name = "ramp-test-model"
    licence = "test"

    def __init__(self) -> None:
        self.calls = 0

    def predict(self, inputs: list[SeriesInput], horizon: int) -> list[QuantileForecast]:
        self.calls += 1
        out = []
        for i in inputs:
            p50 = float(i.target[-1]) + 0.03 * np.arange(1, horizon + 1)
            out.append(QuantileForecast(p50 - 0.05, p50, p50 + 0.05))
        return out


class BrokenModel:
    name = "broken"
    licence = "test"

    def predict(self, inputs, horizon):
        raise RuntimeError("weights not available")


@pytest.fixture(scope="session")
def net():
    return load_network(None)


@pytest.fixture
def settings():
    return Settings(data_source="synthetic", contender="", backtest_days=1, backtest_stride_hours=12,
                    context_days=7)


@pytest.fixture
def naive():
    return SeasonalNaive()


#: a hand-made Mumbai mini network (landmarks.json coordinates) for the calendar and flood-spot tests,
#: independent of the network stream's ids
_MINI = {
    "junctions": [
        {"junction_id": 1, "key": "lalbaug", "name": "Lalbaug", "lat": 18.9935, "lon": 72.8355},
        {"junction_id": 2, "key": "hindmata", "name": "Hindmata (Dadar East)", "name_mr": "हिंदमाता (दादर पूर्व)",
         "lat": 19.0049, "lon": 72.8424},
        {"junction_id": 3, "key": "dadar_tt", "name": "Dadar TT Circle", "name_mr": "दादर टीटी सर्कल",
         "lat": 19.0176, "lon": 72.848},
        {"junction_id": 4, "key": "girgaon_chowpatty", "name": "Girgaon Chowpatty", "lat": 18.9548,
         "lon": 72.8136},
        {"junction_id": 5, "key": "churchgate", "name": "Churchgate", "lat": 18.9353, "lon": 72.8274},
        {"junction_id": 6, "key": "wankhede", "name": "Wankhede Stadium", "lat": 18.9389, "lon": 72.8258},
        {"junction_id": 7, "key": "powai", "name": "Powai (JVLR)", "lat": 19.1176, "lon": 72.906},
        {"junction_id": 8, "key": "ghatkopar", "name": "Ghatkopar", "lat": 19.086, "lon": 72.9081},
    ],
    "segments": [
        {"segment_id": 9001, "road_name": "Dr Ambedkar Road", "from_junction": 1, "to_junction": 2,
         "road_class": "primary", "lanes": 4, "speed_limit_kmh": 40, "length_m": 1500,
         "line": [[72.8355, 18.9935], [72.839, 18.9992], [72.8424, 19.0049]]},
        {"segment_id": 9002, "road_name": "Dr Ambedkar Road", "from_junction": 2, "to_junction": 3,
         "road_class": "primary", "lanes": 4, "speed_limit_kmh": 40, "length_m": 1500,
         "line": [[72.8424, 19.0049], [72.8452, 19.0112], [72.848, 19.0176]]},
        {"segment_id": 9003, "road_name": "Lalbaug–Girgaon procession road", "from_junction": 1,
         "to_junction": 4, "road_class": "secondary", "lanes": 2, "speed_limit_kmh": 30, "length_m": 5000,
         "line": [[72.8355, 18.9935], [72.8245, 18.974], [72.8136, 18.9548]]},
        {"segment_id": 9004, "road_name": "D Road", "from_junction": 5, "to_junction": 6,
         "road_class": "secondary", "lanes": 2, "speed_limit_kmh": 30, "length_m": 500,
         "line": [[72.8274, 18.9353], [72.8266, 18.9371], [72.8258, 18.9389]]},
        {"segment_id": 9005, "road_name": "Jogeshwari–Vikhroli Link Road", "from_junction": 7,
         "to_junction": 8, "road_class": "primary", "lanes": 6, "speed_limit_kmh": 50, "length_m": 3600,
         "line": [[72.906, 19.1176], [72.907, 19.1018], [72.9081, 19.086]]},
    ],
}


@pytest.fixture(scope="session")
def mini_net(tmp_path_factory):
    import json

    d = tmp_path_factory.mktemp("cities") / "mumbai_mini"
    d.mkdir()
    (d / "network.json").write_text(json.dumps(_MINI), encoding="utf-8")
    return load_network(d)
