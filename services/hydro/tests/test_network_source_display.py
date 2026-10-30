"""The network file is named repo-relative in answers, never by its absolute path (audit, 29 Oct).

``network.source`` went out in public, unauthenticated answers (/hydro/nowcast,
/forecast/segments, /health) as /home/<user>/…/cities/mumbai/network.json —
the host's user name included.
"""

from __future__ import annotations

import json
from pathlib import Path

from hydro.network import display_source, load_network

REPO = Path(__file__).resolve().parents[3]


def test_display_source_keeps_the_city_pack_path_only():
    assert display_source(Path("/home/someone/repo/cities/mumbai/network.json")) == \
        "cities/mumbai/network.json"
    assert display_source(Path("/srv/cities/x/cities/mumbai/network.json")) == \
        "cities/mumbai/network.json"
    assert display_source(Path("/opt/elsewhere/net.json")) == "net.json"


def test_loaded_city_network_names_no_absolute_path():
    net = load_network(REPO / "cities" / "mumbai")
    assert net.source == "cities/mumbai/network.json"
    assert not net.source.startswith("/") and str(Path.home()) not in net.source


def test_any_city_dir_is_named_relative(tmp_path):
    city = tmp_path / "cities" / "testcity"
    city.mkdir(parents=True)
    src = json.loads((REPO / "cities" / "mumbai" / "network.json").read_text(encoding="utf-8"))
    (city / "network.json").write_text(json.dumps(src), encoding="utf-8")
    assert load_network(city).source == "cities/testcity/network.json"
